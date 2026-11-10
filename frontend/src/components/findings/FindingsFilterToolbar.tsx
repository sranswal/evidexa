import React from "react";
import { Search, X, RotateCcw } from "lucide-react";
import type {
  FindingSeverity,
  EpistemicClassification,
} from "../../types/api";

export interface FindingsFilterState {
  search: string;
  epistemic: EpistemicClassification | "ALL";
  severity: FindingSeverity | "ALL";
  reviewStatus: string | "ALL";
  sourceType: string | "ALL";
}

interface FindingsFilterToolbarProps {
  filters: FindingsFilterState;
  onFiltersChange: (filters: FindingsFilterState) => void;
  totalCount: number;
  filteredCount: number;
}

export const FindingsFilterToolbar: React.FC<FindingsFilterToolbarProps> = ({
  filters,
  onFiltersChange,
  totalCount,
  filteredCount,
}) => {
  const isFiltered =
    Boolean(filters.search) ||
    filters.epistemic !== "ALL" ||
    filters.severity !== "ALL" ||
    filters.reviewStatus !== "ALL" ||
    filters.sourceType !== "ALL";

  const handleReset = () => {
    onFiltersChange({
      search: "",
      epistemic: "ALL",
      severity: "ALL",
      reviewStatus: "ALL",
      sourceType: "ALL",
    });
  };

  return (
    <div className="bg-brand-charcoal border border-brand-slate rounded-xl p-3 shadow-sm space-y-3">
      {/* Top Search & Filter Bar */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        {/* Search Input */}
        <div className="relative flex-1 min-w-[240px] max-w-md">
          <Search className="w-3.5 h-3.5 absolute left-3 top-1/2 -translate-y-1/2 text-brand-slate-light" />
          <input
            type="text"
            value={filters.search}
            onChange={(e) => onFiltersChange({ ...filters, search: e.target.value })}
            placeholder="Search findings by title, description, rule..."
            className="w-full bg-brand-midnight border border-brand-slate rounded-lg pl-9 pr-8 py-1.5 text-xs text-white placeholder-brand-slate-light focus:outline-none focus:border-brand-cyan font-sans"
          />
          {filters.search && (
            <button
              type="button"
              onClick={() => onFiltersChange({ ...filters, search: "" })}
              className="absolute right-2.5 top-1/2 -translate-y-1/2 text-brand-slate-light hover:text-white"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          )}
        </div>

        {/* Filter Dropdowns */}
        <div className="flex flex-wrap items-center gap-2 text-xs">
          {/* Epistemic Classification */}
          <div className="flex items-center gap-1.5">
            <span className="text-[11px] font-mono text-brand-slate-light">Epistemic:</span>
            <select
              aria-label="Filter by Epistemic Classification"
              value={filters.epistemic}
              onChange={(e) =>
                onFiltersChange({
                  ...filters,
                  epistemic: e.target.value as EpistemicClassification | "ALL",
                })
              }
              className="bg-brand-midnight border border-brand-slate rounded px-2.5 py-1 text-xs text-white focus:outline-none focus:border-brand-cyan font-sans"
            >
              <option value="ALL">All Classifications</option>
              <option value="OBSERVED_FACT">Observed Fact</option>
              <option value="AUTOMATED_INDICATOR">Automated Indicator</option>
              <option value="ANALYTICAL_INTERPRETATION">Analytical Interpretation</option>
              <option value="INVESTIGATOR_CONCLUSION">Investigator Conclusion</option>
            </select>
          </div>

          {/* Severity */}
          <div className="flex items-center gap-1.5">
            <span className="text-[11px] font-mono text-brand-slate-light">Severity:</span>
            <select
              aria-label="Filter by Severity"
              value={filters.severity}
              onChange={(e) =>
                onFiltersChange({
                  ...filters,
                  severity: e.target.value as FindingSeverity | "ALL",
                })
              }
              className="bg-brand-midnight border border-brand-slate rounded px-2.5 py-1 text-xs text-white focus:outline-none focus:border-brand-cyan font-sans"
            >
              <option value="ALL">All Severities</option>
              <option value="CRITICAL">Critical</option>
              <option value="HIGH">High</option>
              <option value="MEDIUM">Medium</option>
              <option value="LOW">Low</option>
              <option value="INFORMATIONAL">Informational</option>
            </select>
          </div>

          {/* Review Status */}
          <div className="flex items-center gap-1.5">
            <span className="text-[11px] font-mono text-brand-slate-light">Review:</span>
            <select
              aria-label="Filter by Review Status"
              value={filters.reviewStatus}
              onChange={(e) =>
                onFiltersChange({
                  ...filters,
                  reviewStatus: e.target.value,
                })
              }
              className="bg-brand-midnight border border-brand-slate rounded px-2.5 py-1 text-xs text-white focus:outline-none focus:border-brand-cyan font-sans"
            >
              <option value="ALL">All Review Statuses</option>
              <option value="UNREVIEWED">Unreviewed</option>
              <option value="CONFIRM_OBSERVATION">Confirmed</option>
              <option value="DISMISS_FALSE_POSITIVE">Dismissed</option>
              <option value="MARK_INCONCLUSIVE">Inconclusive</option>
              <option value="REQUEST_MORE_EVIDENCE">Needs More Evidence</option>
              <option value="MARK_NEEDS_REVIEW">Needs Review</option>
            </select>
          </div>

          {/* Subsystem Source */}
          <div className="flex items-center gap-1.5">
            <span className="text-[11px] font-mono text-brand-slate-light">Source:</span>
            <select
              aria-label="Filter by Source Subsystem"
              value={filters.sourceType}
              onChange={(e) =>
                onFiltersChange({
                  ...filters,
                  sourceType: e.target.value,
                })
              }
              className="bg-brand-midnight border border-brand-slate rounded px-2.5 py-1 text-xs text-white focus:outline-none focus:border-brand-cyan font-sans"
            >
              <option value="ALL">All Subsystems</option>
              <option value="FORENSIC_FINDING">Forensic Findings</option>
              <option value="CONSISTENCY_FINDING">Consistency Engine</option>
              <option value="RELATIONSHIP_ANOMALY">Relationship Anomalies</option>
              <option value="ENTITY_IDENTITY_CONFLICT">Identity Conflicts</option>
            </select>
          </div>

          {isFiltered && (
            <button
              type="button"
              onClick={handleReset}
              className="inline-flex items-center gap-1 px-2.5 py-1 rounded bg-brand-slate/40 hover:bg-brand-slate/60 text-slate-300 hover:text-white transition-colors font-mono text-[11px]"
              title="Reset all filters"
            >
              <RotateCcw className="w-3 h-3 text-brand-cyan" />
              <span>Reset</span>
            </button>
          )}
        </div>
      </div>

      {/* Filter Statistics */}
      <div className="flex items-center justify-between text-[11px] font-mono text-brand-slate-light pt-2 border-t border-brand-slate/50">
        <div className="flex items-center gap-2">
          <span>
            Showing <strong className="text-white">{filteredCount}</strong> of{" "}
            <strong className="text-white">{totalCount}</strong> findings
          </span>
          {isFiltered && (
            <span className="px-1.5 py-0.2 rounded bg-brand-cyan/15 text-brand-cyan border border-brand-cyan/30 text-[10px]">
              Filtered
            </span>
          )}
        </div>

        <div className="flex items-center gap-3">
          <span>Triage View</span>
        </div>
      </div>
    </div>
  );
};
