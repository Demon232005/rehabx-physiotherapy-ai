"use client";

import Link from "next/link";
import { useState } from "react";
import { api } from "@/lib/api";

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);
  const [debugToken, setDebugToken] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setSuccess(false);
    setDebugToken(null);
    setBusy(true);
    try {
      const res = await api<{ message?: string; token?: string }>(
        "/auth/password-reset/request",
        {
          method: "POST",
          body: JSON.stringify({ email }),
        },
        false,
      );
      setSuccess(true);
      if (res.token) {
        setDebugToken(res.token);
      }
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to request password reset",
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-8 shadow-sm">
      <h1 className="text-2xl font-bold text-slate-900">Forgot password?</h1>
      <p className="mt-1 text-sm text-slate-500">
        Enter your email and we&apos;ll send you a reset link.
      </p>

      <form onSubmit={onSubmit} className="mt-6 space-y-4">
        <label className="block text-sm font-medium text-slate-700">
          Email
          <input
            type="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm outline-none focus:border-teal-500 focus:ring-2 focus:ring-teal-100"
          />
        </label>

        {error && (
          <div className="rounded-lg bg-rose-50 px-3 py-2 text-sm text-rose-700">
            {error}
          </div>
        )}

        {success && (
          <div className="rounded-lg bg-emerald-50 px-3 py-2 text-sm text-emerald-700">
            If an account exists with this email, you&apos;ll receive a reset
            link.
          </div>
        )}

        {debugToken && (
          <div className="rounded-lg bg-amber-50 px-3 py-2 text-sm text-amber-700 break-all">
            <span className="font-semibold">Debug token:</span> {debugToken}
          </div>
        )}

        <button
          type="submit"
          disabled={busy}
          className="w-full rounded-lg bg-teal-600 px-4 py-2 text-sm font-semibold text-white hover:bg-teal-700 disabled:opacity-50"
        >
          {busy ? "Sending…" : "Send reset link"}
        </button>
      </form>

      <p className="mt-6 text-center text-sm text-slate-500">
        <Link href="/login" className="font-medium text-teal-600 hover:underline">
          Back to sign in
        </Link>
      </p>
    </div>
  );
}
