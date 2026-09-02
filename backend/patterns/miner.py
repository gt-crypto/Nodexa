"""Deterministic, explainable Pattern Miner engine for Nodal Sentinel exceptions."""
import hashlib
import json
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy import select, delete
from sqlalchemy.orm import Session

from backend.config import settings
from backend.models.exceptions import ExceptionRecord
from backend.models.cluster import ExceptionCluster
from backend.models.audit import AuditEvent
from backend.models.enums import TransitionActorType
from backend.patterns.signatures import PatternSignature, PatternExtractionService

PATTERN_MINER_VERSION = "v2.0"


def generate_cluster_id(cluster_key: str) -> str:
    """Generates a stable, deterministic cluster ID based on the grouping key."""
    h = hashlib.sha256(cluster_key.encode("utf-8")).hexdigest()[:16]
    return f"cl_{h}"


def format_family_label(family: str) -> str:
    """Converts UPPER_SNAKE_CASE family into title case."""
    return family.replace("_", " ").title()


class PatternMinerService:
    """Deterministic analytics engine extracting recurring patterns across exceptions."""

    def __init__(self, min_cluster_size: Optional[int] = None):
        self.min_cluster_size = (
            min_cluster_size
            if min_cluster_size is not None
            else getattr(settings, "pattern_miner_min_cluster_size", 2)
        )

    def mine_patterns(
        self,
        session: Session,
        min_cluster_size: Optional[int] = None,
        persist: bool = True,
        actor_id: str = "pattern_miner_v2",
        request_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Executes deterministic pattern clustering over operational exception records.

        Returns a list of structured cluster dictionaries and idempotently updates
        persisted ExceptionCluster records if persist=True.
        """
        effective_min_size = min_cluster_size if min_cluster_size is not None else self.min_cluster_size
        
        # 1. Extract signatures for all persisted exceptions
        signatures = PatternExtractionService.extract_all_signatures(session)
        if not signatures:
            if persist:
                session.execute(delete(ExceptionCluster))
                session.flush()
            return []

        # 2. Group into candidate clusters along deterministic dimensions
        raw_clusters: Dict[str, Dict[str, Any]] = {}

        # ── Dimension A: Family + Operational Anomaly Signature ─────────────
        family_groups = defaultdict(list)
        for sig in signatures:
            method_str = sig.payment_method or "GENERAL"
            key = f"FAMILY:{sig.exception_type}:{method_str}"
            family_groups[key].append(sig)

        for key, members in family_groups.items():
            if len(members) >= effective_min_size:
                parts = key.split(":")
                fam = parts[1]
                meth = parts[2]
                fam_label = format_family_label(fam)
                label = f"Recurring {fam_label} ({meth})" if meth != "GENERAL" else f"Recurring {fam_label}"
                desc = (
                    f"{len(members)} exceptions share the {fam} operational anomaly signature "
                    f"under payment method '{meth}'."
                )
                raw_clusters[key] = {
                    "cluster_key": key,
                    "pattern_type": "FAMILY_SIGNATURE",
                    "pattern_label": label,
                    "description": desc,
                    "members": members,
                    "matched_fields": ["exception_type", "payment_method"],
                    "signature": {"exception_type": fam, "payment_method": meth},
                    "reason": f"Same exception family ({fam}) and identical operational payment method ({meth}).",
                }

        # ── Dimension B: Merchant Repeated Exception Signature ─────────────
        merchant_groups = defaultdict(list)
        for sig in signatures:
            if sig.merchant_id:
                key = f"MERCHANT:{sig.merchant_id}:{sig.exception_type}"
                merchant_groups[key].append(sig)

        for key, members in merchant_groups.items():
            if len(members) >= effective_min_size:
                parts = key.split(":")
                merch = parts[1]
                fam = parts[2]
                fam_label = format_family_label(fam)
                raw_clusters[key] = {
                    "cluster_key": key,
                    "pattern_type": "MERCHANT_REPEATED_FAMILY",
                    "pattern_label": f"Repeated {fam_label} for Merchant {merch}",
                    "description": f"Merchant '{merch}' has {len(members)} recurring {fam_label} exceptions.",
                    "members": members,
                    "matched_fields": ["merchant_id", "exception_type"],
                    "signature": {"merchant_id": merch, "exception_type": fam},
                    "reason": f"Identical merchant ({merch}) experiencing repeated {fam} anomalies.",
                }

        # ── Dimension C: Shared Invariant Control Violations ────────────────
        control_groups = defaultdict(list)
        for sig in signatures:
            for ccode in sig.control_codes:
                key = f"CONTROL:{ccode}:{sig.exception_type}"
                control_groups[key].append(sig)

        for key, members in control_groups.items():
            # Deduplicate members if exception was added multiple times
            dedup_members = list({m.exception_id: m for m in members}.values())
            if len(dedup_members) >= effective_min_size:
                parts = key.split(":")
                ccode = parts[1]
                fam = parts[2]
                fam_label = format_family_label(fam)
                raw_clusters[key] = {
                    "cluster_key": key,
                    "pattern_type": "CONTROL_FINDING_SIGNATURE",
                    "pattern_label": f"Invariant Violation {ccode} ({fam_label})",
                    "description": f"{len(dedup_members)} cases failed invariant control check '{ccode}'.",
                    "members": dedup_members,
                    "matched_fields": ["control_code", "exception_type"],
                    "signature": {"control_code": ccode, "exception_type": fam},
                    "reason": f"Shared deterministic control check breach ({ccode}) in {fam}.",
                }

        # ── Dimension D: Timing & SLA Breaches ──────────────────────────────
        sla_groups = defaultdict(list)
        for sig in signatures:
            if "SLA" in sig.exception_type or "TIMING" in sig.exception_type:
                key = f"TIMING_SLA:{sig.severity}"
                sla_groups[key].append(sig)

        for key, members in sla_groups.items():
            if len(members) >= effective_min_size:
                sev = key.split(":")[1]
                raw_clusters[key] = {
                    "cluster_key": key,
                    "pattern_type": "TIMING_SLA_SIGNATURE",
                    "pattern_label": f"Settlement Timing & SLA Breaches ({sev} Severity)",
                    "description": f"{len(members)} transactions experienced delayed settlement clearing ({sev} severity).",
                    "members": members,
                    "matched_fields": ["exception_type", "severity"],
                    "signature": {"category": "TIMING_SLA", "severity": sev},
                    "reason": f"Systemic clearing delays meeting {sev} severity threshold.",
                }

        # 3. Format structured clusters
        cluster_records: List[Dict[str, Any]] = []
        now = datetime.now(timezone.utc)

        for key, data in raw_clusters.items():
            members: List[PatternSignature] = data["members"]
            member_ids = sorted([m.exception_id for m in members])
            merchants = sorted(list({m.merchant_id for m in members if m.merchant_id}))
            families = sorted(list({m.exception_type for m in members}))
            
            first_seen = min(m.detected_at for m in members)
            last_seen = max(m.detected_at for m in members)
            total_exp = sum(m.exposure for m in members)
            
            live_count = sum(1 for m in members if m.source_flag == "live-injected")
            seeded_count = sum(1 for m in members if m.source_flag == "seeded")
            
            c_id = generate_cluster_id(key)
            
            evidence_payload = {
                "matched_fields": data["matched_fields"],
                "signature": data["signature"],
                "reason": data["reason"],
                "member_count": len(members),
                "exposure_minor_units": total_exp,
            }

            cluster_records.append({
                "cluster_id": c_id,
                "cluster_key": key,
                "pattern_type": data["pattern_type"],
                "pattern_label": data["pattern_label"],
                "description": data["description"],
                "exception_count": len(members),
                "exception_ids": member_ids,
                "merchants": merchants,
                "families": families,
                "first_seen": first_seen.isoformat(),
                "last_seen": last_seen.isoformat(),
                "total_exposure": total_exp,
                "live_injected_count": live_count,
                "seeded_count": seeded_count,
                "evidence": evidence_payload,
                "created_at": now.isoformat(),
                "updated_at": now.isoformat(),
            })

        # 4. Deterministic Sort: exception_count DESC, total_exposure DESC, cluster_id ASC
        cluster_records.sort(
            key=lambda c: (-c["exception_count"], -c["total_exposure"], c["cluster_id"])
        )

        # 5. Persistence (Idempotent materialization in database)
        if persist:
            session.execute(delete(ExceptionCluster))
            for cr in cluster_records:
                db_cluster = ExceptionCluster(
                    cluster_id=cr["cluster_id"],
                    cluster_key=cr["cluster_key"],
                    pattern_type=cr["pattern_type"],
                    pattern_label=cr["pattern_label"],
                    description=cr["description"],
                    exception_count=cr["exception_count"],
                    exception_ids=json.dumps(cr["exception_ids"]),
                    merchants=json.dumps(cr["merchants"]),
                    families=json.dumps(cr["families"]),
                    first_seen=datetime.fromisoformat(cr["first_seen"]),
                    last_seen=datetime.fromisoformat(cr["last_seen"]),
                    total_exposure=cr["total_exposure"],
                    live_injected_count=cr["live_injected_count"],
                    seeded_count=cr["seeded_count"],
                    evidence=json.dumps(cr["evidence"]),
                    created_at=now,
                    updated_at=now,
                )
                session.add(db_cluster)

            # Audit Event
            audit_event = AuditEvent(
                audit_event_id=f"audit_pattern_miner_{uuid.uuid4().hex[:16]}",
                event_type="PATTERN_MINER_EXECUTED",
                timestamp=now,
                actor_type=TransitionActorType.SYSTEM.value,
                actor_id=actor_id,
                event_summary=f"Pattern Miner executed: {len(cluster_records)} clusters discovered across {len(signatures)} exceptions.",
                event_payload=json.dumps({
                    "cluster_count": len(cluster_records),
                    "total_exceptions_analyzed": len(signatures),
                    "min_cluster_size": effective_min_size,
                    "top_patterns": [c["pattern_label"] for c in cluster_records[:5]],
                    "request_id": request_id,
                    "version": PATTERN_MINER_VERSION,
                }),
            )
            session.add(audit_event)
            session.flush()

        return cluster_records

    def get_clusters(
        self,
        session: Session,
        pattern_type: Optional[str] = None,
        exception_family: Optional[str] = None,
        merchant_id: Optional[str] = None,
        source: Optional[str] = None,
        min_count: Optional[int] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """Retrieves clusters, recomputing if necessary or filtering persisted records."""
        stmt = select(ExceptionCluster).order_by(
            ExceptionCluster.exception_count.desc(),
            ExceptionCluster.total_exposure.desc(),
            ExceptionCluster.cluster_id.asc(),
        )

        if pattern_type:
            stmt = stmt.where(ExceptionCluster.pattern_type == pattern_type)
        if min_count is not None:
            stmt = stmt.where(ExceptionCluster.exception_count >= min_count)

        db_clusters = list(session.scalars(stmt).all())

        # If table is empty, compute on the fly and persist
        if not db_clusters:
            mined = self.mine_patterns(session, persist=True)
            db_clusters = list(session.scalars(stmt).all())

        results: List[Dict[str, Any]] = []
        for c in db_clusters:
            exc_ids = json.loads(c.exception_ids) if c.exception_ids else []
            merchants = json.loads(c.merchants) if c.merchants else []
            families = json.loads(c.families) if c.families else []
            evidence = json.loads(c.evidence) if c.evidence else {}

            # In-memory secondary filters
            if exception_family and exception_family not in families:
                continue
            if merchant_id and merchant_id not in merchants:
                continue
            if source == "live-injected" and c.live_injected_count == 0:
                continue
            if source == "seeded" and c.seeded_count == 0:
                continue

            results.append({
                "cluster_id": c.cluster_id,
                "cluster_key": c.cluster_key,
                "pattern_type": c.pattern_type,
                "pattern_label": c.pattern_label,
                "description": c.description,
                "exception_count": c.exception_count,
                "exception_ids": exc_ids,
                "merchants": merchants,
                "families": families,
                "first_seen": c.first_seen.isoformat() if c.first_seen else None,
                "last_seen": c.last_seen.isoformat() if c.last_seen else None,
                "total_exposure": c.total_exposure,
                "live_injected_count": c.live_injected_count,
                "seeded_count": c.seeded_count,
                "evidence": evidence,
                "created_at": c.created_at.isoformat() if c.created_at else None,
                "updated_at": c.updated_at.isoformat() if c.updated_at else None,
            })

        return results[:limit]
