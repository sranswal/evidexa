import React, { useState } from "react";
import {
  Cpu,
  FileSearch,
  ScanText,
  Tag,
  Table,
  CheckCircle2,
  AlertTriangle,
  Info,
} from "lucide-react";
import { Button } from "../ui/Button";
import { documentsApi } from "../../api/documents";
import type { DocumentItem } from "../../types/api";

export interface ProcessingControlsProps {
  caseId: string;
  document: DocumentItem;
  isCaseArchived?: boolean;
  onOperationComplete: () => void;
}

export const ProcessingControls: React.FC<ProcessingControlsProps> = ({
  caseId,
  document,
  isCaseArchived = false,
  onOperationComplete,
}) => {
  const [activeAction, setActiveAction] = useState<string | null>(null);
  const [actionSuccess, setActionSuccess] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  const isPdf =
    document.media_type === "application/pdf" ||
    document.file_extension.toLowerCase() === ".pdf";

  const handleRunAnalysis = async (analyzerId: string, label: string) => {
    setActiveAction(analyzerId);
    setActionSuccess(null);
    setActionError(null);

    try {
      const res = await documentsApi.analyzeDocument(caseId, document.id, analyzerId);
      setActionSuccess(
        `Completed ${label}: Run status ${res.processing_run.status} with ${res.findings.length} findings recorded.`
      );
      onOperationComplete();
    } catch (err: any) {
      setActionError(err.message || `Failed to execute ${label}.`);
    } finally {
      setActiveAction(null);
    }
  };

  const handleRunOcr = async () => {
    setActiveAction("ocr");
    setActionSuccess(null);
    setActionError(null);

    try {
      const res = await documentsApi.startOcr(caseId, document.id, "hybrid-ocr-pipeline");
      setActionSuccess(
        `OCR Completed: Run ${res.processing_run.status} (${res.summary.execution_duration_ms || 0} ms).`
      );
      onOperationComplete();
    } catch (err: any) {
      setActionError(err.message || "Failed to execute OCR pipeline.");
    } finally {
      setActiveAction(null);
    }
  };

  const handleRunClassification = async () => {
    setActiveAction("classify");
    setActionSuccess(null);
    setActionError(null);

    try {
      const res = await documentsApi.classifyDocument(caseId, document.id);
      setActionSuccess(
        `Classification Complete: Predicted ${res.predicted_class} (score: ${(res.ranking_score * 100).toFixed(1)}%).`
      );
      onOperationComplete();
    } catch (err: any) {
      setActionError(err.message || "Failed to classify document.");
    } finally {
      setActiveAction(null);
    }
  };

  const handleRunExtraction = async () => {
    setActiveAction("extract");
    setActionSuccess(null);
    setActionError(null);

    try {
      const res = await documentsApi.extractFields(caseId, document.id);
      const fieldsCount = Object.keys(res.fields || {}).length;
      setActionSuccess(
        `Structured Extraction Complete: Extracted ${fieldsCount} fields matching schema ${res.schema_id}.`
      );
      onOperationComplete();
    } catch (err: any) {
      setActionError(err.message || "Failed to extract structured fields.");
    } finally {
      setActiveAction(null);
    }
  };

  return (
    <div className="space-y-4">
      {/* Notifications */}
      {actionSuccess && (
        <div
          role="status"
          className="p-3 rounded-lg bg-emerald-950/60 border border-emerald-500/50 text-xs text-emerald-300 flex items-start gap-2"
        >
          <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0 mt-0.5" />
          <span>{actionSuccess}</span>
        </div>
      )}

      {actionError && (
        <div
          role="alert"
          className="p-3 rounded-lg bg-rose-950/60 border border-rose-500/50 text-xs text-rose-300 flex items-start gap-2"
        >
          <AlertTriangle className="w-4 h-4 text-rose-400 shrink-0 mt-0.5" />
          <span>{actionError}</span>
        </div>
      )}

      {isCaseArchived && (
        <div className="p-3 rounded bg-amber-950/40 border border-amber-500/40 text-xs text-amber-300 flex items-center gap-2">
          <Info className="w-4 h-4 text-amber-400 shrink-0" />
          <span>Case is ARCHIVED. Execution of new processing pipelines is restricted.</span>
        </div>
      )}

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        {/* 1. PDF Structural Forensics (PDF only) */}
        {isPdf && (
          <div className="p-3.5 bg-evidexa-midnight/80 border border-evidexa-slate rounded-lg flex flex-col justify-between space-y-3">
            <div>
              <div className="flex items-center gap-2 text-slate-200 font-semibold text-xs mb-1">
                <FileSearch className="w-4 h-4 text-evidexa-cyan" />
                <span>PDF Structural Forensics</span>
              </div>
              <p className="text-[11px] text-slate-400 leading-normal">
                Subprocess-isolated analysis of PDF trailer, font encoding tables, and incremental revisions.
              </p>
            </div>
            <Button
              variant="secondary"
              size="sm"
              disabled={isCaseArchived || !!activeAction}
              isLoading={activeAction === "pdf-structural-analyzer"}
              onClick={() =>
                handleRunAnalysis("pdf-structural-analyzer", "PDF Structural Analysis")
              }
            >
              Run Structural Forensics
            </Button>
          </div>
        )}

        {/* 2. Visual Forensics (ELA / Copy-Move) */}
        <div className="p-3.5 bg-evidexa-midnight/80 border border-evidexa-slate rounded-lg flex flex-col justify-between space-y-3">
          <div>
            <div className="flex items-center gap-2 text-slate-200 font-semibold text-xs mb-1">
              <Cpu className="w-4 h-4 text-purple-400" />
              <span>Error Level Analysis (ELA)</span>
            </div>
            <p className="text-[11px] text-slate-400 leading-normal">
              Detects compression discrepancies and spliced image patches across JPEG resaves.
            </p>
          </div>
          <Button
            variant="secondary"
            size="sm"
            disabled={isCaseArchived || !!activeAction}
            isLoading={activeAction === "ela-analyzer"}
            onClick={() => handleRunAnalysis("ela-analyzer", "Error Level Analysis")}
          >
            Run Visual ELA
          </Button>
        </div>

        {/* 3. Optical Character Recognition (OCR) */}
        <div className="p-3.5 bg-evidexa-midnight/80 border border-evidexa-slate rounded-lg flex flex-col justify-between space-y-3">
          <div>
            <div className="flex items-center gap-2 text-slate-200 font-semibold text-xs mb-1">
              <ScanText className="w-4 h-4 text-sky-400" />
              <span>Hybrid OCR Pipeline</span>
            </div>
            <p className="text-[11px] text-slate-400 leading-normal">
              Adaptive routing between PDFium digital vector text and RapidOCR neural ONNX optical engine.
            </p>
          </div>
          <Button
            variant="secondary"
            size="sm"
            disabled={isCaseArchived || !!activeAction}
            isLoading={activeAction === "ocr"}
            onClick={handleRunOcr}
          >
            Execute Hybrid OCR
          </Button>
        </div>

        {/* 4. Document Classification */}
        <div className="p-3.5 bg-evidexa-midnight/80 border border-evidexa-slate rounded-lg flex flex-col justify-between space-y-3">
          <div>
            <div className="flex items-center gap-2 text-slate-200 font-semibold text-xs mb-1">
              <Tag className="w-4 h-4 text-amber-400" />
              <span>Document Classification</span>
            </div>
            <p className="text-[11px] text-slate-400 leading-normal">
              Predicts document class (Invoice, Receipt, Bank Statement, PO, etc.) from OCR layout signals.
            </p>
          </div>
          <Button
            variant="secondary"
            size="sm"
            disabled={isCaseArchived || !!activeAction}
            isLoading={activeAction === "classify"}
            onClick={handleRunClassification}
          >
            Run Classifier
          </Button>
        </div>

        {/* 5. Structured Field Extraction */}
        <div className="p-3.5 bg-evidexa-midnight/80 border border-evidexa-slate rounded-lg flex flex-col justify-between space-y-3 sm:col-span-2">
          <div>
            <div className="flex items-center gap-2 text-slate-200 font-semibold text-xs mb-1">
              <Table className="w-4 h-4 text-emerald-400" />
              <span>Structured Field Extraction</span>
            </div>
            <p className="text-[11px] text-slate-400 leading-normal">
              Extracts schema-driven fields with Python Decimal financial precision, bounding boxes, and arithmetic validation.
            </p>
          </div>
          <Button
            variant="primary"
            size="sm"
            disabled={isCaseArchived || !!activeAction}
            isLoading={activeAction === "extract"}
            onClick={handleRunExtraction}
          >
            Extract Structured Fields
          </Button>
        </div>
      </div>
    </div>
  );
};
