import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { DocumentUploadModal } from "../components/documents/DocumentUploadModal";
import { documentsApi } from "../api/documents";

describe("DocumentUploadModal Component", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("renders upload modal and drag-and-drop elements", () => {
    render(
      <DocumentUploadModal
        isOpen={true}
        onClose={vi.fn()}
        caseId="case-100"
        onUploadSuccess={vi.fn()}
      />
    );

    expect(screen.getByText("Secure Evidence Document Ingestion")).toBeInTheDocument();
    expect(
      screen.getByText(/Drag and drop original evidence file here/i)
    ).toBeInTheDocument();
    expect(screen.getByText(/Forensic Invariant/i)).toBeInTheDocument();
  });

  it("rejects files exceeding 50 MB threshold", async () => {
    render(
      <DocumentUploadModal
        isOpen={true}
        onClose={vi.fn()}
        caseId="case-100"
        onUploadSuccess={vi.fn()}
      />
    );

    // Create a 51 MB synthetic file
    const oversizedFile = new File([new Uint8Array(51 * 1024 * 1024)], "oversized.pdf", {
      type: "application/pdf",
    });

    const dropzone = screen.getByText(/Drag and drop original evidence file here/i);
    fireEvent.drop(dropzone, {
      dataTransfer: { files: [oversizedFile] },
    });

    await waitFor(() => {
      expect(
        screen.getByText(/exceeds the 50 MB threshold/i)
      ).toBeInTheDocument();
    });
  });

  it("rejects unauthorized file extensions", async () => {
    render(
      <DocumentUploadModal
        isOpen={true}
        onClose={vi.fn()}
        caseId="case-100"
        onUploadSuccess={vi.fn()}
      />
    );

    const badFile = new File(["malicious binary"], "malicious.exe", {
      type: "application/x-msdownload",
    });

    const dropzone = screen.getByText(/Drag and drop original evidence file here/i);
    fireEvent.drop(dropzone, {
      dataTransfer: { files: [badFile] },
    });

    await waitFor(() => {
      expect(screen.getByText(/Unsupported file format/i)).toBeInTheDocument();
    });
  });

  it("submits valid file and executes upload callback", async () => {
    const onSuccess = vi.fn();
    const onClose = vi.fn();

    const mockSavedDoc = {
      id: "doc-new-1",
      case_id: "case-100",
      original_filename: "test_invoice.pdf",
      media_type: "application/pdf",
      file_extension: ".pdf",
      file_size_bytes: 1024,
      sha256: "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
      storage_key: "case-100/doc-new-1.pdf",
      page_count: 1,
      document_type: "INVOICE" as const,
      ingestion_status: "STORED" as const,
      created_at: "2026-11-10T00:00:00Z",
      created_by: "lead-investigator",
      metadata: {},
    };

    vi.spyOn(documentsApi, "uploadDocument").mockResolvedValueOnce(mockSavedDoc);

    render(
      <DocumentUploadModal
        isOpen={true}
        onClose={onClose}
        caseId="case-100"
        onUploadSuccess={onSuccess}
      />
    );

    const validFile = new File(["%PDF-1.4 header"], "test_invoice.pdf", {
      type: "application/pdf",
    });

    const dropzone = screen.getByText(/Drag and drop original evidence file here/i);
    fireEvent.drop(dropzone, {
      dataTransfer: { files: [validFile] },
    });

    await waitFor(() => {
      expect(screen.getByText("test_invoice.pdf")).toBeInTheDocument();
      expect(screen.getByText("Ready")).toBeInTheDocument();
    });

    // Click submit
    const submitBtn = screen.getByText("Ingest & Verify Document");
    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(documentsApi.uploadDocument).toHaveBeenCalledWith(
        "case-100",
        validFile,
        "lead-investigator"
      );
      expect(onSuccess).toHaveBeenCalledWith(mockSavedDoc);
      expect(onClose).toHaveBeenCalled();
    });
  });
});
