from typing import List, Dict
from sqlalchemy import desc, func
from sqlalchemy.orm import Session
from app.db.session import check_db_connection
from app.models.analytics import AnalyticsRunRead, AnalyticsStatsResponse
from app.models.db_models import AnalyticsRun, User
from app.models.github import (
    ActiveRepositorySummary,
    DailyCommitCount,
    GitHubActivityResponse,
    GitHubAnalyticsResponse,
    GitHubCommit,
    GitHubIssue,
    GitHubIssueAnalyticsResponse,
    IssueLabelCount,
    IssueRepositoryCount,
    GitHubPullAnalyticsResponse,
    GitHubPullRequest,
    GitHubRepository,
    MonthlyCommitCount,
)


def calculate_repository_analytics(
    username: str, repos: List[GitHubRepository]
) -> GitHubAnalyticsResponse:
    """Calculate aggregate repository statistics and language distribution."""
    total_repositories = len(repos)
    total_stars = sum(r.stargazers_count for r in repos)
    total_forks = sum(r.forks_count for r in repos)
    total_open_issues = sum(r.open_issues_count for r in repos)
    total_watchers = sum(r.watchers_count for r in repos)
    forked_repositories = sum(1 for r in repos if r.fork)
    original_repositories = total_repositories - forked_repositories
    archived_repositories = sum(1 for r in repos if r.archived)

    languages: Dict[str, int] = {}
    for r in repos:
        if r.language:
            languages[r.language] = languages.get(r.language, 0) + 1

    top_repositories = sorted(
        repos, key=lambda r: r.stargazers_count, reverse=True
    )[:5]

    return GitHubAnalyticsResponse(
        username=username,
        total_repositories=total_repositories,
        total_stars=total_stars,
        total_forks=total_forks,
        total_open_issues=total_open_issues,
        total_watchers=total_watchers,
        forked_repositories=forked_repositories,
        original_repositories=original_repositories,
        archived_repositories=archived_repositories,
        language_distribution=languages,
        top_repositories=top_repositories,
    )


def calculate_user_activity(
    username: str,
    commits: List[GitHubCommit],
    repos: List[GitHubRepository],
    partial: bool = False,
) -> GitHubActivityResponse:
    """Aggregate commit frequency into daily metrics, monthly totals, and repository rankings."""
    clean_username = username.strip()
    total_commits = len(commits)
    user_commits = sum(1 for c in commits if c.is_user_author)

    # 1. Daily aggregation (YYYY-MM-DD)
    daily_stats: Dict[str, Dict[str, int]] = {}
    for c in commits:
        if not c.committed_date or len(c.committed_date) < 10:
            continue
        day_str = c.committed_date[:10]
        if day_str not in daily_stats:
            daily_stats[day_str] = {"count": 0, "user_count": 0}
        daily_stats[day_str]["count"] += 1
        if c.is_user_author:
            daily_stats[day_str]["user_count"] += 1

    daily_commits = [
        DailyCommitCount(
            date=day,
            count=metrics["count"],
            user_count=metrics["user_count"],
        )
        for day, metrics in sorted(daily_stats.items())
    ]

    # 2. Monthly aggregation (YYYY-MM)
    monthly_stats: Dict[str, Dict[str, int]] = {}
    for c in commits:
        if not c.committed_date or len(c.committed_date) < 7:
            continue
        month_str = c.committed_date[:7]
        if month_str not in monthly_stats:
            monthly_stats[month_str] = {"count": 0, "user_count": 0}
        monthly_stats[month_str]["count"] += 1
        if c.is_user_author:
            monthly_stats[month_str]["user_count"] += 1

    monthly_totals = [
        MonthlyCommitCount(
            month=month,
            count=metrics["count"],
            user_count=metrics["user_count"],
        )
        for month, metrics in sorted(monthly_stats.items())
    ]

    # 3. Most-active repositories ranking
    repo_lookup: Dict[str, GitHubRepository] = {r.name.lower(): r for r in repos}
    repo_counts: Dict[str, int] = {}
    repo_display_names: Dict[str, str] = {}
    repo_urls: Dict[str, str] = {}

    for c in commits:
        key = c.repository_name.lower()
        repo_counts[key] = repo_counts.get(key, 0) + 1
        repo_display_names[key] = c.repository_name
        if key not in repo_urls:
            repo_urls[key] = c.repository_url

    most_active_repositories: List[ActiveRepositorySummary] = []
    for key, count in sorted(repo_counts.items(), key=lambda item: item[1], reverse=True):
        repo_meta = repo_lookup.get(key)
        most_active_repositories.append(
            ActiveRepositorySummary(
                repository_name=repo_display_names.get(key, key),
                commit_count=count,
                repo_url=repo_meta.html_url if repo_meta else repo_urls.get(key, ""),
                stars=repo_meta.stargazers_count if repo_meta else 0,
                language=repo_meta.language if repo_meta else None,
            )
        )

    return GitHubActivityResponse(
        username=clean_username,
        total_commits=total_commits,
        user_commits=user_commits,
        daily_commits=daily_commits,
        monthly_totals=monthly_totals,
        most_active_repositories=most_active_repositories,
        partial=partial,
    )


def calculate_pull_request_analytics(
    username: str,
    pulls: List[GitHubPullRequest],
    partial: bool = False,
) -> GitHubPullAnalyticsResponse:
    """Calculate aggregated pull request metrics: total, open, closed, merged, and merge rate."""
    clean_username = username.strip()
    total_prs = len(pulls)
    open_prs = sum(1 for p in pulls if p.state == "open")
    merged_prs = sum(1 for p in pulls if p.state == "merged")
    closed_prs = sum(1 for p in pulls if p.state == "closed")
    merge_rate = round((merged_prs / total_prs) * 100, 1) if total_prs > 0 else 0.0

    return GitHubPullAnalyticsResponse(
        username=clean_username,
        total_prs=total_prs,
        open_prs=open_prs,
        closed_prs=closed_prs,
        merged_prs=merged_prs,
        merge_rate=merge_rate,
        partial=partial,
    )


def calculate_issue_analytics(
    username: str,
    issues: List[GitHubIssue],
    partial: bool = False,
) -> GitHubIssueAnalyticsResponse:
    """Aggregate issue metrics: totals by state plus per-repository and per-label breakdowns."""
    clean_username = username.strip()
    total_issues = len(issues)
    open_issues = sum(1 for i in issues if i.state == "open")
    closed_issues = sum(1 for i in issues if i.state == "closed")

    # Group by repository (open/closed split per repo)
    repo_stats: Dict[str, Dict[str, object]] = {}
    for issue in issues:
        key = issue.repository_name.lower()
        entry = repo_stats.get(key)
        if entry is None:
            entry = {
                "display": issue.repository_name,
                "url": issue.repository_url,
                "open": 0,
                "closed": 0,
            }
            repo_stats[key] = entry
        if issue.state == "open":
            entry["open"] = int(entry["open"]) + 1
        else:
            entry["closed"] = int(entry["closed"]) + 1

    issues_by_repository = [
        IssueRepositoryCount(
            repository_name=str(entry["display"]),
            repo_url=str(entry["url"]),
            open_count=int(entry["open"]),
            closed_count=int(entry["closed"]),
            total_count=int(entry["open"]) + int(entry["closed"]),
        )
        for entry in sorted(
            repo_stats.values(),
            key=lambda e: (int(e["open"]) + int(e["closed"])),
            reverse=True,
        )
    ]

    # Group by label (an issue with N labels counts once per label)
    label_counts: Dict[str, int] = {}
    for issue in issues:
        for label in issue.labels:
            label_counts[label] = label_counts.get(label, 0) + 1

    issues_by_label = [
        IssueLabelCount(label=label, count=count)
        for label, count in sorted(label_counts.items(), key=lambda kv: kv[1], reverse=True)
    ]

    return GitHubIssueAnalyticsResponse(
        username=clean_username,
        total_issues=total_issues,
        open_issues=open_issues,
        closed_issues=closed_issues,
        issues_by_repository=issues_by_repository,
        issues_by_label=issues_by_label,
        partial=partial,
    )


def get_recent_runs(db: Session, limit: int = 20) -> List[AnalyticsRun]:
    """Retrieve the most recent analytics search runs."""
    return (
        db.query(AnalyticsRun)
        .order_by(desc(AnalyticsRun.created_at))
        .limit(limit)
        .all()
    )


def get_analytics_stats(db: Session) -> AnalyticsStatsResponse:
    """Calculate aggregated performance metrics and cache statistics."""
    total_cached_profiles = db.query(func.count(User.id)).scalar() or 0
    total_queries = db.query(func.count(AnalyticsRun.id)).scalar() or 0
    total_cache_hits = (
        db.query(func.count(AnalyticsRun.id))
        .filter(AnalyticsRun.cache_hit.is_(True))
        .scalar()
        or 0
    )
    total_cache_misses = total_queries - total_cache_hits
    cache_hit_rate_pct = (
        round((total_cache_hits / total_queries) * 100, 1) if total_queries > 0 else 0.0
    )
    avg_latency = (
        db.query(func.avg(AnalyticsRun.response_time_ms)).scalar() or 0.0
    )

    is_connected, db_latency_ms, dialect = check_db_connection()
    db_status = f"connected ({dialect})" if is_connected else "disconnected"

    recent_runs_db = get_recent_runs(db, limit=10)
    recent_runs_read = [AnalyticsRunRead.model_validate(r) for r in recent_runs_db]

    return AnalyticsStatsResponse(
        total_cached_profiles=total_cached_profiles,
        total_queries=total_queries,
        total_cache_hits=total_cache_hits,
        total_cache_misses=total_cache_misses,
        cache_hit_rate_pct=cache_hit_rate_pct,
        average_response_time_ms=round(avg_latency, 2),
        database_status=db_status,
        database_latency_ms=db_latency_ms,
        recent_runs=recent_runs_read,
    )
