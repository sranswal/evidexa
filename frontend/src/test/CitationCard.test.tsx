import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { MemoryRouter } from "react-router-dom";
import { CitationCard } from "../components/assistant/CitationCard";
import type { EvidenceCitation } from "../types/api";

describe("CitationCard Component", () => {
  const baseCitation: EvidenceCitation = {
    citation_id: "[E-1]",
    case_id: "case-999",
    document_id: "doc-123",
    document_title: "invoice_vendor_42.pdf",
    evidence_id: "ev-node-1",
    finding_id: "find-42",
    entity_id: null,
    relationship_id: null,
    page_number: 3,
    bounding_box: { x: 100, y: 150, width: 300, height: 200 },
    source_subsystem: "forensics",
    relevant_text: "Hidden stream dictionary mismatch detected on trailer.",
    target_route: "/cases/case-999/documents/doc-123/examine",
  };

  it("renders citation label, document title, and relevant text", () => {
    render(
      <MemoryRouter>
        <CitationCard citation={baseCitation} />
      </MemoryRouter>
    );

    expect(screen.getByText("[E-1]")).toBeInTheDocument();
    expect(screen.getByText("invoice_vendor_42.pdf")).toBeInTheDocument();
    expect(screen.getByText("p. 3")).toBeInTheDocument();
    expect(
      screen.getByText('"Hidden stream dictionary mismatch detected on trailer."')
    ).toBeInTheDocument();
  });

  it("renders as clickable link when target_route is provided", () => {
    render(
      <MemoryRouter>
        <CitationCard citation={baseCitation} />
      </MemoryRouter>
    );

    const link = screen.getByRole("link");
    expect(link).toHaveAttribute(
      "href",
      "/cases/case-999/documents/doc-123/examine"
    );
  });

  it("renders without link when target_route is null", () => {
    const unlinkedCitation: EvidenceCitation = {
      ...baseCitation,
      target_route: null,
    };

    render(
      <MemoryRouter>
        <CitationCard citation={unlinkedCitation} />
      </MemoryRouter>
    );

    expect(screen.queryByRole("link")).toBeNull();
    expect(screen.getByText("[E-1]")).toBeInTheDocument();
  });

  it("displays subsystem badge with proper label", () => {
    render(
      <MemoryRouter>
        <CitationCard
          citation={{ ...baseCitation, source_subsystem: "consistency" }}
        />
      </MemoryRouter>
    );

    expect(screen.getByText("consistency")).toBeInTheDocument();
  });
});
