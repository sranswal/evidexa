import { render, screen, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { EvidenceGraphPage } from "../pages/EvidenceGraphPage";
import { CaseProvider } from "../context/CaseContext";
import { casesApi } from "../api/cases";
import { graphApi } from "../api/graph";
import type { Case, GraphSnapshot } from "../types/api";

vi.mock("../api/cases", () => ({
  casesApi: {
    getCase: vi.fn(),
  },
}));

vi.mock("../api/graph", () => ({
  graphApi: {
    getCaseGraph: vi.fn(),
    getNode: vi.fn(),
    getNeighborhood: vi.fn(),
    findPaths: vi.fn(),
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

const mockGraphSnapshot: GraphSnapshot = {
  case_id: "case-xyz",
  total_nodes: 2,
  total_edges: 1,
  truncated: false,
  projection_version: "1.0",
  query_metadata: {},
  nodes: [
    {
      id: "doc-101",
      case_id: "case-xyz",
      node_type: "DOCUMENT",
      source_entity_type: "documents",
      source_entity_id: "doc-101",
      label: "Invoice_Vendor_Alpha.pdf",
      display_attributes: { page_count: 1 },
      provenance: { document_id: "doc-101" },
      created_at: "2026-11-10T00:00:00Z",
    },
    {
      id: "org-202",
      case_id: "case-xyz",
      node_type: "ORGANIZATION",
      source_entity_type: "entities",
      source_entity_id: "org-202",
      label: "Alpha Procurement Corp",
      display_attributes: {},
      provenance: {},
      created_at: "2026-11-10T00:00:00Z",
    },
  ],
  edges: [
    {
      id: "edge-303",
      case_id: "case-xyz",
      source_node_id: "doc-101",
      target_node_id: "org-202",
      predicate: "ISSUED",
      status: "CONFIRMED",
      status_determination_method: "EVIDENTIARY_RULE",
      score: 1.0,
      explanation: "Document header references vendor organization",
      supporting_evidence_ids: [],
      contradicting_evidence_ids: [],
      source_relationship_id: null,
      metadata: {},
    },
  ],
};

function renderGraphPage(caseId = "case-xyz") {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
    },
  });

  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[`/cases/${caseId}/graph`]}>
        <CaseProvider>
          <Routes>
            <Route path="/cases/:caseId/graph" element={<EvidenceGraphPage />} />
          </Routes>
        </CaseProvider>
      </MemoryRouter>
    </QueryClientProvider>
  );
}

describe("EvidenceGraphPage Integration", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("mounts, fetches graph snapshot, and displays case breadcrumb & canvas controls", async () => {
    vi.mocked(casesApi.getCase).mockResolvedValueOnce(mockCase);
    vi.mocked(graphApi.getCaseGraph).mockResolvedValueOnce(mockGraphSnapshot);

    renderGraphPage();

    await waitFor(() => {
      expect(casesApi.getCase).toHaveBeenCalledWith("case-xyz");
      expect(graphApi.getCaseGraph).toHaveBeenCalledWith("case-xyz", expect.anything());
    });

    await waitFor(() => {
      expect(screen.getByText("Evidence Graph Canvas")).toBeInTheDocument();
      expect(screen.getByText("CASE-20261110-001")).toBeInTheDocument();
      expect(screen.getByText("Projection: Unified Deterministic v1.0")).toBeInTheDocument();
    });
  });

  it("renders empty state notice when case has no graph nodes", async () => {
    vi.mocked(casesApi.getCase).mockResolvedValueOnce(mockCase);
    vi.mocked(graphApi.getCaseGraph).mockResolvedValueOnce({
      case_id: "case-xyz",
      total_nodes: 0,
      total_edges: 0,
      truncated: false,
      projection_version: "1.0",
      query_metadata: {},
      nodes: [],
      edges: [],
    });

    renderGraphPage();

    await waitFor(() => {
      expect(screen.getByText("Evidence Graph Canvas")).toBeInTheDocument();
      expect(screen.getByText("No Evidence Graph Projected")).toBeInTheDocument();
      expect(screen.getByText(/No documents, entities, or forensic findings/i)).toBeInTheDocument();
    });
  });

  it("handles backend error gracefully and provides retry button", async () => {
    vi.mocked(casesApi.getCase).mockResolvedValueOnce(mockCase);
    vi.mocked(graphApi.getCaseGraph).mockRejectedValueOnce(new Error("Database connection timed out"));

    renderGraphPage();

    await waitFor(() => {
      expect(screen.getByText("Failed to Project Graph")).toBeInTheDocument();
      expect(screen.getByText(/Database connection timed out/i)).toBeInTheDocument();
      expect(screen.getByText("Retry Query")).toBeInTheDocument();
    });
  });
});
