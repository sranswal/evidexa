import React, { useState } from 'react';
import {
  X,
  GitFork,
  ArrowRight,
  Search,
  AlertTriangle,
  Loader2,
} from 'lucide-react';
import type { GraphNode, GraphPath, GraphPathsResult } from '../../types/api';
import { graphApi } from '../../api/graph';

interface PathExplorationPanelProps {
  isOpen: boolean;
  onClose: () => void;
  caseId: string;
  allNodes: GraphNode[];
  initialSourceId?: string | null;
  initialTargetId?: string | null;
  onHighlightPath: (path: GraphPath | null) => void;
}

export const PathExplorationPanel: React.FC<PathExplorationPanelProps> = ({
  isOpen,
  onClose,
  caseId,
  allNodes,
  initialSourceId,
  initialTargetId,
  onHighlightPath,
}) => {
  const [sourceNodeId, setSourceNodeId] = useState<string>(initialSourceId || '');
  const [targetNodeId, setTargetNodeId] = useState<string>(initialTargetId || '');
  const [maxDepth, setMaxDepth] = useState<number>(4);
  const [confirmedOnly, setConfirmedOnly] = useState<boolean>(false);

  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<GraphPathsResult | null>(null);
  const [selectedPathIndex, setSelectedPathIndex] = useState<number | null>(null);

  // Sync initial props
  React.useEffect(() => {
    if (initialSourceId) setSourceNodeId(initialSourceId);
  }, [initialSourceId]);

  React.useEffect(() => {
    if (initialTargetId) setTargetNodeId(initialTargetId);
  }, [initialTargetId]);

  if (!isOpen) return null;

  const nodeMap = new Map<string, GraphNode>();
  for (const n of allNodes) {
    nodeMap.set(n.id, n);
  }

  const handleSearchPaths = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!sourceNodeId || !targetNodeId) {
      setError('Please select both a source and target node.');
      return;
    }
    if (sourceNodeId === targetNodeId) {
      setError('Source and target nodes must be distinct.');
      return;
    }

    setLoading(true);
    setError(null);
    setResult(null);
    setSelectedPathIndex(null);

    try {
      const res = await graphApi.findPaths(caseId, {
        source_node_id: sourceNodeId,
        target_node_id: targetNodeId,
        max_depth: maxDepth,
        max_paths: 10,
        confirmed_only: confirmedOnly,
      });
      setResult(res);
      setLoading(false);
    } catch (err: any) {
      setError(err?.message || 'Failed to search paths between nodes.');
      setLoading(false);
    }
  };

  const handleSelectPath = (path: GraphPath, idx: number) => {
    setSelectedPathIndex(idx);
    onHighlightPath(path);
  };

  const handleClearHighlight = () => {
    setSelectedPathIndex(null);
    onHighlightPath(null);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/75 backdrop-blur-sm select-none">
      <div className="w-full max-w-xl bg-brand-charcoal border border-brand-slate rounded-xl shadow-2xl flex flex-col max-h-[85vh] overflow-hidden text-slate-200 text-xs">
        {/* Header */}
        <div className="p-4 border-b border-brand-slate flex items-center justify-between bg-brand-midnight/60">
          <div className="flex items-center gap-2">
            <GitFork className="w-4 h-4 text-brand-cyan" />
            <h3 className="text-sm font-semibold text-white">Bounded Path Exploration</h3>
          </div>

          <button
            type="button"
            onClick={() => {
              handleClearHighlight();
              onClose();
            }}
            className="p-1 rounded text-brand-slate-light hover:text-white hover:bg-brand-slate/50 transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Query Form */}
        <form onSubmit={handleSearchPaths} className="p-4 border-b border-brand-slate space-y-3 bg-brand-charcoal/60">
          <div className="grid grid-cols-2 gap-3">
            {/* Source Node Selector */}
            <div>
              <label className="block text-[10px] uppercase font-mono text-brand-slate-light font-semibold mb-1">
                Source Node (Origin)
              </label>
              <select
                value={sourceNodeId}
                onChange={(e) => setSourceNodeId(e.target.value)}
                className="w-full bg-brand-midnight border border-brand-slate rounded px-2.5 py-1.5 text-xs text-white focus:outline-none focus:border-brand-cyan font-mono"
              >
                <option value="">Select source node...</option>
                {allNodes.map((n) => (
                  <option key={n.id} value={n.id}>
                    {n.label} ({n.node_type})
                  </option>
                ))}
              </select>
            </div>

            {/* Target Node Selector */}
            <div>
              <label className="block text-[10px] uppercase font-mono text-brand-slate-light font-semibold mb-1">
                Target Node (Destination)
              </label>
              <select
                value={targetNodeId}
                onChange={(e) => setTargetNodeId(e.target.value)}
                className="w-full bg-brand-midnight border border-brand-slate rounded px-2.5 py-1.5 text-xs text-white focus:outline-none focus:border-brand-cyan font-mono"
              >
                <option value="">Select target node...</option>
                {allNodes.map((n) => (
                  <option key={n.id} value={n.id}>
                    {n.label} ({n.node_type})
                  </option>
                ))}
              </select>
            </div>
          </div>

          {/* Options: Max Depth & Confirmed Only */}
          <div className="flex items-center justify-between pt-1">
            <div className="flex items-center gap-4">
              <div className="flex items-center gap-2">
                <span className="text-brand-slate-light text-[11px]">Max Depth:</span>
                <select
                  value={maxDepth}
                  onChange={(e) => setMaxDepth(Number(e.target.value))}
                  className="bg-brand-midnight border border-brand-slate rounded px-2 py-1 text-xs text-white font-mono"
                >
                  {[1, 2, 3, 4, 5, 6].map((d) => (
                    <option key={d} value={d}>
                      {d} hops
                    </option>
                  ))}
                </select>
              </div>

              <label className="inline-flex items-center gap-1.5 text-[11px] text-slate-300 cursor-pointer">
                <input
                  type="checkbox"
                  checked={confirmedOnly}
                  onChange={(e) => setConfirmedOnly(e.target.checked)}
                  className="rounded border-brand-slate bg-brand-midnight text-brand-cyan focus:ring-0"
                />
                <span>Confirmed relationships only</span>
              </label>
            </div>

            <button
              type="submit"
              disabled={loading || !sourceNodeId || !targetNodeId}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-brand-blue hover:bg-brand-blue-hover text-white text-xs font-medium rounded transition-colors disabled:opacity-50"
            >
              {loading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Search className="w-3.5 h-3.5" />}
              <span>Find Paths</span>
            </button>
          </div>

          {error && (
            <div className="p-2 rounded bg-red-500/15 border border-red-500/30 text-rose-300 text-[11px] flex items-center gap-1.5">
              <AlertTriangle className="w-3.5 h-3.5 shrink-0" />
              <span>{error}</span>
            </div>
          )}
        </form>

        {/* Results List */}
        <div className="flex-1 overflow-y-auto p-4 space-y-2.5">
          {result && (
            <div>
              <div className="flex items-center justify-between mb-2">
                <span className="text-[11px] font-mono text-brand-slate-light">
                  Discovered {result.paths.length} directed paths (max depth: {result.max_depth})
                </span>

                {selectedPathIndex !== null && (
                  <button
                    type="button"
                    onClick={handleClearHighlight}
                    className="text-[10px] text-brand-cyan hover:underline"
                  >
                    Clear Path Highlight
                  </button>
                )}
              </div>

              {result.paths.length === 0 ? (
                <div className="p-6 text-center text-slate-400 bg-brand-midnight/40 rounded-lg border border-brand-slate/40">
                  <AlertTriangle className="w-6 h-6 mx-auto mb-1 text-amber-400 opacity-60" />
                  <p className="font-semibold text-white">No Paths Found</p>
                  <p className="text-[11px] text-brand-slate-light mt-0.5">
                    No directed connections exist between these nodes within {maxDepth} hops. The graph may be disconnected or relationships flow in the opposite direction.
                  </p>
                </div>
              ) : (
                <div className="space-y-2">
                  {result.paths.map((p, pIdx) => {
                    const isSelected = selectedPathIndex === pIdx;
                    return (
                      <div
                        key={pIdx}
                        onClick={() => handleSelectPath(p, pIdx)}
                        className={`p-3 rounded-lg border cursor-pointer transition-all ${
                          isSelected
                            ? 'bg-brand-midnight border-amber-400 shadow-[0_0_12px_rgba(251,191,36,0.25)]'
                            : 'bg-brand-midnight/60 border-brand-slate/60 hover:border-brand-slate'
                        }`}
                      >
                        <div className="flex items-center justify-between text-[11px] font-mono text-brand-slate-light mb-2">
                          <span className="font-semibold text-white">Path #{pIdx + 1}</span>
                          <span className="text-amber-300">{p.length} hops</span>
                        </div>

                        {/* Node & Edge Step by Step */}
                        <div className="flex flex-wrap items-center gap-1.5 text-[11px]">
                          {p.nodes.map((node, nIdx) => {
                            const nextEdge = p.edges[nIdx];
                            return (
                              <React.Fragment key={node.id}>
                                <span className="px-1.5 py-0.5 rounded bg-brand-charcoal border border-brand-slate text-white font-medium">
                                  {node.label}
                                </span>
                                {nextEdge && (
                                  <span className="inline-flex items-center gap-0.5 text-brand-cyan font-mono text-[9px]">
                                    <ArrowRight className="w-3 h-3" />
                                    <span>{nextEdge.predicate}</span>
                                    <ArrowRight className="w-3 h-3" />
                                  </span>
                                )}
                              </React.Fragment>
                            );
                          })}
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
