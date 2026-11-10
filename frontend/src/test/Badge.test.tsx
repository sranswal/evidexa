import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { StatusBadge } from "../components/ui/Badge";

describe("StatusBadge Accessibility & Semantics", () => {
  it("renders Case Status with text and semantic icon", () => {
    const { rerender } = render(<StatusBadge status="ACTIVE" type="case" />);
    expect(screen.getByText("ACTIVE")).toBeInTheDocument();

    rerender(<StatusBadge status="UNDER_REVIEW" type="case" />);
    expect(screen.getByText("UNDER REVIEW")).toBeInTheDocument();

    rerender(<StatusBadge status="ARCHIVED" type="case" />);
    expect(screen.getByText("ARCHIVED")).toBeInTheDocument();
  });

  it("renders Evidentiary Classification without color-alone communication", () => {
    const { rerender } = render(<StatusBadge status="CONFIRMED" type="evidentiary" />);
    expect(screen.getByText("CONFIRMED")).toBeInTheDocument();

    rerender(<StatusBadge status="CONTRADICTED" type="evidentiary" />);
    expect(screen.getByText("CONTRADICTED")).toBeInTheDocument();

    rerender(<StatusBadge status="CANDIDATE" type="evidentiary" />);
    expect(screen.getByText("CANDIDATE")).toBeInTheDocument();
  });

  it("renders Finding Severity badges", () => {
    const { rerender } = render(<StatusBadge status="CRITICAL" type="severity" />);
    expect(screen.getByText("CRITICAL")).toBeInTheDocument();

    rerender(<StatusBadge status="HIGH" type="severity" />);
    expect(screen.getByText("HIGH")).toBeInTheDocument();
  });
});
