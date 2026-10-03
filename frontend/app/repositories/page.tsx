"use client";

import { useMemo, useState } from "react";
import { useDashboard } from "@/app/providers";
import {
  Card,
  EmptyState,
  Kpi,
  LoadingBlock,
  PageHeader,
  SearchField,
  Select,
} from "@/app/components/ui";
import type { GitHubRepository } from "@/types/github";

type SortKey = "updated" | "stars" | "forks" | "issues" | "name";
type KindFilter = "all" | "original" | "fork" | "archived";

function fmtDate(iso: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso.slice(0, 10);
  return d.toLocaleDateString("en-US", { year: "numeric", month: "short", day: "numeric" });
}

export default function RepositoriesPage() {
  const { user, repos, reposAnalytics, sectionLoading, performLookup } = useDashboard();
  const [query, setQuery] = useState("");
  const [language, setLanguage] = useState("all");
  const [kind, setKind] = useState<KindFilter>("all");
  const [sort, setSort] = useState<SortKey>("updated");
  const [dir, setDir] = useState<"desc" | "asc">("desc");

  const languages = useMemo(() => {
    const set = new Set<string>();
    (repos?.repositories ?? []).forEach((r) => {
      if (r.language) set.add(r.language);
    });
    return ["all", ...Array.from(set).sort()];
  }, [repos]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    const list = (repos?.repositories ?? []).filter((r) => {
      if (q && !`${r.name} ${r.description ?? ""}`.toLowerCase().includes(q)) return false;
      if (language !== "all" && r.language !== language) return false;
      if (kind === "original" && r.fork) return false;
      if (kind === "fork" && !r.fork) return false;
      if (kind === "archived" && !r.archived) return false;
      return true;
    });
    const by: Record<SortKey, (r: GitHubRepository) => string | number> = {
      updated: (r) => r.pushed_at ?? r.updated_at ?? "",
      stars: (r) => r.stargazers_count,
      forks: (r) => r.forks_count,
      issues: (r) => r.open_issues_count,
      name: (r) => r.name.toLowerCase(),
    };
    const get = by[sort];
    return [...list].sort((a, b) => {
      const va = get(a);
      const vb = get(b);
      const cmp = va < vb ? -1 : va > vb ? 1 : 0;
      return dir === "asc" ? cmp : -cmp;
    });
  }, [repos, query, language, kind, sort, dir]);

  if (!user) {
    return (
      <div>
        <PageHeader title="Repositories" subtitle="Stars, forks, and activity per repository" />
        <EmptyState
          title="No developer analyzed yet"
          message="Search a GitHub username in the header to browse real repository data."
        />
      </div>
    );
  }

  return (
    <div>
      <PageHeader
        title="Repositories"
        subtitle={`@${user.login} · ${repos?.total ?? user.public_repos} repositories${repos?.private_included ? " · private included" : ""}`}
      />

      <div className="mb-4 grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Kpi label="Total stars" value={reposAnalytics?.total_stars ?? "—"} tone="text-accent" />
        <Kpi label="Total forks" value={reposAnalytics?.total_forks ?? "—"} />
        <Kpi label="Open issues" value={reposAnalytics?.total_open_issues ?? "—"} tone="text-good" />
        <Kpi label="Watchers" value={reposAnalytics?.total_watchers ?? "—"} />
      </div>

      {sectionLoading && !repos ? (
        <LoadingBlock rows={6} />
      ) : !repos || repos.repositories.length === 0 ? (
        <EmptyState
          title="No repositories found"
          message={`@${user.login} has no visible repositories, or they failed to load.`}
          action={
            <button
              type="button"
              onClick={() => performLookup(user.login, true)}
              className="mt-2 rounded-lg border border-edge px-4 py-2 text-sm font-medium text-muted hover:text-ink"
            >
              Retry
            </button>
          }
        />
      ) : (
        <Card>
          <div className="grid grid-cols-1 gap-2 border-b border-edge p-4 sm:grid-cols-2 lg:grid-cols-4">
            <SearchField value={query} onChange={setQuery} placeholder="Filter by name…" />
            <Select
              ariaLabel="Filter by language"
              value={language}
              onChange={setLanguage}
              options={languages.map((l) => ({ value: l, label: l === "all" ? "All languages" : l }))}
            />
            <Select
              ariaLabel="Filter by kind"
              value={kind}
              onChange={(v) => setKind(v as KindFilter)}
              options={[
                { value: "all", label: "All kinds" },
                { value: "original", label: "Original" },
                { value: "fork", label: "Forks" },
                { value: "archived", label: "Archived" },
              ]}
            />
            <div className="flex gap-2">
              <div className="flex-1">
                <Select
                  ariaLabel="Sort repositories"
                  value={sort}
                  onChange={(v) => setSort(v as SortKey)}
                  options={[
                    { value: "updated", label: "Recently updated" },
                    { value: "stars", label: "Stars" },
                    { value: "forks", label: "Forks" },
                    { value: "issues", label: "Open issues" },
                    { value: "name", label: "Name" },
                  ]}
                />
              </div>
              <button
                type="button"
                onClick={() => setDir((d) => (d === "desc" ? "asc" : "desc"))}
                aria-label={dir === "desc" ? "Sort ascending" : "Sort descending"}
                className="h-9 rounded-lg border border-edge px-3 text-sm text-muted hover:text-ink"
              >
                {dir === "desc" ? "↓" : "↑"}
              </button>
            </div>
          </div>

          {filtered.length === 0 ? (
            <p className="p-6 text-center text-sm text-muted">No repositories match these filters.</p>
          ) : (
            <div className="slim-scroll overflow-x-auto">
              <table className="w-full min-w-[720px] text-left text-sm">
                <thead>
                  <tr className="border-b border-edge text-xs uppercase tracking-wide text-faint">
                    <th className="px-5 py-3 font-medium">Repository</th>
                    <th className="px-3 py-3 font-medium">Language</th>
                    <th className="px-3 py-3 text-right font-medium">Stars</th>
                    <th className="px-3 py-3 text-right font-medium">Forks</th>
                    <th className="px-3 py-3 text-right font-medium">Issues</th>
                    <th className="px-5 py-3 text-right font-medium">Updated</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-edge">
                  {filtered.map((r) => (
                    <tr key={r.id} className="hover:bg-panelsoft">
                      <td className="px-5 py-3">
                        <a href={r.html_url} target="_blank" rel="noopener noreferrer" className="font-medium text-ink hover:underline">
                          {r.name}
                        </a>
                        <div className="mt-0.5 flex flex-wrap items-center gap-1.5">
                          {r.private && (
                            <span className="rounded bg-warnsoft px-1.5 py-px text-[10px] font-semibold text-warn">private</span>
                          )}
                          {r.fork && (
                            <span className="rounded bg-panelsoft px-1.5 py-px text-[10px] text-muted ring-1 ring-edge">fork</span>
                          )}
                          {r.archived && (
                            <span className="rounded bg-panelsoft px-1.5 py-px text-[10px] text-muted ring-1 ring-edge">archived</span>
                          )}
                        </div>
                        {r.description && (
                          <p className="mt-0.5 line-clamp-1 text-xs text-muted">{r.description}</p>
                        )}
                      </td>
                      <td className="px-3 py-3 text-xs text-muted">{r.language ?? "—"}</td>
                      <td className="px-3 py-3 text-right font-mono text-xs tabular-nums text-ink">
                        {r.stargazers_count.toLocaleString()}
                      </td>
                      <td className="px-3 py-3 text-right font-mono text-xs tabular-nums text-ink">
                        {r.forks_count.toLocaleString()}
                      </td>
                      <td className="px-3 py-3 text-right font-mono text-xs tabular-nums text-ink">
                        {r.open_issues_count.toLocaleString()}
                      </td>
                      <td className="px-5 py-3 text-right text-xs text-muted">{fmtDate(r.pushed_at ?? r.updated_at)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          <p className="border-t border-edge px-5 py-3 font-mono text-[11px] text-faint">
            Showing {filtered.length} of {repos.total} repositories
          </p>
        </Card>
      )}

      {sectionLoading && repos && (
        <p className="mt-3 text-center text-xs text-faint">Refreshing repository data…</p>
      )}
    </div>
  );
}
