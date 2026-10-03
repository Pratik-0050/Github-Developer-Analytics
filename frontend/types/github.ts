/** TypeScript types for GitHub API responses and caching metrics. */

export interface GitHubUser {
  login: string;
  id: number;
  name: string | null;
  avatar_url: string;
  html_url: string;
  bio?: string | null;
  company?: string | null;
  location?: string | null;
  blog?: string | null;
  public_repos: number;
  followers: number;
  following: number;
  created_at: string;
  cached?: boolean;
  last_synced_at?: string | null;
  stale?: boolean;
}

export interface DatabaseStatus {
  status: string;
  dialect?: string;
  latency_ms?: number;
  error?: string;
}

export interface HealthStatus {
  status: string;
  service: string;
  database?: DatabaseStatus;
}

export interface AnalyticsRun {
  id: number;
  username: string;
  query_type: string;
  cache_hit: boolean;
  status: string;
  response_time_ms: number;
  created_at: string;
}

export interface AnalyticsStats {
  total_cached_profiles: number;
  total_queries: number;
  total_cache_hits: number;
  total_cache_misses: number;
  cache_hit_rate_pct: number;
  average_response_time_ms: number;
  database_status: string;
  database_latency_ms: number;
  recent_runs: AnalyticsRun[];
}

export interface ApiError {
  detail: string;
}

export interface GitHubCommit {
  sha: string;
  short_sha: string;
  message: string;
  repository_name: string;
  repository_url: string;
  author_name: string;
  author_login: string | null;
  author_avatar_url: string | null;
  committed_date: string;
  html_url: string;
  is_user_author: boolean;
}

export interface GitHubCommitsResponse {
  username: string;
  total_commits: number;
  user_commits: number;
  commits: GitHubCommit[];
  partial: boolean;
}

export interface DailyCommitCount {
  date: string;
  count: number;
  user_count: number;
}

export interface MonthlyCommitCount {
  month: string;
  count: number;
  user_count: number;
}

export interface ActiveRepositorySummary {
  repository_name: string;
  commit_count: number;
  repo_url: string;
  stars: number;
  language: string | null;
}

export interface GitHubActivityResponse {
  username: string;
  total_commits: number;
  user_commits: number;
  daily_commits: DailyCommitCount[];
  monthly_totals: MonthlyCommitCount[];
  most_active_repositories: ActiveRepositorySummary[];
  partial: boolean;
}

// ─── Step 8: GitHub Issues Analytics ────────────────────────────────────────

export interface GitHubIssue {
  id: number;
  number: number;
  title: string;
  state: string;
  repository_name: string;
  repository_url: string;
  author_login: string;
  author_avatar_url: string | null;
  labels: string[];
  created_at: string;
  updated_at: string;
  closed_at: string | null;
  html_url: string;
  is_user_author: boolean;
}

export interface GitHubIssuesResponse {
  username: string;
  total_issues: number;
  open_issues: number;
  closed_issues: number;
  issues: GitHubIssue[];
  partial: boolean;
}

export interface IssueRepositoryCount {
  repository_name: string;
  repo_url: string;
  open_count: number;
  closed_count: number;
  total_count: number;
}

export interface IssueLabelCount {
  label: string;
  count: number;
}

export interface GitHubIssueAnalyticsResponse {
  username: string;
  total_issues: number;
  open_issues: number;
  closed_issues: number;
  issues_by_repository: IssueRepositoryCount[];
  issues_by_label: IssueLabelCount[];
  partial: boolean;
}

// ─── Step 9: Repositories ───────────────────────────────────────────────────

export interface GitHubRepository {
  id: number;
  name: string;
  full_name: string;
  description: string | null;
  html_url: string;
  language: string | null;
  stargazers_count: number;
  forks_count: number;
  open_issues_count: number;
  watchers_count: number;
  size: number;
  default_branch: string;
  created_at: string;
  updated_at: string;
  pushed_at: string | null;
  fork: boolean;
  archived: boolean;
  private: boolean;
}

export interface GitHubRepositoriesResponse {
  username: string;
  total: number;
  repositories: GitHubRepository[];
  private_included: boolean;
}

export interface GitHubRepoAnalytics {
  username: string;
  total_repositories: number;
  total_stars: number;
  total_forks: number;
  total_open_issues: number;
  total_watchers: number;
  forked_repositories: number;
  original_repositories: number;
  archived_repositories: number;
  language_distribution: Record<string, number>;
  top_repositories: GitHubRepository[];
}

// ─── Step 7: GitHub OAuth ─────────────────────────────────────────────────

export interface AuthStatus {
  configured: boolean;
  client_id_present: boolean;
  redirect_uri: string;
  scope: string;
}

export interface AuthLoginUrl {
  authorization_url: string;
  redirect_uri: string;
  scope: string;
}

export interface AuthSession {
  jwt: string;
  login: string;
  github_id: number;
  avatar_url: string;
  scope?: string | null;
  private_enabled: boolean;
}

export interface AuthMe {
  login: string;
  github_id: number;
  avatar_url: string;
  html_url: string;
  scope?: string | null;
  private_enabled: boolean;
  token_obtained_at?: string | null;
}

