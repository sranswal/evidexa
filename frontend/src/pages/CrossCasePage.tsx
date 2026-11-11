import React, { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Network,
  Plus,
  Play,
  CheckCircle2,
  XCircle,
  HelpCircle,
  Clock,
  ShieldAlert,
  Building,
  User,
  CreditCard,
  FileText,
  AlertTriangle,
  Filter,
  FolderOpen,
  Loader2,
} from "lucide-react";
import {
  crossCaseApi,
  CrossCaseCandidateMatch,
} from "../api/crossCase";
import { casesApi } from "../api/cases";
import type { Case } from "../types/api";
import { Card } from "../components/ui/Card";
import { Button } from "../components/ui/Button";
import { EmptyState } from "../components/ui/EmptyState";
import { Modal } from "../components/ui/Modal";

export const CrossCasePage: React.FC = () => {
  const queryClient = useQueryClient();

  const [selectedScopeId, setSelectedScopeId] = useState<string | null>(null);
  const [isCreateScopeOpen, setIsCreateScopeOpen] = useState(false);
  const [newScopeName, setNewScopeName] = useState("");
  const [newScopeDesc, setNewScopeDesc] = useState("");
  const [selectedCaseIds, setSelectedCaseIds] = useState<string[]>([]);
  const [createError, setCreateError] = useState<string | null>(null);

  // Filters
  const [statusFilter, setStatusFilter] = useState<string>("ALL");
  const [typeFilter, setTypeFilter] = useState<string>("ALL");

  // Review modal state
  const [reviewingMatch, setReviewingMatch] = useState<CrossCaseCandidateMatch | null>(null);
  const [reviewDecision, setReviewDecision] = useState<"ACCEPTED" | "REJECTED" | "NEEDS_FURTHER_INVESTIGATION">("ACCEPTED");
  const [reviewRationale, setReviewRationale] = useState("");
  const [reviewError, setReviewError] = useState<string | null>(null);

  // 1. Fetch accessible scopes
  const { data: scopes = [] } = useQuery({
    queryKey: ["cross-case-scopes"],
    queryFn: () => crossCaseApi.listScopes(),
  });

  // Auto-select first scope if none selected
  const activeScopeId = selectedScopeId || (scopes.length > 0 ? scopes[0].id : null);

  // 2. Fetch current scope details
  const { data: currentScope } = useQuery({
    queryKey: ["cross-case-scope", activeScopeId],
    queryFn: () => (activeScopeId ? crossCaseApi.getScope(activeScopeId) : null),
    enabled: Boolean(activeScopeId),
  });

  // 3. Fetch cases for selection
  const { data: casesData } = useQuery({
    queryKey: ["cases-for-scope"],
    queryFn: () => casesApi.listCases({ limit: 50 }),
  });
  const allCases: Case[] = casesData?.items || [];

  // 4. Fetch candidates for active scope
  const { data: candidatesData, isLoading: isLoadingCandidates, refetch: refetchCandidates } = useQuery({
    queryKey: ["cross-case-candidates", activeScopeId, statusFilter, typeFilter],
    queryFn: () => {
      if (!activeScopeId) return { items: [], total: 0, limit: 50, offset: 0 };
      const params: Record<string, string | number> = { limit: 100, offset: 0 };
      if (statusFilter !== "ALL") params.decision_status = statusFilter;
      if (typeFilter !== "ALL") params.entity_type = typeFilter;
      return crossCaseApi.listCandidates(activeScopeId, params);
    },
    enabled: Boolean(activeScopeId),
  });

  // Mutation: Create Scope
  const createScopeMutation = useMutation({
    mutationFn: (payload: { name: string; case_ids: string[]; description?: string }) =>
      crossCaseApi.createScope(payload),
    onSuccess: (newScope) => {
      queryClient.invalidateQueries({ queryKey: ["cross-case-scopes"] });
      setSelectedScopeId(newScope.id);
      setIsCreateScopeOpen(false);
      setNewScopeName("");
      setNewScopeDesc("");
      setSelectedCaseIds([]);
      setCreateError(null);
    },
    onError: (err: any) => {
      setCreateError(err.message || "Failed to create investigation scope.");
    },
  });

  // Mutation: Run Correlation
  const runCorrelationMutation = useMutation({
    mutationFn: (scopeId: string) => crossCaseApi.runCorrelation(scopeId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["cross-case-candidates", activeScopeId] });
      refetchCandidates();
    },
  });

  // Mutation: Review Candidate
  const reviewCandidateMutation = useMutation({
    mutationFn: (payload: { scopeId: string; matchId: string; decision: "ACCEPTED" | "REJECTED" | "NEEDS_FURTHER_INVESTIGATION"; rationale: string }) =>
      crossCaseApi.reviewCandidate(payload.scopeId, payload.matchId, {
        decision: payload.decision,
        rationale: payload.rationale,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["cross-case-candidates", activeScopeId] });
      setReviewingMatch(null);
      setReviewRationale("");
      setReviewError(null);
    },
    onError: (err: any) => {
      setReviewError(err.message || "Failed to record review decision.");
    },
  });

  const handleCreateScope = (e: React.FormEvent) => {
    e.preventDefault();
    if (!newScopeName.trim()) {
      setCreateError("Scope name is required.");
      return;
    }
    if (selectedCaseIds.length < 2) {
      setCreateError("Please select at least 2 authorized cases to correlate.");
      return;
    }
    createScopeMutation.mutate({
      name: newScopeName.trim(),
      description: newScopeDesc.trim() || undefined,
      case_ids: selectedCaseIds,
    });
  };

  const handleToggleCaseSelection = (cid: string) => {
    setSelectedCaseIds((prev) =>
      prev.includes(cid) ? prev.filter((id) => id !== cid) : [...prev, cid]
    );
  };

  const handleOpenReview = (candidate: CrossCaseCandidateMatch) => {
    setReviewingMatch(candidate);
    setReviewDecision(
      candidate.decision_status === "PENDING_REVIEW" ? "ACCEPTED" : candidate.decision_status
    );
    setReviewRationale("");
    setReviewError(null);
  };

  const handleSubmitReview = (e: React.FormEvent) => {
    e.preventDefault();
    if (!reviewingMatch || !activeScopeId) return;
    if (!reviewRationale.trim()) {
      setReviewError("Investigator rationale is required.");
      return;
    }
    reviewCandidateMutation.mutate({
      scopeId: activeScopeId,
      matchId: reviewingMatch.id,
      decision: reviewDecision,
      rationale: reviewRationale.trim(),
    });
  };

  const getEntityIcon = (type: string) => {
    switch (type) {
      case "ORGANIZATION":
        return <Building className="w-4 h-4 text-evidexa-cyan" />;
      case "PERSON":
        return <User className="w-4 h-4 text-purple-400" />;
      case "BANK_ACCOUNT_REFERENCE":
        return <CreditCard className="w-4 h-4 text-emerald-400" />;
      case "TAX_IDENTIFIER":
      case "INVOICE_REFERENCE":
      case "TRANSACTION_REFERENCE":
        return <FileText className="w-4 h-4 text-amber-400" />;
      default:
        return <Network className="w-4 h-4 text-slate-400" />;
    }
  };

  const getClassificationBadge = (cls: string) => {
    switch (cls) {
      case "EXACT_IDENTIFIER":
        return (
          <span className="px-2 py-0.5 text-xs font-semibold rounded bg-emerald-500/15 text-emerald-300 border border-emerald-500/30">
            Exact Identifier
          </span>
        );
      case "HIGH_CONFIDENCE_FUZZY":
      case "STRONG_SIMILARITY":
        return (
          <span className="px-2 py-0.5 text-xs font-semibold rounded bg-blue-500/15 text-blue-300 border border-blue-500/30">
            High Confidence Fuzzy
          </span>
        );
      case "WEAK_INDICATOR":
        return (
          <span className="px-2 py-0.5 text-xs font-semibold rounded bg-amber-500/15 text-amber-300 border border-amber-500/30">
            Weak Indicator
          </span>
        );
      case "CONFLICTING":
        return (
          <span className="px-2 py-0.5 text-xs font-semibold rounded bg-rose-500/15 text-rose-300 border border-rose-500/30">
            Conflicting Signals
          </span>
        );
      default:
        return (
          <span className="px-2 py-0.5 text-xs font-semibold rounded bg-evidexa-slate text-slate-300 border border-evidexa-slate">
            {cls}
          </span>
        );
    }
  };

  const getDecisionBadge = (status: string) => {
    switch (status) {
      case "ACCEPTED":
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 text-xs font-medium rounded-full bg-emerald-950/80 text-emerald-400 border border-emerald-800">
            <CheckCircle2 className="w-3 h-3" /> Accepted
          </span>
        );
      case "REJECTED":
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 text-xs font-medium rounded-full bg-rose-950/80 text-rose-400 border border-rose-800">
            <XCircle className="w-3 h-3" /> Rejected
          </span>
        );
      case "NEEDS_FURTHER_INVESTIGATION":
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 text-xs font-medium rounded-full bg-amber-950/80 text-amber-400 border border-amber-800">
            <HelpCircle className="w-3 h-3" /> Under Review
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 text-xs font-medium rounded-full bg-evidexa-slate/80 text-slate-300 border border-evidexa-slate">
            <Clock className="w-3 h-3" /> Pending Review
          </span>
        );
    }
  };

  const candidateItems = candidatesData?.items || [];

  return (
    <div className="space-y-6">
      {/* Top Banner & Scope Toolbar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-2 border-b border-evidexa-slate/60">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-white font-sans flex items-center gap-2.5">
            <Network className="w-7 h-7 text-evidexa-cyan" />
            Cross-Case Investigation Intelligence
          </h1>
          <p className="text-sm text-slate-400 mt-1">
            Discover potential evidentiary links across multiple authorized cases with strict tenant isolation and audit attribution.
          </p>
        </div>

        <div className="flex items-center gap-2.5 flex-wrap">
          {/* Scope Selector */}
          <div className="flex items-center gap-2 bg-evidexa-charcoal border border-evidexa-slate rounded-md px-3 py-1.5 text-sm">
            <FolderOpen className="w-4 h-4 text-slate-400 shrink-0" />
            <select
              value={activeScopeId || ""}
              onChange={(e) => setSelectedScopeId(e.target.value)}
              className="bg-transparent text-sm font-medium text-white focus:outline-none cursor-pointer"
            >
              {scopes.length === 0 ? (
                <option value="" className="bg-evidexa-charcoal text-slate-400">
                  No Active Scopes
                </option>
              ) : (
                scopes.map((s) => (
                  <option key={s.id} value={s.id} className="bg-evidexa-charcoal text-white">
                    {s.name} ({s.case_ids.length} cases)
                  </option>
                ))
              )}
            </select>
          </div>

          <Button
            variant="secondary"
            size="sm"
            onClick={() => setIsCreateScopeOpen(true)}
          >
            <Plus className="w-4 h-4 mr-1" />
            New Scope
          </Button>

          {activeScopeId && (
            <Button
              variant="primary"
              size="sm"
              onClick={() => runCorrelationMutation.mutate(activeScopeId)}
              isLoading={runCorrelationMutation.isPending}
            >
              <Play className="w-4 h-4 mr-1" />
              Run Correlation
            </Button>
          )}
        </div>
      </div>

      {/* Epistemic Guardrail Notice Banner */}
      <div className="bg-evidexa-charcoal border border-amber-500/30 rounded-lg p-3.5 flex items-start gap-3 text-xs text-amber-200/90 shadow-sm">
        <ShieldAlert className="w-4 h-4 text-amber-400 shrink-0 mt-0.5" />
        <div>
          <span className="font-semibold text-white">Epistemic Warning:</span> Cross-case candidate matches are investigative leads based on deterministic heuristics and fuzzy similarity.
          They do not constitute automated determinations of fraud, common ownership, or culpability. Independent human review is required.
        </div>
      </div>

      {/* Main Workspace Area (2 Columns) */}
      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6 items-start">
        {/* Left Column: Scope Summary & Filters (1 col) */}
        <div className="lg:col-span-1 space-y-5">
          {/* Active Scope Summary Card */}
          <Card className="p-4 space-y-3">
            <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Active Scope</h3>
            {currentScope ? (
              <div className="space-y-3">
                <div>
                  <h4 className="text-base font-semibold text-white">{currentScope.name}</h4>
                  {currentScope.description && (
                    <p className="text-xs text-slate-400 mt-1 leading-relaxed">{currentScope.description}</p>
                  )}
                </div>

                <div className="pt-2 border-t border-evidexa-slate/60">
                  <span className="text-xs font-medium text-slate-400 block mb-2">
                    Constituent Cases ({currentScope.case_ids.length})
                  </span>
                  <div className="flex flex-col gap-1.5">
                    {currentScope.case_ids.map((cid) => (
                      <div
                        key={cid}
                        className="flex items-center justify-between text-xs py-1.5 px-2.5 bg-evidexa-midnight/70 rounded border border-evidexa-slate font-mono text-slate-300"
                      >
                        <span className="truncate">{cid}</span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            ) : (
              <p className="text-xs text-slate-500 py-3">
                No scope selected. Create or select a scope to begin correlation analysis.
              </p>
            )}
          </Card>

          {/* Filters Card */}
          <Card className="p-4 space-y-3">
            <div className="flex items-center gap-2 text-xs font-semibold text-slate-400 uppercase tracking-wider">
              <Filter className="w-3.5 h-3.5 text-evidexa-cyan" />
              Candidate Filters
            </div>

            <div className="space-y-3 pt-1">
              <div>
                <label className="text-xs text-slate-400 block mb-1">Decision Status</label>
                <select
                  value={statusFilter}
                  onChange={(e) => setStatusFilter(e.target.value)}
                  className="w-full bg-evidexa-midnight border border-evidexa-slate rounded px-2.5 py-1.5 text-xs text-white focus:outline-none focus:border-evidexa-cyan"
                >
                  <option value="ALL">All Statuses</option>
                  <option value="PENDING_REVIEW">Pending Review</option>
                  <option value="ACCEPTED">Accepted</option>
                  <option value="REJECTED">Rejected</option>
                  <option value="NEEDS_FURTHER_INVESTIGATION">Needs Further Investigation</option>
                </select>
              </div>

              <div>
                <label className="text-xs text-slate-400 block mb-1">Entity Type</label>
                <select
                  value={typeFilter}
                  onChange={(e) => setTypeFilter(e.target.value)}
                  className="w-full bg-evidexa-midnight border border-evidexa-slate rounded px-2.5 py-1.5 text-xs text-white focus:outline-none focus:border-evidexa-cyan"
                >
                  <option value="ALL">All Entity Types</option>
                  <option value="ORGANIZATION">Organization</option>
                  <option value="PERSON">Person</option>
                  <option value="TAX_IDENTIFIER">Tax Identifier (PAN/GSTIN)</option>
                  <option value="BANK_ACCOUNT_REFERENCE">Bank Account</option>
                  <option value="INVOICE_REFERENCE">Invoice / Document Reference</option>
                </select>
              </div>
            </div>
          </Card>
        </div>

        {/* Right Column: Candidate Matches (3 cols) */}
        <div className="lg:col-span-3 space-y-4">
          <div className="flex items-center justify-between pb-1">
            <div>
              <h2 className="text-lg font-semibold text-white flex items-center gap-2">
                Correlation Candidate Matches
                <span className="text-xs font-mono font-normal bg-evidexa-slate px-2 py-0.5 rounded text-slate-300">
                  {candidatesData?.total ?? 0}
                </span>
              </h2>
              <p className="text-xs text-slate-400 mt-0.5">
                Discovered entity pairs across authorized cases with evidentiary signals and matching rationale.
              </p>
            </div>
          </div>

          {isLoadingCandidates ? (
            <div className="p-12 flex items-center justify-center text-slate-400 text-sm">
              <Loader2 className="w-5 h-5 animate-spin mr-2 text-evidexa-cyan" />
              Loading correlation candidates...
            </div>
          ) : candidateItems.length === 0 ? (
            <EmptyState
              title="No Candidate Matches Found"
              description={
                activeScopeId
                  ? "Click 'Run Correlation' to analyze entities across cases in this scope, or adjust your filter criteria."
                  : "Select or create an investigation scope to begin cross-case correlation."
              }
              icon={<Network className="w-8 h-8 text-slate-400" />}
            />
          ) : (
            <div className="space-y-4">
              {candidateItems.map((c) => (
                <Card
                  key={c.id}
                  className="p-5 space-y-4 transition-all hover:border-slate-600"
                >
                  <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-4">
                    <div className="flex items-start gap-3">
                      <div className="p-2.5 bg-evidexa-midnight border border-evidexa-slate rounded-lg shrink-0 mt-0.5">
                        {getEntityIcon(c.entity_type)}
                      </div>
                      <div>
                        <div className="flex items-center gap-2 flex-wrap">
                          <span className="font-semibold text-white text-base">
                            {c.target_value_display}
                          </span>
                          <span className="text-slate-500 font-normal">↔</span>
                          <span className="font-semibold text-white text-base">
                            {c.candidate_value_display}
                          </span>
                        </div>
                        <div className="flex items-center gap-2 sm:gap-3 mt-1.5 text-xs text-slate-400 flex-wrap">
                          <span>
                            Target Case: <span className="font-mono text-slate-300">{c.target_case_id}</span>
                          </span>
                          <span>•</span>
                          <span>
                            Candidate Case: <span className="font-mono text-slate-300">{c.candidate_case_id}</span>
                          </span>
                        </div>
                      </div>
                    </div>

                    <div className="flex items-center gap-2.5 self-start shrink-0 flex-wrap">
                      {getClassificationBadge(c.match_classification)}
                      {getDecisionBadge(c.decision_status)}
                      <Button
                        variant="secondary"
                        size="sm"
                        onClick={() => handleOpenReview(c)}
                      >
                        Review
                      </Button>
                    </div>
                  </div>

                  {/* Signals & Masked Values Container */}
                  <div className="bg-evidexa-midnight/80 rounded-lg p-3.5 border border-evidexa-slate/60 space-y-2 text-xs">
                    <div className="flex items-center justify-between text-slate-400 flex-wrap gap-2">
                      <span>
                        Matching Method: <span className="text-slate-200 font-medium">{c.matching_method}</span>
                      </span>
                      <span>
                        Confidence Score:{" "}
                        <span className="text-evidexa-cyan font-semibold font-mono">
                          {Math.round(c.match_score * 100)}%
                        </span>
                      </span>
                    </div>

                    {c.raw_target_value_masked && c.raw_candidate_value_masked && (
                      <div className="text-slate-400">
                        Masked Artifact Values:{" "}
                        <span className="font-mono text-slate-300">{c.raw_target_value_masked}</span> ~{" "}
                        <span className="font-mono text-slate-300">{c.raw_candidate_value_masked}</span>
                      </div>
                    )}

                    {c.evidence.matching_signals.length > 0 && (
                      <div className="space-y-1 pt-1">
                        {c.evidence.matching_signals.map((sig, idx) => (
                          <div key={idx} className="flex items-center gap-1.5 text-emerald-400">
                            <CheckCircle2 className="w-3.5 h-3.5 shrink-0" />
                            <span>{sig}</span>
                          </div>
                        ))}
                      </div>
                    )}

                    {c.evidence.contradicting_signals.length > 0 && (
                      <div className="space-y-1 pt-1">
                        {c.evidence.contradicting_signals.map((sig, idx) => (
                          <div key={idx} className="flex items-center gap-1.5 text-rose-400">
                            <AlertTriangle className="w-3.5 h-3.5 shrink-0" />
                            <span>{sig}</span>
                          </div>
                        ))}
                      </div>
                    )}

                    {c.review_history.length > 0 && (
                      <div className="mt-2.5 pt-2.5 border-t border-evidexa-slate/60 text-slate-400">
                        <span className="font-semibold text-slate-300">Latest Review:</span> Reviewed by{" "}
                        <span className="text-white font-medium">
                          {c.review_history[c.review_history.length - 1].reviewer_username}
                        </span>{" "}
                        ({new Date(c.review_history[c.review_history.length - 1].reviewed_at).toLocaleDateString()}): "
                        {c.review_history[c.review_history.length - 1].rationale}"
                      </div>
                    )}
                  </div>
                </Card>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Modal: Create Scope */}
      <Modal
        isOpen={isCreateScopeOpen}
        onClose={() => setIsCreateScopeOpen(false)}
        title="Create Cross-Case Investigation Scope"
      >
        <p className="text-xs text-slate-400 mb-4">
          Select at least two authorized cases from your organization to form an explicit correlation boundary.
        </p>

        {createError && (
          <div className="mb-4 p-3 bg-rose-950/60 border border-rose-800 rounded text-xs text-rose-300">
            {createError}
          </div>
        )}

        <form onSubmit={handleCreateScope} className="space-y-4">
          <div>
            <label className="text-xs font-semibold text-slate-300 block mb-1">Scope Name *</label>
            <input
              type="text"
              value={newScopeName}
              onChange={(e) => setNewScopeName(e.target.value)}
              placeholder="e.g., Regional Vendor Collusion Ring 2026"
              className="w-full bg-evidexa-midnight border border-evidexa-slate rounded px-3 py-2 text-sm text-white focus:outline-none focus:border-evidexa-cyan"
              required
            />
          </div>

          <div>
            <label className="text-xs font-semibold text-slate-300 block mb-1">Description (Optional)</label>
            <textarea
              value={newScopeDesc}
              onChange={(e) => setNewScopeDesc(e.target.value)}
              placeholder="Investigative hypothesis or scope notes..."
              rows={2}
              className="w-full bg-evidexa-midnight border border-evidexa-slate rounded px-3 py-2 text-sm text-white focus:outline-none focus:border-evidexa-cyan"
            />
          </div>

          <div>
            <label className="text-xs font-semibold text-slate-300 block mb-1">
              Select Authorized Cases (Selected: {selectedCaseIds.length}) *
            </label>
            <div className="max-h-48 overflow-y-auto space-y-1.5 p-2 bg-evidexa-midnight border border-evidexa-slate rounded">
              {allCases.length === 0 ? (
                <div className="text-xs text-slate-500 py-2 text-center">No cases available.</div>
              ) : (
                allCases.map((c) => (
                  <label
                    key={c.id}
                    className="flex items-center gap-2 p-2 hover:bg-evidexa-charcoal rounded cursor-pointer text-xs"
                  >
                    <input
                      type="checkbox"
                      checked={selectedCaseIds.includes(c.id)}
                      onChange={() => handleToggleCaseSelection(c.id)}
                      className="rounded border-evidexa-slate text-evidexa-cyan focus:ring-0"
                    />
                    <span className="font-semibold text-white">{c.title}</span>
                    <span className="font-mono text-slate-400">({c.id})</span>
                  </label>
                ))
              )}
            </div>
          </div>

          <div className="flex items-center justify-end gap-3 pt-3 border-t border-evidexa-slate/60">
            <Button
              type="button"
              variant="secondary"
              size="sm"
              onClick={() => setIsCreateScopeOpen(false)}
            >
              Cancel
            </Button>
            <Button
              type="submit"
              variant="primary"
              size="sm"
              isLoading={createScopeMutation.isPending}
            >
              Create Scope
            </Button>
          </div>
        </form>
      </Modal>

      {/* Modal: Review Disposition */}
      <Modal
        isOpen={Boolean(reviewingMatch)}
        onClose={() => setReviewingMatch(null)}
        title="Candidate Review Disposition"
      >
        {reviewingMatch && (
          <div>
            <p className="text-xs text-slate-400 mb-4">
              Formal disposition for correlation between{" "}
              <span className="text-white font-medium">{reviewingMatch.target_value_display}</span> and{" "}
              <span className="text-white font-medium">{reviewingMatch.candidate_value_display}</span>.
            </p>

            {reviewError && (
              <div className="mb-4 p-3 bg-rose-950/60 border border-rose-800 rounded text-xs text-rose-300">
                {reviewError}
              </div>
            )}

            <form onSubmit={handleSubmitReview} className="space-y-4">
              <div>
                <label className="text-xs font-semibold text-slate-300 block mb-1.5">Decision Disposition *</label>
                <div className="grid grid-cols-3 gap-2">
                  <button
                    type="button"
                    onClick={() => setReviewDecision("ACCEPTED")}
                    className={`py-2 px-3 text-xs font-semibold rounded border text-center transition ${
                      reviewDecision === "ACCEPTED"
                        ? "bg-emerald-950/80 border-emerald-500 text-emerald-300"
                        : "bg-evidexa-midnight border-evidexa-slate text-slate-400 hover:text-white"
                    }`}
                  >
                    Accept Match
                  </button>
                  <button
                    type="button"
                    onClick={() => setReviewDecision("REJECTED")}
                    className={`py-2 px-3 text-xs font-semibold rounded border text-center transition ${
                      reviewDecision === "REJECTED"
                        ? "bg-rose-950/80 border-rose-500 text-rose-300"
                        : "bg-evidexa-midnight border-evidexa-slate text-slate-400 hover:text-white"
                    }`}
                  >
                    Reject Match
                  </button>
                  <button
                    type="button"
                    onClick={() => setReviewDecision("NEEDS_FURTHER_INVESTIGATION")}
                    className={`py-2 px-3 text-xs font-semibold rounded border text-center transition ${
                      reviewDecision === "NEEDS_FURTHER_INVESTIGATION"
                        ? "bg-amber-950/80 border-amber-500 text-amber-300"
                        : "bg-evidexa-midnight border-evidexa-slate text-slate-400 hover:text-white"
                    }`}
                  >
                    Needs Info
                  </button>
                </div>
              </div>

              <div>
                <label className="text-xs font-semibold text-slate-300 block mb-1">Investigator Rationale *</label>
                <textarea
                  value={reviewRationale}
                  onChange={(e) => setReviewRationale(e.target.value)}
                  placeholder="Record evidentiary justification for this disposition (required for audit)..."
                  rows={3}
                  className="w-full bg-evidexa-midnight border border-evidexa-slate rounded px-3 py-2 text-sm text-white focus:outline-none focus:border-evidexa-cyan"
                  required
                />
              </div>

              {/* Review History Audit Trail */}
              {reviewingMatch.review_history.length > 0 && (
                <div className="bg-evidexa-midnight/80 rounded-lg p-3 border border-evidexa-slate/60">
                  <span className="text-xs font-semibold text-slate-300 block mb-2">Previous Review History</span>
                  <div className="space-y-2 max-h-32 overflow-y-auto">
                    {reviewingMatch.review_history.map((rev) => (
                      <div key={rev.id} className="text-xs text-slate-400 border-b border-evidexa-slate/40 pb-1.5 last:border-0">
                        <div className="flex items-center justify-between text-slate-300">
                          <span className="font-medium text-white">{rev.reviewer_username}</span>
                          <span>{new Date(rev.reviewed_at).toLocaleString()}</span>
                        </div>
                        <div className="text-evidexa-cyan font-semibold">{rev.decision}</div>
                        <p className="italic text-slate-400 mt-0.5">"{rev.rationale}"</p>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              <div className="flex items-center justify-end gap-3 pt-3 border-t border-evidexa-slate/60">
                <Button
                  type="button"
                  variant="secondary"
                  size="sm"
                  onClick={() => setReviewingMatch(null)}
                >
                  Cancel
                </Button>
                <Button
                  type="submit"
                  variant="primary"
                  size="sm"
                  isLoading={reviewCandidateMutation.isPending}
                >
                  Submit Disposition
                </Button>
              </div>
            </form>
          </div>
        )}
      </Modal>
    </div>
  );
};
