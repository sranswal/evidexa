import React, { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { Plus, Search, FolderKanban, ArrowRight, Calendar } from "lucide-react";
import { casesApi, type CreateCasePayload } from "../api/cases";
import type { CaseStatus } from "../types/api";
import { Card } from "../components/ui/Card";
import { Button } from "../components/ui/Button";
import { StatusBadge } from "../components/ui/Badge";
import { Modal } from "../components/ui/Modal";
import { Skeleton } from "../components/ui/Skeleton";
import { ErrorMessage } from "../components/ui/ErrorMessage";
import { EmptyState } from "../components/ui/EmptyState";

export const CasesPage: React.FC = () => {
  const queryClient = useQueryClient();
  const [statusFilter, setStatusFilter] = useState<CaseStatus | "ALL">("ALL");
  const [searchQuery, setSearchQuery] = useState("");
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);

  // New Case Form State
  const [newTitle, setNewTitle] = useState("");
  const [newDescription, setNewDescription] = useState("");
  const [newCreatedBy, setNewCreatedBy] = useState("lead-investigator");
  const [formError, setFormError] = useState<string | null>(null);

  // Fetch Cases Query
  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ["cases", statusFilter],
    queryFn: () =>
      casesApi.listCases({
        status: statusFilter === "ALL" ? undefined : statusFilter,
        limit: 100,
      }),
  });

  // Create Case Mutation
  const createMutation = useMutation({
    mutationFn: (payload: CreateCasePayload) => casesApi.createCase(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["cases"] });
      setIsCreateModalOpen(false);
      setNewTitle("");
      setNewDescription("");
      setFormError(null);
    },
    onError: (err: any) => {
      setFormError(err.message || "Failed to create investigation case.");
    },
  });

  const handleCreateSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!newTitle.trim()) {
      setFormError("Case title is mandatory.");
      return;
    }
    setFormError(null);
    createMutation.mutate({
      title: newTitle.trim(),
      description: newDescription.trim() || undefined,
      created_by: newCreatedBy.trim() || undefined,
    });
  };

  const cases = data?.items || [];
  const filteredCases = cases.filter(
    (c) =>
      c.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
      c.case_reference.toLowerCase().includes(searchQuery.toLowerCase())
  );

  return (
    <div className="space-y-6">
      {/* Top Banner & Action */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-2 border-b border-evidexa-slate/60">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-white font-sans flex items-center gap-2.5">
            <FolderKanban className="w-7 h-7 text-evidexa-cyan" />
            Investigation Cases
          </h1>
          <p className="text-sm text-slate-400 mt-1">
            Centrally manage forensic case workspaces, evidentiary documents, and chain of custody.
          </p>
        </div>
        <Button onClick={() => setIsCreateModalOpen(true)} className="self-start sm:self-auto">
          <Plus className="w-4 h-4 mr-1.5" />
          Create New Case
        </Button>
      </div>

      {/* Filter and Search Bar */}
      <div className="flex flex-col md:flex-row gap-3 items-stretch md:items-center justify-between">
        {/* Search */}
        <div className="relative flex-1 max-w-md">
          <Search className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            placeholder="Search by case reference or title..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full bg-evidexa-charcoal border border-evidexa-slate rounded-lg pl-9 pr-4 py-2 text-sm text-white placeholder-slate-400 focus:outline-none focus:ring-1 focus:ring-evidexa-cyan focus:border-evidexa-cyan"
          />
        </div>

        {/* Status Filter Tabs */}
        <div className="flex items-center gap-1 overflow-x-auto bg-evidexa-midnight/60 p-1 rounded-lg border border-evidexa-slate/80">
          {(["ALL", "ACTIVE", "UNDER_REVIEW", "COMPLETED", "ARCHIVED", "DRAFT"] as const).map(
            (tabStatus) => (
              <button
                key={tabStatus}
                onClick={() => setStatusFilter(tabStatus)}
                className={`px-3 py-1.5 rounded text-xs font-mono font-medium transition-colors shrink-0 ${
                  statusFilter === tabStatus
                    ? "bg-evidexa-slate text-evidexa-cyan font-semibold shadow"
                    : "text-slate-400 hover:text-slate-200 hover:bg-slate-800/40"
                }`}
              >
                {tabStatus}
              </button>
            )
          )}
        </div>
      </div>

      {/* Loading State */}
      {isLoading && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {[1, 2, 3, 4, 5, 6].map((i) => (
            <Card key={i} className="space-y-3">
              <div className="flex justify-between items-center">
                <Skeleton className="h-5 w-24" />
                <Skeleton className="h-5 w-20 rounded-full" />
              </div>
              <Skeleton className="h-6 w-3/4" />
              <Skeleton className="h-12 w-full" />
              <div className="pt-2 border-t border-slate-800 flex justify-between">
                <Skeleton className="h-4 w-28" />
                <Skeleton className="h-4 w-16" />
              </div>
            </Card>
          ))}
        </div>
      )}

      {/* Error State */}
      {isError && (
        <ErrorMessage
          title="Could not retrieve investigation cases"
          message={error instanceof Error ? error.message : "Backend connection error"}
          onRetry={() => refetch()}
        />
      )}

      {/* Empty State */}
      {!isLoading && !isError && filteredCases.length === 0 && (
        <EmptyState
          title="No investigation cases found"
          description={
            searchQuery
              ? `No cases matched "${searchQuery}". Try adjusting your search query.`
              : "No investigation cases exist in this category yet. Create your first case to begin."
          }
          action={
            <Button onClick={() => setIsCreateModalOpen(true)}>
              <Plus className="w-4 h-4 mr-1.5" />
              Create First Case
            </Button>
          }
        />
      )}

      {/* Cases Grid */}
      {!isLoading && !isError && filteredCases.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {filteredCases.map((caseItem) => (
            <Card
              key={caseItem.id}
              className="flex flex-col justify-between hover:border-slate-500 transition-colors group"
            >
              <div>
                <div className="flex items-center justify-between gap-2 mb-2">
                  <span className="font-mono text-xs font-bold text-evidexa-cyan tracking-wider">
                    {caseItem.case_reference}
                  </span>
                  <StatusBadge status={caseItem.status} type="case" />
                </div>

                <h3 className="font-semibold text-white group-hover:text-evidexa-aqua transition-colors line-clamp-1 mb-2">
                  {caseItem.title}
                </h3>

                <p className="text-xs text-slate-400 line-clamp-2 mb-4">
                  {caseItem.description || "No case description provided."}
                </p>
              </div>

              <div className="pt-3 border-t border-evidexa-slate/60 text-xs text-slate-400 flex items-center justify-between mt-auto">
                <div className="flex items-center gap-1.5">
                  <Calendar className="w-3.5 h-3.5 text-slate-500" />
                  <span>{new Date(caseItem.created_at).toLocaleDateString()}</span>
                </div>

                <Link
                  to={`/cases/${caseItem.id}/overview`}
                  className="inline-flex items-center gap-1 text-evidexa-cyan font-medium hover:text-white transition-colors text-xs"
                >
                  Open Case <ArrowRight className="w-3.5 h-3.5" />
                </Link>
              </div>
            </Card>
          ))}
        </div>
      )}

      {/* Create Case Modal */}
      <Modal
        isOpen={isCreateModalOpen}
        onClose={() => setIsCreateModalOpen(false)}
        title="Create Investigation Case"
      >
        <form onSubmit={handleCreateSubmit} className="space-y-4">
          {formError && (
            <div className="p-3 rounded bg-rose-950/60 border border-rose-500/50 text-xs text-rose-300">
              {formError}
            </div>
          )}

          <div>
            <label className="block text-xs font-semibold uppercase tracking-wider text-slate-300 mb-1.5">
              Case Title <span className="text-rose-400">*</span>
            </label>
            <input
              type="text"
              required
              placeholder="e.g. Acme Corp Forensic Audit - Q3 2026"
              value={newTitle}
              onChange={(e) => setNewTitle(e.target.value)}
              className="w-full bg-evidexa-midnight border border-evidexa-slate rounded-md px-3 py-2 text-sm text-white placeholder-slate-500 focus:outline-none focus:ring-1 focus:ring-evidexa-cyan"
            />
          </div>

          <div>
            <label className="block text-xs font-semibold uppercase tracking-wider text-slate-300 mb-1.5">
              Description (Optional)
            </label>
            <textarea
              rows={3}
              placeholder="Summary of investigation objectives, primary concerns, and initial scope..."
              value={newDescription}
              onChange={(e) => setNewDescription(e.target.value)}
              className="w-full bg-evidexa-midnight border border-evidexa-slate rounded-md px-3 py-2 text-sm text-white placeholder-slate-500 focus:outline-none focus:ring-1 focus:ring-evidexa-cyan"
            />
          </div>

          <div>
            <label className="block text-xs font-semibold uppercase tracking-wider text-slate-300 mb-1.5">
              Lead Investigator Identifier
            </label>
            <input
              type="text"
              value={newCreatedBy}
              onChange={(e) => setNewCreatedBy(e.target.value)}
              className="w-full bg-evidexa-midnight border border-evidexa-slate rounded-md px-3 py-2 text-sm text-white placeholder-slate-500 focus:outline-none focus:ring-1 focus:ring-evidexa-cyan"
            />
            <span className="text-[11px] text-slate-400 mt-1 block">
              Cryptographically logged with forensic audit entries.
            </span>
          </div>

          <div className="flex items-center justify-end gap-3 pt-4 border-t border-evidexa-slate mt-6">
            <Button
              type="button"
              variant="secondary"
              onClick={() => setIsCreateModalOpen(false)}
            >
              Cancel
            </Button>
            <Button type="submit" isLoading={createMutation.isPending}>
              Create Case Workspace
            </Button>
          </div>
        </form>
      </Modal>
    </div>
  );
};
