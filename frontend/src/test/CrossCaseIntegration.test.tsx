import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { CrossCasePage } from "../pages/CrossCasePage";
import { crossCaseApi, CrossCaseScope, CrossCaseCandidateMatch } from "../api/crossCase";
import { casesApi } from "../api/cases";

const mockScopes: CrossCaseScope[] = [
  {
    id: "scope-001",
    organization_id: "org-alpha",
    name: "Regional Vendor Collusion Ring",
    description: "Investigating shared bank accounts across vendor networks.",
    case_ids: ["case-001", "case-002"],
    created_by: "user-investigator",
    created_at: "2026-11-10T12:00:00Z",
    updated_at: "2026-11-10T12:00:00Z",
    is_active: true,
  },
];

const mockCandidates: CrossCaseCandidateMatch[] = [
  {
    id: "match-001",
    scope_id: "scope-001",
    organization_id: "org-alpha",
    entity_type: "BANK_ACCOUNT_REFERENCE",
    target_case_id: "case-001",
    candidate_case_id: "case-002",
    target_value_display: "Account ****9012",
    candidate_value_display: "Account ****9012",
    raw_target_value_masked: "Account ****9012",
    raw_candidate_value_masked: "Account ****9012",
    matching_method: "bank_account_digits",
    match_classification: "EXACT_IDENTIFIER",
    match_score: 0.96,
    decision_status: "PENDING_REVIEW",
    evidence: {
      target_case_id: "case-001",
      candidate_case_id: "case-002",
      target_mention_id: "m-1",
      candidate_mention_id: "m-2",
      target_document_id: "doc-1",
      candidate_document_id: "doc-2",
      target_field_key: "account_number",
      candidate_field_key: "account_number",
      matching_signals: ["Identical bank account digits detected across cases"],
      contradicting_signals: [],
      confidence_score: 0.96,
      matching_method: "bank_account_digits",
      match_classification: "EXACT_IDENTIFIER",
    },
    review_history: [],
    created_at: "2026-11-10T12:05:00Z",
  },
];

describe("CrossCasePage Frontend Integration", () => {
  let queryClient: QueryClient;

  beforeEach(() => {
    vi.restoreAllMocks();
    queryClient = new QueryClient({
      defaultOptions: {
        queries: { retry: false },
      },
    });
  });

  it("renders page header and epistemic warning notice", async () => {
    vi.spyOn(crossCaseApi, "listScopes").mockResolvedValueOnce(mockScopes);
    vi.spyOn(crossCaseApi, "getScope").mockResolvedValueOnce(mockScopes[0]);
    vi.spyOn(casesApi, "listCases").mockResolvedValueOnce({ items: [], total: 0, skip: 0, limit: 50 });
    vi.spyOn(crossCaseApi, "listCandidates").mockResolvedValueOnce({
      items: mockCandidates,
      total: 1,
      limit: 100,
      offset: 0,
    });

    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter>
          <CrossCasePage />
        </MemoryRouter>
      </QueryClientProvider>
    );

    expect(screen.getByText("Cross-Case Investigation Intelligence")).toBeInTheDocument();
    expect(screen.getByText(/Epistemic Warning/i)).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getByText("Regional Vendor Collusion Ring")).toBeInTheDocument();
      expect(screen.getAllByText("Account ****9012").length).toBeGreaterThanOrEqual(1);
      expect(screen.getByText("Exact Identifier")).toBeInTheDocument();
      expect(screen.getAllByText("Pending Review").length).toBeGreaterThanOrEqual(1);
    });
  });

  it("opens review modal and submits disposition with rationale", async () => {
    vi.spyOn(crossCaseApi, "listScopes").mockResolvedValue(mockScopes);
    vi.spyOn(crossCaseApi, "getScope").mockResolvedValue(mockScopes[0]);
    vi.spyOn(casesApi, "listCases").mockResolvedValue({ items: [], total: 0, skip: 0, limit: 50 });
    vi.spyOn(crossCaseApi, "listCandidates").mockResolvedValue({
      items: mockCandidates,
      total: 1,
      limit: 100,
      offset: 0,
    });

    const reviewSpy = vi.spyOn(crossCaseApi, "reviewCandidate").mockResolvedValueOnce({
      ...mockCandidates[0],
      decision_status: "ACCEPTED",
      review_history: [
        {
          id: "rev-1",
          match_id: "match-001",
          scope_id: "scope-001",
          decision: "ACCEPTED",
          reviewer_id: "usr-rev",
          reviewer_username: "lead_reviewer",
          rationale: "Legitimate cross-case entity confirmed",
          new_status: "ACCEPTED",
          reviewed_at: "2026-11-10T12:10:00Z",
        },
      ],
    });

    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter>
          <CrossCasePage />
        </MemoryRouter>
      </QueryClientProvider>
    );

    await waitFor(() => {
      expect(screen.getByText("Review")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText("Review"));

    expect(screen.getByText("Candidate Review Disposition")).toBeInTheDocument();

    const textarea = screen.getByPlaceholderText(/Record evidentiary justification/i);
    fireEvent.change(textarea, { target: { value: "Legitimate cross-case entity confirmed" } });

    fireEvent.click(screen.getByText("Submit Disposition"));

    await waitFor(() => {
      expect(reviewSpy).toHaveBeenCalledWith("scope-001", "match-001", {
        decision: "ACCEPTED",
        rationale: "Legitimate cross-case entity confirmed",
      });
    });
  });
});
