import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import DisclaimerBanner from "@/components/DisclaimerBanner";

describe("DisclaimerBanner", () => {
  it("renders the default disclaimer text", () => {
    render(<DisclaimerBanner />);
    expect(
      screen.getByText(/AI-assisted research\/prototype system/),
    ).toBeInTheDocument();
  });

  it("renders the Disclaimer label", () => {
    render(<DisclaimerBanner />);
    expect(screen.getByText(/Disclaimer:/)).toBeInTheDocument();
  });

  it("renders custom text when provided", () => {
    render(<DisclaimerBanner text="Custom warning" />);
    expect(screen.getByText("Custom warning")).toBeInTheDocument();
  });

  it("does not render default text when custom text is provided", () => {
    render(<DisclaimerBanner text="Custom warning" />);
    expect(
      screen.queryByText(/AI-assisted research\/prototype system/),
    ).not.toBeInTheDocument();
  });

  it("has amber styling", () => {
    const { container } = render(<DisclaimerBanner />);
    const div = container.firstChild as HTMLElement;
    expect(div.className).toContain("bg-amber-50");
    expect(div.className).toContain("border-amber-200");
  });
});
