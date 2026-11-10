import React, { useState, useMemo } from 'react';
import {
  Search,
  Copy,
  Check,
  FileText,
  Cpu,
  Layers,
  Sparkles,
  Info,
  AlertTriangle,
  Languages,
  Eye,
  EyeOff,
  GitCompare,
} from 'lucide-react';
import type { ExtractedDocumentText, TextToken, ObservationDisagreement } from '../../types/api';
import { formatBoxLabel } from '../../utils/coordinates';

interface OcrInspectorProps {
  ocrData?: ExtractedDocumentText | null;
  currentPage: number;
  selectedTokenId?: string | null;
  onSelectToken: (token: TextToken | null) => void;
  onNavigateToPage?: (page: number) => void;
}

export const OcrInspector: React.FC<OcrInspectorProps> = ({
  ocrData,
  currentPage,
  selectedTokenId,
  onSelectToken,
  onNavigateToPage,
}) => {
  const [searchQuery, setSearchQuery] = useState('');
  const [viewMode, setViewMode] = useState<'tokens' | 'lines' | 'raw'>('lines');
  const [scopeAllPages, setScopeAllPages] = useState(false);
  const [copied, setCopied] = useState(false);
  const [activeLayer, setActiveLayer] = useState<'primary' | 'pdfium'>('primary');
  const [showNormalized, setShowNormalized] = useState(true);
  const [selectedScript, setSelectedScript] = useState<string>('ALL');
  const [inspectedToken, setInspectedToken] = useState<TextToken | null>(null);

  // Current page text extraction
  const currentPageData = useMemo(() => {
    if (!ocrData?.pages) return null;
    return ocrData.pages.find((p) => p.page_number === currentPage) || null;
  }, [ocrData, currentPage]);

  // Aggregate pages according to scope
  const targetPages = useMemo(() => {
    if (!ocrData?.pages) return [];
    if (scopeAllPages) return ocrData.pages;
    return currentPageData ? [currentPageData] : [];
  }, [ocrData, scopeAllPages, currentPageData]);

  // Check alternative layer existence
  const altPdfium = currentPageData?.alternative_extractions?.pdfium;
  const hasAlternativePdfium = Boolean(altPdfium);

  // Disagreements
  const disagreements = useMemo(() => {
    return currentPageData?.disagreements || [];
  }, [currentPageData]);

  const activeDisagreements = useMemo(() => {
    return disagreements.filter((d: ObservationDisagreement) => d.has_disagreement);
  }, [disagreements]);

  // Potential duplicates in alternative layer metadata
  const potentialDuplicates = useMemo(() => {
    if (altPdfium?.metadata && Array.isArray(altPdfium.metadata.potential_duplicate_tokens)) {
      return altPdfium.metadata.potential_duplicate_tokens;
    }
    return [];
  }, [altPdfium]);

  // Flatten tokens from target pages based on active layer
  const allTokens = useMemo(() => {
    const list: Array<TextToken & { pageNumber: number }> = [];
    for (const page of targetPages) {
      let pageTokens = page.tokens || [];
      if (activeLayer === 'pdfium' && page.alternative_extractions?.pdfium?.tokens) {
        pageTokens = page.alternative_extractions.pdfium.tokens;
      }
      for (const t of pageTokens) {
        list.push({ ...t, pageNumber: page.page_number });
      }
    }
    return list;
  }, [targetPages, activeLayer]);

  // Filter tokens based on search query and script filter
  const filteredTokens = useMemo(() => {
    return allTokens.filter((t) => {
      // Script filtering
      if (selectedScript !== 'ALL') {
        const tokenScript = (t.detected_script || 'UNKNOWN').toUpperCase();
        if (tokenScript !== selectedScript) {
          return false;
        }
      }

      // Search query filtering
      if (!searchQuery.trim()) return true;
      const q = searchQuery.toLowerCase();
      return (
        (t.raw_text && t.raw_text.toLowerCase().includes(q)) ||
        (t.text && t.text.toLowerCase().includes(q)) ||
        (t.normalized_text && t.normalized_text.toLowerCase().includes(q))
      );
    });
  }, [allTokens, searchQuery, selectedScript]);

  // Flatten lines based on active layer
  const allLines = useMemo(() => {
    const linesList: Array<{
      id: string;
      pageNumber: number;
      rawText: string;
      normalizedText?: string | null;
      confidence?: number | null;
      tokens: TextToken[];
      readingOrder?: number;
      dominantScript?: string | null;
    }> = [];

    for (const page of targetPages) {
      if (activeLayer === 'pdfium' && page.alternative_extractions?.pdfium) {
        const alt = page.alternative_extractions.pdfium;
        if (alt.lines && alt.lines.length > 0) {
          for (const line of alt.lines) {
            linesList.push({
              id: line.id,
              pageNumber: page.page_number,
              rawText: line.raw_text,
              normalizedText: line.normalized_text,
              confidence: line.confidence,
              tokens: line.tokens,
              readingOrder: line.reading_order_index,
              dominantScript: line.dominant_script,
            });
          }
        } else {
          linesList.push({
            id: `page-${page.page_number}-pdfium`,
            pageNumber: page.page_number,
            rawText: alt.raw_text,
            normalizedText: alt.normalized_text,
            confidence: alt.confidence,
            tokens: alt.tokens || [],
            readingOrder: 0,
            dominantScript: 'LATIN',
          });
        }
        continue;
      }

      const pageLines = page.lines || [];
      if (pageLines.length > 0) {
        for (const line of pageLines) {
          linesList.push({
            id: line.id,
            pageNumber: page.page_number,
            rawText: line.raw_text,
            normalizedText: line.normalized_text,
            confidence: line.confidence,
            tokens: line.tokens,
            readingOrder: line.reading_order_index,
            dominantScript: line.dominant_script,
          });
        }
      } else {
        linesList.push({
          id: `page-${page.page_number}-${activeLayer}`,
          pageNumber: page.page_number,
          rawText: page.raw_text,
          normalizedText: page.normalized_text,
          confidence: null,
          tokens: page.tokens || [],
          readingOrder: 0,
        });
      }
    }

    if (!searchQuery.trim()) return linesList;
    const q = searchQuery.toLowerCase();
    return linesList.filter(
      (l) =>
        l.rawText.toLowerCase().includes(q) ||
        (l.normalizedText && l.normalizedText.toLowerCase().includes(q))
    );
  }, [targetPages, searchQuery, activeLayer]);

  // Handle text copy
  const handleCopyText = async () => {
    let textToCopy = '';
    if (scopeAllPages) {
      textToCopy = showNormalized
        ? ocrData?.full_normalized_text || ocrData?.full_raw_text || ''
        : ocrData?.full_raw_text || '';
    } else if (activeLayer === 'pdfium' && altPdfium) {
      textToCopy = showNormalized
        ? altPdfium.normalized_text || altPdfium.raw_text
        : altPdfium.raw_text;
    } else {
      textToCopy = showNormalized
        ? currentPageData?.normalized_text || currentPageData?.raw_text || ''
        : currentPageData?.raw_text || '';
    }
    if (!textToCopy) return;

    await navigator.clipboard.writeText(textToCopy);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleTokenClick = (tok: TextToken, pageNum: number) => {
    if (onNavigateToPage && pageNum !== currentPage) {
      onNavigateToPage(pageNum);
    }
    setInspectedToken(tok);
    onSelectToken(tok);
  };

  if (!ocrData) {
    return (
      <div className="p-6 text-center text-slate-400">
        <FileText className="w-10 h-10 mx-auto mb-3 text-brand-slate-light opacity-50" />
        <h4 className="text-sm font-semibold text-white mb-1">No OCR Data Available</h4>
        <p className="text-xs text-slate-400 max-w-xs mx-auto">
          OCR has not been executed on this document yet. Run the OCR pipeline from Processing Controls to inspect extracted text.
        </p>
      </div>
    );
  }

  const engineName =
    activeLayer === 'pdfium' && altPdfium
      ? altPdfium.engine_name
      : currentPageData?.engine_name || 'hybrid-ocr-pipeline';

  const hasVectorText =
    activeLayer === 'pdfium' ? true : currentPageData?.has_vector_text ?? true;

  const routingDecision = currentPageData?.routing_decision || 'VECTOR_ONLY';

  // Routing badge helper
  const getRoutingBadgeClass = (decision: string) => {
    switch (decision.toUpperCase()) {
      case 'VECTOR_ONLY':
        return 'bg-sky-500/15 text-sky-400 border border-sky-500/30';
      case 'OCR_ONLY':
        return 'bg-purple-500/15 text-purple-300 border border-purple-500/30';
      case 'HYBRID_FUSION':
        return 'bg-emerald-500/15 text-emerald-400 border border-emerald-500/30';
      case 'NO_TEXT':
        return 'bg-slate-500/15 text-slate-400 border border-slate-500/30';
      default:
        return 'bg-brand-slate text-slate-300 border border-brand-slate';
    }
  };

  return (
    <div className="flex flex-col h-full bg-brand-charcoal text-slate-200">
      {/* Engine, Routing & Provenance Banner */}
      <div className="p-3 border-b border-brand-slate bg-brand-midnight/40 space-y-2">
        <div className="flex items-center justify-between text-xs">
          <div className="flex items-center gap-1.5">
            <Cpu className="w-3.5 h-3.5 text-brand-cyan" />
            <span className="font-mono text-slate-300 font-medium truncate max-w-[170px]" title={engineName}>
              {engineName}
            </span>
          </div>

          <div className="flex items-center gap-1.5">
            {/* Page Routing Indicator */}
            <span
              className={`inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-mono font-medium ${getRoutingBadgeClass(
                routingDecision
              )}`}
              title={currentPageData?.routing_reason || undefined}
            >
              {routingDecision}
            </span>

            {/* Vector vs OCR Indicator */}
            <span
              className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-medium ${
                hasVectorText
                  ? 'bg-emerald-500/15 text-emerald-400 border border-emerald-500/30'
                  : 'bg-amber-500/15 text-amber-300 border border-amber-500/30'
              }`}
            >
              <Sparkles className="w-2.5 h-2.5" />
              <span>{hasVectorText ? 'Vector Digital Text' : 'Optical Character Recognition'}</span>
            </span>
          </div>
        </div>

        {/* Script Distribution & Routing Metrics */}
        <div className="flex flex-wrap items-center justify-between gap-1.5 text-[11px] text-brand-slate-light">
          <div className="flex items-center gap-2">
            <span>
              Total Tokens: <span className="font-mono text-white">{ocrData.total_tokens}</span>
            </span>
            <span>
              Total Pages: <span className="font-mono text-white">{ocrData.total_pages}</span>
            </span>
          </div>

          {/* Script distribution tags */}
          {currentPageData?.script_distribution && Object.keys(currentPageData.script_distribution).length > 0 && (
            <div className="flex items-center gap-1">
              <Languages className="w-3 h-3 text-brand-cyan" />
              {Object.entries(currentPageData.script_distribution).map(([s, ratio]) => (
                <span
                  key={s}
                  className="px-1.5 py-0.2 rounded text-[10px] font-mono bg-brand-charcoal text-slate-300 border border-brand-slate/60"
                >
                  {s}: {Math.round(ratio * 100)}%
                </span>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Extraction Layer Comparison Bar (Primary vs PDFium Vector) */}
      {hasAlternativePdfium && (
        <div className="px-3 py-2 border-b border-brand-slate bg-brand-midnight/70 flex items-center justify-between gap-2 text-xs">
          <div className="flex items-center gap-1.5">
            <GitCompare className="w-3.5 h-3.5 text-brand-cyan" />
            <span className="text-[11px] font-medium text-slate-300">Extraction Layer:</span>
            <div className="inline-flex rounded bg-brand-charcoal p-0.5 border border-brand-slate text-[11px]">
              <button
                type="button"
                onClick={() => setActiveLayer('primary')}
                className={`px-2 py-0.5 rounded transition-colors ${
                  activeLayer === 'primary'
                    ? 'bg-brand-midnight text-brand-cyan font-medium'
                    : 'text-brand-slate-light hover:text-white'
                }`}
              >
                Primary ({currentPageData?.engine_name || 'Optical'})
              </button>
              <button
                type="button"
                onClick={() => setActiveLayer('pdfium')}
                className={`px-2 py-0.5 rounded transition-colors ${
                  activeLayer === 'pdfium'
                    ? 'bg-brand-midnight text-brand-cyan font-medium'
                    : 'text-brand-slate-light hover:text-white'
                }`}
              >
                Alternative Vector (PDFium)
              </button>
            </div>
          </div>

          {potentialDuplicates.length > 0 && (
            <span
              className="text-[10px] text-brand-slate-light font-mono px-1.5 py-0.5 rounded bg-brand-charcoal border border-brand-slate/60"
              title="Spatial overlap between optical and vector layers"
            >
              {potentialDuplicates.length} duplicates tracked
            </span>
          )}
        </div>
      )}

      {/* Disagreement Warning Banner */}
      {activeDisagreements.length > 0 && (
        <div className="p-2.5 mx-3 mt-2 rounded bg-amber-500/10 border border-amber-500/30 text-xs text-amber-300 space-y-1">
          <div className="flex items-center gap-1.5 font-medium">
            <AlertTriangle className="w-3.5 h-3.5 text-amber-400 shrink-0" />
            <span>Extraction Layer Disagreement Detected</span>
          </div>
          {activeDisagreements.map((dis: ObservationDisagreement, idx: number) => (
            <div key={idx} className="text-[10px] text-amber-200/90 pl-5">
              <span>
                {dis.primary_engine || 'Primary'} vs {dis.alternative_engine || 'Alternative'} (Δ chars: {dis.char_count_delta}, Δ tokens: {dis.token_count_delta})
              </span>
              {dis.disagreement_reasons.length > 0 && (
                <p className="text-[10px] text-amber-300/70">{dis.disagreement_reasons.join(' • ')}</p>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Toolbar: Scope, View Mode, Normalization Toggle, Script Filter */}
      <div className="p-3 border-b border-brand-slate space-y-2">
        <div className="flex flex-wrap items-center justify-between gap-2">
          {/* Scope toggle */}
          <div className="inline-flex rounded-md bg-brand-midnight p-0.5 border border-brand-slate text-xs">
            <button
              type="button"
              onClick={() => setScopeAllPages(false)}
              className={`px-2 py-1 rounded text-xs transition-colors ${
                !scopeAllPages
                  ? 'bg-brand-charcoal text-brand-cyan font-medium'
                  : 'text-brand-slate-light hover:text-white'
              }`}
            >
              Page {currentPage}
            </button>
            <button
              type="button"
              onClick={() => setScopeAllPages(true)}
              className={`px-2 py-1 rounded text-xs transition-colors ${
                scopeAllPages
                  ? 'bg-brand-charcoal text-brand-cyan font-medium'
                  : 'text-brand-slate-light hover:text-white'
              }`}
            >
              All Pages
            </button>
          </div>

          {/* Normalization View Toggle (Raw vs Normalized) */}
          <button
            type="button"
            onClick={() => setShowNormalized((prev) => !prev)}
            className={`inline-flex items-center gap-1 px-2 py-1 rounded text-xs border transition-colors ${
              showNormalized
                ? 'bg-brand-midnight text-brand-cyan border-brand-cyan/40'
                : 'bg-brand-charcoal text-slate-300 border-brand-slate hover:text-white'
            }`}
            title="Toggle between Unicode NFC / ASCII Normalized Text and Original Observed Raw Text"
          >
            {showNormalized ? <Eye className="w-3 h-3 text-brand-cyan" /> : <EyeOff className="w-3 h-3" />}
            <span>{showNormalized ? 'Normalized Text' : 'Original Raw Text'}</span>
          </button>

          {/* View mode */}
          <div className="inline-flex rounded-md bg-brand-midnight p-0.5 border border-brand-slate text-xs">
            <button
              type="button"
              onClick={() => setViewMode('lines')}
              className={`px-2 py-1 rounded transition-colors ${
                viewMode === 'lines'
                  ? 'bg-brand-charcoal text-brand-cyan font-medium'
                  : 'text-brand-slate-light hover:text-white'
              }`}
              title="Reading-Order Line View"
            >
              Lines
            </button>
            <button
              type="button"
              onClick={() => setViewMode('tokens')}
              className={`px-2 py-1 rounded transition-colors ${
                viewMode === 'tokens'
                  ? 'bg-brand-charcoal text-brand-cyan font-medium'
                  : 'text-brand-slate-light hover:text-white'
              }`}
              title="Token-Level Inspector"
            >
              Tokens
            </button>
            <button
              type="button"
              onClick={() => setViewMode('raw')}
              className={`px-2 py-1 rounded transition-colors ${
                viewMode === 'raw'
                  ? 'bg-brand-charcoal text-brand-cyan font-medium'
                  : 'text-brand-slate-light hover:text-white'
              }`}
              title="Continuous Raw Text"
            >
              Raw
            </button>
          </div>
        </div>

        {/* Search Bar & Script Filter */}
        {viewMode !== 'raw' && (
          <div className="flex items-center gap-2">
            <div className="relative flex-1">
              <Search className="w-3.5 h-3.5 absolute left-2.5 top-1/2 -translate-y-1/2 text-brand-slate-light" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder={`Search in ${scopeAllPages ? 'document' : `page ${currentPage}`}...`}
                className="w-full bg-brand-midnight border border-brand-slate rounded pl-8 pr-3 py-1.5 text-xs text-white placeholder-brand-slate-light focus:outline-none focus:border-brand-cyan font-sans"
              />
            </div>

            {/* Script filter dropdown */}
            <select
              value={selectedScript}
              onChange={(e) => setSelectedScript(e.target.value)}
              className="bg-brand-midnight border border-brand-slate rounded px-2 py-1.5 text-xs text-slate-300 focus:outline-none focus:border-brand-cyan"
              title="Filter by script type"
            >
              <option value="ALL">All Scripts</option>
              <option value="DEVANAGARI">Devanagari</option>
              <option value="LATIN">Latin</option>
              <option value="MIXED">Mixed</option>
              <option value="NUMERIC">Numeric</option>
            </select>
          </div>
        )}
      </div>

      {/* Selected Token Provenance Drawer (when a token is clicked) */}
      {inspectedToken && (
        <div className="p-2.5 mx-3 mt-2 rounded bg-brand-midnight border border-brand-cyan/50 text-xs space-y-1.5">
          <div className="flex items-center justify-between">
            <span className="font-mono text-brand-cyan font-semibold text-[11px]">
              Token #{inspectedToken.reading_order_index} Provenance
            </span>
            <button
              type="button"
              onClick={() => setInspectedToken(null)}
              className="text-brand-slate-light hover:text-white text-[11px]"
            >
              ✕
            </button>
          </div>

          <div className="grid grid-cols-2 gap-2 text-[10px] font-mono">
            <div>
              <span className="text-brand-slate-light block">Raw Text:</span>
              <span className="text-white font-medium break-all select-all">{inspectedToken.raw_text}</span>
            </div>
            <div>
              <span className="text-brand-slate-light block">Normalized Text:</span>
              <span className="text-brand-cyan font-medium break-all select-all">
                {inspectedToken.normalized_text || inspectedToken.raw_text}
              </span>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-1.5 text-[10px]">
            {inspectedToken.detected_script && (
              <span className="px-1.5 py-0.5 rounded bg-brand-charcoal text-slate-300 border border-brand-slate">
                Script: {inspectedToken.detected_script}
              </span>
            )}

            {inspectedToken.is_numeral_converted && (
              <span className="px-1.5 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/30">
                Converted: {inspectedToken.original_raw_value} → {inspectedToken.normalized_text}
              </span>
            )}

            {inspectedToken.is_uncertain && (
              <span
                className="px-1.5 py-0.5 rounded bg-amber-500/10 text-amber-300 border border-amber-500/30 flex items-center gap-1"
                title={inspectedToken.uncertainty_reason || undefined}
              >
                <AlertTriangle className="w-2.5 h-2.5" />
                <span>Uncertain: {inspectedToken.uncertainty_reason}</span>
              </span>
            )}

            <span className="text-slate-400 font-mono">
              Score:{' '}
              {inspectedToken.confidence !== null && inspectedToken.confidence !== undefined
                ? `${Math.round(inspectedToken.confidence * 100)}% (uncalibrated heuristic)`
                : 'None (vector text)'}
            </span>
          </div>
        </div>
      )}

      {/* Main Content Area */}
      <div className="flex-1 overflow-y-auto p-3 space-y-2">
        {viewMode === 'lines' && (
          <div className="space-y-1.5">
            {allLines.length === 0 ? (
              <p className="text-center text-xs text-brand-slate-light py-6">
                No text lines match your query.
              </p>
            ) : (
              allLines.map((line, idx) => {
                const lineDisplayText = showNormalized
                  ? line.normalizedText || line.rawText
                  : line.rawText;

                return (
                  <div
                    key={`line-${line.id || idx}`}
                    className="p-2 rounded bg-brand-midnight/60 border border-brand-slate/60 hover:border-brand-cyan/40 transition-colors text-xs font-mono"
                  >
                    <div className="flex items-center justify-between text-[10px] text-brand-slate-light mb-1">
                      <div className="flex items-center gap-1.5">
                        <span className="text-slate-400">
                          Line #{idx + 1}
                          {scopeAllPages && ` (p. ${line.pageNumber})`}
                        </span>
                        {line.dominantScript && (
                          <span className="px-1 py-0.2 rounded text-[9px] bg-brand-charcoal text-slate-300 border border-brand-slate/60">
                            {line.dominantScript}
                          </span>
                        )}
                      </div>

                      {line.confidence !== null && line.confidence !== undefined && (
                        <span className="text-emerald-400">
                          {Math.round(line.confidence * 100)}% conf
                        </span>
                      )}
                    </div>

                    <p className="text-white whitespace-pre-wrap leading-relaxed select-text font-sans text-xs">
                      {lineDisplayText}
                    </p>

                    {/* Token chips for this line */}
                    {line.tokens && line.tokens.length > 0 && (
                      <div className="mt-2 pt-1.5 border-t border-brand-slate/30 flex flex-wrap gap-1">
                        {line.tokens.map((tok, tIdx) => {
                          const isTokSelected = selectedTokenId === (tok.id || tok.token_id);
                          const tokDisplayText = showNormalized
                            ? tok.normalized_text || tok.raw_text || tok.text || ''
                            : tok.raw_text || tok.text || '';
                          const isDevanagari = tok.detected_script === 'DEVANAGARI';
                          const isMixed = tok.detected_script === 'MIXED';

                          return (
                            <button
                              key={`tok-chip-${tok.id || tIdx}`}
                              type="button"
                              onClick={() => handleTokenClick(tok, line.pageNumber)}
                              className={`px-1.5 py-0.5 rounded text-[10px] border transition-colors flex items-center gap-1 ${
                                isTokSelected
                                  ? 'bg-brand-cyan text-brand-midnight border-brand-cyan font-semibold'
                                  : isDevanagari
                                  ? 'bg-brand-charcoal text-cyan-200 border-cyan-500/40 hover:border-brand-cyan'
                                  : isMixed
                                  ? 'bg-brand-charcoal text-indigo-200 border-indigo-500/40 hover:border-brand-cyan'
                                  : 'bg-brand-charcoal text-slate-300 border-brand-slate/60 hover:border-brand-cyan/60'
                              }`}
                            >
                              <span>{tokDisplayText}</span>
                              {tok.is_numeral_converted && (
                                <span className="text-[9px] opacity-75 font-mono">०→0</span>
                              )}
                              {tok.is_uncertain && (
                                <AlertTriangle className="w-2.5 h-2.5 text-amber-400 shrink-0" />
                              )}
                            </button>
                          );
                        })}
                      </div>
                    )}
                  </div>
                );
              })
            )}
          </div>
        )}

        {viewMode === 'tokens' && (
          <div className="space-y-1">
            {filteredTokens.length === 0 ? (
              <p className="text-center text-xs text-brand-slate-light py-6">
                No tokens match your search query.
              </p>
            ) : (
              filteredTokens.map((token, idx) => {
                const isSelected = selectedTokenId === (token.id || token.token_id);
                const tokenDisplayText = showNormalized
                  ? token.normalized_text || token.raw_text || token.text || ''
                  : token.raw_text || token.text || '';
                const script = (token.detected_script || '').toUpperCase();
                const isDevanagari = script === 'DEVANAGARI';
                const isMixed = script === 'MIXED';
                const isUnknown = script === 'UNKNOWN';

                return (
                  <div
                    key={`token-item-${token.id || idx}`}
                    onClick={() => handleTokenClick(token, token.pageNumber)}
                    className={`p-2 rounded border cursor-pointer transition-colors ${
                      isSelected
                        ? 'bg-brand-cyan/20 border-brand-cyan text-white shadow-[0_0_8px_rgba(0,229,255,0.4)]'
                        : 'bg-brand-midnight/60 border-brand-slate/60 hover:border-brand-cyan/40 text-slate-300'
                    }`}
                  >
                    <div className="flex items-center justify-between text-[10px] text-brand-slate-light mb-1">
                      <div className="flex items-center gap-1.5">
                        <span className="font-mono text-brand-cyan">
                          #{token.reading_order_index || idx + 1}
                          {scopeAllPages && ` • p. ${token.pageNumber}`}
                        </span>

                        {script && (
                          <span
                            className={`px-1 py-0.2 rounded text-[9px] font-mono border ${
                              isDevanagari
                                ? 'bg-cyan-500/10 text-cyan-300 border-cyan-500/30'
                                : isMixed
                                ? 'bg-indigo-500/10 text-indigo-300 border-indigo-500/30'
                                : isUnknown
                                ? 'bg-red-500/10 text-red-400 border-red-500/30'
                                : 'bg-slate-500/10 text-slate-400 border-slate-500/30'
                            }`}
                          >
                            {script}
                          </span>
                        )}

                        {token.is_numeral_converted && (
                          <span className="px-1 py-0.2 rounded text-[9px] bg-emerald-500/10 text-emerald-400 border border-emerald-500/30">
                            ०-९ → 0-9
                          </span>
                        )}

                        {token.is_uncertain && (
                          <span
                            className="px-1 py-0.2 rounded text-[9px] bg-amber-500/10 text-amber-300 border border-amber-500/30 flex items-center gap-0.5"
                            title={token.uncertainty_reason || undefined}
                          >
                            <AlertTriangle className="w-2.5 h-2.5" />
                            <span>Uncertain</span>
                          </span>
                        )}
                      </div>

                      {token.confidence !== null && token.confidence !== undefined ? (
                        <span className="font-mono text-emerald-400">
                          {Math.round(token.confidence * 100)}%
                        </span>
                      ) : (
                        <span className="font-mono text-slate-500">Heuristic</span>
                      )}
                    </div>

                    <div className="text-xs font-mono font-medium text-white mb-1 flex items-center gap-2">
                      <span>{tokenDisplayText}</span>
                      {showNormalized && token.raw_text && token.raw_text !== tokenDisplayText && (
                        <span className="text-[10px] text-slate-400 font-mono">
                          (raw: {token.raw_text})
                        </span>
                      )}
                    </div>

                    {token.bounding_box && (
                      <div className="text-[10px] text-brand-slate-light font-mono flex items-center gap-1">
                        <Layers className="w-2.5 h-2.5" />
                        <span>{formatBoxLabel(token.bounding_box)}</span>
                      </div>
                    )}
                  </div>
                );
              })
            )}
          </div>
        )}

        {viewMode === 'raw' && (
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-xs text-brand-slate-light">
                Viewing: <span className="text-white font-medium">{showNormalized ? 'Normalized Text (Unicode NFC / ASCII Digits)' : 'Original Observed Text'}</span>
              </span>

              <button
                type="button"
                onClick={handleCopyText}
                className="inline-flex items-center gap-1.5 px-2.5 py-1 text-xs font-medium bg-brand-midnight hover:bg-brand-slate/60 text-slate-300 rounded border border-brand-slate transition-colors"
              >
                {copied ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
                <span>{copied ? 'Copied!' : 'Copy Text'}</span>
              </button>
            </div>

            <textarea
              readOnly
              value={
                scopeAllPages
                  ? showNormalized
                    ? ocrData.full_normalized_text || ocrData.full_raw_text
                    : ocrData.full_raw_text
                  : activeLayer === 'pdfium' && altPdfium
                  ? showNormalized
                    ? altPdfium.normalized_text || altPdfium.raw_text
                    : altPdfium.raw_text
                  : showNormalized
                  ? currentPageData?.normalized_text || currentPageData?.raw_text || ''
                  : currentPageData?.raw_text || ''
              }
              className="w-full h-[400px] p-3 bg-brand-midnight border border-brand-slate rounded text-xs font-mono text-slate-300 leading-relaxed resize-none focus:outline-none"
            />
          </div>
        )}
      </div>

      {/* Forensic Heuristic Disclaimer */}
      <div className="p-2.5 border-t border-brand-slate bg-brand-midnight/60 flex items-start gap-2 text-[10px] text-brand-slate-light">
        <Info className="w-3.5 h-3.5 text-brand-cyan shrink-0 mt-0.5" />
        <p className="leading-tight">
          Confidence scores reflect OCR pattern recognition heuristics and are not calibrated statistical probabilities.
        </p>
      </div>
    </div>
  );
};
