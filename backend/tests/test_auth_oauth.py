"""Tests for Step 7: GitHub OAuth 2.0 (redirect + HttpOnly cookie + state CSRF).

Covered: successful login (302 + session cookie), user cancellation,
invalid/missing state, expired sessions, logout, and that no tokens or
secrets ever leak into bodies/URLs. Public analytics stay anonymous-safe.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch
from urllib.parse import parse_qs, urlparse

import jwt
import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.db.session import init_db
from app.services.auth import (
    create_session_jwt,
    decode_session_jwt,
    decrypt_github_token,
    encrypt_github_token,
)


@pytest.fixture(scope="session", autouse=True)
def setup_database():
    init_db()


@pytest.fixture
def client():
    from app.main import app

    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def oauth_configured(monkeypatch):
    """Deterministic OAuth config regardless of local backend/.env."""
    monkeypatch.setattr(settings, "GITHUB_CLIENT_ID", "test-client-id")
    monkeypatch.setattr(settings, "GITHUB_CLIENT_SECRET", "test-client-secret")
    monkeypatch.setattr(
        settings, "GITHUB_OAUTH_REDIRECT_URI", "http://localhost:8000/api/auth/github/callback"
    )
    monkeypatch.setattr(settings, "GITHUB_OAUTH_SCOPE", "read:user")
    monkeypatch.setattr(settings, "FRONTEND_URL", "http://localhost:3000")
    monkeypatch.setattr(settings, "JWT_SECRET", "test-jwt-secret")
    return settings


def _login_state(client: TestClient) -> str:
    """Run the login endpoint (no redirect follow) and return the `state` nonce."""
    res = client.get("/api/auth/github/login", follow_redirects=False)
    assert res.status_code == 302, res.text
    location = res.headers["location"]
    assert location.startswith("https://github.com/login/oauth/authorize")
    query = parse_qs(urlparse(location).query)
    assert query["client_id"] == ["test-client-id"]
    assert query["redirect_uri"] == ["http://localhost:8000/api/auth/github/callback"]
    assert "state" in query
    # CSRF nonce must be HttpOnly (never readable from JS).
    set_cookie = res.headers.get("set-cookie", "")
    assert settings.OAUTH_STATE_COOKIE_NAME in set_cookie
    assert "httponly" in set_cookie.lower()
    return query["state"][0]


def test_token_encrypt_decrypt_roundtrip():
    encrypted = encrypt_github_token("ghu_secret-token-123")
    assert encrypted != "ghu_secret-token-123"
    assert decrypt_github_token(encrypted) == "ghu_secret-token-123"


def test_jwt_create_decode_roundtrip():
    token = create_session_jwt(github_id=12345, login="octocat")
    claims = decode_session_jwt(token)
    assert claims["sub"] == "12345"
    assert claims["login"] == "octocat"


def test_jwt_invalid_rejected():
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc:
        decode_session_jwt("not.a.valid.jwt")
    assert exc.value.status_code == 401


def test_auth_status_public(client, oauth_configured):
    res = client.get("/api/auth/status")
    assert res.status_code == 200
    body = res.json()
    assert body["configured"] is True
    assert body["redirect_uri"].endswith("/api/auth/github/callback")
    # No secrets in the public status payload.
    assert "secret" not in res.text.lower()
    assert "test-client-secret" not in res.text


def test_login_redirects_with_state_cookie(client, oauth_configured):
    state = _login_state(client)
    assert len(state) >= 20


def test_login_json_mode_sets_state_cookie_without_secret(client, oauth_configured):
    res = client.get("/api/auth/github/login?format=json")
    assert res.status_code == 200
    body = res.json()
    assert body["authorization_url"].startswith("https://github.com/login/oauth/authorize")
    assert "test-client-secret" not in res.text
    set_cookie = res.headers.get("set-cookie", "")
    assert settings.OAUTH_STATE_COOKIE_NAME in set_cookie
    assert "httponly" in set_cookie.lower()


def test_login_unconfigured_returns_503(client, monkeypatch):
    monkeypatch.setattr(settings, "GITHUB_CLIENT_ID", None)
    monkeypatch.setattr(settings, "GITHUB_CLIENT_SECRET", None)
    res = client.get("/api/auth/github/login?format=json")
    assert res.status_code == 503
    assert "not configured" in res.json()["detail"].lower()


def test_me_requires_auth(client):
    res = client.get("/api/auth/me")
    assert res.status_code == 401


def test_me_rejects_bad_token(client):
    res = client.get("/api/auth/me", headers={"Authorization": "Bearer garbage"})
    assert res.status_code == 401


def test_me_rejects_expired_session_cookie(client, oauth_configured):
    secret = settings.JWT_SECRET or "dev-only-change-me"
    now = datetime.now(timezone.utc)
    expired = jwt.encode(
        {
            "sub": "424242",
            "login": "expired-user",
            "iat": int((now - timedelta(hours=2)).timestamp()),
            "exp": int((now - timedelta(hours=1)).timestamp()),
        },
        secret,
        algorithm=settings.JWT_ALGORITHM,
    )
    client.cookies.set(settings.SESSION_COOKIE_NAME, expired)
    res = client.get("/api/auth/me")
    assert res.status_code == 401
    assert "expired" in res.json()["detail"].lower()
    client.cookies.clear()


def test_callback_full_flow_with_mocks(client, oauth_configured):
    """Successful login: state validated, session cookie set, redirect to frontend."""
    state = _login_state(client)
    fake_token = "ghu_test-token"
    fake_profile = {
        "login": "oauth-test-user-xyz",
        "id": 999888777,
        "name": "OAuth Tester",
        "avatar_url": "https://avatars.githubusercontent.com/u/999888777?v=4",
        "html_url": "https://github.com/oauth-test-user-xyz",
        "bio": None,
        "company": None,
        "location": None,
        "blog": None,
        "public_repos": 3,
        "followers": 1,
        "following": 2,
        "created_at": "2020-01-01T00:00:00Z",
    }

    with (
        patch("app.api.routes.auth.exchange_code_for_token", return_value=(fake_token, "read:user")),
        patch("app.api.routes.auth.fetch_token_owner", return_value=fake_profile),
    ):
        res = client.get(
            f"/api/auth/github/callback?code=temp-code-123&state={state}",
            follow_redirects=False,
        )
        assert res.status_code == 302, res.text
        assert res.headers["location"].startswith("http://localhost:3000")
        assert "login=success" in res.headers["location"]
        # Session cookie: HttpOnly, and the raw GitHub token is nowhere in play.
        set_cookie = res.headers.get("set-cookie", "")
        assert settings.SESSION_COOKIE_NAME in set_cookie
        assert "httponly" in set_cookie.lower()
        assert fake_token not in set_cookie

        # Cookie session resolves via /me (no Authorization header needed).
        me = client.get("/api/auth/me")
        assert me.status_code == 200
        assert me.json()["login"] == "oauth-test-user-xyz"
        assert me.json()["private_enabled"] is True
        assert fake_token not in me.text

        # Private repos endpoint must not leak without matching login ownership;
        # anonymous include_private must degrade to public (no 401).
        with patch("app.api.routes.github.get_github_repositories", return_value=[]) as mock_repos:
            r = client.get("/api/github/repos/someone-else?include_private=true")
            assert r.status_code == 200
            assert r.json()["private_included"] is False
            mock_repos.assert_called_once()
            # token must NOT be forwarded for a different username
            assert mock_repos.call_args.kwargs.get("access_token") is None

        # JSON mode: user snapshot WITHOUT any token material in the body.
        state2 = _login_state(client)
        with (
            patch("app.api.routes.auth.exchange_code_for_token", return_value=(fake_token, "read:user")),
            patch("app.api.routes.auth.fetch_token_owner", return_value=fake_profile),
        ):
            j = client.get(f"/api/auth/github/callback?code=x&state={state2}&format=json")
            assert j.status_code == 200
            body = j.json()
            assert body["login"] == "oauth-test-user-xyz"
            assert "access_token" not in body
            assert fake_token not in j.text
            assert settings.SESSION_COOKIE_NAME in j.headers.get("set-cookie", "")

        # Disconnect clears private access but keeps profile/session.
        disc = client.delete("/api/auth/token")
        assert disc.status_code == 200
        assert disc.json()["disconnected"] is True

        me2 = client.get("/api/auth/me")
        assert me2.status_code == 200
        assert me2.json()["private_enabled"] is False

        # Logout clears the session cookie; /me becomes 401 (expired session).
        out = client.post("/api/auth/logout")
        assert out.status_code == 200
        assert out.json()["logged_out"] is True
        me3 = client.get("/api/auth/me")
        assert me3.status_code == 401


def test_callback_user_cancellation(client, oauth_configured):
    """GitHub `error=access_denied` (user pressed Cancel) never hits exchange."""
    _login_state(client)
    with patch("app.api.routes.auth.exchange_code_for_token") as mock_exchange:
        res = client.get(
            "/api/auth/github/callback?error=access_denied&error_description=The+user+denied",
            follow_redirects=False,
        )
        assert res.status_code == 302
        assert "oauth=cancelled" in res.headers["location"]
        mock_exchange.assert_not_called()

    # JSON mode surfaces a 400 instead of a redirect.
    res_json = client.get("/api/auth/github/callback?error=access_denied&format=json")
    assert res_json.status_code == 400


def test_callback_invalid_state_rejected(client, oauth_configured):
    """Wrong/missing `state` (CSRF) must not exchange the code."""
    _login_state(client)
    with patch("app.api.routes.auth.exchange_code_for_token") as mock_exchange:
        res = client.get(
            "/api/auth/github/callback?code=abc&state=tampered-state",
            follow_redirects=False,
        )
        assert res.status_code == 302
        assert "oauth=invalid_state" in res.headers["location"]
        mock_exchange.assert_not_called()

    res_json = client.get("/api/auth/github/callback?code=abc&state=tampered-state&format=json")
    assert res_json.status_code == 400
    assert "state" in res_json.json()["detail"].lower()


def test_callback_missing_code(client, oauth_configured):
    state = _login_state(client)
    res = client.get(
        f"/api/auth/github/callback?state={state}", follow_redirects=False
    )
    assert res.status_code == 302
    assert "oauth=error" in res.headers["location"]


def test_private_repos_uses_user_repos_endpoint():
    """Authenticated /user/repos visibility=all path is exercised."""
    from app.services import github as gh_service

    fake_resp = MagicMock()
    fake_resp.status_code = 200
    fake_resp.ok = True
    fake_resp.json.return_value = [
        {
            "id": 1,
            "name": "secret-repo",
            "full_name": "owner/secret-repo",
            "description": None,
            "html_url": "https://github.com/owner/secret-repo",
            "language": "Python",
            "stargazers_count": 0,
            "forks_count": 0,
            "open_issues_count": 0,
            "watchers_count": 0,
            "size": 10,
            "default_branch": "main",
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-02T00:00:00Z",
            "pushed_at": "2024-01-02T00:00:00Z",
            "fork": False,
            "archived": False,
            "private": True,
        }
    ]

    with patch("app.services.github._github_get", return_value=fake_resp) as mock_get:
        gh_service.clear_github_cache()
        repos = gh_service.get_github_repositories(
            "owner", access_token="ghu_x", include_private=True
        )
        assert len(repos) == 1
        assert repos[0].private is True
        called_url = mock_get.call_args.args[0]
        assert called_url.endswith("/user/repos")
        assert mock_get.call_args.kwargs["params"]["visibility"] == "all"
