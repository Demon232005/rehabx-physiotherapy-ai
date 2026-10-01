"use client";

import Link from "next/link";
import { useState } from "react";
import ExerciseAnimation from "@/components/ExerciseAnimation";
import {
  difficultyLabel,
  getExerciseMetaForRow,
  resolveTrackingMode,
} from "@/lib/exerciseLibrary";
import type { ExerciseOut, RecommendedCategoryOut } from "@/lib/types";

const TRACKING_BADGE: Record<string, string> = {
  hand: "AI Hand Tracked",
  pose: "AI Pose Tracked",
  "hand+pose": "AI Dual Tracked",
};

interface Props {
  categories: RecommendedCategoryOut[];
  /** Report-driven heading, e.g. "Recommended for your Left Index Finger". */
  title?: string;
  subtitle?: string;
  /** Links the session to the report-backed analysis (spec §18-§19). */
  analysisId?: string;
}

/** Rough session length so users know what they are committing to. */
function estimateMinutes(exercise: ExerciseOut): string {
  if (exercise.duration_minutes) return `~${exercise.duration_minutes} min`;
  const meta = getExerciseMetaForRow(exercise);
  const perRep = meta.holdSeconds ? meta.holdSeconds + 1.5 : 2;
  const seconds = meta.recommendedReps * exercise.set_range_max * perRep;
  return `~${Math.max(1, Math.round(seconds / 60))} min`;
}

function intensityLabel(exercise: ExerciseOut): string {
  return exercise.difficulty === "beginner" ? "Low intensity" : "Moderate intensity";
}

function difficultyPillClass(difficulty: string): string {
  if (difficulty === "beginner") return "bg-emerald-100 text-emerald-700";
  if (difficulty === "intermediate") return "bg-amber-100 text-amber-700";
  return "bg-rose-100 text-rose-700";
}

function sessionHref(slug: string, analysisId?: string): string {
  const base = `/exercises/${slug}`;
  return analysisId ? `${base}?analysis=${analysisId}` : base;
}

/** Report-derived target line, e.g. "Target: Left index finger" (spec §15). */
function targetLabel(category: RecommendedCategoryOut): string | null {
  const side = category.target_side
    ? category.target_side.charAt(0).toUpperCase() + category.target_side.slice(1)
    : null;
  const area =
    category.specific_structure?.replace(/_/g, " ") ??
    category.sub_region?.replace(/_/g, " ") ??
    category.target_region?.replace(/_/g, " ") ??
    null;
  const label = [side, area].filter(Boolean).join(" ");
  return label ? `Target: ${label}` : null;
}

/** One recommended focus area. The primary action opens the first
 * clinician-approved exercise of the category directly in a live session;
 * remaining members are one click away too. */
function RecommendationCard({
  category,
  analysisId,
}: {
  category: RecommendedCategoryOut;
  analysisId?: string;
}) {
  const [showDetails, setShowDetails] = useState(false);
  const exercises = category.exercises ?? [];
  const primary = exercises[0];
  const target = targetLabel(category);

  if (!primary) {
    // Safety fallback (spec §12/§21): nothing can be recommended safely —
    // say so plainly instead of guessing.
    const consult = category.status === "not_safe" || category.status === "needs_clarification";
    return (
      <div className="flex flex-col rounded-xl border border-dashed border-slate-300 bg-slate-50 p-4">
        <h3 className="font-semibold text-slate-900">{category.label}</h3>
        <p className="mt-1 text-sm text-slate-600">{category.description}</p>
        {consult && (
          <p className="mt-2 rounded-lg bg-amber-50 px-3 py-2 text-xs font-medium text-amber-800">
            {category.message ??
              "Your report does not provide enough information to safely recommend this exercise. Please consult your physiotherapist."}
          </p>
        )}
        <Link
          href="/exercises"
          className="mt-auto pt-3 text-sm font-medium text-teal-700 hover:text-teal-800 hover:underline"
        >
          View all exercises →
        </Link>
      </div>
    );
  }

  const rest = exercises.slice(1);
  const primaryMeta = getExerciseMetaForRow(primary);
  const mode = resolveTrackingMode(primary);

  return (
    <div className="flex flex-col overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm transition-shadow hover:shadow-md">
      {/* Clickable preview area */}
      <Link href={sessionHref(primary.slug, analysisId)} className="block bg-gradient-to-br from-teal-50 to-slate-50">
        <div className="flex items-center justify-center py-2">
          <ExerciseAnimation slug={primary.slug} label={primary.name} />
        </div>
      </Link>

      <div className="flex flex-1 flex-col p-4">
        {target && (
          <p className="text-[11px] font-semibold uppercase tracking-wide text-teal-700">{target}</p>
        )}
        <div className="mt-1 flex flex-wrap items-center gap-1.5">
          <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[11px] font-medium text-slate-600">
            {primaryMeta.areaIcon} {primaryMeta.targetArea}
          </span>
          <span
            className={`rounded-full px-2 py-0.5 text-[11px] font-medium ${difficultyPillClass(primary.difficulty)}`}
          >
            {difficultyLabel(primary.difficulty, primary.slug)}
          </span>
          <span className="rounded-full bg-teal-50 px-2 py-0.5 text-[11px] font-semibold text-teal-700">
            {TRACKING_BADGE[mode] ?? "AI Tracked"}
          </span>
        </div>
        <h3 className="mt-1.5 font-semibold leading-snug text-slate-900">{primary.name}</h3>
        <p className="mt-1 text-sm text-slate-600">{category.description}</p>

        <dl className="mt-3 grid grid-cols-3 gap-2 rounded-lg bg-slate-50 px-3 py-2 text-center text-xs">
          <div>
            <dt className="text-slate-400">Duration</dt>
            <dd className="font-semibold text-slate-700">{estimateMinutes(primary)}</dd>
          </div>
          <div className="border-x border-slate-200">
            <dt className="text-slate-400">Intensity</dt>
            <dd className="font-semibold text-slate-700">{intensityLabel(primary)}</dd>
          </div>
          <div>
            <dt className="text-slate-400">Recommended</dt>
            <dd className="font-semibold text-slate-700">{primary.rep_range_min}–{primary.rep_range_max} reps</dd>
          </div>
        </dl>

        {rest.length > 0 && (
          <p className="mt-2 text-xs text-slate-500">
            Also in this focus:{" "}
            {rest.map((ex, i) => (
              <span key={ex.slug}>
                {i > 0 && " · "}
                <Link href={sessionHref(ex.slug, analysisId)} className="font-medium text-teal-700 hover:underline">
                  {ex.name}
                </Link>
              </span>
            ))}
          </p>
        )}

        {/* Primary action — straight into the session for THIS exercise */}
        <Link
          href={sessionHref(primary.slug, analysisId)}
          className="mt-4 block w-full rounded-lg bg-teal-600 px-3 py-2.5 text-center text-sm font-semibold text-white transition-colors hover:bg-teal-700"
        >
          Start Exercise →
        </Link>

        <button
          type="button"
          onClick={() => setShowDetails((v) => !v)}
          className="mt-2 self-start text-xs font-medium text-slate-500 hover:text-slate-700 hover:underline"
        >
          {showDetails ? "Hide details" : "View Details"}
        </button>

        {showDetails && (
          <div className="mt-2 space-y-1.5 rounded-lg bg-slate-50 p-3 text-xs text-slate-600">
            <p><strong className="text-slate-700">Start:</strong> {primary.starting_position}</p>
            <p><strong className="text-slate-700">Movement:</strong> {primary.required_movement}</p>
            {primary.contraindications.length > 0 && (
              <p className="text-amber-700"><strong>Caution:</strong> {primary.contraindications.join("; ")}</p>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

export default function RecommendedExercises({ categories, title, subtitle, analysisId }: Props) {
  return (
    <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h2 className="text-lg font-semibold text-slate-900">
            {title ?? "Recommended exercises"}
          </h2>
          <p className="mt-0.5 text-sm text-slate-500">
            {subtitle ?? "Personalised for your analysis — start any session directly, no searching needed."}
          </p>
        </div>
        <Link href="/exercises" className="text-sm font-medium text-teal-700 hover:text-teal-800 hover:underline">
          Browse full library →
        </Link>
      </div>
      <div className="mt-4 grid gap-4 sm:grid-cols-2">
        {categories.map((c) => (
          <RecommendationCard key={c.key} category={c} analysisId={analysisId} />
        ))}
      </div>
    </section>
  );
}
