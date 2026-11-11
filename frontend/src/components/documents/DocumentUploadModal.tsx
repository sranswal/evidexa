import React, { useState, useRef } from "react";
import { UploadCloud, File, AlertTriangle, CheckCircle, ShieldCheck } from "lucide-react";
import { Modal } from "../ui/Modal";
import { Button } from "../ui/Button";
import { documentsApi } from "../../api/documents";
import type { DocumentItem } from "../../types/api";

const MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024; // 50 MB
const ALLOWED_EXTENSIONS = [".pdf", ".png", ".jpg", ".jpeg", ".tiff", ".tif"];
const ALLOWED_MIME_TYPES = [
  "application/pdf",
  "image/png",
  "image/jpeg",
  "image/tiff",
];

export interface DocumentUploadModalProps {
  isOpen: boolean;
  onClose: () => void;
  caseId: string;
  onUploadSuccess: (doc: DocumentItem) => void;
}

export const DocumentUploadModal: React.FC<DocumentUploadModalProps> = ({
  isOpen,
  onClose,
  caseId,
  onUploadSuccess,
}) => {
  const [dragActive, setDragActive] = useState(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [investigatorId, setInvestigatorId] = useState("lead-investigator");
  const [autoRunOcr, setAutoRunOcr] = useState(true);
  const [selectedPipeline, setSelectedPipeline] = useState<"hybrid-ocr-pipeline" | "ppocrv5-devanagari-engine">("hybrid-ocr-pipeline");
  const [uploadStage, setUploadStage] = useState<string | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const resetState = () => {
    setSelectedFile(null);
    setErrorMsg(null);
    setIsUploading(false);
    setUploadStage(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  };

  const handleClose = () => {
    if (isUploading) return;
    resetState();
    onClose();
  };

  const validateFile = (file: File): string | null => {
    // 1. File size check
    if (file.size > MAX_FILE_SIZE_BYTES) {
      return `File size (${(file.size / (1024 * 1024)).toFixed(1)} MB) exceeds the 50 MB threshold.`;
    }

    // 2. Extension check
    const nameLower = file.name.toLowerCase();
    const hasValidExt = ALLOWED_EXTENSIONS.some((ext) => nameLower.endsWith(ext));
    if (!hasValidExt) {
      return `Unsupported file format. Allowed extensions: ${ALLOWED_EXTENSIONS.join(", ")}`;
    }

    // 3. MIME check (if provided by browser)
    if (file.type && !ALLOWED_MIME_TYPES.includes(file.type)) {
      // Browsers occasionally assign generic application/octet-stream to TIFFs, so only reject if clearly non-matching
      if (file.type !== "application/octet-stream") {
        return `Unsupported MIME type: ${file.type}. Allowed: PDF, PNG, JPEG, TIFF.`;
      }
    }

    return null;
  };

  const handleFileSelection = (file: File) => {
    setErrorMsg(null);
    const validationError = validateFile(file);
    if (validationError) {
      setErrorMsg(validationError);
      setSelectedFile(null);
      return;
    }
    setSelectedFile(file);
  };

  const handleDrag = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === "dragenter" || e.type === "dragover") {
      setDragActive(true);
    } else if (e.type === "dragleave") {
      setDragActive(false);
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);

    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      handleFileSelection(e.dataTransfer.files[0]);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedFile) {
      setErrorMsg("Please select an evidence file to upload.");
      return;
    }

    setIsUploading(true);
    setUploadStage("Uploading & hashing file...");
    setErrorMsg(null);

    try {
      const doc = await documentsApi.uploadDocument(
        caseId,
        selectedFile,
        investigatorId.trim() || undefined
      );

      if (autoRunOcr) {
        setUploadStage("Running Forensic OCR Pipeline...");
        try {
          await documentsApi.startOcr(caseId, doc.id, selectedPipeline);
        } catch (ocrErr: any) {
          console.warn("Auto-OCR pipeline notice:", ocrErr);
        }
      }

      resetState();
      onUploadSuccess(doc);
      onClose();
    } catch (err: any) {
      setErrorMsg(err.message || "Failed to upload and ingest evidence file.");
    } finally {
      setIsUploading(false);
      setUploadStage(null);
    }
  };

  return (
    <Modal isOpen={isOpen} onClose={handleClose} title="Secure Evidence Document Ingestion">
      <form onSubmit={handleSubmit} className="space-y-4">
        {/* Error Alert */}
        {errorMsg && (
          <div
            role="alert"
            className="p-3 rounded-lg bg-rose-950/60 border border-rose-500/50 text-xs text-rose-300 flex items-start gap-2"
          >
            <AlertTriangle className="w-4 h-4 text-rose-400 shrink-0 mt-0.5" />
            <span className="leading-relaxed">{errorMsg}</span>
          </div>
        )}

        {/* Drag and drop zone */}
        <div
          onDragEnter={handleDrag}
          onDragLeave={handleDrag}
          onDragOver={handleDrag}
          onDrop={handleDrop}
          onClick={() => fileInputRef.current?.click()}
          className={`border-2 border-dashed rounded-xl p-6 text-center cursor-pointer transition-colors ${
            dragActive
              ? "border-evidexa-cyan bg-evidexa-cyan/10"
              : "border-evidexa-slate bg-evidexa-midnight/60 hover:border-slate-500"
          }`}
        >
          <input
            ref={fileInputRef}
            type="file"
            className="hidden"
            accept=".pdf,.png,.jpg,.jpeg,.tiff,.tif,application/pdf,image/png,image/jpeg,image/tiff"
            onChange={(e) => {
              if (e.target.files && e.target.files[0]) {
                handleFileSelection(e.target.files[0]);
              }
            }}
          />

          <div className="flex flex-col items-center gap-2">
            <div className="p-3 rounded-full bg-slate-800 text-slate-300">
              <UploadCloud className="w-8 h-8 text-evidexa-cyan" />
            </div>
            <div>
              <p className="text-sm font-semibold text-white">
                Drag and drop original evidence file here, or{" "}
                <span className="text-evidexa-aqua underline">browse</span>
              </p>
              <p className="text-xs text-slate-400 mt-1">
                Accepted: Digital PDF, Scanned PDF, PNG, JPEG, TIFF (Max 50 MB)
              </p>
            </div>
          </div>
        </div>

        {/* Selected file card */}
        {selectedFile && (
          <div className="p-3 rounded-lg bg-slate-900 border border-evidexa-slate flex items-center justify-between gap-3 text-xs">
            <div className="flex items-center gap-2.5 truncate">
              <File className="w-4 h-4 text-evidexa-cyan shrink-0" />
              <div className="truncate">
                <p className="font-semibold text-slate-200 truncate">{selectedFile.name}</p>
                <p className="text-[11px] text-slate-400 font-mono">
                  {(selectedFile.size / (1024 * 1024)).toFixed(2)} MB •{" "}
                  {selectedFile.type || "binary stream"}
                </p>
              </div>
            </div>
            <span className="shrink-0 px-2 py-0.5 rounded text-[10px] font-mono bg-emerald-950 text-emerald-300 border border-emerald-600 flex items-center gap-1">
              <CheckCircle className="w-3 h-3 text-emerald-400" />
              Ready
            </span>
          </div>
        )}

        {/* Lead Investigator */}
        <div>
          <label className="block text-xs font-semibold uppercase tracking-wider text-slate-300 mb-1">
            Examiner / Investigator Identifier
          </label>
          <input
            type="text"
            required
            value={investigatorId}
            onChange={(e) => setInvestigatorId(e.target.value)}
            className="w-full bg-evidexa-midnight border border-evidexa-slate rounded-md px-3 py-2 text-sm text-white placeholder-slate-500 focus:outline-none focus:ring-1 focus:ring-evidexa-cyan font-mono"
          />
          <p className="text-[11px] text-slate-400 mt-1">
            Recorded in the immutable cryptographic audit ledger upon document registration.
          </p>
        </div>

        {/* Automatic OCR Processing Options */}
        <div className="p-3 bg-evidexa-midnight/80 rounded border border-evidexa-slate space-y-2">
          <label className="flex items-center gap-2 cursor-pointer text-xs text-slate-200">
            <input
              type="checkbox"
              checked={autoRunOcr}
              onChange={(e) => setAutoRunOcr(e.target.checked)}
              className="rounded border-evidexa-slate text-evidexa-cyan focus:ring-0"
            />
            <span className="font-semibold text-white">Execute Forensic OCR Pipeline automatically upon upload</span>
          </label>
          {autoRunOcr && (
            <div className="pl-6 flex items-center gap-2 text-xs">
              <span className="text-slate-400">Engine:</span>
              <select
                value={selectedPipeline}
                onChange={(e: any) => setSelectedPipeline(e.target.value)}
                className="bg-evidexa-charcoal border border-evidexa-slate rounded px-2.5 py-1 text-xs text-white focus:outline-none focus:border-evidexa-cyan"
              >
                <option value="hybrid-ocr-pipeline">Hybrid OCR (English, Latin, Numbers, Standard Invoices)</option>
                <option value="ppocrv5-devanagari-engine">PP-OCRv5 Devanagari (Hindi, Sanskrit, Regional Indian Bills)</option>
              </select>
            </div>
          )}
        </div>

        {/* Forensic Policy Disclaimer */}
        <div className="p-3 bg-evidexa-midnight/80 rounded border border-evidexa-slate/60 flex items-start gap-2 text-[11px] text-slate-400 leading-relaxed">
          <ShieldCheck className="w-4 h-4 text-emerald-400 shrink-0 mt-0.5" />
          <span>
            <strong>Forensic Invariant:</strong> Client validation checks file size and extension. The backend authoritatively verifies magic bytes, computes SHA-256 digests in isolated storage, and checks for identical duplicates.
          </span>
        </div>

        {/* Modal Actions */}
        <div className="flex items-center justify-end gap-3 pt-3 border-t border-evidexa-slate">
          <Button type="button" variant="secondary" onClick={handleClose} disabled={isUploading}>
            Cancel
          </Button>
          <Button
            type="submit"
            variant="primary"
            isLoading={isUploading}
            disabled={!selectedFile || isUploading}
          >
            {uploadStage || "Ingest & Process Document"}
          </Button>
        </div>
      </form>
    </Modal>
  );
};

