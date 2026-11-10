import React, { useEffect, useRef, useState, useCallback } from 'react';
import {
  ChevronLeft,
  ChevronRight,
  ZoomIn,
  ZoomOut,
  RotateCw,
  Maximize2,
  FileText,
  ShieldAlert,
  Flame,
  AlertTriangle,
  Loader2,
  RefreshCw,
} from 'lucide-react';
import { configurePdfWorker, pdfjsLib } from '../../utils/pdfLoader';
import {
  NormalizedBoundingBox,
  RotationAngle,
  ViewportDimensions,
  normalizedToPixelBox,
  sanitizeNormalizedBox,
  formatBoxLabel,
} from '../../utils/coordinates';
import type { TextToken, EvidenceNode } from '../../types/api';

export interface HeatmapArtifact {
  pageNumber: number;
  imageUrl: string;
}

interface PdfDocumentViewerProps {
  documentUrl: string;
  fileExtension: string;
  currentPage: number;
  onPageChange: (page: number) => void;
  onTotalPagesDetected?: (total: number) => void;
  scale: number;
  onScaleChange: (scale: number) => void;
  rotation: RotationAngle;
  onRotationChange: (rot: RotationAngle) => void;
  activeOverlays: Set<'ocr' | 'findings' | 'heatmap'>;
  onToggleOverlay: (type: 'ocr' | 'findings' | 'heatmap') => void;
  tokens?: TextToken[];
  selectedTokenId?: string | null;
  onSelectToken?: (token: TextToken | null) => void;
  evidenceList?: EvidenceNode[];
  selectedEvidenceId?: string | null;
  onSelectEvidence?: (evidence: EvidenceNode | null) => void;
  highlightedBox?: NormalizedBoundingBox | null;
  heatmapArtifacts?: HeatmapArtifact[];
}

export const PdfDocumentViewer: React.FC<PdfDocumentViewerProps> = ({
  documentUrl,
  fileExtension,
  currentPage,
  onPageChange,
  onTotalPagesDetected,
  scale,
  onScaleChange,
  rotation,
  onRotationChange,
  activeOverlays,
  onToggleOverlay,
  tokens = [],
  selectedTokenId,
  onSelectToken,
  evidenceList = [],
  selectedEvidenceId,
  onSelectEvidence,
  highlightedBox,
  heatmapArtifacts = [],
}) => {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const containerRef = useRef<HTMLDivElement | null>(null);

  const [numPages, setNumPages] = useState<number>(1);
  const [loading, setLoading] = useState<boolean>(true);
  const [rendering, setRendering] = useState<boolean>(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [viewportDims, setViewportDims] = useState<ViewportDimensions>({ width: 0, height: 0 });
  const [hoveredInfo, setHoveredInfo] = useState<{
    text: string;
    subtext?: string;
    x: number;
    y: number;
  } | null>(null);

  const isPdf = fileExtension.toLowerCase() === '.pdf';
  const pdfDocRef = useRef<any>(null);
  const renderTaskRef = useRef<any>(null);

  // Initialize PDF worker
  useEffect(() => {
    configurePdfWorker();
  }, []);

  // Load PDF Document
  const loadPdf = useCallback(async () => {
    if (!isPdf) {
      setNumPages(1);
      if (onTotalPagesDetected) onTotalPagesDetected(1);
      setLoading(false);
      return;
    }

    setLoading(true);
    setLoadError(null);

    try {
      const loadingTask = pdfjsLib.getDocument({
        url: documentUrl,
        withCredentials: false,
      });

      const pdf = await loadingTask.promise;
      pdfDocRef.current = pdf;
      setNumPages(pdf.numPages);
      if (onTotalPagesDetected) {
        onTotalPagesDetected(pdf.numPages);
      }
      setLoading(false);
    } catch (err: any) {
      // Don't show error if aborted
      if (err?.name === 'RenderingCancelledException') return;
      setLoadError(err?.message || 'Failed to load PDF document');
      setLoading(false);
    }
  }, [documentUrl, isPdf, onTotalPagesDetected]);

  useEffect(() => {
    loadPdf();
    return () => {
      if (renderTaskRef.current) {
        renderTaskRef.current.cancel();
      }
      if (pdfDocRef.current) {
        pdfDocRef.current.destroy();
      }
    };
  }, [loadPdf]);

  // Render current PDF page on canvas
  const renderPdfPage = useCallback(async () => {
    if (!isPdf || !pdfDocRef.current || !canvasRef.current) return;

    if (renderTaskRef.current) {
      renderTaskRef.current.cancel();
    }

    setRendering(true);

    try {
      const page = await pdfDocRef.current.getPage(currentPage);
      const canvas = canvasRef.current;
      const ctx = canvas.getContext('2d');
      if (!ctx) return;

      const viewport = page.getViewport({ scale, rotation });

      canvas.width = viewport.width;
      canvas.height = viewport.height;
      setViewportDims({ width: viewport.width, height: viewport.height });

      const renderContext = {
        canvasContext: ctx,
        viewport,
      };

      const renderTask = page.render(renderContext);
      renderTaskRef.current = renderTask;
      await renderTask.promise;
      setRendering(false);
    } catch (err: any) {
      if (err?.name !== 'RenderingCancelledException') {
        console.error('PDF rendering failed:', err);
      }
      setRendering(false);
    }
  }, [isPdf, currentPage, scale, rotation]);

  useEffect(() => {
    if (!loading && !loadError && isPdf) {
      renderPdfPage();
    }
  }, [loading, loadError, isPdf, renderPdfPage]);

  // Handle image dimensions for non-PDF documents
  const handleImageLoad = (e: React.SyntheticEvent<HTMLImageElement>) => {
    const img = e.currentTarget;
    const width = img.naturalWidth * scale;
    const height = img.naturalHeight * scale;
    setViewportDims({ width, height });
    setLoading(false);
  };

  // Zoom handlers
  const handleZoomIn = () => {
    onScaleChange(Math.min(3.0, Number((scale + 0.25).toFixed(2))));
  };

  const handleZoomOut = () => {
    onScaleChange(Math.max(0.25, Number((scale - 0.25).toFixed(2))));
  };

  const handleResetZoom = () => {
    onScaleChange(1.0);
  };

  const handleFitWidth = () => {
    if (!containerRef.current || viewportDims.width === 0) return;
    const containerWidth = containerRef.current.clientWidth - 48; // padding
    const currentUnscaledWidth = viewportDims.width / scale;
    if (currentUnscaledWidth > 0) {
      const newScale = Number((containerWidth / currentUnscaledWidth).toFixed(2));
      onScaleChange(Math.max(0.25, Math.min(3.0, newScale)));
    }
  };

  const handleRotate = () => {
    const nextRot = (((rotation + 90) % 360) as RotationAngle);
    onRotationChange(nextRot);
  };

  // Filter current page tokens
  const pageTokens = tokens.filter((t) => {
    // If token has explicit bounding box
    return t.bounding_box && sanitizeNormalizedBox(t.bounding_box) !== null;
  });

  // Filter current page evidence
  const pageEvidence = evidenceList.filter((ev) => {
    if (ev.page_number && ev.page_number !== currentPage) return false;
    return ev.bounding_box && sanitizeNormalizedBox(ev.bounding_box) !== null;
  });

  // Check if active heatmap exists for this page
  const currentHeatmap = heatmapArtifacts.find((h) => h.pageNumber === currentPage);

  return (
    <div className="flex flex-col h-full bg-brand-midnight select-none" ref={containerRef}>
      {/* Top Viewer Control Bar */}
      <div className="flex flex-wrap items-center justify-between gap-3 px-4 py-2.5 bg-brand-charcoal border-b border-brand-slate text-sm">
        {/* Page Navigation */}
        <div className="flex items-center gap-1.5">
          <button
            type="button"
            aria-label="Previous Page"
            disabled={currentPage <= 1 || loading}
            onClick={() => onPageChange(Math.max(1, currentPage - 1))}
            className="p-1.5 rounded text-brand-slate-light hover:text-white hover:bg-brand-slate/50 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
          >
            <ChevronLeft className="w-4 h-4" />
          </button>

          <div className="flex items-center gap-1 text-xs font-mono text-slate-300">
            <span className="font-semibold text-brand-cyan">{currentPage}</span>
            <span className="text-brand-slate-light">/</span>
            <span>{numPages}</span>
          </div>

          <button
            type="button"
            aria-label="Next Page"
            disabled={currentPage >= numPages || loading}
            onClick={() => onPageChange(Math.min(numPages, currentPage + 1))}
            className="p-1.5 rounded text-brand-slate-light hover:text-white hover:bg-brand-slate/50 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
          >
            <ChevronRight className="w-4 h-4" />
          </button>
        </div>

        {/* Zoom & Rotation Controls */}
        <div className="flex items-center gap-1">
          <button
            type="button"
            aria-label="Zoom Out"
            onClick={handleZoomOut}
            className="p-1.5 rounded text-brand-slate-light hover:text-white hover:bg-brand-slate/50 transition-colors"
            title="Zoom Out (-25%)"
          >
            <ZoomOut className="w-4 h-4" />
          </button>

          <button
            type="button"
            onClick={handleResetZoom}
            className="px-2 py-1 text-xs font-mono font-medium rounded text-slate-300 hover:text-white hover:bg-brand-slate/50 transition-colors"
            title="Reset Zoom to 100%"
          >
            {Math.round(scale * 100)}%
          </button>

          <button
            type="button"
            aria-label="Zoom In"
            onClick={handleZoomIn}
            className="p-1.5 rounded text-brand-slate-light hover:text-white hover:bg-brand-slate/50 transition-colors"
            title="Zoom In (+25%)"
          >
            <ZoomIn className="w-4 h-4" />
          </button>

          <div className="h-4 w-px bg-brand-slate mx-1" />

          <button
            type="button"
            onClick={handleFitWidth}
            className="p-1.5 rounded text-brand-slate-light hover:text-white hover:bg-brand-slate/50 transition-colors"
            title="Fit to Width"
          >
            <Maximize2 className="w-4 h-4" />
          </button>

          <button
            type="button"
            onClick={handleRotate}
            className="p-1.5 rounded text-brand-slate-light hover:text-white hover:bg-brand-slate/50 transition-colors"
            title={`Rotate Clockwise 90° (Current: ${rotation}°)`}
          >
            <RotateCw className="w-4 h-4" />
          </button>
        </div>

        {/* Layer Visibility Toggles */}
        <div className="flex items-center gap-1.5">
          <button
            type="button"
            onClick={() => onToggleOverlay('ocr')}
            className={`inline-flex items-center gap-1 px-2.5 py-1 text-xs font-medium rounded border transition-colors ${
              activeOverlays.has('ocr')
                ? 'bg-brand-cyan/20 border-brand-cyan text-brand-cyan'
                : 'bg-brand-midnight/60 border-brand-slate text-brand-slate-light hover:text-slate-300'
            }`}
            title="Toggle OCR text bounding boxes"
          >
            <FileText className="w-3.5 h-3.5" />
            <span>OCR ({pageTokens.length})</span>
          </button>

          <button
            type="button"
            onClick={() => onToggleOverlay('findings')}
            className={`inline-flex items-center gap-1 px-2.5 py-1 text-xs font-medium rounded border transition-colors ${
              activeOverlays.has('findings')
                ? 'bg-amber-400/20 border-amber-400 text-amber-300'
                : 'bg-brand-midnight/60 border-brand-slate text-brand-slate-light hover:text-slate-300'
            }`}
            title="Toggle forensic findings and evidence regions"
          >
            <ShieldAlert className="w-3.5 h-3.5" />
            <span>Findings ({pageEvidence.length})</span>
          </button>

          {currentHeatmap && (
            <button
              type="button"
              onClick={() => onToggleOverlay('heatmap')}
              className={`inline-flex items-center gap-1 px-2.5 py-1 text-xs font-medium rounded border transition-colors ${
                activeOverlays.has('heatmap')
                  ? 'bg-rose-500/20 border-rose-500 text-rose-300'
                  : 'bg-brand-midnight/60 border-brand-slate text-brand-slate-light hover:text-slate-300'
              }`}
              title="Toggle ELA visual anomaly heatmap overlay"
            >
              <Flame className="w-3.5 h-3.5" />
              <span>Heatmap</span>
            </button>
          )}
        </div>
      </div>

      {/* Main Document Canvas Viewport */}
      <div className="flex-1 overflow-auto p-4 flex items-center justify-center relative">
        {loading && (
          <div className="flex flex-col items-center justify-center gap-3 text-slate-400">
            <Loader2 className="w-8 h-8 animate-spin text-brand-cyan" />
            <p className="text-sm font-mono">Loading original evidence document...</p>
          </div>
        )}

        {loadError && (
          <div className="flex flex-col items-center justify-center max-w-md p-6 bg-brand-charcoal border border-red-500/30 rounded-lg text-center">
            <AlertTriangle className="w-8 h-8 text-red-400 mb-2" />
            <h4 className="text-base font-semibold text-white mb-1">Failed to Render Document</h4>
            <p className="text-xs text-slate-400 mb-4 font-mono">{loadError}</p>
            <button
              type="button"
              onClick={loadPdf}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-brand-blue hover:bg-brand-blue-hover text-white text-xs font-medium rounded transition-colors"
            >
              <RefreshCw className="w-3.5 h-3.5" />
              <span>Retry Rendering</span>
            </button>
          </div>
        )}

        {/* Canvas & Overlay Container */}
        <div
          className={`relative shadow-2xl transition-opacity duration-200 ${
            loading || loadError ? 'hidden' : 'block'
          } ${rendering ? 'opacity-80' : 'opacity-100'}`}
          style={{
            width: viewportDims.width > 0 ? `${viewportDims.width}px` : 'auto',
            height: viewportDims.height > 0 ? `${viewportDims.height}px` : 'auto',
          }}
        >
          {/* PDF Canvas */}
          {isPdf ? (
            <canvas ref={canvasRef} className="block bg-white rounded-sm shadow-md" />
          ) : (
            <img
              src={documentUrl}
              alt="Evidence Document Page"
              onLoad={handleImageLoad}
              style={{
                width: viewportDims.width > 0 ? `${viewportDims.width}px` : 'auto',
                height: viewportDims.height > 0 ? `${viewportDims.height}px` : 'auto',
                transform: `rotate(${rotation}deg)`,
              }}
              className="block bg-white rounded-sm shadow-md object-contain"
            />
          )}

          {/* ELA Visual Heatmap Overlay (if enabled) */}
          {activeOverlays.has('heatmap') && currentHeatmap && (
            <img
              src={currentHeatmap.imageUrl}
              alt="ELA Heatmap Overlay"
              className="absolute inset-0 pointer-events-none mix-blend-screen opacity-65"
              style={{
                width: `${viewportDims.width}px`,
                height: `${viewportDims.height}px`,
              }}
            />
          )}

          {/* Coordinate Overlay Layer */}
          {viewportDims.width > 0 && viewportDims.height > 0 && (
            <div
              className="absolute inset-0 pointer-events-auto"
              style={{
                width: `${viewportDims.width}px`,
                height: `${viewportDims.height}px`,
              }}
            >
              {/* OCR Bounding Boxes */}
              {activeOverlays.has('ocr') &&
                pageTokens.map((token, idx) => {
                  const sanitized = sanitizeNormalizedBox(token.bounding_box);
                  if (!sanitized) return null;
                  const pixelBox = normalizedToPixelBox(sanitized, viewportDims, rotation);
                  const isSelected = selectedTokenId === (token.id || token.token_id);
                  const tokenText = token.raw_text || token.text || '';

                  return (
                    <div
                      key={`token-${token.id || idx}`}
                      onClick={(e) => {
                        e.stopPropagation();
                        if (onSelectToken) onSelectToken(token);
                      }}
                      onMouseEnter={(e) => {
                        const rect = e.currentTarget.getBoundingClientRect();
                        setHoveredInfo({
                          text: tokenText,
                          subtext: `OCR Token #${token.reading_order_index || idx + 1} | Conf: ${
                            token.confidence !== null && token.confidence !== undefined
                              ? `${Math.round(token.confidence * 100)}%`
                              : 'Heuristic'
                          }`,
                          x: rect.left,
                          y: rect.top - 8,
                        });
                      }}
                      onMouseLeave={() => setHoveredInfo(null)}
                      style={{
                        left: `${pixelBox.left}px`,
                        top: `${pixelBox.top}px`,
                        width: `${pixelBox.width}px`,
                        height: `${pixelBox.height}px`,
                      }}
                      className={`absolute cursor-pointer transition-all ${
                        isSelected
                          ? 'border-2 border-brand-cyan bg-brand-cyan/25 shadow-[0_0_10px_rgba(0,229,255,0.7)] z-30'
                          : 'border border-brand-cyan/40 bg-brand-cyan/5 hover:border-brand-cyan hover:bg-brand-cyan/20 z-10'
                      }`}
                    />
                  );
                })}

              {/* Forensic Findings & Evidence Bounding Boxes */}
              {activeOverlays.has('findings') &&
                pageEvidence.map((ev, idx) => {
                  const sanitized = sanitizeNormalizedBox(ev.bounding_box);
                  if (!sanitized) return null;
                  const pixelBox = normalizedToPixelBox(sanitized, viewportDims, rotation);
                  const isSelected = selectedEvidenceId === ev.id;

                  return (
                    <div
                      key={`ev-${ev.id || idx}`}
                      onClick={(e) => {
                        e.stopPropagation();
                        if (onSelectEvidence) onSelectEvidence(ev);
                      }}
                      onMouseEnter={(e) => {
                        const rect = e.currentTarget.getBoundingClientRect();
                        setHoveredInfo({
                          text: ev.title || 'Evidence Observation',
                          subtext: `Source: ${ev.source_component} | ${formatBoxLabel(sanitized)}`,
                          x: rect.left,
                          y: rect.top - 8,
                        });
                      }}
                      onMouseLeave={() => setHoveredInfo(null)}
                      style={{
                        left: `${pixelBox.left}px`,
                        top: `${pixelBox.top}px`,
                        width: `${pixelBox.width}px`,
                        height: `${pixelBox.height}px`,
                      }}
                      className={`absolute cursor-pointer transition-all ${
                        isSelected
                          ? 'border-2 border-red-500 bg-red-500/30 shadow-[0_0_12px_rgba(239,68,68,0.8)] z-30 animate-pulse'
                          : 'border-2 border-amber-400/80 bg-amber-400/15 hover:border-amber-300 hover:bg-amber-400/30 z-20'
                      }`}
                    />
                  );
                })}

              {/* Active Highlighted Box (e.g. from Structured Extraction) */}
              {highlightedBox &&
                (() => {
                  const sanitized = sanitizeNormalizedBox(highlightedBox);
                  if (!sanitized) return null;
                  const pixelBox = normalizedToPixelBox(sanitized, viewportDims, rotation);

                  return (
                    <div
                      style={{
                        left: `${pixelBox.left}px`,
                        top: `${pixelBox.top}px`,
                        width: `${pixelBox.width}px`,
                        height: `${pixelBox.height}px`,
                      }}
                      className="absolute border-2 border-emerald-400 bg-emerald-400/25 shadow-[0_0_14px_rgba(52,211,153,0.8)] z-40 pointer-events-none animate-pulse"
                    />
                  );
                })()}
            </div>
          )}
        </div>

        {/* Global Floating Tooltip */}
        {hoveredInfo && (
          <div
            style={{
              position: 'fixed',
              left: `${hoveredInfo.x}px`,
              top: `${hoveredInfo.y}px`,
              transform: 'translateY(-100%)',
            }}
            className="z-50 pointer-events-none px-2.5 py-1.5 bg-brand-charcoal/95 border border-brand-slate rounded shadow-xl text-xs max-w-xs backdrop-blur-sm"
          >
            <div className="font-medium text-white truncate">{hoveredInfo.text}</div>
            {hoveredInfo.subtext && (
              <div className="text-[10px] text-brand-slate-light font-mono truncate">
                {hoveredInfo.subtext}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};

