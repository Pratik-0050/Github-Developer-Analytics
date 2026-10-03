"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import {
  checkHealthDetailed,
  getAnalyticsStats,
  getGithubActivity,
  getGithubCommits,
  getGithubIssueAnalytics,
  getGithubIssues,
  getGithubRepos,
  getGithubReposAnalytics,
  getGithubUser,
  getSession,
  isRateLimitError,
} from "@/services/api";
import type {
  AnalyticsStats,
  AuthMe,
  GitHubActivityResponse,
  GitHubCommitsResponse,
  GitHubIssueAnalyticsResponse,
  GitHubIssuesResponse,
  GitHubRepoAnalytics,
  GitHubRepositoriesResponse,
  GitHubUser,
  HealthStatus,
} from "@/types/github";

// ─── Theme ──────────────────────────────────────────────────────────────────

type Theme = "dark" | "light";
const THEME_KEY = "gda_theme";

function readInitialTheme(): Theme {
  if (typeof window === "undefined") return "dark";
  const stored = window.localStorage.getItem(THEME_KEY);
  return stored === "light" ? "light" : "dark";
}

interface ThemeCtx {
  theme: Theme;
  setTheme: (t: Theme) => void;
  toggleTheme: () => void;
}

const ThemeContext = createContext<ThemeCtx>({ theme: "dark", setTheme: () => {}, toggleTheme: () => {} });

export function useTheme(): ThemeCtx {
  return useContext(ThemeContext);
}

// ─── Dashboard data ─────────────────────────────────────────────────────────

interface AuthOpts {
  includePrivate?: boolean;
}

export interface DashboardCtx {
  activeLogin: string | null;
  user: GitHubUser | null;
  repos: GitHubRepositoriesResponse | null;
  reposAnalytics: GitHubRepoAnalytics | null;
  activity: GitHubActivityResponse | null;
  commits: GitHubCommitsResponse | null;
  issues: GitHubIssuesResponse | null;
  issuesAnalytics: GitHubIssueAnalyticsResponse | null;
  loading: boolean;
  sectionLoading: boolean;
  refreshing: boolean;
  error: string | null;
  sectionError: string | null;
  issuesError: string | null;
  /** Non-null when any current error is a GitHub rate-limit (429) failure. */
  rateLimit: string | null;
  partial: boolean;
  health: HealthStatus | null;
  stats: AnalyticsStats | null;
  sessionMe: AuthMe | null;
  includePrivate: boolean;
  setIncludePrivate: (v: boolean) => void;
  handleSessionChange: (me: AuthMe | null) => void;
  performLookup: (login: string, forceRefresh?: boolean) => Promise<void>;
  refreshMeta: () => void;
}

const DashboardContext = createContext<DashboardCtx | null>(null);

export function useDashboard(): DashboardCtx {
  const ctx = useContext(DashboardContext);
  if (!ctx) throw new Error("useDashboard must be used inside DashboardProvider");
  return ctx;
}

export function Providers({ children }: { children: ReactNode }) {
  const [theme, setThemeState] = useState<Theme>(readInitialTheme);

  const setTheme = useCallback((t: Theme) => {
    setThemeState(t);
    if (typeof window !== "undefined") {
      window.localStorage.setItem(THEME_KEY, t);
      document.documentElement.classList.toggle("dark", t === "dark");
    }
  }, []);

  const toggleTheme = useCallback(() => {
    setThemeState((prev) => {
      const next: Theme = prev === "dark" ? "light" : "dark";
      if (typeof window !== "undefined") {
        window.localStorage.setItem(THEME_KEY, next);
        document.documentElement.classList.toggle("dark", next === "dark");
      }
      return next;
    });
  }, []);

  // Sync <html> class on mount (default markup ships with class="dark").
  useEffect(() => {
    document.documentElement.classList.toggle("dark", readInitialTheme() === "dark");
  }, []);

  const [activeLogin, setActiveLogin] = useState<string | null>(null);
  const [user, setUser] = useState<GitHubUser | null>(null);
  const [repos, setRepos] = useState<GitHubRepositoriesResponse | null>(null);
  const [reposAnalytics, setReposAnalytics] = useState<GitHubRepoAnalytics | null>(null);
  const [activity, setActivity] = useState<GitHubActivityResponse | null>(null);
  const [commits, setCommits] = useState<GitHubCommitsResponse | null>(null);
  const [issues, setIssues] = useState<GitHubIssuesResponse | null>(null);
  const [issuesAnalytics, setIssuesAnalytics] = useState<GitHubIssueAnalyticsResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [sectionLoading, setSectionLoading] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sectionError, setSectionError] = useState<string | null>(null);
  const [issuesError, setIssuesError] = useState<string | null>(null);
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [stats, setStats] = useState<AnalyticsStats | null>(null);
  const [sessionMe, setSessionMe] = useState<AuthMe | null>(null);
  const [includePrivate, setIncludePrivate] = useState(false);

  const refreshMeta = useCallback(() => {
    checkHealthDetailed().then((h) => {
      if (h) setHealth(h);
    });
    getAnalyticsStats().then(setStats);
  }, []);

  useEffect(() => {
    refreshMeta();
    // Session resolves from the HttpOnly cookie; expired sessions read as null.
    getSession().then((m) => setSessionMe(m));
  }, [refreshMeta]);

  const handleSessionChange = useCallback((me: AuthMe | null) => {
    setSessionMe(me);
    setIncludePrivate(false);
  }, []);

  const performLookup = useCallback(
    async (targetUser: string, forceRefresh = false) => {
      const trimmed = targetUser.trim();
      if (!trimmed) {
        setError("Please enter a GitHub username.");
        return;
      }
      setError(null);
      setSectionError(null);
      setIssuesError(null);
      if (forceRefresh) {
        setRefreshing(true);
      } else {
        setUser(null);
        setRepos(null);
        setReposAnalytics(null);
        setActivity(null);
        setCommits(null);
        setIssues(null);
        setIssuesAnalytics(null);
        setActiveLogin(null);
        setLoading(true);
      }

      try {
        const data = await getGithubUser(trimmed, forceRefresh);
        setUser(data);
        setActiveLogin(data.login);
        getAnalyticsStats().then(setStats);
      } catch (err) {
        setError(err instanceof Error ? err.message : "An unexpected error occurred.");
        setLoading(false);
        setRefreshing(false);
        return;
      } finally {
        setLoading(false);
        setRefreshing(false);
      }

      setSectionLoading(true);
      // The session cookie (if any) is sent automatically via credentials:
      // include — the backend gates private data on the session owner.
      const authOpts: AuthOpts | undefined = includePrivate ? { includePrivate: true } : undefined;
      try {
        const [actRes, comRes, issRes, issAggRes, repoRes, repoAggRes] =
          await Promise.allSettled([
            getGithubActivity(trimmed, authOpts),
            getGithubCommits(trimmed, 30, authOpts),
            getGithubIssues(trimmed, 30, authOpts),
            getGithubIssueAnalytics(trimmed, authOpts),
            getGithubRepos(trimmed, authOpts),
            getGithubReposAnalytics(trimmed, authOpts),
          ]);
        if (actRes.status === "fulfilled") setActivity(actRes.value);
        else setSectionError(actRes.reason instanceof Error ? actRes.reason.message : "Failed to load activity metrics.");
        if (comRes.status === "fulfilled") setCommits(comRes.value);
        if (issRes.status === "fulfilled") setIssues(issRes.value);
        else setIssuesError(issRes.reason instanceof Error ? issRes.reason.message : "Failed to load issue metrics.");
        if (issAggRes.status === "fulfilled") setIssuesAnalytics(issAggRes.value);
        if (repoRes.status === "fulfilled") setRepos(repoRes.value);
        if (repoAggRes.status === "fulfilled") setReposAnalytics(repoAggRes.value);
      } finally {
        setSectionLoading(false);
      }
    },
    [includePrivate]
  );

  const partial = useMemo(
    () =>
      Boolean(
        activity?.partial || commits?.partial || issues?.partial || issuesAnalytics?.partial
      ),
    [activity, commits, issues, issuesAnalytics]
  );

  // Surface a dedicated rate-limit message so pages can render RateLimitBanner
  // (with wait guidance) instead of a generic error + Retry button.
  const rateLimit = useMemo(() => {
    for (const msg of [error, sectionError, issuesError]) {
      if (msg && isRateLimitError(msg)) return msg;
    }
    return null;
  }, [error, sectionError, issuesError]);

  const dashboard = useMemo<DashboardCtx>(
    () => ({
      activeLogin,
      user,
      repos,
      reposAnalytics,
      activity,
      commits,
      issues,
      issuesAnalytics,
      loading,
      sectionLoading,
      refreshing,
      error,
      sectionError,
      issuesError,
      rateLimit,
      partial,
      health,
      stats,
      sessionMe,
      includePrivate,
      setIncludePrivate,
      handleSessionChange,
      performLookup,
      refreshMeta,
    }),
    [
      activeLogin, user, repos, reposAnalytics, activity, commits, issues, issuesAnalytics,
      loading, sectionLoading, refreshing, error, sectionError, issuesError, partial,
      health, stats, sessionMe, includePrivate, handleSessionChange,
      performLookup, refreshMeta, rateLimit,
    ]
  );

  return (
    <ThemeContext.Provider value={useMemo(() => ({ theme, setTheme, toggleTheme }), [theme, setTheme, toggleTheme])}>
      <DashboardContext.Provider value={dashboard}>{children}</DashboardContext.Provider>
    </ThemeContext.Provider>
  );
}
