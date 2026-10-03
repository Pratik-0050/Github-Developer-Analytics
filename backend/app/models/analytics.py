"""Pydantic schemas for analytics run history and statistics."""

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict


class AnalyticsRunRead(BaseModel):
    """Schema for returning individual analytics search audit records."""

    id: int
    username: str
    query_type: str
    cache_hit: bool
    status: str
    response_time_ms: float
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AnalyticsStatsResponse(BaseModel):
    """Aggregated cache and query performance metrics."""

    total_cached_profiles: int
    total_queries: int
    total_cache_hits: int
    total_cache_misses: int
    cache_hit_rate_pct: float
    average_response_time_ms: float
    database_status: str
    database_latency_ms: float
    recent_runs: List[AnalyticsRunRead]

    model_config = ConfigDict(from_attributes=True)
