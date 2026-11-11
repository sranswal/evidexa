import React, { useState } from "react";
import { useParams, Link } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  FileCheck2,
  Plus,
  Download,
  ShieldCheck,
  ShieldAlert,
  Loader2,
  Lock,
  ChevronDown,
  ChevronUp,
  CheckCircle2,
  Layers,
  Copy,
  Check,
} from "lucide-react";
import { Card } from "../components/ui/Card";
import { Button } from "../components/ui/Button";
import { StatusBadge } from "../components/ui/Badge";
import { EmptyState } from "../components/ui/EmptyState";
import { Modal } from "../components/ui/Modal";
import { dossiersApi } from "../api/dossiers";
import { findingsApi } from "../api/findings";
import { casesApi } from "../api/cases";
import type { DossierGenerateRequest, InvestigationDossier } from "../types/api";

const DOSSIER_12_SECTIONS = [
  "1. Executive Summary & Investigation Mandate",
  "2. Target Entity Profile & Commercial Identifiers",
  "3. Document Inventory & Cryptographic Chain of Custody",
  "4. Multilingual OCR & Bilingual Text Extraction",
  "5. Visual Forensics (ELA & Copy-Move Heatmaps)",
  "6. Structural PDF Analysis & Metadata Integrity",
  "7. Cross-Document Numerical & Date Consistency",
  "8. Entity Resolution & Cross-Case Intelligence",
  "9. Forensic Evidence Graph & Relational Clustering",
  "10. Epistemic Confidence Boundaries & Automated Warnings",
  "11. Investigator Review History & Determinations",
  "12. Cryptographic Content Seal & Audit Attribution",
];

export const DossiersPage: React.FC = () => {
  const { caseId } = useParams<{ caseId: string }>();
  const queryClient = useQueryClient();

  // Create Modal State
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  const [scopeAndPurpose, setScopeAndPurpose] = useState(
    "Comprehensive verification and multi-document consistency audit."
  );
  const [createdBy, setCreatedBy] = useState("lead-investigator");
  const [createError, setCreateError] = useState<string | null>(null);

  // Finalize State
  const [finalizingDossierId, setFinalizingDossierId] = useState<string | null>(null);
  const [finalizeUserId, setFinalizeUserId] = useState("lead-investigator");
  const [finalizeError, setFinalizeError] = useState<string | null>(null);

  // Expanded Sections State
  const [expandedDossierIds, setExpandedDossierIds] = useState<Set<string>>(new Set());
  const [copiedHash, setCopiedHash] = useState<string | null>(null);

  // 1. Fetch Case Context
  const { data: currentCase } = useQuery({
    queryKey: ["case", caseId],
    queryFn: () => (caseId ? casesApi.getCase(caseId) : null),
    enabled: Boolean(caseId),
  });

  // 2. Fetch Findings for review readiness metrics
  const { data: findings = [] } = useQuery({
    queryKey: ["case-findings", caseId],
    queryFn: () => (caseId ? findingsApi.getAggregatedFindings(caseId) : []),
    enabled: Boolean(caseId),
  });

  // 3. Fetch Case Dossiers
  const { data: dossiers = [], isLoading: isDossiersLoading } = useQuery({
    queryKey: ["case-dossiers", caseId],
    queryFn: () => (caseId ? dossiersApi.listDossiers(caseId) : []),
    enabled: Boolean(caseId),
  });

  // Readiness calculations
  const totalFindings = findings.length;
  const reviewedFindings = findings.filter(
    (f) => f.is_reviewed || (f.review_status && f.review_status !== "UNREVIEWED")
  ).length;
  const unreviewedFindings = totalFindings - reviewedFindings;
  const readinessPercent = totalFindings > 0 ? Math.round((reviewedFindings / totalFindings) * 100) : 100;

  // Mutations
  const generateMutation = useMutation({
    mutationFn: (payload: DossierGenerateRequest) =>
      dossiersApi.generateDossier(caseId!, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["case-dossiers", caseId] });
      setIsCreateModalOpen(false);
      setCreateError(null);
    },
    onError: (err: any) => {
      setCreateError(err.message || "Failed to generate investigation dossier draft.");
    },
  });

  const finalizeMutation = useMutation({
    mutationFn: ({ dossierId, userId }: { dossierId: string; userId: string }) =>
      dossiersApi.finalizeDossier(caseId!, dossierId, { user_id: userId }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["case-dossiers", caseId] });
      setFinalizingDossierId(null);
      setFinalizeError(null);
    },
    onError: (err: any) => {
      setFinalizeError(err.message || "Failed to finalize and seal dossier.");
    },
  });

  const handleCreateSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!scopeAndPurpose.trim()) {
      setCreateError("Scope and purpose is required.");
      return;
    }
    generateMutation.mutate({
      scope_and_purpose: scopeAndPurpose.trim(),
      created_by: createdBy.trim() || undefined,
    });
  };

  const handleFinalizeSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!finalizingDossierId) return;
    finalizeMutation.mutate({
      dossierId: finalizingDossierId,
      userId: finalizeUserId.trim() || "lead-investigator",
    });
  };

  const toggleExpand = (id: string) => {
    setExpandedDossierIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const handleCopyHash = async (hash: string) => {
    await navigator.clipboard.writeText(hash);
    setCopiedHash(hash);
    setTimeout(() => setCopiedHash(null), 2000);
  };

  if (!caseId) {
    return (
      <div className="p-8 text-center text-slate-400">
        <p>No active case identifier provided.</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Top Banner & Actions */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-2 border-b border-evidexa-slate/60">
        <div>
          <div className="flex items-center gap-2 text-xs font-mono text-slate-400 mb-1">
            <Link to="/cases" className="hover:text-evidexa-cyan">Cases</Link>
            <span>/</span>
            <Link to={`/cases/${caseId}/overview`} className="hover:text-evidexa-cyan font-bold text-slate-300">
              {currentCase?.case_reference || caseId.slice(0, 8)}
            </Link>
            <span>/</span>
            <span className="text-evidexa-cyan font-semibold">Dossiers</span>
          </div>
          <h1 className="text-2xl font-bold tracking-tight text-white font-sans flex items-center gap-2.5">
            <FileCheck2 className="w-7 h-7 text-evidexa-cyan" />
            Evidence Dossiers & Legal Export
          </h1>
          <p className="text-sm text-slate-400 mt-1">
            Compile, inspect, finalize, and export court-ready evidentiary dossiers with cryptographic SHA-256 integrity sealing.
          </p>
        </div>

        <Button
          onClick={() => setIsCreateModalOpen(true)}
          disabled={currentCase?.status === "ARCHIVED"}
          className="self-start sm:self-auto"
        >
          <Plus className="w-4 h-4 mr-1.5" />
          Generate New Dossier
        </Button>
      </div>

      {/* Epistemic Guardrail Notice Banner */}
      <div className="bg-evidexa-charcoal border border-amber-500/30 rounded-lg p-3.5 flex items-start gap-3 text-xs text-amber-200/90 shadow-sm">
        <ShieldAlert className="w-4 h-4 text-amber-400 shrink-0 mt-0.5" />
        <div>
          <span className="font-semibold text-white">Epistemic Guardrail:</span> Investigation dossiers synthesize verified document evidence, physical observations, and forensic findings across 12 structured analytical sections. Finalized dossiers are cryptographically frozen with immutable SHA-256 content hashes.
        </div>
      </div>

      {/* Dossier Review-Readiness Metrics */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card className="p-4 space-y-1">
          <span className="text-xs font-mono uppercase tracking-wider text-slate-400">Total Case Findings</span>
          <div className="text-2xl font-bold text-white font-mono">{totalFindings}</div>
          <span className="text-[11px] text-slate-400">Forensic & consistency observations</span>
        </Card>

        <Card className="p-4 space-y-1">
          <span className="text-xs font-mono uppercase tracking-wider text-slate-400">Reviewed Findings</span>
          <div className="text-2xl font-bold text-emerald-400 font-mono">{reviewedFindings}</div>
          <span className="text-[11px] text-slate-400">Validated by investigator review</span>
        </Card>

        <Card className="p-4 space-y-1">
          <span className="text-xs font-mono uppercase tracking-wider text-slate-400">Pending Review</span>
          <div className="text-2xl font-bold text-amber-400 font-mono">{unreviewedFindings}</div>
          <span className="text-[11px] text-slate-400">Heuristics awaiting adjudication</span>
        </Card>

        <Card className="p-4 space-y-1">
          <div className="flex items-center justify-between">
            <span className="text-xs font-mono uppercase tracking-wider text-slate-400">Readiness Score</span>
            <span className="text-xs font-mono text-evidexa-cyan font-bold">{readinessPercent}%</span>
          </div>
          <div className="w-full bg-evidexa-midnight h-2 rounded-full overflow-hidden mt-1.5 border border-evidexa-slate">
            <div
              className="bg-evidexa-cyan h-full rounded-full transition-all duration-300"
              style={{ width: `${readinessPercent}%` }}
            />
          </div>
          <span className="text-[11px] text-slate-400 block pt-0.5">
            {readinessPercent >= 100 ? "Ready for final legal sealing" : "Review pending findings prior to sealing"}
          </span>
        </Card>
      </div>

      {/* Existing Case Dossiers */}
      <div className="space-y-4">
        <div className="flex items-center justify-between pb-1">
          <h2 className="text-lg font-semibold text-white flex items-center gap-2">
            Compiled Investigation Dossiers
            <span className="text-xs font-mono font-normal bg-evidexa-slate px-2 py-0.5 rounded text-slate-300">
              ({dossiers.length})
            </span>
          </h2>
        </div>

        {isDossiersLoading ? (
          <div className="p-12 flex items-center justify-center text-slate-400 text-sm">
            <Loader2 className="w-5 h-5 animate-spin mr-2 text-evidexa-cyan" />
            Loading investigation dossiers...
          </div>
        ) : dossiers.length === 0 ? (
          <EmptyState
            title="No Investigation Dossiers Compiled"
            description="Generate a comprehensive 12-section investigation dossier draft compiling all case evidence, forensic observations, and graph relationships."
            icon={<FileCheck2 className="w-8 h-8 text-slate-400" />}
            action={
              <Button onClick={() => setIsCreateModalOpen(true)}>
                <Plus className="w-4 h-4 mr-1.5" />
                Generate First Dossier
              </Button>
            }
          />
        ) : (
          <div className="space-y-4">
            {dossiers.map((dos: InvestigationDossier) => {
              const isApproved = dos.status === "APPROVED";
              const isExpanded = expandedDossierIds.has(dos.id);

              return (
                <Card
                  key={dos.id}
                  className={`p-5 space-y-4 transition-all hover:border-slate-600 ${
                    isApproved ? "border-emerald-500/40" : ""
                  }`}
                >
                  <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-4">
                    <div className="flex items-start gap-3">
                      <div className="p-2.5 bg-evidexa-midnight border border-evidexa-slate rounded-lg shrink-0 mt-0.5">
                        {isApproved ? (
                          <ShieldCheck className="w-5 h-5 text-emerald-400" />
                        ) : (
                          <FileCheck2 className="w-5 h-5 text-evidexa-cyan" />
                        )}
                      </div>
                      <div>
                        <div className="flex items-center gap-2.5 flex-wrap">
                          <span className="font-semibold text-white text-base">
                            {dos.title}
                          </span>
                          <StatusBadge status={dos.status} type="dossier" />
                          <span className="text-xs font-mono text-slate-400 bg-evidexa-midnight px-2 py-0.5 rounded border border-evidexa-slate">
                            v{dos.version}
                          </span>
                        </div>
                        <div className="flex items-center gap-2 sm:gap-3 mt-1.5 text-xs text-slate-400 flex-wrap font-mono">
                          <span>Reference: <span className="text-slate-300">{dos.dossier_reference || dos.id}</span></span>
                          <span>•</span>
                          <span>Created: <span className="text-slate-300">{new Date(dos.created_at).toLocaleString()}</span></span>
                        </div>
                      </div>
                    </div>

                    {/* Actions: Finalize & Exports */}
                    <div className="flex items-center gap-2 self-start shrink-0 flex-wrap">
                      {!isApproved && (
                        <Button
                          variant="secondary"
                          size="sm"
                          onClick={() => setFinalizingDossierId(dos.id)}
                        >
                          <Lock className="w-3.5 h-3.5 mr-1 text-evidexa-cyan" />
                          Seal & Finalize
                        </Button>
                      )}

                      <a
                        href={dossiersApi.getExportUrl(caseId, dos.id, "pdf")}
                        download
                        className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium bg-evidexa-charcoal text-slate-200 border border-evidexa-slate hover:bg-slate-800 hover:text-white transition-all font-mono"
                        title="Download official Vector PDF Dossier"
                      >
                        <Download className="w-3.5 h-3.5 text-evidexa-cyan" />
                        <span>PDF</span>
                      </a>

                      <a
                        href={dossiersApi.getExportUrl(caseId, dos.id, "json")}
                        download
                        className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium bg-evidexa-charcoal text-slate-200 border border-evidexa-slate hover:bg-slate-800 hover:text-white transition-all font-mono"
                        title="Download structured JSON legal artifact"
                      >
                        <Download className="w-3.5 h-3.5 text-evidexa-cyan" />
                        <span>JSON</span>
                      </a>

                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => toggleExpand(dos.id)}
                      >
                        {isExpanded ? (
                          <>
                            <ChevronUp className="w-3.5 h-3.5 mr-1" />
                            <span>Hide Sections</span>
                          </>
                        ) : (
                          <>
                            <ChevronDown className="w-3.5 h-3.5 mr-1" />
                            <span>12 Sections</span>
                          </>
                        )}
                      </Button>
                    </div>
                  </div>

                  {/* Purpose / Scope */}
                  {dos.scope_and_purpose && (
                    <div className="bg-evidexa-midnight/60 rounded p-3 text-xs text-slate-300 border border-evidexa-slate/60 leading-relaxed">
                      <span className="font-semibold text-slate-400 block mb-0.5">Inquiry Mandate & Scope:</span>
                      {dos.scope_and_purpose}
                    </div>
                  )}

                  {/* Cryptographic Content Hash Seal */}
                  {isApproved && (
                    <div className="p-3 rounded bg-emerald-950/20 border border-emerald-500/30 flex items-center justify-between gap-3 text-xs">
                      <div className="flex items-center gap-2">
                        <ShieldCheck className="w-4 h-4 text-emerald-400 shrink-0" />
                        <div>
                          <span className="font-semibold text-emerald-300 block font-mono text-[11px] uppercase">
                            Cryptographic Integrity Seal
                          </span>
                          <span className="font-mono text-slate-300 break-all select-all text-[11px]">
                            {dos.content_hash || "SEALED_IMMUTABLE_HASH_ACTIVE"}
                          </span>
                        </div>
                      </div>
                      <button
                        type="button"
                        onClick={() => handleCopyHash(dos.content_hash || "")}
                        className="p-1.5 rounded bg-emerald-950/60 hover:bg-emerald-900 border border-emerald-700 text-emerald-300 transition shrink-0"
                        title="Copy SHA-256 seal digest"
                      >
                        {copiedHash === dos.content_hash ? (
                          <Check className="w-3.5 h-3.5 text-emerald-400" />
                        ) : (
                          <Copy className="w-3.5 h-3.5" />
                        )}
                      </button>
                    </div>
                  )}

                  {/* 12-Section Analytical Breakdown Accordion */}
                  {isExpanded && (
                    <div className="pt-3 border-t border-evidexa-slate/60 space-y-3">
                      <div className="flex items-center justify-between">
                        <h4 className="text-xs font-semibold text-slate-300 uppercase tracking-wider flex items-center gap-1.5">
                          <Layers className="w-3.5 h-3.5 text-evidexa-cyan" />
                          Included 12 Analytical Sections
                        </h4>
                        <span className="text-[11px] text-slate-400">Structured Forensic Dossier Standard</span>
                      </div>

                      <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                        {DOSSIER_12_SECTIONS.map((sec, idx) => (
                          <div
                            key={idx}
                            className="flex items-center gap-2 p-2 rounded bg-evidexa-midnight/80 border border-evidexa-slate/60 text-xs text-slate-300"
                          >
                            <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400 shrink-0" />
                            <span className="truncate">{sec}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </Card>
              );
            })}
          </div>
        )}
      </div>

      {/* Modal: Generate New Dossier */}
      <Modal
        isOpen={isCreateModalOpen}
        onClose={() => setIsCreateModalOpen(false)}
        title="Generate Investigation Dossier Draft"
      >
        <p className="text-xs text-slate-400 mb-4">
          Synthesize all case documents, OCR transcripts, forensic observations, and entity relationships into an authoritative 12-section dossier draft.
        </p>

        {createError && (
          <div className="mb-4 p-3 bg-rose-950/60 border border-rose-800 rounded text-xs text-rose-300">
            {createError}
          </div>
        )}

        <form onSubmit={handleCreateSubmit} className="space-y-4">
          <div>
            <label className="text-xs font-semibold text-slate-300 block mb-1">Inquiry Scope & Purpose *</label>
            <textarea
              value={scopeAndPurpose}
              onChange={(e) => setScopeAndPurpose(e.target.value)}
              placeholder="e.g., Forensic audit of regional vendor procurement and payment discrepancies..."
              rows={3}
              className="w-full bg-evidexa-midnight border border-evidexa-slate rounded px-3 py-2 text-sm text-white focus:outline-none focus:border-evidexa-cyan"
              required
            />
          </div>

          <div>
            <label className="text-xs font-semibold text-slate-300 block mb-1">Lead Examiner Identifier</label>
            <input
              type="text"
              value={createdBy}
              onChange={(e) => setCreatedBy(e.target.value)}
              className="w-full bg-evidexa-midnight border border-evidexa-slate rounded px-3 py-2 text-sm text-white focus:outline-none focus:border-evidexa-cyan font-mono"
            />
          </div>

          <div className="flex items-center justify-end gap-3 pt-3 border-t border-evidexa-slate/60">
            <Button
              type="button"
              variant="secondary"
              size="sm"
              onClick={() => setIsCreateModalOpen(false)}
            >
              Cancel
            </Button>
            <Button
              type="submit"
              variant="primary"
              size="sm"
              isLoading={generateMutation.isPending}
            >
              Compile Dossier
            </Button>
          </div>
        </form>
      </Modal>

      {/* Modal: Finalize & Seal Dossier */}
      <Modal
        isOpen={Boolean(finalizingDossierId)}
        onClose={() => setFinalizingDossierId(null)}
        title="Cryptographically Seal Investigation Dossier"
      >
        <p className="text-xs text-slate-400 mb-4">
          Finalizing this dossier transitions it to <span className="text-emerald-400 font-semibold">APPROVED</span>, computes an immutable SHA-256 integrity hash, and freezes the evidence record for court submission.
        </p>

        {finalizeError && (
          <div className="mb-4 p-3 bg-rose-950/60 border border-rose-800 rounded text-xs text-rose-300">
            {finalizeError}
          </div>
        )}

        <form onSubmit={handleFinalizeSubmit} className="space-y-4">
          <div>
            <label className="text-xs font-semibold text-slate-300 block mb-1">Authorizing Examiner Identifier *</label>
            <input
              type="text"
              value={finalizeUserId}
              onChange={(e) => setFinalizeUserId(e.target.value)}
              className="w-full bg-evidexa-midnight border border-evidexa-slate rounded px-3 py-2 text-sm text-white focus:outline-none focus:border-evidexa-cyan font-mono"
              required
            />
          </div>

          <div className="p-3 bg-emerald-950/30 border border-emerald-500/30 rounded text-xs text-emerald-300 flex items-start gap-2">
            <Lock className="w-4 h-4 text-emerald-400 shrink-0 mt-0.5" />
            <span>
              Once sealed, the dossier cannot be modified. Any subsequent findings will require compiling a new version.
            </span>
          </div>

          <div className="flex items-center justify-end gap-3 pt-3 border-t border-evidexa-slate/60">
            <Button
              type="button"
              variant="secondary"
              size="sm"
              onClick={() => setFinalizingDossierId(null)}
            >
              Cancel
            </Button>
            <Button
              type="submit"
              variant="primary"
              size="sm"
              isLoading={finalizeMutation.isPending}
            >
              Seal & Approve
            </Button>
          </div>
        </form>
      </Modal>
    </div>
  );
};
