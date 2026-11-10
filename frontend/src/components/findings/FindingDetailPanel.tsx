import React from "react";
import { Link } from "react-router-dom";
import {
  X,
  FileText,
  AlertTriangle,
  ShieldAlert,
  CheckCircle2,
  ExternalLink,
  UserCheck,
} from "lucide-react";
import { StatusBadge } from "../ui/Badge";
import type { AggregatedFinding } from "../../types/api";

interface FindingDetailPanelProps {
  finding: AggregatedFinding | null;
  onClose: () => void;
  caseId: string;
  onOpenReviewModal: () => void;
  isCaseArchived?: boolean;
}

export const FindingDetailPanel: React.FC<FindingDetailPanelProps> = ({
  finding,
  onClose,
  caseId,
  onOpenReviewModal,
  isCaseArchived = false,
}) => {
  if (!finding) return null;

  const epistemic = finding.evidentiary_classification || "AUTOMATED_INDICATOR";
  const reviewStatus = finding.review_status || (finding.is_reviewed ? "CONFIRMED" : "UNREVIEWED");

  return (
    <div className="w-full lg:w-[420px] xl:w-[460px] bg-brand-charcoal border border-brand-slate rounded-xl flex flex-col shadow-xl overflow-hidden shrink-0 max-h-[85vh]">
      {/* Top Header */}
      <div className="p-3.5 border-b border-brand-slate flex items-center justify-between bg-brand-midnight/60">
        <div className="flex items-center gap-2 min-w-0">
          <ShieldAlert className="w-4 h-4 text-brand-cyan shrink-0" />
          <span className="text-xs font-semibold text-white uppercase tracking-wider font-mono truncate">
            Finding Dossier Record
          </span>
        </div>

        <button
          type="button"
          onClick={onClose}
          className="p-1 rounded text-brand-slate-light hover:text-white hover:bg-brand-slate/50 transition-colors"
          title="Close details"
        >
          <X className="w-4 h-4" />
        </button>
      </div>

      {/* Scrollable Content */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4 text-xs text-slate-300">
        {/* Title & Epistemic Category */}
        <div className="space-y-2 pb-3 border-b border-brand-slate/60">
          <div className="flex flex-wrap items-center gap-2">
            <StatusBadge status={epistemic} type="epistemic" />
            <StatusBadge status={finding.severity} type="severity" />
            <StatusBadge status={reviewStatus} type="review" />
          </div>

          <h3 className="text-sm font-semibold text-white leading-snug">
            {finding.title}
          </h3>

          <div className="flex items-center gap-2 text-[10px] font-mono text-brand-slate-light">
            <span>ID: {finding.id}</span>
            <span>•</span>
            <span>Subsystem: {finding.source_type}</span>
          </div>
        </div>

        {/* Primary Description & Explanation */}
        <div className="space-y-1.5">
          <h4 className="text-[10px] font-mono font-semibold uppercase tracking-wider text-brand-slate-light">
            Forensic Observation
          </h4>
          <p className="p-2.5 rounded-lg bg-brand-midnight/60 border border-brand-slate/60 text-xs text-white leading-relaxed font-sans">
            {finding.description || "No narrative description recorded."}
          </p>

          {finding.explanation && (
            <p className="text-[11px] text-brand-slate-light italic font-sans px-1">
              {finding.explanation}
            </p>
          )}
        </div>

        {/* Confidence & Uncalibrated Heuristic Notice */}
        {finding.confidence !== null && finding.confidence !== undefined && (
          <div className="p-2.5 rounded-lg bg-brand-midnight/40 border border-brand-slate/50 space-y-1">
            <div className="flex items-center justify-between text-[11px] font-mono">
              <span className="text-brand-slate-light">Algorithm Signal Score:</span>
              <span className="text-amber-300 font-bold">{finding.confidence.toFixed(2)}</span>
            </div>
            <p className="text-[10px] text-slate-400 font-sans leading-tight">
              Signal score represents relative algorithmic ranking weight, not mathematical probability of intentional fraud.
            </p>
          </div>
        )}

        {/* Action Button: Adjudicate Finding */}
        <div className="pt-1">
          {isCaseArchived ? (
            <div className="p-2 rounded bg-amber-950/40 border border-amber-500/40 text-amber-300 text-[11px] text-center font-sans">
              Case is ARCHIVED. Adjudication of findings is restricted.
            </div>
          ) : (
            <button
              type="button"
              onClick={onOpenReviewModal}
              className="w-full inline-flex items-center justify-center gap-2 px-3 py-2 bg-brand-blue hover:bg-brand-blue-hover text-white text-xs font-medium rounded-lg transition-colors shadow-sm"
            >
              <UserCheck className="w-4 h-4" />
              <span>Adjudicate / Record Investigator Review</span>
            </button>
          )}
        </div>

        {/* Evidentiary Locations & Document Provenance */}
        <div className="space-y-2 pt-2 border-t border-brand-slate/60">
          <div className="flex items-center justify-between">
            <h4 className="text-[10px] font-mono font-semibold uppercase tracking-wider text-brand-slate-light">
              Evidentiary Provenance ({finding.locations?.length || 0})
            </h4>
          </div>

          {(!finding.locations || finding.locations.length === 0) && (
            <div className="p-2.5 rounded bg-brand-midnight/40 border border-brand-slate/40 text-[11px] text-slate-400">
              {finding.affected_document_ids && finding.affected_document_ids.length > 0 ? (
                <div className="space-y-1.5">
                  <p>Document references available without specific page coordinates:</p>
                  <div className="flex flex-wrap gap-1.5">
                    {finding.affected_document_ids.map((docId) => (
                      <Link
                        key={docId}
                        to={`/cases/${caseId}/documents/${docId}/examine`}
                        className="inline-flex items-center gap-1 px-2 py-1 rounded bg-brand-midnight border border-brand-slate text-[11px] text-brand-cyan hover:underline font-mono"
                      >
                        <FileText className="w-3 h-3" />
                        <span>Doc #{docId.slice(-6)}</span>
                        <ExternalLink className="w-2.5 h-2.5" />
                      </Link>
                    ))}
                  </div>
                </div>
              ) : (
                <span>No direct coordinate locations recorded for this finding.</span>
              )}
            </div>
          )}

          {finding.locations && finding.locations.length > 0 && (
            <div className="space-y-2">
              {finding.locations.map((loc, idx) => {
                const docId = loc.document_id;
                const pageNum = loc.page_number;
                const fieldName = loc.field_name;

                return (
                  <div
                    key={idx}
                    className="p-2.5 rounded-lg bg-brand-midnight/70 border border-brand-slate/60 space-y-1.5 font-mono text-[11px]"
                  >
                    <div className="flex items-center justify-between">
                      <span className="text-white font-medium">
                        {fieldName ? `Field: ${fieldName}` : `Location #${idx + 1}`}
                      </span>
                      {pageNum !== undefined && pageNum !== null && (
                        <span className="text-brand-cyan">Page {pageNum}</span>
                      )}
                    </div>

                    {docId && (
                      <div className="flex items-center justify-between text-[10px] text-slate-400">
                        <span className="truncate max-w-[200px]" title={docId}>
                          Doc ID: {docId}
                        </span>
                        <Link
                          to={`/cases/${caseId}/documents/${docId}/examine${
                            pageNum ? `?page=${pageNum}` : ""
                          }`}
                          className="inline-flex items-center gap-1 text-brand-cyan hover:underline"
                        >
                          <span>Examine Document</span>
                          <ExternalLink className="w-2.5 h-2.5" />
                        </Link>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Supporting & Contradictory Evidence References */}
        <div className="space-y-2 pt-2 border-t border-brand-slate/60">
          <h4 className="text-[10px] font-mono font-semibold uppercase tracking-wider text-brand-slate-light">
            Supporting & Contradictory Evidence
          </h4>

          <div className="grid grid-cols-2 gap-2 text-[11px]">
            {/* Supporting */}
            <div className="p-2.5 rounded-lg bg-emerald-950/20 border border-emerald-500/30 space-y-1">
              <div className="flex items-center gap-1 text-emerald-300 font-semibold text-[10px] uppercase font-mono">
                <CheckCircle2 className="w-3 h-3 text-emerald-400" />
                <span>Supporting ({finding.supporting_evidence_ids?.length || 0})</span>
              </div>
              {finding.supporting_evidence_ids && finding.supporting_evidence_ids.length > 0 ? (
                <ul className="list-disc list-inside text-[10px] text-slate-300 font-mono space-y-0.5">
                  {finding.supporting_evidence_ids.map((id) => (
                    <li key={id} className="truncate" title={id}>
                      #{id.slice(-8)}
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-[10px] text-slate-400 italic">No supporting keys</p>
              )}
            </div>

            {/* Contradicting */}
            <div className="p-2.5 rounded-lg bg-rose-950/20 border border-rose-500/30 space-y-1">
              <div className="flex items-center gap-1 text-rose-300 font-semibold text-[10px] uppercase font-mono">
                <AlertTriangle className="w-3 h-3 text-rose-400" />
                <span>Contradicting ({finding.contradicting_evidence_ids?.length || 0})</span>
              </div>
              {finding.contradicting_evidence_ids && finding.contradicting_evidence_ids.length > 0 ? (
                <ul className="list-disc list-inside text-[10px] text-rose-200 font-mono space-y-0.5">
                  {finding.contradicting_evidence_ids.map((id) => (
                    <li key={id} className="truncate" title={id}>
                      #{id.slice(-8)}
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-[10px] text-slate-400 italic">None reported</p>
              )}
            </div>
          </div>
        </div>

        {/* Known Limitations */}
        {finding.limitations && finding.limitations.length > 0 && (
          <div className="space-y-1.5 pt-2 border-t border-brand-slate/60">
            <h4 className="text-[10px] font-mono font-semibold uppercase tracking-wider text-amber-300/80">
              Investigative Limitations & Caveats
            </h4>
            <ul className="p-2.5 rounded-lg bg-amber-950/20 border border-amber-500/30 text-[11px] text-slate-300 list-disc list-inside space-y-1 font-sans">
              {finding.limitations.map((lim, idx) => (
                <li key={idx}>{lim}</li>
              ))}
            </ul>
          </div>
        )}

        {/* Append-Only Review History */}
        <div className="space-y-2 pt-2 border-t border-brand-slate/60">
          <div className="flex items-center justify-between">
            <h4 className="text-[10px] font-mono font-semibold uppercase tracking-wider text-brand-slate-light">
              Append-Only Review History ({finding.review_history?.length || 0})
            </h4>
          </div>

          {(!finding.review_history || finding.review_history.length === 0) ? (
            <p className="text-[11px] text-slate-500 italic p-2 rounded bg-brand-midnight/40 border border-brand-slate/30">
              No human reviews recorded yet. Finding remains in UNREVIEWED state.
            </p>
          ) : (
            <div className="space-y-2">
              {finding.review_history.map((rev) => (
                <div
                  key={rev.id}
                  className="p-2.5 rounded-lg bg-brand-midnight border border-brand-slate/70 space-y-1 text-xs"
                >
                  <div className="flex items-center justify-between text-[11px] font-mono">
                    <span className="font-semibold text-brand-cyan">{rev.action}</span>
                    <span className="text-slate-400 text-[10px]">
                      {new Date(rev.reviewed_at || rev.created_at || "").toLocaleString()}
                    </span>
                  </div>

                  <p className="text-slate-200 font-sans leading-relaxed pt-0.5">
                    {rev.comment || rev.rationale || "No commentary recorded"}
                  </p>

                  <div className="flex items-center justify-between pt-1 border-t border-brand-slate/40 text-[10px] font-mono text-slate-400">
                    <span>Reviewer: {rev.reviewer_id}</span>
                    <span>
                      {rev.previous_status || rev.prior_status} → {rev.new_status}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
