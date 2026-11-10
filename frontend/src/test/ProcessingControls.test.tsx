import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { ProcessingControls } from "../components/documents/ProcessingControls";
import { documentsApi } from "../api/documents";
import type { DocumentItem } from "../types/api";

const mockPdfDoc: DocumentItem = {
  id: "doc-pdf-1",
  case_id: "case-200",
  original_filename: "statement.pdf",
  media_type: "application/pdf",
  file_extension: ".pdf",
  file_size_bytes: 4096,
  sha256: "1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef",
  storage_key: "case-200/doc-pdf-1.pdf",
  page_count: 1,
  document_type: "BANK_STATEMENT",
  ingestion_status: "STORED",
  created_at: "2026-11-10T00:00:00Z",
  created_by: "lead",
  metadata: {},
};

const mockImgDoc: DocumentItem = {
  id: "doc-img-1",
  case_id: "case-200",
  original_filename: "receipt.png",
  media_type: "image/png",
  file_extension: ".png",
  file_size_bytes: 2048,
  sha256: "abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890",
  storage_key: "case-200/doc-img-1.png",
  page_count: 1,
  document_type: "RECEIPT",
  ingestion_status: "STORED",
  created_at: "2026-11-10T00:00:00Z",
  created_by: "lead",
  metadata: {},
};

describe("ProcessingControls Component", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("exposes PDF structural analysis for PDF files", () => {
    render(
      <ProcessingControls
        caseId="case-200"
        document={mockPdfDoc}
        onOperationComplete={vi.fn()}
      />
    );

    expect(screen.getByText("Run Structural Forensics")).toBeInTheDocument();
    expect(screen.getByText("Run Visual ELA")).toBeInTheDocument();
    expect(screen.getByText("Execute Hybrid OCR")).toBeInTheDocument();
    expect(screen.getByText("Run Classifier")).toBeInTheDocument();
    expect(screen.getByText("Extract Structured Fields")).toBeInTheDocument();
  });

  it("omits PDF structural analysis for raster images", () => {
    render(
      <ProcessingControls
        caseId="case-200"
        document={mockImgDoc}
        onOperationComplete={vi.fn()}
      />
    );

    expect(screen.queryByText("Run Structural Forensics")).not.toBeInTheDocument();
    expect(screen.getByText("Run Visual ELA")).toBeInTheDocument();
    expect(screen.getByText("Execute Hybrid OCR")).toBeInTheDocument();
  });

  it("executes hybrid OCR pipeline and notifies parent", async () => {
    const onComplete = vi.fn();
    vi.spyOn(documentsApi, "startOcr").mockResolvedValueOnce({
      processing_run: {
        id: "run-ocr-1",
        pipeline_name: "hybrid-ocr-pipeline",
        status: "SUCCEEDED",
        started_at: "2026-11-10T00:00:00Z",
        completed_at: "2026-11-10T00:00:01Z",
        error_message: null,
      },
      summary: { execution_duration_ms: 120 },
    });

    render(
      <ProcessingControls
        caseId="case-200"
        document={mockPdfDoc}
        onOperationComplete={onComplete}
      />
    );

    const ocrBtn = screen.getByText("Execute Hybrid OCR");
    fireEvent.click(ocrBtn);

    await waitFor(() => {
      expect(documentsApi.startOcr).toHaveBeenCalledWith(
        "case-200",
        "doc-pdf-1",
        "hybrid-ocr-pipeline"
      );
      expect(screen.getByText(/OCR Completed/i)).toBeInTheDocument();
      expect(onComplete).toHaveBeenCalled();
    });
  });

  it("disables operations when case is archived", () => {
    render(
      <ProcessingControls
        caseId="case-200"
        document={mockPdfDoc}
        isCaseArchived={true}
        onOperationComplete={vi.fn()}
      />
    );

    expect(
      screen.getByText(/Case is ARCHIVED. Execution of new processing pipelines is restricted/i)
    ).toBeInTheDocument();

    const buttons = screen.getAllByRole("button");
    buttons.forEach((btn) => {
      expect(btn).toBeDisabled();
    });
  });
});
