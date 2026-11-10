import React from 'react';
import { Link } from 'react-router-dom';
import {
  X,
  FileText,
  GitFork,
  ArrowRight,
  Shield,
  Share2,
  AlertTriangle,
  Info,
} from 'lucide-react';
import type { GraphNode, GraphEdge, GraphRelationshipStatus } from '../../types/api';

interface GraphDetailsInspectorProps {
  selectedNode: GraphNode | null;
  selectedEdge: GraphEdge | null;
  allNodes: GraphNode[];
  caseId: string;
  onClose: () => void;
  onSelectNode: (nodeId: string) => void;
  onSelectEdge: (edgeId: string) => void;
  onExpandNeighborhood: (nodeId: string) => void;
  onSetPathSource: (nodeId: string) => void;
  onSetPathTarget: (nodeId: string) => void;
  isExpanding?: boolean;
}

export const GraphDetailsInspector: React.FC<GraphDetailsInspectorProps> = ({
  selectedNode,
  selectedEdge,
  allNodes,
  caseId,
  onClose,
  onSelectNode,
  onExpandNeighborhood,
  onSetPathSource,
  onSetPathTarget,
  isExpanding = false,
}) => {
  const nodeMap = React.useMemo(() => {
    const map = new Map<string, GraphNode>();
    for (const n of allNodes) {
      map.set(n.id, n);
    }
    return map;
  }, [allNodes]);

  if (!selectedNode && !selectedEdge) {
    return null;
  }

  const getStatusBadge = (status: GraphRelationshipStatus | string) => {
    switch (status.toUpperCase()) {
      case 'CONFIRMED':
        return (
          <span className="px-2 py-0.5 rounded text-[10px] font-mono font-semibold bg-emerald-500/15 border border-emerald-500/30 text-emerald-300">
            CONFIRMED
          </span>
        );
      case 'CANDIDATE':
        return (
          <span className="px-2 py-0.5 rounded text-[10px] font-mono font-semibold bg-amber-500/15 border border-amber-500/30 text-amber-300">
            CANDIDATE
          </span>
        );
      case 'CONTRADICTED':
        return (
          <span className="px-2 py-0.5 rounded text-[10px] font-mono font-semibold bg-red-500/15 border border-red-500/30 text-red-300">
            CONTRADICTED
          </span>
        );
      case 'UNRESOLVED':
        return (
          <span className="px-2 py-0.5 rounded text-[10px] font-mono font-semibold bg-slate-500/15 border border-slate-500/30 text-slate-400">
            UNRESOLVED
          </span>
        );
      default:
        return (
          <span className="px-2 py-0.5 rounded text-[10px] font-mono font-semibold bg-brand-slate/40 text-brand-slate-light border border-brand-slate">
            {status}
          </span>
        );
    }
  };

  return (
    <div className="w-80 md:w-96 bg-brand-charcoal border-l border-brand-slate flex flex-col h-full shrink-0 shadow-2xl z-30 select-text overflow-hidden">
      {/* Top Header */}
      <div className="p-3 border-b border-brand-slate flex items-center justify-between bg-brand-midnight/60">
        <div className="flex items-center gap-1.5 min-w-0">
          <Share2 className="w-4 h-4 text-brand-cyan shrink-0" />
          <span className="text-xs font-semibold text-white uppercase tracking-wider truncate">
            {selectedNode ? 'Node Details' : 'Relationship Semantics'}
          </span>
        </div>

        <button
          type="button"
          onClick={onClose}
          className="p-1 rounded text-brand-slate-light hover:text-white hover:bg-brand-slate/50 transition-colors"
          title="Close Inspector"
        >
          <X className="w-4 h-4" />
        </button>
      </div>

      {/* Main Inspector Scroll Area */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4 text-xs text-slate-300">
        {/* ======================================================== */}
        {/* NODE INSPECTOR */}
        {/* ======================================================== */}
        {selectedNode && (
          <>
            {/* Title & Type Badge */}
            <div className="space-y-1.5 pb-3 border-b border-brand-slate/60">
              <div className="flex items-center justify-between gap-2">
                <span className="px-2 py-0.5 rounded text-[10px] font-mono font-semibold bg-brand-cyan/15 border border-brand-cyan/30 text-brand-cyan uppercase">
                  {selectedNode.node_type.replace('_', ' ')}
                </span>
                <span className="text-[10px] font-mono text-brand-slate-light">
                  {selectedNode.source_entity_type}
                </span>
              </div>

              <h4 className="text-sm font-semibold text-white leading-snug">
                {selectedNode.label}
              </h4>

              <div className="text-[10px] font-mono text-brand-slate-light truncate" title={selectedNode.id}>
                ID: {selectedNode.id}
              </div>
            </div>

            {/* Quick Actions Bar */}
            <div className="grid grid-cols-2 gap-2">
              <button
                type="button"
                disabled={isExpanding}
                onClick={() => onExpandNeighborhood(selectedNode.id)}
                className="inline-flex items-center justify-center gap-1.5 px-2.5 py-1.5 rounded bg-brand-midnight hover:bg-brand-slate/50 border border-brand-slate text-xs font-medium text-white transition-colors disabled:opacity-50"
              >
                <GitFork className="w-3.5 h-3.5 text-brand-cyan" />
                <span>{isExpanding ? 'Expanding...' : 'Expand 2 Hops'}</span>
              </button>

              {/* Navigate to Document Examination if Document ID is available */}
              {Boolean(
                selectedNode.node_type === 'DOCUMENT'
                  ? selectedNode.source_entity_id
                  : selectedNode.provenance?.document_id
              ) && (
                  <Link
                    to={`/cases/${caseId}/documents/${selectedNode.node_type === 'DOCUMENT'
                        ? selectedNode.source_entity_id
                        : selectedNode.provenance?.document_id
                      }/examine`}
                    className="inline-flex items-center justify-center gap-1.5 px-2.5 py-1.5 rounded bg-brand-blue/30 hover:bg-brand-blue/60 border border-brand-blue/50 text-xs font-medium text-brand-cyan transition-colors"
                  >
                    <FileText className="w-3.5 h-3.5" />
                    <span>View in Doc</span>
                  </Link>
                )}

              <button
                type="button"
                onClick={() => onSetPathSource(selectedNode.id)}
                className="inline-flex items-center justify-center gap-1 px-2 py-1 rounded bg-brand-midnight hover:bg-brand-slate/40 border border-brand-slate/60 text-[11px] text-slate-300"
              >
                <span>Set as Source</span>
              </button>

              <button
                type="button"
                onClick={() => onSetPathTarget(selectedNode.id)}
                className="inline-flex items-center justify-center gap-1 px-2 py-1 rounded bg-brand-midnight hover:bg-brand-slate/40 border border-brand-slate/60 text-[11px] text-slate-300"
              >
                <span>Set as Target</span>
              </button>
            </div>

            {/* Display Attributes */}
            {selectedNode.display_attributes &&
              Object.keys(selectedNode.display_attributes).length > 0 && (
                <div className="space-y-1.5">
                  <h5 className="font-semibold text-white uppercase text-[10px] tracking-wider text-brand-slate-light">
                    Display Attributes
                  </h5>
                  <div className="bg-brand-midnight/60 rounded border border-brand-slate/60 p-2.5 space-y-1.5 font-mono text-[11px]">
                    {Object.entries(selectedNode.display_attributes).map(([k, v]) => (
                      <div key={k} className="flex items-start justify-between gap-2">
                        <span className="text-brand-slate-light shrink-0">{k}:</span>
                        <span className="text-white truncate max-w-[190px]" title={String(v)}>
                          {String(v ?? '-')}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

            {/* Provenance & Traceability */}
            {selectedNode.provenance && Object.keys(selectedNode.provenance).length > 0 && (
              <div className="space-y-1.5">
                <h5 className="font-semibold text-white uppercase text-[10px] tracking-wider text-brand-slate-light">
                  Evidentiary Provenance
                </h5>
                <div className="bg-brand-midnight/60 rounded border border-brand-slate/60 p-2.5 space-y-1.5 font-mono text-[11px]">
                  {Object.entries(selectedNode.provenance).map(([k, v]) => (
                    <div key={k} className="flex items-start justify-between gap-2">
                      <span className="text-brand-slate-light shrink-0">{k}:</span>
                      <span className="text-white truncate max-w-[190px]" title={typeof v === 'object' ? JSON.stringify(v) : String(v)}>
                        {typeof v === 'object' ? JSON.stringify(v) : String(v ?? '-')}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </>
        )}

        {/* ======================================================== */}
        {/* EDGE INSPECTOR */}
        {/* ======================================================== */}
        {selectedEdge && (
          <>
            {/* Edge Title & Status */}
            <div className="space-y-2 pb-3 border-b border-brand-slate/60">
              <div className="flex items-center justify-between gap-2">
                <span className="text-xs font-semibold text-white uppercase tracking-wider font-mono">
                  {selectedEdge.predicate.replace(/_/g, ' ')}
                </span>
                {getStatusBadge(selectedEdge.status)}
              </div>

              {/* Subject -> Object Directionality */}
              <div className="p-2 rounded bg-brand-midnight border border-brand-slate/60 space-y-1.5 text-xs">
                <div className="flex items-center justify-between gap-2">
                  <span className="text-[10px] font-mono text-brand-slate-light uppercase">Subject</span>
                  <button
                    type="button"
                    onClick={() => onSelectNode(selectedEdge.source_node_id)}
                    className="font-medium text-brand-cyan hover:underline truncate max-w-[200px]"
                  >
                    {nodeMap.get(selectedEdge.source_node_id)?.label || selectedEdge.source_node_id}
                  </button>
                </div>

                <div className="flex items-center justify-center py-0.5 text-brand-slate-light">
                  <ArrowRight className="w-3.5 h-3.5 text-brand-cyan" />
                </div>

                <div className="flex items-center justify-between gap-2">
                  <span className="text-[10px] font-mono text-brand-slate-light uppercase">Object</span>
                  <button
                    type="button"
                    onClick={() => onSelectNode(selectedEdge.target_node_id)}
                    className="font-medium text-brand-cyan hover:underline truncate max-w-[200px]"
                  >
                    {nodeMap.get(selectedEdge.target_node_id)?.label || selectedEdge.target_node_id}
                  </button>
                </div>
              </div>
            </div>

            {/* Explanation */}
            {selectedEdge.explanation && (
              <div className="space-y-1">
                <h5 className="font-semibold text-white uppercase text-[10px] tracking-wider text-brand-slate-light">
                  Evidentiary Rationale
                </h5>
                <p className="p-2.5 rounded bg-brand-midnight/60 border border-brand-slate/60 text-xs text-slate-300 leading-relaxed font-sans">
                  {selectedEdge.explanation}
                </p>
              </div>
            )}

            {/* Determination & Score */}
            <div className="space-y-1.5">
              <h5 className="font-semibold text-white uppercase text-[10px] tracking-wider text-brand-slate-light">
                Ontology Metadata
              </h5>
              <div className="bg-brand-midnight/60 rounded border border-brand-slate/60 p-2.5 space-y-1.5 font-mono text-[11px]">
                <div className="flex items-center justify-between">
                  <span className="text-brand-slate-light">Determination:</span>
                  <span className="text-white">
                    {selectedEdge.status_determination_method || 'EVIDENTIARY_RULE'}
                  </span>
                </div>

                {selectedEdge.score !== null && selectedEdge.score !== undefined && (
                  <div className="flex items-center justify-between">
                    <span className="text-brand-slate-light">Heuristic Score:</span>
                    <span className="text-amber-300 font-semibold">{selectedEdge.score}</span>
                  </div>
                )}
              </div>
            </div>

            {/* Supporting Evidence References */}
            <div className="space-y-1.5">
              <h5 className="font-semibold text-white uppercase text-[10px] tracking-wider text-brand-slate-light">
                Supporting Evidence ({selectedEdge.supporting_evidence_ids?.length || 0})
              </h5>
              {!selectedEdge.supporting_evidence_ids || selectedEdge.supporting_evidence_ids.length === 0 ? (
                <p className="text-[11px] text-slate-500 italic">No direct evidence nodes linked.</p>
              ) : (
                <div className="space-y-1">
                  {selectedEdge.supporting_evidence_ids.map((id) => (
                    <div
                      key={id}
                      className="p-1.5 rounded bg-brand-midnight/80 border border-brand-slate/50 text-[11px] font-mono text-emerald-400 flex items-center justify-between"
                    >
                      <span>Evidence #{id.slice(-8)}</span>
                      <Shield className="w-3 h-3 text-emerald-400" />
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Contradicting Evidence References */}
            {selectedEdge.contradicting_evidence_ids && selectedEdge.contradicting_evidence_ids.length > 0 && (
              <div className="space-y-1.5">
                <h5 className="font-semibold text-rose-400 uppercase text-[10px] tracking-wider">
                  Contradicting Evidence ({selectedEdge.contradicting_evidence_ids.length})
                </h5>
                <div className="space-y-1">
                  {selectedEdge.contradicting_evidence_ids.map((id) => (
                    <div
                      key={id}
                      className="p-1.5 rounded bg-red-950/40 border border-red-500/40 text-[11px] font-mono text-rose-300 flex items-center justify-between"
                    >
                      <span>Conflict #{id.slice(-8)}</span>
                      <AlertTriangle className="w-3 h-3 text-rose-400" />
                    </div>
                  ))}
                </div>
              </div>
            )}
          </>
        )}
      </div>

      {/* Epistemic Disclaimer Footer */}
      <div className="p-2.5 border-t border-brand-slate bg-brand-midnight/80 flex items-start gap-2 text-[10px] text-brand-slate-light">
        <Info className="w-3.5 h-3.5 text-brand-cyan shrink-0 mt-0.5" />
        <p className="leading-tight">
          Graph relationships reflect deterministic domain ontology rules and candidate entity links. Candidate connections are not confirmed facts.
        </p>
      </div>
    </div>
  );
};
