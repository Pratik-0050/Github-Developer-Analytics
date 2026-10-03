"""Tests for GitHub API rate-limit handling, token auth, session reuse, and caching."""

from unittest.mock import MagicMock, patch

import pytest

from app.services import github as gh_service


def _resp(status_code=200, ok=True, payload=None, headers=None):
    fake = MagicMock()
    fake.status_code = status_code
    fake.ok = ok
    fake.headers = headers or {}
    fake.json.return_value = payload if payload is not None else {}
    return fake


@pytest.fixture(autouse=True)
def _clean_cache():
    gh_service.clear_github_cache()
    yield
    gh_service.clear_github_cache()


def test_github_token_sent_as_bearer_header():
    """GITHUB_TOKEN from backend/.env must be sent as Authorization: Bearer."""
    with patch.object(gh_service.settings, "GITHUB_TOKEN", "secret-token-xyz"):
        headers = gh_service.get_github_headers()
        assert headers["Authorization"] == "Bearer secret-token-xyz"


def test_no_token_no_auth_header():
    """Anonymous requests must not carry an Authorization header."""
    with patch.object(gh_service.settings, "GITHUB_TOKEN", None):
        headers = gh_service.get_github_headers()
        assert "Authorization" not in headers


def test_per_request_token_takes_priority():
    """OAuth user token wins over the server-side GITHUB_TOKEN."""
    with patch.object(gh_service.settings, "GITHUB_TOKEN", "server-token"):
        headers = gh_service.get_github_headers(access_token="user-token")
        assert headers["Authorization"] == "Bearer user-token"


def test_shared_session_reused():
    """All GitHub calls share one pooled Session (no per-request clients)."""
    assert gh_service._get_session() is gh_service._get_session()


def test_retry_after_header_honored():
    resp = _resp(status_code=403, ok=False, headers={"Retry-After": "45"})
    assert gh_service._rate_limit_wait_seconds(resp) == 45


def test_rate_limit_reset_header_honored():
    import time

    reset_epoch = str(int(time.time()) + 120)
    resp = _resp(status_code=429, ok=False, headers={"X-RateLimit-Reset": reset_epoch})
    wait = gh_service._rate_limit_wait_seconds(resp)
    assert 100 <= wait <= 120


def test_429_detected_as_rate_limited():
    assert gh_service._is_rate_limited(_resp(status_code=429, ok=False)) is True


def test_403_with_rate_message_detected():
    resp = _resp(
        status_code=403,
        ok=False,
        payload={"message": "API rate limit exceeded for x"},
        headers={"X-RateLimit-Remaining": "0"},
    )
    assert gh_service._is_rate_limited(resp) is True


def test_rate_limit_raises_429_not_403():
    """Uncached user lookup under rate limiting must 429 (no retry, no fake data)."""
    limited = _resp(
        status_code=403,
        ok=False,
        payload={"message": "API rate limit exceeded"},
        headers={"Retry-After": "30"},
    )
    with patch.object(gh_service, "_github_get", return_value=limited):
        with pytest.raises(Exception) as exc:
            gh_service.get_github_user("someuser", db=None)
        assert exc.value.status_code == 429
        assert "30" in exc.value.detail


def test_repos_cached_second_call_free():
    """Second identical repos call must not touch the network."""
    payload = [
        {
            "id": 1,
            "name": "r",
            "full_name": "alice/r",
            "description": None,
            "html_url": "https://github.com/alice/r",
            "language": "Python",
            "stargazers_count": 0,
            "forks_count": 0,
            "open_issues_count": 0,
            "watchers_count": 0,
            "size": 1,
            "default_branch": "main",
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-02T00:00:00Z",
            "pushed_at": "2024-01-02T00:00:00Z",
            "fork": False,
            "archived": False,
            "private": False,
        }
    ]
    with patch.object(
        gh_service, "_github_get", return_value=_resp(payload=payload)
    ) as mock_get:
        first = gh_service.get_github_repositories("alice")
        second = gh_service.get_github_repositories("alice")
        assert len(first) == 1 and len(second) == 1
        assert mock_get.call_count == 1


def test_rate_limit_sets_partial_without_retry():
    """Per-repo rate limiting stops the scan (single attempt, partial flag)."""
    repo = MagicMock()
    repo.name = "demo"
    repo.full_name = "alice/demo"
    repo.html_url = "https://github.com/alice/demo"
    repo.pushed_at = "2024-01-02T00:00:00Z"
    repo.updated_at = "2024-01-02T00:00:00Z"
    limited = _resp(
        status_code=403,
        ok=False,
        payload={"message": "API rate limit exceeded"},
        headers={},
    )
    with patch.object(
        gh_service, "_github_get", return_value=limited
    ) as mock_get:
        issues, partial = gh_service.get_github_issues(
            "alice", limit=10, repos=[repo]
        )
        assert issues == []
        assert partial is True
        assert mock_get.call_count == 1  # no retry loop
