"use client";

import { useState } from "react";
import type { DailyCommitCount, MonthlyCommitCount } from "@/types/github";

interface ActivityChartProps {
  dailyCommits: DailyCommitCount[];
  monthlyTotals: MonthlyCommitCount[];
  username: string;
  totalCommits: number;
  userCommits: number;
}

export default function ActivityChart({
  dailyCommits,
  monthlyTotals,
  username,
  totalCommits,
  userCommits,
}: ActivityChartProps) {
  const [hoveredDay, setHoveredDay] = useState<DailyCommitCount | null>(null);

  const maxDailyCount = Math.max(...dailyCommits.map((d) => d.count), 1);
  const activeDaysCount = dailyCommits.filter((d) => d.count > 0).length;
  const userCommitPct = totalCommits > 0 ? Math.round((userCommits / totalCommits) * 100) : 0;

  return (
    <div className="rounded-2xl border border-zinc-200 bg-white p-6 shadow-xs dark:border-zinc-800 dark:bg-zinc-900">
      {/* Header and key metrics */}
      <div className="mb-6 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h3 className="text-lg font-bold text-zinc-900 dark:text-zinc-50">
            Commit Activity & Cadence
          </h3>
          <p className="text-xs text-zinc-500 dark:text-zinc-400">
            Daily frequency and monthly distribution across analyzed public repositories
          </p>
        </div>

        {/* Quick summary chips */}
        <div className="flex flex-wrap items-center gap-2">
          <span className="inline-flex items-center gap-1.5 rounded-lg border border-emerald-500/20 bg-emerald-500/10 px-2.5 py-1 text-xs font-medium text-emerald-600 dark:text-emerald-400">
            <span className="h-2 w-2 rounded-full bg-emerald-500" />
            {userCommits} by @{username} ({userCommitPct}%)
          </span>
          <span className="inline-flex items-center gap-1.5 rounded-lg border border-zinc-200 bg-zinc-50 px-2.5 py-1 text-xs font-medium text-zinc-600 dark:border-zinc-800 dark:bg-zinc-800 dark:text-zinc-300">
            {activeDaysCount} active days
          </span>
        </div>
      </div>

      {/* Daily Commits Bar Chart */}
      {dailyCommits.length === 0 ? (
        <div className="py-10 text-center text-xs text-zinc-400 dark:text-zinc-500">
          No daily commit logs recorded in this period.
        </div>
      ) : (
        <div className="mb-6">
          <div className="mb-2 flex items-center justify-between text-xs text-zinc-500 dark:text-zinc-400">
            <span>Daily Activity Timeline</span>
            <span>
              {hoveredDay ? (
                <span className="font-mono text-emerald-600 dark:text-emerald-400">
                  {hoveredDay.date}: <strong>{hoveredDay.count}</strong> commit{hoveredDay.count === 1 ? "" : "s"} ({hoveredDay.user_count} by @{username})
                </span>
              ) : (
                <span className="text-zinc-400">Hover over any bar to inspect daily stats</span>
              )}
            </span>
          </div>

          {/* Responsive SVG/HTML Bar Chart */}
          <div className="relative flex h-36 items-end gap-1.5 overflow-x-auto rounded-xl border border-zinc-100 bg-zinc-50/50 p-4 dark:border-zinc-800/60 dark:bg-zinc-950/40">
            {dailyCommits.map((day) => {
              const heightPercent = Math.max(Math.round((day.count / maxDailyCount) * 100), 10);
              const isUserHeavy = day.user_count > 0;
              const isHovered = hoveredDay?.date === day.date;

              return (
                <div
                  key={day.date}
                  onMouseEnter={() => setHoveredDay(day)}
                  onMouseLeave={() => setHoveredDay(null)}
                  className="group relative flex h-full flex-1 min-w-[12px] cursor-pointer flex-col justify-end items-center"
                >
                  {/* Floating tooltip on hover */}
                  {isHovered && (
                    <div className="absolute -top-12 z-20 whitespace-nowrap rounded-md bg-zinc-900 px-2 py-1 text-[10px] font-mono text-zinc-100 shadow-md dark:bg-zinc-100 dark:text-zinc-900">
                      <div>{day.date}</div>
                      <div>
                        {day.count} total ({day.user_count} @{username})
                      </div>
                    </div>
                  )}

                  {/* The bar element */}
                  <div
                    style={{ height: `${heightPercent}%` }}
                    className={`w-full rounded-t-sm transition-all duration-150 ${
                      isHovered
                        ? "bg-emerald-400 shadow-xs ring-2 ring-emerald-400/50"
                        : isUserHeavy
                        ? "bg-emerald-500/80 hover:bg-emerald-500 dark:bg-emerald-500/70 dark:hover:bg-emerald-400"
                        : "bg-zinc-300 hover:bg-zinc-400 dark:bg-zinc-700 dark:hover:bg-zinc-600"
                    }`}
                  />
                  <span className="mt-1 text-[9px] font-mono text-zinc-400 dark:text-zinc-500 truncate max-w-full">
                    {day.date.slice(5)}
                  </span>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Monthly Summary Breakdown */}
      {monthlyTotals.length > 0 && (
        <div>
          <h4 className="mb-2 text-xs font-semibold uppercase tracking-wider text-zinc-400 dark:text-zinc-500">
            Monthly Commit Volumes
          </h4>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 md:grid-cols-4">
            {monthlyTotals.map((m) => {
              const monthShare = totalCommits > 0 ? Math.round((m.count / totalCommits) * 100) : 0;
              const formattedMonth = new Date(`${m.month}-01T00:00:00`).toLocaleDateString("en-US", {
                month: "short",
                year: "numeric",
              });

              return (
                <div
                  key={m.month}
                  className="rounded-xl border border-zinc-100 bg-zinc-50/70 p-3 dark:border-zinc-800/60 dark:bg-zinc-950/40"
                >
                  <div className="flex items-center justify-between text-xs">
                    <span className="font-semibold text-zinc-800 dark:text-zinc-200">
                      {formattedMonth}
                    </span>
                    <span className="font-mono text-[11px] text-zinc-400">{monthShare}%</span>
                  </div>
                  <div className="mt-1 flex items-baseline gap-1.5">
                    <span className="text-lg font-bold text-zinc-900 dark:text-zinc-50">
                      {m.count}
                    </span>
                    <span className="text-[11px] text-zinc-500 dark:text-zinc-400">
                      ({m.user_count} by author)
                    </span>
                  </div>
                  {/* Visual ratio bar */}
                  <div className="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-zinc-200 dark:bg-zinc-800">
                    <div
                      style={{
                        width: `${m.count > 0 ? (m.user_count / m.count) * 100 : 0}%`,
                      }}
                      className="h-full bg-emerald-500"
                    />
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
