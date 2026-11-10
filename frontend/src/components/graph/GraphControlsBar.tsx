import React, { useState } from 'react';
import {
  Search,
  Filter,
  Maximize2,
  RotateCw,
  GitFork,
  AlertCircle,
  X,
  Layers,
  ChevronDown,
} from 'lucide-react';
import type { GraphNode, GraphNodeType, GraphRelationshipStatus } from '../../types/api';

export interface GraphFilterState {
  searchQuery: string;
  selectedNodeTypes: Set<GraphNodeType>;
  selectedStatuses: Set<GraphRelationshipStatus>;
  selectedPredicate: string | null;
}

interface GraphControlsBarProps {
  nodes: GraphNode[];
  filters: GraphFilterState;
  onFiltersChange: (filters: GraphFilterState) => void;
  onFitView: () => void;
  onReLayout: () => void;
  onOpenPathFinder: () => void;
  onSelectNode: (nodeId: string) => void;
  isTruncated?: boolean;
  totalNodesCount?: number;
  totalEdgesCount?: number;
}

const ALL_NODE_TYPES: GraphNodeType[] = [
  'DOCUMENT',
  'EVIDENCE',
  'FORENSIC_FINDING',
  'CONSISTENCY_FINDING',
  'ORGANIZATION',
  'PERSON',
  'ACCOUNT',
  'INVOICE',
  'RECEIPT',
  'PURCHASE_ORDER',
  'BANK_TRANSACTION',
];

const ALL_STATUSES: GraphRelationshipStatus[] = [
  'CONFIRMED',
  'CANDIDATE',
  'CONTRADICTED',
  'UNRESOLVED',
  'REJECTED',
];

export const GraphControlsBar: React.FC<GraphControlsBarProps> = ({
  nodes,
  filters,
  onFiltersChange,
  onFitView,
  onReLayout,
  onOpenPathFinder,
  onSelectNode,
  isTruncated = false,
  totalNodesCount = 0,
  totalEdgesCount = 0,
}) => {
  const [filterMenuOpen, setFilterMenuOpen] = useState(false);
  const [searchResultsOpen, setSearchResultsOpen] = useState(false);

  // Search matches
  const searchMatches = React.useMemo(() => {
    if (!filters.searchQuery.trim()) return [];
    const q = filters.searchQuery.toLowerCase();
    return nodes
      .filter((n) => n.label.toLowerCase().includes(q) || n.id.toLowerCase().includes(q))
      .slice(0, 8);
  }, [nodes, filters.searchQuery]);

  const toggleNodeType = (type: GraphNodeType) => {
    const next = new Set(filters.selectedNodeTypes);
    if (next.has(type)) {
      next.delete(type);
    } else {
      next.add(type);
    }
    onFiltersChange({ ...filters, selectedNodeTypes: next });
  };

  const toggleStatus = (status: GraphRelationshipStatus) => {
    const next = new Set(filters.selectedStatuses);
    if (next.has(status)) {
      next.delete(status);
    } else {
      next.add(status);
    }
    onFiltersChange({ ...filters, selectedStatuses: next });
  };

  const clearAllFilters = () => {
    onFiltersChange({
      searchQuery: '',
      selectedNodeTypes: new Set(),
      selectedStatuses: new Set(),
      selectedPredicate: null,
    });
  };

  const hasActiveFilters =
    Boolean(filters.searchQuery) ||
    filters.selectedNodeTypes.size > 0 ||
    filters.selectedStatuses.size > 0 ||
    Boolean(filters.selectedPredicate);

  return (
    <div className="flex flex-wrap items-center justify-between gap-3 px-4 py-2.5 bg-brand-charcoal border-b border-brand-slate text-sm select-none z-20">
      {/* Left: Search & Node Autocomplete */}
      <div className="flex items-center gap-2 relative">
        <div className="relative">
          <Search className="w-3.5 h-3.5 absolute left-2.5 top-1/2 -translate-y-1/2 text-brand-slate-light" />
          <input
            type="text"
            value={filters.searchQuery}
            onChange={(e) => {
              onFiltersChange({ ...filters, searchQuery: e.target.value });
              setSearchResultsOpen(true);
            }}
            onFocus={() => setSearchResultsOpen(true)}
            placeholder="Search nodes in graph..."
            className="w-56 md:w-64 bg-brand-midnight border border-brand-slate rounded pl-8 pr-7 py-1.5 text-xs text-white placeholder-brand-slate-light focus:outline-none focus:border-brand-cyan font-sans"
          />
          {filters.searchQuery && (
            <button
              type="button"
              onClick={() => {
                onFiltersChange({ ...filters, searchQuery: '' });
                setSearchResultsOpen(false);
              }}
              className="absolute right-2 top-1/2 -translate-y-1/2 text-brand-slate-light hover:text-white"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          )}
        </div>

        {/* Autocomplete Dropdown */}
        {searchResultsOpen && searchMatches.length > 0 && (
          <div className="absolute left-0 top-full mt-1 w-72 bg-brand-charcoal border border-brand-slate rounded-lg shadow-2xl py-1 z-50 text-xs">
            <div className="px-2.5 py-1 text-[10px] uppercase font-mono text-brand-slate-light border-b border-brand-slate/40">
              Matching Graph Nodes ({searchMatches.length})
            </div>
            {searchMatches.map((n) => (
              <button
                key={n.id}
                type="button"
                onClick={() => {
                  onSelectNode(n.id);
                  setSearchResultsOpen(false);
                }}
                className="w-full text-left px-3 py-1.5 hover:bg-brand-midnight flex items-center justify-between gap-2 transition-colors"
              >
                <div className="min-w-0">
                  <div className="text-white truncate font-medium">{n.label}</div>
                  <div className="text-[10px] text-brand-slate-light font-mono truncate">
                    {n.node_type} • #{n.source_entity_id.slice(-6)}
                  </div>
                </div>
              </button>
            ))}
          </div>
        )}

        {/* Filter Dropdown Toggle */}
        <div className="relative">
          <button
            type="button"
            onClick={() => setFilterMenuOpen(!filterMenuOpen)}
            className={`inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded border text-xs font-medium transition-colors ${
              hasActiveFilters
                ? 'bg-brand-cyan/20 border-brand-cyan text-brand-cyan'
                : 'bg-brand-midnight border-brand-slate text-brand-slate-light hover:text-white'
            }`}
          >
            <Filter className="w-3.5 h-3.5" />
            <span>Filters</span>
            {hasActiveFilters && (
              <span className="w-1.5 h-1.5 rounded-full bg-brand-cyan" />
            )}
            <ChevronDown className="w-3 h-3 ml-0.5" />
          </button>

          {/* Filter Popover Panel */}
          {filterMenuOpen && (
            <div className="absolute left-0 top-full mt-1.5 w-80 bg-brand-charcoal border border-brand-slate rounded-lg shadow-2xl p-3 z-50 text-xs space-y-3">
              <div className="flex items-center justify-between pb-1.5 border-b border-brand-slate">
                <span className="font-semibold text-white">Graph Filters</span>
                {hasActiveFilters && (
                  <button
                    type="button"
                    onClick={clearAllFilters}
                    className="text-[10px] text-brand-cyan hover:underline"
                  >
                    Reset All
                  </button>
                )}
              </div>

              {/* Node Types Filter */}
              <div>
                <span className="text-[10px] uppercase font-mono text-brand-slate-light font-semibold block mb-1.5">
                  Node Types
                </span>
                <div className="flex flex-wrap gap-1 max-h-36 overflow-y-auto">
                  {ALL_NODE_TYPES.map((t) => {
                    const isSelected = filters.selectedNodeTypes.has(t);
                    return (
                      <button
                        key={t}
                        type="button"
                        onClick={() => toggleNodeType(t)}
                        className={`px-2 py-0.5 rounded text-[10px] font-mono border transition-colors ${
                          isSelected
                            ? 'bg-brand-cyan/25 border-brand-cyan text-brand-cyan font-bold'
                            : 'bg-brand-midnight border-brand-slate text-slate-300 hover:text-white'
                        }`}
                      >
                        {t.replace('_', ' ')}
                      </button>
                    );
                  })}
                </div>
              </div>

              {/* Status Filter */}
              <div>
                <span className="text-[10px] uppercase font-mono text-brand-slate-light font-semibold block mb-1.5">
                  Evidentiary Status
                </span>
                <div className="flex flex-wrap gap-1">
                  {ALL_STATUSES.map((s) => {
                    const isSelected = filters.selectedStatuses.has(s);
                    return (
                      <button
                        key={s}
                        type="button"
                        onClick={() => toggleStatus(s)}
                        className={`px-2 py-0.5 rounded text-[10px] font-mono border transition-colors ${
                          isSelected
                            ? 'bg-brand-cyan/25 border-brand-cyan text-brand-cyan font-bold'
                            : 'bg-brand-midnight border-brand-slate text-slate-300 hover:text-white'
                        }`}
                      >
                        {s}
                      </button>
                    );
                  })}
                </div>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Middle: Graph Totals & Truncation Warnings */}
      <div className="flex items-center gap-2 text-xs font-mono text-brand-slate-light">
        <span className="flex items-center gap-1">
          <Layers className="w-3.5 h-3.5 text-brand-cyan" />
          <span className="text-white font-semibold">{totalNodesCount}</span> nodes,
          <span className="text-white font-semibold">{totalEdgesCount}</span> edges
        </span>

        {isTruncated && (
          <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded bg-amber-500/15 border border-amber-500/30 text-amber-300 text-[10px]">
            <AlertCircle className="w-3 h-3" />
            <span>Truncated at Limit</span>
          </span>
        )}
      </div>

      {/* Right: Graph Canvas Actions */}
      <div className="flex items-center gap-1.5">
        {/* Path Exploration Action */}
        <button
          type="button"
          onClick={onOpenPathFinder}
          className="inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded bg-brand-midnight hover:bg-brand-slate/40 border border-brand-slate text-slate-300 hover:text-white text-xs font-medium transition-colors"
          title="Find directed evidentiary paths between two nodes"
        >
          <GitFork className="w-3.5 h-3.5 text-brand-cyan" />
          <span>Explore Paths</span>
        </button>

        <div className="h-4 w-px bg-brand-slate mx-0.5" />

        {/* Re-Layout Button */}
        <button
          type="button"
          onClick={onReLayout}
          className="p-1.5 rounded text-brand-slate-light hover:text-white hover:bg-brand-slate/40 transition-colors"
          title="Re-run hierarchical Dagre layout"
        >
          <RotateCw className="w-4 h-4" />
        </button>

        {/* Fit to View Button */}
        <button
          type="button"
          onClick={onFitView}
          className="p-1.5 rounded text-brand-slate-light hover:text-white hover:bg-brand-slate/40 transition-colors"
          title="Fit graph to view"
        >
          <Maximize2 className="w-4 h-4" />
        </button>
      </div>
    </div>
  );
};

