import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { EpistemicNoticeBanner } from "../components/findings/EpistemicNoticeBanner";
import { FindingsFilterToolbar, type FindingsFilterState } from "../components/findings/FindingsFilterToolbar";
import { FindingsTable } from "../components/findings/FindingsTable";
import { FindingDetailPanel } from "../components/findings/FindingDetailPanel";
import { FindingReviewModal } from "../components/findings/FindingReviewModal";
import { DossierReadinessDrawer } from "../components/findings/DossierReadinessDrawer";
import { findingsApi } from "../api/findings";
import { dossiersApi } from "../api/dossiers";
import type { AggregatedFinding, InvestigationDossier } from "../types/api";

vi.mock("../api/findings", () => ({
  findingsApi: {
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
    getExportUrl: vi.fn((caseId, id, format) => `/api/v1/cases/${caseId}/dossiers/${id}/export/${format}`),
  },
}));

const mockFindings: AggregatedFinding[] = [
  {
    id: "finding-001",
    case_id: "case-xyz",
    title: "Invoice and PO Total Discrepancy",
    description: "Invoice INV-2024-001 declares $45,000.00 while Purchase Order PO-9801 declares $38,500.00.",
    category: "CROSS_DOCUMENT_INCONSISTENCY",
    severity: "HIGH",
    confidence: 0.95,
    evidentiary_classification: "ANALYTICAL_INTERPRETATION",
    source_type: "CONSISTENCY_FINDING",
    explanation: "Rule compared parsed net amount across matched purchase order and vendor invoice.",
    limitations: ["OCR rounding error possible if cent separator is smeared."],
    affected_document_ids: ["doc-1", "doc-2"],
    affected_entity_ids: ["ent-vendor"],
    locations: [
      {
        document_id: "doc-1",
        page_number: 1,
        field_name: "total_amount",
      },
    ],
    supporting_evidence_ids: ["ev-1"],
    contradicting_evidence_ids: ["ev-2"],
    is_reviewed: false,
    review_status: "UNREVIEWED",
    review_history: [],
    created_at: "2026-11-10T00:00:00Z",
  },
  {
    id: "finding-002",
    case_id: "case-xyz",
    title: "Signature Area ELA Discontinuity",
    description: "High frequency variance detected in the signature block on page 2.",
    category: "VISUAL_ANOMALY",
    severity: "CRITICAL",
    confidence: 0.88,
    evidentiary_classification: "AUTOMATED_INDICATOR",
    source_type: "FORENSIC_FINDING",
    explanation: "Error Level Analysis shows compression artifact discrepancy.",
    limitations: ["Rescaling or multi-pass JPEG compression can produce false indicators."],
    affected_document_ids: ["doc-1"],
    affected_entity_ids: [],
    locations: [],
    supporting_evidence_ids: [],
    contradicting_evidence_ids: [],
    is_reviewed: true,
    review_status: "CONFIRMED_OBSERVATION",
    review_history: [
      {
        id: "rev-1",
        case_id: "case-xyz",
        finding_id: "finding-002",
        reviewer_id: "investigator-1",
        action: "CONFIRM_OBSERVATION",
        comment: "Microscopic artifact review confirmed pixel level edge discontinuity.",
        rationale: "Microscopic artifact review confirmed pixel level edge discontinuity.",
        previous_status: "UNREVIEWED",
        prior_status: "UNREVIEWED",
        new_status: "CONFIRMED_OBSERVATION",
        reviewed_at: "2026-11-10T01:00:00Z",
      },
    ],
    created_at: "2026-11-10T00:00:00Z",
  },
];

const mockDossiers: InvestigationDossier[] = [
  {
    id: "dossier-001",
    case_id: "case-xyz",
    dossier_reference: "DOS-20261110-001",
    title: "Preliminary Forensic Case Dossier",
    scope_and_purpose: "Case cross-consistency and authenticity review.",
    status: "DRAFT",
    version: 1,
    created_by: "investigator-lead",
    sections: [],
    total_findings: 2,
    reviewed_findings_count: 1,
    created_at: "2026-11-10T01:10:00Z",
    updated_at: "2026-11-10T01:10:00Z",
  },
];

function createTestQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
    },
  });
}

describe("EpistemicNoticeBanner", () => {
  it("renders forensic triage notice text and expands epistemic guide", () => {
    render(<EpistemicNoticeBanner />);

    expect(
      screen.getByText(/Forensic Triage Notice:/i)
    ).toBeInTheDocument();
    expect(
      screen.getByText(/Automated findings support investigative triage/i)
    ).toBeInTheDocument();

    const toggleButton = screen.getByRole("button", { name: /Epistemic Guide/i });
    expect(toggleButton).toHaveAttribute("aria-expanded", "false");

    // Click to expand
    fireEvent.click(toggleButton);
    expect(toggleButton).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByText("OBSERVED FACT")).toBeInTheDocument();
    expect(screen.getByText("AUTOMATED INDICATOR")).toBeInTheDocument();
    expect(screen.getByText("ANALYTICAL INTERPRETATION")).toBeInTheDocument();
    expect(screen.getByText("INVESTIGATOR CONCLUSION")).toBeInTheDocument();

    // Click to collapse
    fireEvent.click(toggleButton);
    expect(toggleButton).toHaveAttribute("aria-expanded", "false");
    expect(screen.queryByText("OBSERVED FACT")).not.toBeInTheDocument();
  });
});

describe("FindingsFilterToolbar", () => {
  const defaultFilters: FindingsFilterState = {
    search: "",
    epistemic: "ALL",
    severity: "ALL",
    reviewStatus: "ALL",
    sourceType: "ALL",
  };

  it("renders counts and emits updated filters on input", () => {
    const onFiltersChange = vi.fn();
    render(
      <FindingsFilterToolbar
        filters={defaultFilters}
        onFiltersChange={onFiltersChange}
        totalCount={10}
        filteredCount={5}
      />
    );

    expect(screen.getByText("10")).toBeInTheDocument();
    expect(screen.getByText("5")).toBeInTheDocument();

    const searchInput = screen.getByPlaceholderText(/Search findings by title/i);
    fireEvent.change(searchInput, { target: { value: "discrepancy" } });
    expect(onFiltersChange).toHaveBeenCalledWith({
      ...defaultFilters,
      search: "discrepancy",
    });
  });

  it("handles dropdown filters and reset button", () => {
    const onFiltersChange = vi.fn();
    const activeFilters: FindingsFilterState = {
      search: "invoice",
      epistemic: "ANALYTICAL_INTERPRETATION",
      severity: "HIGH",
      reviewStatus: "UNREVIEWED",
      sourceType: "ALL",
    };

    const { rerender } = render(
      <FindingsFilterToolbar
        filters={activeFilters}
        onFiltersChange={onFiltersChange}
        totalCount={5}
        filteredCount={1}
      />
    );

    const resetButton = screen.getByRole("button", { name: /Reset/i });
    fireEvent.click(resetButton);
    expect(onFiltersChange).toHaveBeenCalledWith(defaultFilters);

    // Test select change
    rerender(
      <FindingsFilterToolbar
        filters={defaultFilters}
        onFiltersChange={onFiltersChange}
        totalCount={5}
        filteredCount={5}
      />
    );

    const severitySelect = screen.getByLabelText(/Filter by Severity/i);
    fireEvent.change(severitySelect, { target: { value: "CRITICAL" } });
    expect(onFiltersChange).toHaveBeenCalledWith({
      ...defaultFilters,
      severity: "CRITICAL",
    });
  });
});

describe("FindingsTable", () => {
  it("renders empty state when findings array is empty", () => {
    render(
      <FindingsTable
        findings={[]}
        selectedFindingId={null}
        onSelectFinding={vi.fn()}
      />
    );

    expect(screen.getByText(/No Findings Match Filter Criteria/i)).toBeInTheDocument();
  });

  it("renders findings and calls onSelectFinding on row click", () => {
    const onSelectFinding = vi.fn();
    render(
      <FindingsTable
        findings={mockFindings}
        selectedFindingId="finding-001"
        onSelectFinding={onSelectFinding}
      />
    );

    expect(screen.getByText("Invoice and PO Total Discrepancy")).toBeInTheDocument();
    expect(screen.getByText("Signature Area ELA Discontinuity")).toBeInTheDocument();

    const secondRow = screen.getByText("Signature Area ELA Discontinuity").closest("tr");
    expect(secondRow).not.toBeNull();
    fireEvent.click(secondRow!);
    expect(onSelectFinding).toHaveBeenCalledWith(mockFindings[1]);
  });
});

describe("FindingDetailPanel", () => {
  it("renders nothing when finding is null", () => {
    const { container } = render(
      <MemoryRouter>
        <FindingDetailPanel
          finding={null}
          onClose={vi.fn()}
          caseId="case-xyz"
          onOpenReviewModal={vi.fn()}
        />
      </MemoryRouter>
    );

    expect(container.firstChild).toBeNull();
  });

  it("renders complete finding details, evidence links, and review button", () => {
    const onClose = vi.fn();
    const onOpenReviewModal = vi.fn();

    render(
      <MemoryRouter>
        <FindingDetailPanel
          finding={mockFindings[0]}
          onClose={onClose}
          caseId="case-xyz"
          onOpenReviewModal={onOpenReviewModal}
        />
      </MemoryRouter>
    );

    expect(screen.getByText("Invoice and PO Total Discrepancy")).toBeInTheDocument();
    expect(screen.getByText(/Field: total_amount/i)).toBeInTheDocument();
    expect(screen.getByText(/Signal score represents relative algorithmic ranking weight/i)).toBeInTheDocument();
    expect(screen.getByText(/OCR rounding error possible/i)).toBeInTheDocument();
    expect(screen.getByText(/Supporting \(1\)/i)).toBeInTheDocument();
    expect(screen.getByText(/Contradicting \(1\)/i)).toBeInTheDocument();

    const reviewButton = screen.getByRole("button", { name: /Adjudicate \/ Record Investigator Review/i });
    fireEvent.click(reviewButton);
    expect(onOpenReviewModal).toHaveBeenCalledTimes(1);

    const closeButton = screen.getByTitle("Close details");
    fireEvent.click(closeButton);
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("renders review history when present", () => {
    render(
      <MemoryRouter>
        <FindingDetailPanel
          finding={mockFindings[1]}
          onClose={vi.fn()}
          caseId="case-xyz"
          onOpenReviewModal={vi.fn()}
        />
      </MemoryRouter>
    );

    expect(screen.getByText(/Append-Only Review History \(1\)/i)).toBeInTheDocument();
    expect(screen.getByText(/investigator-1/i)).toBeInTheDocument();
    expect(screen.getByText(/Microscopic artifact review confirmed pixel level edge discontinuity\./i)).toBeInTheDocument();
  });
});

describe("FindingReviewModal", () => {
  it("validates mandatory fields and submits human review", async () => {
    const onClose = vi.fn();
    const onSuccess = vi.fn();
    const mockCreatedReview = {
      id: "rev-new",
      case_id: "case-xyz",
      finding_id: "finding-001",
      reviewer_id: "examiner-mary",
      action: "CONFIRM_OBSERVATION" as const,
      comment: "Cross verified against physical signed invoice record.",
      rationale: "Cross verified against physical signed invoice record.",
      previous_status: "UNREVIEWED",
      prior_status: "UNREVIEWED",
      new_status: "CONFIRMED_OBSERVATION",
      reviewed_at: "2026-11-10T01:30:00Z",
    };

    vi.mocked(findingsApi.recordFindingReview).mockResolvedValue(mockCreatedReview);

    render(
      <FindingReviewModal
        isOpen={true}
        onClose={onClose}
        finding={mockFindings[0]}
        caseId="case-xyz"
        onSuccess={onSuccess}
      />
    );

    expect(screen.getByText("Record Investigator Review Adjudication")).toBeInTheDocument();
    expect(screen.getByText("Invoice and PO Total Discrepancy")).toBeInTheDocument();

    const submitButton = screen.getByRole("button", { name: /Commit Review/i });
    expect(submitButton).toBeDisabled();

    // Fill Reviewer ID using placeholder
    const reviewerInput = screen.getByPlaceholderText(/e\.g\. examiner-jones/i);
    fireEvent.change(reviewerInput, { target: { value: "examiner-mary" } });

    // Fill Rationale using placeholder
    const rationaleInput = screen.getByPlaceholderText(/Provide the factual basis/i);
    fireEvent.change(rationaleInput, {
      target: { value: "Cross verified against physical signed invoice record." },
    });

    // Check confirmation checkbox
    const confirmCheckbox = screen.getByRole("checkbox");
    fireEvent.click(confirmCheckbox);

    // Button should now be enabled
    expect(submitButton).not.toBeDisabled();
    fireEvent.click(submitButton);

    await waitFor(() => {
      expect(findingsApi.recordFindingReview).toHaveBeenCalledWith(
        "case-xyz",
        "finding-001",
        {
          reviewer_id: "examiner-mary",
          action: "CONFIRM_OBSERVATION",
          rationale: "Cross verified against physical signed invoice record.",
        }
      );
      expect(onSuccess).toHaveBeenCalledWith(mockCreatedReview);
    });
  });
});

describe("DossierReadinessDrawer", () => {
  let queryClient: QueryClient;

  beforeEach(() => {
    queryClient = createTestQueryClient();
    vi.mocked(dossiersApi.listDossiers).mockResolvedValue(mockDossiers);
  });

  it("calculates review-readiness metrics and renders existing dossiers", async () => {
    render(
      <QueryClientProvider client={queryClient}>
        <DossierReadinessDrawer
          isOpen={true}
          onClose={vi.fn()}
          caseId="case-xyz"
          findings={mockFindings}
          isCaseArchived={false}
        />
      </QueryClientProvider>
    );

    expect(screen.getByText(/Investigation Dossier Workbench/i)).toBeInTheDocument();
    expect(screen.getByText("1 / 2 Reviewed")).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getByText("Preliminary Forensic Case Dossier")).toBeInTheDocument();
    });
    expect(screen.getByText(/DOS-20261110-001|dossier-001/i)).toBeInTheDocument();
  });

  it("supports generating a new dossier draft", async () => {
    const newDossier: InvestigationDossier = {
      ...mockDossiers[0],
      id: "dossier-002",
      dossier_reference: "DOS-20261110-002",
      title: "Comprehensive Audit Dossier",
    };
    vi.mocked(dossiersApi.generateDossier).mockResolvedValue(newDossier);

    render(
      <QueryClientProvider client={queryClient}>
        <DossierReadinessDrawer
          isOpen={true}
          onClose={vi.fn()}
          caseId="case-xyz"
          findings={mockFindings}
          isCaseArchived={false}
        />
      </QueryClientProvider>
    );

    const newDraftBtn = screen.getByRole("button", { name: /New Draft/i });
    fireEvent.click(newDraftBtn);

    const compileButton = screen.getByRole("button", { name: /Compile Draft/i });
    fireEvent.click(compileButton);

    await waitFor(() => {
      expect(dossiersApi.generateDossier).toHaveBeenCalledWith("case-xyz", {
        created_by: "investigator-lead",
        scope_and_purpose: "Comprehensive verification and multi-document consistency audit.",
      });
    });
  });

  it("supports finalizing an approved dossier", async () => {
    const finalizedDossier: InvestigationDossier = {
      ...mockDossiers[0],
      status: "APPROVED",
      finalized_at: "2026-11-10T02:00:00Z",
      content_hash: "a".repeat(64),
    };
    vi.mocked(dossiersApi.finalizeDossier).mockResolvedValue(finalizedDossier);

    render(
      <QueryClientProvider client={queryClient}>
        <DossierReadinessDrawer
          isOpen={true}
          onClose={vi.fn()}
          caseId="case-xyz"
          findings={mockFindings}
          isCaseArchived={false}
        />
      </QueryClientProvider>
    );

    await waitFor(() => {
      expect(screen.getByText("Preliminary Forensic Case Dossier")).toBeInTheDocument();
    });

    const finalizeBtn = screen.getByRole("button", { name: /Finalize & Seal/i });
    fireEvent.click(finalizeBtn);

    await waitFor(() => {
      expect(screen.getByRole("button", { name: /Seal Snapshot/i })).toBeInTheDocument();
    });

    const confirmFinalizeBtn = screen.getByRole("button", { name: /Seal Snapshot/i });
    fireEvent.click(confirmFinalizeBtn);

    await waitFor(() => {
      expect(dossiersApi.finalizeDossier).toHaveBeenCalledWith(
        "case-xyz",
        "dossier-001",
        { user_id: "investigator-lead" }
      );
    });
  });
});
