"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";
import type { ExerciseSessionOut, ProgressOut } from "@/lib/types";
import ProgressCharts from "@/components/ProgressCharts";

/** Dashboard-level body areas and which library regions belong to each. */
const BODY_AREAS = ["all", "Hand", "Wrist", "Forearm", "Elbow", "Shoulder"] as const;
type BodyArea = (typeof BODY_AREAS)[number];

function regionToArea(region: string | undefined): Exclude<BodyArea, "all"> | "General" {
  switch (region) {
    case "hand":
    case "fingers":
    case "thumb":
    case "palm":
    case "grip":
      return "Hand";
    case "wrist":
      return "Wrist";
    case "forearm":
      return "Forearm";
    case "elbow":
      return "Elbow";
    case "shoulder":
      return "Shoulder";
    default:
      return "General"; // manual entries without a linked session
  }
}

export default function ProgressPage() {
  const [sessions, setSessions] = useState<ExerciseSessionOut[] | null>(null);
  const [progress, setProgress] = useState<ProgressOut[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [areaFilter, setAreaFilter] = useState<BodyArea>("all");

  const [pain, setPain] = useState("3");
  const [grip, setGrip] = useState("");
  const [rom, setRom] = useState("");
  const [improvement, setImprovement] = useState("");
  const [notes, setNotes] = useState("");
  const [submitting, setSubmitting] = useState(false);

  // session id → body area, so auto-logged entries inherit their exercise's region
  const areaBySessionId = useMemo(() => {
    const map = new Map<string, ReturnType<typeof regionToArea>>();
    for (const s of sessions ?? []) {
      map.set(s.id, regionToArea(s.exercise?.target_region));
    }
    return map;
  }, [sessions]);

  const visibleProgress = useMemo(() => {
    if (!progress) return [];
    if (areaFilter === "all") return progress;
    return progress.filter((p) => {
      const area = p.exercise_session_id
        ? areaBySessionId.get(p.exercise_session_id) ?? "General"
        : "General";
      return area === areaFilter || area === "General";
    });
  }, [progress, areaFilter, areaBySessionId]);

  const load = useCallback(() => {
    api<ExerciseSessionOut[]>("/sessions").then(setSessions).catch(() => undefined);
    api<ProgressOut[]>("/progress").then(setProgress).catch(() => undefined);
  }, []);

  useEffect(() => {
    api<ExerciseSessionOut[]>("/sessions")
      .then(setSessions)
      .catch((e) => setError(e instanceof Error ? e.message : "Failed to load data"));
    api<ProgressOut[]>("/progress")
      .then(setProgress)
      .catch(() => undefined);
  }, []);

  async function onLog(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      await api("/progress", {
        method: "POST",
        body: JSON.stringify({
          pain_level: Number(pain),
          grip_strength_kg: grip ? Number(grip) : null,
          range_of_motion_deg: rom ? Number(rom) : null,
          self_reported_improvement: improvement ? Number(improvement) : null,
          notes: notes || null,
        }),
      });
      setGrip("");
      setRom("");
      setImprovement("");
      setNotes("");
      load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to save progress");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="mx-auto max-w-4xl space-y-8">
      <div>
        <h1 className="text-2xl font-bold text-slate-900">Progress tracking</h1>
        <p className="text-sm text-slate-500">
          Log exercise sessions and self-reported measurements over time.
        </p>
      </div>

      {error && <div className="rounded-lg bg-rose-50 px-3 py-2 text-sm text-rose-700">{error}</div>}

      <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        <h2 className="text-lg font-semibold text-slate-900">Log today&apos;s progress</h2>
        <form onSubmit={onLog} className="mt-4 grid gap-4 sm:grid-cols-2">
          <label className="block text-sm font-medium text-slate-700">
            Pain level (0–10)
            <input
              type="range"
              min={0}
              max={10}
              value={pain}
              onChange={(e) => setPain(e.target.value)}
              className="mt-2 w-full accent-teal-600"
            />
            <span className="text-xs text-slate-500">{pain} / 10</span>
          </label>
          <label className="block text-sm font-medium text-slate-700">
            <span>
              Grip strength (Optional){" "}
              {grip && (
                <button
                  type="button"
                  onClick={() => setGrip("")}
                  className="ml-1 text-xs font-normal text-slate-400 underline hover:text-slate-600"
                >
                  Skip
                </button>
              )}
            </span>
            <input
              type="number"
              min={0}
              step={0.1}
              value={grip}
              onChange={(e) => setGrip(e.target.value)}
              placeholder="e.g. 18.5"
              className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm outline-none focus:border-teal-500"
            />
            <span className="mt-1 block text-xs font-normal text-slate-500">
              Only enter this if you have a grip dynamometer.
            </span>
          </label>
          <label className="block text-sm font-medium text-slate-700">
            ROM (Optional)
            <input
              type="number"
              min={0}
              step={1}
              value={rom}
              onChange={(e) => setRom(e.target.value)}
              placeholder="e.g. 55"
              className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm outline-none focus:border-teal-500"
            />
            <span className="mt-1 block text-xs font-normal text-slate-500">
              Only enter this if you measured it with a goniometer. Otherwise, RehabX uses the
              AI-measured ROM recorded during your exercise sessions.
            </span>
          </label>
          <label className="block text-sm font-medium text-slate-700">
            Self-reported improvement (0–100%)
            <input
              type="number"
              min={0}
              max={100}
              value={improvement}
              onChange={(e) => setImprovement(e.target.value)}
              placeholder="e.g. 40"
              className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm outline-none focus:border-teal-500"
            />
          </label>
          <label className="block text-sm font-medium text-slate-700 sm:col-span-2">
            Notes
            <textarea
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              rows={2}
              className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm outline-none focus:border-teal-500"
            />
          </label>
          <div className="sm:col-span-2">
            <button
              type="submit"
              disabled={submitting}
              className="rounded-lg bg-teal-600 px-4 py-2 text-sm font-semibold text-white hover:bg-teal-700 disabled:opacity-50"
            >
              {submitting ? "Saving…" : "Save entry"}
            </button>
          </div>
        </form>
      </section>

      <section>
        <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
          <h2 className="text-lg font-semibold text-slate-900">Progress charts</h2>
          {/* Body-area filter (spec §17) */}
          <div className="flex flex-wrap gap-1.5" role="group" aria-label="Filter by body area">
            {BODY_AREAS.map((area) => (
              <button
                key={area}
                type="button"
                onClick={() => setAreaFilter(area)}
                aria-pressed={areaFilter === area}
                className={`rounded-full px-3 py-1 text-xs font-medium transition-colors ${
                  areaFilter === area
                    ? "bg-teal-600 text-white"
                    : "bg-white text-slate-600 ring-1 ring-slate-200 hover:bg-slate-50"
                }`}
              >
                {area === "all" ? "All areas" : area}
              </button>
            ))}
          </div>
        </div>
        <ProgressCharts data={visibleProgress} />
      </section>

      <section>
        <h2 className="mb-3 text-lg font-semibold text-slate-900">Progress history</h2>
        {visibleProgress.length === 0 ? (
          <div className="rounded-xl border border-dashed border-slate-300 bg-white p-8 text-center text-sm text-slate-500">
            No progress logged yet.
          </div>
        ) : (
          <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white shadow-sm">
            <table className="w-full text-sm">
              <thead className="bg-slate-50 text-left text-xs uppercase text-slate-500">
                <tr>
                  <th className="px-4 py-3 font-medium">Date</th>
                  <th className="px-4 py-3 font-medium">Source</th>
                  <th className="px-4 py-3 font-medium">Pain</th>
                  <th className="px-4 py-3 font-medium">Grip (kg)</th>
                  <th className="px-4 py-3 font-medium">ROM (°)</th>
                  <th className="px-4 py-3 font-medium">Form</th>
                  <th className="px-4 py-3 font-medium">Improvement</th>
                  <th className="px-4 py-3 font-medium">Notes</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {visibleProgress.map((p) => (
                  <tr key={p.id} className="hover:bg-slate-50">
                    <td className="px-4 py-3 text-slate-600">{new Date(p.date).toLocaleDateString()}</td>
                    <td className="px-4 py-3">
                      <span
                        className={`rounded-full px-2 py-0.5 text-[11px] font-medium ${
                          p.source === "session"
                            ? "bg-teal-50 text-teal-700"
                            : "bg-slate-100 text-slate-600"
                        }`}
                      >
                        {p.source === "session" ? "AI session" : "Manual"}
                      </span>
                    </td>
                    <td className="px-4 py-3">{p.pain_level ?? "—"}</td>
                    <td className="px-4 py-3">{p.grip_strength_kg ?? "—"}</td>
                    <td className="px-4 py-3">{p.range_of_motion_deg != null ? `≈${p.range_of_motion_deg}°` : "—"}</td>
                    <td className="px-4 py-3">{p.form_score != null ? `${p.form_score}%` : "—"}</td>
                    <td className="px-4 py-3">
                      {p.self_reported_improvement != null ? `${p.self_reported_improvement}%` : "—"}
                    </td>
                    <td className="max-w-[220px] truncate px-4 py-3 text-slate-500">{p.notes ?? "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <section>
        <h2 className="mb-3 text-lg font-semibold text-slate-900">Exercise sessions</h2>
        {!sessions || sessions.length === 0 ? (
          <div className="rounded-xl border border-dashed border-slate-300 bg-white p-8 text-center text-sm text-slate-500">
            No exercise sessions yet. Sessions are planned from your rehabilitation plan.
          </div>
        ) : (
          <div className="space-y-2">
            {sessions.map((s) => (
              <div
                key={s.id}
                className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-slate-200 bg-white px-5 py-3 shadow-sm"
              >
                <div>
                  <div className="font-medium text-slate-900">{s.exercise?.name ?? s.exercise_id}</div>
                  <div className="text-xs text-slate-500">
                    {s.completed_reps != null ? `${s.completed_reps}/${s.planned_reps ?? "–"} reps` : `${s.planned_reps ?? "–"} reps planned`}
                    {" · "}
                    {s.completed_sets != null ? `${s.completed_sets}/${s.planned_sets ?? "–"} sets` : `${s.planned_sets ?? "–"} sets planned`}
                    {s.pain_level != null ? ` · pain ${s.pain_level}/10` : ""}
                  </div>
                </div>
                <span
                  className={`rounded-full px-2.5 py-0.5 text-xs font-medium capitalize ${
                    s.status === "completed"
                      ? "bg-emerald-100 text-emerald-700"
                      : s.status === "planned"
                        ? "bg-slate-100 text-slate-600"
                        : "bg-sky-100 text-sky-700"
                  }`}
                >
                  {s.status.replace("_", " ")}
                </span>
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
