"use client";

import type { DetectedRegionOut } from "@/lib/types";

interface RegionOverlayProps {
  regions: DetectedRegionOut[];
  imageWidth: number;
  imageHeight: number;
}

const COLORS = ["#0ea5e9", "#f59e0b", "#ef4444", "#10b981", "#8b5cf6", "#ec4899"];

export default function RegionOverlay({ regions, imageWidth, imageHeight }: RegionOverlayProps) {
  if (imageWidth <= 0 || imageHeight <= 0 || regions.length === 0) return null;

  return (
    <div className="pointer-events-none absolute inset-0">
      {regions.map((r, i) => {
        if (r.bbox_x == null || r.bbox_y == null || r.bbox_w == null || r.bbox_h == null) return null;
        const color = COLORS[i % COLORS.length];
        const left = (r.bbox_x / imageWidth) * 100;
        const top = (r.bbox_y / imageHeight) * 100;
        const width = (r.bbox_w / imageWidth) * 100;
        const height = (r.bbox_h / imageHeight) * 100;
        return (
          <div
            key={r.id}
            className="absolute border-2"
            style={{
              left: `${left}%`,
              top: `${top}%`,
              width: `${width}%`,
              height: `${height}%`,
              borderColor: color,
            }}
            title={`${r.label} (${r.region_type}) — ${Math.round(r.confidence * 100)}%`}
          >
            <span
              className="absolute -top-6 left-0 rounded px-1 text-[10px] font-semibold text-white"
              style={{ backgroundColor: color }}
            >
              {r.label}
            </span>
          </div>
        );
      })}
    </div>
  );
}
