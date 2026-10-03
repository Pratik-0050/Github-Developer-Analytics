/**
 * API service for communicating with the FastAPI backend.
 * All backend URLs are sourced from NEXT_PUBLIC_API_URL — never hard-coded.
 */

import type {
  AnalyticsRun,
  AnalyticsStats,
  AuthMe,
  AuthStatus,
  GitHubActivityResponse,
  GitHubCommitsResponse,
  GitHubIssueAnalyticsResponse,
  GitHubIssuesResponse,
  GitHubRepoAnalytics,
  GitHubRepositoriesResponse,
  GitHubUser,
  HealthStatus,
} from "@/types/github";

const API_URL = process.env.NEXT_PUBLIC_API_URL;

if (!API_URL) {
  throw new Error("NEXT_PUBLIC_API_URL is not defined. Check your .env.local file.");
}

/**
 * Generic fetch helper that handles HTTP errors and parses JSON.
 * Throws a plain Error with a user-friendly message on failure.
 *
 * Always sends `credentials: "include"` so the HttpOnly session cookie
 * (`gda_session`) accompanies auth requests — tokens are never handled in JS.
 */
async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;

  try {
    response = await fetch(`${API_URL}${path}`, { credentials: "include", ...init });
  } catch {
    throw new Error("Unable to connect to backend.");
  }

  if (!response.ok) {
    try {
      const errorBody = await response.json();
      if (typeof errorBody?.detail === "string") {
        throw new Error(errorBody.detail);
      }
    } catch (parseError) {
      if (parseError instanceof Error && parseError.message !== "Unable to connect to backend.") {
        throw parseError;
      }
    }
    throw new Error(`Request failed with status ${response.status}.`);
  }

  try {
    return (await response.json()) as T;
  } catch {
    throw new Error("Received an unexpected response from the server.");
  }
}

/**
 * Detects GitHub rate-limit failures surfaced by the backend.
 * The backend returns HTTP 429 with a "rate limit exceeded ... wait ~Ns"
 * detail (honoring Retry-After / X-RateLimit-Reset); the UI should show a
 * dedicated banner for these instead of a generic error with Retry button,
 * so users don't hammer Refresh and extend the limit window.
 */
export function isRateLimitError(err: unknown): boolean {
  const msg =
    err instanceof Error ? err.message : typeof err === "string" ? err : "";
  return /rate limit|429|retry in|try again in/i.test(msg);
}

/**
 * Checks backend health by calling GET /api/health.
 * Returns true if the backend is healthy, false otherwise.
 */
export async function checkHealth(): Promise<boolean> {
  try {
    const data = await apiFetch<HealthStatus>("/api/health");
    return data.status === "healthy";
  } catch {
    return false;
  }
}

/**
 * Retrieves detailed health check including database dialect and latency.
 */
export async function checkHealthDetailed(): Promise<HealthStatus | null> {
  try {
    return await apiFetch<HealthStatus>("/api/health");
  } catch {
    return null;
  }
}

/**
 * Fetches a GitHub user profile from the backend with caching support.
 *
 * @param username - GitHub username to look up.
 * @param refresh - When true, bypasses the database cache and fetches fresh data from GitHub.
 * @returns Structured GitHubUser data from FastAPI.
 */
export async function getGithubUser(username: string, refresh = false): Promise<GitHubUser> {
  const trimmed = username.trim();
  if (!trimmed) {
    throw new Error("Please enter a GitHub username.");
  }
  const query = refresh ? "?refresh=true" : "";
  return apiFetch<GitHubUser>(`/api/github/user/${encodeURIComponent(trimmed)}${query}`);
}

/**
 * Fetches query volumes, cache hit rates, and database performance metrics.
 */
export async function getAnalyticsStats(): Promise<AnalyticsStats | null> {
  try {
    return await apiFetch<AnalyticsStats>("/api/analytics/stats");
  } catch {
    return null;
  }
}

/**
 * Fetches recent search audit records.
 */
export async function getRecentAnalytics(limit = 10): Promise<AnalyticsRun[]> {
  try {
    return await apiFetch<AnalyticsRun[]>(`/api/analytics/history?limit=${limit}`);
  } catch {
    return [];
  }
}

/**
 * Fetches recent commits across public repositories for a given user.
 *
 * @param username - GitHub username.
 * @param limit - Maximum number of commits (default 30).
 */
export async function getGithubCommits(
  username: string,
  limit = 30,
  opts?: { includePrivate?: boolean }
): Promise<GitHubCommitsResponse> {
  const trimmed = username.trim();
  if (!trimmed) {
    throw new Error("Please enter a GitHub username.");
  }
  const query = `?limit=${limit}${opts?.includePrivate ? "&include_private=true" : ""}`;
  return apiFetch<GitHubCommitsResponse>(
    `/api/github/commits/${encodeURIComponent(trimmed)}${query}`
  );
}

/**
 * Fetches aggregated developer activity: daily commit frequency, monthly volume, and active repos.
 *
 * @param username - GitHub username.
 */
export async function getGithubActivity(
  username: string,
  opts?: { includePrivate?: boolean }
): Promise<GitHubActivityResponse> {
  const trimmed = username.trim();
  if (!trimmed) {
    throw new Error("Please enter a GitHub username.");
  }
  const query = opts?.includePrivate ? "?include_private=true" : "";
  return apiFetch<GitHubActivityResponse>(
    `/api/github/activity/${encodeURIComponent(trimmed)}${query}`
  );
}

/**
 * Fetches the repository list for a given user.
 *
 * @param username - GitHub username.
 */
export async function getGithubRepos(
  username: string,
  opts?: { includePrivate?: boolean }
): Promise<GitHubRepositoriesResponse> {
  const trimmed = username.trim();
  if (!trimmed) {
    throw new Error("Please enter a GitHub username.");
  }
  const query = opts?.includePrivate ? "?include_private=true" : "";
  return apiFetch<GitHubRepositoriesResponse>(
    `/api/github/repos/${encodeURIComponent(trimmed)}${query}`
  );
}

/**
 * Fetches aggregated repository analytics: stars, forks, languages, top repos.
 *
 * @param username - GitHub username.
 */
export async function getGithubReposAnalytics(
  username: string,
  opts?: { includePrivate?: boolean }
): Promise<GitHubRepoAnalytics> {
  const trimmed = username.trim();
  if (!trimmed) {
    throw new Error("Please enter a GitHub username.");
  }
  const query = opts?.includePrivate ? "?include_private=true" : "";
  return apiFetch<GitHubRepoAnalytics>(
    `/api/github/repos/${encodeURIComponent(trimmed)}/analytics${query}`
  );
}

// ─── Step 8: GitHub Issues Analytics ────────────────────────────────────────

/**
 * Fetches recent issues across repositories for a given user.
 * Pull requests are excluded server-side.
 *
 * @param username - GitHub username.
 * @param limit - Maximum number of issues (default 30).
 */
export async function getGithubIssues(
  username: string,
  limit = 30,
  opts?: { includePrivate?: boolean }
): Promise<GitHubIssuesResponse> {
  const trimmed = username.trim();
  if (!trimmed) {
    throw new Error("Please enter a GitHub username.");
  }
  const query = `?limit=${limit}${opts?.includePrivate ? "&include_private=true" : ""}`;
  return apiFetch<GitHubIssuesResponse>(
    `/api/github/issues/${encodeURIComponent(trimmed)}${query}`
  );
}

/**
 * Fetches aggregated issue analytics: totals plus per-repository and
 * per-label breakdowns.
 *
 * @param username - GitHub username.
 */
export async function getGithubIssueAnalytics(
  username: string,
  opts?: { includePrivate?: boolean }
): Promise<GitHubIssueAnalyticsResponse> {
  const trimmed = username.trim();
  if (!trimmed) {
    throw new Error("Please enter a GitHub username.");
  }
  const query = opts?.includePrivate ? "?include_private=true" : "";
  return apiFetch<GitHubIssueAnalyticsResponse>(
    `/api/github/issues/${encodeURIComponent(trimmed)}/analytics${query}`
  );
}

// ─── Step 7: GitHub OAuth session (HttpOnly cookie) ──────────────────────────
// The session JWT lives ONLY in the `gda_session` HttpOnly cookie set by the
// backend — it is never readable from JavaScript and never in localStorage.
// `apiFetch` sends `credentials: "include"` on every request so the cookie
// accompanies auth calls automatically. Private-repo analytics are gated
// server-side: anonymous requests transparently receive public data only.

/**
 * Start OAuth sign-in: navigates to the backend login endpoint, which
 * 302-redirects to GitHub authorization (with CSRF `state` protection).
 */
export function loginWithGitHub(): void {
  // Full-page navigation to the API origin (sets the state cookie, then
  // 302s to GitHub) — intentionally not Next.js router navigation.
  // eslint-disable-next-line @next/next/no-location-assign-relative-destination
  window.location.href = `${API_URL}/api/auth/github/login`;
}

export async function getAuthStatus(): Promise<AuthStatus | null> {
  try {
    return await apiFetch<AuthStatus>("/api/auth/status");
  } catch {
    return null;
  }
}

/**
 * Current signed-in user resolved from the session cookie.
 * Returns null when signed out, expired, or unreachable — never throws.
 */
export async function getSession(): Promise<AuthMe | null> {
  try {
    return await apiFetch<AuthMe>("/api/auth/me");
  } catch {
    return null;
  }
}

/**
 * Fetch the current session user; throws with the backend message when
 * signed out (for contexts that distinguish errors from signed-out state).
 */
export async function getAuthMe(): Promise<AuthMe> {
  return apiFetch<AuthMe>("/api/auth/me");
}

/** Sign out: clears the HttpOnly session cookie server-side. */
export async function logout(): Promise<void> {
  try {
    await apiFetch<{ logged_out: boolean }>("/api/auth/logout", { method: "POST" });
  } catch {
    // Already signed out / backend unreachable — UI treats as signed out.
  }
}

/** Remove the stored GitHub token (keeps cached profile + session). */
export async function disconnectPrivateAccess(): Promise<void> {
  await apiFetch<{ disconnected: boolean }>("/api/auth/token", { method: "DELETE" });
}
