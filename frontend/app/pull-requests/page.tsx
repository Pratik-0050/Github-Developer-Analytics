"use client";

import Link from "next/link";
import { useDashboard } from "@/app/providers";
import { Card, EmptyState, PageHeader } from "@/app/components/ui";

export default function PullRequestsPage() {
  const { user } = useDashboard();

  return (
    <div>
      <PageHeader
        title="Pull Requests"
        subtitle={
          user
            ? `@${user.login} · pull request review activity`
            : "Pull request review activity"
        }
      />
      {!user ? (
        <EmptyState
          title="No developer analyzed yet"
          message="Search a GitHub username in the header first — pull request shortcuts and related activity appear here."
        />
      ) : (
        <Card className="flex flex-col items-center gap-2 px-6 py-14 text-center">
          <div className="flex h-11 w-11 items-center justify-center rounded-full border border-edge bg-panelsoft">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5} className="h-5 w-5 text-muted" aria-hidden="true">
              <path strokeLinecap="round" strokeLinejoin="round" d="M7 4a2 2 0 100 4 2 2 0 000-4zm0 0v12m0 0a2 2 0 104 0M7 16h7.5a2 2 0 002-2v-2.5m0-3.5a2 2 0 104 0 2 2 0 00-4 0z" />
            </svg>
          </div>
          <p className="text-sm font-semibold text-ink">No pull request endpoint yet</p>
          <p className="max-w-md text-sm text-muted">
            The API does not expose pull request analytics (only commits, issues, and
            repositories), so there are no PR statistics to show. Review @{user.login}
            {"'s"} pull requests directly on GitHub, or explore the data we do track.
          </p>
          <div className="mt-2 flex flex-wrap items-center justify-center gap-2">
            <a
              href={`https://github.com/pulls?q=is%3Apr+author%3A${user.login}`}
              target="_blank"
              rel="noopener noreferrer"
              className="rounded-lg bg-ink px-4 py-2 text-sm font-medium text-base hover:opacity-85"
            >
              View PRs on GitHub
            </a>
            <Link
              href="/issues"
              className="rounded-lg border border-edge px-4 py-2 text-sm font-medium text-muted hover:text-ink"
            >
              Browse issues
            </Link>
            <Link
              href="/commits"
              className="rounded-lg border border-edge px-4 py-2 text-sm font-medium text-muted hover:text-ink"
            >
              Browse commits
            </Link>
          </div>
        </Card>
      )}
    </div>
  );
}
