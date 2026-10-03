"""GitHub endpoints router (Step 7 adds optional private-repo support via session JWT)."""

from typing import Optional

from fastapi import APIRouter, Depends, Header, Query, Request
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.models.github import (
    GitHubActivityResponse,
    GitHubAnalyticsResponse,
    GitHubCommitsResponse,
    GitHubIssueAnalyticsResponse,
    GitHubIssuesResponse,
    GitHubRepositoriesResponse,
    GitHubUser,
)
from app.services.analytics import (
    calculate_issue_analytics,
    calculate_repository_analytics,
    calculate_user_activity,
)
from app.services.auth import decode_session_jwt
from app.services.github import (
    get_github_commits,
    get_github_issues,
    get_github_repositories,
    get_github_user,
)
from app.models.db_models import User

router = APIRouter(prefix="/api/github", tags=["GitHub"])


def _session_claims(
    request: Request,
    authorization: Optional[str],
) -> Optional[dict]:
    """Decode the session JWT from the HttpOnly cookie (preferred) or a
    Bearer header fallback. Returns claims or None for anonymous requests."""
    # Lazy import to avoid circulars
    from app.services.auth import read_session_token

    token = read_session_token(request, authorization)
    if not token:
        return None
    try:
        return decode_session_jwt(token)
    except Exception:
        return None


def resolve_oauth_token(
    request: Request,
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
) -> Optional[str]:
    """Return decrypted GitHub OAuth token when a valid session is supplied.

    Returns None for anonymous/public requests so existing behavior is unchanged.
    Only the session owner's stored token is ever used (never another user's).
    """
    claims = _session_claims(request, authorization)
    if not claims:
        return None
    try:
        github_id = int(claims.get("sub", "0"))
    except Exception:
        return None
    user = db.query(User).filter(User.github_id == github_id).first()
    if not user or not user.github_token_encrypted:
        return None
    # Lazy import to avoid circulars
    from app.services.auth import decrypt_github_token

    try:
        return decrypt_github_token(user.github_token_encrypted)
    except Exception:
        return None


def resolve_session_login(
    request: Request,
    authorization: Optional[str] = Header(default=None),
) -> Optional[str]:
    """Return session login claim if valid, else None (used to gate private access)."""
    claims = _session_claims(request, authorization)
    if not claims:
        return None
    try:
        return str(claims.get("login", "") or "").lower() or None
    except Exception:
        return None


@router.get(
    "/user/{username}",
    response_model=GitHubUser,
    summary="Get GitHub User Profile",
)
def fetch_user(
    username: str,
    refresh: bool = Query(
        default=False,
        description="Force fresh fetch from GitHub, bypassing cache",
    ),
    db: Session = Depends(get_db),
):
    """Retrieve structured GitHub user profile information by username with database caching."""
    return get_github_user(username, db=db, refresh=refresh)


@router.get(
    "/repos/{username}",
    response_model=GitHubRepositoriesResponse,
    summary="Get GitHub User Repositories",
)
def fetch_repositories(
    request: Request,
    username: str,
    include_private: bool = Query(
        default=False,
        description="Include private repos using your linked OAuth token (requires Authorization: Bearer <JWT> and matching login)",
    ),
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
):
    """Retrieve repositories. Public by default; private+public when include_private with own session."""
    token: Optional[str] = None
    private_included = False
    if include_private:
        session_login = resolve_session_login(request, authorization)
        if session_login and session_login == username.strip().lower():
            token = resolve_oauth_token(request, authorization, db)
            private_included = bool(token)
    repos = get_github_repositories(username, access_token=token, include_private=private_included)
    return GitHubRepositoriesResponse(
        username=username,
        total=len(repos),
        repositories=repos,
        private_included=private_included,
    )


@router.get(
    "/repos/{username}/analytics",
    response_model=GitHubAnalyticsResponse,
    summary="Get GitHub User Repository Analytics",
)
def fetch_repository_analytics(
    request: Request,
    username: str,
    include_private: bool = Query(default=False),
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
):
    """Retrieve aggregated repository statistics and language distribution."""
    token: Optional[str] = None
    if include_private:
        session_login = resolve_session_login(request, authorization)
        if session_login and session_login == username.strip().lower():
            token = resolve_oauth_token(request, authorization, db)
    repos = get_github_repositories(username, access_token=token, include_private=bool(token))
    return calculate_repository_analytics(username, repos)


@router.get(
    "/commits/{username}",
    response_model=GitHubCommitsResponse,
    summary="Get Recent Public Commits",
)
def fetch_commits(
    request: Request,
    username: str,
    limit: int = Query(
        default=30,
        ge=1,
        le=50,
        description="Maximum number of commits to retrieve across active public repositories",
    ),
    include_private: bool = Query(default=False),
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
):
    """Retrieve recent commits across repositories, distinguishing commit authors from repository owners."""
    token: Optional[str] = None
    if include_private:
        session_login = resolve_session_login(request, authorization)
        if session_login and session_login == username.strip().lower():
            token = resolve_oauth_token(request, authorization, db)
    commits, partial = get_github_commits(username, limit=limit, access_token=token)
    user_commits = sum(1 for c in commits if c.is_user_author)
    return GitHubCommitsResponse(
        username=username,
        total_commits=len(commits),
        user_commits=user_commits,
        commits=commits,
        partial=partial,
    )


@router.get(
    "/activity/{username}",
    response_model=GitHubActivityResponse,
    summary="Get Developer Commit & Repository Activity",
)
def fetch_activity(
    request: Request,
    username: str,
    include_private: bool = Query(default=False),
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
):
    """Retrieve aggregated activity: daily commit frequency, monthly volume, and most-active repositories."""
    token: Optional[str] = None
    if include_private:
        session_login = resolve_session_login(request, authorization)
        if session_login and session_login == username.strip().lower():
            token = resolve_oauth_token(request, authorization, db)
    # Fetch the repo list once and share it with the commits scan so one
    # /activity call costs a single repos request (cached for parallel calls).
    repos = get_github_repositories(username, access_token=token, include_private=bool(token))
    commits, partial = get_github_commits(username, limit=50, access_token=token, repos=repos)
    return calculate_user_activity(username, commits, repos, partial=partial)


@router.get(
    "/issues/{username}",
    response_model=GitHubIssuesResponse,
    summary="Get Recent Issues",
)
def fetch_issues(
    request: Request,
    username: str,
    limit: int = Query(
        default=30,
        ge=1,
        le=50,
        description="Maximum number of recent issues to retrieve across active repositories",
    ),
    include_private: bool = Query(default=False),
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
):
    """Retrieve recent issues across repositories. Pull requests are excluded."""
    token: Optional[str] = None
    if include_private:
        session_login = resolve_session_login(request, authorization)
        if session_login and session_login == username.strip().lower():
            token = resolve_oauth_token(request, authorization, db)
    issues, partial = get_github_issues(username, limit=limit, access_token=token)
    open_count = sum(1 for i in issues if i.state == "open")
    closed_count = sum(1 for i in issues if i.state == "closed")
    return GitHubIssuesResponse(
        username=username,
        total_issues=len(issues),
        open_issues=open_count,
        closed_issues=closed_count,
        issues=issues,
        partial=partial,
    )


@router.get(
    "/issues/{username}/analytics",
    response_model=GitHubIssueAnalyticsResponse,
    summary="Get Issue Analytics",
)
def fetch_issue_analytics(
    request: Request,
    username: str,
    limit: int = Query(
        default=50,
        ge=1,
        le=50,
        description="Maximum number of recent issues to aggregate across active repositories",
    ),
    include_private: bool = Query(default=False),
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
):
    """Retrieve aggregated issue metrics: totals plus per-repository and per-label breakdowns."""
    token: Optional[str] = None
    if include_private:
        session_login = resolve_session_login(request, authorization)
        if session_login and session_login == username.strip().lower():
            token = resolve_oauth_token(request, authorization, db)
    issues, partial = get_github_issues(username, limit=limit, access_token=token)
    return calculate_issue_analytics(username, issues, partial=partial)
