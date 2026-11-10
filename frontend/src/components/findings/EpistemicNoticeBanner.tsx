import React, { useState } from "react";
import {
  ShieldAlert,
  ChevronDown,
  ChevronUp,
  FileText,
  Cpu,
  GitFork,
  ShieldCheck,
} from "lucide-react";

export const EpistemicNoticeBanner: React.FC = () => {
  const [isExpanded, setIsExpanded] = useState<boolean>(false);

  return (
    <div className="bg-brand-charcoal/90 border border-brand-slate rounded-xl p-4 shadow-sm text-xs select-text">
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-start gap-2.5">
          <ShieldAlert className="w-4 h-4 text-amber-400 shrink-0 mt-0.5" />
          <div>
            <p className="font-medium text-slate-200 leading-relaxed">
              <span className="font-semibold text-white">Forensic Triage Notice:</span>{" "}
              Automated findings support investigative triage. They are not independent determinations of fraud or misconduct. Conclusions require investigator review and supporting evidence.
            </p>
            <p className="text-[11px] text-brand-slate-light mt-1">
              EVIDEXA distinguishes between observed physical facts, automated anomaly indicators, cross-document interpretations, and human investigator conclusions.
            </p>
          </div>
        </div>

        <button
          type="button"
          onClick={() => setIsExpanded(!isExpanded)}
          className="inline-flex items-center gap-1 text-[11px] font-mono text-brand-cyan hover:underline shrink-0 pt-0.5"
          aria-expanded={isExpanded}
        >
          <span>{isExpanded ? "Hide Epistemic Guide" : "Epistemic Guide"}</span>
          {isExpanded ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
        </button>
      </div>

      {isExpanded && (
        <div className="mt-3 pt-3 border-t border-brand-slate/60 grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3 animate-in fade-in duration-200">
          {/* Observed Fact */}
          <div className="p-2.5 rounded-lg bg-brand-midnight/70 border border-cyan-500/30 space-y-1">
            <div className="flex items-center gap-1.5 text-cyan-300 font-mono font-semibold text-[11px]">
              <FileText className="w-3.5 h-3.5 text-cyan-400 shrink-0" />
              <span>OBSERVED FACT</span>
            </div>
            <p className="text-[11px] text-slate-300 leading-snug">
              Directly verifiable physical or digital evidence extracted from document bytes, metadata, or layout structure without algorithmic speculation.
            </p>
          </div>

          {/* Automated Indicator */}
          <div className="p-2.5 rounded-lg bg-brand-midnight/70 border border-amber-500/30 space-y-1">
            <div className="flex items-center gap-1.5 text-amber-300 font-mono font-semibold text-[11px]">
              <Cpu className="w-3.5 h-3.5 text-amber-400 shrink-0" />
              <span>AUTOMATED INDICATOR</span>
            </div>
            <p className="text-[11px] text-slate-300 leading-snug">
              Machine-generated anomaly signals (e.g. font substitution, ELA compression differences, OCR token misalignment). Requires human review.
            </p>
          </div>

          {/* Analytical Interpretation */}
          <div className="p-2.5 rounded-lg bg-brand-midnight/70 border border-purple-500/30 space-y-1">
            <div className="flex items-center gap-1.5 text-purple-300 font-mono font-semibold text-[11px]">
              <GitFork className="w-3.5 h-3.5 text-purple-400 shrink-0" />
              <span>ANALYTICAL INTERPRETATION</span>
            </div>
            <p className="text-[11px] text-slate-300 leading-snug">
              Deductive cross-document correlation or rule engine evaluation (e.g. invoice vs receipt total mismatch, temporal ordering contradictions).
            </p>
          </div>

          {/* Investigator Conclusion */}
          <div className="p-2.5 rounded-lg bg-brand-midnight/70 border border-emerald-500/30 space-y-1">
            <div className="flex items-center gap-1.5 text-emerald-300 font-mono font-semibold text-[11px]">
              <ShieldCheck className="w-3.5 h-3.5 text-emerald-400 shrink-0" />
              <span>INVESTIGATOR CONCLUSION</span>
            </div>
            <p className="text-[11px] text-slate-300 leading-snug">
              Formal adjudication asserted by a human examiner with recorded rationale, entered into the append-only case audit ledger.
            </p>
          </div>
        </div>
      )}
    </div>
  );
};
