"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api, useAuth } from "@/lib/api";
import type { AuditLogOut, AuditLogListOut } from "@/lib/types";

const PAGE_SIZE = 30;

export default function AdminAuditPage() {
  const { user, loading: authLoading } = useAuth();
  const router = useRouter();
  const [logs, setLogs] = useState<AuditLogOut[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(0);
  const [userIdFilter, setUserIdFilter] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchLogs = useCallback(
    async (skip: number, userId?: string) => {
      setLoading(true);
      setError(null);
      try {
        const params = new URLSearchParams({
          skip: String(skip),
          limit: String(PAGE_SIZE),
        });
        if (userId) params.set("user_id", userId);
        const data = await api<AuditLogListOut>(
          `/admin/audit-logs?${params.toString()}`
        );
        setLogs(data.items);
        setTotal(data.total);
      } catch (e: unknown) {
        setError(e instanceof Error ? e.message : "Request failed");
      } finally {
        setLoading(false);
      }
    },
    []
  );

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
    fetchLogs(0);
  }, [user, authLoading, router, fetchLogs]);

  const handlePageChange = (newPage: number) => {
    setPage(newPage);
    fetchLogs(newPage * PAGE_SIZE, userIdFilter || undefined);
  };

  const handleFilter = () => {
    setPage(0);
    fetchLogs(0, userIdFilter || undefined);
  };

  const totalPages = Math.ceil(total / PAGE_SIZE);

  if (authLoading || (loading && logs.length === 0)) {
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

  return (
    <div className="mx-auto max-w-6xl space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-slate-900">Audit Logs</h1>
        <span className="text-sm text-slate-500">{total} entries</span>
      </div>

      <div className="flex items-center gap-2">
        <input
          type="text"
          placeholder="Filter by User ID…"
          value={userIdFilter}
          onChange={(e) => setUserIdFilter(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && handleFilter()}
          className="w-64 rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-sm text-slate-700 placeholder:text-slate-400 focus:border-teal-500 focus:outline-none"
        />
        <button
          onClick={handleFilter}
          className="rounded-lg bg-teal-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-teal-700"
        >
          Filter
        </button>
        {userIdFilter && (
          <button
            onClick={() => {
              setUserIdFilter("");
              setPage(0);
              fetchLogs(0);
            }}
            className="rounded-lg border border-slate-200 px-3 py-1.5 text-sm text-slate-600 hover:bg-slate-50"
          >
            Clear
          </button>
        )}
      </div>

      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">
          {error}
        </div>
      )}

      <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white">
        <table className="w-full text-left text-sm">
          <thead>
            <tr className="border-b border-slate-100 bg-slate-50">
              <th className="px-4 py-3 font-medium text-slate-600">Time</th>
              <th className="px-4 py-3 font-medium text-slate-600">User ID</th>
              <th className="px-4 py-3 font-medium text-slate-600">Action</th>
              <th className="px-4 py-3 font-medium text-slate-600">Entity</th>
              <th className="px-4 py-3 font-medium text-slate-600">IP Address</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {logs.map((log) => (
              <tr key={log.id} className="hover:bg-slate-50">
                <td className="whitespace-nowrap px-4 py-2.5 text-slate-500">
                  {new Date(log.created_at).toLocaleString()}
                </td>
                <td className="px-4 py-2.5 font-mono text-xs text-slate-600">
                  {log.user_id.slice(0, 8)}…
                </td>
                <td className="px-4 py-2.5">
                  <span className="rounded-md bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-700">
                    {log.action}
                  </span>
                </td>
                <td className="px-4 py-2.5 text-slate-600">
                  {log.entity}
                  {log.entity_id && (
                    <span className="ml-1 font-mono text-xs text-slate-400">
                      ({log.entity_id.slice(0, 8)}…)
                    </span>
                  )}
                </td>
                <td className="px-4 py-2.5 font-mono text-xs text-slate-500">
                  {log.ip_address ?? "—"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>

        {logs.length === 0 && !loading && (
          <div className="py-8 text-center text-sm text-slate-400">
            No audit logs found.
          </div>
        )}
      </div>

      {totalPages > 1 && (
        <div className="flex items-center justify-center gap-2">
          <button
            onClick={() => handlePageChange(page - 1)}
            disabled={page === 0}
            className="rounded-lg border border-slate-200 px-3 py-1.5 text-sm text-slate-600 hover:bg-slate-50 disabled:opacity-40"
          >
            Previous
          </button>
          <span className="text-sm text-slate-500">
            Page {page + 1} of {totalPages}
          </span>
          <button
            onClick={() => handlePageChange(page + 1)}
            disabled={page >= totalPages - 1}
            className="rounded-lg border border-slate-200 px-3 py-1.5 text-sm text-slate-600 hover:bg-slate-50 disabled:opacity-40"
          >
            Next
          </button>
        </div>
      )}
    </div>
  );
}
