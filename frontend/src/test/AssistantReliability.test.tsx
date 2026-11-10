import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { AssistantPage } from "../pages/AssistantPage";
import { CaseProvider } from "../context/CaseContext";
import { casesApi } from "../api/cases";
import { api } from "../api/client";
import type {
  Case,
  AssistantContextSummary,
  AssistantQueryResponse,
} from "../types/api";

vi.mock("../api/cases", () => ({
  casesApi: {
    getCase: vi.fn(),
  },
}));

vi.mock("../api/client", () => ({
  api: {
    get: vi.fn(),
    post: vi.fn(),
  },
}));

const mockCase: Case = {
  id: "case-99",
  case_reference: "CASE-20261110-099",
  title: "Reliability & Grounding Audit",
  description: "Provider resilience and adversarial verification.",
  status: "ACTIVE",
  created_at: "2026-11-10T00:00:00Z",
  updated_at: "2026-11-10T00:00:00Z",
  created_by: "auditor-1",
  metadata: {},
};

const mockSummary: AssistantContextSummary = {
  case_id: "case-99",
  case_title: "Reliability & Grounding Audit",
  case_status: "ACTIVE",
  counts: {
    documents: 2,
    forensic_findings: 1,
    consistency_findings: 1,
    entities: 2,
    relationships: 1,
    reviews: 0,
    total_items: 7,
  },
  document_titles: ["contract.pdf", "amendment.pdf"],
  unavailable_subsystems: [],
};

const renderWithProviders = () => {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });

  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={["/cases/case-99/assistant"]}>
        <CaseProvider>
          <Routes>
            <Route path="/cases/:caseId/assistant" element={<AssistantPage />} />
          </Routes>
        </CaseProvider>
      </MemoryRouter>
    </QueryClientProvider>
  );
};

describe("Assistant Reliability & Transparency Frontend", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(casesApi.getCase).mockResolvedValue(mockCase);
    vi.mocked(api.get).mockResolvedValue(mockSummary);
  });

  it("renders distinct provider failure banner with retry guidance when LLM provider fails", async () => {
    vi.mocked(api.post).mockRejectedValueOnce(
      new Error("LLM provider read timeout after 30.0s.")
    );

    renderWithProviders();

    await waitFor(() => {
      expect(screen.getByText(/Grounded Investigation Assistant/i)).toBeInTheDocument();
    });

    const textarea = screen.getByPlaceholderText(/Compare the invoice gross amount/i);
    fireEvent.change(textarea, { target: { value: "Perform contradiction check" } });

    const sendButton = screen.getByRole("button", { name: /Send/i });
    fireEvent.click(sendButton);

    await waitFor(() => {
      expect(screen.getByTestId("assistant-provider-error-alert")).toBeInTheDocument();
      expect(screen.getByText("Assistant Provider Failure")).toBeInTheDocument();
      expect(
        screen.getByText("LLM provider read timeout after 30.0s.")
      ).toBeInTheDocument();
      expect(screen.getByRole("button", { name: /Retry Query/i })).toBeInTheDocument();
    });

    // Verify clicking retry triggers the call again
    const mockSuccessResponse: AssistantQueryResponse = {
      case_id: "case-99",
      question_category: "CONTRADICTION_ANALYSIS",
      answer_text: "Recovered successfully on retry.",
      observed_facts: ["Invoice total is $5,000."],
      automated_indicators: [],
      analytical_interpretations: [],
      contradictory_evidence: ["Receipt records $4,200 (discrepancy)."],
      unresolved_questions: [],
      limitations: [],
      citations: [
        {
          citation_id: "cite_1",
          case_id: "case-99",
          document_id: "doc-1",
          document_title: "contract.pdf",
          evidence_id: null,
          finding_id: null,
          entity_id: null,
          relationship_id: null,
          page_number: 1,
          bounding_box: null,
          source_subsystem: "consistency",
          relevant_text: "Total $5,000",
          target_route: "/cases/case-99/documents/doc-1",
        },
      ],
      follow_up_suggestions: [],
      model_name: "evidexa-fast-v1",
      has_sufficient_evidence: true,
      ai_notice: "Authoritative ground truth",
      retrieval_stats: {},
    };

    vi.mocked(api.post).mockResolvedValueOnce(mockSuccessResponse);
    fireEvent.click(screen.getByRole("button", { name: /Retry Query/i }));

    await waitFor(() => {
      expect(screen.getByText("Recovered successfully on retry.")).toBeInTheDocument();
      expect(screen.getByText(/Citations Linked/i)).toBeInTheDocument();
    });
  });

  it("renders insufficient evidence notice and epistemic indicators clearly", async () => {
    const insufficientResponse: AssistantQueryResponse = {
      case_id: "case-99",
      question_category: "CROSS_DOCUMENT_COMPARISON",
      answer_text: "Insufficient records exist to establish cross-document reconciliation.",
      observed_facts: ["Document doc-1 exists."],
      automated_indicators: ["Automated OCR discrepancy flag present."],
      analytical_interpretations: ["Tentative match between signatory names."],
      contradictory_evidence: ["Tax ID mismatch detected."],
      unresolved_questions: ["Missing page 4 of contract."],
      limitations: ["Handwritten marginal notes unparsed."],
      citations: [],
      follow_up_suggestions: ["Upload complete contract annexes."],
      model_name: "evidexa-deep-v1",
      has_sufficient_evidence: false,
      ai_notice: "Authoritative ground truth",
      retrieval_stats: {},
    };

    vi.mocked(api.post).mockResolvedValueOnce(insufficientResponse);

    renderWithProviders();

    await waitFor(() => {
      expect(screen.getByText(/Grounded Investigation Assistant/i)).toBeInTheDocument();
    });

    const textarea = screen.getByPlaceholderText(/Compare the invoice gross amount/i);
    fireEvent.change(textarea, { target: { value: "Verify contract completeness" } });
    fireEvent.click(screen.getByRole("button", { name: /Send/i }));

    await waitFor(() => {
      expect(screen.getByText("Insufficient Case Evidence Notice")).toBeInTheDocument();
      expect(
        screen.getByText("Insufficient records exist to establish cross-document reconciliation.")
      ).toBeInTheDocument();
      expect(screen.getByText("Tax ID mismatch detected.")).toBeInTheDocument();
      expect(screen.getByText("Missing page 4 of contract.")).toBeInTheDocument();
      expect(screen.getByText("Handwritten marginal notes unparsed.")).toBeInTheDocument();
    });
  });
});
