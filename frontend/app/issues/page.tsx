"use client";

import { useState } from "react";
import { useDashboard } from "@/app/providers";
import IssuesAnalytics from "@/app/components/IssuesAnalytics";
import RecentIssuesTable from "@/app/components/RecentIssuesTable";
import {
  EmptyState,
  ErrorState,
  LoadingBlock,
  PageHeader,
  PartialBanner,
  RateLimitBanner,
  SearchField,
} from "@/app/components/ui";
import { isRateLimitError } from "@/services/api";

export default function IssuesPage() {
  const { user, issues, issuesAnalytics, sectionLoading, issuesError, rateLimit, partial, performLookup } =
    useDashboard();
  const [query, setQuery] = useState("");

  if (!user) {
    return (
      <div>
        <PageHeader title="Issues" subtitle="Open vs. closed, by repository and label" />
        <EmptyState
          title="No developer analyzed yet"
          message="Search a GitHub username in the header to load real issue data."
        />
      </div>
    );
  }

  return (
    <div>
      <PageHeader
        title="Issues"
        subtitle={`@${user.login} · open vs. closed, by repository and label`}
        action={
          <div className="w-full sm:w-64">
            <SearchField value={query} onChange={setQuery} placeholder="Search title, repo, label…" />
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

      {sectionLoading && !issues && !issuesAnalytics ? (
        <LoadingBlock rows={6} />
      ) : (
        <div className="space-y-4">
          {issuesError && !isRateLimitError(issuesError) && (
            <ErrorState message={issuesError} onRetry={() => performLookup(user.login)} />
          )}
          {issuesAnalytics && issuesAnalytics.total_issues > 0 && (
            <IssuesAnalytics analytics={issuesAnalytics} />
          )}
          {issues && (
            <RecentIssuesTable issues={issues.issues} username={user.login} query={query} />
          )}
        </div>
      )}
    </div>
  );
}
