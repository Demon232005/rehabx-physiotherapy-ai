"use client";

import { useEffect, useState } from "react";
import { API_BASE, getToken } from "@/lib/api";

/** Shows the original uploaded X-ray report file (image preview,
 *  embedded PDF or plain text) fetched with the user's bearer token. */
export default function ReportFileView({ uploadId }: { uploadId: string }) {
  const [objectUrl, setObjectUrl] = useState<string | null>(null);
  const [mediaType, setMediaType] = useState<string>("");
  const [textBody, setTextBody] = useState<string>("");
  const [fileName, setFileName] = useState<string>("");
  const [state, setState] = useState<"loading" | "ready" | "missing" | "error">("loading");

  useEffect(() => {
    let objectUrlToRevoke: string | null = null;
    let cancelled = false;

    async function load() {
      try {
        const token = getToken();
        const res = await fetch(`${API_BASE}/uploads/${uploadId}/report-file`, {
          headers: token ? { Authorization: `Bearer ${token}` } : {},
        });
        if (res.status === 404) {
          if (!cancelled) setState("missing");
          return;
        }
        if (!res.ok) throw new Error(`report fetch failed: ${res.status}`);

        const type = res.headers.get("Content-Type") ?? "application/octet-stream";
        const disposition = res.headers.get("Content-Disposition") ?? "";
        const nameMatch = /filename="?([^";]+)"?/.exec(disposition);
        setFileName(nameMatch?.[1] ?? "report");
        setMediaType(type);

        if (type.startsWith("image/") || type === "application/pdf") {
          const blob = await res.blob();
          objectUrlToRevoke = URL.createObjectURL(blob);
          if (!cancelled) setObjectUrl(objectUrlToRevoke);
        } else {
          const body = await res.text();
          if (!cancelled) setTextBody(body);
        }
        if (!cancelled) setState("ready");
      } catch {
        if (!cancelled) setState("error");
      }
    }

    load();
    return () => {
      cancelled = true;
      if (objectUrlToRevoke) URL.revokeObjectURL(objectUrlToRevoke);
    };
  }, [uploadId]);

  if (state === "loading") {
    return (
      <div className="rounded-xl border border-slate-200 bg-white p-5 text-sm text-slate-400">
        Loading report…
      </div>
    );
  }
  if (state !== "ready") {
    return (
      <div className="rounded-xl border border-dashed border-slate-300 bg-slate-50 p-5 text-sm text-slate-500">
        {state === "missing"
          ? "The original report file is not available for this analysis."
          : "Unable to load the report file."}
      </div>
    );
  }

  return (
    <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
      <h3 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-500">
        Uploaded X-ray report{fileName ? ` — ${fileName}` : ""}
      </h3>

      {mediaType.startsWith("image/") && objectUrl && (
        // Blob URL from an authenticated fetch; next/image cannot optimize blob: URLs.
        // eslint-disable-next-line @next/next/no-img-element
        <img
          src={objectUrl}
          alt="Uploaded X-ray report"
          className="max-h-[480px] w-auto rounded-lg border border-slate-200"
        />
      )}

      {mediaType === "application/pdf" && objectUrl && (
        <iframe
          src={objectUrl}
          title="Uploaded X-ray report PDF"
          className="h-[480px] w-full rounded-lg border border-slate-200"
        />
      )}

      {(mediaType.startsWith("text/") || (!objectUrl && textBody)) && (
        <pre className="max-h-72 overflow-auto whitespace-pre-wrap rounded-lg bg-slate-50 p-3 text-xs leading-relaxed text-slate-700">
          {textBody}
        </pre>
      )}
    </div>
  );
}
