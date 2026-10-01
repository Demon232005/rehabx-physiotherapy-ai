"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";
import Sidebar from "@/components/Sidebar";
import { useAuth } from "@/lib/api";

export default function AppLayout({ children }: { children: React.ReactNode }) {
  const { user, loading, logout } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!loading && !user) {
      router.replace("/login");
    }
  }, [loading, user, router]);

  if (loading || !user) {
    return (
      <div className="flex min-h-screen items-center justify-center text-sm text-slate-400">
        Loading…
      </div>
    );
  }

  return (
    <div className="flex min-h-screen">
      <Sidebar userName={user.full_name} userRole={user.role} onLogout={logout} />
      <main className="flex-1 overflow-x-hidden p-8">{children}</main>
    </div>
  );
}
