"""Tests for database caching and analytics auditing."""

import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.db.session import init_db


@pytest.fixture(scope="session", autouse=True)
def setup_database():
    """Ensure database schema is created prior to tests."""
    init_db()


@pytest.fixture
def client():
    """TestClient fixture with app context."""
    with TestClient(app) as test_client:
        yield test_client


def test_health_check_with_database(client):
    """Verify /api/health returns database connectivity status."""
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] in ["healthy", "degraded"]
    assert "database" in data
    assert data["database"]["status"] == "connected"
    assert data["database"]["latency_ms"] >= 0


def test_user_caching_and_force_refresh(client):
    """Verify caching behavior: first fetch caches, subsequent fetch is served from cache."""
    # 1. Force refresh to ensure a clean cache state
    res1 = client.get("/api/github/user/octocat?refresh=true")
    assert res1.status_code == 200
    user1 = res1.json()
    assert user1["login"].lower() == "octocat"
    assert user1["cached"] is False

    # 2. Immediate second request should be served from database cache
    res2 = client.get("/api/github/user/octocat")
    assert res2.status_code == 200
    user2 = res2.json()
    assert user2["login"].lower() == "octocat"
    assert user2["cached"] is True
    assert user2["id"] == user1["id"]

    # 3. Request with refresh=True should re-query GitHub API
    res3 = client.get("/api/github/user/octocat?refresh=true")
    assert res3.status_code == 200
    user3 = res3.json()
    assert user3["cached"] is False


def test_analytics_stats_and_history(client):
    """Verify /api/analytics/stats and /api/analytics/history return proper metrics."""
    res_stats = client.get("/api/analytics/stats")
    assert res_stats.status_code == 200
    stats = res_stats.json()
    assert stats["total_queries"] >= 1
    assert stats["total_cached_profiles"] >= 1
    assert "database_status" in stats

    res_history = client.get("/api/analytics/history?limit=10")
    assert res_history.status_code == 200
    history = res_history.json()
    assert isinstance(history, list)
    assert len(history) >= 1
    assert any(h["username"].lower() == "octocat" for h in history)


def test_user_not_found_handling(client):
    """Verify 404 behavior for invalid users and proper error response."""
    invalid_user = "user-that-definitely-does-not-exist-9876543210"
    response = client.get(f"/api/github/user/{invalid_user}")
    assert response.status_code == 404
    data = response.json()
    assert "detail" in data
