"use client";

import { useRef, useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import AuthButton from "@/app/components/AuthButton";
import { useDashboard, useTheme } from "@/app/providers";

// ─── Navigation ─────────────────────────────────────────────────────────────

const NAV = [
  {
    href: "/",
    label: "Overview",
    icon: (
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M4 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2V6zm10 0a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2V6zM4 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2v-2zm10 0a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2v-2z" />
    ),
  },
  {
    href: "/repositories",
    label: "Repositories",
    icon: (
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M5 5a2 2 0 012-2h10a2 2 0 012 2v14l-5-2.5L9 19l-4 2V5z" />
    ),
  },
  {
    href: "/commits",
    label: "Commits",
    icon: (
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M7 8a2 2 0 100-4 2 2 0 000 4zm0 0v8m0 0a2 2 0 104 0 2 2 0 00-4 0zm7-12a2 2 0 100-4 2 2 0 000 4zm0 0v12m0 0a2 2 0 104 0 2 2 0 00-4 0z" />
    ),
  },
  {
    href: "/pull-requests",
    label: "Pull Requests",
    icon: (
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M7 4a2 2 0 100 4 2 2 0 000-4zm0 0v12m0 0a2 2 0 104 0M7 16h7.5a2 2 0 002-2v-2.5m0-3.5a2 2 0 104 0 2 2 0 00-4 0z" />
    ),
  },
  {
    href: "/issues",
    label: "Issues",
    icon: (
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M12 21a9 9 0 100-18 9 9 0 000 18zm0 0c2.5 0 4-1.5 4-1.5M12 8v5m0 3.5v.01" />
    ),
  },
  {
    href: "/languages",
    label: "Languages",
    icon: (
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M16 18l6-6-6-6M8 6l-6 6 6 6" />
    ),
  },
  {
    href: "/settings",
    label: "Settings",
    icon: (
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M4 8h4l1.5-2.5h5L16 8h4v3h-2.2a3.5 3.5 0 01-2.6 2.6V16h-6v-2.4a3.5 3.5 0 01-2.6-2.6H4V8zm4 4a3 3 0 106 0 3 3 0 00-6 0z" />
    ),
  },
];

function Brand() {
  return (
    <Link href="/" className="flex items-center gap-2.5 px-2 py-1">
      <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-ink text-base">
        <svg viewBox="0 0 16 16" className="h-4.5 w-4.5 fill-current" aria-hidden="true">
          <path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0016 8c0-4.42-3.58-8-8-8z" />
        </svg>
      </span>
      <span className="text-sm font-semibold tracking-tight text-ink">
        Developer Analytics
      </span>
    </Link>
  );
}

function NavLinks({ onNavigate }: { onNavigate?: () => void }) {
  const pathname = usePathname();
  return (
    <nav className="flex flex-col gap-0.5 px-3">
      {NAV.map((item) => {
        const active = item.href === "/" ? pathname === "/" : pathname.startsWith(item.href);
        return (
          <Link
            key={item.href}
            href={item.href}
            onClick={onNavigate}
            className={`flex items-center gap-2.5 rounded-lg px-3 py-2 text-sm font-medium transition ${
              active
                ? "bg-panelsoft text-ink ring-1 ring-edge"
                : "text-muted hover:bg-panelsoft hover:text-ink"
            }`}
          >
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" className="h-4 w-4 flex-shrink-0" aria-hidden="true">
              {item.icon}
            </svg>
            {item.label}
          </Link>
        );
      })}
    </nav>
  );
}

export function Sidebar() {
  const { health, user } = useDashboard();
  const connected = health?.status === "healthy";
  return (
    <aside className="hidden w-60 flex-shrink-0 flex-col border-r border-edge bg-panel lg:flex">
      <div className="px-3 pb-2 pt-5">
        <Brand />
      </div>
      <div className="mt-4 flex-1 overflow-y-auto pb-4">
        <NavLinks />
      </div>
      <div className="border-t border-edge p-4">
        <div className="flex items-center gap-2 text-xs text-muted">
          <span className={`h-2 w-2 rounded-full ${connected ? "bg-good" : "bg-bad"}`} />
          API {connected ? "connected" : "disconnected"}
          {user && <span className="ml-auto truncate font-mono">@{user.login}</span>}
        </div>
      </div>
    </aside>
  );
}

// ─── Header ─────────────────────────────────────────────────────────────────

export function Header({ onMenu }: { onMenu: () => void }) {
  const router = useRouter();
  const { activeLogin, loading, refreshing, performLookup, handleSessionChange } =
    useDashboard();
  const { theme, toggleTheme } = useTheme();
  // Uncontrolled input keyed by active login: remounts (showing the new login)
  // whenever analysis switches accounts, with no render-loop effects.
  const inputRef = useRef<HTMLInputElement>(null);

  function submit(e: React.FormEvent) {
    e.preventDefault();
    const value = inputRef.current?.value ?? "";
    if (!value.trim() || loading || refreshing) return;
    performLookup(value, false);
    router.push("/");
  }

  return (
    <header className="sticky top-0 z-20 border-b border-edge bg-base/95 backdrop-blur">
      <div className="flex h-14 items-center gap-2 px-4 sm:gap-3 sm:px-6">
        <button
          type="button"
          onClick={onMenu}
          aria-label="Open navigation"
          className="rounded-lg border border-edge p-2 text-muted hover:text-ink lg:hidden"
        >
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} className="h-4 w-4" aria-hidden="true">
            <path strokeLinecap="round" d="M4 7h16M4 12h16M4 17h16" />
          </svg>
        </button>

        <form onSubmit={submit} className="flex min-w-0 flex-1 items-center gap-2 sm:max-w-xl">
          <input
            id="dashboard-search"
            key={activeLogin ?? "none"}
            ref={inputRef}
            type="text"
            defaultValue={activeLogin ?? ""}
            placeholder="GitHub username (e.g. octocat)…"
            autoComplete="off"
            spellCheck={false}
            disabled={loading || refreshing}
            className="h-9 w-full rounded-lg border border-edge bg-panel px-3 text-sm text-ink placeholder-faint outline-none focus:border-accent disabled:opacity-50"
          />
          <button
            type="submit"
            disabled={loading || refreshing}
            className="h-9 flex-shrink-0 rounded-lg bg-ink px-4 text-sm font-medium text-base transition hover:opacity-85 disabled:cursor-not-allowed disabled:opacity-40"
          >
            {loading ? "Analyzing…" : "Analyze"}
          </button>
        </form>

        <div className="ml-auto flex flex-shrink-0 items-center gap-2">
          <button
            type="button"
            onClick={toggleTheme}
            aria-label={theme === "dark" ? "Switch to light theme" : "Switch to dark theme"}
            title={theme === "dark" ? "Switch to light theme" : "Switch to dark theme"}
            className="rounded-lg border border-edge p-2 text-muted hover:text-ink"
          >
            {theme === "dark" ? (
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8} className="h-4 w-4" aria-hidden="true">
                <path strokeLinecap="round" strokeLinejoin="round" d="M12 3v2m0 14v2m9-9h-2M5 12H3m14.5-5.5l-1.4 1.4M7.9 16.1l-1.4 1.4m11.4 0l-1.4-1.4M7.9 7.9L6.5 6.5M16 12a4 4 0 11-8 0 4 4 0 018 0z" />
              </svg>
            ) : (
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8} className="h-4 w-4" aria-hidden="true">
                <path strokeLinecap="round" strokeLinejoin="round" d="M21 13A9 9 0 1111 3a7 7 0 0010 10z" />
              </svg>
            )}
          </button>
          <AuthButton onSessionChange={handleSessionChange} />
        </div>
      </div>
    </header>
  );
}

// ─── Shell ──────────────────────────────────────────────────────────────────

export function DashboardShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const [drawer, setDrawer] = useState(false);
  const [drawerPath, setDrawerPath] = useState(pathname);

  // Close the mobile drawer on navigation (derived-state-during-render pattern).
  if (drawerPath !== pathname) {
    setDrawerPath(pathname);
    if (drawer) setDrawer(false);
  }

  if (pathname.startsWith("/auth")) {
    return <div className="min-h-screen bg-base text-ink">{children}</div>;
  }

  return (
    <div className="flex min-h-screen bg-base text-ink">
      <Sidebar />
      <div className="flex min-w-0 flex-1 flex-col">
        <Header onMenu={() => setDrawer(true)} />
        <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-6 sm:px-6">{children}</main>
        <footer className="border-t border-edge px-6 py-4">
          <p className="text-center text-xs text-faint">
            GitHub Developer Analytics · Data from the{" "}
            <a href="https://docs.github.com/en/rest" target="_blank" rel="noopener noreferrer" className="underline underline-offset-2 hover:text-muted">
              GitHub REST API
            </a>
          </p>
        </footer>
      </div>

      {/* Mobile drawer */}
      {drawer && (
        <div className="fixed inset-0 z-30 lg:hidden">
          <div className="absolute inset-0 bg-black/60" onClick={() => setDrawer(false)} />
          <aside className="absolute left-0 top-0 flex h-full w-64 flex-col border-r border-edge bg-panel">
            <div className="flex items-center justify-between px-3 pb-2 pt-5">
              <Brand />
              <button
                type="button"
                onClick={() => setDrawer(false)}
                aria-label="Close navigation"
                className="rounded-lg border border-edge p-1.5 text-muted hover:text-ink"
              >
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} className="h-4 w-4" aria-hidden="true">
                  <path strokeLinecap="round" d="M6 6l12 12M18 6L6 18" />
                </svg>
              </button>
            </div>
            <div className="mt-4 flex-1 overflow-y-auto pb-4">
              <NavLinks onNavigate={() => setDrawer(false)} />
            </div>
          </aside>
        </div>
      )}
    </div>
  );
}
