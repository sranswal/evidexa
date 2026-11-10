import React from "react";
import {
  CheckCircle2,
  AlertTriangle,
  AlertCircle,
  HelpCircle,
  Clock,
  Eye,
  CheckCircle,
  Archive,
  Activity,
  Info,
  Flame,
  FileText,
  Cpu,
  GitFork,
  ShieldCheck,
  XCircle,
  FileQuestion,
} from "lucide-react";
import clsx from "clsx";
import type {
  CaseStatus,
  EvidentiaryClassification,
  EpistemicClassification,
  FindingSeverity,
  DossierStatus,
  IngestionStatus,
  InvestigatorReviewAction,
} from "../../types/api";

export interface StatusBadgeProps {
  status?:
    | CaseStatus
    | EvidentiaryClassification
    | EpistemicClassification
    | FindingSeverity
    | DossierStatus
    | IngestionStatus
    | InvestigatorReviewAction
    | string
    | null;
  type?: "case" | "evidentiary" | "epistemic" | "severity" | "dossier" | "ingestion" | "review" | "generic";
  className?: string;
}

export const StatusBadge: React.FC<StatusBadgeProps> = ({ status, type = "generic", className }) => {
  const normStatus = (status || "").toUpperCase();

  // Render Epistemic Classification
  if (
    type === "epistemic" ||
    [
      "OBSERVED_FACT",
      "AUTOMATED_INDICATOR",
      "ANALYTICAL_INTERPRETATION",
      "INVESTIGATOR_CONCLUSION",
    ].includes(normStatus)
  ) {
    switch (normStatus) {
      case "OBSERVED_FACT":
        return (
          <span
            className={clsx(
              "inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded text-xs font-mono font-medium bg-cyan-950/70 text-cyan-300 border border-cyan-500/40",
              className
            )}
            title="Epistemic Classification: Directly observed and verifiable in physical/digital source records."
          >
            <FileText className="w-3.5 h-3.5 text-cyan-400 shrink-0" aria-hidden="true" />
            <span>OBSERVED FACT</span>
          </span>
        );
      case "AUTOMATED_INDICATOR":
        return (
          <span
            className={clsx(
              "inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded text-xs font-mono font-medium bg-amber-950/70 text-amber-300 border border-amber-500/40",
              className
            )}
            title="Epistemic Classification: Algorithmic signal or anomaly flagged by automated analysis. Requires investigator adjudication."
          >
            <Cpu className="w-3.5 h-3.5 text-amber-400 shrink-0" aria-hidden="true" />
            <span>AUTOMATED INDICATOR</span>
          </span>
        );
      case "ANALYTICAL_INTERPRETATION":
        return (
          <span
            className={clsx(
              "inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded text-xs font-mono font-medium bg-purple-950/70 text-purple-300 border border-purple-500/40",
              className
            )}
            title="Epistemic Classification: Deductive cross-document correlation or consistency rule outcome."
          >
            <GitFork className="w-3.5 h-3.5 text-purple-400 shrink-0" aria-hidden="true" />
            <span>ANALYTICAL INTERPRETATION</span>
          </span>
        );
      case "INVESTIGATOR_CONCLUSION":
        return (
          <span
            className={clsx(
              "inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded text-xs font-mono font-semibold bg-emerald-950/80 text-emerald-300 border border-emerald-500/50",
              className
            )}
            title="Epistemic Classification: Human examiner evaluated and asserted conclusion."
          >
            <ShieldCheck className="w-3.5 h-3.5 text-emerald-400 shrink-0" aria-hidden="true" />
            <span>INVESTIGATOR CONCLUSION</span>
          </span>
        );
    }
  }

  // Render Human Review Status
  if (
    type === "review" ||
    [
      "UNREVIEWED",
      "CONFIRM_OBSERVATION",
      "CONFIRMED_OBSERVATION",
      "DISMISS_FALSE_POSITIVE",
      "DISMISSED",
      "MARK_INCONCLUSIVE",
      "INCONCLUSIVE",
      "REQUEST_MORE_EVIDENCE",
      "MORE_EVIDENCE_REQUESTED",
      "MARK_NEEDS_REVIEW",
      "NEEDS_REVIEW",
    ].includes(normStatus)
  ) {
    switch (normStatus) {
      case "CONFIRM_OBSERVATION":
      case "CONFIRMED_OBSERVATION":
        return (
          <span
            className={clsx(
              "inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-xs font-mono font-medium bg-emerald-950/60 text-emerald-300 border border-emerald-500/40",
              className
            )}
            title="Review Status: Confirmed by Human Investigator"
          >
            <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400 shrink-0" aria-hidden="true" />
            <span>CONFIRMED</span>
          </span>
        );
      case "DISMISS_FALSE_POSITIVE":
      case "DISMISSED":
        return (
          <span
            className={clsx(
              "inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-xs font-mono font-medium bg-slate-900/90 text-slate-400 border border-slate-700/60 line-through",
              className
            )}
            title="Review Status: Dismissed as False Positive"
          >
            <XCircle className="w-3.5 h-3.5 text-slate-500 shrink-0" aria-hidden="true" />
            <span>DISMISSED</span>
          </span>
        );
      case "MARK_INCONCLUSIVE":
      case "INCONCLUSIVE":
        return (
          <span
            className={clsx(
              "inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-xs font-mono font-medium bg-amber-950/60 text-amber-300 border border-amber-500/40",
              className
            )}
            title="Review Status: Marked Inconclusive"
          >
            <HelpCircle className="w-3.5 h-3.5 text-amber-400 shrink-0" aria-hidden="true" />
            <span>INCONCLUSIVE</span>
          </span>
        );
      case "REQUEST_MORE_EVIDENCE":
      case "MORE_EVIDENCE_REQUESTED":
        return (
          <span
            className={clsx(
              "inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-xs font-mono font-medium bg-sky-950/60 text-sky-300 border border-sky-500/40",
              className
            )}
            title="Review Status: Additional Evidence Requested"
          >
            <FileQuestion className="w-3.5 h-3.5 text-sky-400 shrink-0" aria-hidden="true" />
            <span>MORE EVIDENCE NEEDED</span>
          </span>
        );
      case "MARK_NEEDS_REVIEW":
      case "NEEDS_REVIEW":
        return (
          <span
            className={clsx(
              "inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-xs font-mono font-medium bg-orange-950/60 text-orange-300 border border-orange-500/40",
              className
            )}
            title="Review Status: Needs Investigator Review"
          >
            <Eye className="w-3.5 h-3.5 text-orange-400 shrink-0" aria-hidden="true" />
            <span>NEEDS REVIEW</span>
          </span>
        );
      case "UNREVIEWED":
      default:
        return (
          <span
            className={clsx(
              "inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-xs font-mono font-medium bg-slate-900 text-slate-400 border border-slate-700",
              className
            )}
            title="Review Status: Pending Human Evaluation"
          >
            <Clock className="w-3.5 h-3.5 text-slate-500 shrink-0" aria-hidden="true" />
            <span>UNREVIEWED</span>
          </span>
        );
    }
  }

  // Render case status
  if (type === "case" || ["ACTIVE", "DRAFT", "UNDER_REVIEW", "COMPLETED", "ARCHIVED"].includes(normStatus)) {
    switch (normStatus) {
      case "ACTIVE":
        return (
          <span
            className={clsx(
              "inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-mono font-medium bg-emerald-950/60 text-emerald-300 border border-emerald-500/40",
              className
            )}
            title="Status: Active Investigation"
          >
            <Activity className="w-3.5 h-3.5 text-emerald-400" aria-hidden="true" />
            <span>ACTIVE</span>
          </span>
        );
      case "UNDER_REVIEW":
        return (
          <span
            className={clsx(
              "inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-mono font-medium bg-amber-950/60 text-amber-300 border border-amber-500/40",
              className
            )}
            title="Status: Under Forensic Review"
          >
            <Eye className="w-3.5 h-3.5 text-amber-400" aria-hidden="true" />
            <span>UNDER REVIEW</span>
          </span>
        );
      case "COMPLETED":
        return (
          <span
            className={clsx(
              "inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-mono font-medium bg-blue-950/60 text-blue-300 border border-blue-500/40",
              className
            )}
            title="Status: Completed"
          >
            <CheckCircle className="w-3.5 h-3.5 text-blue-400" aria-hidden="true" />
            <span>COMPLETED</span>
          </span>
        );
      case "ARCHIVED":
        return (
          <span
            className={clsx(
              "inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-mono font-medium bg-slate-900/80 text-slate-400 border border-slate-700",
              className
            )}
            title="Status: Archived (Sealed Chain of Custody)"
          >
            <Archive className="w-3.5 h-3.5 text-slate-400" aria-hidden="true" />
            <span>ARCHIVED</span>
          </span>
        );
      case "DRAFT":
      default:
        return (
          <span
            className={clsx(
              "inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-mono font-medium bg-slate-800/80 text-slate-300 border border-slate-600",
              className
            )}
            title="Status: Draft Workspace"
          >
            <Clock className="w-3.5 h-3.5 text-slate-400" aria-hidden="true" />
            <span>DRAFT</span>
          </span>
        );
    }
  }

  // Render Evidentiary Classification
  if (
    type === "evidentiary" ||
    ["CONFIRMED", "CANDIDATE", "CONTRADICTED", "UNRESOLVED"].includes(normStatus)
  ) {
    switch (normStatus) {
      case "CONFIRMED":
        return (
          <span
            className={clsx(
              "inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded text-xs font-mono font-medium bg-emerald-950/60 text-emerald-300 border border-emerald-500/40",
              className
            )}
            title="Evidentiary Status: Confirmed by Evidence"
          >
            <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" aria-hidden="true" />
            <span>CONFIRMED</span>
          </span>
        );
      case "CANDIDATE":
        return (
          <span
            className={clsx(
              "inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded text-xs font-mono font-medium bg-amber-950/60 text-amber-300 border border-amber-500/40",
              className
            )}
            title="Evidentiary Status: Candidate Under Review"
          >
            <AlertCircle className="w-3.5 h-3.5 text-amber-400" aria-hidden="true" />
            <span>CANDIDATE</span>
          </span>
        );
      case "CONTRADICTED":
        return (
          <span
            className={clsx(
              "inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded text-xs font-mono font-medium bg-rose-950/60 text-rose-300 border border-rose-500/40",
              className
            )}
            title="Evidentiary Status: Contradicted Anomaly"
          >
            <AlertTriangle className="w-3.5 h-3.5 text-rose-400" aria-hidden="true" />
            <span>CONTRADICTED</span>
          </span>
        );
      case "UNRESOLVED":
      default:
        return (
          <span
            className={clsx(
              "inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded text-xs font-mono font-medium bg-slate-800/80 text-slate-400 border border-slate-700",
              className
            )}
            title="Evidentiary Status: Unresolved"
          >
            <HelpCircle className="w-3.5 h-3.5 text-slate-400" aria-hidden="true" />
            <span>UNRESOLVED</span>
          </span>
        );
    }
  }

  // Render Finding Severity
  if (
    type === "severity" ||
    ["CRITICAL", "HIGH", "MEDIUM", "LOW", "INFORMATIONAL"].includes(normStatus)
  ) {
    switch (normStatus) {
      case "CRITICAL":
        return (
          <span
            className={clsx(
              "inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-xs font-mono font-semibold bg-red-950/80 text-red-300 border border-red-500/50",
              className
            )}
            title="Severity: Critical"
          >
            <Flame className="w-3.5 h-3.5 text-red-400" aria-hidden="true" />
            <span>CRITICAL</span>
          </span>
        );
      case "HIGH":
        return (
          <span
            className={clsx(
              "inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-xs font-mono font-semibold bg-orange-950/70 text-orange-300 border border-orange-500/50",
              className
            )}
            title="Severity: High"
          >
            <AlertTriangle className="w-3.5 h-3.5 text-orange-400" aria-hidden="true" />
            <span>HIGH</span>
          </span>
        );
      case "MEDIUM":
        return (
          <span
            className={clsx(
              "inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-xs font-mono font-medium bg-amber-950/60 text-amber-300 border border-amber-500/40",
              className
            )}
            title="Severity: Medium"
          >
            <AlertCircle className="w-3.5 h-3.5 text-amber-400" aria-hidden="true" />
            <span>MEDIUM</span>
          </span>
        );
      case "LOW":
        return (
          <span
            className={clsx(
              "inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-xs font-mono font-medium bg-sky-950/60 text-sky-300 border border-sky-500/40",
              className
            )}
            title="Severity: Low"
          >
            <Info className="w-3.5 h-3.5 text-sky-400" aria-hidden="true" />
            <span>LOW</span>
          </span>
        );
      case "INFORMATIONAL":
      default:
        return (
          <span
            className={clsx(
              "inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-xs font-mono font-medium bg-slate-800 text-slate-400 border border-slate-700",
              className
            )}
            title="Severity: Informational"
          >
            <Info className="w-3.5 h-3.5 text-slate-400" aria-hidden="true" />
            <span>INFO</span>
          </span>
        );
    }
  }

  // Generic fallback
  return (
    <span
      className={clsx(
        "inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded text-xs font-mono font-medium bg-slate-800 text-slate-300 border border-slate-700",
        className
      )}
    >
      <span>{normStatus}</span>
    </span>
  );
};

