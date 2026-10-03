"use client";

import { useEffect, useState } from "react";
import Image from "next/image";
import {
  disconnectPrivateAccess,
  getAuthStatus,
  getSession,
  loginWithGitHub,
  logout,
} from "@/services/api";
import type { AuthMe, AuthStatus } from "@/types/github";

export default function AuthButton({
  onSessionChange,
}: {
  onSessionChange?: (me: AuthMe | null) => void;
}) {
  const [me, setMe] = useState<AuthMe | null>(null);
  const [status, setStatus] = useState<AuthStatus | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Session is resolved from the HttpOnly cookie — nothing token-like is
  // ever stored in JavaScript. An expired/invalid session reads as signed out.
  useEffect(() => {
    let cancelled = false;
    getAuthStatus().then((s) => {
      if (!cancelled) setStatus(s);
    });
    getSession().then((m) => {
      if (cancelled) return;
      setMe(m);
      onSessionChange?.(m);
    });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function handleLogin() {
    setError(null);
    loginWithGitHub();
  }

  async function handleLogout() {
    setBusy(true);
    await logout();
    setBusy(false);
    setMe(null);
    onSessionChange?.(null);
  }

  async function handleDisconnect() {
    setBusy(true);
    setError(null);
    try {
      await disconnectPrivateAccess();
      const refreshed = await getSession();
      setMe(refreshed);
      onSessionChange?.(refreshed);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Disconnect failed.");
    } finally {
      setBusy(false);
    }
  }

  if (me) {
    return (
      <div className="flex items-center gap-2">
        <span
          className={`inline-flex items-center gap-1.5 rounded-full border py-1 pl-1 pr-2.5 text-xs font-medium ${
            me.private_enabled
              ? "border-emerald-200 bg-emerald-50 text-emerald-700 dark:border-emerald-800 dark:bg-emerald-950 dark:text-emerald-400"
              : "border-zinc-200 bg-zinc-50 text-zinc-600 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-400"
          }`}
          title={me.scope ? `Scope: ${me.scope}` : "Signed in with GitHub"}
        >
          {me.avatar_url ? (
            <Image
              src={me.avatar_url}
              alt={`${me.login}'s avatar`}
              width={20}
              height={20}
              className="h-5 w-5 rounded-full"
            />
          ) : (
            <span className="h-2 w-2 rounded-full bg-emerald-500" />
          )}
          @{me.login}
          {me.private_enabled ? " · Private ✓" : ""}
        </span>
        {me.private_enabled && (
          <button
            type="button"
            onClick={handleDisconnect}
            disabled={busy}
            className="rounded-md border border-zinc-200 px-2 py-1 text-xs text-zinc-500 hover:bg-zinc-100 disabled:opacity-50 dark:border-zinc-800 dark:text-zinc-400 dark:hover:bg-zinc-800"
            title="Remove stored GitHub token (keeps cached profile)"
          >
            Disconnect
          </button>
        )}
        <button
          type="button"
          onClick={handleLogout}
          disabled={busy}
          className="rounded-md border border-zinc-200 px-2 py-1 text-xs text-zinc-500 hover:bg-zinc-100 disabled:opacity-50 dark:border-zinc-800 dark:text-zinc-400 dark:hover:bg-zinc-800"
        >
          Sign out
        </button>
      </div>
    );
  }

  const unconfigured = status && !status.configured;

  return (
    <div className="flex items-center gap-2">
      <button
        type="button"
        onClick={handleLogin}
        disabled={busy || !!unconfigured}
        className="inline-flex h-8 items-center gap-1.5 rounded-lg bg-zinc-900 px-3 text-xs font-medium text-white hover:bg-zinc-700 disabled:opacity-50 dark:bg-zinc-50 dark:text-zinc-900 dark:hover:bg-zinc-200"
        title={
          unconfigured
            ? "Set GITHUB_CLIENT_ID / GITHUB_CLIENT_SECRET in backend/.env, then restart API"
            : "Continue with GitHub (public profile; private repos only if you authorize them)"
        }
      >
        <svg viewBox="0 0 16 16" className="h-3.5 w-3.5 fill-current" aria-hidden="true">
          <path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0016 8c0-4.42-3.58-8-8-8z" />
        </svg>
        Continue with GitHub
      </button>
      {error && <span className="text-xs text-red-500">{error}</span>}
      {unconfigured && (
        <span className="hidden text-[11px] text-amber-600 sm:inline" title="Backend returns 503 until OAuth App credentials are set">
          OAuth unconfigured
        </span>
      )}
    </div>
  );
}
