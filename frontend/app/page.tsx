"use client";

import Image from "next/image";
import Link from "next/link";
import { useDashboard } from "@/app/providers";
import ActivityChart from "@/app/components/ActivityChart";
import {
  Card,
  CardHeader,
  EmptyState,
  ErrorState,
  Kpi,
  LoadingBlock,
  PageHeader,
  PartialBanner,
  ProgressBar,
  RateLimitBanner,
} from "@/app/components/ui";
import { isRateLimitError } from "@/services/api";

function formatDate(iso: string): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso.slice(0, 10);
  return d.toLocaleDateString("en-US", { year: "numeric", month: "short", day: "numeric" });
}

export default function OverviewPage() {
  const {
    activeLogin,
    user,
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
    sessionMe,
    includePrivate,
    setIncludePrivate,
    performLookup,
  } = useDashboard();

  if (error && !user) {
    if (rateLimit) {
      return (
        <div>
          <PageHeader title="Overview" subtitle="Developer profile and key metrics" />
          <RateLimitBanner message={rateLimit} />
        </div>
      );
    }
    return (
      <div>
        <PageHeader title="Overview" subtitle="Developer profile and key metrics" />
        <ErrorState message={error} onRetry={() => activeLogin && performLookup(activeLogin)} />
      </div>
    );
  }

  if (!user && !loading) {
    return (
      <div>
        <PageHeader title="Overview" subtitle="Developer profile and key metrics" />
        <EmptyState
          title="No developer analyzed yet"
          message="Search a GitHub username in the header to load repositories, commits, issues, and language analytics."
          action={
            <button
              type="button"
              onClick={() => performLookup("octocat")}
              className="mt-2 rounded-lg bg-ink px-4 py-2 text-sm font-medium text-base hover:opacity-85"
            >
              Try octocat
            </button>
          }
        />
      </div>
    );
  }

  if (loading || !user) {
    return (
      <div>
        <PageHeader title="Overview" subtitle="Loading developer analytics…" />
        <LoadingBlock rows={5} />
      </div>
    );
  }

  const topLanguages = reposAnalytics
    ? Object.entries(reposAnalytics.language_distribution)
        .sort((a, b) => b[1] - a[1])
        .slice(0, 5)
    : [];
  const maxLang = Math.max(...topLanguages.map(([, c]) => c), 1);
  const recentCommits = (commits?.commits ?? []).slice(0, 5);
  const recentIssues = (issues?.issues ?? []).slice(0, 5);

  return (
    <div>
      <PageHeader
        title="Overview"
        subtitle={`@${user.login}${user.name ? ` · ${user.name}` : ""}`}
        action={
          <div className="flex flex-wrap items-center gap-2">
            {sessionMe?.private_enabled && (
              <label className="inline-flex cursor-pointer items-center gap-1.5 rounded-lg border border-edge px-2.5 py-1.5 text-xs font-medium text-muted">
                <input
                  type="checkbox"
                  checked={includePrivate}
                  onChange={(e) => {
                    setIncludePrivate(e.target.checked);
                    performLookup(user.login, false);
                  }}
                  className="h-3.5 w-3.5 accent-emerald-500"
                />
                Private repos
              </label>
            )}
            <button
              type="button"
              disabled={refreshing}
              onClick={() => performLookup(user.login, true)}
              className="rounded-lg border border-edge px-3 py-1.5 text-xs font-medium text-muted hover:text-ink disabled:opacity-50"
            >
              {refreshing ? "Refreshing…" : "Refresh"}
            </button>
          </div>
        }
      />

      {partial && (
        <div className="mb-4">
          <PartialBanner />
        </div>
      )}

      {/* Profile card */}
      <Card className="mb-4 p-5">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center">
          <Image
            src={user.avatar_url}
            alt={`${user.login}'s GitHub avatar`}
            width={64}
            height={64}
            className="h-16 w-16 flex-shrink-0 rounded-full ring-1 ring-edge"
            priority
          />
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-center gap-2">
              <h2 className="text-lg font-semibold text-ink">{user.name ?? user.login}</h2>
              <span className="font-mono text-xs text-muted">@{user.login}</span>
              {user.cached ? (
                <span className="rounded-full bg-warnsoft px-2 py-0.5 text-[11px] font-medium text-warn">
                  Cached{user.stale ? " · fallback" : ""}
                </span>
              ) : (
                <span className="rounded-full bg-goodsoft px-2 py-0.5 text-[11px] font-medium text-good">
                  Live
                </span>
              )}
            </div>
            {user.bio && <p className="mt-1 line-clamp-2 text-sm text-muted">{user.bio}</p>}
            <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted">
              {user.company && <span>{user.company}</span>}
              {user.location && <span>{user.location}</span>}
              <span>Joined {formatDate(user.created_at)}</span>
              <a href={user.html_url} target="_blank" rel="noopener noreferrer" className="text-accent hover:underline">
                View on GitHub
              </a>
            </div>
          </div>
          <div className="grid flex-shrink-0 grid-cols-3 gap-4 text-center sm:gap-6">
            {[
              { v: user.public_repos, l: "Repos" },
              { v: user.followers, l: "Followers" },
              { v: user.following, l: "Following" },
            ].map((s) => (
              <div key={s.l}>
                <div className="text-xl font-semibold tabular-nums text-ink">{s.v.toLocaleString()}</div>
                <div className="text-[11px] uppercase tracking-wide text-faint">{s.l}</div>
              </div>
            ))}
          </div>
        </div>
      </Card>

      {/* KPI cards */}
      <div className="mb-4 grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Kpi label="Total stars" value={reposAnalytics?.total_stars ?? "—"} tone="text-accent" />
        <Kpi label="Total forks" value={reposAnalytics?.total_forks ?? "—"} />
        <Kpi
          label="Open issues"
          value={issuesAnalytics?.open_issues ?? issues?.open_issues ?? "—"}
          tone="text-good"
        />
        <Kpi
          label="Commits analyzed"
          value={activity ? activity.total_commits : "—"}
          sub={activity ? `${activity.user_commits} by @${user.login}` : undefined}
        />
      </div>

      {rateLimit && (
        <div className="mb-4">
          <RateLimitBanner message={rateLimit} />
        </div>
      )}

      {sectionLoading && <LoadingBlock rows={4} />}
      {sectionError && !sectionLoading && !isRateLimitError(sectionError) && (
        <div className="mb-4">
          <ErrorState message={sectionError} onRetry={() => performLookup(user.login)} />
        </div>
      )}

      {/* Activity chart */}
      {!sectionLoading && activity && (
        <div className="mb-4">
          <ActivityChart
            dailyCommits={activity.daily_commits}
            monthlyTotals={activity.monthly_totals}
            username={user.login}
            totalCommits={activity.total_commits}
            userCommits={activity.user_commits}
          />
        </div>
      )}

      {/* Languages + top repos */}
      {!sectionLoading && reposAnalytics && (
        <div className="mb-4 grid grid-cols-1 gap-4 lg:grid-cols-2">
          <Card>
            <CardHeader
              title="Top languages"
              subtitle="By repository count"
              action={
                <Link href="/languages" className="text-xs font-medium text-accent hover:underline">
                  View all
                </Link>
              }
            />
            <div className="space-y-3 px-5 pb-5 pt-3">
              {topLanguages.length === 0 && (
                <p className="text-sm text-muted">No language data available.</p>
              )}
              {topLanguages.map(([lang, count]) => (
                <div key={lang}>
                  <div className="mb-1 flex items-center justify-between text-xs">
                    <span className="font-medium text-ink">{lang}</span>
                    <span className="font-mono text-muted">{count} repos</span>
                  </div>
                  <ProgressBar pct={(count / maxLang) * 100} />
                </div>
              ))}
            </div>
          </Card>

          <Card>
            <CardHeader
              title="Top repositories"
              subtitle="By stars"
              action={
                <Link href="/repositories" className="text-xs font-medium text-accent hover:underline">
                  View all
                </Link>
              }
            />
            <ul className="divide-y divide-edge px-5 pb-3">
              {reposAnalytics.top_repositories.slice(0, 5).map((r) => (
                <li key={r.id} className="flex items-center justify-between gap-3 py-2.5">
                  <div className="min-w-0">
                    <a href={r.html_url} target="_blank" rel="noopener noreferrer" className="block truncate text-sm font-medium text-ink hover:underline">
                      {r.name}
                    </a>
                    <span className="text-xs text-faint">
                      {r.language ?? "No language"} · {r.forks_count} forks
                    </span>
                  </div>
                  <span className="flex-shrink-0 font-mono text-xs text-muted">
                    ★ {r.stargazers_count.toLocaleString()}
                  </span>
                </li>
              ))}
              {reposAnalytics.top_repositories.length === 0 && (
                <li className="py-4 text-sm text-muted">No repositories found.</li>
              )}
            </ul>
          </Card>
        </div>
      )}

      {/* Recent activity */}
      {!sectionLoading && (recentCommits.length > 0 || recentIssues.length > 0) && (
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          {recentCommits.length > 0 && (
            <Card>
              <CardHeader
                title="Recent commits"
                action={
                  <Link href="/commits" className="text-xs font-medium text-accent hover:underline">
                    View all
                  </Link>
                }
              />
              <ul className="divide-y divide-edge px-5 pb-3">
                {recentCommits.map((c) => (
                  <li key={c.sha} className="py-2.5">
                    <a href={c.html_url} target="_blank" rel="noopener noreferrer" className="block truncate text-sm font-medium text-ink hover:underline">
                      {c.message}
                    </a>
                    <span className="font-mono text-xs text-faint">
                      {c.short_sha} · {c.repository_name} · {formatDate(c.committed_date)}
                    </span>
                  </li>
                ))}
              </ul>
            </Card>
          )}
          {recentIssues.length > 0 && (
            <Card>
              <CardHeader
                title="Recent issues"
                action={
                  <Link href="/issues" className="text-xs font-medium text-accent hover:underline">
                    View all
                  </Link>
                }
              />
              <ul className="divide-y divide-edge px-5 pb-3">
                {recentIssues.map((i) => (
                  <li key={i.id} className="py-2.5">
                    <div className="flex items-center gap-2">
                      <span className={`h-1.5 w-1.5 flex-shrink-0 rounded-full ${i.state === "open" ? "bg-good" : "bg-vio"}`} />
                      <a href={i.html_url} target="_blank" rel="noopener noreferrer" className="block truncate text-sm font-medium text-ink hover:underline">
                        {i.title}
                      </a>
                    </div>
                    <span className="font-mono text-xs text-faint">
                      {i.repository_name}#{i.number} · {i.state}
                    </span>
                  </li>
                ))}
              </ul>
            </Card>
          )}
        </div>
      )}

      {issuesError && !sectionLoading && !isRateLimitError(issuesError) && (
        <div className="mt-4">
          <ErrorState message={issuesError} onRetry={() => performLookup(user.login)} />
        </div>
      )}
    </div>
  );
}
