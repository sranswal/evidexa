import React from "react";
import {
  FileText,
  ChevronRight,
  ShieldAlert,
} from "lucide-react";
import { StatusBadge } from "../ui/Badge";
import type { AggregatedFinding } from "../../types/api";

interface FindingsTableProps {
  findings: AggregatedFinding[];
  selectedFindingId: string | null;
  onSelectFinding: (finding: AggregatedFinding) => void;
  caseId?: string;
}

export const FindingsTable: React.FC<FindingsTableProps> = ({
  findings,
  selectedFindingId,
  onSelectFinding,
}) => {
  if (findings.length === 0) {
    return (
      <div className="p-8 text-center bg-brand-charcoal border border-brand-slate rounded-xl">
        <ShieldAlert className="w-8 h-8 text-slate-500 mx-auto mb-2 opacity-60" />
        <h4 className="text-sm font-semibold text-white mb-1">No Findings Match Filter Criteria</h4>
        <p className="text-xs text-brand-slate-light max-w-sm mx-auto">
          Adjust or reset your active filters to inspect aggregated case findings.
        </p>
      </div>
    );
  }

  return (
    <div className="bg-brand-charcoal border border-brand-slate rounded-xl overflow-hidden shadow-sm">
      <div className="overflow-x-auto">
        <table className="w-full text-left border-collapse text-xs">
          <thead>
            <tr className="border-b border-brand-slate bg-brand-midnight/60 font-mono text-[11px] text-brand-slate-light uppercase tracking-wider">
              <th className="py-2.5 px-3">Classification & Severity</th>
              <th className="py-2.5 px-3">Finding Title & Subsystem</th>
              <th className="py-2.5 px-3">Review Status</th>
              <th className="py-2.5 px-3">Affected Documents</th>
              <th className="py-2.5 px-3">Recorded</th>
              <th className="py-2.5 px-2 w-8"></th>
            </tr>
          </thead>
          <tbody className="divide-y divide-brand-slate/40">
            {findings.map((f) => {
              const isSelected = f.id === selectedFindingId;
              const epistemic = f.evidentiary_classification || "AUTOMATED_INDICATOR";
              const reviewStatus = f.review_status || (f.is_reviewed ? "CONFIRMED" : "UNREVIEWED");

              return (
                <tr
                  key={f.id}
                  onClick={() => onSelectFinding(f)}
                  className={`cursor-pointer transition-colors select-none ${isSelected
                      ? "bg-brand-midnight/90 ring-1 ring-inset ring-brand-cyan/50"
                      : "hover:bg-brand-midnight/40"
                    }`}
                >
                  {/* Classification & Severity */}
                  <td className="py-2.5 px-3 align-top whitespace-nowrap">
                    <div className="flex flex-col gap-1 items-start">
                      <StatusBadge status={epistemic} type="epistemic" />
                      <StatusBadge status={f.severity} type="severity" />
                    </div>
                  </td>

                  {/* Finding Title & Subsystem */}
                  <td className="py-2.5 px-3 align-top">
                    <div className="space-y-0.5">
                      <div className="font-medium text-white line-clamp-1 leading-snug">
                        {f.title}
                      </div>
                      <div className="text-[11px] text-brand-slate-light line-clamp-1">
                        {f.description || f.explanation || "No description recorded"}
                      </div>
                      <div className="flex items-center gap-2 pt-0.5 text-[10px] font-mono text-slate-400">
                        <span className="px-1.5 py-0.2 rounded bg-brand-midnight border border-brand-slate text-brand-slate-light">
                          {f.source_type || "FORENSIC"}
                        </span>
                        {f.source_id && (
                          <span title={f.source_id} className="text-slate-500 truncate max-w-[120px]">
                            #{f.source_id.slice(-8)}
                          </span>
                        )}
                      </div>
                    </div>
                  </td>

                  {/* Review Status */}
                  <td className="py-2.5 px-3 align-top whitespace-nowrap">
                    <div className="space-y-1">
                      <StatusBadge status={reviewStatus} type="review" />
                      {f.review_history && f.review_history.length > 0 && (
                        <div className="text-[10px] font-mono text-slate-400">
                          {f.review_history.length} review(s)
                        </div>
                      )}
                    </div>
                  </td>

                  {/* Affected Documents */}
                  <td className="py-2.5 px-3 align-top whitespace-nowrap font-mono text-[11px]">
                    {f.affected_document_ids && f.affected_document_ids.length > 0 ? (
                      <span className="inline-flex items-center gap-1 text-slate-300">
                        <FileText className="w-3.5 h-3.5 text-brand-cyan" />
                        <span>{f.affected_document_ids.length} doc(s)</span>
                      </span>
                    ) : (
                      <span className="text-slate-500">-</span>
                    )}
                  </td>

                  {/* Recorded Timestamp */}
                  <td className="py-2.5 px-3 align-top whitespace-nowrap font-mono text-[11px] text-slate-400">
                    <span title={new Date(f.created_at).toLocaleString()}>
                      {new Date(f.created_at).toLocaleDateString()}
                    </span>
                  </td>

                  {/* Action Chevron */}
                  <td className="py-2.5 px-2 align-middle text-right">
                    <ChevronRight
                      className={`w-4 h-4 transition-transform ${isSelected ? "text-brand-cyan translate-x-0.5" : "text-slate-600"
                        }`}
                    />
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
};
