"use client";

import { useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";
import type { ExerciseOut } from "@/lib/types";
import {
  CANONICAL_REGIONS,
  CATEGORY_META,
  REGION_META,
  difficultyLabel,
  getExerciseMetaForRow,
  resolveTrackingMode,
  type TrackingMode,
} from "@/lib/exerciseLibrary";
import ExerciseAnimation from "@/components/ExerciseAnimation";
import LiveCoach from "@/components/LiveCoach";

const TRACKING_BADGE: Record<TrackingMode, string> = {
  hand: "🤚 AI Hand Tracked",
  pose: "🧍 AI Pose Tracked",
  "hand+pose": "🤚🧍 AI Dual Tracked",
};

export default function ExercisesPage() {
  const [exercises, setExercises] = useState<ExerciseOut[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [regionFilter, setRegionFilter] = useState("all");
  const [categoryFilter, setCategoryFilter] = useState("all");
  const [search, setSearch] = useState("");
  const [active, setActive] = useState<ExerciseOut | null>(null);

  useEffect(() => {
    api<ExerciseOut[]>("/exercises")
      .then(setExercises)
      .catch((e) => setError(e instanceof Error ? e.message : "Failed to load exercises"));
  }, []);

  const regions = useMemo(() => {
    if (!exercises) return ["all"];
    const present = [...new Set(exercises.map((e) => e.target_region))];
    const ordered = [
      ...CANONICAL_REGIONS.filter((r) => r !== "all" && present.includes(r)),
      ...present.filter((r) => !CANONICAL_REGIONS.includes(r)),
    ];
    return ["all", ...ordered];
  }, [exercises]);

  if (error) return <div className="text-sm text-rose-600">{error}</div>;
  if (!exercises) return <div className="text-sm text-slate-400">Loading exercise library…</div>;

  const term = search.trim().toLowerCase();
  const visible = exercises.filter((e) => {
    if (regionFilter !== "all" && e.target_region !== regionFilter) return false;
    if (categoryFilter !== "all" && (e.category ?? "mobility") !== categoryFilter) return false;
    if (
      term &&
      !e.name.toLowerCase().includes(term) &&
      !e.description.toLowerCase().includes(term)
    ) {
      return false;
    }
    return true;
  });

  const categories = ["all", ...Object.keys(CATEGORY_META)];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-900">Upper-Limb Rehabilitation Library</h1>
        <p className="text-sm text-slate-500">
          {exercises.length} clinician-reviewed exercises across fingers, thumb, palm, wrist, forearm,
          elbow &amp; shoulder — every one with an AI-guided live session.
        </p>
      </div>

      {/* Search + filters */}
      <div className="space-y-3">
        <input
          type="search"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search exercises… (e.g. shoulder, tendon, pinch)"
          className="w-full max-w-md rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-teal-500 focus:outline-none"
          aria-label="Search exercises"
        />
        <div className="flex flex-wrap gap-2" role="group" aria-label="Filter by body area">
          {regions.map((r) => (
            <button
              key={r}
              onClick={() => setRegionFilter(r)}
              className={`rounded-full px-3 py-1 text-xs font-medium capitalize transition-colors ${
                regionFilter === r
                  ? "bg-teal-600 text-white"
                  : "bg-white text-slate-600 hover:bg-slate-100"
              }`}
            >
              {r === "all" ? "All Exercises" : `${REGION_META[r]?.icon ?? ""} ${REGION_META[r]?.label ?? r}`}
            </button>
          ))}
        </div>
        <div className="flex flex-wrap gap-2" role="group" aria-label="Filter by exercise type">
          {categories.map((c) => (
            <button
              key={c}
              onClick={() => setCategoryFilter(c)}
              className={`rounded-full border px-3 py-1 text-xs font-medium transition-colors ${
                categoryFilter === c
                  ? "border-teal-600 bg-teal-50 text-teal-700"
                  : "border-slate-200 bg-white text-slate-600 hover:bg-slate-50"
              }`}
            >
              {c === "all" ? "All Types" : `${CATEGORY_META[c].icon} ${CATEGORY_META[c].label}`}
            </button>
          ))}
        </div>
      </div>

      <p className="text-xs text-slate-400" aria-live="polite">
        Showing {visible.length} of {exercises.length} exercises
      </p>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {visible.map((e) => {
          const meta = getExerciseMetaForRow(e);
          const mode = resolveTrackingMode(e);
          return (
            <div key={e.id} className="flex flex-col items-center rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
              <ExerciseAnimation slug={e.slug} label={e.name} />
              <div className="flex w-full items-start justify-between gap-2">
                <h2 className="font-semibold leading-snug text-slate-900">{e.name}</h2>
                <span
                  className={`shrink-0 rounded-full px-2 py-0.5 text-[11px] font-medium ${
                    e.difficulty === "beginner"
                      ? "bg-emerald-100 text-emerald-700"
                      : e.difficulty === "intermediate"
                        ? "bg-amber-100 text-amber-700"
                        : "bg-rose-100 text-rose-700"
                  }`}
                >
                  {difficultyLabel(e.difficulty, e.slug)}
                </span>
              </div>
              <p className="mt-2 text-sm text-slate-600">{e.description}</p>

              <dl className="mt-4 space-y-1 text-xs text-slate-500">
                <div className="flex justify-between">
                  <dt>Target area</dt>
                  <dd className="text-slate-700">
                    {meta.areaIcon} {meta.targetArea}
                  </dd>
                </div>
                <div className="flex justify-between">
                  <dt>Session</dt>
                  <dd className="text-slate-700">
                    {e.duration_minutes ? `~${e.duration_minutes} min · ` : ""}
                    {meta.recommendedReps} reps × {e.set_range_min}–{e.set_range_max}
                  </dd>
                </div>
                <div className="flex justify-between">
                  <dt>AI tracking</dt>
                  <dd className="font-medium text-teal-700">{TRACKING_BADGE[mode]}</dd>
                </div>
              </dl>

              <button
                onClick={() => setActive(e)}
                className="mt-4 w-full rounded-lg bg-teal-600 px-3 py-2 text-sm font-semibold text-white transition-colors hover:bg-teal-700"
              >
                ▶ Start Session
              </button>

              <details className="mt-4 rounded-lg bg-slate-50 p-3 text-sm text-slate-600">
                <summary className="cursor-pointer font-medium text-slate-700">Instructions</summary>
                <p className="mt-2"><strong>Start:</strong> {e.starting_position}</p>
                <p className="mt-1"><strong>Movement:</strong> {e.required_movement}</p>
                {e.contraindications.length > 0 && (
                  <p className="mt-1 text-amber-700">
                    <strong>Caution:</strong> {e.contraindications.join("; ")}
                  </p>
                )}
              </details>
            </div>
          );
        })}
      </div>

      {active && <LiveCoach exercise={active} onClose={() => setActive(null)} />}
    </div>
  );
}
