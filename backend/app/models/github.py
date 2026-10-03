"""Pydantic models for GitHub data structures."""

from typing import Optional
from pydantic import BaseModel, ConfigDict


class GitHubUser(BaseModel):
    """Structured response model for GitHub user profiles."""

    login: str
    id: int
    name: Optional[str] = None
    avatar_url: str
    html_url: str
    bio: Optional[str] = None
    company: Optional[str] = None
    location: Optional[str] = None
    blog: Optional[str] = None
    public_repos: int
    followers: int
    following: int
    created_at: str

    # Caching metadata
    cached: bool = False
    last_synced_at: Optional[str] = None
    stale: bool = False

    model_config = ConfigDict(from_attributes=True)


class GitHubRepository(BaseModel):
    """Structured model for individual GitHub repositories."""

    id: int
    name: str
    full_name: str
    description: Optional[str] = None
    html_url: str
    language: Optional[str] = None
    stargazers_count: int
    forks_count: int
    open_issues_count: int
    watchers_count: int
    size: int
    default_branch: str
    created_at: str
    updated_at: str
    pushed_at: Optional[str] = None
    fork: bool
    archived: bool
    private: bool = False

    model_config = ConfigDict(from_attributes=True)


class GitHubRepositoriesResponse(BaseModel):
    """Response envelope for user repositories."""

    username: str
    total: int
    repositories: list[GitHubRepository]
    private_included: bool = False

    model_config = ConfigDict(from_attributes=True)


class GitHubAnalyticsResponse(BaseModel):
    """Aggregated repository analytics response model."""

    username: str
    total_repositories: int
    total_stars: int
    total_forks: int
    total_open_issues: int
    total_watchers: int
    forked_repositories: int
    original_repositories: int
    archived_repositories: int
    language_distribution: dict[str, int]
    top_repositories: list[GitHubRepository]

    model_config = ConfigDict(from_attributes=True)


class GitHubCommit(BaseModel):
    """Structured model for individual GitHub commits across repositories."""

    sha: str
    short_sha: str
    message: str
    repository_name: str
    repository_url: str
    author_name: str
    author_login: Optional[str] = None
    author_avatar_url: Optional[str] = None
    committed_date: str
    html_url: str
    is_user_author: bool = False

    model_config = ConfigDict(from_attributes=True)


class GitHubCommitsResponse(BaseModel):
    """Response envelope for recent public repository commits."""

    username: str
    total_commits: int
    user_commits: int
    commits: list[GitHubCommit]
    partial: bool = False

    model_config = ConfigDict(from_attributes=True)


class DailyCommitCount(BaseModel):
    """Daily commit activity frequency."""

    date: str
    count: int
    user_count: int


class MonthlyCommitCount(BaseModel):
    """Monthly commit aggregation."""

    month: str
    count: int
    user_count: int


class ActiveRepositorySummary(BaseModel):
    """Activity ranking per repository."""

    repository_name: str
    commit_count: int
    repo_url: str
    stars: int = 0
    language: Optional[str] = None


class GitHubActivityResponse(BaseModel):
    """Aggregated commit and repository activity analytics."""

    username: str
    total_commits: int
    user_commits: int
    daily_commits: list[DailyCommitCount]
    monthly_totals: list[MonthlyCommitCount]
    most_active_repositories: list[ActiveRepositorySummary]
    partial: bool = False

    model_config = ConfigDict(from_attributes=True)


class GitHubPullRequest(BaseModel):
    """Structured model for individual pull requests."""

    id: int
    number: int
    title: str
    state: str  # "open", "closed", "merged"
    repository_name: str
    repository_url: str
    author_login: str
    author_avatar_url: Optional[str] = None
    created_at: str
    updated_at: str
    merged_at: Optional[str] = None
    closed_at: Optional[str] = None
    html_url: str
    is_user_author: bool = False

    model_config = ConfigDict(from_attributes=True)


class GitHubPullsResponse(BaseModel):
    """Response envelope for recent public pull requests."""

    username: str
    total_pulls: int
    pulls: list[GitHubPullRequest]
    partial: bool = False

    model_config = ConfigDict(from_attributes=True)


class GitHubPullAnalyticsResponse(BaseModel):
    """Aggregated pull request analytics response."""

    username: str
    total_prs: int
    open_prs: int
    closed_prs: int
    merged_prs: int
    merge_rate: float
    partial: bool = False

    model_config = ConfigDict(from_attributes=True)


class GitHubIssue(BaseModel):
    """Structured model for an individual GitHub issue (pull requests excluded)."""

    id: int
    number: int
    title: str
    state: str  # "open" | "closed"
    repository_name: str
    repository_url: str
    author_login: str
    author_avatar_url: Optional[str] = None
    labels: list[str] = []
    created_at: str
    updated_at: str
    closed_at: Optional[str] = None
    html_url: str
    is_user_author: bool = False

    model_config = ConfigDict(from_attributes=True)


class GitHubIssuesResponse(BaseModel):
    """Response envelope for recent issues across repositories."""

    username: str
    total_issues: int
    open_issues: int
    closed_issues: int
    issues: list[GitHubIssue]
    partial: bool = False

    model_config = ConfigDict(from_attributes=True)


class IssueRepositoryCount(BaseModel):
    """Issue count grouped by repository."""

    repository_name: str
    repo_url: str
    open_count: int
    closed_count: int
    total_count: int

    model_config = ConfigDict(from_attributes=True)


class IssueLabelCount(BaseModel):
    """Issue count grouped by label."""

    label: str
    count: int

    model_config = ConfigDict(from_attributes=True)


class GitHubIssueAnalyticsResponse(BaseModel):
    """Aggregated issue analytics: totals plus per-repository and per-label breakdowns."""

    username: str
    total_issues: int
    open_issues: int
    closed_issues: int
    issues_by_repository: list[IssueRepositoryCount]
    issues_by_label: list[IssueLabelCount]
    partial: bool = False

    model_config = ConfigDict(from_attributes=True)
