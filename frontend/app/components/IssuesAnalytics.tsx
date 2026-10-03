"use client";

import type { GitHubIssueAnalyticsResponse } from "@/types/github";

interface IssuesAnalyticsProps {
  analytics: GitHubIssueAnalyticsResponse;
}

function SummaryCard({ label, value, accent }: { label: string; value: number; accent: string }) {
  return (
    <div className="flex flex-col items-center gap-0.5 rounded-xl border border-zinc-200 bg-white px-5 py-4 text-center dark:border-zinc-700 dark:bg-zinc-900">
      <span className={`text-2xl font-bold ${accent}`}>{value.toLocaleString()}</span>
      <span className="text-xs font-medium uppercase tracking-wide text-zinc-500 dark:text-zinc-400">
        {label}
      </span>
    </div>
  );
}

export default function IssuesAnalytics({ analytics }: IssuesAnalyticsProps) {
  const { total_issues, open_issues, closed_issues, issues_by_repository, issues_by_label } =
    analytics;
  const openPct = total_issues > 0 ? Math.round((open_issues / total_issues) * 100) : 0;
  const closedPct = total_issues > 0 ? 100 - openPct : 0;
  const maxRepoTotal = Math.max(...issues_by_repository.map((r) => r.total_count), 1);
  const maxLabelCount = Math.max(...issues_by_label.map((l) => l.count), 1);

  return (
    <div className="space-y-6">
      {/* Summary cards */}
      <div className="rounded-2xl border border-zinc-200 bg-white p-6 shadow-xs dark:border-zinc-800 dark:bg-zinc-900">
        <h3 className="text-lg font-bold text-zinc-900 dark:text-zinc-50">Issue Summary</h3>
        <p className="mb-4 text-xs text-zinc-500 dark:text-zinc-400">
          Open vs. closed split across the analyzed repositories (pull requests excluded)
        </p>
        <div className="mb-4 grid grid-cols-3 gap-4">
          <SummaryCard
            label="Total Issues"
            value={total_issues}
            accent="text-zinc-900 dark:text-zinc-50"
          />
          <SummaryCard
            label="Open"
            value={open_issues}
            accent="text-emerald-600 dark:text-emerald-400"
          />
          <SummaryCard label="Closed" value={closed_issues} accent="text-violet-600 dark:text-violet-400" />
        </div>

        {/* Open/closed proportional bar */}
        {total_issues > 0 ? (
          <div>
            <div className="flex h-3 w-full overflow-hidden rounded-full bg-zinc-200 dark:bg-zinc-800">
              <div style={{ width: `${openPct}%` }} className="h-full bg-emerald-500" />
              <div style={{ width: `${closedPct}%` }} className="h-full bg-violet-500" />
            </div>
            <div className="mt-2 flex items-center justify-between text-xs text-zinc-500 dark:text-zinc-400">
              <span className="inline-flex items-center gap-1.5">
                <span className="h-2 w-2 rounded-full bg-emerald-500" />
                Open {openPct}%
              </span>
              <span className="inline-flex items-center gap-1.5">
                <span className="h-2 w-2 rounded-full bg-violet-500" />
                Closed {closedPct}%
              </span>
            </div>
          </div>
        ) : (
          <p className="text-sm text-zinc-500 dark:text-zinc-400">
            No issues found in the analyzed repositories.
          </p>
        )}
      </div>

      {/* Repository breakdown */}
      {issues_by_repository.length > 0 && (
        <div className="rounded-2xl border border-zinc-200 bg-white p-6 shadow-xs dark:border-zinc-800 dark:bg-zinc-900">
          <div className="mb-5 flex items-center justify-between">
            <div>
              <h3 className="text-lg font-bold text-zinc-900 dark:text-zinc-50">
                Issues by Repository
              </h3>
              <p className="text-xs text-zinc-500 dark:text-zinc-400">
                Open vs. closed counts per repository
              </p>
            </div>
            <span className="text-xs font-mono text-zinc-400 dark:text-zinc-500">
              {issues_by_repository.length} repos
            </span>
          </div>
          <div className="space-y-3">
            {issues_by_repository.map((repo) => {
              const barWidth = Math.max(Math.round((repo.total_count / maxRepoTotal) * 100), 8);
              return (
                <div key={repo.repository_name}>
                  <div className="flex items-center justify-between gap-2 text-sm">
                    <a
                      href={repo.repo_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="truncate font-semibold text-zinc-900 underline-offset-2 hover:underline dark:text-zinc-50"
                    >
                      {repo.repository_name}
                    </a>
                    <span className="flex-shrink-0 font-mono text-[11px] text-zinc-500 dark:text-zinc-400">
                      <span className="text-emerald-600 dark:text-emerald-400">
                        {repo.open_count} open
                      </span>
                      {" · "}
                      <span className="text-violet-600 dark:text-violet-400">
                        {repo.closed_count} closed
                      </span>
                    </span>
                  </div>
                  <div className="mt-1.5 flex h-1.5 w-full overflow-hidden rounded-full bg-zinc-200 dark:bg-zinc-800">
                    <div
                      style={{
                        width: `${repo.total_count > 0 ? Math.round((repo.open_count / repo.total_count) * barWidth) : 0}%`,
                      }}
                      className="h-full bg-emerald-500"
                    />
                    <div
                      style={{
                        width: `${repo.total_count > 0 ? Math.round((repo.closed_count / repo.total_count) * barWidth) : 0}%`,
                      }}
                      className="h-full bg-violet-500"
                    />
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Label breakdown */}
      {issues_by_label.length > 0 && (
        <div className="rounded-2xl border border-zinc-200 bg-white p-6 shadow-xs dark:border-zinc-800 dark:bg-zinc-900">
          <h3 className="text-lg font-bold text-zinc-900 dark:text-zinc-50">Issues by Label</h3>
          <p className="mb-4 text-xs text-zinc-500 dark:text-zinc-400">
            An issue with multiple labels counts once per label
          </p>
          <div className="flex flex-wrap gap-2">
            {issues_by_label.map((entry) => {
              const intensity = Math.max(Math.round((entry.count / maxLabelCount) * 100), 15);
              return (
                <span
                  key={entry.label}
                  className="inline-flex items-center gap-1.5 rounded-full border border-sky-200 bg-sky-50 px-3 py-1 text-xs font-medium text-sky-800 dark:border-sky-900 dark:bg-sky-950 dark:text-sky-300"
                  title={`${entry.count} issue${entry.count === 1 ? "" : "s"}`}
                >
                  <span
                    className="inline-flex h-4 min-w-4 items-center justify-center rounded-full bg-sky-500/20 px-1 font-mono text-[10px] font-bold"
                    style={{ opacity: `${intensity}%` }}
                  >
                    {entry.count}
                  </span>
                  {entry.label}
                </span>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
