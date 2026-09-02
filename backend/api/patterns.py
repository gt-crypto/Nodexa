"""FastAPI REST router for Pattern Miner endpoints (PRD: GET /clusters)."""
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.models.database import get_db
from backend.patterns.miner import PatternMinerService

router = APIRouter(tags=["Pattern Miner"])


class ClusterEvidence(BaseModel):
    matched_fields: List[str]
    signature: Dict[str, Any]
    reason: str
    member_count: int
    exposure_minor_units: int


class ClusterResponseItem(BaseModel):
    cluster_id: str
    cluster_key: str
    pattern_type: str
    pattern_label: str
    description: str
    exception_count: int
    exception_ids: List[str]
    merchants: List[str]
    families: List[str]
    first_seen: str
    last_seen: str
    total_exposure: int
    live_injected_count: int
    seeded_count: int
    evidence: ClusterEvidence
    created_at: str
    updated_at: str


class ClustersListResponse(BaseModel):
    clusters: List[ClusterResponseItem]
    total_clusters: int
    total_clustered_exceptions: int
    total_clustered_exposure: int
    min_cluster_size: int
    retrieved_at: str


@router.get("/clusters", response_model=ClustersListResponse)
def get_clusters(
    pattern_type: Optional[str] = Query(default=None, description="Filter by pattern type"),
    exception_family: Optional[str] = Query(default=None, description="Filter by exception family"),
    merchant_id: Optional[str] = Query(default=None, description="Filter by merchant identifier"),
    source: Optional[str] = Query(default=None, description="Filter by source flag (seeded, live-injected)"),
    min_count: Optional[int] = Query(default=None, ge=1, description="Minimum exception member count"),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
) -> ClustersListResponse:
    """Retrieves deterministic recurring exception clusters discovered by the Pattern Miner."""
    service = PatternMinerService()
    clusters = service.get_clusters(
        session=db,
        pattern_type=pattern_type,
        exception_family=exception_family,
        merchant_id=merchant_id,
        source=source,
        min_count=min_count,
        limit=limit,
    )
    db.commit()

    from datetime import datetime, timezone
    now_iso = datetime.now(timezone.utc).isoformat()

    total_exc = sum(c["exception_count"] for c in clusters)
    total_exp = sum(c["total_exposure"] for c in clusters)

    return ClustersListResponse(
        clusters=clusters,
        total_clusters=len(clusters),
        total_clustered_exceptions=total_exc,
        total_clustered_exposure=total_exp,
        min_cluster_size=service.min_cluster_size,
        retrieved_at=now_iso,
    )


@router.post("/clusters/refresh", response_model=ClustersListResponse)
def refresh_clusters(
    request: Request,
    min_cluster_size: Optional[int] = Query(default=None, ge=2, description="Override minimum cluster size threshold"),
    db: Session = Depends(get_db),
) -> ClustersListResponse:
    """Forces an on-demand recomputation and materialization of all pattern clusters."""
    request_id = getattr(request.state, "request_id", None) if hasattr(request, "state") else None
    service = PatternMinerService()
    mined = service.mine_patterns(
        session=db,
        min_cluster_size=min_cluster_size,
        persist=True,
        actor_id="operator_refresh",
        request_id=request_id,
    )
    db.commit()

    from datetime import datetime, timezone
    now_iso = datetime.now(timezone.utc).isoformat()

    total_exc = sum(c["exception_count"] for c in mined)
    total_exp = sum(c["total_exposure"] for c in mined)

    return ClustersListResponse(
        clusters=mined,
        total_clusters=len(mined),
        total_clustered_exceptions=total_exc,
        total_clustered_exposure=total_exp,
        min_cluster_size=min_cluster_size or service.min_cluster_size,
        retrieved_at=now_iso,
    )
