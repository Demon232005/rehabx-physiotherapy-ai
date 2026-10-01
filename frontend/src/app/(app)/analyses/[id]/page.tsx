"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { use } from "react";
import DisclaimerBanner from "@/components/DisclaimerBanner";
import RegionOverlay from "@/components/RegionOverlay";
import StatusBadge from "@/components/StatusBadge";
import XrayImage from "@/components/XrayImage";
import ReportFileView from "@/components/ReportFileView";
import { api } from "@/lib/api";
import type { AnalysisDetailOut, ReportParsed } from "@/lib/types";

export default function AnalysisPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const [analysis, setAnalysis] = useState<AnalysisDetailOut | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [imgDims, setImgDims] = useState({ w: 0, h: 0 });

  useEffect(() => {
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | undefined;

    async function poll() {
      try {
        const a = await api<AnalysisDetailOut>(`/analyses/${id}`);
        if (!cancelled) setAnalysis(a);
        if (a.status === "processing") {
          timer = setTimeout(poll, 1500);
        }
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : "Failed to load analysis");
      }
    }

    poll();
    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
    };
  }, [id]);

  if (error) return <div className="text-sm text-rose-600">{error}</div>;
  if (!analysis) return <div className="text-sm text-slate-400">Loading analysis…</div>;

  const processing = analysis.status === "processing";
  const findings = analysis.findings as Record<string, unknown>;
  const reportFindings = (findings.report ?? {}) as Partial<ReportParsed> & { provided?: boolean };
  const reportProvided = reportFindings.provided === true;
  const imgW = imgDims.w || analysis.upload?.image_width || 0;
  const imgH = imgDims.h || analysis.upload?.image_height || 0;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Analysis</h1>
          <p className="text-sm text-slate-500">
            {analysis.upload?.original_filename} · uploaded{" "}
            {new Date(analysis.created_at).toLocaleString()}
          </p>
        </div>
        <StatusBadge status={analysis.status} />
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <div className="relative">
          <XrayImage
            uploadId={analysis.upload_id}
            onLoad={(w, h) => setImgDims({ w, h })}
            className="h-auto w-full rounded-lg border border-slate-200 bg-black shadow-sm"
          />
          <RegionOverlay regions={analysis.regions} imageWidth={imgW} imageHeight={imgH} />
          {processing && (
            <div className="absolute inset-0 flex items-center justify-center rounded-lg bg-black/40">
              <div className="rounded-xl bg-white/95 px-5 py-4 text-center shadow">
                <div className="mx-auto mb-2 h-5 w-5 animate-spin rounded-full border-2 border-teal-600 border-t-transparent" />
                <p className="text-sm font-medium text-slate-800">
                  AI is analyzing this X-ray…
                </p>
                <p className="text-xs text-slate-500">
                  Model: {analysis.model_name} ({analysis.model_status})
                </p>
              </div>
            </div>
          )}
        </div>

        <div className="lg:col-span-2">
          <ReportFileView uploadId={analysis.upload_id} />
        </div>

        <div className="space-y-4">
          {processing ? (
            <div className="rounded-xl border border-slate-200 bg-white p-6 text-sm text-slate-500">
              Results will appear here when analysis completes.
            </div>
          ) : analysis.status === "failed" ? (
            <div className="rounded-xl border border-rose-200 bg-rose-50 p-6 text-sm text-rose-700">
              This analysis failed. Please delete it and try uploading again.
            </div>
          ) : (
            <>
              <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
                <div className="flex items-center justify-between">
                  <h2 className="text-lg font-semibold text-slate-900">Prediction</h2>
                  <span
                    className={`rounded-full px-3 py-1 text-sm font-bold ${
                      analysis.prediction_label === "abnormal"
                        ? "bg-rose-100 text-rose-700"
                        : "bg-emerald-100 text-emerald-700"
                    }`}
                  >
                    {analysis.prediction_label.toUpperCase()}
                  </span>
                </div>
                <div className="mt-4">
                  <div className="mb-1 flex justify-between text-sm">
                    <span className="text-slate-500">Abnormal</span>
                    <span className="font-medium text-slate-800">
                      {(analysis.class_probabilities.abnormal ?? 0) * 100}%
                    </span>
                  </div>
                  <div className="h-2.5 w-full overflow-hidden rounded-full bg-slate-100">
                    <div
                      className="h-full rounded-full bg-gradient-to-r from-emerald-400 via-amber-400 to-rose-500"
                      style={{ width: "100%" }}
                    />
                    <div
                      className="pointer-events-none mt-[-10px] h-2.5 w-0.5 bg-slate-900"
                      style={{ marginLeft: `${(analysis.class_probabilities.abnormal ?? 0) * 100}%` }}
                    />
                  </div>
                </div>
                <p className="mt-3 text-sm text-slate-500">{findings.summary as string}</p>
              </div>

              {reportProvided && (
                <div className="rounded-xl border border-teal-200 bg-teal-50 p-5 shadow-sm">
                  <h3 className="mb-2 text-sm font-semibold text-teal-900">From the X-ray report</h3>
                  <dl className="grid grid-cols-2 gap-2 text-sm">
                    <dt className="text-teal-700">Side</dt>
                    <dd className="text-right font-medium capitalize text-teal-900">
                      {String(reportFindings.affected_side ?? "—")}
                    </dd>
                    <dt className="text-teal-700">Affected area</dt>
                    <dd className="text-right font-medium capitalize text-teal-900">
                      {String(
                        reportFindings.specific_structure?.replace(/_/g, " ") ??
                          reportFindings.sub_region?.replace(/_/g, " ") ??
                          reportFindings.affected_region ??
                          "—"
                      )}
                    </dd>
                    <dt className="text-teal-700">Severity</dt>
                    <dd className="text-right font-medium capitalize text-teal-900">
                      {String(reportFindings.severity ?? "—")}
                    </dd>
                    <dt className="text-teal-700">Condition</dt>
                    <dd className="text-right font-medium capitalize text-teal-900">
                      {String(reportFindings.condition_label ?? "—")}
                    </dd>
                  </dl>
                  {(reportFindings.restrictions?.length ?? 0) > 0 && (
                    <p className="mt-2 text-xs font-medium text-amber-700">
                      Precautions:{" "}
                      {reportFindings
                        .restrictions!.map((r) => r.restriction.replace(/_/g, " "))
                        .join(", ")}
                    </p>
                  )}
                  {typeof reportFindings.summary === "string" && reportFindings.summary && (
                    <p className="mt-3 text-sm text-teal-900">{reportFindings.summary}</p>
                  )}
                </div>
              )}

              {analysis.regions.length > 0 && (
                <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
                  <h3 className="mb-2 text-sm font-semibold text-slate-900">Detected regions</h3>
                  <ul className="space-y-1.5 text-sm">
                    {analysis.regions.map((r) => (
                      <li key={r.id} className="flex justify-between text-slate-600">
                        <span>
                          {r.label} <span className="text-slate-400">({r.region_type})</span>
                        </span>
                        <span className="font-medium text-slate-800">
                          {Math.round(r.confidence * 100)}% · {r.detection_method}
                        </span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              <Link
                href={`/report/${analysis.id}`}
                className="block w-full rounded-lg bg-teal-600 px-4 py-2 text-center text-sm font-semibold text-white hover:bg-teal-700"
              >
                View rehabilitation plan & report
              </Link>
            </>
          )}

          <DisclaimerBanner />
        </div>
      </div>
    </div>
  );
}
