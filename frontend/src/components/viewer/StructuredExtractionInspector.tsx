import React, { useState } from 'react';
import {
  FileSpreadsheet,
  Eye,
  EyeOff,
  Navigation,
  CheckCircle2,
  AlertTriangle,
  HelpCircle,
  AlertCircle,
  ExternalLink,
  Shield,
  Layers,
  Info,
} from 'lucide-react';
import type { DocumentExtractionResult, ExtractedFieldValue } from '../../types/api';
import { NormalizedBoundingBox, formatBoxLabel } from '../../utils/coordinates';
import { isSensitiveField, maskSensitiveValue } from '../../utils/masking';

interface StructuredExtractionInspectorProps {
  extractionData?: DocumentExtractionResult | null;
  currentPage: number;
  onNavigateToPage: (page: number) => void;
  onHighlightBox: (box: NormalizedBoundingBox | null) => void;
  onSelectEvidenceNode?: (evidenceId: string) => void;
}

export const StructuredExtractionInspector: React.FC<StructuredExtractionInspectorProps> = ({
  extractionData,
  currentPage,
  onNavigateToPage,
  onHighlightBox,
  onSelectEvidenceNode,
}) => {
  const [unmaskedFields, setUnmaskedFields] = useState<Set<string>>(new Set());
  const [selectedFieldKey, setSelectedFieldKey] = useState<string | null>(null);

  const toggleMask = (key: string) => {
    setUnmaskedFields((prev) => {
      const next = new Set(prev);
      if (next.has(key)) {
        next.delete(key);
      } else {
        next.add(key);
      }
      return next;
    });
  };

  if (!extractionData || Object.keys(extractionData.fields || {}).length === 0) {
    return (
      <div className="p-6 text-center text-slate-400">
        <FileSpreadsheet className="w-10 h-10 mx-auto mb-3 text-brand-slate-light opacity-50" />
        <h4 className="text-sm font-semibold text-white mb-1">No Structured Fields Extracted</h4>
        <p className="text-xs text-slate-400 max-w-xs mx-auto">
          Structured field extraction has not been executed on this document. Run field extraction from Processing Controls to inspect structured fields.
        </p>
      </div>
    );
  }

  const fields = Object.values(extractionData.fields);

  const getStatusBadge = (status: string) => {
    switch (status.toUpperCase()) {
      case 'VALID':
      case 'PASSED':
        return (
          <span className="inline-flex items-center gap-1 text-[10px] text-emerald-400 bg-emerald-500/10 px-1.5 py-0.5 rounded border border-emerald-500/30">
            <CheckCircle2 className="w-2.5 h-2.5" />
            <span>Valid</span>
          </span>
        );
      case 'WARNING':
        return (
          <span className="inline-flex items-center gap-1 text-[10px] text-amber-400 bg-amber-500/10 px-1.5 py-0.5 rounded border border-amber-500/30">
            <AlertTriangle className="w-2.5 h-2.5" />
            <span>Warning</span>
          </span>
        );
      case 'ERROR':
      case 'FAILED':
        return (
          <span className="inline-flex items-center gap-1 text-[10px] text-red-400 bg-red-500/10 px-1.5 py-0.5 rounded border border-red-500/30">
            <AlertCircle className="w-2.5 h-2.5" />
            <span>Error</span>
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center gap-1 text-[10px] text-slate-400 bg-brand-midnight px-1.5 py-0.5 rounded border border-brand-slate">
            <HelpCircle className="w-2.5 h-2.5" />
            <span>Unvalidated</span>
          </span>
        );
    }
  };

  const handleFieldClick = (field: ExtractedFieldValue) => {
    setSelectedFieldKey(field.field_key);
    const firstBox = field.source_bounding_boxes?.[0];
    if (firstBox) {
      if (field.source_page_number && field.source_page_number !== currentPage) {
        onNavigateToPage(field.source_page_number);
      }
      onHighlightBox(firstBox);
    } else {
      onHighlightBox(null);
    }
  };

  return (
    <div className="flex flex-col h-full bg-brand-charcoal text-slate-200">
      {/* Schema Header */}
      <div className="p-3 border-b border-brand-slate bg-brand-midnight/40">
        <div className="flex items-center justify-between text-xs mb-1">
          <div className="flex items-center gap-1.5">
            <Shield className="w-3.5 h-3.5 text-brand-cyan" />
            <span className="font-semibold text-white uppercase tracking-wider text-[11px]">
              {extractionData.document_class}
            </span>
          </div>

          <span className="text-[10px] font-mono text-brand-slate-light">
            Schema: {extractionData.schema_id} (v{extractionData.schema_version})
          </span>
        </div>

        <div className="text-[11px] text-brand-slate-light flex items-center justify-between">
          <span>{fields.length} extracted fields</span>
          <span className="font-mono">{extractionData.execution_duration_ms} ms</span>
        </div>
      </div>

      {/* Field List */}
      <div className="flex-1 overflow-y-auto p-3 space-y-2">
        {fields.map((field) => {
          const isSelected = selectedFieldKey === field.field_key;
          const sensitive = isSensitiveField(field.field_key, field.data_type);
          const isUnmasked = unmaskedFields.has(field.field_key);

          // Check if normalized value differs from raw text
          const hasDifferentNormalization =
            field.normalized_value !== null &&
            field.normalized_value !== undefined &&
            String(field.normalized_value) !== field.raw_text;

          const rawDisplay =
            sensitive && !isUnmasked ? maskSensitiveValue(field.raw_text) : field.raw_text;
          const normDisplay =
            sensitive && !isUnmasked
              ? maskSensitiveValue(String(field.normalized_value ?? ''))
              : String(field.normalized_value ?? '');

          const hasBoundingBox = Boolean(
            field.source_bounding_boxes && field.source_bounding_boxes.length > 0
          );

          const heuristicScore = field.score ?? field.confidence;

          return (
            <div
              key={field.id || field.field_key}
              onClick={() => handleFieldClick(field)}
              className={`p-3 rounded-lg border transition-all cursor-pointer ${
                isSelected
                  ? 'bg-brand-midnight border-brand-cyan shadow-[0_0_10px_rgba(0,229,255,0.25)]'
                  : 'bg-brand-midnight/60 border-brand-slate/60 hover:border-brand-slate'
              }`}
            >
              {/* Field Label and Status */}
              <div className="flex items-start justify-between gap-2 mb-1.5">
                <div>
                  <h5 className="text-xs font-medium text-white">{field.label}</h5>
                  <span className="text-[10px] font-mono text-brand-slate-light">
                    {field.field_key} ({field.data_type})
                  </span>
                </div>

                <div className="flex items-center gap-1.5 shrink-0">
                  {getStatusBadge(field.validation_status)}
                </div>
              </div>

              {/* Extracted Value Display */}
              <div className="space-y-1 mb-2">
                {/* Normalized / Primary Value */}
                <div className="flex items-center justify-between gap-2 py-1 px-2 bg-brand-charcoal/80 rounded border border-brand-slate/40 text-xs font-mono">
                  <div className="flex items-center gap-1.5 truncate">
                    {hasDifferentNormalization && (
                      <span className="text-[10px] text-brand-cyan font-sans uppercase tracking-wider">
                        Norm:
                      </span>
                    )}
                    <span className="text-white truncate font-medium" title={normDisplay || rawDisplay}>
                      {hasDifferentNormalization ? normDisplay : rawDisplay}
                    </span>
                  </div>

                  {sensitive && (
                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation();
                        toggleMask(field.field_key);
                      }}
                      className="p-1 text-brand-slate-light hover:text-brand-cyan transition-colors shrink-0"
                      title={isUnmasked ? 'Mask identifier' : 'Reveal identifier'}
                    >
                      {isUnmasked ? <EyeOff className="w-3.5 h-3.5" /> : <Eye className="w-3.5 h-3.5" />}
                    </button>
                  )}
                </div>

                {/* Original Observed Raw Value if different */}
                {hasDifferentNormalization && (
                  <div className="px-2 py-0.5 text-[10px] font-mono text-slate-400 flex items-center gap-1">
                    <span className="text-brand-slate-light">Observed:</span>
                    <span className="text-slate-300 font-medium truncate">{rawDisplay}</span>
                  </div>
                )}
              </div>

              {/* Provenance, Location & Confidence */}
              <div className="flex flex-wrap items-center justify-between gap-2 text-[10px] text-brand-slate-light">
                <div className="flex items-center gap-2">
                  <span>Page {field.source_page_number}</span>
                  {hasBoundingBox ? (
                    <span className="inline-flex items-center gap-1 text-brand-cyan font-mono">
                      <Layers className="w-2.5 h-2.5" />
                      {formatBoxLabel(field.source_bounding_boxes![0])}
                    </span>
                  ) : (
                    <span className="text-slate-500 italic">No spatial bounds</span>
                  )}
                </div>

                <div className="flex items-center gap-2">
                  {heuristicScore !== null && heuristicScore !== undefined && (
                    <span
                      className="font-mono text-emerald-400"
                      title={field.confidence_explanation || 'Uncalibrated rule match score'}
                    >
                      Score: {Math.round(heuristicScore * 100)}%
                    </span>
                  )}

                  {hasBoundingBox && (
                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation();
                        handleFieldClick(field);
                      }}
                      className="inline-flex items-center gap-1 text-brand-cyan hover:text-white transition-colors text-[10px]"
                    >
                      <Navigation className="w-2.5 h-2.5" />
                      <span>Locate</span>
                    </button>
                  )}
                </div>
              </div>

              {/* Warnings & Notes */}
              {field.warnings && field.warnings.length > 0 && (
                <div className="mt-2 pt-1.5 border-t border-brand-slate/30 text-[10px] text-amber-400 space-y-0.5">
                  {field.warnings.map((w, wIdx) => (
                    <div key={wIdx} className="flex items-center gap-1">
                      <AlertTriangle className="w-2.5 h-2.5 shrink-0" />
                      <span>{w}</span>
                    </div>
                  ))}
                </div>
              )}

              {/* Evidence Node Link */}
              {field.evidence_node_id && onSelectEvidenceNode && (
                <div className="mt-1 text-right">
                  <button
                    type="button"
                    onClick={(e) => {
                      e.stopPropagation();
                      onSelectEvidenceNode(field.evidence_node_id!);
                    }}
                    className="text-[10px] text-brand-slate-light hover:text-brand-cyan transition-colors inline-flex items-center gap-1"
                  >
                    <ExternalLink className="w-2.5 h-2.5" />
                    <span>Evidence #{field.evidence_node_id.slice(-6)}</span>
                  </button>
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* Epistemic Integrity Notice */}
      <div className="p-2.5 border-t border-brand-slate bg-brand-midnight/60 flex items-start gap-2 text-[10px] text-brand-slate-light">
        <Info className="w-3.5 h-3.5 text-brand-cyan shrink-0 mt-0.5" />
        <p className="leading-tight">
          Structured fields represent candidate extractions with heuristic scores. They are not promoted to verified facts without investigator corroboration.
        </p>
      </div>
    </div>
  );
};
