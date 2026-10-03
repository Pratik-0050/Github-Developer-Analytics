"use client";

import { useMemo, useState } from "react";
import { useDashboard } from "@/app/providers";
import RecentCommitsTable from "@/app/components/RecentCommitsTable";
import {
  EmptyState,
  ErrorState,
  Kpi,
  LoadingBlock,
  PageHeader,
  PartialBanner,
  RateLimitBanner,
  SearchField,
} from "@/app/components/ui";
import { isRateLimitError } from "@/services/api";

export default function CommitsPage() {
  const { user, commits, activity, sectionLoading, sectionError, rateLimit, partial, performLookup } =
    useDashboard();
  const [query, setQuery] = useState("");

  const repoCount = useMemo(
    () => new Set((commits?.commits ?? []).map((c) => c.repository_name.toLowerCase())).size,
    [commits]
  );

  if (!user) {
    return (
      <div>
        <PageHeader title="Commits" subtitle="Recent work across analyzed repositories" />
        <EmptyState
          title="No developer analyzed yet"
          message="Search a GitHub username in the header to load real commit data."
        />
      </div>
    );
  }

  return (
    <div>
      <PageHeader
        title="Commits"
        subtitle={`@${user.login} · recent work across analyzed repositories`}
        action={
          <div className="w-full sm:w-64">
            <SearchField value={query} onChange={setQuery} placeholder="Search message, repo, SHA…" />
          </div>
        }
      />

      {rateLimit && (
        <div className="mb-4">
          <RateLimitBanner message={rateLimit} />
        </div>
      )}

      {partial && (
        <div className="mb-4">
          <PartialBanner />
        </div>
      )}

      <div className="mb-4 grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Kpi label="Commits analyzed" value={commits?.total_commits ?? "—"} />
        <Kpi
          label={`By @${user.login}`}
          value={commits?.user_commits ?? "—"}
          tone="text-accent"
        />
        <Kpi label="Repositories touched" value={commits ? repoCount : "—"} />
        <Kpi label="Active days" value={activity ? activity.daily_commits.length : "—"} tone="text-good" />
      </div>

      {sectionLoading && !commits ? (
        <LoadingBlock rows={6} />
      ) : (
        <>
          {sectionError && !isRateLimitError(sectionError) && (
            <div className="mb-4">
              <ErrorState message={sectionError} onRetry={() => performLookup(user.login)} />
            </div>
          )}
          {commits && <RecentCommitsTable commits={commits.commits} username={user.login} query={query} />}
        </>
      )}
    </div>
  );
}
