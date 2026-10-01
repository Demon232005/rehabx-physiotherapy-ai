import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import type { ProgressOut } from "@/lib/types";

vi.mock("recharts", () => ({
  ResponsiveContainer: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="responsive-container">{children}</div>
  ),
  LineChart: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="line-chart">{children}</div>
  ),
  Line: () => null,
  XAxis: () => null,
  YAxis: () => null,
  CartesianGrid: () => null,
  Tooltip: () => null,
  Legend: () => null,
}));

const ProgressCharts = (await import("@/components/ProgressCharts")).default;

function makeProgress(overrides: Partial<ProgressOut>): ProgressOut {
  return {
    id: "1",
    analysis_id: null,
    date: "2025-01-15",
    pain_level: null,
    grip_strength_kg: null,
    range_of_motion_deg: null,
    self_reported_improvement: null,
    notes: null,
    ...overrides,
  };
}

describe("ProgressCharts", () => {
  it("shows empty state when data is empty", () => {
    render(<ProgressCharts data={[]} />);
    expect(screen.getByText("No data available yet.")).toBeInTheDocument();
  });

  it("shows empty state when data has null values", () => {
    const data = [makeProgress({ pain_level: null, grip_strength_kg: null })];
    render(<ProgressCharts data={data} />);
    expect(screen.getByText("No data available yet.")).toBeInTheDocument();
  });

  it("renders chart for pain level data", () => {
    const data = [makeProgress({ pain_level: 7 })];
    render(<ProgressCharts data={data} />);
    expect(screen.getByText("Pain Level")).toBeInTheDocument();
    expect(screen.getByTestId("line-chart")).toBeInTheDocument();
  });

  it("renders chart for grip strength data", () => {
    const data = [makeProgress({ grip_strength_kg: 25 })];
    render(<ProgressCharts data={data} />);
    expect(screen.getByText("Grip Strength")).toBeInTheDocument();
  });

  it("renders chart for AI-Measured ROM data", () => {
    const data = [makeProgress({ range_of_motion_deg: 90 })];
    render(<ProgressCharts data={data} />);
    expect(screen.getByText("AI-Measured ROM")).toBeInTheDocument();
  });

  it("renders chart for self-reported improvement data", () => {
    const data = [makeProgress({ self_reported_improvement: 60 })];
    render(<ProgressCharts data={data} />);
    expect(screen.getByText("Self-Reported Improvement")).toBeInTheDocument();
  });

  it("renders multiple charts when multiple metrics exist", () => {
    const data = [
      makeProgress({
        pain_level: 5,
        grip_strength_kg: 20,
        range_of_motion_deg: 80,
      }),
    ];
    render(<ProgressCharts data={data} />);
    expect(screen.getByText("Pain Level")).toBeInTheDocument();
    expect(screen.getByText("Grip Strength")).toBeInTheDocument();
    expect(screen.getByText("AI-Measured ROM")).toBeInTheDocument();
  });
});
