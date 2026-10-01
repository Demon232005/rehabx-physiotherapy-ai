const STYLES: Record<string, string> = {
  completed: "bg-emerald-100 text-emerald-700",
  processing: "bg-sky-100 text-sky-700",
  planned: "bg-slate-100 text-slate-600",
  in_progress: "bg-sky-100 text-sky-700",
  failed: "bg-rose-100 text-rose-700",
  pending: "bg-slate-100 text-slate-500",
};

export default function StatusBadge({ status }: { status: string }) {
  return (
    <span
      className={`inline-flex rounded-full px-2.5 py-0.5 text-xs font-medium capitalize ${
        STYLES[status] ?? "bg-slate-100 text-slate-600"
      }`}
    >
      {status.replace("_", " ")}
    </span>
  );
}
