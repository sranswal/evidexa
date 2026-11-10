import React, { useState } from "react";
import {
  X,
  UserCheck,
  AlertTriangle,
  Loader2,
  CheckCircle2,
} from "lucide-react";
import type {
  AggregatedFinding,
  AggregatedFindingReview,
  InvestigatorReviewAction,
} from "../../types/api";
import { findingsApi } from "../../api/findings";

interface FindingReviewModalProps {
  isOpen: boolean;
  onClose: () => void;
  finding: AggregatedFinding | null;
  caseId: string;
  onSuccess: (newReview: AggregatedFindingReview) => void;
  isCaseArchived?: boolean;
}

const ACTION_DESCRIPTIONS: Record<
  InvestigatorReviewAction,
  { label: string; description: string; badgeColor: string }
> = {
  CONFIRM_OBSERVATION: {
    label: "Confirm Observation",
    description:
      "Examiner confirms the factual observation or anomaly is grounded in document evidence.",
    badgeColor: "text-emerald-300 border-emerald-500/40 bg-emerald-950/40",
  },
  DISMISS_FALSE_POSITIVE: {
    label: "Dismiss False Positive",
    description:
      "Examiner determines the indicator is a benign formatting variation, OCR artifact, or false signal.",
    badgeColor: "text-slate-400 border-slate-600 bg-slate-900",
  },
  MARK_INCONCLUSIVE: {
    label: "Mark Inconclusive",
    description:
      "Evidence is ambiguous or insufficient to confirm or refute the observation.",
    badgeColor: "text-amber-300 border-amber-500/40 bg-amber-950/40",
  },
  REQUEST_MORE_EVIDENCE: {
    label: "Request More Evidence",
    description:
      "Finding requires supplemental case documentation or secondary forensic re-examination.",
    badgeColor: "text-sky-300 border-sky-500/40 bg-sky-950/40",
  },
  MARK_NEEDS_REVIEW: {
    label: "Mark Needs Review",
    description:
      "Flags the finding for prioritized attention or senior forensic triage.",
    badgeColor: "text-orange-300 border-orange-500/40 bg-orange-950/40",
  },
};

export const FindingReviewModal: React.FC<FindingReviewModalProps> = ({
  isOpen,
  onClose,
  finding,
  caseId,
  onSuccess,
  isCaseArchived = false,
}) => {
  const [action, setAction] = useState<InvestigatorReviewAction>("CONFIRM_OBSERVATION");
  const [reviewerId, setReviewerId] = useState<string>("investigator-lead");
  const [rationale, setRationale] = useState<string>("");
  const [isConfirmed, setIsConfirmed] = useState<boolean>(false);

  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  if (!isOpen || !finding) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (isCaseArchived) {
      setError("Cannot record review decisions on an archived case.");
      return;
    }

    if (!reviewerId.trim()) {
      setError("Please provide a valid reviewer or investigator identifier.");
      return;
    }

    if (!rationale.trim()) {
      setError("Factual rationale is mandatory for recording an investigator review.");
      return;
    }

    if (!isConfirmed) {
      setError("Please explicitly check the confirmation acknowledgment before recording.");
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const review = await findingsApi.recordFindingReview(caseId, finding.id, {
        reviewer_id: reviewerId.trim(),
        action,
        rationale: rationale.trim(),
      });

      setLoading(false);
      onSuccess(review);
      onClose();
    } catch (err: any) {
      setLoading(false);
      setError(
        err?.message || "Failed to record investigator review. Please verify case authorization."
      );
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm select-none">
      <div className="w-full max-w-lg bg-brand-charcoal border border-brand-slate rounded-xl shadow-2xl flex flex-col overflow-hidden text-slate-200 text-xs animate-in zoom-in-95 duration-150">
        {/* Modal Header */}
        <div className="p-4 border-b border-brand-slate flex items-center justify-between bg-brand-midnight/60">
          <div className="flex items-center gap-2">
            <UserCheck className="w-4 h-4 text-brand-cyan" />
            <h3 className="text-sm font-semibold text-white">
              Record Investigator Review Adjudication
            </h3>
          </div>

          <button
            type="button"
            onClick={onClose}
            disabled={loading}
            className="p-1 rounded text-brand-slate-light hover:text-white hover:bg-brand-slate/50 transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Modal Body / Form */}
        <form onSubmit={handleSubmit} className="p-4 space-y-4 overflow-y-auto max-h-[80vh]">
          {/* Finding Subject Card */}
          <div className="p-3 rounded-lg bg-brand-midnight border border-brand-slate/70 space-y-1">
            <span className="text-[10px] font-mono uppercase tracking-wider text-brand-slate-light">
              Review Subject
            </span>
            <h4 className="font-semibold text-white text-xs">{finding.title}</h4>
            <div className="flex items-center gap-2 text-[10px] font-mono text-slate-400">
              <span>ID: #{finding.id.slice(-8)}</span>
              <span>•</span>
              <span>Current Status: {finding.review_status || "UNREVIEWED"}</span>
            </div>
          </div>

          {/* Action Choice */}
          <div className="space-y-1.5">
            <label className="block text-xs font-semibold text-white">
              Review Decision Action
            </label>
            <div className="space-y-1.5">
              {(Object.keys(ACTION_DESCRIPTIONS) as InvestigatorReviewAction[]).map((act) => {
                const isSelected = action === act;
                const info = ACTION_DESCRIPTIONS[act];

                return (
                  <label
                    key={act}
                    className={`flex items-start gap-2.5 p-2.5 rounded-lg border cursor-pointer transition-colors ${
                      isSelected
                        ? "bg-brand-midnight border-brand-cyan ring-1 ring-brand-cyan/40"
                        : "bg-brand-midnight/40 border-brand-slate/50 hover:bg-brand-midnight/80"
                    }`}
                  >
                    <input
                      type="radio"
                      name="review_action"
                      value={act}
                      checked={isSelected}
                      onChange={() => setAction(act)}
                      className="mt-0.5 text-brand-cyan focus:ring-0"
                    />
                    <div className="space-y-0.5">
                      <div className="font-semibold text-white text-xs flex items-center gap-2">
                        <span>{info.label}</span>
                        <span
                          className={`text-[9px] font-mono px-1.5 py-0.2 rounded border ${info.badgeColor}`}
                        >
                          {act}
                        </span>
                      </div>
                      <p className="text-[11px] text-slate-400 leading-snug">
                        {info.description}
                      </p>
                    </div>
                  </label>
                );
              })}
            </div>
          </div>

          {/* Reviewer Identifier */}
          <div className="space-y-1">
            <label className="block text-xs font-semibold text-white">
              Reviewer Identifier
            </label>
            <input
              type="text"
              value={reviewerId}
              onChange={(e) => setReviewerId(e.target.value)}
              placeholder="e.g. examiner-jones, senior-forensic-lead"
              className="w-full bg-brand-midnight border border-brand-slate rounded-lg px-3 py-1.5 text-xs text-white placeholder-brand-slate-light focus:outline-none focus:border-brand-cyan font-mono"
            />
            <p className="text-[10px] text-slate-400 font-sans">
              Asserted reviewer identity (unauthenticated development mode). Does not establish legal non-repudiation.
            </p>
          </div>

          {/* Mandatory Rationale */}
          <div className="space-y-1">
            <label className="block text-xs font-semibold text-white">
              Investigator Rationale & Justification <span className="text-rose-400">*</span>
            </label>
            <textarea
              rows={3}
              value={rationale}
              onChange={(e) => setRationale(e.target.value)}
              placeholder="Provide the factual basis, verification checks performed, or reason for this review decision..."
              className="w-full bg-brand-midnight border border-brand-slate rounded-lg p-2.5 text-xs text-white placeholder-brand-slate-light focus:outline-none focus:border-brand-cyan font-sans resize-none"
            />
          </div>

          {/* Acknowledgment Checkbox */}
          <label className="flex items-start gap-2 text-[11px] text-slate-300 cursor-pointer pt-1">
            <input
              type="checkbox"
              checked={isConfirmed}
              onChange={(e) => setIsConfirmed(e.target.checked)}
              className="mt-0.5 rounded border-brand-slate bg-brand-midnight text-brand-cyan focus:ring-0"
            />
            <span>
              I confirm this review decision reflects my independent evaluation of the evidence and will be recorded into the append-only case audit ledger.
            </span>
          </label>

          {/* Error Banner */}
          {error && (
            <div className="p-2.5 rounded bg-red-950/40 border border-red-500/40 text-rose-300 text-[11px] flex items-center gap-2">
              <AlertTriangle className="w-4 h-4 shrink-0" />
              <span>{error}</span>
            </div>
          )}

          {/* Submit Actions */}
          <div className="pt-2 border-t border-brand-slate/60 flex items-center justify-end gap-2">
            <button
              type="button"
              onClick={onClose}
              disabled={loading}
              className="px-3 py-1.5 rounded border border-brand-slate bg-brand-midnight text-slate-300 hover:text-white transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={loading || !rationale.trim() || !reviewerId.trim() || !isConfirmed || isCaseArchived}
              className="inline-flex items-center gap-1.5 px-4 py-1.5 bg-brand-blue hover:bg-brand-blue-hover text-white text-xs font-medium rounded transition-colors disabled:opacity-50"
            >
              {loading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <CheckCircle2 className="w-3.5 h-3.5" />}
              <span>Commit Review</span>
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
