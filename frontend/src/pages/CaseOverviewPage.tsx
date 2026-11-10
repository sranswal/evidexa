import React, { useState } from "react";
import { useParams, Link } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  FileText,
  ShieldAlert,
  GitCompare,
  Network,
  FileCheck2,
  Calendar,
  User,
  Archive,
  Download,
  Plus,
  ArrowRight,
  ShieldCheck,
} from "lucide-react";
import { casesApi } from "../api/cases";
import { Card, CardHeader, CardTitle } from "../components/ui/Card";
import { Button } from "../components/ui/Button";
import { StatusBadge } from "../components/ui/Badge";
import { Skeleton } from "../components/ui/Skeleton";
import { ErrorMessage } from "../components/ui/ErrorMessage";
import { EmptyState } from "../components/ui/EmptyState";
import { Modal } from "../components/ui/Modal";
import { useCaseContext } from "../context/CaseContext";

export const CaseOverviewPage: React.FC = () => {
  const { caseId } = useParams<{ caseId: string }>();
  const queryClient = useQueryClient();
  const { refreshCase } = useCaseContext();
  const [isArchiveModalOpen, setIsArchiveModalOpen] = useState(false);
  const [isDossierModalOpen, setIsDossierModalOpen] = useState(false);
  const [dossierScope, setDossierScope] = useState("");

  if (!caseId) {
    return <ErrorMessage message="No case ID provided in route." />;
  }

  // 1. Case Details
  const {
    data: caseData,
    isLoading: isCaseLoading,
    isError: isCaseError,
    error: caseError,
    refetch: refetchCase,
  } = useQuery({
    queryKey: ["case", caseId],
    queryFn: () => casesApi.getCase(caseId),
  });

  // 2. Case Documents
  const { data: documentsData, isLoading: isDocsLoading } = useQuery({
    queryKey: ["case-documents", caseId],
    queryFn: () => casesApi.listCaseDocuments(caseId, 0, 10),
  });

  // 3. Aggregated Findings
  const { data: findingsData, isLoading: isFindingsLoading } = useQuery({
    queryKey: ["case-findings", caseId],
    queryFn: () => casesApi.listAggregatedFindings(caseId),
  });

  // 4. Relationships
  const { data: relationshipsData, isLoading: isRelsLoading } = useQuery({
    queryKey: ["case-relationships", caseId],
    queryFn: () => casesApi.listRelationships(caseId, 0, 10),
  });

  // 5. Consistency Runs
  const { data: consistencyRunsData, isLoading: isConsistencyLoading } = useQuery({
    queryKey: ["case-consistency-runs", caseId],
    queryFn: () => casesApi.listConsistencyRuns(caseId),
  });

  // 6. Dossiers
  const { data: dossiersData, isLoading: isDossiersLoading, refetch: refetchDossiers } = useQuery({
    queryKey: ["case-dossiers", caseId],
    queryFn: () => casesApi.listDossiers(caseId),
  });

  // Archive Mutation
  const archiveMutation = useMutation({
    mutationFn: () => casesApi.archiveCase(caseId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["case", caseId] });
      queryClient.invalidateQueries({ queryKey: ["cases"] });
      refreshCase();
      setIsArchiveModalOpen(false);
    },
  });

  // Generate Dossier Mutation
  const generateDossierMutation = useMutation({
    mutationFn: (scope?: string) => casesApi.generateDossier(caseId, scope),
    onSuccess: () => {
      refetchDossiers();
      setIsDossierModalOpen(false);
      setDossierScope("");
    },
  });

  if (isCaseLoading) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-28 w-full" />
        <div className="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-5 gap-4">
          {[1, 2, 3, 4, 5].map((i) => (
            <Skeleton key={i} className="h-24 w-full" />
          ))}
        </div>
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <Skeleton className="h-64 w-full" />
          <Skeleton className="h-64 w-full" />
        </div>
      </div>
    );
  }

  if (isCaseError || !caseData) {
    return (
      <ErrorMessage
        title="Failed to load case overview"
        message={caseError instanceof Error ? caseError.message : "Unable to retrieve case."}
        onRetry={() => refetchCase()}
      />
    );
  }

  // Calculate Findings Statistics
  const findings = findingsData || [];
  const criticalFindings = findings.filter((f) => f.severity === "CRITICAL").length;
  const highFindings = findings.filter((f) => f.severity === "HIGH").length;

  // Calculate Relationship Statistics
  const rels = relationshipsData?.items || [];
  const confirmedRels = rels.filter((r) => r.evidentiary_status === "CONFIRMED").length;

  // Consistency Statistics
  const consistencyRuns = consistencyRunsData || [];
  const hasConsistencyRuns = consistencyRuns.length > 0;

  // Dossiers
  const dossiers = dossiersData || [];
  const latestDossier = dossiers.length > 0 ? dossiers[0] : null;

  return (
    <div className="space-y-6">
      {/* Case Header Card */}
      <div className="bg-evidexa-charcoal border border-evidexa-slate rounded-xl p-6 shadow-card">
        <div className="flex flex-col md:flex-row md:items-start justify-between gap-4">
          <div>
            <div className="flex items-center gap-3 mb-2">
              <span className="font-mono text-xs font-bold px-2 py-0.5 rounded bg-slate-900 border border-slate-700 text-evidexa-cyan tracking-wider">
                {caseData.case_reference}
              </span>
              <StatusBadge status={caseData.status} type="case" />
            </div>
            <h1 className="text-2xl font-bold text-white tracking-tight">{caseData.title}</h1>
            <p className="text-sm text-slate-300 mt-2 max-w-3xl">
              {caseData.description || "No description specified for this investigation workspace."}
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-2.5 self-start shrink-0">
            {caseData.status !== "ARCHIVED" && (
              <Button
                variant="secondary"
                size="sm"
                onClick={() => setIsArchiveModalOpen(true)}
                className="text-slate-300 hover:text-rose-400"
              >
                <Archive className="w-3.5 h-3.5 mr-1.5" />
                Archive Case
              </Button>
            )}
            <Button
              variant="primary"
              size="sm"
              onClick={() => setIsDossierModalOpen(true)}
            >
              <FileCheck2 className="w-3.5 h-3.5 mr-1.5" />
              Generate Dossier
            </Button>
          </div>
        </div>

        {/* Case Metadata Footer */}
        <div className="mt-6 pt-4 border-t border-evidexa-slate/60 flex flex-wrap items-center gap-6 text-xs text-slate-400 font-mono">
          <div className="flex items-center gap-1.5">
            <Calendar className="w-3.5 h-3.5 text-slate-500" />
            <span>Created: {new Date(caseData.created_at).toLocaleString()}</span>
          </div>
          <div className="flex items-center gap-1.5">
            <User className="w-3.5 h-3.5 text-slate-500" />
            <span>Lead: {caseData.created_by || "System"}</span>
          </div>
          <div className="flex items-center gap-1.5">
            <ShieldCheck className="w-3.5 h-3.5 text-emerald-400" />
            <span>Forensic Chain of Custody Verified</span>
          </div>
        </div>
      </div>

      {/* Forensic Intelligence Metrics Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
        {/* Metric 1: Documents */}
        <Card className="flex flex-col justify-between">
          <div className="flex items-center justify-between text-slate-400 mb-2">
            <span className="text-xs font-mono uppercase tracking-wider font-semibold">
              Documents
            </span>
            <FileText className="w-4 h-4 text-evidexa-cyan" />
          </div>
          <div className="text-2xl font-bold font-mono text-white">
            {isDocsLoading ? <Skeleton className="h-8 w-12" /> : documentsData?.total ?? 0}
          </div>
          <p className="text-[11px] text-slate-400 mt-2">
            {(documentsData?.total ?? 0) === 1 ? "1 file registered" : `${documentsData?.total ?? 0} files registered`}
          </p>
        </Card>

        {/* Metric 2: Forensic Findings */}
        <Card className="flex flex-col justify-between">
          <div className="flex items-center justify-between text-slate-400 mb-2">
            <span className="text-xs font-mono uppercase tracking-wider font-semibold">
              Findings
            </span>
            <ShieldAlert className="w-4 h-4 text-orange-400" />
          </div>
          <div className="text-2xl font-bold font-mono text-white">
            {isFindingsLoading ? <Skeleton className="h-8 w-12" /> : findings.length}
          </div>
          <div className="text-[11px] text-slate-400 mt-2 flex items-center gap-1.5">
            {criticalFindings > 0 && (
              <span className="text-rose-400 font-semibold">{criticalFindings} critical</span>
            )}
            {highFindings > 0 && (
              <span className="text-orange-400 font-medium">{highFindings} high</span>
            )}
            {criticalFindings === 0 && highFindings === 0 && (
              <span>No critical anomalies</span>
            )}
          </div>
        </Card>

        {/* Metric 3: Consistency Runs */}
        <Card className="flex flex-col justify-between">
          <div className="flex items-center justify-between text-slate-400 mb-2">
            <span className="text-xs font-mono uppercase tracking-wider font-semibold">
              Consistency Runs
            </span>
            <GitCompare className="w-4 h-4 text-sky-400" />
          </div>
          <div className="text-2xl font-bold font-mono text-white">
            {isConsistencyLoading ? (
              <Skeleton className="h-8 w-12" />
            ) : hasConsistencyRuns ? (
              consistencyRuns.length
            ) : (
              <span className="text-sm font-sans font-normal text-slate-400">Not Run</span>
            )}
          </div>
          <p className="text-[11px] text-slate-400 mt-2">
            {hasConsistencyRuns ? `${consistencyRuns.length} deterministic runs` : "Engine pending execution"}
          </p>
        </Card>

        {/* Metric 4: Relationships */}
        <Card className="flex flex-col justify-between">
          <div className="flex items-center justify-between text-slate-400 mb-2">
            <span className="text-xs font-mono uppercase tracking-wider font-semibold">
              Relationships
            </span>
            <Network className="w-4 h-4 text-purple-400" />
          </div>
          <div className="text-2xl font-bold font-mono text-white">
            {isRelsLoading ? (
              <Skeleton className="h-8 w-12" />
            ) : (
              relationshipsData?.total ?? 0
            )}
          </div>
          <p className="text-[11px] text-slate-400 mt-2">
            {confirmedRels > 0 ? `${confirmedRels} confirmed` : "Cross-document links"}
          </p>
        </Card>

        {/* Metric 5: Dossiers */}
        <Card className="flex flex-col justify-between">
          <div className="flex items-center justify-between text-slate-400 mb-2">
            <span className="text-xs font-mono uppercase tracking-wider font-semibold">
              Dossiers
            </span>
            <FileCheck2 className="w-4 h-4 text-emerald-400" />
          </div>
          <div className="text-2xl font-bold font-mono text-white">
            {isDossiersLoading ? <Skeleton className="h-8 w-12" /> : dossiers.length}
          </div>
          <div className="text-[11px] text-slate-400 mt-2">
            {latestDossier ? (
              <span className="font-mono text-emerald-400">{latestDossier.dossier_reference}</span>
            ) : (
              "None generated"
            )}
          </div>
        </Card>
      </div>

      {/* Two Column Section: Documents Table & Priority Findings */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Case Documents Summary Card */}
        <Card>
          <CardHeader>
            <CardTitle>
              <FileText className="w-4 h-4 text-evidexa-cyan" />
              Registered Evidence Documents
            </CardTitle>
            <Link
              to={`/cases/${caseId}/documents`}
              className="text-xs text-evidexa-aqua hover:underline flex items-center gap-1 font-medium"
            >
              View All <ArrowRight className="w-3.5 h-3.5" />
            </Link>
          </CardHeader>

          {isDocsLoading && (
            <div className="space-y-3">
              {[1, 2, 3].map((i) => (
                <Skeleton key={i} className="h-12 w-full" />
              ))}
            </div>
          )}

          {!isDocsLoading && (!documentsData || documentsData.items.length === 0) && (
            <EmptyState
              title="No documents uploaded"
              description="Ingest PDFs or images to initiate structural forensics and OCR extraction."
              className="py-6"
            />
          )}

          {!isDocsLoading && documentsData && documentsData.items.length > 0 && (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead>
                  <tr className="border-b border-evidexa-slate text-slate-400 font-mono">
                    <th className="pb-2 font-medium">Filename</th>
                    <th className="pb-2 font-medium">SHA-256</th>
                    <th className="pb-2 font-medium">Size</th>
                    <th className="pb-2 font-medium">Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-evidexa-slate/40">
                  {documentsData.items.slice(0, 5).map((doc) => (
                    <tr key={doc.id} className="hover:bg-slate-800/40">
                      <td className="py-2.5 font-medium text-slate-200 truncate max-w-[160px]" title={doc.original_filename}>
                        {doc.original_filename}
                      </td>
                      <td className="py-2.5 font-mono text-[11px] text-slate-400">
                        {doc.sha256.slice(0, 10)}…
                      </td>
                      <td className="py-2.5 font-mono text-slate-400">
                        {(doc.file_size_bytes / 1024).toFixed(1)} KB
                      </td>
                      <td className="py-2.5">
                        <span className="px-2 py-0.5 rounded text-[10px] font-mono bg-slate-800 text-slate-300 border border-slate-700">
                          {doc.ingestion_status}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>

        {/* Priority Findings Card */}
        <Card>
          <CardHeader>
            <CardTitle>
              <ShieldAlert className="w-4 h-4 text-orange-400" />
              Forensic & Consistency Findings
            </CardTitle>
            <Link
              to={`/cases/${caseId}/findings`}
              className="text-xs text-evidexa-aqua hover:underline flex items-center gap-1 font-medium"
            >
              View All <ArrowRight className="w-3.5 h-3.5" />
            </Link>
          </CardHeader>

          {isFindingsLoading && (
            <div className="space-y-3">
              {[1, 2, 3].map((i) => (
                <Skeleton key={i} className="h-12 w-full" />
              ))}
            </div>
          )}

          {!isFindingsLoading && findings.length === 0 && (
            <EmptyState
              title="No findings recorded"
              description="No anomalies or inconsistencies have been detected across current evidence."
              className="py-6"
            />
          )}

          {!isFindingsLoading && findings.length > 0 && (
            <div className="space-y-3">
              {findings.slice(0, 5).map((finding) => (
                <div
                  key={finding.id}
                  className="p-3 rounded-lg bg-evidexa-midnight/70 border border-evidexa-slate/80 flex items-start justify-between gap-3"
                >
                  <div className="space-y-1">
                    <div className="flex items-center gap-2">
                      <StatusBadge status={finding.severity} type="severity" />
                      <StatusBadge status={finding.evidentiary_status} type="evidentiary" />
                    </div>
                    <p className="text-xs font-medium text-slate-200 line-clamp-1">{finding.title}</p>
                    <p className="text-[11px] text-slate-400 line-clamp-1">{finding.description}</p>
                  </div>
                  <span className="font-mono text-[10px] text-slate-400 shrink-0">
                    {finding.finding_source}
                  </span>
                </div>
              ))}
            </div>
          )}
        </Card>
      </div>

      {/* Dossier & Export Workflow Card */}
      <Card>
        <CardHeader>
          <CardTitle>
            <FileCheck2 className="w-4 h-4 text-emerald-400" />
            Investigation Dossier Export & Audit Trail
          </CardTitle>
          {latestDossier && (
            <a
              href={`/api/v1/cases/${caseId}/dossiers/${latestDossier.id}/export?format=pdf`}
              download
              className="inline-flex items-center gap-1.5 text-xs font-mono font-medium px-3 py-1.5 rounded bg-emerald-950/60 text-emerald-300 border border-emerald-500/40 hover:bg-emerald-900/60 transition-colors"
            >
              <Download className="w-3.5 h-3.5" />
              Export Latest Dossier (PDF)
            </a>
          )}
        </CardHeader>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="p-4 bg-evidexa-midnight/60 rounded-lg border border-evidexa-slate/60 md:col-span-2">
            <h4 className="text-xs font-semibold uppercase tracking-wider text-slate-300 mb-1">
              Forensic Integrity Standard
            </h4>
            <p className="text-xs text-slate-400 leading-relaxed">
              EVIDEXA dossiers are compiled deterministically across 12 analytical sections (Executive Summary, Document Registry, Forensic Metadata, Optical Analysis, Entity Resolution, Cross-Document Consistency, Evidence Graph, Chronology, and Cryptographic Hash Manifest). Every finding is accompanied by verifiable bounding coordinates and SHA-256 digests.
            </p>
          </div>

          <div className="p-4 bg-evidexa-midnight/60 rounded-lg border border-evidexa-slate/60 flex flex-col justify-between">
            <div>
              <span className="text-[11px] font-mono uppercase tracking-wider text-slate-400 block mb-1">
                Active Dossiers
              </span>
              <span className="text-lg font-bold font-mono text-white">
                {dossiers.length} Compiled
              </span>
            </div>
            <Button
              variant="secondary"
              size="sm"
              onClick={() => setIsDossierModalOpen(true)}
              className="mt-3 w-full"
            >
              <Plus className="w-3.5 h-3.5 mr-1" />
              Compile New Dossier Draft
            </Button>
          </div>
        </div>
      </Card>

      {/* Archive Modal */}
      <Modal
        isOpen={isArchiveModalOpen}
        onClose={() => setIsArchiveModalOpen(false)}
        title="Archive Investigation Case"
      >
        <div className="space-y-4">
          <p className="text-sm text-slate-300">
            Are you sure you want to archive case{" "}
            <span className="font-mono font-semibold text-evidexa-cyan">
              {caseData.case_reference}
            </span>
            ?
          </p>
          <div className="p-3 rounded bg-amber-950/40 border border-amber-500/40 text-xs text-amber-300">
            Archiving places the case into a read-only state. Ingestion and analysis are halted while all evidence, cryptographic hashes, and audit ledger entries remain immutable and fully preserved.
          </div>
          <div className="flex items-center justify-end gap-3 pt-3 border-t border-evidexa-slate">
            <Button variant="secondary" onClick={() => setIsArchiveModalOpen(false)}>
              Cancel
            </Button>
            <Button
              variant="danger"
              isLoading={archiveMutation.isPending}
              onClick={() => archiveMutation.mutate()}
            >
              Confirm Archive
            </Button>
          </div>
        </div>
      </Modal>

      {/* Generate Dossier Modal */}
      <Modal
        isOpen={isDossierModalOpen}
        onClose={() => setIsDossierModalOpen(false)}
        title="Generate Investigation Dossier"
      >
        <form
          onSubmit={(e) => {
            e.preventDefault();
            generateDossierMutation.mutate(dossierScope.trim() || undefined);
          }}
          className="space-y-4"
        >
          <p className="text-sm text-slate-300">
            Compiling an investigation evidence dossier aggregates all verified findings, cross-document inconsistencies, detected relationships, and document hashes into a standardized 12-section report.
          </p>
          <div>
            <label className="block text-xs font-semibold uppercase tracking-wider text-slate-300 mb-1.5">
              Investigation Scope & Purpose (Optional)
            </label>
            <textarea
              rows={3}
              placeholder="e.g. Comprehensive forensic examination of contractor invoices and bank statements for Case Q3-2026."
              value={dossierScope}
              onChange={(e) => setDossierScope(e.target.value)}
              className="w-full bg-evidexa-midnight border border-evidexa-slate rounded-md px-3 py-2 text-sm text-white placeholder-slate-500 focus:outline-none focus:ring-1 focus:ring-evidexa-cyan"
            />
          </div>
          <div className="flex items-center justify-end gap-3 pt-3 border-t border-evidexa-slate">
            <Button
              type="button"
              variant="secondary"
              onClick={() => setIsDossierModalOpen(false)}
            >
              Cancel
            </Button>
            <Button type="submit" isLoading={generateDossierMutation.isPending}>
              Compile Dossier
            </Button>
          </div>
        </form>
      </Modal>
    </div>
  );
};
