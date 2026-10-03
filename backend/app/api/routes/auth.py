"""OAuth 2.0 authentication router (Step 7): login, callback, session, logout.

Secure browser flow (no tokens ever reach JavaScript):
  1. ``GET /api/auth/github/login`` sets a short-lived HttpOnly ``state``
     cookie (CSRF nonce) and **302-redirects** to github.com authorize.
  2. GitHub redirects back to ``GET /api/auth/github/callback`` with
     ``?code=...&state=...``. The backend validates ``state`` against the
     cookie, exchanges the code server-side, stores the GitHub token
     encrypted in the DB, and sets the session JWT in an HttpOnly
     (Secure-in-production, SameSite=Lax) cookie.
  3. The browser is then 302-redirected to the frontend — the session is
     read via ``GET /api/auth/me`` (cookie) and private analytics work
     without any token in JavaScript, logs, or URLs.

API clients may pass ``?format=json`` (or ``Accept: application/json``) to
receive JSON instead of redirects; the session is still delivered via the
``Set-Cookie`` header, never in the body.
"""

import time
from datetime import datetime, timezone
from typing import Optional
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Header, Query, Request, Response
from fastapi import HTTPException, status
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db
from app.models.auth import (
    AuthCallbackResponse,
    AuthLoginUrlResponse,
    AuthMeResponse,
    AuthStatusResponse,
)
from app.models.db_models import AnalyticsRun, User
from app.services.auth import (
    build_authorization_url,
    clear_oauth_state_cookie,
    clear_session_cookie,
    create_session_jwt,
    decode_session_jwt,
    decrypt_github_token,
    encrypt_github_token,
    exchange_code_for_token,
    fetch_token_owner,
    generate_oauth_state,
    read_session_token,
    set_oauth_state_cookie,
    set_session_cookie,
    states_match,
)

router = APIRouter(prefix="/api/auth", tags=["Auth"])


def _frontend_url(path: str = "", query: str = "") -> str:
    base = (settings.FRONTEND_URL or "http://localhost:3000").rstrip("/")
    url = f"{base}{path}" if path else base
    return f"{url}?{query}" if query else url


def _wants_json(request: Request, format: Optional[str]) -> bool:
    if (format or "").strip().lower() == "json":
        return True
    accept = request.headers.get("accept", "")
    return "application/json" in accept.lower()


def _session_user(
    request: Request,
    authorization: Optional[str],
    db: Session,
) -> Optional[User]:
    """Resolve JWT (HttpOnly cookie preferred, Bearer fallback) -> DB user."""
    token = read_session_token(request, authorization)
    if not token:
        return None
    try:
        claims = decode_session_jwt(token)
        github_id = int(claims.get("sub", "0"))
    except (HTTPException, TypeError, ValueError):
        return None
    return db.query(User).filter(User.github_id == github_id).first()


def get_optional_session(
    request: Request,
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
) -> Optional[User]:
    """Resolve JWT -> DB user if a valid session is supplied, else None."""
    return _session_user(request, authorization, db)


def require_session(
    request: Request,
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
) -> User:
    """Require a valid session (cookie or Bearer), returning the DB user."""
    token = read_session_token(request, authorization)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not signed in. Use Continue with GitHub.",
        )
    claims = decode_session_jwt(token)  # 401 on expired/invalid
    try:
        github_id = int(claims.get("sub", "0"))
    except (TypeError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid session token."
        )
    user = db.query(User).filter(User.github_id == github_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Session user no longer exists."
        )
    return user


def resolve_user_github_token(user: User) -> Optional[str]:
    """Decrypt the stored OAuth token for API calls, or None if not connected."""
    if not user.github_token_encrypted:
        return None
    return decrypt_github_token(user.github_token_encrypted)


@router.get("/status", response_model=AuthStatusResponse, summary="OAuth configuration status")
def auth_status():
    """Public endpoint: is GitHub OAuth configured (no secrets exposed)?"""
    configured = bool(settings.GITHUB_CLIENT_ID and settings.GITHUB_CLIENT_SECRET)
    return AuthStatusResponse(
        configured=configured,
        client_id_present=bool(settings.GITHUB_CLIENT_ID),
        redirect_uri=settings.GITHUB_OAUTH_REDIRECT_URI,
        scope=settings.GITHUB_OAUTH_SCOPE,
    )


@router.get("/github/login", summary="Redirect to GitHub authorization")
def github_login(
    request: Request,
    response: Response,
    format: Optional[str] = Query(default=None, description="Pass 'json' for URL payload instead of redirect"),
):
    """Set a CSRF `state` cookie and 302-redirect to GitHub authorization.

    Pass ``?format=json`` (or ``Accept: application/json``) to receive
    ``{"authorization_url", ...}`` instead — the state cookie is still set.
    """
    if not settings.GITHUB_CLIENT_ID:
        if _wants_json(request, format):
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="GitHub OAuth is not configured. Set GITHUB_CLIENT_ID / GITHUB_CLIENT_SECRET.",
            )
        return RedirectResponse(_frontend_url(query="oauth=unconfigured"), status_code=302)

    state = generate_oauth_state()
    url = build_authorization_url(oauth_state=state)

    if _wants_json(request, format):
        payload = AuthLoginUrlResponse(
            authorization_url=url,
            redirect_uri=settings.GITHUB_OAUTH_REDIRECT_URI,
            scope=settings.GITHUB_OAUTH_SCOPE,
        )
        json_resp = JSONResponse(payload.model_dump())
        set_oauth_state_cookie(json_resp, state, request)
        return json_resp

    redirect = RedirectResponse(url, status_code=302)
    set_oauth_state_cookie(redirect, state, request)
    return redirect


@router.get("/github/callback", summary="Exchange OAuth code (validates state)")
def github_callback(
    request: Request,
    code: Optional[str] = Query(default=None, description="Temporary code from GitHub redirect"),
    state: Optional[str] = Query(default=None, description="CSRF nonce echoed by GitHub"),
    error: Optional[str] = Query(default=None, description="OAuth error (e.g. access_denied on cancel)"),
    error_description: Optional[str] = Query(default=None),
    format: Optional[str] = Query(default=None, description="Pass 'json' for JSON payload instead of redirect"),
    db: Session = Depends(get_db),
):
    """Validate the OAuth response, exchange `code` server-side, set the
    HttpOnly session cookie, and redirect to the frontend.

    - User cancellation (``?error=access_denied``) -> frontend ``?oauth=cancelled``.
    - Missing/mismatched ``state`` (CSRF) -> frontend ``?oauth=invalid_state``.
    - Success -> session cookie + frontend ``?login=success``.
    """
    wants_json = _wants_json(request, format)
    frontend = lambda q: RedirectResponse(_frontend_url(query=q), status_code=302)  # noqa: E731

    def _fail_redirect(query: str):
        resp = frontend(query)
        clear_oauth_state_cookie(resp)
        return resp

    def _fail_json(status_code: int, detail: str):
        raise HTTPException(status_code=status_code, detail=detail)

    # 1. User cancelled (or GitHub refused): never touch the code exchanger.
    if error:
        if wants_json:
            _fail_json(status.HTTP_400_BAD_REQUEST, f"GitHub OAuth: {error_description or error}")
        return _fail_redirect("oauth=cancelled")

    # 2. CSRF check: callback `state` must match the HttpOnly state cookie.
    expected_state = request.cookies.get(settings.OAUTH_STATE_COOKIE_NAME)
    if not states_match(expected_state, state):
        if wants_json:
            _fail_json(status.HTTP_400_BAD_REQUEST, "Invalid OAuth state. Please try signing in again.")
        return _fail_redirect("oauth=invalid_state")

    if not code:
        if wants_json:
            _fail_json(status.HTTP_400_BAD_REQUEST, "Missing OAuth code. Please try signing in again.")
        return _fail_redirect("oauth=error")

    # 3. Exchange + profile (server-side only; secrets/tokens never leave here).
    start = time.perf_counter()
    now_utc = datetime.now(timezone.utc)
    try:
        github_token, scope = exchange_code_for_token(code)
        profile = fetch_token_owner(github_token)
    except HTTPException as exc:
        if wants_json:
            raise
        # Don't leak upstream details in the URL; the server log keeps them.
        return _fail_redirect("oauth=error")

    login = str(profile.get("login", ""))
    try:
        github_id = int(profile.get("id", 0))
    except (TypeError, ValueError):
        github_id = 0
    if not login or not github_id:
        if wants_json:
            _fail_json(status.HTTP_502_BAD_GATEWAY, "GitHub /user missing login/id")
        return _fail_redirect("oauth=error")

    user = db.query(User).filter(User.github_id == github_id).first()
    encrypted = encrypt_github_token(github_token)
    if user:
        user.login = login
        user.name = profile.get("name")
        user.avatar_url = profile.get("avatar_url", user.avatar_url)
        user.html_url = profile.get("html_url", user.html_url)
        user.bio = profile.get("bio")
        user.company = profile.get("company")
        user.location = profile.get("location")
        user.blog = profile.get("blog")
        user.public_repos = profile.get("public_repos", user.public_repos)
        user.followers = profile.get("followers", user.followers)
        user.following = profile.get("following", user.following)
        user.github_token_encrypted = encrypted
        user.token_scope = scope
        user.token_obtained_at = now_utc
        user.last_synced_at = now_utc
    else:
        user = User(
            github_id=github_id,
            login=login,
            name=profile.get("name"),
            avatar_url=profile.get("avatar_url", ""),
            html_url=profile.get("html_url", ""),
            bio=profile.get("bio"),
            company=profile.get("company"),
            location=profile.get("location"),
            blog=profile.get("blog"),
            public_repos=profile.get("public_repos", 0),
            followers=profile.get("followers", 0),
            following=profile.get("following", 0),
            github_created_at=str(profile.get("created_at", "")),
            last_synced_at=now_utc,
            github_token_encrypted=encrypted,
            token_scope=scope,
            token_obtained_at=now_utc,
        )
        db.add(user)
        db.flush()

    elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
    db.add(
        AnalyticsRun(
            user_id=user.id,
            username=user.login,
            query_type="oauth_login",
            cache_hit=False,
            status="success",
            response_time_ms=elapsed_ms,
        )
    )
    db.commit()

    session_jwt = create_session_jwt(github_id=user.github_id, login=user.login)

    if wants_json:
        payload = AuthCallbackResponse(
            scope=scope,
            private_enabled=True,
            login=user.login,
            github_id=user.github_id,
            avatar_url=user.avatar_url,
            html_url=user.html_url,
        )
        json_resp = JSONResponse(payload.model_dump())
        set_session_cookie(json_resp, session_jwt, request)
        clear_oauth_state_cookie(json_resp)
        return json_resp

    redirect = frontend("login=success")
    set_session_cookie(redirect, session_jwt, request)
    clear_oauth_state_cookie(redirect)
    return redirect


@router.get("/me", response_model=AuthMeResponse, summary="Current session user")
def get_me(current: User = Depends(require_session)):
    """Return the session owner + private-access state (never the raw token)."""
    return AuthMeResponse(
        login=current.login,
        github_id=current.github_id,
        avatar_url=current.avatar_url,
        html_url=current.html_url,
        scope=current.token_scope,
        private_enabled=bool(current.github_token_encrypted),
        token_obtained_at=current.token_obtained_at.isoformat() if current.token_obtained_at else None,
    )


@router.post("/logout", summary="Sign out (clears session cookie)")
def logout_post():
    """Clear the HttpOnly session cookie."""
    resp = JSONResponse({"logged_out": True})
    clear_session_cookie(resp)
    return resp


@router.delete("/logout", summary="Sign out (clears session cookie)")
def logout_delete():
    """Clear the HttpOnly session cookie (DELETE variant)."""
    resp = JSONResponse({"logged_out": True})
    clear_session_cookie(resp)
    return resp


@router.delete("/token", summary="Disconnect private access")
def disconnect_token(current: User = Depends(require_session), db: Session = Depends(get_db)):
    """Remove the stored GitHub OAuth token (keeps cached profile + session)."""
    db_user = db.query(User).filter(User.id == current.id).first()
    if db_user:
        db_user.github_token_encrypted = None
        db_user.token_scope = None
        db_user.token_obtained_at = None
        db.commit()
    return {"disconnected": True, "login": current.login}
