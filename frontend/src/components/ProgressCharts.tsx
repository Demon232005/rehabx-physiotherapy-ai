"use client";

import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import type { ProgressOut } from "@/lib/types";

function formatDate(dateStr: string) {
  const d = new Date(dateStr);
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

interface ChartCardProps {
  title: string;
  data: { date: string; value: number }[];
  unit: string;
  color: string;
  reversed?: boolean;
}

function ChartCard({ title, data, unit, color, reversed }: ChartCardProps) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
      <h3 className="mb-3 text-sm font-semibold text-slate-700">{title}</h3>
      <ResponsiveContainer width="100%" height={220}>
        <LineChart data={data} margin={{ top: 5, right: 20, bottom: 5, left: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
          <XAxis
            dataKey="date"
            tickFormatter={formatDate}
            tick={{ fontSize: 11, fill: "#64748b" }}
            tickLine={false}
            axisLine={false}
          />
          <YAxis
            domain={reversed ? [10, 0] : ["auto", "auto"]}
            tick={{ fontSize: 11, fill: "#64748b" }}
            tickLine={false}
            axisLine={false}
            unit={unit}
            width={45}
          />
          <Tooltip
            labelFormatter={(label) => formatDate(label as string)}
            formatter={(value) => [`${value}${unit}`, title]}
            contentStyle={{
              borderRadius: "0.5rem",
              border: "1px solid #e2e8f0",
              fontSize: "0.75rem",
            }}
          />
          <Line
            type="monotone"
            dataKey="value"
            stroke={color}
            strokeWidth={2.5}
            dot={{ r: 3, fill: color }}
            activeDot={{ r: 5 }}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

interface ProgressChartsProps {
  data: ProgressOut[];
}

export default function ProgressCharts({ data }: ProgressChartsProps) {
  if (!data || data.length === 0) {
    return (
      <div className="rounded-xl border border-dashed border-slate-300 bg-white p-8 text-center text-sm text-slate-500">
        No data available yet.
      </div>
    );
  }

  const sorted = [...data].sort(
    (a, b) => new Date(a.date).getTime() - new Date(b.date).getTime(),
  );

  const painData = sorted
    .filter((p) => p.pain_level != null)
    .map((p) => ({ date: p.date, value: p.pain_level! }));

  const gripData = sorted
    .filter((p) => p.grip_strength_kg != null)
    .map((p) => ({ date: p.date, value: p.grip_strength_kg! }));

  const romData = sorted
    .filter((p) => p.range_of_motion_deg != null)
    .map((p) => ({ date: p.date, value: p.range_of_motion_deg! }));

  const improvementData = sorted
    .filter((p) => p.self_reported_improvement != null)
    .map((p) => ({ date: p.date, value: p.self_reported_improvement! }));

  // Auto-logged from completed exercise sessions (AI-measured).
  const formData = sorted
    .filter((p) => p.form_score != null)
    .map((p) => ({ date: p.date, value: p.form_score! }));

  const repsData = sorted
    .filter((p) => p.reps_completed != null)
    .map((p) => ({ date: p.date, value: p.reps_completed! }));

  const hasAnyData =
    painData.length > 0 ||
    gripData.length > 0 ||
    romData.length > 0 ||
    improvementData.length > 0 ||
    formData.length > 0 ||
    repsData.length > 0;

  if (!hasAnyData) {
    return (
      <div className="rounded-xl border border-dashed border-slate-300 bg-white p-8 text-center text-sm text-slate-500">
        No data available yet.
      </div>
    );
  }

  return (
    <div className="grid gap-4 sm:grid-cols-2">
      {painData.length > 0 && (
        <ChartCard
          title="Pain Level"
          data={painData}
          unit="/10"
          color="#0d9488"
          reversed
        />
      )}
      {gripData.length > 0 && (
        <ChartCard
          title="Grip Strength"
          data={gripData}
          unit="kg"
          color="#059669"
        />
      )}
      {romData.length > 0 && (
        <ChartCard
          title="AI-Measured ROM"
          data={romData}
          unit="°"
          color="#d97706"
        />
      )}
      {formData.length > 0 && (
        <ChartCard
          title="AI Form Score"
          data={formData}
          unit="%"
          color="#7c3aed"
        />
      )}
      {repsData.length > 0 && (
        <ChartCard
          title="Reps Completed"
          data={repsData}
          unit=""
          color="#2563eb"
        />
      )}
      {improvementData.length > 0 && (
        <ChartCard
          title="Self-Reported Improvement"
          data={improvementData}
          unit="%"
          color="#e11d48"
        />
      )}
    </div>
  );
}
