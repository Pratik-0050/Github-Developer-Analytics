import time
from datetime import datetime, timezone
from typing import Any, Optional
import requests
from requests.adapters import HTTPAdapter
from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.db_models import AnalyticsRun, User
from app.models.github import (
    GitHubCommit,
    GitHubIssue,
    GitHubPullRequest,
    GitHubRepository,
    GitHubUser,
)

# ─── Shared HTTP session (connection reuse) ──────────────────────────────
# A single module-level Session keeps a pooled HTTPS connection to
# api.github.com alive across requests instead of paying for a new
# TCP+TLS handshake on every call (requests.get() creates a throwaway
# session internally). Thread-safe for our usage; never store per-user
# tokens on it — Authorization is passed per-request via headers.
_session: Optional[requests.Session] = None


def _get_session() -> requests.Session:
    """Return the shared pooled Session to api.github.com."""
    global _session
    if _session is None:
        sess = requests.Session()
        adapter = HTTPAdapter(pool_connections=10, pool_maxsize=10, max_retries=0)
        sess.mount("https://", adapter)
        sess.mount("http://", adapter)
        sess.headers.update(
            {
                "Accept": "application/vnd.github.v3+json",
                "User-Agent": "GitHub-Developer-Analytics-API",
            }
        )
        _session = sess
    return _session


def _github_get(
    url: str,
    *,
    headers: Optional[dict[str, str]] = None,
    params: Optional[dict[str, Any]] = None,
    timeout: float = 10.0,
) -> requests.Response:
    """Single-attempt GET via the shared session. Never retries internally.

    Network failures map to HTTP 503. Rate-limit handling is left to the
    caller (single attempt, no retry loop) via _rate_limit_wait_seconds().
    """
    try:
        return _get_session().get(url, headers=headers, params=params, timeout=timeout)
    except requests.exceptions.RequestException:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Unable to connect to GitHub API",
        )


# ─── In-memory TTL cache (repos / commits / pulls / issues) ─────────────
# User profiles already have a persistent DB cache; these list endpoints
# previously hit GitHub on every dashboard load with zero caching. Entries
# are keyed by (kind, username, token-mode, limit) and expire after
# CACHE_TTL_SECONDS. Token *values* are never used as keys.
_github_cache: dict[tuple, tuple[float, Any]] = {}


def _cache_get(key: tuple) -> Optional[Any]:
    entry = _github_cache.get(key)
    if not entry:
        return None
    expires_at, value = entry
    if time.monotonic() >= expires_at:
        _github_cache.pop(key, None)
        return None
    return value


def _cache_set(key: tuple, value: Any, ttl: Optional[float] = None) -> None:
    ttl_seconds = float(ttl if ttl is not None else settings.CACHE_TTL_SECONDS)
    _github_cache[key] = (time.monotonic() + ttl_seconds, value)


def clear_github_cache() -> None:
    """Evict all in-memory GitHub list entries (used by tests / refresh)."""
    _github_cache.clear()


def _token_mode(access_token: Optional[str]) -> str:
    """Cache-key component: only whether a per-request token is used."""
    return "private" if access_token else "public"


# ─── Rate-limit helpers ──────────────────────────────────────────────────
def _rate_limit_wait_seconds(response: Any) -> int:
    """Honor GitHub's Retry-After / X-RateLimit-Reset guidance (seconds).

    Returns 0 when the response carries no usable reset signal. Defensive
    about header shapes (tests use MagicMock responses).
    """
    headers = getattr(response, "headers", None) or {}

    def _get(name: str) -> Optional[str]:
        try:
            value = headers.get(name)
        except Exception:
            return None
        return value if isinstance(value, str) and value.strip() else None

    retry_after = _get("Retry-After")
    if retry_after is not None:
        try:
            return max(0, int(float(retry_after)))
        except (TypeError, ValueError):
            pass

    reset_at = _get("X-RateLimit-Reset")
    if reset_at is not None:
        try:
            wait = int(float(reset_at)) - int(time.time())
            return max(0, min(wait, 3600))
        except (TypeError, ValueError):
            pass
    return 0


def _rate_limit_exceeded(wait_seconds: int = 0) -> HTTPException:
    """Build a clear 429 error telling the caller when it may retry.

    Never retried server-side — the client decides, guided by this message.
    """
    if wait_seconds > 0:
        detail = (
            "GitHub API rate limit exceeded. "
            f"Please wait ~{wait_seconds}s before retrying "
            "(avoid repeated Refresh — cached results are served where available)."
        )
    else:
        detail = (
            "GitHub API rate limit exceeded. "
            "Please wait a minute before retrying "
            "(avoid repeated Refresh — cached results are served where available)."
        )
    return HTTPException(
        status_code=429,
        detail=detail,
        headers={"Retry-After": str(wait_seconds)} if wait_seconds > 0 else None,
    )


def _is_rate_limited(response: Any) -> bool:
    """True for 403/429 rate-limit responses (incl. secondary limits)."""
    code = getattr(response, "status_code", None)
    if code == 429:
        return True
    if code == 403:
        try:
            body = response.json()
            message = str(body.get("message", "")).lower() if isinstance(body, dict) else ""
        except Exception:
            message = ""
        remaining = None
        try:
            remaining = response.headers.get("X-RateLimit-Remaining")
        except Exception:
            remaining = None
        return (
            "rate limit" in message
            or "secondary" in message
            or (isinstance(remaining, str) and remaining.strip() == "0")
            or not message  # conservative: unexplained 403 on api.github.com
        )
    return False


# Pagination / fan-out guardrails: one dashboard load must not crawl the API.
# Repos are a single page (no auto-pagination); per-repo item scans are
# capped so commits+pulls+issues stay within a small request budget.
MAX_ACTIVE_REPOS = 5
PER_REPO_ITEMS = 10
REPOS_PER_PAGE = 100


def get_github_headers(access_token: Optional[str] = None) -> dict[str, str]:
    """Construct standard headers for GitHub API requests with optional token authorization."""
    headers = {
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "GitHub-Developer-Analytics-API",
    }
    # Priority: per-request OAuth user token > server-side GITHUB_TOKEN.
    # The token value is only ever sent in this server-side header —
    # it is never returned to, or logged for, the frontend.
    token = (access_token or settings.GITHUB_TOKEN or "").strip()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def get_github_user(username: str, db: Optional[Session] = None, refresh: bool = False) -> GitHubUser:
    """Fetch user profile information from cache or GitHub API.

    Args:
        username (str): The GitHub username to query.
        db (Session, optional): Database session for caching and analytics audit.
        refresh (bool): When True, bypass cache and fetch freshly from GitHub.

    Returns:
        GitHubUser: Filtered, validated, and cached user data model.

    Raises:
        HTTPException: Sanitized HTTP error detailing the outcome.
    """
    clean_username = username.strip()
    start_time = time.perf_counter()
    now_utc = datetime.now(timezone.utc)

    cached_user: Optional[User] = None
    is_fresh = False

    # 1. Check database cache if DB session is available
    if db is not None:
        cached_user = (
            db.query(User)
            .filter(func.lower(User.login) == clean_username.lower())
            .first()
        )

        if cached_user and not refresh:
            synced_at = cached_user.last_synced_at
            if synced_at.tzinfo is None:
                synced_at = synced_at.replace(tzinfo=timezone.utc)

            age_seconds = (now_utc - synced_at).total_seconds()
            if age_seconds < settings.CACHE_TTL_SECONDS:
                is_fresh = True

    # 2. Return fresh cached profile if valid
    if is_fresh and cached_user is not None and db is not None:
        elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)
        audit_run = AnalyticsRun(
            user_id=cached_user.id,
            username=cached_user.login,
            query_type="profile_lookup",
            cache_hit=True,
            status="success",
            response_time_ms=elapsed_ms,
        )
        db.add(audit_run)
        try:
            db.commit()
        except Exception:
            db.rollback()

        return GitHubUser(
            login=cached_user.login,
            id=cached_user.github_id,
            name=cached_user.name,
            avatar_url=cached_user.avatar_url,
            html_url=cached_user.html_url,
            bio=cached_user.bio,
            company=cached_user.company,
            location=cached_user.location,
            blog=cached_user.blog,
            public_repos=cached_user.public_repos,
            followers=cached_user.followers,
            following=cached_user.following,
            created_at=cached_user.github_created_at or "",
            cached=True,
            last_synced_at=cached_user.last_synced_at.isoformat(),
            stale=False,
        )

    # 3. Query external GitHub REST API
    url = f"{settings.GITHUB_API_URL.rstrip('/')}/users/{clean_username}"
    headers = get_github_headers()

    try:
        response = _github_get(url, headers=headers, timeout=10.0)
    except HTTPException as exc:
        if exc.status_code != status.HTTP_503_SERVICE_UNAVAILABLE:
            raise
        if cached_user and db is not None:
            # Resilient fallback: return stale cached record rather than failing
            elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)
            audit_run = AnalyticsRun(
                user_id=cached_user.id,
                username=cached_user.login,
                query_type="profile_lookup",
                cache_hit=True,
                status="network_error_fallback",
                response_time_ms=elapsed_ms,
            )
            db.add(audit_run)
            db.commit()
            return GitHubUser(
                login=cached_user.login,
                id=cached_user.github_id,
                name=cached_user.name,
                avatar_url=cached_user.avatar_url,
                html_url=cached_user.html_url,
                bio=cached_user.bio,
                company=cached_user.company,
                location=cached_user.location,
                blog=cached_user.blog,
                public_repos=cached_user.public_repos,
                followers=cached_user.followers,
                following=cached_user.following,
                created_at=cached_user.github_created_at or "",
                cached=True,
                last_synced_at=cached_user.last_synced_at.isoformat(),
                stale=True,
            )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Unable to connect to GitHub API",
        )

    elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)

    # 4. Handle HTTP responses from GitHub
    if response.status_code == 404:
        if db is not None:
            audit_run = AnalyticsRun(
                username=clean_username,
                query_type="profile_lookup",
                cache_hit=False,
                status="not_found",
                response_time_ms=elapsed_ms,
            )
            db.add(audit_run)
            db.commit()
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"GitHub user '{clean_username}' not found",
        )
    elif _is_rate_limited(response):
        # Rate limit exceeded — fallback to stale cached record if available,
        # otherwise surface a clear 429 with GitHub's own retry guidance.
        # Single attempt only: never retried server-side.
        wait_seconds = _rate_limit_wait_seconds(response)
        if cached_user and db is not None:
            audit_run = AnalyticsRun(
                user_id=cached_user.id,
                username=cached_user.login,
                query_type="profile_lookup",
                cache_hit=True,
                status="rate_limited_fallback",
                response_time_ms=elapsed_ms,
            )
            db.add(audit_run)
            db.commit()
            return GitHubUser(
                login=cached_user.login,
                id=cached_user.github_id,
                name=cached_user.name,
                avatar_url=cached_user.avatar_url,
                html_url=cached_user.html_url,
                bio=cached_user.bio,
                company=cached_user.company,
                location=cached_user.location,
                blog=cached_user.blog,
                public_repos=cached_user.public_repos,
                followers=cached_user.followers,
                following=cached_user.following,
                created_at=cached_user.github_created_at or "",
                cached=True,
                last_synced_at=cached_user.last_synced_at.isoformat(),
                stale=True,
            )
        if db is not None:
            audit_run = AnalyticsRun(
                username=clean_username,
                query_type="profile_lookup",
                cache_hit=False,
                status="rate_limited",
                response_time_ms=elapsed_ms,
            )
            db.add(audit_run)
            db.commit()
        raise _rate_limit_exceeded(wait_seconds)
    elif response.status_code >= 500:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="GitHub API service error",
        )
    elif not response.ok:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"GitHub API error occurred (Status {response.status_code})",
        )

    data = response.json()

    # 5. Upsert user into database cache
    if db is not None:
        try:
            if cached_user:
                cached_user.github_id = data.get("id", cached_user.github_id)
                cached_user.name = data.get("name")
                cached_user.avatar_url = data.get("avatar_url", cached_user.avatar_url)
                cached_user.html_url = data.get("html_url", cached_user.html_url)
                cached_user.bio = data.get("bio")
                cached_user.company = data.get("company")
                cached_user.location = data.get("location")
                cached_user.blog = data.get("blog")
                cached_user.public_repos = data.get("public_repos", 0)
                cached_user.public_gists = data.get("public_gists", 0)
                cached_user.followers = data.get("followers", 0)
                cached_user.following = data.get("following", 0)
                cached_user.github_created_at = str(data.get("created_at", ""))
                cached_user.last_synced_at = now_utc
                target_user = cached_user
            else:
                target_user = User(
                    github_id=data.get("id", 0),
                    login=data.get("login", clean_username),
                    name=data.get("name"),
                    avatar_url=data.get("avatar_url", ""),
                    html_url=data.get("html_url", ""),
                    bio=data.get("bio"),
                    company=data.get("company"),
                    location=data.get("location"),
                    blog=data.get("blog"),
                    public_repos=data.get("public_repos", 0),
                    public_gists=data.get("public_gists", 0),
                    followers=data.get("followers", 0),
                    following=data.get("following", 0),
                    github_created_at=str(data.get("created_at", "")),
                    last_synced_at=now_utc,
                )
                db.add(target_user)
                db.flush()

            audit_run = AnalyticsRun(
                user_id=target_user.id,
                username=target_user.login,
                query_type="profile_lookup",
                cache_hit=False,
                status="success",
                response_time_ms=elapsed_ms,
            )
            db.add(audit_run)
            db.commit()
        except Exception:
            db.rollback()

    return GitHubUser(
        login=data.get("login", clean_username),
        id=data.get("id", 0),
        name=data.get("name"),
        avatar_url=data.get("avatar_url", ""),
        html_url=data.get("html_url", ""),
        bio=data.get("bio"),
        company=data.get("company"),
        location=data.get("location"),
        blog=data.get("blog"),
        public_repos=data.get("public_repos", 0),
        followers=data.get("followers", 0),
        following=data.get("following", 0),
        created_at=str(data.get("created_at", "")),
        cached=False,
        last_synced_at=now_utc.isoformat(),
        stale=False,
    )


def get_github_repositories(
    username: str,
    access_token: Optional[str] = None,
    include_private: bool = False,
) -> list[GitHubRepository]:
    """Fetch repositories for a given GitHub user.

    Args:
        username (str): The GitHub username whose repositories to query.
        access_token (str, optional): OAuth user token. When supplied with
            include_private=True, queries /user/repos (visibility=all) so
            private repos are included. Otherwise queries public /users/{u}/repos.
        include_private (bool): Only honored when access_token is provided.

    Returns:
        list[GitHubRepository]: Filtered list of validated repository models.

    Raises:
        HTTPException: Sanitized HTTP error detailing the outcome.
    """
    clean_username = username.strip()
    use_private = bool(include_private and access_token)
    cache_key = ("repos", clean_username.lower(), _token_mode(access_token if use_private else None))
    cached = _cache_get(cache_key)
    if cached is not None:
        return list(cached)

    if use_private:
        url = f"{settings.GITHUB_API_URL.rstrip('/')}/user/repos"
        params = {
            "per_page": REPOS_PER_PAGE,
            "sort": "updated",
            "direction": "desc",
            "visibility": "all",
        }
    else:
        url = f"{settings.GITHUB_API_URL.rstrip('/')}/users/{clean_username}/repos"
        # Single page on purpose: auto-paginating every dashboard load would
        # multiply GitHub calls. The dashboard only needs the active repos.
        params = {
            "per_page": REPOS_PER_PAGE,
            "sort": "updated",
            "direction": "desc",
        }
    headers = get_github_headers(access_token if use_private else None)

    response = _github_get(url, headers=headers, params=params, timeout=10.0)

    if response.status_code == 404:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"GitHub user '{username}' not found",
        )
    elif response.status_code == 401:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="GitHub token rejected. Please sign in again.",
        )
    elif _is_rate_limited(response):
        # Single attempt only — never retried server-side.
        raise _rate_limit_exceeded(_rate_limit_wait_seconds(response))
    elif response.status_code >= 500:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="GitHub API service error",
        )
    elif not response.ok:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"GitHub API error occurred (Status {response.status_code})",
        )

    raw_repos = response.json()
    if not isinstance(raw_repos, list):
        return []

    repositories: list[GitHubRepository] = []
    for item in raw_repos:
        repo = GitHubRepository(
            id=item.get("id", 0),
            name=item.get("name", ""),
            full_name=item.get("full_name", ""),
            description=item.get("description"),
            html_url=item.get("html_url", ""),
            language=item.get("language"),
            stargazers_count=item.get("stargazers_count", 0),
            forks_count=item.get("forks_count", 0),
            open_issues_count=item.get("open_issues_count", 0),
            watchers_count=item.get("watchers_count", 0),
            size=item.get("size", 0),
            default_branch=item.get("default_branch", "main"),
            created_at=str(item.get("created_at", "")),
            updated_at=str(item.get("updated_at", "")),
            pushed_at=str(item.get("pushed_at", "")) if item.get("pushed_at") else None,
            fork=bool(item.get("fork", False)),
            archived=bool(item.get("archived", False)),
            private=bool(item.get("private", False)),
        )
        repositories.append(repo)

    _cache_set(cache_key, repositories)
    return repositories


def get_github_commits(
    username: str,
    limit: int = 30,
    access_token: Optional[str] = None,
    repos: Optional[list[GitHubRepository]] = None,
) -> tuple[list[GitHubCommit], bool]:
    """Fetch recent commits across public repositories for a given GitHub user.

    Limits external requests to active repositories to preserve rate limits,
    handles empty/inaccessible repositories gracefully, and distinguishes commit authors
    from repository owners.

    Args:
        username (str): Target GitHub username.
        limit (int): Maximum number of recent commits to return (default 30).
        access_token (str, optional): OAuth token enabling private repo commit access.
        repos (list, optional): Pre-fetched repositories. When supplied, the
            extra repos-list request is skipped — callers aggregating several
            datasets (e.g. /activity) should fetch once and share.

    Returns:
        tuple[list[GitHubCommit], bool]: (list of parsed commits, is_partial_flag).
    """
    clean_username = username.strip()
    limit = max(1, min(int(limit), 50))
    headers = get_github_headers(access_token)

    cache_key = ("commits", clean_username.lower(), _token_mode(access_token), limit)
    if repos is None:
        cached = _cache_get(cache_key)
        if cached is not None:
            commits_cached, partial_cached = cached
            return list(commits_cached), partial_cached

    # 1. Retrieve user's repositories (private included when caller passes a token)
    # Cached inside get_github_repositories, so parallel dashboard calls share it.
    if repos is None:
        repos = get_github_repositories(
            clean_username, access_token=access_token, include_private=bool(access_token)
        )
    if not repos:
        return [], False

    # 2. Select the top active repositories (sorted by latest push or update date)
    def repo_activity_key(r: GitHubRepository) -> str:
        return r.pushed_at or r.updated_at or ""

    active_repos = sorted(repos, key=repo_activity_key, reverse=True)
    # Capped fan-out: at most MAX_ACTIVE_REPOS repos x PER_REPO_ITEMS commits.
    target_repos = active_repos[:MAX_ACTIVE_REPOS]

    commits_by_sha: dict[str, GitHubCommit] = {}
    is_partial = False

    for repo in target_repos:
        repo_owner = repo.full_name.split("/")[0] if "/" in repo.full_name else clean_username
        repo_name = repo.name
        commits_url = f"{settings.GITHUB_API_URL.rstrip('/')}/repos/{repo_owner}/{repo_name}/commits"
        params = {"per_page": PER_REPO_ITEMS}

        try:
            resp = _github_get(commits_url, headers=headers, params=params, timeout=6.0)
        except HTTPException as exc:
            if exc.status_code == status.HTTP_503_SERVICE_UNAVAILABLE:
                # Network issue or timeout on this repository — continue to others
                is_partial = True
                continue
            raise

        if resp.status_code == 409:
            # Git repository is empty — completely normal for new repos
            continue
        elif _is_rate_limited(resp):
            # Rate limited — flag partial and stop further requests.
            # Single attempt only: never retried server-side.
            is_partial = True
            break
        elif resp.status_code == 404:
            # Repository renamed, private, or removed
            is_partial = True
            continue
        elif not resp.ok:
            is_partial = True
            continue

        data = resp.json()
        if not isinstance(data, list):
            continue

        for item in data:
            sha = item.get("sha", "")
            if not sha or sha in commits_by_sha:
                continue

            commit_dict = item.get("commit") or {}
            raw_message = (commit_dict.get("message") or "").strip()
            # First line of commit message for clean tabular display
            clean_message = raw_message.split("\n")[0] if raw_message else "No commit message"

            # Author attribution: inspect GitHub account author vs git author
            gh_author = item.get("author") or {}
            author_login = gh_author.get("login")
            author_avatar = gh_author.get("avatar_url")

            git_author = commit_dict.get("author") or {}
            author_name = git_author.get("name") or author_login or "Unknown"
            committed_date = git_author.get("date") or ""

            # Distinguish commit author from repository owner:
            # A commit belongs to the searched user ONLY if their login or author name matches
            is_user = False
            if author_login and author_login.lower() == clean_username.lower():
                is_user = True
            elif not author_login and author_name.lower() == clean_username.lower():
                is_user = True

            html_url = item.get("html_url") or f"https://github.com/{repo_owner}/{repo_name}/commit/{sha}"

            commit_model = GitHubCommit(
                sha=sha,
                short_sha=sha[:7],
                message=clean_message,
                repository_name=repo_name,
                repository_url=repo.html_url,
                author_name=author_name,
                author_login=author_login,
                author_avatar_url=author_avatar,
                committed_date=committed_date,
                html_url=html_url,
                is_user_author=is_user,
            )
            commits_by_sha[sha] = commit_model

    # 3. Sort all commits chronologically descending and cap at requested limit
    sorted_commits = sorted(
        commits_by_sha.values(),
        key=lambda c: c.committed_date,
        reverse=True,
    )

    result = sorted_commits[:limit], is_partial
    _cache_set(cache_key, (result[0], result[1]))
    return result


def get_github_pull_requests(
    username: str,
    limit: int = 30,
    access_token: Optional[str] = None,
    repos: Optional[list[GitHubRepository]] = None,
) -> tuple[list[GitHubPullRequest], bool]:
    """Fetch recent pull requests across public repositories for a given GitHub user.

    Scans active repositories, normalizes lifecycle states ('open', 'merged', 'closed'),
    handles rate limits and empty repositories gracefully with partial indicators.

    Args:
        username (str): Target GitHub username.
        limit (int): Maximum number of recent pull requests to return (default 30).
        access_token (str, optional): OAuth token enabling private repo PR access.
        repos (list, optional): Pre-fetched repositories to skip the extra list request.

    Returns:
        tuple[list[GitHubPullRequest], bool]: (list of parsed pull requests, is_partial_flag).
    """
    clean_username = username.strip()
    limit = max(1, min(int(limit), 50))
    headers = get_github_headers(access_token)

    cache_key = ("pulls", clean_username.lower(), _token_mode(access_token), limit)
    if repos is None:
        cached = _cache_get(cache_key)
        if cached is not None:
            pulls_cached, partial_cached = cached
            return list(pulls_cached), partial_cached

    # 1. Retrieve user's repositories (private included when caller passes a token)
    # Cached inside get_github_repositories, so parallel dashboard calls share it.
    if repos is None:
        repos = get_github_repositories(
            clean_username, access_token=access_token, include_private=bool(access_token)
        )
    if not repos:
        return [], False

    # 2. Select top active repositories (sorted by latest push or update date)
    def repo_activity_key(r: GitHubRepository) -> str:
        return r.pushed_at or r.updated_at or ""

    active_repos = sorted(repos, key=repo_activity_key, reverse=True)
    target_repos = active_repos[:MAX_ACTIVE_REPOS]

    pulls_by_id: dict[int, GitHubPullRequest] = {}
    is_partial = False

    for repo in target_repos:
        repo_owner = repo.full_name.split("/")[0] if "/" in repo.full_name else clean_username
        repo_name = repo.name
        pulls_url = f"{settings.GITHUB_API_URL.rstrip('/')}/repos/{repo_owner}/{repo_name}/pulls"
        params = {"state": "all", "per_page": PER_REPO_ITEMS}

        try:
            resp = _github_get(pulls_url, headers=headers, params=params, timeout=6.0)
        except HTTPException as exc:
            if exc.status_code == status.HTTP_503_SERVICE_UNAVAILABLE:
                is_partial = True
                continue
            raise

        if resp.status_code == 409:
            # Empty repository
            continue
        elif _is_rate_limited(resp):
            # Rate limited — flag partial and stop further requests.
            # Single attempt only: never retried server-side.
            is_partial = True
            break
        elif resp.status_code == 404:
            is_partial = True
            continue
        elif not resp.ok:
            is_partial = True
            continue

        data = resp.json()
        if not isinstance(data, list):
            continue

        for item in data:
            pr_id = item.get("id")
            if not pr_id or pr_id in pulls_by_id:
                continue

            pr_number = item.get("number", 0)
            raw_title = (item.get("title") or "").strip()
            title = raw_title if raw_title else "Untitled PR"

            user_dict = item.get("user") or {}
            author_login = user_dict.get("login") or "unknown"
            author_avatar = user_dict.get("avatar_url")

            raw_state = item.get("state", "open")
            merged_at = item.get("merged_at")
            closed_at = item.get("closed_at")

            # Determine effective state: open, merged, or closed
            if merged_at:
                effective_state = "merged"
            elif raw_state == "closed":
                effective_state = "closed"
            else:
                effective_state = "open"

            created_at = str(item.get("created_at") or "")
            updated_at = str(item.get("updated_at") or "")
            html_url = item.get("html_url") or f"https://github.com/{repo_owner}/{repo_name}/pull/{pr_number}"
            is_user = author_login.lower() == clean_username.lower()

            pr_model = GitHubPullRequest(
                id=pr_id,
                number=pr_number,
                title=title,
                state=effective_state,
                repository_name=repo_name,
                repository_url=repo.html_url,
                author_login=author_login,
                author_avatar_url=author_avatar,
                created_at=created_at,
                updated_at=updated_at,
                merged_at=str(merged_at) if merged_at else None,
                closed_at=str(closed_at) if closed_at else None,
                html_url=html_url,
                is_user_author=is_user,
            )
            pulls_by_id[pr_id] = pr_model

    # 3. Sort pull requests chronologically descending (by created_at)
    sorted_pulls = sorted(
        pulls_by_id.values(),
        key=lambda p: p.created_at,
        reverse=True,
    )

    result = sorted_pulls[:limit], is_partial
    _cache_set(cache_key, (result[0], result[1]))
    return result


def get_github_issues(
    username: str,
    limit: int = 30,
    access_token: Optional[str] = None,
    repos: Optional[list[GitHubRepository]] = None,
) -> tuple[list[GitHubIssue], bool]:
    """Fetch recent issues across repositories for a given GitHub user.

    Scans top active repositories via the Issues API (state=all), and
    excludes pull requests (GitHub returns PRs as issues with a
    `pull_request` key) so issue counts stay accurate.

    Args:
        username (str): Target GitHub username.
        limit (int): Maximum number of recent issues to return (default 30).
        access_token (str, optional): OAuth token enabling private repo access.
        repos (list, optional): Pre-fetched repositories to skip the extra list request.

    Returns:
        tuple[list[GitHubIssue], bool]: (list of parsed issues, is_partial_flag).
    """
    clean_username = username.strip()
    limit = max(1, min(int(limit), 50))
    headers = get_github_headers(access_token)

    cache_key = ("issues", clean_username.lower(), _token_mode(access_token), limit)
    if repos is None:
        cached = _cache_get(cache_key)
        if cached is not None:
            issues_cached, partial_cached = cached
            return list(issues_cached), partial_cached

    # 1. Retrieve user's repositories (private included when caller passes a token)
    # Cached inside get_github_repositories, so parallel dashboard calls share it.
    if repos is None:
        repos = get_github_repositories(
            clean_username, access_token=access_token, include_private=bool(access_token)
        )
    if not repos:
        return [], False

    # 2. Select top active repositories (sorted by latest push or update date)
    def repo_activity_key(r: GitHubRepository) -> str:
        return r.pushed_at or r.updated_at or ""

    active_repos = sorted(repos, key=repo_activity_key, reverse=True)
    target_repos = active_repos[:MAX_ACTIVE_REPOS]

    issues_by_id: dict[int, GitHubIssue] = {}
    is_partial = False

    for repo in target_repos:
        repo_owner = repo.full_name.split("/")[0] if "/" in repo.full_name else clean_username
        repo_name = repo.name
        issues_url = f"{settings.GITHUB_API_URL.rstrip('/')}/repos/{repo_owner}/{repo_name}/issues"
        params = {"state": "all", "per_page": PER_REPO_ITEMS, "sort": "updated", "direction": "desc"}

        try:
            resp = _github_get(issues_url, headers=headers, params=params, timeout=6.0)
        except HTTPException as exc:
            if exc.status_code == status.HTTP_503_SERVICE_UNAVAILABLE:
                is_partial = True
                continue
            raise

        if resp.status_code == 409:
            # Empty repository
            continue
        elif _is_rate_limited(resp):
            # Rate limited — flag partial and stop further requests.
            # Single attempt only: never retried server-side.
            is_partial = True
            break
        elif resp.status_code == 404:
            is_partial = True
            continue
        elif not resp.ok:
            is_partial = True
            continue

        data = resp.json()
        if not isinstance(data, list):
            continue

        for item in data:
            # Exclude pull requests: the Issues API returns PRs with a `pull_request` key
            if "pull_request" in item:
                continue

            issue_id = item.get("id")
            if not issue_id or issue_id in issues_by_id:
                continue

            raw_title = (item.get("title") or "").strip()
            title = raw_title if raw_title else "Untitled issue"
            raw_state = str(item.get("state", "open")).lower()
            effective_state = "closed" if raw_state == "closed" else "open"

            user_dict = item.get("user") or {}
            author_login = user_dict.get("login") or "unknown"
            author_avatar = user_dict.get("avatar_url")

            raw_labels = item.get("labels") or []
            labels: list[str] = []
            for lbl in raw_labels:
                if isinstance(lbl, dict) and lbl.get("name"):
                    labels.append(str(lbl["name"]))
                elif isinstance(lbl, str) and lbl:
                    labels.append(lbl)

            issue_number = item.get("number", 0)
            created_at = str(item.get("created_at") or "")
            updated_at = str(item.get("updated_at") or "")
            closed_at = item.get("closed_at")
            html_url = item.get("html_url") or (
                f"https://github.com/{repo_owner}/{repo_name}/issues/{issue_number}"
            )
            is_user = author_login.lower() == clean_username.lower()

            issues_by_id[issue_id] = GitHubIssue(
                id=issue_id,
                number=issue_number,
                title=title,
                state=effective_state,
                repository_name=repo_name,
                repository_url=repo.html_url,
                author_login=author_login,
                author_avatar_url=author_avatar,
                labels=labels,
                created_at=created_at,
                updated_at=updated_at,
                closed_at=str(closed_at) if closed_at else None,
                html_url=html_url,
                is_user_author=is_user,
            )

    # 3. Sort issues by most recently updated first
    sorted_issues = sorted(
        issues_by_id.values(),
        key=lambda i: i.updated_at,
        reverse=True,
    )

    result = sorted_issues[:limit], is_partial
    _cache_set(cache_key, (result[0], result[1]))
    return result

