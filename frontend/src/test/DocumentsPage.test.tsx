import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { DocumentsPage } from "../pages/DocumentsPage";
import { CaseProvider } from "../context/CaseContext";
import { documentsApi } from "../api/documents";
import { casesApi } from "../api/cases";
import type { DocumentItem, Case } from "../types/api";

const mockCase: Case = {
  id: "case-300",
  case_reference: "CASE-20261110-300",
  title: "Underwriting Fraud Ring Investigation",
  description: "Cross-document verification of financial submissions.",
  status: "ACTIVE",
  created_at: "2026-11-10T00:00:00Z",
  updated_at: "2026-11-10T00:00:00Z",
  created_by: "lead-investigator",
  metadata: {},
};

const mockDocs: DocumentItem[] = [
  {
    id: "doc-301",
    case_id: "case-300",
    original_filename: "invoice_supplier_alpha.pdf",
    media_type: "application/pdf",
    file_extension: ".pdf",
    file_size_bytes: 300000,
    sha256: "1111222233334444555566667777888899990000aaaabbbbccccddddeeeeffff",
    storage_key: "case-300/doc-301.pdf",
    page_count: 2,
    document_type: "INVOICE",
    ingestion_status: "PARSED",
    created_at: "2026-11-10T00:05:00Z",
    created_by: "lead-investigator",
    metadata: {},
  },
  {
    id: "doc-302",
    case_id: "case-300",
    original_filename: "receipt_retail_beta.png",
    media_type: "image/png",
    file_extension: ".png",
    file_size_bytes: 150000,
    sha256: "9999888877776666555544443333222211110000ffffeeeeddddccccbbbbaaaa",
    storage_key: "case-300/doc-302.png",
    page_count: 1,
    document_type: "RECEIPT",
    ingestion_status: "STORED",
    created_at: "2026-11-10T00:10:00Z",
    created_by: "lead-investigator",
    metadata: {},
  },
];

describe("DocumentsPage Component", () => {
  let queryClient: QueryClient;

  beforeEach(() => {
    vi.restoreAllMocks();
    queryClient = new QueryClient({
      defaultOptions: {
        queries: { retry: false },
      },
    });
  });

  it("renders document inventory, KPIs, and table records", async () => {
    vi.spyOn(casesApi, "getCase").mockResolvedValue(mockCase);
    vi.spyOn(documentsApi, "listDocuments").mockResolvedValue({
      items: mockDocs,
      total: 2,
      skip: 0,
      limit: 50,
    });

    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={["/cases/case-300/documents"]}>
          <Routes>
            <Route
              path="/cases/:caseId/documents"
              element={
                <CaseProvider>
                  <DocumentsPage />
                </CaseProvider>
              }
            />
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>
    );

    expect(screen.getByText("Case Evidence Documents")).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getByText("invoice_supplier_alpha.pdf")).toBeInTheDocument();
      expect(screen.getByText("receipt_retail_beta.png")).toBeInTheDocument();
    });

    // Verify KPI values
    expect(screen.getByText("Total Files")).toBeInTheDocument();
    expect(screen.getByText("Storage Volume")).toBeInTheDocument();
  });

  it("renders empty state when no documents exist", async () => {
    vi.spyOn(casesApi, "getCase").mockResolvedValue(mockCase);
    vi.spyOn(documentsApi, "listDocuments").mockResolvedValue({
      items: [],
      total: 0,
      skip: 0,
      limit: 50,
    });

    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={["/cases/case-300/documents"]}>
          <Routes>
            <Route
              path="/cases/:caseId/documents"
              element={
                <CaseProvider>
                  <DocumentsPage />
                </CaseProvider>
              }
            />
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>
    );

    await waitFor(() => {
      expect(screen.getByText("No evidence documents registered")).toBeInTheDocument();
      expect(screen.getByText("Ingest First Document")).toBeInTheDocument();
    });
  });

  it("filters documents by search query", async () => {
    vi.spyOn(casesApi, "getCase").mockResolvedValue(mockCase);
    vi.spyOn(documentsApi, "listDocuments").mockResolvedValue({
      items: mockDocs,
      total: 2,
      skip: 0,
      limit: 50,
    });

    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={["/cases/case-300/documents"]}>
          <Routes>
            <Route
              path="/cases/:caseId/documents"
              element={
                <CaseProvider>
                  <DocumentsPage />
                </CaseProvider>
              }
            />
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>
    );

    await waitFor(() => {
      expect(screen.getByText("invoice_supplier_alpha.pdf")).toBeInTheDocument();
      expect(screen.getByText("receipt_retail_beta.png")).toBeInTheDocument();
    });

    const searchInput = screen.getByPlaceholderText(/Search by filename, document ID, or SHA-256/i);
    fireEvent.change(searchInput, { target: { value: "alpha" } });

    expect(screen.getByText("invoice_supplier_alpha.pdf")).toBeInTheDocument();
    expect(screen.queryByText("receipt_retail_beta.png")).not.toBeInTheDocument();
  });
});

