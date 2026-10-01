import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import StatusBadge from "@/components/StatusBadge";

describe("StatusBadge", () => {
  it("renders the status text", () => {
    render(<StatusBadge status="completed" />);
    expect(screen.getByText("completed")).toBeInTheDocument();
  });

  it("applies emerald styles for completed", () => {
    render(<StatusBadge status="completed" />);
    const badge = screen.getByText("completed");
    expect(badge.className).toContain("bg-emerald-100");
    expect(badge.className).toContain("text-emerald-700");
  });

  it("applies sky styles for processing", () => {
    render(<StatusBadge status="processing" />);
    const badge = screen.getByText("processing");
    expect(badge.className).toContain("bg-sky-100");
    expect(badge.className).toContain("text-sky-700");
  });

  it("applies rose styles for failed", () => {
    render(<StatusBadge status="failed" />);
    const badge = screen.getByText("failed");
    expect(badge.className).toContain("bg-rose-100");
    expect(badge.className).toContain("text-rose-700");
  });

  it("applies default slate styles for uploaded", () => {
    render(<StatusBadge status="uploaded" />);
    const badge = screen.getByText("uploaded");
    expect(badge.className).toContain("bg-slate-100");
  });

  it("replaces underscores with spaces", () => {
    render(<StatusBadge status="in_progress" />);
    expect(screen.getByText("in progress")).toBeInTheDocument();
  });

  it("applies default styles for unknown status", () => {
    render(<StatusBadge status="custom_status" />);
    const badge = screen.getByText("custom status");
    expect(badge.className).toContain("bg-slate-100");
  });
});
