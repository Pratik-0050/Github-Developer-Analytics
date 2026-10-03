"use client";

import { useState } from "react";
import type { GitHubIssue } from "@/types/github";

interface RecentIssuesTableProps {
  issues: GitHubIssue[];
  username: string;
  query?: string;
}

type StateFilter = "all" | "open" | "closed";

function formatDate(iso: string): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso.slice(0, 10);
  return d.toLocaleDateString("en-US", { year: "numeric", month: "short", day: "numeric" });
}

export default function RecentIssuesTable({ issues, username, query = "" }: RecentIssuesTableProps) {
  const [filter, setFilter] = useState<StateFilter>("all");

  const openCount = issues.filter((i) => i.state === "open").length;
  const byState = filter === "all" ? issues : issues.filter((i) => i.state === filter);
  const q = query.trim().toLowerCase();
  const displayed = q
    ? byState.filter((i) =>
        `${i.title} ${i.repository_name} ${i.author_login} ${i.labels.join(" ")}`
          .toLowerCase()
          .includes(q)
      )
    : byState;

  if (issues.length === 0) {
    return (
      <div className="rounded-2xl border border-zinc-200 bg-white p-8 text-center text-zinc-500 shadow-xs dark:border-zinc-800 dark:bg-zinc-900 dark:text-zinc-400">
        No issues found in the analyzed repositories for @{username}.
      </div>
    );
  }

  const tabs: { key: StateFilter; label: string }[] = [
    { key: "all", label: `All (${issues.length})` },
    { key: "open", label: `Open (${openCount})` },
    { key: "closed", label: `Closed (${issues.length - openCount})` },
  ];

  return (
    <div className="rounded-2xl border border-zinc-200 bg-white shadow-xs dark:border-zinc-800 dark:bg-zinc-900">
      <div className="flex flex-col gap-3 border-b border-zinc-100 p-6 dark:border-zinc-800 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h3 className="text-lg font-bold text-zinc-900 dark:text-zinc-50">Recent Issues</h3>
          <p className="text-xs text-zinc-500 dark:text-zinc-400">
            Real issues across analyzed repositories (pull requests excluded)
          </p>
        </div>
        <div className="inline-flex rounded-lg border border-zinc-200 bg-zinc-50 p-0.5 text-xs dark:border-zinc-800 dark:bg-zinc-950">
          {tabs.map((t) => (
            <button
              key={t.key}
              type="button"
              onClick={() => setFilter(t.key)}
              className={`rounded-md px-3 py-1 font-medium transition ${
                filter === t.key
                  ? "bg-white text-zinc-900 shadow-xs dark:bg-zinc-800 dark:text-zinc-50"
                  : "text-zinc-500 hover:text-zinc-900 dark:text-zinc-400 dark:hover:text-zinc-200"
              }`}
            >
              {t.label}
            </button>
          ))}
        </div>
      </div>

      {displayed.length === 0 ? (
        <p className="p-6 text-center text-sm text-zinc-500 dark:text-zinc-400">
          No {filter} issues in this sample.
        </p>
      ) : (
        <ul className="divide-y divide-zinc-100 dark:divide-zinc-800">
          {displayed.map((issue) => (
            <li key={issue.id} className="flex flex-col gap-2 p-4 sm:flex-row sm:items-center sm:justify-between">
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-2">
                  <span
                    className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-semibold ${
                      issue.state === "open"
                        ? "bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300"
                        : "bg-violet-100 text-violet-800 dark:bg-violet-950 dark:text-violet-300"
                    }`}
                  >
                    <span
                      className={`h-1.5 w-1.5 rounded-full ${issue.state === "open" ? "bg-emerald-500" : "bg-violet-500"}`}
                    />
                    {issue.state}
                  </span>
                  <a
                    href={issue.html_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="truncate text-sm font-semibold text-zinc-900 underline-offset-2 hover:underline dark:text-zinc-50"
                  >
                    {issue.title}
                  </a>
                </div>
                <div className="mt-1.5 flex flex-wrap items-center gap-x-3 gap-y-1 text-[11px] text-zinc-500 dark:text-zinc-400">
                  <span className="font-mono">
                    {issue.repository_name}#{issue.number}
                  </span>
                  <span>
                    by <span className="font-medium text-zinc-700 dark:text-zinc-300">@{issue.author_login}</span>
                    {issue.is_user_author && (
                      <span className="ml-1 rounded bg-zinc-200/70 px-1 py-px text-[10px] font-semibold text-zinc-700 dark:bg-zinc-800 dark:text-zinc-300">
                        author
                      </span>
                    )}
                  </span>
                  <span>updated {formatDate(issue.updated_at)}</span>
                  {issue.labels.length > 0 && (
                    <span className="inline-flex flex-wrap gap-1">
                      {issue.labels.slice(0, 4).map((label) => (
                        <span
                          key={label}
                          className="rounded-full border border-zinc-200 bg-zinc-50 px-2 py-px text-[10px] text-zinc-600 dark:border-zinc-700 dark:bg-zinc-800 dark:text-zinc-300"
                        >
                          {label}
                        </span>
                      ))}
                      {issue.labels.length > 4 && (
                        <span className="text-[10px] text-zinc-400">+{issue.labels.length - 4} more</span>
                      )}
                    </span>
                  )}
                </div>
              </div>
              <span className="flex-shrink-0 font-mono text-[11px] text-zinc-400">
                {formatDate(issue.created_at)}
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
