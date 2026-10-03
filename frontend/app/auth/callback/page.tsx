"use client";

import { Suspense, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { getSession, loginWithGitHub } from "@/services/api";

/**
 * OAuth landing page. The backend owns the code exchange and redirects here
 * (or to `/?login=success`) with an outcome query param — this page only
 * interprets the outcome and verifies the HttpOnly-cookie session.
 */
function CallbackInner() {
  const router = useRouter();
  const params = useSearchParams();
  const [message, setMessage] = useState<string>("Completing GitHub sign-in…");
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let cancelled = false;
    async function run() {
      const outcome = params.get("oauth");
      const login = params.get("login");
      const legacyCode = params.get("code");
      const oauthError = params.get("error_description") || params.get("error");

      if (oauthError && !login && !outcome) {
        if (!cancelled) {
          setMessage(`GitHub OAuth: ${oauthError}`);
          setFailed(true);
        }
        return;
      }
      if (outcome === "cancelled") {
        if (!cancelled) {
          setMessage("Sign-in was cancelled. No account was connected.");
          setFailed(true);
        }
        return;
      }
      if (outcome === "invalid_state") {
        if (!cancelled) {
          setMessage("Security check failed (invalid state). Please try signing in again.");
          setFailed(true);
        }
        return;
      }
      if (outcome === "unconfigured") {
        if (!cancelled) {
          setMessage("GitHub OAuth is not configured on the backend (missing Client ID / Secret).");
          setFailed(true);
        }
        return;
      }
      if (outcome && outcome !== "cancelled") {
        if (!cancelled) {
          setMessage("GitHub sign-in failed. Please try again.");
          setFailed(true);
        }
        return;
      }
      if (legacyCode) {
        // Legacy frontend-driven exchange is retired: the code must be
        // exchanged by the backend callback (state cookie would not match).
        if (!cancelled) {
          setMessage("This sign-in attempt expired. Please start again with Continue with GitHub.");
          setFailed(true);
        }
        return;
      }
      // Success (or direct visit): verify the cookie session, then go home.
      const me = await getSession();
      if (cancelled) return;
      if (me) {
        setMessage(`Signed in as @${me.login} — redirecting…`);
        router.replace(login === "success" || !login ? "/" : "/");
      } else {
        setMessage("No active session. Please sign in with GitHub.");
        setFailed(true);
      }
    }
    run();
    return () => {
      cancelled = true;
    };
  }, [params, router]);

  return (
    <div className="mx-auto flex min-h-screen w-full max-w-md flex-col items-center justify-center gap-3 px-6 text-center">
      {!failed ? (
        <>
          <svg className="h-8 w-8 animate-spin text-zinc-400" viewBox="0 0 24 24" fill="none" aria-hidden="true">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
          </svg>
          <p className="text-sm text-zinc-500">{message}</p>
        </>
      ) : (
        <>
          <p className="text-sm font-medium text-red-600">{message}</p>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={loginWithGitHub}
              className="rounded-lg bg-zinc-900 px-4 py-2 text-sm text-white dark:bg-zinc-50 dark:text-zinc-900"
            >
              Try again
            </button>
            <button
              type="button"
              onClick={() => router.replace("/")}
              className="rounded-lg border border-zinc-300 px-4 py-2 text-sm text-zinc-600 dark:border-zinc-700 dark:text-zinc-300"
            >
              Back to dashboard
            </button>
          </div>
        </>
      )}
    </div>
  );
}

export default function AuthCallbackPage() {
  return (
    <Suspense>
      <CallbackInner />
    </Suspense>
  );
}
