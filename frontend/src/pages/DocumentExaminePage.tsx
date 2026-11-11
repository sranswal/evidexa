import React, { useState, useMemo } from 'react';
import { useParams, Link } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  ChevronLeft,
  Download,
  Copy,
  Check,
  FileText,
  FileSpreadsheet,
  ShieldAlert,
  Info,
  Loader2,
  AlertTriangle,
  SidebarClose,
  SidebarOpen,
  Play,
} from 'lucide-react';
import { documentsApi } from '../api/documents';
import { casesApi } from '../api/cases';
import { PdfDocumentViewer, HeatmapArtifact } from '../components/viewer/PdfDocumentViewer';
import { OcrInspector } from '../components/viewer/OcrInspector';
import { StructuredExtractionInspector } from '../components/viewer/StructuredExtractionInspector';
import { FindingsInspector } from '../components/viewer/FindingsInspector';
import { PageThumbnailStrip } from '../components/viewer/PageThumbnailStrip';
import { NormalizedBoundingBox, RotationAngle } from '../utils/coordinates';
import type { TextToken, EvidenceNode } from '../types/api';

export const DocumentExaminePage: React.FC = () => {
  const { caseId, documentId } = useParams<{ caseId: string; documentId: string }>();
  const queryClient = useQueryClient();

  // State
  const [currentPage, setCurrentPage] = useState<number>(1);
  const [totalPages, setTotalPages] = useState<number>(1);
  const [scale, setScale] = useState<number>(1.0);
  const [rotation, setRotation] = useState<RotationAngle>(0);
  const [activeOverlays, setActiveOverlays] = useState<Set<'ocr' | 'findings' | 'heatmap'>>(
    new Set(['ocr', 'findings'])
  );

  const [selectedToken, setSelectedToken] = useState<TextToken | null>(null);
  const [selectedEvidence, setSelectedEvidence] = useState<EvidenceNode | null>(null);
  const [highlightedBox, setHighlightedBox] = useState<NormalizedBoundingBox | null>(null);
  const [activeTab, setActiveTab] = useState<'ocr' | 'extraction' | 'findings' | 'info'>('ocr');

  const [thumbnailsCollapsed, setThumbnailsCollapsed] = useState<boolean>(false);
  const [inspectorCollapsed, setInspectorCollapsed] = useState<boolean>(false);
  const [copiedHash, setCopiedHash] = useState<boolean>(false);
  const [selectedEngine, setSelectedEngine] = useState<string>("hybrid-ocr-pipeline");

  // Mutation to run OCR
  const runOcrMutation = useMutation({
    mutationFn: (analyzerId: string) => documentsApi.startOcr(caseId!, documentId!, analyzerId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['ocr', caseId, documentId] });
      queryClient.invalidateQueries({ queryKey: ['extraction', caseId, documentId] });
      queryClient.invalidateQueries({ queryKey: ['findings', caseId, documentId] });
      queryClient.invalidateQueries({ queryKey: ['evidence', caseId, documentId] });
      queryClient.invalidateQueries({ queryKey: ['runs', caseId, documentId] });
      queryClient.invalidateQueries({ queryKey: ['document', caseId, documentId] });
    },
  });

  // Queries
  const { data: document, isLoading: docLoading, error: docError } = useQuery({
    queryKey: ['document', caseId, documentId],
    queryFn: () => documentsApi.getDocument(caseId!, documentId!),
    enabled: Boolean(caseId && documentId),
  });

  const { data: currentCase } = useQuery({
    queryKey: ['case', caseId],
    queryFn: () => casesApi.getCase(caseId!),
    enabled: Boolean(caseId),
  });

  const { data: ocrData } = useQuery({
    queryKey: ['ocr', caseId, documentId],
    queryFn: () => documentsApi.getOcrText(caseId!, documentId!),
    enabled: Boolean(caseId && documentId),
    retry: false,
  });

  const { data: extractionData } = useQuery({
    queryKey: ['extraction', caseId, documentId],
    queryFn: () => documentsApi.getExtraction(caseId!, documentId!),
    enabled: Boolean(caseId && documentId),
    retry: false,
  });

  const { data: findingsResponse } = useQuery({
    queryKey: ['findings', caseId, documentId],
    queryFn: () => documentsApi.listDocumentFindings(caseId!, documentId!),
    enabled: Boolean(caseId && documentId),
  });

  const { data: evidenceResponse } = useQuery({
    queryKey: ['evidence', caseId, documentId],
    queryFn: () => documentsApi.listDocumentEvidence(caseId!, documentId!),
    enabled: Boolean(caseId && documentId),
  });

  const { data: runsResponse } = useQuery({
    queryKey: ['runs', caseId, documentId],
    queryFn: () => documentsApi.listDocumentRuns(caseId!, documentId!),
    enabled: Boolean(caseId && documentId),
  });

  const findings = findingsResponse?.items || [];
  const evidenceList = evidenceResponse?.items || [];
  const runs = runsResponse?.items || [];

  // Detect visual ELA artifacts from evidence nodes
  const heatmapArtifacts: HeatmapArtifact[] = useMemo(() => {
    if (!caseId || !documentId) return [];
    const artifacts: HeatmapArtifact[] = [];

    for (const ev of evidenceList) {
      if (ev.evidence_type === 'VISUAL_REGION' && ev.raw_value) {
        try {
          const payload = JSON.parse(ev.raw_value);
          if (payload.artifact_key && ev.page_number) {
            // artifact_key is case_id/document_id/run_id/filename
            const parts = payload.artifact_key.split('/');
            const filename = parts[parts.length - 1];
            const runId = parts[parts.length - 2] || ev.processing_run_id;
            const url = documentsApi.getArtifactUrl(caseId, documentId, runId, filename);
            artifacts.push({ pageNumber: ev.page_number, imageUrl: url });
          }
        } catch {
          // ignore parsing error
        }
      }
    }
    return artifacts;
  }, [evidenceList, caseId, documentId]);

  // Handle overlay toggle
  const handleToggleOverlay = (type: 'ocr' | 'findings' | 'heatmap') => {
    setActiveOverlays((prev) => {
      const next = new Set(prev);
      if (next.has(type)) {
        next.delete(type);
      } else {
        next.add(type);
      }
      return next;
    });
  };

  // Copy SHA-256
  const handleCopyHash = async () => {
    if (!document?.sha256) return;
    await navigator.clipboard.writeText(document.sha256);
    setCopiedHash(true);
    setTimeout(() => setCopiedHash(false), 2000);
  };

  if (docLoading) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[60vh] gap-3 text-slate-400">
        <Loader2 className="w-8 h-8 animate-spin text-brand-cyan" />
        <p className="text-sm font-mono">Loading document forensic workspace...</p>
      </div>
    );
  }

  if (docError || !document) {
    return (
      <div className="max-w-md mx-auto my-12 p-6 bg-brand-charcoal border border-red-500/30 rounded-lg text-center">
        <AlertTriangle className="w-8 h-8 text-red-400 mx-auto mb-2" />
        <h4 className="text-base font-semibold text-white mb-1">Document Not Found</h4>
        <p className="text-xs text-slate-400 mb-4 font-mono">
          Unable to locate document #{documentId} in case #{caseId}.
        </p>
        <Link
          to={`/cases/${caseId}/documents`}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-brand-blue hover:bg-brand-blue-hover text-white text-xs font-medium rounded transition-colors"
        >
          <ChevronLeft className="w-3.5 h-3.5" />
          <span>Back to Documents</span>
        </Link>
      </div>
    );
  }

  const documentDownloadUrl = documentsApi.getDocumentDownloadUrl(caseId!, document.id);

  return (
    <div className="flex flex-col h-[calc(100vh-4rem)] bg-brand-midnight text-white overflow-hidden">
      {/* Top Breadcrumb & Metadata Header */}
      <div className="flex flex-wrap items-center justify-between gap-3 px-4 py-2.5 bg-brand-charcoal border-b border-brand-slate text-xs shrink-0">
        {/* Left: Breadcrumbs & Title */}
        <div className="flex items-center gap-2">
          <Link
            to={`/cases/${caseId}/documents`}
            className="inline-flex items-center gap-1 text-brand-slate-light hover:text-brand-cyan transition-colors"
          >
            <ChevronLeft className="w-3.5 h-3.5" />
            <span>{currentCase?.case_reference || "Documents"}</span>
          </Link>

          <span className="text-brand-slate-light">/</span>

          <span className="font-semibold text-white max-w-xs truncate" title={document.original_filename}>
            {document.original_filename}
          </span>

          <span className="px-1.5 py-0.5 rounded text-[10px] font-mono bg-brand-midnight border border-brand-slate text-brand-slate-light">
            {document.file_extension.toUpperCase().replace('.', '')}
          </span>

          {Boolean(document.metadata?.duplicate_of_document_id) && (
            <span className="px-1.5 py-0.5 rounded text-[10px] font-medium bg-amber-500/15 border border-amber-500/30 text-amber-300">
              Duplicate
            </span>
          )}
        </div>

        {/* Right: Cryptographic Hash & Actions */}
        <div className="flex items-center gap-2">
          {/* SHA-256 Copy */}
          <button
            type="button"
            onClick={handleCopyHash}
            className="inline-flex items-center gap-1.5 px-2 py-1 rounded bg-brand-midnight hover:bg-brand-slate/50 border border-brand-slate text-slate-300 font-mono text-[11px] transition-colors"
            title={`SHA-256: ${document.sha256} (Click to copy)`}
          >
            <span>SHA-256: {document.sha256.slice(0, 12)}...</span>
            {copiedHash ? <Check className="w-3 h-3 text-emerald-400" /> : <Copy className="w-3 h-3" />}
          </button>

          {/* Run OCR Pipeline Controls */}
          <div className="flex items-center gap-1 bg-brand-midnight border border-brand-slate rounded p-0.5 text-xs">
            <select
              value={selectedEngine}
              onChange={(e) => setSelectedEngine(e.target.value)}
              className="bg-transparent text-slate-200 font-mono text-[11px] px-1 focus:outline-none cursor-pointer"
            >
              <option value="hybrid-ocr-pipeline" className="bg-evidexa-charcoal text-white">Hybrid OCR</option>
              <option value="ppocrv5-devanagari-engine" className="bg-evidexa-charcoal text-white">Devanagari (Hindi)</option>
            </select>
            <button
              type="button"
              onClick={() => runOcrMutation.mutate(selectedEngine)}
              disabled={runOcrMutation.isPending}
              className="inline-flex items-center gap-1 px-2.5 py-1 rounded bg-evidexa-cyan hover:bg-evidexa-aqua text-black font-semibold text-xs shadow-glow transition-all disabled:opacity-50"
              title="Run or re-run forensic OCR analysis on this document"
            >
              {runOcrMutation.isPending ? (
                <Loader2 className="w-3 h-3 animate-spin" />
              ) : (
                <Play className="w-3 h-3" />
              )}
              <span>{runOcrMutation.isPending ? "Analyzing..." : ocrData ? "Re-run OCR" : "Run OCR"}</span>
            </button>
          </div>

          {/* Download Evidence */}
          <a
            href={documentDownloadUrl}
            download={document.original_filename}
            className="inline-flex items-center gap-1 px-2.5 py-1 rounded bg-brand-blue hover:bg-brand-blue-hover text-white text-xs font-medium transition-colors"
          >
            <Download className="w-3.5 h-3.5" />
            <span>Download</span>
          </a>

          {/* Toggle Inspector Sidebar */}
          <button
            type="button"
            onClick={() => setInspectorCollapsed(!inspectorCollapsed)}
            className="p-1 rounded text-brand-slate-light hover:text-white hover:bg-brand-slate/40 transition-colors ml-1"
            title={inspectorCollapsed ? 'Open Inspector Panel' : 'Collapse Inspector Panel'}
          >
            {inspectorCollapsed ? <SidebarOpen className="w-4 h-4" /> : <SidebarClose className="w-4 h-4" />}
          </button>
        </div>
      </div>

      {/* Main 3-Region Workspace */}
      <div className="flex flex-1 overflow-hidden relative">
        {/* Left: Page Thumbnail Strip */}
        <PageThumbnailStrip
          totalPages={totalPages}
          currentPage={currentPage}
          onPageSelect={(p) => {
            setCurrentPage(p);
            setHighlightedBox(null);
          }}
          ocrPages={ocrData?.pages}
          findings={findings}
          collapsed={thumbnailsCollapsed}
          onToggleCollapse={() => setThumbnailsCollapsed(!thumbnailsCollapsed)}
        />

        {/* Center: Interactive PDF Canvas & Overlay Layer */}
        <div className="flex-1 flex flex-col min-w-0 bg-brand-midnight">
          <PdfDocumentViewer
            documentUrl={documentDownloadUrl}
            fileExtension={document.file_extension}
            currentPage={currentPage}
            onPageChange={(p) => {
              setCurrentPage(p);
              setHighlightedBox(null);
            }}
            onTotalPagesDetected={(total) => setTotalPages(total)}
            scale={scale}
            onScaleChange={(s) => setScale(s)}
            rotation={rotation}
            onRotationChange={(r) => setRotation(r)}
            activeOverlays={activeOverlays}
            onToggleOverlay={handleToggleOverlay}
            tokens={ocrData?.pages?.find((p) => p.page_number === currentPage)?.tokens || []}
            selectedTokenId={selectedToken?.id || selectedToken?.token_id}
            onSelectToken={(t) => {
              setSelectedToken(t);
              setActiveTab('ocr');
            }}
            evidenceList={evidenceList}
            selectedEvidenceId={selectedEvidence?.id}
            onSelectEvidence={(ev) => {
              setSelectedEvidence(ev);
              setActiveTab('findings');
            }}
            highlightedBox={highlightedBox}
            heatmapArtifacts={heatmapArtifacts}
          />
        </div>

        {/* Right: Inspector Sidebar */}
        {!inspectorCollapsed && (
          <div className="w-80 md:w-96 bg-brand-charcoal border-l border-brand-slate flex flex-col h-full shrink-0">
            {/* Inspector Tab Bar */}
            <div className="flex items-center border-b border-brand-slate bg-brand-midnight/40 p-1">
              <button
                type="button"
                data-testid="tab-ocr"
                onClick={() => setActiveTab('ocr')}
                className={`flex-1 flex items-center justify-center gap-1.5 py-1.5 text-xs font-medium rounded transition-colors ${
                  activeTab === 'ocr'
                    ? 'bg-brand-charcoal text-brand-cyan shadow-sm'
                    : 'text-brand-slate-light hover:text-white'
                }`}
              >
                <FileText className="w-3.5 h-3.5" />
                <span>OCR</span>
              </button>

              <button
                type="button"
                data-testid="tab-extraction"
                onClick={() => setActiveTab('extraction')}
                className={`flex-1 flex items-center justify-center gap-1.5 py-1.5 text-xs font-medium rounded transition-colors ${
                  activeTab === 'extraction'
                    ? 'bg-brand-charcoal text-brand-cyan shadow-sm'
                    : 'text-brand-slate-light hover:text-white'
                }`}
              >
                <FileSpreadsheet className="w-3.5 h-3.5" />
                <span>Extraction</span>
              </button>

              <button
                type="button"
                data-testid="tab-findings"
                onClick={() => setActiveTab('findings')}
                className={`flex-1 flex items-center justify-center gap-1.5 py-1.5 text-xs font-medium rounded transition-colors ${
                  activeTab === 'findings'
                    ? 'bg-brand-charcoal text-brand-cyan shadow-sm'
                    : 'text-brand-slate-light hover:text-white'
                }`}
              >
                <ShieldAlert className="w-3.5 h-3.5" />
                <span>Findings ({findings.length})</span>
              </button>

              <button
                type="button"
                data-testid="tab-info"
                onClick={() => setActiveTab('info')}
                className={`flex-1 flex items-center justify-center gap-1.5 py-1.5 text-xs font-medium rounded transition-colors ${
                  activeTab === 'info'
                    ? 'bg-brand-charcoal text-brand-cyan shadow-sm'
                    : 'text-brand-slate-light hover:text-white'
                }`}
              >
                <Info className="w-3.5 h-3.5" />
                <span>Runs</span>
              </button>
            </div>

            {/* Inspector Tab Panels */}
            <div className="flex-1 overflow-hidden">
              {activeTab === 'ocr' && (
                <OcrInspector
                  ocrData={ocrData}
                  currentPage={currentPage}
                  selectedTokenId={selectedToken?.id || selectedToken?.token_id}
                  onSelectToken={(t) => {
                    setSelectedToken(t);
                    if (t?.bounding_box) {
                      setHighlightedBox(t.bounding_box);
                    }
                  }}
                  onNavigateToPage={(p) => setCurrentPage(p)}
                  onRunOcr={(engine) => runOcrMutation.mutate(engine)}
                  isOcrRunning={runOcrMutation.isPending}
                />
              )}

              {activeTab === 'extraction' && (
                <StructuredExtractionInspector
                  extractionData={extractionData}
                  currentPage={currentPage}
                  onNavigateToPage={(p) => setCurrentPage(p)}
                  onHighlightBox={(box) => setHighlightedBox(box)}
                />
              )}

              {activeTab === 'findings' && (
                <FindingsInspector
                  findings={findings}
                  evidenceList={evidenceList}
                  currentPage={currentPage}
                  onNavigateToPage={(p) => setCurrentPage(p)}
                  onSelectEvidence={(ev) => setSelectedEvidence(ev)}
                  selectedEvidenceId={selectedEvidence?.id}
                  onHighlightBox={(box) => setHighlightedBox(box)}
                  onToggleHeatmap={() => handleToggleOverlay('heatmap')}
                  isHeatmapActive={activeOverlays.has('heatmap')}
                />
              )}

              {activeTab === 'info' && (
                <div className="p-4 space-y-4 overflow-y-auto h-full text-xs text-slate-300">
                  <div>
                    <h5 className="font-semibold text-white mb-2 uppercase text-[10px] tracking-wider text-brand-slate-light">
                      Document Metadata
                    </h5>
                    <div className="space-y-1.5 font-mono text-[11px] bg-brand-midnight/60 p-2.5 rounded border border-brand-slate/60">
                      <div>
                        <span className="text-brand-slate-light">ID: </span>
                        <span className="text-white">{document.id}</span>
                      </div>
                      <div>
                        <span className="text-brand-slate-light">Storage Key: </span>
                        <span className="text-white break-all">{document.storage_key}</span>
                      </div>
                      <div>
                        <span className="text-brand-slate-light">Size: </span>
                        <span className="text-white">
                          {(document.file_size_bytes / 1024).toFixed(1)} KB ({document.file_size_bytes} bytes)
                        </span>
                      </div>
                      <div>
                        <span className="text-brand-slate-light">Ingestion Status: </span>
                        <span className="text-emerald-400 font-semibold">{document.ingestion_status}</span>
                      </div>
                      <div>
                        <span className="text-brand-slate-light">Uploaded: </span>
                        <span className="text-slate-400">
                          {new Date(document.created_at).toLocaleString()}
                        </span>
                      </div>
                    </div>
                  </div>

                  <div>
                    <h5 className="font-semibold text-white mb-2 uppercase text-[10px] tracking-wider text-brand-slate-light">
                      Processing Runs ({runs.length})
                    </h5>
                    {runs.length === 0 ? (
                      <p className="text-slate-500 italic text-[11px]">No processing runs recorded.</p>
                    ) : (
                      <div className="space-y-2">
                        {runs.map((run) => (
                          <div
                            key={run.id}
                            className="p-2.5 rounded bg-brand-midnight/60 border border-brand-slate/60 space-y-1 text-[11px]"
                          >
                            <div className="flex items-center justify-between font-mono">
                              <span className="font-semibold text-white">{run.pipeline_name}</span>
                              <span
                                className={`px-1.5 py-0.5 rounded text-[10px] ${
                                  run.status === 'SUCCEEDED'
                                    ? 'bg-emerald-500/15 text-emerald-400 border border-emerald-500/30'
                                    : run.status === 'RUNNING'
                                    ? 'bg-blue-500/15 text-blue-400 border border-blue-500/30 animate-pulse'
                                    : 'bg-slate-500/15 text-slate-400'
                                }`}
                              >
                                {run.status}
                              </span>
                            </div>
                            <div className="text-[10px] text-brand-slate-light font-mono">
                              Run ID: #{run.id.slice(-8)}
                            </div>
                            {run.error_message && (
                              <p className="text-rose-400 text-[10px]">{run.error_message}</p>
                            )}
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
