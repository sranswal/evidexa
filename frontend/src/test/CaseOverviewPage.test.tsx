import { render, screen, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { CaseOverviewPage } from "../pages/CaseOverviewPage";
import { CaseProvider } from "../context/CaseContext";
import { casesApi } from "../api/cases";
import type { Case, DocumentItem, AggregatedFinding } from "../types/api";

const mockCase: Case = {
  id: "case-999",
  case_reference: "CASE-20261109-999",
  title: "Target Acquisition Due Diligence",
  description: "Comprehensive verification of financial statements.",
  status: "ACTIVE",
  created_at: "2026-11-09T08:00:00Z",
  updated_at: "2026-11-09T09:00:00Z",
  created_by: "lead-forensic",
  metadata: {},
};

const mockDocs: DocumentItem[] = [
  {
    id: "doc-1",
    case_id: "case-999",
    original_filename: "invoice_vendor_a.pdf",
    media_type: "application/pdf",
    file_extension: ".pdf",
    file_size_bytes: 1048576,
    sha256: "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    storage_key: "case-999/doc-1.pdf",
    page_count: 2,
    document_type: "INVOICE",
    ingestion_status: "PARSED",
    created_at: "2026-11-09T08:05:00Z",
    created_by: "lead-forensic",
    metadata: {},
  },
];

const mockFindings: AggregatedFinding[] = [
  {
    id: "finding-1",
    case_id: "case-999",
    finding_source: "FORENSIC",
    source_finding_id: "raw-find-1",
    document_id: "doc-1",
    document_ids: ["doc-1"],
    severity: "CRITICAL",
    title: "Font Inconsistency in Total Amount",
    description: "Mismatch in PDF font subset tags indicating glyph alteration.",
    rule_id: "PDF-STRUCT-003",
    confidence_score: 0.95,
    evidentiary_status: "CONTRADICTED",
    active_review_decision: null,
    review_count: 0,
    created_at: "2026-11-09T08:10:00Z",
    updated_at: "2026-11-09T08:10:00Z",
  },
];

describe("CaseOverviewPage Component", () => {
  let queryClient: QueryClient;

  beforeEach(() => {
    vi.restoreAllMocks();
    queryClient = new QueryClient({
      defaultOptions: {
        queries: { retry: false },
      },
    });
  });

  it("renders case overview dashboard with real backend data", async () => {
    vi.spyOn(casesApi, "getCase").mockResolvedValue(mockCase);
    vi.spyOn(casesApi, "listCaseDocuments").mockResolvedValue({
      items: mockDocs,
      total: 1,
      skip: 0,
      limit: 10,
    });
    vi.spyOn(casesApi, "listAggregatedFindings").mockResolvedValue(mockFindings);
    vi.spyOn(casesApi, "listRelationships").mockResolvedValue({
      ontology_version: "2.0",
      items: [],
      total: 0,
      skip: 0,
      limit: 10,
    });
    vi.spyOn(casesApi, "listConsistencyRuns").mockResolvedValue([]);
    vi.spyOn(casesApi, "listDossiers").mockResolvedValue([]);

    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={["/cases/case-999/overview"]}>
          <Routes>
            <Route
              path="/cases/:caseId/overview"
              element={
                <CaseProvider>
                  <CaseOverviewPage />
                </CaseProvider>
              }
            />
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>
    );

    await waitFor(() => {
      expect(screen.getByText("Target Acquisition Due Diligence")).toBeInTheDocument();
      expect(screen.getByText("CASE-20261109-999")).toBeInTheDocument();
    });

    // Check Metrics Grid
    expect(screen.getByText("Documents")).toBeInTheDocument();
    expect(screen.getByText("1 file registered")).toBeInTheDocument();

    // Check Document in table
    expect(screen.getByText("invoice_vendor_a.pdf")).toBeInTheDocument();

    // Check Finding
    expect(screen.getByText("Font Inconsistency in Total Amount")).toBeInTheDocument();
  });
});
