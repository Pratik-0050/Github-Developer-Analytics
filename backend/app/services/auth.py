"""GitHub OAuth 2.0 service: token encryption, JWT sessions, code exchange (Step 7)."""

import base64
import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt
import requests
from fastapi import HTTPException, Request, Response, status
from cryptography.fernet import Fernet, InvalidToken

from app.core.config import settings

# Cookie lifetimes
OAUTH_STATE_MAX_AGE_SECONDS = 10 * 60  # 10 minutes (CSRF nonce, short-lived)


def _fernet() -> Fernet:
    """Resolve Fernet instance.

    Prefers OAUTH_TOKEN_FERNET_KEY; falls back to a JWT_SECRET-derived 32-byte
    key (dev convenience — set OAUTH_TOKEN_FERNET_KEY explicitly in prod).
    """
    raw = (settings.OAUTH_TOKEN_FERNET_KEY or "").strip()
    if raw:
        try:
            return Fernet(raw.encode())
        except Exception:
            pass  # fall through to derived key
    secret = (settings.JWT_SECRET or "dev-only-change-me").encode()
    digest = hashlib.sha256(secret).digest()  # 32 bytes
    key = base64.urlsafe_b64encode(digest)
    return Fernet(key)


def encrypt_github_token(plain_token: str) -> str:
    """Encrypt a GitHub OAuth token for DB storage."""
    return _fernet().encrypt(plain_token.encode()).decode()


def decrypt_github_token(encrypted_token: str) -> str:
    """Decrypt a stored GitHub OAuth token. Raises HTTPException on failure."""
    try:
        return _fernet().decrypt(encrypted_token.encode()).decode()
    except InvalidToken:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Stored GitHub token cannot be decrypted (key mismatch?)",
        )


def generate_oauth_state() -> str:
    """Generate a cryptographically random OAuth `state` nonce (CSRF protection)."""
    return secrets.token_urlsafe(32)


def states_match(expected: Optional[str], received: Optional[str]) -> bool:
    """Constant-time comparison of the state cookie vs. the callback `state`."""
    if not expected or not received:
        return False
    return hmac.compare_digest(expected, received)


def _cookie_secure(request: Optional[Request] = None) -> bool:
    """Secure flag: on in production (HTTPS). Plain HTTP locally so cookies work.

    True when the frontend URL is https, the incoming request was https, or
    APP_ENV/ENVIRONMENT is production. Explicit SESSION_COOKIE_SECURE=1/0
    env override wins when set.
    """
    import os

    override = os.getenv("SESSION_COOKIE_SECURE", "").strip().lower()
    if override in ("1", "true", "yes"):
        return True
    if override in ("0", "false", "no"):
        return False
    if (settings.FRONTEND_URL or "").strip().lower().startswith("https://"):
        return True
    if request is not None and request.url.scheme == "https":
        return True
    env = (os.getenv("APP_ENV") or os.getenv("ENVIRONMENT") or "").strip().lower()
    return env in ("prod", "production")


def set_session_cookie(response: Response, session_jwt: str, request: Optional[Request] = None) -> None:
    """Store the session JWT in an HttpOnly cookie (never in body/URL)."""
    response.set_cookie(
        key=settings.SESSION_COOKIE_NAME,
        value=session_jwt,
        max_age=settings.JWT_EXPIRE_MINUTES * 60,
        expires=settings.JWT_EXPIRE_MINUTES * 60,
        path="/",
        httponly=True,
        secure=_cookie_secure(request),
        samesite=settings.SESSION_COOKIE_SAMESITE,
    )


def clear_session_cookie(response: Response) -> None:
    """Expire the session cookie (logout)."""
    response.delete_cookie(key=settings.SESSION_COOKIE_NAME, path="/")


def set_oauth_state_cookie(response: Response, state: str, request: Optional[Request] = None) -> None:
    """Store the OAuth CSRF nonce in a short-lived HttpOnly cookie."""
    response.set_cookie(
        key=settings.OAUTH_STATE_COOKIE_NAME,
        value=state,
        max_age=OAUTH_STATE_MAX_AGE_SECONDS,
        expires=OAUTH_STATE_MAX_AGE_SECONDS,
        path="/",
        httponly=True,
        secure=_cookie_secure(request),
        samesite=settings.SESSION_COOKIE_SAMESITE,
    )


def clear_oauth_state_cookie(response: Response) -> None:
    """Expire the OAuth state cookie (single-use nonce)."""
    response.delete_cookie(key=settings.OAUTH_STATE_COOKIE_NAME, path="/")


def read_session_token(request: Optional[Request], authorization: Optional[str]) -> Optional[str]:
    """Return the session JWT from the HttpOnly cookie (preferred) or a
    Bearer header fallback (kept for API clients / backwards compatibility)."""
    if request is not None:
        cookie_token = request.cookies.get(settings.SESSION_COOKIE_NAME)
        if cookie_token:
            return cookie_token
    if authorization and authorization.lower().startswith("bearer "):
        candidate = authorization.split(" ", 1)[1].strip()
        if candidate:
            return candidate
    return None


def build_authorization_url(oauth_state: Optional[str] = None) -> str:
    """Build the github.com authorize URL. Raises 503 if OAuth is unconfigured."""
    if not settings.GITHUB_CLIENT_ID:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="GitHub OAuth is not configured. Set GITHUB_CLIENT_ID / GITHUB_CLIENT_SECRET.",
        )
    from urllib.parse import urlencode

    params = {
        "client_id": settings.GITHUB_CLIENT_ID,
        "redirect_uri": settings.GITHUB_OAUTH_REDIRECT_URI,
        "scope": settings.GITHUB_OAUTH_SCOPE,
    }
    if oauth_state:
        params["state"] = oauth_state
    return f"https://github.com/login/oauth/authorize?{urlencode(params)}"


def exchange_code_for_token(code: str) -> tuple[str, str]:
    """Exchange an OAuth `code` for a user access token.

    Returns (access_token, scope). Raises HTTPException on failure.
    """
    if not settings.GITHUB_CLIENT_ID or not settings.GITHUB_CLIENT_SECRET:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="GitHub OAuth is not configured. Set GITHUB_CLIENT_ID / GITHUB_CLIENT_SECRET.",
        )
    try:
        resp = requests.post(
            "https://github.com/login/oauth/access_token",
            headers={"Accept": "application/json", "User-Agent": "GitHub-Developer-Analytics-API"},
            data={
                "client_id": settings.GITHUB_CLIENT_ID,
                "client_secret": settings.GITHUB_CLIENT_SECRET,
                "code": code,
                "redirect_uri": settings.GITHUB_OAUTH_REDIRECT_URI,
            },
            timeout=10.0,
        )
    except requests.exceptions.RequestException:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Unable to reach GitHub OAuth endpoint",
        )
    if not resp.ok:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="GitHub OAuth token exchange failed",
        )
    payload = resp.json()
    token = payload.get("access_token")
    if not token:
        detail = payload.get("error_description") or payload.get("error") or "OAuth code exchange failed"
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)
    scope = payload.get("scope", "")
    return token, scope


def fetch_token_owner(github_token: str) -> dict:
    """Fetch the authenticated /user profile for a GitHub OAuth token."""
    try:
        resp = requests.get(
            f"{settings.GITHUB_API_URL.rstrip('/')}/user",
            headers={
                "Accept": "application/vnd.github.v3+json",
                "User-Agent": "GitHub-Developer-Analytics-API",
                "Authorization": f"Bearer {github_token}",
            },
            timeout=10.0,
        )
    except requests.exceptions.RequestException:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Unable to connect to GitHub API",
        )
    if resp.status_code == 401:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="GitHub token rejected (bad credentials)",
        )
    if not resp.ok:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="GitHub API service error",
        )
    data = resp.json()
    if not isinstance(data, dict) or not data.get("login"):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Unexpected GitHub /user response",
        )
    return data


def create_session_jwt(github_id: int, login: str) -> str:
    """Create a signed session JWT. Requires JWT_SECRET in production."""
    secret = settings.JWT_SECRET or "dev-only-change-me"
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(github_id),
        "login": login,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=settings.JWT_EXPIRE_MINUTES)).timestamp()),
    }
    return jwt.encode(payload, secret, algorithm=settings.JWT_ALGORITHM)


def decode_session_jwt(token: str) -> dict:
    """Decode/verify a session JWT. Raises 401 on any failure."""
    secret = settings.JWT_SECRET or "dev-only-change-me"
    try:
        return jwt.decode(token, secret, algorithms=[settings.JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Session expired. Please sign in again."
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid session token."
        )
