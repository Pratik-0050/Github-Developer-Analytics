"""Health check endpoints with database monitoring."""

from fastapi import APIRouter
from app.db.session import check_db_connection

router = APIRouter(tags=["Health"])


@router.get("/", summary="Root status message")
def read_root():
    """Root endpoint verifying API availability."""
    return {"message": "GitHub Developer Analytics API is running"}


@router.get("/api/health", summary="Health check endpoint")
def health_check():
    """Health check endpoint for service status and database connectivity monitoring."""
    db_connected, db_latency_ms, dialect_or_err = check_db_connection()

    db_info = {
        "status": "connected" if db_connected else "disconnected",
        "latency_ms": db_latency_ms,
        "dialect": dialect_or_err if db_connected else "unknown",
    }
    if not db_connected:
        db_info["error"] = dialect_or_err

    return {
        "status": "healthy" if db_connected else "degraded",
        "service": "github-developer-analytics-api",
        "database": db_info,
    }
