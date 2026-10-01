import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import ExerciseAnimation from "@/components/ExerciseAnimation";

describe("ExerciseAnimation", () => {
  const knownSlugs = [
    "finger-flexion",
    "finger-extension",
    "finger-spreading",
    "wrist-flexion",
    "wrist-extension",
    "wrist-circumduction",
    "grip-strength",
    "thumb-opposition",
    "forearm-pronation",
    "forearm-supination",
  ];

  it.each(knownSlugs)("renders SVG for '%s'", (slug) => {
    const { container } = render(<ExerciseAnimation slug={slug} />);
    const svg = container.querySelector("svg");
    expect(svg).toBeInTheDocument();
  });

  it("renders fallback GenericHand for unknown slug", () => {
    const { container } = render(
      <ExerciseAnimation slug="unknown-exercise" />,
    );
    const svg = container.querySelector("svg");
    expect(svg).toBeInTheDocument();
    // GenericHand should still render (no crash)
    const lines = svg!.querySelectorAll("line");
    expect(lines.length).toBeGreaterThan(0);
  });

  it("displays custom label when provided", () => {
    render(<ExerciseAnimation slug="finger-flexion" label="Bend fingers" />);
    expect(screen.getByText("Bend fingers")).toBeInTheDocument();
  });

  it("displays default label when no label is provided", () => {
    render(<ExerciseAnimation slug="finger-flexion" />);
    expect(screen.getByText("Follow instructions")).toBeInTheDocument();
  });

  it("renders style element for known slug", () => {
    const { container } = render(
      <ExerciseAnimation slug="finger-flexion" />,
    );
    const style = container.querySelector("style");
    expect(style).toBeInTheDocument();
  });

  it("does not render style element for unknown slug", () => {
    const { container } = render(
      <ExerciseAnimation slug="unknown-exercise" />,
    );
    const style = container.querySelector("style");
    expect(style).not.toBeInTheDocument();
  });
});
