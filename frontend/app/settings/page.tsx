"use client";

import { useRouter } from "next/navigation";
import AuthButton from "@/app/components/AuthButton";
import { useDashboard, useTheme } from "@/app/providers";
import { Card, CardHeader, PageHeader, Segmented } from "@/app/components/ui";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "(not configured)";

export default function SettingsPage() {
  const router = useRouter();
  const { theme, setTheme } = useTheme();
  const {
    user,
    health,
    stats,
    sessionMe,
    includePrivate,
    setIncludePrivate,
    handleSessionChange,
    performLookup,
    refreshMeta,
  } = useDashboard();

  const db = health?.database;
  const recentLogins = stats
    ? Array.from(new Set(stats.recent_runs.map((r) => r.username))).slice(0, 8)
    : [];

  return (
    <div>
      <PageHeader title="Settings" subtitle="Appearance, connection, and cached data" />

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        {/* Appearance */}
        <Card>
          <CardHeader title="Appearance" subtitle="Interface theme (saved on this device)" />
          <div className="px-5 pb-5 pt-3">
            <Segmented
              value={theme}
              onChange={setTheme}
              options={[
                { key: "dark", label: "Dark" },
                { key: "light", label: "Light" },
              ]}
            />
            <p className="mt-3 text-xs text-muted">
              Dark is the default studio theme (#0B0D10 surfaces, #252A30 borders).
            </p>
          </div>
        </Card>

        {/* Backend connection */}
        <Card>
          <CardHeader
            title="Backend connection"
            subtitle="Live status of the FastAPI service"
            action={
              <button
                type="button"
                onClick={refreshMeta}
                className="rounded-lg border border-edge px-3 py-1.5 text-xs font-medium text-muted hover:text-ink"
              >
                Refresh status
              </button>
            }
          />
          <dl className="space-y-2 px-5 pb-5 pt-3 text-sm">
            <div className="flex items-center justify-between gap-3">
              <dt className="text-muted">API URL</dt>
              <dd className="truncate font-mono text-xs text-ink">{API_URL}</dd>
            </div>
            <div className="flex items-center justify-between gap-3">
              <dt className="text-muted">API status</dt>
              <dd className="flex items-center gap-1.5 text-xs font-medium text-ink">
                <span className={`h-2 w-2 rounded-full ${health?.status === "healthy" ? "bg-good" : "bg-bad"}`} />
                {health ? `${health.status} · ${health.service}` : "unknown"}
              </dd>
            </div>
            <div className="flex items-center justify-between gap-3">
              <dt className="text-muted">Database</dt>
              <dd className="font-mono text-xs text-ink">
                {db ? `${db.status}${db.dialect ? ` · ${db.dialect}` : ""}${db.latency_ms != null ? ` · ${db.latency_ms}ms` : ""}` : "unknown"}
              </dd>
            </div>
          </dl>
        </Card>

        {/* GitHub connection */}
        <Card>
          <CardHeader title="GitHub connection" subtitle="OAuth sign-in unlocks private repositories" />
          <div className="space-y-3 px-5 pb-5 pt-3">
            <AuthButton onSessionChange={handleSessionChange} />
            {sessionMe?.private_enabled && (
              <label className="inline-flex cursor-pointer items-center gap-1.5 text-xs font-medium text-muted">
                <input
                  type="checkbox"
                  checked={includePrivate}
                  onChange={(e) => setIncludePrivate(e.target.checked)}
                  className="h-3.5 w-3.5 accent-emerald-500"
                />
                Include private repositories in analysis
              </label>
            )}
            {!sessionMe && (
              <p className="text-xs text-muted">
                Without sign-in, all analytics use public repositories only.
              </p>
            )}
          </div>
        </Card>

        {/* Cache & history */}
        <Card>
          <CardHeader
            title="Cache & history"
            subtitle="Real query metrics from the backend"
            action={
              user ? (
                <button
                  type="button"
                  onClick={() => performLookup(user.login, true)}
                  className="rounded-lg border border-edge px-3 py-1.5 text-xs font-medium text-muted hover:text-ink"
                >
                  Force refresh @{user.login}
                </button>
              ) : undefined
            }
          />
          <div className="px-5 pb-5 pt-3">
            <div className="mb-3 grid grid-cols-3 gap-2 text-center">
              {[
                { v: stats?.total_cached_profiles ?? "—", l: "Cached" },
                { v: stats ? `${stats.cache_hit_rate_pct}%` : "—", l: "Hit rate" },
                { v: stats?.total_queries ?? "—", l: "Queries" },
              ].map((s) => (
                <div key={s.l} className="rounded-lg border border-edge bg-panelsoft px-2 py-2.5">
                  <div className="text-base font-semibold tabular-nums text-ink">{s.v}</div>
                  <div className="text-[11px] uppercase tracking-wide text-faint">{s.l}</div>
                </div>
              ))}
            </div>
            {recentLogins.length > 0 ? (
              <div className="flex flex-wrap gap-1.5">
                {recentLogins.map((login) => (
                  <button
                    key={login}
                    type="button"
                    onClick={() => {
                      performLookup(login, false);
                      router.push("/");
                    }}
                    className="rounded-md border border-edge px-2 py-1 font-mono text-xs text-muted hover:text-ink"
                  >
                    @{login}
                  </button>
                ))}
              </div>
            ) : (
              <p className="text-xs text-muted">No analyzed profiles yet.</p>
            )}
          </div>
        </Card>
      </div>
    </div>
  );
}
