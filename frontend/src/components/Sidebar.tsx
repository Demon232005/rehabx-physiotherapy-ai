"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const NAV = [
  { href: "/dashboard", label: "Dashboard", icon: "▦" },
  { href: "/upload", label: "New Analysis", icon: "⇪" },
  { href: "/progress", label: "Progress", icon: "◷" },
  { href: "/exercises", label: "Exercise Library", icon: "⚕" },
];

const ADMIN_NAV = [
  { href: "/admin", label: "Admin", icon: "⚙" },
];

export default function Sidebar({
  userName,
  userRole,
  onLogout,
}: {
  userName: string;
  userRole: string;
  onLogout: () => void;
}) {
  const pathname = usePathname();
  const isAdmin = userRole === "admin";
  const allNav = isAdmin ? [...NAV, ...ADMIN_NAV] : NAV;

  return (
    <aside className="flex w-60 shrink-0 flex-col border-r border-slate-200 bg-white">
      <div className="flex items-center gap-2 border-b border-slate-200 px-5 py-4">
        <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-teal-600 text-lg font-bold text-white">
          R
        </span>
        <div className="leading-tight">
          <div className="text-sm font-bold text-slate-900">RehabX AI</div>
          <div className="text-[11px] text-slate-400">Research prototype</div>
        </div>
      </div>

      <nav className="flex-1 space-y-1 px-3 py-4">
        {allNav.map((item) => {
          const active = pathname === item.href || pathname.startsWith(`${item.href}/`);
          return (
            <Link
              key={item.href}
              href={item.href}
              className={`flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors ${
                active ? "bg-teal-50 text-teal-700" : "text-slate-600 hover:bg-slate-50 hover:text-slate-900"
              }`}
            >
              <span className="text-base">{item.icon}</span>
              {item.label}
            </Link>
          );
        })}
      </nav>

      <div className="border-t border-slate-200 px-5 py-4">
        <div className="mb-2 truncate text-sm font-medium text-slate-700">{userName}</div>
        <button
          onClick={onLogout}
          className="w-full rounded-lg border border-slate-200 px-3 py-1.5 text-sm text-slate-600 hover:bg-slate-50"
        >
          Sign out
        </button>
      </div>
    </aside>
  );
}
