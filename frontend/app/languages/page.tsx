"use client";

import { useMemo, useState } from "react";
import { useDashboard } from "@/app/providers";
import {
  Card,
  CardHeader,
  EmptyState,
  LoadingBlock,
  PageHeader,
  ProgressBar,
  Segmented,
} from "@/app/components/ui";

export default function LanguagesPage() {
  const { user, repos, reposAnalytics, sectionLoading } = useDashboard();
  const [selected, setSelected] = useState<string>("all");

  const distribution = useMemo(() => {
    const dist = reposAnalytics?.language_distribution ?? {};
    return Object.entries(dist).sort((a, b) => b[1] - a[1]);
  }, [reposAnalytics]);

  const total = useMemo(
    () => distribution.reduce((sum, [, c]) => sum + c, 0),
    [distribution]
  );
  const max = Math.max(...distribution.map(([, c]) => c), 1);

  const matchingRepos = useMemo(() => {
    if (selected === "all") return [];
    return (repos?.repositories ?? []).filter((r) => r.language === selected);
  }, [repos, selected]);

  if (!user) {
    return (
      <div>
        <PageHeader title="Languages" subtitle="Technology mix across repositories" />
        <EmptyState
          title="No developer analyzed yet"
          message="Search a GitHub username in the header to load real language data."
        />
      </div>
    );
  }

  return (
    <div>
      <PageHeader
        title="Languages"
        subtitle={`@${user.login} · technology mix by repository count`}
      />

      {sectionLoading && !reposAnalytics ? (
        <LoadingBlock rows={5} />
      ) : distribution.length === 0 ? (
        <EmptyState
          title="No language data"
          message="None of the analyzed repositories report a primary language."
        />
      ) : (
        <div className="space-y-4">
          <Card>
            <CardHeader
              title="Language distribution"
              subtitle={`${total} repositories with a detected language · select a language to list its repositories`}
              action={
                <Segmented
                  value={selected}
                  onChange={setSelected}
                  options={[
                    { key: "all", label: "All" },
                    ...distribution.slice(0, 4).map(([lang]) => ({ key: lang, label: lang })),
                  ]}
                />
              }
            />
            <div className="space-y-3 px-5 pb-5 pt-3">
              {distribution.map(([lang, count]) => {
                const pct = total > 0 ? (count / total) * 100 : 0;
                const isActive = selected === lang;
                return (
                  <button
                    key={lang}
                    type="button"
                    onClick={() => setSelected(isActive ? "all" : lang)}
                    className={`block w-full rounded-lg p-2 text-left transition hover:bg-panelsoft ${
                      isActive ? "bg-panelsoft ring-1 ring-edge" : ""
                    }`}
                  >
                    <div className="mb-1 flex items-center justify-between text-xs">
                      <span className="font-medium text-ink">{lang}</span>
                      <span className="font-mono text-muted">
                        {count} repos · {pct.toFixed(1)}%
                      </span>
                    </div>
                    <ProgressBar pct={(count / max) * 100} />
                  </button>
                );
              })}
            </div>
          </Card>

          {selected !== "all" && (
            <Card>
              <CardHeader
                title={`Repositories using ${selected}`}
                subtitle={`${matchingRepos.length} repositories`}
              />
              <ul className="divide-y divide-edge px-5 pb-3">
                {matchingRepos.map((r) => (
                  <li key={r.id} className="flex items-center justify-between gap-3 py-2.5">
                    <div className="min-w-0">
                      <a
                        href={r.html_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="block truncate text-sm font-medium text-ink hover:underline"
                      >
                        {r.name}
                      </a>
                      {r.description && (
                        <p className="line-clamp-1 text-xs text-muted">{r.description}</p>
                      )}
                    </div>
                    <span className="flex-shrink-0 font-mono text-xs text-muted">
                      ★ {r.stargazers_count.toLocaleString()}
                    </span>
                  </li>
                ))}
                {matchingRepos.length === 0 && (
                  <li className="py-4 text-sm text-muted">No repositories found for this language.</li>
                )}
              </ul>
            </Card>
          )}
        </div>
      )}
    </div>
  );
}
