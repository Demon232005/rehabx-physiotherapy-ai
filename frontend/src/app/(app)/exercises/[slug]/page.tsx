"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { use } from "react";
import { useEffect, useState } from "react";
import LiveCoach from "@/components/LiveCoach";
import { api } from "@/lib/api";
import type { ExerciseOut } from "@/lib/types";

export default function ExerciseSessionPage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = use(params);
  const router = useRouter();
  const searchParams = useSearchParams();
  // Present when launched from a report-backed recommendation card: links the
  // session (and its auto-logged progress) to that analysis/injury.
  const analysisId = searchParams.get("analysis") ?? undefined;
  const [exercise, setExercise] = useState<ExerciseOut | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    api<ExerciseOut>(`/exercises/${slug}`)
      .then((e) => {
        if (!cancelled) setExercise(e);
      })
      .catch(() => {
        if (!cancelled) setError("This exercise is no longer available in the library.");
      });
    return () => {
      cancelled = true;
    };
  }, [slug]);

  /** Leave the session — return where the user came from (recommended
   * exercises, library, …) or the library when opened directly. */
  function leaveSession() {
    if (typeof window !== "undefined" && window.history.length > 1) router.back();
    else router.push("/exercises");
  }

  if (error) {
    return (
      <div className="mx-auto max-w-md rounded-2xl border border-slate-200 bg-white p-6 text-center shadow-sm">
        <p className="text-3xl">🤔</p>
        <h1 className="mt-2 text-lg font-bold text-slate-900">Exercise not found</h1>
        <p className="mt-1 text-sm text-slate-600">{error}</p>
        <Link
          href="/exercises"
          className="mt-4 inline-block rounded-lg bg-teal-600 px-4 py-2 text-sm font-semibold text-white hover:bg-teal-700"
        >
          View all exercises
        </Link>
      </div>
    );
  }

  if (!exercise) {
    return (
      <div className="flex min-h-[40vh] items-center justify-center">
        <div className="text-sm text-slate-400">Loading session…</div>
      </div>
    );
  }

  return <LiveCoach exercise={exercise} onClose={leaveSession} analysisId={analysisId} />;
}
