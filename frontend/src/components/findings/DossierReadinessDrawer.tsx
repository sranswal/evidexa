import React, { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  X,
  FileCheck2,
  Download,
  ShieldCheck,
  AlertTriangle,
  Loader2,
  Plus,
  FileText,
  Lock,
} from "lucide-react";
import { StatusBadge } from "../ui/Badge";
import type {
  AggregatedFinding,
  DossierGenerateRequest,
} from "../../types/api";
import { dossiersApi } from "../../api/dossiers";

interface DossierReadinessDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  caseId: string;
  findings: AggregatedFinding[];
  isCaseArchived?: boolean;
}

export const DossierReadinessDrawer: React.FC<DossierReadinessDrawerProps> = ({
  isOpen,
  onClose,
  caseId,
  findings,
  isCaseArchived = false,
}) => {
  const queryClient = useQueryClient();

  // New Dossier Form state
  const [isGenerating, setIsGenerating] = useState<boolean>(false);
  const [createdBy, setCreatedBy] = useState<string>("investigator-lead");
  const [scopeAndPurpose, setScopeAndPurpose] = useState<string>(
    "Comprehensive verification and multi-document consistency audit."
  );

  // Finalization state
  const [finalizingDossierId, setFinalizingDossierId] = useState<string | null>(null);
  const [finalizeUserId, setFinalizeUserId] = useState<string>("investigator-lead");
  const [actionError, setActionError] = useState<string | null>(null);

  // Fetch Existing Dossiers
  const {
    data: dossiers = [],
    isLoading: isDossiersLoading,
  } = useQuery({
    queryKey: ["case-dossiers", caseId],
    queryFn: () => dossiersApi.listDossiers(caseId),
    enabled: isOpen && Boolean(caseId),
  });

  // Calculate actual readiness metrics
  const totalFindings = findings.length;
  const reviewedFindings = findings.filter((f) => f.is_reviewed || f.review_status !== "UNREVIEWED").length;
  const unreviewedFindings = findings.filter((f) => !f.is_reviewed && (f.review_status === "UNREVIEWED" || !f.review_status)).length;
  const inconclusiveFindings = findings.filter(
    (f) => f.review_status === "MARK_INCONCLUSIVE" || f.review_status === "INCONCLUSIVE"
  ).length;
  const contradictoryFindings = findings.filter(
    (f) => f.contradicting_evidence_ids && f.contradicting_evidence_ids.length > 0
  ).length;

  // Generate Dossier Mutation
  const generateMutation = useMutation({
    mutationFn: (payload: DossierGenerateRequest) =>
      dossiersApi.generateDossier(caseId, payload),
    onSuccess: () => {
      setIsGenerating(false);
      setActionError(null);
      queryClient.invalidateQueries({ queryKey: ["case-dossiers", caseId] });
      queryClient.invalidateQueries({ queryKey: ["case-overview", caseId] });
    },
    onError: (err: any) => {
      setActionError(err?.message || "Failed to generate investigation dossier draft.");
    },
  });

  // Finalize Mutation
  const finalizeMutation = useMutation({
    mutationFn: ({ dossierId, userId }: { dossierId: string; userId: string }) =>
      dossiersApi.finalizeDossier(caseId, dossierId, { user_id: userId }),
    onSuccess: () => {
      setFinalizingDossierId(null);
      setActionError(null);
      queryClient.invalidateQueries({ queryKey: ["case-dossiers", caseId] });
      queryClient.invalidateQueries({ queryKey: ["case-overview", caseId] });
    },
    onError: (err: any) => {
      setActionError(err?.message || "Failed to finalize and seal dossier.");
    },
  });

  if (!isOpen) return null;

  const handleCreateDossier = (e: React.FormEvent) => {
    e.preventDefault();
    if (isCaseArchived) {
      setActionError("Cannot generate dossiers in an archived case.");
      return;
    }
    setActionError(null);
    generateMutation.mutate({
      created_by: createdBy.trim() || "investigator-lead",
      scope_and_purpose: scopeAndPurpose.trim() || null,
    });
  };

  const handleConfirmFinalize = (dossierId: string) => {
    if (isCaseArchived) {
      setActionError("Cannot finalize dossiers in an archived case.");
      return;
    }
    setActionError(null);
    finalizeMutation.mutate({
      dossierId,
      userId: finalizeUserId.trim() || "investigator-lead",
    });
  };

  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-black/75 backdrop-blur-sm select-none">
      <div className="w-full max-w-xl bg-brand-charcoal border-l border-brand-slate shadow-2xl flex flex-col h-full text-slate-200 text-xs animate-in slide-in-from-right duration-200">
        {/* Drawer Header */}
        <div className="p-4 border-b border-brand-slate flex items-center justify-between bg-brand-midnight/70">
          <div className="flex items-center gap-2">
            <FileCheck2 className="w-5 h-5 text-brand-cyan" />
            <div>
              <h3 className="text-sm font-semibold text-white">Investigation Dossier Workbench</h3>
              <p className="text-[11px] text-brand-slate-light">
                12-section structured forensic reports & integrity sealing
              </p>
            </div>
          </div>

          <button
            type="button"
            onClick={onClose}
            className="p-1.5 rounded text-brand-slate-light hover:text-white hover:bg-brand-slate/50 transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Drawer Body */}
        <div className="flex-1 overflow-y-auto p-4 space-y-5">
          {/* Action Error Banner */}
          {actionError && (
            <div className="p-3 rounded-lg bg-red-950/40 border border-red-500/40 text-rose-300 text-xs flex items-center gap-2">
              <AlertTriangle className="w-4 h-4 shrink-0" />
              <span>{actionError}</span>
            </div>
          )}

          {/* Review-Readiness Summary */}
          <div className="bg-brand-midnight/70 border border-brand-slate rounded-xl p-3.5 space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-[10px] font-mono uppercase tracking-wider text-brand-slate-light font-semibold">
                Findings Review-Readiness Audit
              </span>
              <span className="text-[10px] font-mono text-brand-cyan">
                {reviewedFindings} / {totalFindings} Reviewed
              </span>
            </div>

            <div className="grid grid-cols-5 gap-1.5 text-center font-mono">
              <div className="p-2 rounded bg-brand-charcoal border border-brand-slate/60">
                <span className="text-xs font-bold text-white block">{totalFindings}</span>
                <span className="text-[9px] text-brand-slate-light">Total</span>
              </div>
              <div className="p-2 rounded bg-emerald-950/30 border border-emerald-500/30">
                <span className="text-xs font-bold text-emerald-300 block">{reviewedFindings}</span>
                <span className="text-[9px] text-emerald-400">Reviewed</span>
              </div>
              <div className="p-2 rounded bg-amber-950/30 border border-amber-500/30">
                <span className="text-xs font-bold text-amber-300 block">{unreviewedFindings}</span>
                <span className="text-[9px] text-amber-400">Awaiting</span>
              </div>
              <div className="p-2 rounded bg-yellow-950/30 border border-yellow-500/30">
                <span className="text-xs font-bold text-yellow-300 block">{inconclusiveFindings}</span>
                <span className="text-[9px] text-yellow-400">Inconclusive</span>
              </div>
              <div className="p-2 rounded bg-rose-950/30 border border-rose-500/30">
                <span className="text-xs font-bold text-rose-300 block">{contradictoryFindings}</span>
                <span className="text-[9px] text-rose-400">Conflicts</span>
              </div>
            </div>

            {unreviewedFindings > 0 && (
              <p className="text-[11px] text-amber-300/90 font-sans leading-tight flex items-start gap-1.5 pt-1">
                <AlertTriangle className="w-3.5 h-3.5 shrink-0 text-amber-400 mt-0.5" />
                <span>
                  {unreviewedFindings} finding(s) remain unreviewed. Generating a dossier will record unreviewed signals as automated indicators without human verification.
                </span>
              </p>
            )}
          </div>

          {/* New Dossier Draft Action Form */}
          {!isGenerating ? (
            <div className="flex items-center justify-between p-3 rounded-lg bg-brand-midnight/40 border border-brand-slate/60">
              <div>
                <h4 className="text-xs font-semibold text-white">Generate Dossier Draft</h4>
                <p className="text-[11px] text-brand-slate-light">
                  Compile current case evidence into 12 structured chapters.
                </p>
              </div>
              <button
                type="button"
                disabled={isCaseArchived}
                onClick={() => setIsGenerating(true)}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-brand-blue hover:bg-brand-blue-hover text-white text-xs font-medium rounded transition-colors disabled:opacity-50"
              >
                <Plus className="w-3.5 h-3.5" />
                <span>New Draft</span>
              </button>
            </div>
          ) : (
            <form onSubmit={handleCreateDossier} className="p-3.5 rounded-lg bg-brand-midnight border border-brand-slate space-y-3">
              <div className="flex items-center justify-between pb-2 border-b border-brand-slate/60">
                <h4 className="text-xs font-semibold text-white">Compile New Dossier Draft</h4>
                <button
                  type="button"
                  onClick={() => setIsGenerating(false)}
                  className="text-brand-slate-light hover:text-white"
                >
                  <X className="w-3.5 h-3.5" />
                </button>
              </div>

              <div className="space-y-1">
                <label className="block text-[11px] font-mono text-brand-slate-light">
                  Created By / Examiner ID
                </label>
                <input
                  type="text"
                  value={createdBy}
                  onChange={(e) => setCreatedBy(e.target.value)}
                  className="w-full bg-brand-midnight border border-brand-slate rounded px-2.5 py-1 text-xs text-white focus:outline-none focus:border-brand-cyan font-mono"
                  placeholder="e.g. lead-investigator"
                />
              </div>

              <div className="space-y-1">
                <label className="block text-[11px] font-mono text-brand-slate-light">
                  Scope and Purpose
                </label>
                <textarea
                  rows={2}
                  value={scopeAndPurpose}
                  onChange={(e) => setScopeAndPurpose(e.target.value)}
                  className="w-full bg-brand-midnight border border-brand-slate rounded p-2 text-xs text-white focus:outline-none focus:border-brand-cyan font-sans resize-none"
                  placeholder="Inquiry scope..."
                />
              </div>

              <div className="flex items-center justify-end gap-2 pt-1">
                <button
                  type="button"
                  onClick={() => setIsGenerating(false)}
                  className="px-2.5 py-1 rounded border border-brand-slate text-xs text-slate-300 hover:text-white"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={generateMutation.isPending || isCaseArchived}
                  className="inline-flex items-center gap-1.5 px-3 py-1 bg-brand-blue hover:bg-brand-blue-hover text-white text-xs font-medium rounded transition-colors disabled:opacity-50"
                >
                  {generateMutation.isPending ? (
                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  ) : (
                    <FileCheck2 className="w-3.5 h-3.5" />
                  )}
                  <span>Compile Draft</span>
                </button>
              </div>
            </form>
          )}

          {/* Dossiers Listing */}
          <div className="space-y-3">
            <h4 className="text-[10px] font-mono font-semibold uppercase tracking-wider text-brand-slate-light">
              Case Evidence Dossiers ({dossiers.length})
            </h4>

            {isDossiersLoading && (
              <div className="p-6 text-center text-slate-400">
                <Loader2 className="w-5 h-5 animate-spin text-brand-cyan mx-auto mb-1" />
                <p>Retrieving dossiers...</p>
              </div>
            )}

            {!isDossiersLoading && dossiers.length === 0 && (
              <div className="p-6 text-center bg-brand-midnight/40 rounded-lg border border-brand-slate/40 text-slate-400">
                <FileText className="w-6 h-6 mx-auto mb-1 text-slate-500 opacity-60" />
                <p className="font-semibold text-white text-xs">No Dossiers Compiled</p>
                <p className="text-[11px] text-brand-slate-light mt-0.5">
                  Compile an investigation dossier to generate structured vector PDF and JSON evidence packages.
                </p>
              </div>
            )}

            {dossiers.map((dos) => {
              const isApproved = dos.status === "APPROVED";
              const isFinalizingThis = finalizingDossierId === dos.id;

              return (
                <div
                  key={dos.id}
                  className={`p-3.5 rounded-lg border transition-all space-y-2.5 ${
                    isApproved
                      ? "bg-brand-midnight/80 border-emerald-500/40 shadow-sm"
                      : "bg-brand-midnight/60 border-brand-slate/70"
                  }`}
                >
                  <div className="flex items-start justify-between gap-2">
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="font-bold text-white text-xs">
                          {dos.title}
                        </span>
                        <StatusBadge status={dos.status} type="dossier" />
                        <span className="text-[10px] font-mono text-brand-slate-light">
                          v{dos.version}
                        </span>
                      </div>
                      <div className="text-[10px] font-mono text-slate-400 mt-0.5">
                        ID: {dos.id} • {new Date(dos.created_at).toLocaleString()}
                      </div>
                    </div>

                    {/* Export Actions */}
                    <div className="flex items-center gap-1.5 shrink-0">
                      <a
                        href={dossiersApi.getExportUrl(caseId, dos.id, "pdf")}
                        download
                        className="inline-flex items-center gap-1 px-2 py-1 rounded bg-brand-midnight border border-brand-slate text-[11px] text-brand-cyan hover:bg-brand-slate/40 transition-colors font-mono"
                        title="Download Vector PDF Dossier"
                      >
                        <Download className="w-3 h-3" />
                        <span>PDF</span>
                      </a>
                      <a
                        href={dossiersApi.getExportUrl(caseId, dos.id, "json")}
                        download
                        className="inline-flex items-center gap-1 px-2 py-1 rounded bg-brand-midnight border border-brand-slate text-[11px] text-brand-cyan hover:bg-brand-slate/40 transition-colors font-mono"
                        title="Download Structured JSON Dossier"
                      >
                        <Download className="w-3 h-3" />
                        <span>JSON</span>
                      </a>
                    </div>
                  </div>

                  {/* Purpose / Scope */}
                  {dos.scope_and_purpose && (
                    <p className="text-[11px] text-slate-300 font-sans line-clamp-2">
                      {dos.scope_and_purpose}
                    </p>
                  )}

                  {/* Canonical Integrity Hash (If finalized) */}
                  {isApproved && dos.content_hash && (
                    <div className="p-2 rounded bg-emerald-950/30 border border-emerald-500/30 space-y-0.5">
                      <div className="flex items-center gap-1 text-[10px] font-mono text-emerald-300 font-semibold uppercase">
                        <ShieldCheck className="w-3.5 h-3.5 text-emerald-400" />
                        <span>Immutable Canonical SHA-256 Digest</span>
                      </div>
                      <div className="text-[10px] font-mono text-slate-200 select-all break-all">
                        {dos.content_hash}
                      </div>
                    </div>
                  )}

                  {/* Finalize Action (If draft) */}
                  {!isApproved && !isFinalizingThis && (
                    <div className="flex items-center justify-between pt-1 border-t border-brand-slate/40">
                      <span className="text-[10px] text-brand-slate-light font-sans">
                        Draft is mutable. Finalize to seal canonical hash.
                      </span>
                      <button
                        type="button"
                        disabled={isCaseArchived}
                        onClick={() => setFinalizingDossierId(dos.id)}
                        className="inline-flex items-center gap-1 text-[11px] font-mono text-emerald-400 hover:text-emerald-300 disabled:opacity-50"
                      >
                        <Lock className="w-3 h-3" />
                        <span>Finalize & Seal</span>
                      </button>
                    </div>
                  )}

                  {/* Inline Finalization Confirmation */}
                  {isFinalizingThis && (
                    <div className="p-3 rounded bg-brand-midnight border border-emerald-500/50 space-y-2 mt-2">
                      <div className="flex items-center gap-1.5 text-emerald-300 font-semibold text-xs">
                        <Lock className="w-3.5 h-3.5 text-emerald-400" />
                        <span>Confirm Dossier Finalization & Sealing</span>
                      </div>
                      <p className="text-[11px] text-slate-300 leading-tight">
                        Finalization freezes this dossier snapshot and computes an immutable SHA-256 canonical hash. Subsequent case activity will not alter this snapshot.
                      </p>

                      <div className="space-y-1">
                        <label className="text-[10px] font-mono text-brand-slate-light block">
                          Examiner / Finalizing User ID
                        </label>
                        <input
                          type="text"
                          value={finalizeUserId}
                          onChange={(e) => setFinalizeUserId(e.target.value)}
                          className="w-full bg-brand-charcoal border border-brand-slate rounded px-2.5 py-1 text-xs text-white font-mono focus:outline-none focus:border-brand-cyan"
                        />
                      </div>

                      <div className="flex items-center justify-end gap-2 pt-1">
                        <button
                          type="button"
                          onClick={() => setFinalizingDossierId(null)}
                          className="px-2 py-0.5 rounded border border-brand-slate text-[11px] text-slate-300"
                        >
                          Cancel
                        </button>
                        <button
                          type="button"
                          disabled={finalizeMutation.isPending || isCaseArchived}
                          onClick={() => handleConfirmFinalize(dos.id)}
                          className="inline-flex items-center gap-1 px-3 py-1 bg-emerald-600 hover:bg-emerald-500 text-white text-[11px] font-medium rounded transition-colors disabled:opacity-50 font-mono"
                        >
                          {finalizeMutation.isPending ? (
                            <Loader2 className="w-3 h-3 animate-spin" />
                          ) : (
                            <ShieldCheck className="w-3 h-3" />
                          )}
                          <span>Seal Snapshot</span>
                        </button>
                      </div>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
};
