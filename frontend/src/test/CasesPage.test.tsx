import { render, screen, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { CasesPage } from "../pages/CasesPage";
import { casesApi } from "../api/cases";
import type { Case } from "../types/api";

const mockCases: Case[] = [
  {
    id: "case-001",
    case_reference: "CASE-20261109-001",
    title: "Global Supply Corp Invoicing Investigation",
    description: "Multi-party forensic audit regarding altered invoice amounts.",
    status: "ACTIVE",
    created_at: "2026-11-09T10:00:00Z",
    updated_at: "2026-11-09T10:00:00Z",
    created_by: "lead-auditor",
    metadata: {},
  },
  {
    id: "case-002",
    case_reference: "CASE-20261109-002",
    title: "Delta Partners Payroll Reconciliation",
    description: "Cross-document payroll tax consistency examination.",
    status: "UNDER_REVIEW",
    created_at: "2026-11-08T14:30:00Z",
    updated_at: "2026-11-08T15:00:00Z",
    created_by: "investigator-2",
    metadata: {},
  },
];

describe("CasesPage Component", () => {
  let queryClient: QueryClient;

  beforeEach(() => {
    vi.restoreAllMocks();
    queryClient = new QueryClient({
      defaultOptions: {
        queries: { retry: false },
      },
    });
  });

  it("renders page header and investigation cases list", async () => {
    vi.spyOn(casesApi, "listCases").mockResolvedValueOnce({
      items: mockCases,
      total: 2,
      skip: 0,
      limit: 100,
    });

    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter>
          <CasesPage />
        </MemoryRouter>
      </QueryClientProvider>
    );

    expect(screen.getByText("Investigation Cases")).toBeInTheDocument();

    await waitFor(() => {
      expect(
        screen.getByText("Global Supply Corp Invoicing Investigation")
      ).toBeInTheDocument();
      expect(
        screen.getByText("Delta Partners Payroll Reconciliation")
      ).toBeInTheDocument();
    });

    expect(screen.getByText("CASE-20261109-001")).toBeInTheDocument();
    expect(screen.getByText("CASE-20261109-002")).toBeInTheDocument();
  });

  it("shows empty state when no cases exist", async () => {
    vi.spyOn(casesApi, "listCases").mockResolvedValueOnce({
      items: [],
      total: 0,
      skip: 0,
      limit: 100,
    });

    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter>
          <CasesPage />
        </MemoryRouter>
      </QueryClientProvider>
    );

    await waitFor(() => {
      expect(screen.getByText("No investigation cases found")).toBeInTheDocument();
    });
  });
});
