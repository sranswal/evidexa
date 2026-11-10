import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";
import { DocumentTable } from "../components/documents/DocumentTable";
import type { DocumentItem } from "../types/api";

const mockDocuments: DocumentItem[] = [
  {
    id: "doc-101",
    case_id: "case-01",
    original_filename: "vendor_invoice_october.pdf",
    media_type: "application/pdf",
    file_extension: ".pdf",
    file_size_bytes: 524288,
    sha256: "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2",
    storage_key: "case-01/doc-101.pdf",
    page_count: 3,
    document_type: "INVOICE",
    ingestion_status: "PARSED",
    created_at: "2026-11-09T10:00:00Z",
    created_by: "lead-auditor",
    metadata: {},
  },
  {
    id: "doc-102",
    case_id: "case-01",
    original_filename: "receipt_scanned_copy.png",
    media_type: "image/png",
    file_extension: ".png",
    file_size_bytes: 204800,
    sha256: "b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3",
    storage_key: "case-01/doc-102.png",
    page_count: 1,
    document_type: "RECEIPT",
    ingestion_status: "STORED",
    created_at: "2026-11-09T11:30:00Z",
    created_by: "lead-auditor",
    metadata: { duplicate_of_document_id: "doc-101" },
  },
];

describe("DocumentTable Component", () => {
  it("renders document inventory columns and formatting", () => {
    const onSelect = vi.fn();
    render(
      <MemoryRouter>
        <DocumentTable
          caseId="case-01"
          documents={mockDocuments}
          onSelectDocument={onSelect}
        />
      </MemoryRouter>
    );

    // Verify filenames and IDs
    expect(screen.getByText("vendor_invoice_october.pdf")).toBeInTheDocument();
    expect(screen.getByText("doc-101")).toBeInTheDocument();
    expect(screen.getByText("receipt_scanned_copy.png")).toBeInTheDocument();
    expect(screen.getByText("doc-102")).toBeInTheDocument();

    // Verify truncated SHA-256 representation
    expect(screen.getByText("a1b2c3d4…e5f6a1b2")).toBeInTheDocument();

    // Verify duplicate badge for second document
    expect(screen.getByText("Duplicate of prior submission")).toBeInTheDocument();
  });

  it("calls onSelectDocument when a row or Inspect button is clicked", () => {
    const onSelect = vi.fn();
    render(
      <MemoryRouter>
        <DocumentTable
          caseId="case-01"
          documents={mockDocuments}
          onSelectDocument={onSelect}
        />
      </MemoryRouter>
    );

    const inspectButtons = screen.getAllByText("Inspect");
    fireEvent.click(inspectButtons[0]);

    expect(onSelect).toHaveBeenCalledWith(mockDocuments[0]);
  });
});

