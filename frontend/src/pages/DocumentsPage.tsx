import React, { useState } from "react";
import { useParams } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  FileText,
  UploadCloud,
  Search,
  HardDrive,
  CopyCheck,
  CheckCircle2,
  AlertTriangle,
  ChevronLeft,
  ChevronRight,
} from "lucide-react";
import { Card } from "../components/ui/Card";
import { Button } from "../components/ui/Button";
import { Skeleton } from "../components/ui/Skeleton";
import { ErrorMessage } from "../components/ui/ErrorMessage";
import { EmptyState } from "../components/ui/EmptyState";
import { DocumentTable } from "../components/documents/DocumentTable";
import { DocumentUploadModal } from "../components/documents/DocumentUploadModal";
import { DocumentDetailDrawer } from "../components/documents/DocumentDetailDrawer";
import { documentsApi } from "../api/documents";
import { useCaseContext } from "../context/CaseContext";
import type { DocumentItem, IngestionStatus } from "../types/api";

export const DocumentsPage: React.FC = () => {
  const { caseId } = useParams<{ caseId: string }>();
  const queryClient = useQueryClient();
  const { activeCase } = useCaseContext();

  const [searchQuery, setSearchQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState<IngestionStatus | "ALL">("ALL");
  const [formatFilter, setFormatFilter] = useState<string>("ALL");
  const [sortBy, setSortBy] = useState<"date_desc" | "date_asc" | "size_desc" | "name_asc">("date_desc");
  const [currentPage, setCurrentPage] = useState(1);
  const pageSize = 50;

  // Modals & Drawers
  const [isUploadModalOpen, setIsUploadModalOpen] = useState(false);
  const [selectedDocument, setSelectedDocument] = useState<DocumentItem | null>(null);
  const [isDrawerOpen, setIsDrawerOpen] = useState(false);

  if (!caseId) {
    return <ErrorMessage message="No case ID provided in route." />;
  }

  const isCaseArchived = activeCase?.status === "ARCHIVED";

  // Fetch Documents
  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ["case-documents", caseId, currentPage],
    queryFn: () => documentsApi.listDocuments(caseId, (currentPage - 1) * pageSize, pageSize),
  });

  const documents = data?.items || [];
  const totalDocuments = data?.total ?? 0;

  // Filter & Search
  const filteredDocuments = documents.filter((doc) => {
    const matchesSearch =
      doc.original_filename.toLowerCase().includes(searchQuery.toLowerCase()) ||
      doc.id.toLowerCase().includes(searchQuery.toLowerCase()) ||
      doc.sha256.toLowerCase().includes(searchQuery.toLowerCase());

    const matchesStatus =
      statusFilter === "ALL" || doc.ingestion_status === statusFilter;

    const matchesFormat =
      formatFilter === "ALL" ||
      doc.file_extension.toLowerCase().replace(".", "") === formatFilter.toLowerCase();

    return matchesSearch && matchesStatus && matchesFormat;
  });

  // Sorting
  const sortedDocuments = [...filteredDocuments].sort((a, b) => {
    switch (sortBy) {
      case "date_asc":
        return new Date(a.created_at).getTime() - new Date(b.created_at).getTime();
      case "size_desc":
        return b.file_size_bytes - a.file_size_bytes;
      case "name_asc":
        return a.original_filename.localeCompare(b.original_filename);
      case "date_desc":
      default:
        return new Date(b.created_at).getTime() - new Date(a.created_at).getTime();
    }
  });

  // Overall Statistics
  const totalBytes = documents.reduce((acc, doc) => acc + doc.file_size_bytes, 0);
  const duplicateCount = documents.filter((d) => d.metadata?.duplicate_of_document_id).length;
  const parsedCount = documents.filter((d) => d.ingestion_status === "PARSED").length;

  const handleDocumentSelect = (doc: DocumentItem) => {
    setSelectedDocument(doc);
    setIsDrawerOpen(true);
  };

  const handleUploadSuccess = (doc: DocumentItem) => {
    queryClient.invalidateQueries({ queryKey: ["case-documents", caseId] });
    queryClient.invalidateQueries({ queryKey: ["case", caseId] });
    setSelectedDocument(doc);
    setIsDrawerOpen(true);
  };

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-2 border-b border-evidexa-slate/60">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-white font-sans flex items-center gap-2.5">
            <FileText className="w-7 h-7 text-evidexa-cyan" />
            Case Evidence Documents
          </h1>
          <p className="text-sm text-slate-400 mt-1">
            Centrally inspect original evidence files, verify SHA-256 hashes, and execute forensic & OCR pipelines.
          </p>
        </div>

        <Button
          onClick={() => setIsUploadModalOpen(true)}
          disabled={isCaseArchived}
          className="self-start sm:self-auto"
        >
          <UploadCloud className="w-4 h-4 mr-1.5" />
          Ingest Document
        </Button>
      </div>

      {/* Case Archival Banner */}
      {isCaseArchived && (
        <div className="p-3.5 rounded-lg bg-amber-950/40 border border-amber-500/50 text-xs text-amber-300 flex items-center gap-2.5">
          <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0" />
          <span>Case is sealed and ARCHIVED. Existing evidence is preserved; new uploads and analysis are restricted.</span>
        </div>
      )}

      {/* Summary KPI Strip */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-xs">
        <Card className="p-3.5 flex items-center justify-between">
          <div>
            <span className="text-[10px] font-mono uppercase tracking-wider text-slate-400 block">Total Files</span>
            <span className="text-xl font-bold font-mono text-white">{totalDocuments}</span>
          </div>
          <FileText className="w-5 h-5 text-evidexa-cyan opacity-80" />
        </Card>

        <Card className="p-3.5 flex items-center justify-between">
          <div>
            <span className="text-[10px] font-mono uppercase tracking-wider text-slate-400 block">Storage Volume</span>
            <span className="text-xl font-bold font-mono text-white">
              {(totalBytes / (1024 * 1024)).toFixed(1)} MB
            </span>
          </div>
          <HardDrive className="w-5 h-5 text-purple-400 opacity-80" />
        </Card>

        <Card className="p-3.5 flex items-center justify-between">
          <div>
            <span className="text-[10px] font-mono uppercase tracking-wider text-slate-400 block">Parsed & Indexed</span>
            <span className="text-xl font-bold font-mono text-emerald-400">{parsedCount}</span>
          </div>
          <CheckCircle2 className="w-5 h-5 text-emerald-400 opacity-80" />
        </Card>

        <Card className="p-3.5 flex items-center justify-between">
          <div>
            <span className="text-[10px] font-mono uppercase tracking-wider text-slate-400 block">Identical Duplicates</span>
            <span className="text-xl font-bold font-mono text-amber-400">{duplicateCount}</span>
          </div>
          <CopyCheck className="w-5 h-5 text-amber-400 opacity-80" />
        </Card>
      </div>

      {/* Filter and Search Bar */}
      <div className="flex flex-col lg:flex-row gap-3 items-stretch lg:items-center justify-between">
        {/* Search */}
        <div className="relative flex-1 max-w-md">
          <Search className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            placeholder="Search by filename, document ID, or SHA-256..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full bg-evidexa-charcoal border border-evidexa-slate rounded-lg pl-9 pr-4 py-2 text-sm text-white placeholder-slate-400 focus:outline-none focus:ring-1 focus:ring-evidexa-cyan focus:border-evidexa-cyan font-sans"
          />
        </div>

        {/* Filters */}
        <div className="flex flex-wrap items-center gap-2">
          {/* Format Selector */}
          <div className="flex items-center gap-1 bg-evidexa-midnight/60 p-1 rounded-lg border border-evidexa-slate/80 text-xs font-mono">
            {["ALL", "PDF", "PNG", "JPEG", "TIFF"].map((fmt) => (
              <button
                key={fmt}
                onClick={() => setFormatFilter(fmt)}
                className={`px-2.5 py-1 rounded transition-colors ${
                  formatFilter === fmt
                    ? "bg-evidexa-slate text-evidexa-cyan font-semibold shadow"
                    : "text-slate-400 hover:text-slate-200"
                }`}
              >
                {fmt}
              </button>
            ))}
          </div>

          {/* Sort By Dropdown */}
          <select
            value={sortBy}
            onChange={(e) => setSortBy(e.target.value as any)}
            className="bg-evidexa-charcoal border border-evidexa-slate rounded-lg px-3 py-1.5 text-xs text-slate-200 focus:outline-none focus:ring-1 focus:ring-evidexa-cyan font-mono"
          >
            <option value="date_desc">Newest First</option>
            <option value="date_asc">Oldest First</option>
            <option value="size_desc">Largest Size</option>
            <option value="name_asc">Filename (A-Z)</option>
          </select>
        </div>
      </div>

      {/* Loading Skeleton */}
      {isLoading && (
        <Card className="space-y-3 p-5">
          {[1, 2, 3, 4, 5].map((i) => (
            <Skeleton key={i} className="h-12 w-full" />
          ))}
        </Card>
      )}

      {/* Error Message */}
      {isError && (
        <ErrorMessage
          title="Could not load document registry"
          message={error instanceof Error ? error.message : "Backend communication error."}
          onRetry={() => refetch()}
        />
      )}

      {/* Empty State */}
      {!isLoading && !isError && totalDocuments === 0 && (
        <EmptyState
          title="No evidence documents registered"
          description="This case workspace currently contains no uploaded files. Ingest original PDFs, scans, or images to begin forensic examination."
          action={
            <Button
              onClick={() => setIsUploadModalOpen(true)}
              disabled={isCaseArchived}
            >
              <UploadCloud className="w-4 h-4 mr-1.5" />
              Ingest First Document
            </Button>
          }
        />
      )}

      {/* Filtered Empty State */}
      {!isLoading && !isError && totalDocuments > 0 && sortedDocuments.length === 0 && (
        <EmptyState
          title="No matching documents found"
          description={`No files match your current search "${searchQuery}" and format filter "${formatFilter}".`}
          action={
            <Button
              variant="secondary"
              onClick={() => {
                setSearchQuery("");
                setFormatFilter("ALL");
                setStatusFilter("ALL");
              }}
            >
              Clear Filters
            </Button>
          }
        />
      )}

      {/* Document Inventory Table */}
      {!isLoading && !isError && sortedDocuments.length > 0 && (
        <>
          <DocumentTable
            caseId={caseId}
            documents={sortedDocuments}
            onSelectDocument={handleDocumentSelect}
          />

          {/* Pagination Controls */}
          {totalDocuments > pageSize && (
            <div className="flex items-center justify-between text-xs font-mono text-slate-400 pt-2">
              <span>
                Showing {(currentPage - 1) * pageSize + 1}–
                {Math.min(currentPage * pageSize, totalDocuments)} of {totalDocuments} files
              </span>
              <div className="flex items-center gap-2">
                <Button
                  variant="secondary"
                  size="sm"
                  disabled={currentPage === 1}
                  onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
                >
                  <ChevronLeft className="w-3.5 h-3.5 mr-1" />
                  Previous
                </Button>
                <span>
                  Page {currentPage} of {Math.ceil(totalDocuments / pageSize)}
                </span>
                <Button
                  variant="secondary"
                  size="sm"
                  disabled={currentPage >= Math.ceil(totalDocuments / pageSize)}
                  onClick={() => setCurrentPage((p) => p + 1)}
                >
                  Next
                  <ChevronRight className="w-3.5 h-3.5 ml-1" />
                </Button>
              </div>
            </div>
          )}
        </>
      )}

      {/* Upload Modal */}
      <DocumentUploadModal
        isOpen={isUploadModalOpen}
        onClose={() => setIsUploadModalOpen(false)}
        caseId={caseId}
        onUploadSuccess={handleUploadSuccess}
      />

      {/* Document Detail Drawer */}
      <DocumentDetailDrawer
        isOpen={isDrawerOpen}
        onClose={() => setIsDrawerOpen(false)}
        caseId={caseId}
        document={selectedDocument}
        isCaseArchived={isCaseArchived}
        onRefreshDocumentList={() => {
          queryClient.invalidateQueries({ queryKey: ["case-documents", caseId] });
        }}
      />
    </div>
  );
};
