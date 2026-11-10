import React, { useState, useMemo } from 'react';
import {
  ShieldAlert,
  AlertTriangle,
  Flame,
  Info,
  Navigation,
  HelpCircle,
  Eye,
  CheckCircle,
} from 'lucide-react';
import type { ForensicFinding, EvidenceNode, FindingSeverity } from '../../types/api';
import { NormalizedBoundingBox, formatBoxLabel } from '../../utils/coordinates';

interface FindingsInspectorProps {
  findings: ForensicFinding[];
  evidenceList: EvidenceNode[];
  currentPage: number;
  onNavigateToPage: (page: number) => void;
  onSelectEvidence: (evidence: EvidenceNode | null) => void;
  selectedEvidenceId?: string | null;
  onHighlightBox: (box: NormalizedBoundingBox | null) => void;
  onToggleHeatmap?: () => void;
  isHeatmapActive?: boolean;
}

export const FindingsInspector: React.FC<FindingsInspectorProps> = ({
  findings,
  evidenceList,
  currentPage,
  onNavigateToPage,
  onSelectEvidence,
  selectedEvidenceId,
  onHighlightBox,
  onToggleHeatmap,
  isHeatmapActive = false,
}) => {
  const [filterPageOnly, setFilterPageOnly] = useState<boolean>(false);
  const [selectedSeverity, setSelectedSeverity] = useState<string>('ALL');

  // Map evidence nodes by ID for fast lookup
  const evidenceMap = useMemo(() => {
    const map = new Map<string, EvidenceNode>();
    for (const ev of evidenceList) {
      map.set(ev.id, ev);
    }
    return map;
  }, [evidenceList]);

  // Filter findings
  const filteredFindings = useMemo(() => {
    return findings.filter((f) => {
      if (filterPageOnly && f.page_number && f.page_number !== currentPage) {
        return false;
      }
      if (selectedSeverity !== 'ALL' && f.severity !== selectedSeverity) {
        return false;
      }
      return true;
    });
  }, [findings, filterPageOnly, currentPage, selectedSeverity]);

  const severityCounts = useMemo(() => {
    const counts: Record<string, number> = { CRITICAL: 0, HIGH: 0, MEDIUM: 0, LOW: 0, INFORMATIONAL: 0 };
    for (const f of findings) {
      if (counts[f.severity] !== undefined) {
        counts[f.severity]++;
      }
    }
    return counts;
  }, [findings]);

  const getSeverityBadge = (sev: FindingSeverity) => {
    switch (sev) {
      case 'CRITICAL':
        return (
          <span className="inline-flex items-center gap-1 text-[10px] font-semibold text-rose-400 bg-rose-500/15 border border-rose-500/30 px-1.5 py-0.5 rounded">
            <Flame className="w-2.5 h-2.5" />
            <span>CRITICAL</span>
          </span>
        );
      case 'HIGH':
        return (
          <span className="inline-flex items-center gap-1 text-[10px] font-semibold text-orange-400 bg-orange-500/15 border border-orange-500/30 px-1.5 py-0.5 rounded">
            <AlertTriangle className="w-2.5 h-2.5" />
            <span>HIGH</span>
          </span>
        );
      case 'MEDIUM':
        return (
          <span className="inline-flex items-center gap-1 text-[10px] font-semibold text-amber-300 bg-amber-500/15 border border-amber-500/30 px-1.5 py-0.5 rounded">
            <AlertTriangle className="w-2.5 h-2.5" />
            <span>MEDIUM</span>
          </span>
        );
      case 'LOW':
        return (
          <span className="inline-flex items-center gap-1 text-[10px] font-semibold text-blue-400 bg-blue-500/15 border border-blue-500/30 px-1.5 py-0.5 rounded">
            <Info className="w-2.5 h-2.5" />
            <span>LOW</span>
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center gap-1 text-[10px] font-semibold text-slate-400 bg-slate-500/15 border border-slate-500/30 px-1.5 py-0.5 rounded">
            <Info className="w-2.5 h-2.5" />
            <span>INFO</span>
          </span>
        );
    }
  };

  const handleLocateFinding = (finding: ForensicFinding) => {
    // Locate via finding's supporting evidence
    const supportingId = finding.evidence_ids?.[0];
    const evidence = supportingId ? evidenceMap.get(supportingId) : null;

    if (evidence) {
      onSelectEvidence(evidence);
      if (evidence.page_number && evidence.page_number !== currentPage) {
        onNavigateToPage(evidence.page_number);
      }
      if (evidence.bounding_box) {
        onHighlightBox(evidence.bounding_box);
      }
    } else if (finding.page_number) {
      if (finding.page_number !== currentPage) {
        onNavigateToPage(finding.page_number);
      }
      if (finding.bounding_box) {
        onHighlightBox(finding.bounding_box);
      }
    }
  };

  return (
    <div className="flex flex-col h-full bg-brand-charcoal text-slate-200">
      {/* Forensic Caveat Header */}
      <div className="p-3 border-b border-brand-slate bg-brand-midnight/60">
        <div className="flex items-start gap-2 p-2 rounded bg-amber-500/10 border border-amber-500/20 text-[11px] text-amber-200/90 leading-tight">
          <ShieldAlert className="w-3.5 h-3.5 text-amber-400 shrink-0 mt-0.5" />
          <p>
            Forensic findings and visual heatmaps indicate potential anomalies for investigator triage. They do not constitute automated fraud determinations.
          </p>
        </div>
      </div>

      {/* Filter Strip */}
      <div className="p-3 border-b border-brand-slate space-y-2">
        <div className="flex items-center justify-between text-xs">
          <div className="flex items-center gap-1 font-mono text-[11px]">
            <span className="text-white font-semibold">{findings.length}</span>
            <span className="text-brand-slate-light">findings total</span>
          </div>

          {/* Page scope toggle */}
          <button
            type="button"
            onClick={() => setFilterPageOnly(!filterPageOnly)}
            className={`px-2 py-0.5 rounded text-[11px] border transition-colors ${
              filterPageOnly
                ? 'bg-brand-cyan/20 border-brand-cyan text-brand-cyan font-medium'
                : 'bg-brand-midnight border-brand-slate text-brand-slate-light hover:text-white'
            }`}
          >
            {filterPageOnly ? `Page ${currentPage} Only` : 'All Pages'}
          </button>
        </div>

        {/* Severity filter pills */}
        <div className="flex flex-wrap gap-1">
          {['ALL', 'CRITICAL', 'HIGH', 'MEDIUM', 'LOW'].map((sev) => {
            const count = sev === 'ALL' ? findings.length : severityCounts[sev] || 0;
            return (
              <button
                key={sev}
                type="button"
                onClick={() => setSelectedSeverity(sev)}
                className={`px-2 py-0.5 rounded text-[10px] font-mono border transition-colors ${
                  selectedSeverity === sev
                    ? 'bg-brand-blue border-brand-blue text-white'
                    : 'bg-brand-midnight/60 border-brand-slate/60 text-brand-slate-light hover:text-slate-300'
                }`}
              >
                {sev} ({count})
              </button>
            );
          })}
        </div>
      </div>

      {/* Findings List */}
      <div className="flex-1 overflow-y-auto p-3 space-y-2.5">
        {filteredFindings.length === 0 ? (
          <div className="p-6 text-center text-slate-400">
            <CheckCircle className="w-8 h-8 mx-auto mb-2 text-emerald-400 opacity-60" />
            <h5 className="text-xs font-semibold text-white mb-0.5">No Findings Detected</h5>
            <p className="text-[11px] text-brand-slate-light">
              No anomalies found for the current page and filter criteria.
            </p>
          </div>
        ) : (
          filteredFindings.map((finding) => {
            const supportingEvidence = (finding.evidence_ids || [])
              .map((id) => evidenceMap.get(id))
              .filter(Boolean) as EvidenceNode[];

            const isSelected = supportingEvidence.some((ev) => ev.id === selectedEvidenceId);
            const isVisual = finding.category === 'VISUAL_ANOMALY' || finding.finding_type?.includes('visual');

            return (
              <div
                key={finding.id}
                className={`p-3 rounded-lg border transition-all ${
                  isSelected
                    ? 'bg-brand-midnight border-brand-cyan shadow-[0_0_12px_rgba(0,229,255,0.25)]'
                    : 'bg-brand-midnight/60 border-brand-slate/60 hover:border-brand-slate'
                }`}
              >
                {/* Finding Header */}
                <div className="flex items-start justify-between gap-2 mb-1.5">
                  <div className="space-y-0.5">
                    <h5 className="text-xs font-medium text-white leading-snug">{finding.title}</h5>
                    <div className="flex items-center gap-2 text-[10px] text-brand-slate-light font-mono">
                      <span>{finding.category || finding.finding_type || 'ANOMALY'}</span>
                      {finding.page_number && <span>• Page {finding.page_number}</span>}
                    </div>
                  </div>

                  {getSeverityBadge(finding.severity)}
                </div>

                {/* Description */}
                <p className="text-xs text-slate-300 leading-relaxed mb-2.5 font-sans">
                  {finding.description}
                </p>

                {/* Visual ELA Specific Caveat */}
                {isVisual && (
                  <div className="mb-2 p-2 rounded bg-brand-charcoal/90 border border-brand-slate/50 text-[10px] text-brand-slate-light space-y-1">
                    <div className="flex items-center gap-1.5 text-amber-300 font-medium">
                      <Flame className="w-3 h-3" />
                      <span>Visual Forensics Indicator</span>
                    </div>
                    <p>
                      Compression differences may arise from legitimate re-saving, embedded graphics, or scanner artifacts. Manual verification required.
                    </p>
                    {onToggleHeatmap && (
                      <button
                        type="button"
                        onClick={onToggleHeatmap}
                        className="inline-flex items-center gap-1 text-brand-cyan hover:underline text-[10px] font-medium pt-0.5"
                      >
                        <Eye className="w-3 h-3" />
                        <span>{isHeatmapActive ? 'Hide Heatmap Overlay' : 'View Heatmap Overlay'}</span>
                      </button>
                    )}
                  </div>
                )}

                {/* Limitations */}
                {finding.limitations && finding.limitations.length > 0 && (
                  <div className="mb-2 text-[10px] text-slate-400 space-y-0.5">
                    <div className="flex items-center gap-1 text-slate-400 font-medium">
                      <HelpCircle className="w-2.5 h-2.5" />
                      <span>Known Limitations:</span>
                    </div>
                    <ul className="list-disc list-inside space-y-0.5 text-brand-slate-light pl-1">
                      {finding.limitations.map((lim, idx) => (
                        <li key={idx}>{lim}</li>
                      ))}
                    </ul>
                  </div>
                )}

                {/* Supporting Evidence Links & Actions */}
                <div className="pt-2 border-t border-brand-slate/40 flex items-center justify-between text-[10px]">
                  <div className="flex items-center gap-1.5 text-brand-slate-light">
                    <span>Evidence:</span>
                    {supportingEvidence.length > 0 ? (
                      supportingEvidence.map((ev) => (
                        <button
                          key={ev.id}
                          type="button"
                          onClick={() => {
                            onSelectEvidence(ev);
                            if (ev.page_number && ev.page_number !== currentPage) {
                              onNavigateToPage(ev.page_number);
                            }
                            if (ev.bounding_box) {
                              onHighlightBox(ev.bounding_box);
                            }
                          }}
                          className={`font-mono hover:text-brand-cyan transition-colors ${
                            selectedEvidenceId === ev.id ? 'text-brand-cyan font-bold' : ''
                          }`}
                          title={ev.bounding_box ? formatBoxLabel(ev.bounding_box) : 'No coordinate box'}
                        >
                          #{ev.id.slice(-6)}
                        </button>
                      ))
                    ) : (
                      <span className="italic">None cited</span>
                    )}
                  </div>

                  <button
                    type="button"
                    onClick={() => handleLocateFinding(finding)}
                    className="inline-flex items-center gap-1 text-brand-cyan hover:text-white transition-colors font-medium"
                  >
                    <Navigation className="w-3 h-3" />
                    <span>Locate on Page</span>
                  </button>
                </div>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
};
