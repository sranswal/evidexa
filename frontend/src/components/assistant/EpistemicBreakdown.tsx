import React, { useState } from "react";
import { CheckCircle2, Activity, Network, AlertTriangle, HelpCircle, Info, ChevronDown, ChevronRight } from "lucide-react";

interface EpistemicBreakdownProps {
  observedFacts: string[];
  automatedIndicators: string[];
  analyticalInterpretations: string[];
  contradictoryEvidence: string[];
  unresolvedQuestions: string[];
  limitations: string[];
}

export const EpistemicBreakdown: React.FC<EpistemicBreakdownProps> = ({
  observedFacts,
  automatedIndicators,
  analyticalInterpretations,
  contradictoryEvidence,
  unresolvedQuestions,
  limitations,
}) => {
  const [isExpanded, setIsExpanded] = useState<boolean>(true);

  const totalPoints =
    observedFacts.length +
    automatedIndicators.length +
    analyticalInterpretations.length +
    contradictoryEvidence.length +
    unresolvedQuestions.length +
    limitations.length;

  if (totalPoints === 0) {
    return null;
  }

  return (
    <div className="mt-4 border border-evidexa-slate/80 rounded-lg bg-evidexa-charcoal/60 overflow-hidden">
      <button
        type="button"
        onClick={() => setIsExpanded(!isExpanded)}
        className="w-full px-4 py-2.5 flex items-center justify-between text-xs font-mono font-semibold text-slate-300 hover:bg-slate-800/40 transition-colors"
      >
        <div className="flex items-center gap-2">
          {isExpanded ? <ChevronDown className="w-4 h-4 text-evidexa-cyan" /> : <ChevronRight className="w-4 h-4 text-slate-400" />}
          <span className="text-slate-200">Epistemic Evidence Breakdown</span>
          <span className="px-1.5 py-0.2 rounded text-[10px] bg-slate-800 text-slate-400 border border-slate-700">
            {totalPoints} attributes
          </span>
        </div>
        <span className="text-[11px] text-slate-400 font-normal">
          {isExpanded ? "Collapse" : "Expand"}
        </span>
      </button>

      {isExpanded && (
        <div className="p-4 border-t border-evidexa-slate/80 space-y-4 text-xs">
          {/* 1. Observed Facts */}
          {observedFacts.length > 0 && (
            <div>
              <div className="flex items-center gap-1.5 mb-1.5 text-emerald-400 font-mono font-semibold">
                <CheckCircle2 className="w-3.5 h-3.5" />
                <span>Observed Facts ({observedFacts.length})</span>
              </div>
              <ul className="space-y-1 pl-5 list-disc text-slate-300">
                {observedFacts.map((fact, i) => (
                  <li key={i} className="leading-relaxed">
                    {fact}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* 2. Automated Indicators */}
          {automatedIndicators.length > 0 && (
            <div>
              <div className="flex items-center gap-1.5 mb-1.5 text-evidexa-cyan font-mono font-semibold">
                <Activity className="w-3.5 h-3.5" />
                <span>Automated Algorithmic Indicators ({automatedIndicators.length})</span>
              </div>
              <ul className="space-y-1 pl-5 list-disc text-slate-300">
                {automatedIndicators.map((ind, i) => (
                  <li key={i} className="leading-relaxed">
                    {ind}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* 3. Analytical Interpretations */}
          {analyticalInterpretations.length > 0 && (
            <div>
              <div className="flex items-center gap-1.5 mb-1.5 text-indigo-400 font-mono font-semibold">
                <Network className="w-3.5 h-3.5" />
                <span>Analytical Interpretations ({analyticalInterpretations.length})</span>
              </div>
              <ul className="space-y-1 pl-5 list-disc text-slate-300">
                {analyticalInterpretations.map((interp, i) => (
                  <li key={i} className="leading-relaxed">
                    {interp}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* 4. Contradictory Evidence */}
          {contradictoryEvidence.length > 0 && (
            <div className="p-2.5 rounded-md bg-rose-950/30 border border-rose-900/60">
              <div className="flex items-center gap-1.5 mb-1.5 text-rose-400 font-mono font-semibold">
                <AlertTriangle className="w-3.5 h-3.5" />
                <span>Contradictory Evidence & Inconsistencies ({contradictoryEvidence.length})</span>
              </div>
              <ul className="space-y-1 pl-5 list-disc text-rose-200/90">
                {contradictoryEvidence.map((contra, i) => (
                  <li key={i} className="leading-relaxed">
                    {contra}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* 5. Unresolved Questions */}
          {unresolvedQuestions.length > 0 && (
            <div className="p-2.5 rounded-md bg-amber-950/30 border border-amber-900/60">
              <div className="flex items-center gap-1.5 mb-1.5 text-amber-400 font-mono font-semibold">
                <HelpCircle className="w-3.5 h-3.5" />
                <span>Unresolved Questions & Evidence Gaps ({unresolvedQuestions.length})</span>
              </div>
              <ul className="space-y-1 pl-5 list-disc text-amber-200/90">
                {unresolvedQuestions.map((q, i) => (
                  <li key={i} className="leading-relaxed">
                    {q}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* 6. Limitations */}
          {limitations.length > 0 && (
            <div>
              <div className="flex items-center gap-1.5 mb-1.5 text-slate-400 font-mono font-semibold">
                <Info className="w-3.5 h-3.5" />
                <span>Analytical Limitations & Caveats ({limitations.length})</span>
              </div>
              <ul className="space-y-1 pl-5 list-disc text-slate-400">
                {limitations.map((lim, i) => (
                  <li key={i} className="leading-relaxed">
                    {lim}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

