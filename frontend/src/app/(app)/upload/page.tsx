"use client";

import { useRouter } from "next/navigation";
import { useRef, useState } from "react";
import { api } from "@/lib/api";
import type { AnalysisOut, ReportParsed, ReportFileParsedOut, UploadOut } from "@/lib/types";

export default function UploadPage() {
  const router = useRouter();
  const reportFileInput = useRef<HTMLInputElement>(null);

  const [side, setSide] = useState("right");
  const [region, setRegion] = useState("wrist");
  const [reportFile, setReportFile] = useState<File | null>(null);
  const [reportFileText, setReportFileText] = useState("");
  const [parsed, setParsed] = useState<ReportParsed | null>(null);
  const [parsing, setParsing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function onReportFileChange(f: File | undefined) {
    setError(null);
    setReportFile(f ?? null);
    setReportFileText("");
    setParsed(null);
    if (!f) return;
    setParsing(true);
    try {
      const form = new FormData();
      form.append("report_file", f);
      const res = await api<ReportFileParsedOut>(
        "/uploads/parse-report-file",
        { method: "POST", body: form },
        true
      );
      setReportFileText(res.text);
      setParsed(res.parsed);
      if (res.parsed.affected_side) setSide(res.parsed.affected_side);
      if (res.parsed.affected_region) setRegion(res.parsed.affected_region);
    } catch (e) {
      setParsed(null);
      setReportFile(null);
      setReportFileText("");
      setError(e instanceof Error ? e.message : "Could not read the report file");
      if (reportFileInput.current) reportFileInput.current.value = "";
    } finally {
      setParsing(false);
    }
  }

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!reportFile) {
      setError("Please upload the X-ray report file (PDF, image or text).");
      return;
    }
    setError(null);
    setBusy(true);
    try {
      const form = new FormData();
      form.append("report_file", reportFile);
      form.append("affected_side", side);
      form.append("affected_region", region);
      const upload = await api<UploadOut>("/uploads", { method: "POST", body: form }, true);

      // The report controls scope: only send an explicit override when the
      // user's selection differs from what was parsed from the report.
      const sideOverride = parsed?.affected_side !== side ? side : null;
      const regionOverride = parsed?.affected_region !== region ? region : null;
      const analysis = await api<AnalysisOut>(
        "/analyses",
        {
          method: "POST",
          body: JSON.stringify({
            upload_id: upload.id,
            affected_side: sideOverride,
            affected_region: regionOverride,
          }),
        },
        true
      );
      router.push(`/analyses/${analysis.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed");
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-900">New analysis</h1>
        <p className="text-sm text-slate-500">
          Upload the X-ray report file. The report is read automatically to identify which hand is
          affected, how severe it is, and what was found.
        </p>
      </div>

      <form onSubmit={onSubmit} className="space-y-6 rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        <div className="rounded-xl border border-slate-200 bg-slate-50 p-4">
          <label className="mb-2 block text-sm font-medium text-slate-700">
            X-ray report file <span className="text-rose-600">*</span>
          </label>
          <input
            ref={reportFileInput}
            type="file"
            accept=".txt,.md,.pdf,.png,.jpg,.jpeg"
            required
            onChange={(e) => onReportFileChange(e.target.files?.[0])}
            className="block w-full cursor-pointer rounded-lg border border-dashed border-slate-300 bg-white px-3 py-4 text-sm text-slate-600 file:mr-3 file:rounded-lg file:border-0 file:bg-teal-600 file:px-3 file:py-1.5 file:text-sm file:font-semibold file:text-white hover:file:bg-teal-700"
          />
          <p className="mt-1 text-xs text-slate-400">
            Upload the report as PDF, image (PNG/JPG) or text. Text is read automatically.
          </p>
          {reportFileText && (
            <details className="mt-2">
              <summary className="cursor-pointer text-xs font-medium text-teal-700">
                Text read from {reportFile?.name}
              </summary>
              <pre className="mt-1 max-h-32 overflow-auto rounded-lg bg-white p-2 text-xs leading-relaxed text-slate-600">
                {reportFileText}
              </pre>
            </details>
          )}
        </div>

        {parsing && <p className="text-xs text-slate-400">Reading report…</p>}
        {parsed && (
          <div className="rounded-lg bg-teal-50 px-3 py-2 text-xs text-teal-800">
            <span className="font-semibold">Detected from report:</span>{" "}
            {[
              parsed.affected_side ? `${parsed.affected_side} side` : null,
              parsed.specific_structure?.replace(/_/g, " ") ?? parsed.affected_region,
              parsed.severity ? `${parsed.severity} severity` : null,
              parsed.condition_label ?? null,
            ]
              .filter(Boolean)
              .join(" · ") || "Nothing recognized yet"}
          </div>
        )}
        {parsed && !parsed.affected_side && !parsed.affected_region && (
          <div className="rounded-lg border border-dashed border-amber-300 bg-amber-50 px-3 py-2 text-xs text-amber-800" role="alert">
            We couldn&apos;t confidently identify the affected body area from this report.
            Please review the text below and select the affected side and area manually.
          </div>
        )}

        <div className="grid gap-4 sm:grid-cols-2">
          <label className="block text-sm font-medium text-slate-700">
            Affected side
            <select
              value={side}
              onChange={(e) => setSide(e.target.value)}
              className="mt-1 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm outline-none focus:border-teal-500 focus:ring-2 focus:ring-teal-100"
            >
              <option value="left">Left</option>
              <option value="right">Right</option>
              <option value="bilateral">Bilateral</option>
            </select>
          </label>
          <label className="block text-sm font-medium text-slate-700">
            Affected region
            <select
              value={region}
              onChange={(e) => setRegion(e.target.value)}
              className="mt-1 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm outline-none focus:border-teal-500 focus:ring-2 focus:ring-teal-100"
            >
              <optgroup label="Shoulder & arm">
                <option value="shoulder">Shoulder</option>
                <option value="upper_arm">Upper arm</option>
              </optgroup>
              <optgroup label="Elbow & forearm">
                <option value="elbow">Elbow</option>
                <option value="forearm">Forearm</option>
              </optgroup>
              <optgroup label="Wrist & hand">
                <option value="wrist">Wrist</option>
                <option value="hand">Hand</option>
                <option value="thumb">Thumb</option>
                <option value="palm">Palm</option>
                <option value="fingers">Fingers</option>
              </optgroup>
            </select>
          </label>
        </div>

        {error && <div className="rounded-lg bg-rose-50 px-3 py-2 text-sm text-rose-700">{error}</div>}

        <button
          type="submit"
          disabled={busy || !reportFile}
          className="w-full rounded-lg bg-teal-600 px-4 py-2 text-sm font-semibold text-white hover:bg-teal-700 disabled:opacity-50"
        >
          {busy ? "Uploading and starting analysis…" : "Upload & analyze"}
        </button>
      </form>
    </div>
  );
}
