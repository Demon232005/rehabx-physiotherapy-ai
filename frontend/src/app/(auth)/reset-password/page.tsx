"use client";

import Link from "next/link";
import { useState } from "react";
import { useSearchParams } from "next/navigation";
import { api } from "@/lib/api";

export default function ResetPasswordPage() {
  const searchParams = useSearchParams();
  const token = searchParams.get("token");

  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);
  const [busy, setBusy] = useState(false);

  if (!token) {
    return (
      <div className="rounded-2xl border border-slate-200 bg-white p-8 shadow-sm">
        <h1 className="text-2xl font-bold text-slate-900">
          Invalid reset link
        </h1>
        <p className="mt-2 text-sm text-slate-500">
          This password reset link is invalid or has expired. Please request a
          new one.
        </p>
        <Link
          href="/forgot-password"
          className="mt-6 block w-full rounded-lg bg-teal-600 px-4 py-2 text-center text-sm font-semibold text-white hover:bg-teal-700"
        >
          Request new link
        </Link>
      </div>
    );
  }

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);

    if (password.length < 8) {
      setError("Password must be at least 8 characters.");
      return;
    }
    if (password !== confirmPassword) {
      setError("Passwords do not match.");
      return;
    }

    setBusy(true);
    try {
      await api("/auth/password-reset/confirm", {
        method: "POST",
        body: JSON.stringify({ token, new_password: password }),
      }, false);
      setSuccess(true);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to reset password",
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-8 shadow-sm">
      <h1 className="text-2xl font-bold text-slate-900">Set new password</h1>
      <p className="mt-1 text-sm text-slate-500">
        Choose a strong password for your account.
      </p>

      <form onSubmit={onSubmit} className="mt-6 space-y-4">
        <label className="block text-sm font-medium text-slate-700">
          New password
          <input
            type="password"
            required
            minLength={8}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="8+ characters"
            className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm outline-none focus:border-teal-500 focus:ring-2 focus:ring-teal-100"
          />
        </label>
        <label className="block text-sm font-medium text-slate-700">
          Confirm password
          <input
            type="password"
            required
            minLength={8}
            value={confirmPassword}
            onChange={(e) => setConfirmPassword(e.target.value)}
            placeholder="Re-enter password"
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
            Password has been reset successfully.
          </div>
        )}

        <button
          type="submit"
          disabled={busy || success}
          className="w-full rounded-lg bg-teal-600 px-4 py-2 text-sm font-semibold text-white hover:bg-teal-700 disabled:opacity-50"
        >
          {busy ? "Resetting…" : "Reset password"}
        </button>
      </form>

      {success && (
        <p className="mt-6 text-center text-sm text-slate-500">
          <Link
            href="/login"
            className="font-medium text-teal-600 hover:underline"
          >
            Go to sign in
          </Link>
        </p>
      )}

      {!success && (
        <p className="mt-6 text-center text-sm text-slate-500">
          <Link
            href="/login"
            className="font-medium text-teal-600 hover:underline"
          >
            Back to sign in
          </Link>
        </p>
      )}
    </div>
  );
}
