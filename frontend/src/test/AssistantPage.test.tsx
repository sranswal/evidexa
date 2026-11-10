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
  id: "case-42",
  case_reference: "CASE-20261110-042",
  title: "Operation Apex Forensics",
  description: "Cross-document verification and audit inquiry.",
  status: "ACTIVE",
  created_at: "2026-11-10T00:00:00Z",
  updated_at: "2026-11-10T00:00:00Z",
  created_by: "examiner-1",
  metadata: {},
};

const mockSummary: AssistantContextSummary = {
  case_id: "case-42",
  case_title: "Operation Apex Forensics",
  case_status: "ACTIVE",
  counts: {
    documents: 2,
    forensic_findings: 2,
    consistency_findings: 1,
    entities: 4,
    relationships: 2,
    reviews: 0,
    total_items: 11,
  },
  document_titles: ["invoice_101.pdf", "receipt_202.pdf"],
  unavailable_subsystems: [],
};

const mockQueryResponse: AssistantQueryResponse = {
  case_id: "case-42",
  question_category: "INVESTIGATION_SUMMARY",
  answer_text: "Based on authoritative case records, 2 documents have been analyzed.",
  observed_facts: ["Document doc-1 has SHA-256 e3b0c..."],
  automated_indicators: ["Structural anomaly detected on page 1."],
  analytical_interpretations: ["Vendor Alpha matches Vendor Beta heuristically."],
  contradictory_evidence: [],
  unresolved_questions: ["Original signed paper contract remains unverified."],
  limitations: ["No raw OCR ground truth for redacted sections."],
  citations: [
    {
      citation_id: "[E-1]",
      case_id: "case-42",
      document_id: "doc-1",
      document_title: "invoice_101.pdf",
      evidence_id: null,
      finding_id: null,
      entity_id: null,
      relationship_id: null,
      page_number: 1,
      bounding_box: null,
      source_subsystem: "inventory",
      relevant_text: "Primary invoice submitted for verification.",
      target_route: "/cases/case-42/documents/doc-1/examine",
    },
  ],
  follow_up_suggestions: [
    "Verify whether the trailer dictionary alteration occurred before or after signing.",
  ],
  has_sufficient_evidence: true,
  ai_notice: "AI-generated response grounded strictly in EVIDEXA case records.",
  retrieval_stats: {},
  model_name: "evidexa-mock-llm-v1",
};

describe("AssistantPage", () => {
  let queryClient: QueryClient;

  beforeEach(() => {
    vi.clearAllMocks();
    queryClient = new QueryClient({
      defaultOptions: {
        queries: { retry: false },
        mutations: { retry: false },
      },
    });

    vi.mocked(casesApi.getCase).mockResolvedValue(mockCase);
    vi.mocked(api.get).mockResolvedValue(mockSummary);
    vi.mocked(api.post).mockResolvedValue(mockQueryResponse);
  });

  const renderComponent = () =>
    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={["/cases/case-42/assistant"]}>
          <CaseProvider>
            <Routes>
              <Route path="/cases/:caseId/assistant" element={<AssistantPage />} />
            </Routes>
          </CaseProvider>
        </MemoryRouter>
      </QueryClientProvider>
    );

  it("renders page header, AI notice banner, and context summary counters", async () => {
    renderComponent();

    expect(screen.getByText("Grounded Investigation Assistant")).toBeInTheDocument();
    expect(
      screen.getByText(/EVIDEXA Evidentiary AI Boundary/i)
    ).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getByText(/2 docs • 3 findings • 4 entities/i)).toBeInTheDocument();
    });
  });

  it("renders prompt category suggestion pills", async () => {
    renderComponent();

    expect(screen.getByText("Case Summary")).toBeInTheDocument();
    expect(screen.getByText("Contradiction Check")).toBeInTheDocument();
    expect(screen.getByText("Compare Documents")).toBeInTheDocument();
    expect(screen.getByText("Explain Findings")).toBeInTheDocument();
    expect(screen.getByText("Investigate Entities")).toBeInTheDocument();
    expect(screen.getByText("Suggest Next Steps")).toBeInTheDocument();
  });

  it("submits question and renders response, citations, and epistemic breakdown", async () => {
    renderComponent();

    const input = screen.getByPlaceholderText(
      /Compare the invoice gross amount against the receipt payment records/i
    );
    fireEvent.change(input, {
      target: { value: "Provide an investigation summary of this case." },
    });

    const sendBtn = screen.getByRole("button", { name: /Send/i });
    fireEvent.click(sendBtn);

    await waitFor(() => {
      expect(
        screen.getByText(
          "Based on authoritative case records, 2 documents have been analyzed."
        )
      ).toBeInTheDocument();
    });

    // Check citation rendered
    expect(screen.getByText("[E-1]")).toBeInTheDocument();
    expect(screen.getByText("invoice_101.pdf")).toBeInTheDocument();

    // Check Epistemic breakdown accordion headers
    expect(screen.getByText(/Epistemic Evidence Breakdown/i)).toBeInTheDocument();
    expect(screen.getByText(/Automated Algorithmic Indicators/i)).toBeInTheDocument();

    // Check follow-up suggestions
    expect(
      screen.getByText(/Verify whether the trailer dictionary alteration/i)
    ).toBeInTheDocument();
  });
});
