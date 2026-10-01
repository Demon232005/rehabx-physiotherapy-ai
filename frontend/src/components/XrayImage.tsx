"use client";

import { useEffect, useState } from "react";
import { API_BASE, getToken } from "@/lib/api";

interface XrayImageProps {
  uploadId: string;
  alt?: string;
  className?: string;
  onLoad?: (naturalWidth: number, naturalHeight: number) => void;
}

export default function XrayImage({ uploadId, alt, className, onLoad }: XrayImageProps) {
  const [src, setSrc] = useState<string | null>(null);
  const [error, setError] = useState(false);
  const [notFound, setNotFound] = useState(false);

  useEffect(() => {
    let objectUrl: string | null = null;
    let cancelled = false;

    async function load() {
      try {
        const token = getToken();
        const res = await fetch(`${API_BASE}/uploads/${uploadId}/image`, {
          headers: token ? { Authorization: `Bearer ${token}` } : {},
          cache: "force-cache",
        });
        if (res.status === 404) {
          if (!cancelled) setNotFound(true);
          return;
        }
        if (!res.ok) throw new Error(`image fetch failed: ${res.status}`);
        const blob = await res.blob();
        objectUrl = URL.createObjectURL(blob);
        if (!cancelled) setSrc(objectUrl);
      } catch {
        if (!cancelled) setError(true);
      }
    }

    load();
    return () => {
      cancelled = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [uploadId]);

  if (notFound) {
    return (
      <div className="flex items-center justify-center rounded-lg border border-dashed border-slate-300 bg-slate-100 p-10 text-sm text-slate-500">
        No X-ray image was uploaded (report-based analysis)
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center justify-center rounded-lg border border-dashed border-slate-300 bg-slate-100 p-10 text-sm text-slate-500">
        Unable to load X-ray image
      </div>
    );
  }

  if (!src) {
    return (
      <div className="flex items-center justify-center rounded-lg border border-slate-200 bg-slate-100 p-10 text-sm text-slate-400">
        Loading X-ray…
      </div>
    );
  }

  return (
    // Blob URL from an authenticated fetch; next/image cannot optimize blob: URLs.
    // eslint-disable-next-line @next/next/no-img-element
    <img
      src={src}
      alt={alt ?? "Hand X-ray"}
      className={className ?? "h-auto w-full rounded-lg"}
      onLoad={(e) => {
        const el = e.currentTarget;
        if (onLoad) onLoad(el.naturalWidth, el.naturalHeight);
      }}
    />
  );
}
