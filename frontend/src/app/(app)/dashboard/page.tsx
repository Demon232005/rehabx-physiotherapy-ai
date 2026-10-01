"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import DisclaimerBanner from "@/components/DisclaimerBanner";
import StatusBadge from "@/components/StatusBadge";
import { api } from "@/lib/api";
import type { DashboardOut } from "@/lib/types";

export default function DashboardPage() {
  const [data, setData] = useState<DashboardOut | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api<DashboardOut>("/dashboard")
      .then(setData)
      .catch((e) => setError(e instanceof Error ? e.message : "Failed to load dashboard"));
  }, []);

  if (error) return <div className="text-sm text-rose-600">{error}</div>;
  if (!data) return <div className="text-sm text-slate-400">Loading dashboard…</div>;

  const stats = [
    { label: "Total analyses", value: data.total_analyses },
    { label: "Sessions completed", value: data.total_sessions_completed },
    { label: "Exercises in library", value: data.exercise_count },
  ];

  return (
    <div className="space-y-8">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Dashboard</h1>
          <p className="text-sm text-slate-500">Your recovery at a glance.</p>
        </div>
        <Link
          href="/upload"
          className="rounded-lg bg-teal-600 px-4 py-2 text-sm font-semibold text-white hover:bg-teal-700"
        >
          New analysis
        </Link>
      </div>

      <div className="grid gap-4 sm:grid-cols-3">
        {stats.map((s) => (
          <div key={s.label} className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
            <div className="text-2xl font-bold text-slate-900">{s.value}</div>
            <div className="text-sm text-slate-500">{s.label}</div>
          </div>
        ))}
      </div>

      <DisclaimerBanner />

      <section>
        <h2 className="mb-3 text-lg font-semibold text-slate-900">Recent analyses</h2>
        {data.recent_analyses.length === 0 ? (
          <div className="rounded-xl border border-dashed border-slate-300 bg-white p-8 text-center text-sm text-slate-500">
            No analyses yet.{" "}
            <Link href="/upload" className="font-medium text-teal-600 hover:underline">
              Upload your first X-ray
            </Link>
            .
          </div>
        ) : (
          <div className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
            <table className="w-full text-sm">
              <thead className="bg-slate-50 text-left text-xs uppercase text-slate-500">
                <tr>
                  <th className="px-4 py-3 font-medium">Date</th>
                  <th className="px-4 py-3 font-medium">File</th>
                  <th className="px-4 py-3 font-medium">Region</th>
                  <th className="px-4 py-3 font-medium">Prediction</th>
                  <th className="px-4 py-3 font-medium">Status</th>
                  <th className="px-4 py-3 font-medium"></th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {data.recent_analyses.map((a) => (
                  <tr key={a.id} className="hover:bg-slate-50">
                    <td className="px-4 py-3 text-slate-600">
                      {new Date(a.created_at).toLocaleDateString()}
                    </td>
                    <td className="px-4 py-3 font-medium text-slate-800">
                      {a.upload?.original_filename ?? "—"}
                    </td>
                    <td className="px-4 py-3 capitalize text-slate-600">
                      {a.upload?.affected_region ?? "—"}
                    </td>
                    <td className="px-4 py-3">
                      <span
                        className={`font-semibold ${
                          a.prediction_label === "abnormal" ? "text-rose-600" : "text-emerald-600"
                        }`}
                      >
                        {a.prediction_label}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <StatusBadge status={a.status} />
                    </td>
                    <td className="px-4 py-3 text-right">
                      <Link
                        href={`/analyses/${a.id}`}
                        className="font-medium text-teal-600 hover:underline"
                      >
                        View
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}
