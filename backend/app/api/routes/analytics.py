"""API endpoints for analytics history, query audits, and cache metrics."""

from typing import List
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.models.analytics import AnalyticsRunRead, AnalyticsStatsResponse
from app.services.analytics import get_analytics_stats, get_recent_runs

router = APIRouter(prefix="/api/analytics", tags=["Analytics"])


@router.get("/history", response_model=List[AnalyticsRunRead])
def get_history(
    limit: int = Query(default=20, ge=1, le=100, description="Max records to return"),
    db: Session = Depends(get_db),
):
    """Retrieve audit records of recently performed profile and analytics queries."""
    runs = get_recent_runs(db, limit=limit)
    return [AnalyticsRunRead.model_validate(r) for r in runs]


@router.get("/stats", response_model=AnalyticsStatsResponse)
def get_stats(db: Session = Depends(get_db)):
    """Retrieve aggregate cache metrics, query volumes, and database performance."""
    return get_analytics_stats(db)
