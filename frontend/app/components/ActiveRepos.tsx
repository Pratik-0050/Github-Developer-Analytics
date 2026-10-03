"use client";

import type { ActiveRepositorySummary } from "@/types/github";

interface ActiveReposProps {
  repositories: ActiveRepositorySummary[];
  totalCommits: number;
}

export default function ActiveRepos({ repositories, totalCommits }: ActiveReposProps) {
  if (repositories.length === 0) {
    return null;
  }

  const maxCommits = Math.max(...repositories.map((r) => r.commit_count), 1);

  return (
    <div className="rounded-2xl border border-zinc-200 bg-white p-6 shadow-xs dark:border-zinc-800 dark:bg-zinc-900">
      <div className="mb-5 flex items-center justify-between">
        <div>
          <h3 className="text-lg font-bold text-zinc-900 dark:text-zinc-50">
            Most-Active Repositories
          </h3>
          <p className="text-xs text-zinc-500 dark:text-zinc-400">
            Ranked by commit density in the analyzed sample
          </p>
        </div>
        <span className="text-xs font-mono text-zinc-400 dark:text-zinc-500">
          {repositories.length} repos analyzed
        </span>
      </div>

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 md:grid-cols-3">
        {repositories.map((repo, idx) => {
          const barWidth = Math.max(Math.round((repo.commit_count / maxCommits) * 100), 8);
          const share = totalCommits > 0 ? Math.round((repo.commit_count / totalCommits) * 100) : 0;

          return (
            <div
              key={repo.repository_name}
              className="flex flex-col justify-between rounded-xl border border-zinc-100 bg-zinc-50/70 p-4 transition hover:border-zinc-300 hover:bg-zinc-50 dark:border-zinc-800/70 dark:bg-zinc-950/40 dark:hover:border-zinc-700 dark:hover:bg-zinc-800/50"
            >
              <div>
                <div className="flex items-center justify-between gap-2">
                  <span className="text-[11px] font-mono font-semibold text-zinc-400">
                    #{idx + 1}
                  </span>
                  {repo.language && (
                    <span className="inline-flex items-center gap-1 rounded-full bg-zinc-200/60 px-2 py-0.5 text-[10px] font-medium text-zinc-700 dark:bg-zinc-800 dark:text-zinc-300">
                      <span className="h-1.5 w-1.5 rounded-full bg-sky-400" />
                      {repo.language}
                    </span>
                  )}
                </div>

                <a
                  href={repo.repo_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="mt-2 block truncate text-sm font-semibold text-zinc-900 underline-offset-2 hover:underline dark:text-zinc-50"
                >
                  {repo.repository_name}
                </a>
              </div>

              <div className="mt-4">
                <div className="flex items-center justify-between text-xs text-zinc-500 dark:text-zinc-400">
                  <span className="font-semibold text-zinc-900 dark:text-zinc-100">
                    {repo.commit_count} commit{repo.commit_count === 1 ? "" : "s"}
                  </span>
                  <span className="font-mono text-[11px] text-zinc-400">{share}% share</span>
                </div>

                {/* Progress bar */}
                <div className="mt-1.5 h-1.5 w-full overflow-hidden rounded-full bg-zinc-200 dark:bg-zinc-800">
                  <div
                    style={{ width: `${barWidth}%` }}
                    className="h-full rounded-full bg-gradient-to-r from-emerald-500 to-sky-500"
                  />
                </div>

                {/* Stars info */}
                <div className="mt-2.5 flex items-center gap-1 text-[11px] text-zinc-400">
                  <svg className="h-3.5 w-3.5 fill-amber-400" viewBox="0 0 20 20">
                    <path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z" />
                  </svg>
                  <span>{repo.stars.toLocaleString()} stars</span>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
