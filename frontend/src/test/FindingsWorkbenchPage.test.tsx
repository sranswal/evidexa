import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { FindingsWorkbenchPage } from "../pages/FindingsWorkbenchPage";
import { CaseProvider } from "../context/CaseContext";
import { casesApi } from "../api/cases";
import { findingsApi } from "../api/findings";
import { dossiersApi } from "../api/dossiers";
import type { Case, AggregatedFinding } from "../types/api";

vi.mock("../api/cases", () => ({
  casesApi: {
    getCase: vi.fn(),
  },
}));

vi.mock("../api/findings", () => ({
  findingsApi: {
    getAggregatedFindings: vi.fn(),
    recordFindingReview: vi.fn(),
    listFindingReviews: vi.fn(),
  },
}));

vi.mock("../api/dossiers", () => ({
  dossiersApi: {
    listDossiers: vi.fn(),
    getDossier: vi.fn(),
    generateDossier: vi.fn(),
    finalizeDossier: vi.fn(),
    getExportUrl: vi.fn(),
  },
}));

const mockCase: Case = {
  id: "case-xyz",
  case_reference: "CASE-20261110-001",
  title: "Operation Cross-Check",
  description: "Cross-document forensic consistency and entity mapping.",
  status: "ACTIVE",
  created_at: "2026-11-10T00:00:00Z",
  updated_at: "2026-11-10T00:00:00Z",
  created_by: "agent-forensic",
  metadata: {},
};

const mockFindings: AggregatedFinding[] = [
  {
    id: "f-1",
    case_id: "case-xyz",
    title: "Invoice vs PO Value Discrepancy",
    description: "Difference of $6,500.00 observed across document records.",
    category: "CROSS_DOCUMENT_INCONSISTENCY",
    severity: "HIGH",
    confidence: 0.95,
    evidentiary_classification: "ANALYTICAL_INTERPRETATION",
    source_type: "CONSISTENCY_FINDING",
    explanation: "Rule evaluated line item aggregates.",
    limitations: ["Tax rounding divergence may account for sub-dollar differences."],
    affected_document_ids: ["doc-1", "doc-2"],
    affected_entity_ids: [],
    locations: [],
    supporting_evidence_ids: [],
    contradicting_evidence_ids: [],
    is_reviewed: false,
    review_status: "UNREVIEWED",
    review_history: [],
    created_at: "2026-11-10T00:00:00Z",
  },
  {
    id: "f-2",
    case_id: "case-xyz",
    title: "Font Substitution in Vendor Address",
    description: "Embedded Helvetica typeface replaced by synthetic Arial glyphs.",
    category: "VISUAL_ANOMALY",
    severity: "MEDIUM",
    confidence: 0.82,
    evidentiary_classification: "OBSERVED_FACT",
    source_type: "FORENSIC_FINDING",
    explanation: "Font descriptor mismatch in PDF content stream.",
    limitations: ["Virtual printer print-to-PDF drivers frequently replace font subsets."],
    affected_document_ids: ["doc-1"],
    affected_entity_ids: [],
    locations: [],
    supporting_evidence_ids: [],
    contradicting_evidence_ids: [],
    is_reviewed: true,
    review_status: "CONFIRMED_OBSERVATION",
    review_history: [],
    created_at: "2026-11-10T00:00:00Z",
  },
];

function renderWorkbench() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
    },
  });

  return render(
    <QueryClientProvider client={queryClient}>
      <CaseProvider>
        <MemoryRouter initialEntries={["/cases/case-xyz/findings"]}>
          <Routes>
            <Route path="/cases/:caseId/findings" element={<FindingsWorkbenchPage />} />
          </Routes>
        </MemoryRouter>
      </CaseProvider>
    </QueryClientProvider>
  );
}

describe("FindingsWorkbenchPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(casesApi.getCase).mockResolvedValue(mockCase);
    vi.mocked(findingsApi.getAggregatedFindings).mockResolvedValue(mockFindings);
    vi.mocked(dossiersApi.listDossiers).mockResolvedValue([]);
  });

  it("renders page title, KPIs, and findings table", async () => {
    renderWorkbench();

    await waitFor(() => {
      expect(screen.getByText("Unified Findings & Investigator Review")).toBeInTheDocument();
      expect(screen.getByText("CASE-20261110-001")).toBeInTheDocument();
      expect(screen.getAllByText("Invoice vs PO Value Discrepancy").length).toBeGreaterThan(0);
      expect(screen.getByText("Font Substitution in Vendor Address")).toBeInTheDocument();
    });

    // Check KPI metrics
    expect(screen.getByText(/Total Findings/i)).toBeInTheDocument();
    expect(screen.getByText(/Observed Facts/i)).toBeInTheDocument();
    expect(screen.getByText(/Automated Signals/i)).toBeInTheDocument();
    expect(screen.getAllByText(/Interpretations/i).length).toBeGreaterThan(0);
    expect(screen.getByText(/Investigator Asserted/i)).toBeInTheDocument();
    expect(screen.getAllByText(/Review Status/i).length).toBeGreaterThan(0);
  });

  it("filters findings when search input is used", async () => {
    renderWorkbench();

    await waitFor(() => {
      expect(screen.getAllByText("Invoice vs PO Value Discrepancy").length).toBeGreaterThan(0);
    });

    const searchInput = screen.getByPlaceholderText(/Search findings by title/i);
    fireEvent.change(searchInput, { target: { value: "Font Substitution" } });

    await waitFor(() => {
      expect(screen.queryByText("Invoice vs PO Value Discrepancy")).not.toBeInTheDocument();
      expect(screen.getAllByText("Font Substitution in Vendor Address").length).toBeGreaterThan(0);
    });
  });

  it("opens review modal when clicking review button in detail panel", async () => {
    renderWorkbench();

    await waitFor(() => {
      expect(screen.getAllByText("Invoice vs PO Value Discrepancy").length).toBeGreaterThan(0);
    });

    // The first item is auto-selected into the detail panel
    const reviewButton = screen.getByRole("button", { name: /Adjudicate \/ Record Investigator Review/i });
    fireEvent.click(reviewButton);

    await waitFor(() => {
      expect(screen.getByText("Record Investigator Review Adjudication")).toBeInTheDocument();
    });

    // Close review modal
    const cancelButton = screen.getByRole("button", { name: /Cancel/i });
    fireEvent.click(cancelButton);

    await waitFor(() => {
      expect(screen.queryByText("Record Investigator Review Adjudication")).not.toBeInTheDocument();
    });
  });

  it("opens dossier readiness drawer when button is clicked", async () => {
    renderWorkbench();

    await waitFor(() => {
      expect(screen.getByText("Unified Findings & Investigator Review")).toBeInTheDocument();
    });

    const dossierButton = screen.getByRole("button", { name: /Dossier Readiness/i });
    fireEvent.click(dossierButton);

    await waitFor(() => {
      expect(screen.getByText(/Investigation Dossier Workbench/i)).toBeInTheDocument();
    });
  });

  it("renders error state when findings API fails and allows retry", async () => {
    vi.mocked(findingsApi.getAggregatedFindings).mockRejectedValueOnce(
      new Error("Database connection timeout")
    );

    renderWorkbench();

    await waitFor(() => {
      expect(screen.getByText(/Failed to Load Aggregated Findings/i)).toBeInTheDocument();
      expect(screen.getByText(/Database connection timeout/i)).toBeInTheDocument();
    });

    // Click retry
    const retryButton = screen.getByRole("button", { name: /Retry Query/i });
    fireEvent.click(retryButton);

    await waitFor(() => {
      expect(screen.getAllByText("Invoice vs PO Value Discrepancy").length).toBeGreaterThan(0);
    });
  });
});
