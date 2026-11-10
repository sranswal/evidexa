import React, { useState } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import {
  X,
  Download,
  Copy,
  Check,
  Calendar,
  User,
  ShieldCheck,
  AlertTriangle,
  History,
  Tag,
  Table,
  FileText,
} from "lucide-react";
import { Button } from "../ui/Button";
import { StatusBadge } from "../ui/Badge";
import { Skeleton } from "../ui/Skeleton";
import { ProcessingControls } from "./ProcessingControls";
import { documentsApi } from "../../api/documents";
import type { DocumentItem } from "../../types/api";

export interface DocumentDetailDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  caseId: string;
  document: DocumentItem | null;
  isCaseArchived?: boolean;
  onRefreshDocumentList: () => void;
}

export const DocumentDetailDrawer: React.FC<DocumentDetailDrawerProps> = ({
  isOpen,
  onClose,
  caseId,
  document,
  isCaseArchived = false,
  onRefreshDocumentList,
}) => {
  const [activeTab, setActiveTab] = useState<"metadata" | "actions" | "history" | "findings">("metadata");
  const [copiedHash, setCopiedHash] = useState(false);

  // Queries for document details
  const {
    data: runsData,
    isLoading: isRunsLoading,
    refetch: refetchRuns,
  } = useQuery({
    queryKey: ["document-runs", caseId, document?.id],
    queryFn: () => (document ? documentsApi.listDocumentRuns(caseId, document.id) : null),
    enabled: isOpen && !!document,
  });

  const {
    data: findingsData,
    isLoading: isFindingsLoading,
    refetch: refetchFindings,
  } = useQuery({
    queryKey: ["document-findings", caseId, document?.id],
    queryFn: () => (document ? documentsApi.listDocumentFindings(caseId, document.id) : null),
    enabled: isOpen && !!document,
  });

  const {
    data: classificationData,
    refetch: refetchClassification,
  } = useQuery({
    queryKey: ["document-classification", caseId, document?.id],
    queryFn: () => (document ? documentsApi.getClassification(caseId, document.id).catch(() => null) : null),
    enabled: isOpen && !!document,
  });

  const {
    data: extractionData,
    refetch: refetchExtraction,
  } = useQuery({
    queryKey: ["document-extraction", caseId, document?.id],
    queryFn: () => (document ? documentsApi.getExtraction(caseId, document.id).catch(() => null) : null),
    enabled: isOpen && !!document,
  });

  if (!isOpen || !document) return null;

  const handleCopyHash = () => {
    navigator.clipboard.writeText(document.sha256);
    setCopiedHash(true);
    setTimeout(() => setCopiedHash(false), 2000);
  };

  const handleOperationComplete = () => {
    refetchRuns();
    refetchFindings();
    refetchClassification();
    refetchExtraction();
    onRefreshDocumentList();
  };

  const runs = runsData?.items || [];
  const findings = findingsData?.items || [];
  const duplicateOf = document.metadata?.duplicate_of_document_id as string | undefined;

  return (
    <div
      className="fixed inset-0 z-50 flex justify-end bg-black/75 backdrop-blur-sm transition-opacity"
      role="dialog"
      aria-modal="true"
      aria-labelledby="drawer-title"
    >
      <div className="relative w-full max-w-2xl bg-evidexa-charcoal border-l border-evidexa-slate shadow-2xl h-full flex flex-col overflow-hidden">
        {/* Drawer Header */}
        <div className="p-5 border-b border-evidexa-slate flex items-start justify-between gap-4 bg-evidexa-midnight/80">
          <div className="space-y-1 truncate">
            <div className="flex items-center gap-2">
              <span className="font-mono text-xs font-bold text-evidexa-cyan">
                {document.id}
              </span>
              <StatusBadge status={document.ingestion_status} type="ingestion" />
              {classificationData && (
                <span className="px-2 py-0.5 rounded text-[10px] font-mono bg-blue-950 text-blue-300 border border-blue-600">
                  {classificationData.effective_class}
                </span>
              )}
            </div>
            <h2 id="drawer-title" className="text-lg font-bold text-white tracking-tight truncate">
              {document.original_filename}
            </h2>
          </div>

          <div className="flex items-center gap-2 shrink-0">
            <a
              href={`/api/v1/cases/${caseId}/documents/${document.id}/download`}
              download={document.original_filename}
              className="p-1.5 rounded-md hover:bg-slate-800 text-slate-300 hover:text-white transition-colors"
              title="Download original file"
            >
              <Download className="w-5 h-5 text-evidexa-aqua" />
            </a>
            <button
              onClick={onClose}
              className="p-1.5 rounded-md hover:bg-slate-800 text-slate-400 hover:text-white transition-colors"
              aria-label="Close drawer"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* Tab Navigation */}
        <div className="flex border-b border-evidexa-slate bg-evidexa-midnight/50 px-5 gap-4 overflow-x-auto">
          {(
            [
              { id: "metadata", label: "Metadata & Hash" },
              { id: "actions", label: "Processing Controls" },
              { id: "history", label: `Runs (${runs.length})` },
              { id: "findings", label: `Findings (${findings.length})` },
            ] as const
          ).map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`py-3 text-xs font-mono font-medium transition-colors border-b-2 shrink-0 ${
                activeTab === tab.id
                  ? "border-evidexa-cyan text-evidexa-cyan font-semibold"
                  : "border-transparent text-slate-400 hover:text-slate-200"
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {/* Drawer Body */}
        <div className="flex-1 p-6 overflow-y-auto space-y-6">
          {/* TAB 1: METADATA & PROVENANCE */}
          {activeTab === "metadata" && (
            <div className="space-y-4">
              {/* Duplicate alert if applicable */}
              {duplicateOf && (
                <div className="p-3.5 rounded-lg bg-amber-950/40 border border-amber-500/50 text-xs text-amber-300 flex items-start gap-2.5">
                  <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0 mt-0.5" />
                  <div>
                    <span className="font-semibold block mb-0.5">SHA-256 Byte-Identical Duplicate</span>
                    <span>
                      Identical to prior document{" "}
                      <span className="font-mono text-white">{duplicateOf}</span>. Preserved as a distinct evidentiary submission without discarding history.
                    </span>
                  </div>
                </div>
              )}

              {/* SHA-256 Digest Box */}
              <div className="p-4 bg-evidexa-midnight rounded-lg border border-evidexa-slate">
                <div className="flex items-center justify-between mb-1.5">
                  <span className="text-[11px] font-mono uppercase tracking-wider text-slate-400 font-semibold flex items-center gap-1.5">
                    <ShieldCheck className="w-3.5 h-3.5 text-emerald-400" />
                    Cryptographic SHA-256 Digest
                  </span>
                  <button
                    onClick={handleCopyHash}
                    className="text-xs text-evidexa-aqua hover:underline flex items-center gap-1 font-mono"
                  >
                    {copiedHash ? (
                      <>
                        <Check className="w-3.5 h-3.5 text-emerald-400" /> Copied
                      </>
                    ) : (
                      <>
                        <Copy className="w-3.5 h-3.5" /> Copy Digest
                      </>
                    )}
                  </button>
                </div>
                <p className="font-mono text-xs text-slate-200 break-all bg-slate-900 p-2.5 rounded border border-slate-800 select-all">
                  {document.sha256}
                </p>
              </div>

              {/* Metadata Grid */}
              <div className="grid grid-cols-2 gap-3 text-xs font-mono">
                <div className="p-3 bg-evidexa-midnight/60 rounded border border-evidexa-slate/60">
                  <span className="text-slate-400 block text-[10px] uppercase">Media Type</span>
                  <span className="text-slate-200">{document.media_type}</span>
                </div>
                <div className="p-3 bg-evidexa-midnight/60 rounded border border-evidexa-slate/60">
                  <span className="text-slate-400 block text-[10px] uppercase">File Size</span>
                  <span className="text-slate-200">
                    {(document.file_size_bytes / 1024).toFixed(1)} KB ({document.file_size_bytes.toLocaleString()} bytes)
                  </span>
                </div>
                <div className="p-3 bg-evidexa-midnight/60 rounded border border-evidexa-slate/60">
                  <span className="text-slate-400 block text-[10px] uppercase">Page Count</span>
                  <span className="text-slate-200">
                    {document.page_count !== null ? `${document.page_count} pages` : "Unparsed"}
                  </span>
                </div>
                <div className="p-3 bg-evidexa-midnight/60 rounded border border-evidexa-slate/60">
                  <span className="text-slate-400 block text-[10px] uppercase">Extension</span>
                  <span className="text-slate-200">{document.file_extension}</span>
                </div>
              </div>

              {/* Ingestion & Provenance Footer */}
              <div className="p-3 bg-evidexa-midnight/60 rounded border border-evidexa-slate/60 space-y-2 text-xs">
                <div className="flex items-center gap-2 text-slate-400">
                  <Calendar className="w-3.5 h-3.5 text-slate-500" />
                  <span>Ingested: {new Date(document.created_at).toLocaleString()}</span>
                </div>
                <div className="flex items-center gap-2 text-slate-400">
                  <User className="w-3.5 h-3.5 text-slate-500" />
                  <span>Lead Examiner: {document.created_by || "System Ingestion"}</span>
                </div>
              </div>
            </div>
          )}

          {/* TAB 2: PROCESSING CONTROLS */}
          {activeTab === "actions" && (
            <div className="space-y-4">
              <ProcessingControls
                caseId={caseId}
                document={document}
                isCaseArchived={isCaseArchived}
                onOperationComplete={handleOperationComplete}
              />
            </div>
          )}

          {/* TAB 3: PROCESSING RUNS HISTORY */}
          {activeTab === "history" && (
            <div className="space-y-3">
              {isRunsLoading && (
                <div className="space-y-2">
                  {[1, 2, 3].map((i) => (
                    <Skeleton key={i} className="h-16 w-full" />
                  ))}
                </div>
              )}

              {!isRunsLoading && runs.length === 0 && (
                <div className="p-6 text-center border border-dashed border-evidexa-slate rounded-lg text-slate-400 text-xs">
                  <History className="w-8 h-8 text-slate-500 mx-auto mb-2" />
                  No processing runs have been executed for this document yet. Switch to "Processing Controls" to run analysis.
                </div>
              )}

              {!isRunsLoading && runs.length > 0 && (
                <div className="space-y-2.5">
                  {runs.map((run) => (
                    <div
                      key={run.id}
                      className="p-3.5 rounded-lg bg-evidexa-midnight/80 border border-evidexa-slate text-xs space-y-1.5"
                    >
                      <div className="flex items-center justify-between">
                        <span className="font-semibold text-white">{run.pipeline_name}</span>
                        <span
                          className={`px-2 py-0.5 rounded text-[10px] font-mono ${
                            run.status === "SUCCEEDED"
                              ? "bg-emerald-950 text-emerald-300 border border-emerald-600"
                              : run.status === "FAILED"
                              ? "bg-rose-950 text-rose-300 border border-rose-600"
                              : "bg-slate-800 text-slate-300"
                          }`}
                        >
                          {run.status}
                        </span>
                      </div>
                      <div className="flex items-center justify-between text-[11px] text-slate-400 font-mono">
                        <span>Run: {run.id.slice(0, 8)}…</span>
                        <span>{new Date(run.started_at).toLocaleTimeString()}</span>
                      </div>
                      {run.error_message && (
                        <p className="text-[11px] text-rose-300 bg-rose-950/40 p-2 rounded border border-rose-900">
                          {run.error_message}
                        </p>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* TAB 4: FINDINGS & EXTRACTION */}
          {activeTab === "findings" && (
            <div className="space-y-5">
              {/* Classification Summary */}
              {classificationData && (
                <div className="p-3.5 rounded-lg bg-evidexa-midnight/80 border border-evidexa-slate space-y-2 text-xs">
                  <div className="flex items-center justify-between">
                    <span className="font-semibold text-white flex items-center gap-1.5">
                      <Tag className="w-4 h-4 text-amber-400" />
                      Classification Result
                    </span>
                    <span className="px-2 py-0.5 rounded text-[10px] font-mono bg-amber-950 text-amber-300 border border-amber-600">
                      {classificationData.effective_class}
                    </span>
                  </div>
                  <p className="text-[11px] text-slate-400 font-mono">
                    Deterministic score: {(classificationData.ranking_score * 100).toFixed(1)}% • Method: {classificationData.classification_method}
                  </p>
                </div>
              )}

              {/* Extraction Summary */}
              {extractionData && (
                <div className="p-3.5 rounded-lg bg-evidexa-midnight/80 border border-evidexa-slate space-y-2 text-xs">
                  <div className="flex items-center justify-between">
                    <span className="font-semibold text-white flex items-center gap-1.5">
                      <Table className="w-4 h-4 text-emerald-400" />
                      Structured Extraction ({Object.keys(extractionData.fields || {}).length} fields)
                    </span>
                    <span className="font-mono text-[10px] text-slate-400">
                      Schema: {extractionData.schema_id}
                    </span>
                  </div>
                  <div className="space-y-1.5 pt-1">
                    {Object.values(extractionData.fields || {}).slice(0, 5).map((f) => (
                      <div key={f.id} className="flex justify-between text-[11px] font-mono border-b border-slate-800 pb-1">
                        <span className="text-slate-400">{f.label || f.field_key}:</span>
                        <span className="text-slate-200 font-semibold">{String(f.normalized_value ?? f.raw_text)}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Findings list */}
              <div className="space-y-2.5">
                <h4 className="text-xs font-mono uppercase tracking-wider text-slate-400 font-semibold">
                  Detected Forensic Findings ({findings.length})
                </h4>

                {isFindingsLoading && (
                  <div className="space-y-2">
                    {[1, 2].map((i) => (
                      <Skeleton key={i} className="h-16 w-full" />
                    ))}
                  </div>
                )}

                {!isFindingsLoading && findings.length === 0 && (
                  <p className="text-xs text-slate-400 italic">No forensic anomalies recorded on this document.</p>
                )}

                {!isFindingsLoading && findings.length > 0 && (
                  <div className="space-y-2">
                    {findings.map((f) => (
                      <div
                        key={f.id}
                        className="p-3 rounded-lg bg-evidexa-midnight/80 border border-evidexa-slate space-y-1 text-xs"
                      >
                        <div className="flex items-center justify-between">
                          <StatusBadge status={f.severity} type="severity" />
                          <span className="font-mono text-[10px] text-slate-400">
                            Page {f.page_number || "All"}
                          </span>
                        </div>
                        <p className="font-semibold text-slate-200">{f.title}</p>
                        <p className="text-[11px] text-slate-400">{f.description}</p>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          )}
        </div>

        {/* Drawer Footer */}
        <div className="p-4 border-t border-evidexa-slate bg-evidexa-midnight/80 flex items-center justify-between text-xs">
          <Button variant="secondary" size="sm" onClick={onClose}>
            Close
          </Button>
          <div className="flex items-center gap-2">
            <Link to={`/cases/${caseId}/documents/${document.id}/examine`}>
              <Button variant="secondary" size="sm" className="border-brand-cyan/40 text-brand-cyan hover:bg-brand-cyan hover:text-brand-midnight">
                <FileText className="w-3.5 h-3.5 mr-1.5" />
                Examine in Viewer
              </Button>
            </Link>
            <a
              href={`/api/v1/cases/${caseId}/documents/${document.id}/download`}
              download={document.original_filename}
            >
              <Button variant="primary" size="sm">
                <Download className="w-3.5 h-3.5 mr-1.5" />
                Download Original
              </Button>
            </a>
          </div>
        </div>
      </div>
    </div>
  );
};
