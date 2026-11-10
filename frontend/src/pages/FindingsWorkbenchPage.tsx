import React, { useState, useMemo } from "react";
import { useParams, Link } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ShieldAlert,
  ChevronLeft,
  Loader2,
  AlertTriangle,
  RefreshCw,
  FileCheck2,
} from "lucide-react";

import { casesApi } from "../api/cases";
import { findingsApi } from "../api/findings";
import { EpistemicNoticeBanner } from "../components/findings/EpistemicNoticeBanner";
import {
  FindingsFilterToolbar,
  FindingsFilterState,
} from "../components/findings/FindingsFilterToolbar";
import { FindingsTable } from "../components/findings/FindingsTable";
import { FindingDetailPanel } from "../components/findings/FindingDetailPanel";
import { FindingReviewModal } from "../components/findings/FindingReviewModal";
import { DossierReadinessDrawer } from "../components/findings/DossierReadinessDrawer";
import type { AggregatedFindingReview } from "../types/api";

export const FindingsWorkbenchPage: React.FC = () => {
  const { caseId } = useParams<{ caseId: string }>();
  const queryClient = useQueryClient();

  // Selection & Modal States
  const [selectedFindingId, setSelectedFindingId] = useState<string | null>(null);
  const [isReviewModalOpen, setIsReviewModalOpen] = useState<boolean>(false);
  const [isDossierDrawerOpen, setIsDossierDrawerOpen] = useState<boolean>(false);

  // Filters State
  const [filters, setFilters] = useState<FindingsFilterState>({
    search: "",
    epistemic: "ALL",
    severity: "ALL",
    reviewStatus: "ALL",
    sourceType: "ALL",
  });

  // 1. Fetch Case Context
  const { data: currentCase } = useQuery({
    queryKey: ["case", caseId],
    queryFn: () => (caseId ? casesApi.getCase(caseId) : null),
    enabled: Boolean(caseId),
  });

  // 2. Fetch Aggregated Findings
  const {
    data: allFindings = [],
    isLoading: isFindingsLoading,
    error: findingsError,
    refetch,
  } = useQuery({
    queryKey: ["case-findings", caseId],
    queryFn: () => (caseId ? findingsApi.getAggregatedFindings(caseId) : []),
    enabled: Boolean(caseId),
  });

  // Filtered Findings Calculation
  const filteredFindings = useMemo(() => {
    return allFindings.filter((f) => {
      // 1. Search Query
      if (filters.search) {
        const q = filters.search.toLowerCase();
        const matchesTitle = f.title.toLowerCase().includes(q);
        const matchesDesc = (f.description || "").toLowerCase().includes(q);
        const matchesExp = (f.explanation || "").toLowerCase().includes(q);
        const matchesSource = (f.source_type || "").toLowerCase().includes(q);
        const matchesId = f.id.toLowerCase().includes(q);

        if (!matchesTitle && !matchesDesc && !matchesExp && !matchesSource && !matchesId) {
          return false;
        }
      }

      // 2. Epistemic Classification
      if (filters.epistemic !== "ALL") {
        const ep = f.evidentiary_classification || "AUTOMATED_INDICATOR";
        if (ep !== filters.epistemic) return false;
      }

      // 3. Severity
      if (filters.severity !== "ALL") {
        if (f.severity !== filters.severity) return false;
      }

      // 4. Review Status
      if (filters.reviewStatus !== "ALL") {
        const revStatus = f.review_status || (f.is_reviewed ? "CONFIRMED" : "UNREVIEWED");
        if (filters.reviewStatus === "UNREVIEWED") {
          if (f.is_reviewed || (f.review_status && f.review_status !== "UNREVIEWED")) {
            return false;
          }
        } else if (filters.reviewStatus === "CONFIRM_OBSERVATION") {
          if (!["CONFIRM_OBSERVATION", "CONFIRMED_OBSERVATION", "CONFIRMED"].includes(revStatus)) {
            return false;
          }
        } else if (filters.reviewStatus === "DISMISS_FALSE_POSITIVE") {
          if (!["DISMISS_FALSE_POSITIVE", "DISMISSED"].includes(revStatus)) {
            return false;
          }
        } else if (filters.reviewStatus === "MARK_INCONCLUSIVE") {
          if (!["MARK_INCONCLUSIVE", "INCONCLUSIVE"].includes(revStatus)) {
            return false;
          }
        } else if (filters.reviewStatus === "REQUEST_MORE_EVIDENCE") {
          if (!["REQUEST_MORE_EVIDENCE", "MORE_EVIDENCE_REQUESTED"].includes(revStatus)) {
            return false;
          }
        } else if (filters.reviewStatus === "MARK_NEEDS_REVIEW") {
          if (!["MARK_NEEDS_REVIEW", "NEEDS_REVIEW"].includes(revStatus)) {
            return false;
          }
        } else if (revStatus !== filters.reviewStatus) {
          return false;
        }
      }

      // 5. Source Subsystem
      if (filters.sourceType !== "ALL") {
        if (f.source_type !== filters.sourceType) return false;
      }

      return true;
    });
  }, [allFindings, filters]);

  // Selected Finding Entity
  const selectedFinding = useMemo(() => {
    if (!selectedFindingId) {
      return filteredFindings.length > 0 ? filteredFindings[0] : null;
    }
    return allFindings.find((f) => f.id === selectedFindingId) || null;
  }, [allFindings, filteredFindings, selectedFindingId]);

  // KPI Metrics Calculations
  const stats = useMemo(() => {
    const total = allFindings.length;
    const facts = allFindings.filter((f) => f.evidentiary_classification === "OBSERVED_FACT").length;
    const indicators = allFindings.filter(
      (f) => !f.evidentiary_classification || f.evidentiary_classification === "AUTOMATED_INDICATOR"
    ).length;
    const interpretations = allFindings.filter(
      (f) => f.evidentiary_classification === "ANALYTICAL_INTERPRETATION"
    ).length;
    const conclusions = allFindings.filter(
      (f) => f.evidentiary_classification === "INVESTIGATOR_CONCLUSION"
    ).length;
    const reviewed = allFindings.filter(
      (f) => f.is_reviewed || (f.review_status && f.review_status !== "UNREVIEWED")
    ).length;
    const unreviewed = total - reviewed;

    return { total, facts, indicators, interpretations, conclusions, reviewed, unreviewed };
  }, [allFindings]);

  // Handle Review Success
  const handleReviewSuccess = (_newReview: AggregatedFindingReview) => {
    // Invalidate queries to refresh findings and review history
    queryClient.invalidateQueries({ queryKey: ["case-findings", caseId] });
    queryClient.invalidateQueries({ queryKey: ["case-overview", caseId] });
  };

  if (!caseId) {
    return (
      <div className="p-8 text-center text-slate-400">
        <p>No active case identifier provided.</p>
      </div>
    );
  }

  return (
    <div className="p-6 space-y-5 max-w-[1600px] mx-auto min-h-screen">
      {/* Top Header & Breadcrumbs */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-2 border-b border-brand-slate/60">
        <div className="space-y-1">
          <div className="flex items-center gap-2 text-xs">
            <Link
              to={`/cases/${caseId}/overview`}
              className="inline-flex items-center gap-1 text-brand-slate-light hover:text-brand-cyan transition-colors"
            >
              <ChevronLeft className="w-3.5 h-3.5" />
              <span>{currentCase?.case_reference || "Case Overview"}</span>
            </Link>
            <span className="text-brand-slate-light">/</span>
            <span className="font-semibold text-white flex items-center gap-1.5">
              <ShieldAlert className="w-3.5 h-3.5 text-brand-cyan" />
              <span>Findings Workbench</span>
            </span>
          </div>

          <h1 className="text-xl font-bold text-white tracking-wide flex items-center gap-2">
            <span>Unified Findings & Investigator Review</span>
            <span className="text-xs font-mono font-normal px-2 py-0.5 rounded bg-brand-charcoal text-brand-cyan border border-brand-slate">
              Phase 3D
            </span>
          </h1>
        </div>

        {/* Action Controls */}
        <div className="flex items-center gap-2.5 shrink-0">
          <button
            type="button"
            onClick={() => refetch()}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded border border-brand-slate bg-brand-midnight text-xs text-slate-300 hover:text-white transition-colors"
            title="Reload findings from backend"
          >
            <RefreshCw className="w-3.5 h-3.5 text-brand-cyan" />
            <span>Refresh</span>
          </button>

          <button
            type="button"
            onClick={() => setIsDossierDrawerOpen(true)}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded bg-brand-blue hover:bg-brand-blue-hover text-white text-xs font-medium transition-colors shadow-sm"
          >
            <FileCheck2 className="w-3.5 h-3.5" />
            <span>Dossier Readiness ({stats.reviewed}/{stats.total})</span>
          </button>
        </div>
      </div>

      {/* Persistent Epistemic Notice */}
      <EpistemicNoticeBanner />

      {/* KPI Stats Row */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
        <div className="p-3 bg-brand-charcoal border border-brand-slate rounded-xl">
          <span className="text-[10px] font-mono uppercase tracking-wider text-brand-slate-light block mb-0.5">
            Total Findings
          </span>
          <span className="text-lg font-bold font-mono text-white">{stats.total}</span>
        </div>

        <div className="p-3 bg-brand-charcoal border border-cyan-500/30 rounded-xl">
          <span className="text-[10px] font-mono uppercase tracking-wider text-cyan-400 block mb-0.5">
            Observed Facts
          </span>
          <span className="text-lg font-bold font-mono text-cyan-300">{stats.facts}</span>
        </div>

        <div className="p-3 bg-brand-charcoal border border-amber-500/30 rounded-xl">
          <span className="text-[10px] font-mono uppercase tracking-wider text-amber-400 block mb-0.5">
            Automated Signals
          </span>
          <span className="text-lg font-bold font-mono text-amber-300">{stats.indicators}</span>
        </div>

        <div className="p-3 bg-brand-charcoal border border-purple-500/30 rounded-xl">
          <span className="text-[10px] font-mono uppercase tracking-wider text-purple-400 block mb-0.5">
            Interpretations
          </span>
          <span className="text-lg font-bold font-mono text-purple-300">{stats.interpretations}</span>
        </div>

        <div className="p-3 bg-brand-charcoal border border-emerald-500/30 rounded-xl">
          <span className="text-[10px] font-mono uppercase tracking-wider text-emerald-400 block mb-0.5">
            Investigator Asserted
          </span>
          <span className="text-lg font-bold font-mono text-emerald-300">{stats.conclusions}</span>
        </div>

        <div className="p-3 bg-brand-charcoal border border-brand-slate rounded-xl">
          <span className="text-[10px] font-mono uppercase tracking-wider text-brand-slate-light block mb-0.5">
            Review Status
          </span>
          <div className="flex items-center gap-1.5 font-mono text-xs mt-1">
            <span className="text-emerald-400 font-bold">{stats.reviewed} reviewed</span>
            <span className="text-slate-500">/</span>
            <span className="text-amber-400 font-bold">{stats.unreviewed} pending</span>
          </div>
        </div>
      </div>

      {/* Filter Toolbar */}
      <FindingsFilterToolbar
        filters={filters}
        onFiltersChange={setFilters}
        totalCount={allFindings.length}
        filteredCount={filteredFindings.length}
      />

      {/* Loading State */}
      {isFindingsLoading && (
        <div className="p-12 text-center text-slate-400 bg-brand-charcoal border border-brand-slate rounded-xl space-y-2">
          <Loader2 className="w-8 h-8 animate-spin text-brand-cyan mx-auto" />
          <p className="text-sm font-mono">Aggregating cross-domain investigation findings...</p>
        </div>
      )}

      {/* Error State */}
      {findingsError && (
        <div className="p-6 text-center bg-brand-charcoal border border-red-500/40 rounded-xl space-y-3">
          <AlertTriangle className="w-8 h-8 text-red-400 mx-auto" />
          <h4 className="text-base font-semibold text-white">Failed to Load Aggregated Findings</h4>
          <p className="text-xs text-brand-slate-light max-w-md mx-auto font-mono">
            {(findingsError as any)?.message || "A network or database error occurred."}
          </p>
          <button
            type="button"
            onClick={() => refetch()}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-brand-blue hover:bg-brand-blue-hover text-white text-xs font-medium rounded transition-colors"
          >
            <RefreshCw className="w-3.5 h-3.5" />
            <span>Retry Query</span>
          </button>
        </div>
      )}

      {/* Main Content: Split Table & Detail View */}
      {!isFindingsLoading && !findingsError && (
        <div className="flex flex-col lg:flex-row items-start gap-4">
          {/* Findings Inventory Table */}
          <div className="flex-1 w-full min-w-0">
            <FindingsTable
              findings={filteredFindings}
              selectedFindingId={selectedFinding?.id || null}
              onSelectFinding={(f) => setSelectedFindingId(f.id)}
              caseId={caseId}
            />
          </div>

          {/* Finding Detail & Provenance Inspector */}
          {selectedFinding && (
            <FindingDetailPanel
              finding={selectedFinding}
              onClose={() => setSelectedFindingId(null)}
              caseId={caseId}
              onOpenReviewModal={() => setIsReviewModalOpen(true)}
              isCaseArchived={currentCase?.status === "ARCHIVED"}
            />
          )}
        </div>
      )}

      {/* Human Review Adjudication Modal */}
      <FindingReviewModal
        isOpen={isReviewModalOpen}
        onClose={() => setIsReviewModalOpen(false)}
        finding={selectedFinding}
        caseId={caseId}
        onSuccess={handleReviewSuccess}
        isCaseArchived={currentCase?.status === "ARCHIVED"}
      />

      {/* Dossier Readiness & Export Drawer */}
      <DossierReadinessDrawer
        isOpen={isDossierDrawerOpen}
        onClose={() => setIsDossierDrawerOpen(false)}
        caseId={caseId}
        findings={allFindings}
        isCaseArchived={currentCase?.status === "ARCHIVED"}
      />
    </div>
  );
};
