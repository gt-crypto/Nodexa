"""Service for calculating deterministic Merchant Trust & Impact Scores."""
import json
from datetime import datetime, timezone
from collections import defaultdict
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func

from backend.models.financial_sources import GatewayTransaction
from backend.models.exceptions import ExceptionRecord
from backend.models.cluster import ExceptionCluster
from backend.models.merchant_score import MerchantScore
from backend.models.audit import AuditEvent
from backend.models.enums import ExceptionSeverity, ExceptionState

SCORING_VERSION = "v1.0.0"

def utc_now():
    return datetime.now(timezone.utc)

class MerchantScoringService:
    """Service to calculate and persist Merchant Trust & Impact Scores."""
    
    def calculate_all_scores(self, db: Session) -> List[MerchantScore]:
        """Calculates and persists scores for all merchants with activity."""
        # 1. Get total merchant activity from GatewayTransactions
        merchant_activity = db.query(
            GatewayTransaction.merchant_id,
            func.count(GatewayTransaction.id).label("total_tx"),
            func.sum(GatewayTransaction.amount).label("total_vol")
        ).group_by(GatewayTransaction.merchant_id).all()
        
        activity_map = {
            m.merchant_id: {"total_tx": m.total_tx, "total_vol": m.total_vol or 0}
            for m in merchant_activity
        }
        
        # 2. Get exception data per merchant
        # Join ExceptionRecord -> GatewayTransaction to link exceptions to merchants
        exceptions = db.query(
            ExceptionRecord, GatewayTransaction.merchant_id
        ).join(
            GatewayTransaction, ExceptionRecord.primary_payment_id == GatewayTransaction.payment_id
        ).all()
        
        exc_by_merchant = defaultdict(list)
        for exc, m_id in exceptions:
            if m_id:
                exc_by_merchant[m_id].append(exc)
                
        # Also, check if there are any merchants in exceptions that don't have activity in GatewayTransaction?
        # Unlikely since anomalies stem from transactions. But we'll combine the keys.
        all_merchants = set(activity_map.keys()).union(set(exc_by_merchant.keys()))
        
        # 3. Get Pattern Miner clusters
        clusters = db.query(ExceptionCluster).all()
        merchant_patterns = defaultdict(int)
        for c in clusters:
            if c.merchants:
                try:
                    m_list = json.loads(c.merchants)
                    for m in m_list:
                        merchant_patterns[m] += 1
                except Exception:
                    pass

        results = []
        for m_id in all_merchants:
            # We skip merchants with absolutely no exceptions unless they have activity
            # Actually, calculate for all.
            score_record = self._calculate_single_merchant(
                m_id=m_id,
                activity=activity_map.get(m_id, {"total_tx": 0, "total_vol": 0}),
                exceptions=exc_by_merchant.get(m_id, []),
                pattern_count=merchant_patterns.get(m_id, 0)
            )
            
            # Upsert
            existing = db.query(MerchantScore).filter(MerchantScore.merchant_id == m_id).first()
            if existing:
                for k, v in score_record.items():
                    setattr(existing, k, v)
                existing.updated_at = utc_now()
                results.append(existing)
            else:
                new_score = MerchantScore(**score_record)
                db.add(new_score)
                results.append(new_score)
                
            import uuid
            audit = AuditEvent(
                audit_event_id=f"audit_merch_{uuid.uuid4().hex[:16]}",
                event_type="MERCHANT_SCORE_REFRESH",
                actor_type="SYSTEM",
                actor_id="SCORING_ENGINE",
                event_summary=f"Calculated score for merchant {m_id}",
                event_payload=json.dumps({
                    "merchant_id": m_id,
                    "trust_score": score_record["trust_score"],
                    "impact_score": score_record["impact_score"],
                    "version": SCORING_VERSION
                }),
            )
            db.add(audit)
            
        db.commit()
        return results

    def _calculate_single_merchant(self, m_id: str, activity: Dict, exceptions: List[ExceptionRecord], pattern_count: int) -> Dict[str, Any]:
        """Core deterministic scoring logic."""
        total_tx = activity["total_tx"]
        
        exc_count = len(exceptions)
        high_risk_count = sum(1 for e in exceptions if e.severity in (ExceptionSeverity.HIGH.value, ExceptionSeverity.CRITICAL.value))
        
        # Actionable: we'll define as not VERIFIED_CLOSED unless it's a severe one? 
        # Better: anything that isn't a known FALSE_POSITIVE or LEGITIMATE. Since we don't have a direct FALSE_POSITIVE state on exception,
        # we consider all exceptions actionable unless they were resolved with 0 exposure? Let's just use all exceptions for simplicity,
        # or maybe we can check state. For now, actionable = all exceptions that are not closed, plus closed ones that had exposure.
        actionable_count = exc_count  # Keep simple for deterministic rule
        
        total_exp = sum((e.exposure or 0) for e in exceptions)
        
        seeded_count = sum(1 for e in exceptions if e.source_flag == "seeded")
        live_injected_count = sum(1 for e in exceptions if e.source_flag == "live-injected")
        
        first_seen = min([e.detected_at for e in exceptions]) if exceptions else None
        last_seen = max([e.detected_at for e in exceptions]) if exceptions else None

        factors = []
        
        # ==========================================
        # 1. TRUST SCORE (0 - 100)
        # ==========================================
        # Starts at 100, drops based on bad behavior relative to volume
        trust = 100
        
        # Exception rate penalty
        if total_tx > 0:
            exc_rate = exc_count / total_tx
            rate_penalty = min(40, int(exc_rate * 100 * 2))  # e.g. 10% rate -> 20 penalty. Max 40.
            if rate_penalty > 0:
                trust -= rate_penalty
                factors.append({
                    "factor": "EXCEPTION_RATE",
                    "direction": "NEGATIVE",
                    "value": round(exc_rate, 4),
                    "contribution": -rate_penalty,
                    "explanation": f"Merchant has {exc_count} exceptions out of {total_tx} transactions ({exc_rate*100:.1f}%)."
                })
        else:
            # No base volume, absolute penalty
            rate_penalty = min(40, exc_count * 2)
            if rate_penalty > 0:
                trust -= rate_penalty
                factors.append({
                    "factor": "ABSOLUTE_EXCEPTION_VOLUME",
                    "direction": "NEGATIVE",
                    "value": exc_count,
                    "contribution": -rate_penalty,
                    "explanation": f"Merchant has {exc_count} exceptions with no recorded normal volume."
                })
                
        # High Risk penalty
        hr_penalty = min(30, high_risk_count * 10)
        if hr_penalty > 0:
            trust -= hr_penalty
            factors.append({
                "factor": "HIGH_RISK_INCIDENCE",
                "direction": "NEGATIVE",
                "value": high_risk_count,
                "contribution": -hr_penalty,
                "explanation": f"Merchant has {high_risk_count} high or critical severity exceptions."
            })
            
        # Pattern Miner penalty
        pattern_penalty = min(30, pattern_count * 10)
        if pattern_penalty > 0:
            trust -= pattern_penalty
            factors.append({
                "factor": "RECURRING_PATTERNS",
                "direction": "NEGATIVE",
                "value": pattern_count,
                "contribution": -pattern_penalty,
                "explanation": f"Merchant is involved in {pattern_count} recurring anomaly patterns."
            })
            
        trust = max(0, trust)
        if trust == 100:
            factors.append({
                "factor": "CLEAN_RECORD",
                "direction": "POSITIVE",
                "value": 1,
                "contribution": 0,
                "explanation": "Merchant exhibits no significant operational anomalies."
            })

        # ==========================================
        # 2. IMPACT SCORE (0 - 100)
        # ==========================================
        # Starts at 0, increases based on raw damage
        impact = 0
        
        # Exposure impact (Rs. 10,000 = 1 point, max 50)
        exp_rupees = total_exp / 100.0
        exp_impact = min(50, int(exp_rupees / 10000))
        if exp_impact > 0:
            impact += exp_impact
            factors.append({
                "factor": "FINANCIAL_EXPOSURE",
                "direction": "NEGATIVE",
                "value": total_exp,
                "contribution": exp_impact,
                "explanation": f"Total exposure of Rs. {exp_rupees:.2f} drives operational impact."
            })
            
        # High Risk volume impact (10 points each, max 30)
        hr_impact = min(30, high_risk_count * 10)
        if hr_impact > 0:
            impact += hr_impact
            factors.append({
                "factor": "SEVERE_CASES",
                "direction": "NEGATIVE",
                "value": high_risk_count,
                "contribution": hr_impact,
                "explanation": f"{high_risk_count} severe cases requiring immediate attention."
            })
            
        # Pattern impact (10 points each, max 20)
        pat_impact = min(20, pattern_count * 10)
        if pat_impact > 0:
            impact += pat_impact
            factors.append({
                "factor": "SYSTEMIC_PATTERNS",
                "direction": "NEGATIVE",
                "value": pattern_count,
                "contribution": pat_impact,
                "explanation": f"Involvement in {pattern_count} systemic patterns amplifies impact."
            })
            
        impact = min(100, impact)

        # ==========================================
        # 3. SCORE BAND
        # ==========================================
        if trust >= 90:
            band = "EXCELLENT"
        elif trust >= 75:
            band = "HEALTHY"
        elif trust >= 50:
            band = "WATCH"
        elif trust >= 25:
            band = "HIGH_RISK"
        else:
            band = "CRITICAL"

        return {
            "merchant_id": m_id,
            "trust_score": trust,
            "impact_score": impact,
            "score_band": band,
            "exception_count": exc_count,
            "actionable_exception_count": actionable_count,
            "legitimate_exception_count": 0,
            "high_risk_exception_count": high_risk_count,
            "total_exposure": total_exp,
            "recurring_pattern_count": pattern_count,
            "seeded_case_count": seeded_count,
            "live_injected_case_count": live_injected_count,
            "total_transaction_count": total_tx,
            "total_transaction_volume": activity["total_vol"],
            "scoring_version": SCORING_VERSION,
            "score_factors": json.dumps(factors),
            "first_seen": first_seen,
            "last_seen": last_seen,
        }
