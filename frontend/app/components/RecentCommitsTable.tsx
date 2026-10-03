"use client";

import { useState } from "react";
import Image from "next/image";
import type { GitHubCommit } from "@/types/github";

interface RecentCommitsTableProps {
  commits: GitHubCommit[];
  username: string;
  query?: string;
}

export default function RecentCommitsTable({ commits, username, query = "" }: RecentCommitsTableProps) {
  const [filterAuthorOnly, setFilterAuthorOnly] = useState(false);

  const q = query.trim().toLowerCase();
  const searched = q
    ? commits.filter((c) =>
        `${c.message} ${c.repository_name} ${c.short_sha} ${c.author_login ?? ""}`
          .toLowerCase()
          .includes(q)
      )
    : commits;
  const displayedCommits = filterAuthorOnly
    ? searched.filter((c) => c.is_user_author)
    : searched;

  const userCommitCount = commits.filter((c) => c.is_user_author).length;

  if (commits.length === 0) {
    return (
      <div className="rounded-2xl border border-zinc-200 bg-white p-8 text-center text-zinc-500 shadow-xs dark:border-zinc-800 dark:bg-zinc-900 dark:text-zinc-400">
        No commits found in the analyzed repositories.
      </div>
    );
  }

  return (
    <div className="rounded-2xl border border-zinc-200 bg-white shadow-xs dark:border-zinc-800 dark:bg-zinc-900">
      {/* Table Header and Filter */}
      <div className="flex flex-col gap-3 border-b border-zinc-100 p-6 dark:border-zinc-800 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h3 className="text-lg font-bold text-zinc-900 dark:text-zinc-50">
            Recent Commits Across Repositories
          </h3>
          <p className="text-xs text-zinc-500 dark:text-zinc-400">
            Showing real git commits with granular author vs. repository owner attribution
          </p>
        </div>

        {/* Filter buttons */}
        <div className="inline-flex rounded-lg border border-zinc-200 bg-zinc-50 p-0.5 text-xs dark:border-zinc-800 dark:bg-zinc-950">
          <button
            type="button"
            onClick={() => setFilterAuthorOnly(false)}
            className={`rounded-md px-3 py-1 font-medium transition ${
              !filterAuthorOnly
                ? "bg-white text-zinc-900 shadow-xs dark:bg-zinc-800 dark:text-zinc-50"
                : "text-zinc-500 hover:text-zinc-900 dark:text-zinc-400 dark:hover:text-zinc-200"
            }`}
          >
            All Commits ({commits.length})
          </button>
          <button
            type="button"
            onClick={() => setFilterAuthorOnly(true)}
            className={`rounded-md px-3 py-1 font-medium transition ${
              filterAuthorOnly
                ? "bg-white text-zinc-900 shadow-xs dark:bg-zinc-800 dark:text-zinc-50"
                : "text-zinc-500 hover:text-zinc-900 dark:text-zinc-400 dark:hover:text-zinc-200"
            }`}
          >
            @{username} Only ({userCommitCount})
          </button>
        </div>
      </div>

      {/* Responsive Table / Card Layout */}
      <div className="overflow-x-auto">
        <table className="w-full text-left text-xs">
          <thead className="border-b border-zinc-100 bg-zinc-50/50 text-[11px] font-semibold uppercase tracking-wider text-zinc-400 dark:border-zinc-800/80 dark:bg-zinc-950/40 dark:text-zinc-500">
            <tr>
              <th scope="col" className="px-6 py-3">
                Commit Message
              </th>
              <th scope="col" className="px-4 py-3">
                Repository
              </th>
              <th scope="col" className="px-4 py-3">
                Commit Author
              </th>
              <th scope="col" className="px-4 py-3">
                SHA
              </th>
              <th scope="col" className="px-6 py-3 text-right">
                Committed
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-zinc-100 dark:divide-zinc-800/60">
            {displayedCommits.map((commit) => {
              const formattedDate = commit.committed_date
                ? new Date(commit.committed_date).toLocaleDateString("en-US", {
                    month: "short",
                    day: "numeric",
                    year: "numeric",
                  })
                : "Unknown";

              return (
                <tr
                  key={commit.sha}
                  className="transition hover:bg-zinc-50/80 dark:hover:bg-zinc-800/40"
                >
                  {/* Message */}
                  <td className="px-6 py-3.5 max-w-xs sm:max-w-md">
                    <a
                      href={commit.html_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="block truncate font-medium text-zinc-900 hover:text-emerald-600 hover:underline dark:text-zinc-100 dark:hover:text-emerald-400"
                      title={commit.message}
                    >
                      {commit.message}
                    </a>
                  </td>

                  {/* Repository */}
                  <td className="px-4 py-3.5 whitespace-nowrap">
                    <a
                      href={commit.repository_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-flex items-center gap-1 rounded-md border border-zinc-200 bg-zinc-50 px-2 py-0.5 font-mono text-[11px] text-zinc-700 hover:border-zinc-400 dark:border-zinc-800 dark:bg-zinc-900 dark:text-zinc-300 dark:hover:bg-zinc-800"
                    >
                      {commit.repository_name}
                    </a>
                  </td>

                  {/* Author Attribution */}
                  <td className="px-4 py-3.5 whitespace-nowrap">
                    <div className="flex items-center gap-2">
                      {commit.author_avatar_url ? (
                        <Image
                          src={commit.author_avatar_url}
                          alt={`${commit.author_name}'s avatar`}
                          width={20}
                          height={20}
                          className="h-5 w-5 rounded-full ring-1 ring-zinc-200 dark:ring-zinc-700"
                        />
                      ) : (
                        <div className="h-5 w-5 rounded-full bg-zinc-200 dark:bg-zinc-800 flex items-center justify-center text-[10px] font-bold text-zinc-600 dark:text-zinc-300">
                          {(commit.author_login || commit.author_name).slice(0, 1).toUpperCase()}
                        </div>
                      )}

                      <span className="font-medium text-zinc-800 dark:text-zinc-200">
                        {commit.author_login ? `@${commit.author_login}` : commit.author_name}
                      </span>

                      {/* Explicit author vs contributor badge */}
                      {commit.is_user_author ? (
                        <span className="inline-flex items-center rounded-full border border-emerald-500/30 bg-emerald-500/10 px-1.5 py-0.2 text-[9px] font-semibold text-emerald-600 dark:text-emerald-400">
                          Author
                        </span>
                      ) : (
                        <span className="inline-flex items-center rounded-full border border-zinc-300 bg-zinc-100 px-1.5 py-0.2 text-[9px] font-medium text-zinc-600 dark:border-zinc-700 dark:bg-zinc-800 dark:text-zinc-400">
                          Contributor
                        </span>
                      )}
                    </div>
                  </td>

                  {/* Short SHA */}
                  <td className="px-4 py-3.5 whitespace-nowrap">
                    <a
                      href={commit.html_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="font-mono text-[11px] text-zinc-500 hover:text-zinc-900 hover:underline dark:text-zinc-400 dark:hover:text-zinc-200"
                    >
                      {commit.short_sha}
                    </a>
                  </td>

                  {/* Committed Date */}
                  <td className="px-6 py-3.5 whitespace-nowrap text-right font-mono text-[11px] text-zinc-400 dark:text-zinc-500">
                    {formattedDate}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
