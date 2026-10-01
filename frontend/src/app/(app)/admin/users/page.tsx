"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api, useAuth } from "@/lib/api";
import type { UserListOut } from "@/lib/types";

const PAGE_SIZE = 20;
const ROLES = ["patient", "clinician", "admin"];

export default function AdminUsersPage() {
  const { user, loading: authLoading } = useAuth();
  const router = useRouter();
  const [users, setUsers] = useState<UserListOut[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchUsers = useCallback(async (skip: number) => {
    setLoading(true);
    setError(null);
    try {
      const data = await api<{ items: UserListOut[]; total: number }>(
        `/admin/users?skip=${skip}&limit=${PAGE_SIZE}`
      );
      setUsers(data.items);
      setTotal(data.total);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Request failed");
    } finally {
      setLoading(false);
    }
  }, []);

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
    fetchUsers(0);
  }, [user, authLoading, router, fetchUsers]);

  const handlePageChange = (newPage: number) => {
    setPage(newPage);
    fetchUsers(newPage * PAGE_SIZE);
  };

  const handleRoleChange = async (userId: string, newRole: string) => {
    try {
      await api(`/admin/users/${userId}`, {
        method: "PATCH",
        body: JSON.stringify({ role: newRole }),
      });
      setUsers((prev) =>
        prev.map((u) => (u.id === userId ? { ...u, role: newRole } : u))
      );
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Request failed");
    }
  };

  const handleToggleActive = async (userId: string, currentActive: boolean) => {
    try {
      if (currentActive) {
        await api(`/admin/users/${userId}`, { method: "DELETE" });
        setUsers((prev) =>
          prev.map((u) => (u.id === userId ? { ...u, is_active: false } : u))
        );
      } else {
        await api(`/admin/users/${userId}`, {
          method: "PATCH",
          body: JSON.stringify({ is_active: true }),
        });
        setUsers((prev) =>
          prev.map((u) => (u.id === userId ? { ...u, is_active: true } : u))
        );
      }
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Request failed");
    }
  };

  const totalPages = Math.ceil(total / PAGE_SIZE);

  if (authLoading || (loading && users.length === 0)) {
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
        <h1 className="text-2xl font-bold text-slate-900">User Management</h1>
        <span className="text-sm text-slate-500">{total} users</span>
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
              <th className="px-4 py-3 font-medium text-slate-600">Name</th>
              <th className="px-4 py-3 font-medium text-slate-600">Email</th>
              <th className="px-4 py-3 font-medium text-slate-600">Role</th>
              <th className="px-4 py-3 font-medium text-slate-600">Active</th>
              <th className="px-4 py-3 font-medium text-slate-600">Created</th>
              <th className="px-4 py-3 font-medium text-slate-600">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {users.map((u) => (
              <tr key={u.id} className="hover:bg-slate-50">
                <td className="px-4 py-3 font-medium text-slate-900">
                  {u.full_name}
                </td>
                <td className="px-4 py-3 text-slate-600">{u.email}</td>
                <td className="px-4 py-3">
                  <select
                    value={u.role}
                    onChange={(e) => handleRoleChange(u.id, e.target.value)}
                    className="rounded-lg border border-slate-200 bg-white px-2 py-1 text-xs font-medium text-slate-700 focus:border-teal-500 focus:outline-none"
                  >
                    {ROLES.map((r) => (
                      <option key={r} value={r}>
                        {r}
                      </option>
                    ))}
                  </select>
                </td>
                <td className="px-4 py-3">
                  <span
                    className={`inline-flex rounded-full px-2 py-0.5 text-xs font-medium ${
                      u.is_active
                        ? "bg-green-50 text-green-700"
                        : "bg-slate-100 text-slate-500"
                    }`}
                  >
                    {u.is_active ? "Active" : "Inactive"}
                  </span>
                </td>
                <td className="px-4 py-3 text-slate-500">
                  {new Date(u.created_at).toLocaleDateString()}
                </td>
                <td className="px-4 py-3">
                  <button
                    onClick={() => handleToggleActive(u.id, u.is_active)}
                    className={`rounded-lg px-3 py-1 text-xs font-medium transition-colors ${
                      u.is_active
                        ? "border border-red-200 text-red-600 hover:bg-red-50"
                        : "border border-green-200 text-green-600 hover:bg-green-50"
                    }`}
                  >
                    {u.is_active ? "Deactivate" : "Activate"}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>

        {users.length === 0 && !loading && (
          <div className="py-8 text-center text-sm text-slate-400">
            No users found.
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
