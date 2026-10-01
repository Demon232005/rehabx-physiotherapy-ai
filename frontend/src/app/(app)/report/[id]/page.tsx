"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { use } from "react";
import DisclaimerBanner from "@/components/DisclaimerBanner";
import RecommendedExercises from "@/components/RecommendedExercises";
import { api } from "@/lib/api";
import type { ReportOut } from "@/lib/types";

export default function ReportPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const [report, setReport] = useState<ReportOut | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api<ReportOut>(`/analyses/${id}/report`)
      .then(setReport)
      .catch((e) => setError(e instanceof Error ? e.message : "Failed to load report"));
  }, [id]);

  if (error) return <div className="text-sm text-rose-600">{error}</div>;
  if (!report) return <div className="text-sm text-slate-400">Loading report…</div>;

  const rec = report.recommendation;
  const guidance = rec.repetition_guidance as Record<string, unknown>;
  const structure = rec.session_structure as Record<string, unknown>;
  const reportFindings = (report.analysis.findings.report ?? {}) as Record<string, any>;
  const reportProvided = reportFindings.provided === true;

  // Spec §15: the plan heading names the affected area from the report,
  // e.g. "Left Index Finger Rehabilitation".
  const pretty = (s: string | null | undefined) =>
    (s ?? "").replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase()).trim();
  const specificArea =
    pretty(reportFindings.specific_structure) ||
    pretty(rec.extraction?.specific_structure) ||
    pretty(reportFindings.sub_region) ||
    pretty(rec.extraction?.sub_region) ||
    pretty(rec.affected_region);
  const sideWord = pretty(rec.affected_side);
  const planHeading = [sideWord, specificArea].filter(Boolean).join(" ") || "Your";
  const isReportDriven = rec.engine_version.startsWith("2.");

  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">{planHeading} Rehabilitation</h1>
          <p className="text-sm text-slate-500">
            {isReportDriven
              ? `Based on your uploaded report · generated ${new Date(rec.created_at).toLocaleDateString()}`
              : `Generated for ${rec.affected_side} ${rec.affected_region} on ${new Date(rec.created_at).toLocaleDateString()}`}
          </p>
        </div>
        <Link
          href={`/analyses/${report.analysis.id}`}
          className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
        >
          Back to analysis
        </Link>
      </div>

      {reportProvided && (
        <section className="rounded-2xl border border-teal-200 bg-teal-50 p-5 shadow-sm">
          <h2 className="text-sm font-semibold text-teal-900">From the X-ray report</h2>
          <dl className="mt-2 grid grid-cols-2 gap-2 text-sm sm:grid-cols-4">
            <div>
              <dt className="text-teal-700">Side</dt>
              <dd className="font-medium capitalize text-teal-900">
                {String(reportFindings.affected_side ?? "—")}
              </dd>
            </div>
            <div>
              <dt className="text-teal-700">Severity</dt>
              <dd className="font-medium capitalize text-teal-900">
                {String(reportFindings.severity ?? "—")}
              </dd>
            </div>
            <div>
              <dt className="text-teal-700">Condition</dt>
              <dd className="font-medium capitalize text-teal-900">
                {String(reportFindings.condition_label ?? "—")}
              </dd>
            </div>
            <div>
              <dt className="text-teal-700">Region</dt>
              <dd className="font-medium capitalize text-teal-900">
                {String(reportFindings.affected_region ?? "—")}
              </dd>
            </div>
          </dl>
          {typeof reportFindings.summary === "string" && reportFindings.summary && (
            <p className="mt-3 text-sm text-teal-900">{reportFindings.summary}</p>
          )}
        </section>
      )}

      <DisclaimerBanner text={rec.disclaimer} />

      <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h2 className="text-lg font-semibold text-slate-900">{rec.rehab_focus}</h2>
          <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-medium text-slate-600">
            {rec.abnormality_category}
          </span>
        </div>

        <h3 className="mt-5 text-sm font-semibold text-slate-700">Why this focus</h3>
        <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-slate-600">
          {rec.focus_reasoning.map((r, i) => (
            <li key={i}>{r}</li>
          ))}
        </ul>
      </section>

      <RecommendedExercises
        categories={rec.recommended_exercise_categories}
        title={`Recommended for your ${planHeading}`}
        subtitle="Based on your uploaded report."
        analysisId={report.analysis.id}
      />

      <div className="grid gap-6 md:grid-cols-2">
        <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
          <h2 className="text-lg font-semibold text-slate-900">Movement requirements</h2>
          <ul className="mt-3 list-disc space-y-1.5 pl-5 text-sm text-slate-600">
            {rec.movement_requirements.map((m, i) => (
              <li key={i}>{m}</li>
            ))}
          </ul>
        </section>

        <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
          <h2 className="text-lg font-semibold text-slate-900">Session guidance</h2>
          <dl className="mt-3 space-y-2 text-sm">
            {Object.entries({ ...(guidance as object), ...(structure as object) }).map(
              ([k, v]) => (
                <div key={k} className="flex justify-between gap-4">
                  <dt className="capitalize text-slate-500">{k.replace(/_/g, " ")}</dt>
                  <dd className="text-right font-medium text-slate-800">
                    {Array.isArray(v) ? v.join(" – ") : typeof v === "object" && v !== null ? JSON.stringify(v) : String(v)}
                  </dd>
                </div>
              )
            )}
          </dl>
        </section>
      </div>

      <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        <h2 className="text-lg font-semibold text-slate-900">Safety warnings</h2>
        <ul className="mt-3 list-disc space-y-1.5 pl-5 text-sm text-slate-600">
          {rec.safety_warnings.map((w, i) => (
            <li key={i}>{w}</li>
          ))}
        </ul>
      </section>

      <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        <h2 className="text-lg font-semibold text-slate-900">Full report text</h2>
        <pre className="mt-3 overflow-x-auto rounded-lg bg-slate-950 p-4 text-xs leading-relaxed text-slate-100">
          {report.report_text}
        </pre>
      </section>
    </div>
  );
}
