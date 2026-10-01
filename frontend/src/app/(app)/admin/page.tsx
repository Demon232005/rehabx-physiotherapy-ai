"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api, useAuth } from "@/lib/api";
import type { AdminStatsOut } from "@/lib/types";

export default function AdminDashboardPage() {
  const { user, loading: authLoading } = useAuth();
  const router = useRouter();
  const [stats, setStats] = useState<AdminStatsOut | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (authLoading) return;
    if (!user) {
      router.replace("/login");
      return;
    }
    if (user.role !== "admin") {
      setLoading(false);
      return;
    }
    api<AdminStatsOut>("/admin/stats")
      .then(setStats)
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false));
  }, [user, authLoading, router]);

  if (authLoading || loading) {
    return (
      <div className="flex min-h-[50vh] items-center justify-center text-sm text-slate-400">
        Loading…
      </div>
    );
  }

  if (!user || user.role !== "admin") {
    return (
      <div className="flex min-h-[50vh] flex-col items-center justify-center gap-2">
        <span className="text-3xl">🔒</span>
        <p className="text-sm font-medium text-slate-600">Access denied</p>
        <p className="text-xs text-slate-400">You need admin privileges to view this page.</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">
        {error}
      </div>
    );
  }

  if (!stats) return null;

  const statCards = [
    { label: "Total Users", value: stats.total_users, icon: "👤" },
    { label: "Analyses", value: stats.total_analyses, icon: "📊" },
    { label: "Uploads", value: stats.total_uploads, icon: "📁" },
    { label: "Exercises", value: stats.total_exercises, icon: "🏋" },
    { label: "Sessions", value: stats.total_sessions, icon: "🗓" },
  ];

  return (
    <div className="mx-auto max-w-5xl space-y-8">
      <h1 className="text-2xl font-bold text-slate-900">Admin Dashboard</h1>

      <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-5">
        {statCards.map((card) => (
          <div
            key={card.label}
            className="rounded-xl border border-slate-200 bg-white p-4"
          >
            <div className="mb-2 text-2xl">{card.icon}</div>
            <div className="text-2xl font-bold text-slate-900">{card.value}</div>
            <div className="text-xs text-slate-500">{card.label}</div>
          </div>
        ))}
      </div>

      <div className="grid gap-6 sm:grid-cols-2">
        <div className="rounded-xl border border-slate-200 bg-white p-6">
          <h2 className="mb-4 text-sm font-semibold uppercase tracking-wide text-slate-500">
            Users by Role
          </h2>
          <div className="space-y-3">
            {Object.entries(stats.users_by_role).map(([role, count]) => (
              <div key={role} className="flex items-center justify-between">
                <span className="text-sm font-medium capitalize text-slate-700">
                  {role}
                </span>
                <span className="rounded-full bg-teal-50 px-3 py-0.5 text-sm font-semibold text-teal-700">
                  {count}
                </span>
              </div>
            ))}
          </div>
        </div>

        <div className="rounded-xl border border-slate-200 bg-white p-6">
          <h2 className="mb-4 text-sm font-semibold uppercase tracking-wide text-slate-500">
            Analyses by Status
          </h2>
          <div className="space-y-3">
            {Object.entries(stats.analyses_by_status).map(([status, count]) => (
              <div key={status} className="flex items-center justify-between">
                <span className="text-sm font-medium capitalize text-slate-700">
                  {status.replace("_", " ")}
                </span>
                <span className="rounded-full bg-teal-50 px-3 py-0.5 text-sm font-semibold text-teal-700">
                  {count}
                </span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
