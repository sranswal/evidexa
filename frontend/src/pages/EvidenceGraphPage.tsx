import React, { useState, useEffect, useMemo, useCallback } from 'react';
import { useParams, Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import {
  ReactFlow,
  ReactFlowProvider,
  useNodesState,
  useEdgesState,
  useReactFlow,
  Background,
  BackgroundVariant,
  Controls,
  MiniMap,
  Node,
  Edge,
  NodeMouseHandler,
  EdgeMouseHandler,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';

import {
  ChevronLeft,
  Loader2,
  AlertTriangle,
  RefreshCw,
  Network,
} from 'lucide-react';

import { graphApi } from '../api/graph';
import { casesApi } from '../api/cases';
import { EvidenceGraphNode } from '../components/graph/EvidenceGraphNode';
import { EvidenceGraphEdge } from '../components/graph/EvidenceGraphEdge';
import {
  GraphControlsBar,
  GraphFilterState,
} from '../components/graph/GraphControlsBar';
import { GraphDetailsInspector } from '../components/graph/GraphDetailsInspector';
import { PathExplorationPanel } from '../components/graph/PathExplorationPanel';
import {
  applyDagreLayout,
  toReactFlowNode,
  toReactFlowEdge,
  EvidenceNodeData,
  EvidenceEdgeData,
} from '../components/graph/layout';
import type { GraphNode, GraphEdge, GraphPath, GraphNodeType, GraphRelationshipStatus } from '../types/api';

const nodeTypes = {
  evidenceNode: EvidenceGraphNode,
};

const edgeTypes = {
  evidenceEdge: EvidenceGraphEdge,
};

const InnerGraphCanvas: React.FC<{
  caseId: string;
}> = ({ caseId }) => {
  const { fitView } = useReactFlow();

  // Filters State
  const [filters, setFilters] = useState<GraphFilterState>({
    searchQuery: '',
    selectedNodeTypes: new Set<GraphNodeType>(),
    selectedStatuses: new Set<GraphRelationshipStatus>(),
    selectedPredicate: null,
  });

  // Selection & Details State
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [selectedEdgeId, setSelectedEdgeId] = useState<string | null>(null);
  const [inspectorOpen, setInspectorOpen] = useState<boolean>(false);

  // Path Finder State
  const [pathFinderOpen, setPathFinderOpen] = useState<boolean>(false);
  const [pathSourceId, setPathSourceId] = useState<string | null>(null);
  const [pathTargetId, setPathTargetId] = useState<string | null>(null);
  const [highlightedPath, setHighlightedPath] = useState<GraphPath | null>(null);

  // Neighborhood Expansion Loading State
  const [isExpanding, setIsExpanding] = useState<boolean>(false);

  // Local Graph State (allows dynamically merging neighborhood expansions)
  const [graphNodesMap, setGraphNodesMap] = useState<Map<string, GraphNode>>(new Map());
  const [graphEdgesMap, setGraphEdgesMap] = useState<Map<string, GraphEdge>>(new Map());

  // React Flow state
  const [nodes, setNodes, onNodesChange] = useNodesState<Node<EvidenceNodeData>>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge<EvidenceEdgeData>>([]);

  // Fetch Case Data
  const { data: currentCase } = useQuery({
    queryKey: ['case', caseId],
    queryFn: () => casesApi.getCase(caseId),
    enabled: Boolean(caseId),
  });

  // Build query options
  const queryOptions = useMemo(() => {
    return {
      node_types:
        filters.selectedNodeTypes.size > 0 ? Array.from(filters.selectedNodeTypes) : undefined,
      statuses:
        filters.selectedStatuses.size > 0 ? Array.from(filters.selectedStatuses) : undefined,
      limit: 500,
    };
  }, [filters.selectedNodeTypes, filters.selectedStatuses]);

  // Fetch Initial Graph Snapshot
  const {
    data: snapshot,
    isLoading: isGraphLoading,
    error: graphError,
    refetch,
  } = useQuery({
    queryKey: ['caseGraph', caseId, queryOptions],
    queryFn: () => graphApi.getCaseGraph(caseId, queryOptions),
    enabled: Boolean(caseId),
  });

  // Re-layout and synchronize React Flow when map changes
  const synchronizeReactFlow = useCallback(
    (
      nodesMap: Map<string, GraphNode>,
      edgesMap: Map<string, GraphEdge>,
      activePath: GraphPath | null = null
    ) => {
      const pathNodeIds = new Set(activePath?.nodes.map((n) => n.id) || []);
      const pathEdgeIds = new Set(activePath?.edges.map((e) => e.id) || []);

      const rawNodes = Array.from(nodesMap.values());
      const rawEdges = Array.from(edgesMap.values());

      const rfNodes: Node<EvidenceNodeData>[] = rawNodes.map((n) =>
        toReactFlowNode(n, pathNodeIds.has(n.id))
      );
      const rfEdges: Edge<EvidenceEdgeData>[] = rawEdges.map((e) =>
        toReactFlowEdge(e, pathEdgeIds.has(e.id))
      );

      const layouted = applyDagreLayout(rfNodes, rfEdges, 'LR');
      setNodes(layouted.nodes);
      setEdges(layouted.edges);

      // Smooth fit view
      setTimeout(() => {
        fitView({ padding: 0.2, duration: 400 });
      }, 50);
    },
    [fitView, setNodes, setEdges]
  );

  // Initialize from snapshot
  useEffect(() => {
    if (snapshot) {
      const newNodesMap = new Map<string, GraphNode>();
      const newEdgesMap = new Map<string, GraphEdge>();

      for (const n of snapshot.nodes) {
        newNodesMap.set(n.id, n);
      }
      for (const e of snapshot.edges) {
        newEdgesMap.set(e.id, e);
      }

      setGraphNodesMap(newNodesMap);
      setGraphEdgesMap(newEdgesMap);
      synchronizeReactFlow(newNodesMap, newEdgesMap, highlightedPath);
    }
  }, [snapshot, synchronizeReactFlow, highlightedPath]);

  // Handle Neighborhood Expansion
  const handleExpandNeighborhood = async (nodeId: string) => {
    setIsExpanding(true);
    try {
      const res = await graphApi.getNeighborhood(caseId, nodeId, { max_hops: 2, limit: 150 });

      setGraphNodesMap((prev) => {
        const next = new Map(prev);
        for (const n of res.nodes) {
          next.set(n.id, n);
        }
        return next;
      });

      setGraphEdgesMap((prev) => {
        const next = new Map(prev);
        for (const e of res.edges) {
          next.set(e.id, e);
        }
        return next;
      });

      // Synchronize with updated maps
      const updatedNodes = new Map(graphNodesMap);
      for (const n of res.nodes) updatedNodes.set(n.id, n);
      const updatedEdges = new Map(graphEdgesMap);
      for (const e of res.edges) updatedEdges.set(e.id, e);

      synchronizeReactFlow(updatedNodes, updatedEdges, highlightedPath);
      setIsExpanding(false);
    } catch (err) {
      console.error('Failed to expand neighborhood:', err);
      setIsExpanding(false);
    }
  };

  // Node Click
  const onNodeClick: NodeMouseHandler = (_, node) => {
    setSelectedNodeId(node.id);
    setSelectedEdgeId(null);
    setInspectorOpen(true);
  };

  // Edge Click
  const onEdgeClick: EdgeMouseHandler = (_, edge) => {
    setSelectedEdgeId(edge.id);
    setSelectedNodeId(null);
    setInspectorOpen(true);
  };

  // Canvas Click (Deselect)
  const onPaneClick = () => {
    setSelectedNodeId(null);
    setSelectedEdgeId(null);
  };

  // Selected entities for Inspector
  const selectedNode = selectedNodeId ? graphNodesMap.get(selectedNodeId) || null : null;
  const selectedEdge = selectedEdgeId ? graphEdgesMap.get(selectedEdgeId) || null : null;

  const rawNodesList = useMemo(() => Array.from(graphNodesMap.values()), [graphNodesMap]);

  return (
    <div className="flex flex-col h-[calc(100vh-4rem)] bg-brand-midnight text-white overflow-hidden relative">
      {/* Top Breadcrumbs Header */}
      <div className="flex items-center justify-between px-4 py-2 bg-brand-charcoal border-b border-brand-slate text-xs shrink-0">
        <div className="flex items-center gap-2">
          <Link
            to={`/cases/${caseId}/overview`}
            className="inline-flex items-center gap-1 text-brand-slate-light hover:text-brand-cyan transition-colors"
          >
            <ChevronLeft className="w-3.5 h-3.5" />
            <span>{currentCase?.case_reference || 'Case Overview'}</span>
          </Link>
          <span className="text-brand-slate-light">/</span>
          <span className="font-semibold text-white flex items-center gap-1.5">
            <Network className="w-3.5 h-3.5 text-brand-cyan" />
            <span>Evidence Graph Canvas</span>
          </span>
        </div>

        <div className="text-[11px] font-mono text-brand-slate-light">
          Projection: Unified Deterministic v1.0
        </div>
      </div>

      {/* Controls Bar */}
      <GraphControlsBar
        nodes={rawNodesList}
        filters={filters}
        onFiltersChange={(f) => setFilters(f)}
        onFitView={() => fitView({ padding: 0.2, duration: 400 })}
        onReLayout={() => synchronizeReactFlow(graphNodesMap, graphEdgesMap, highlightedPath)}
        onOpenPathFinder={() => setPathFinderOpen(true)}
        onSelectNode={(nodeId) => {
          setSelectedNodeId(nodeId);
          setSelectedEdgeId(null);
          setInspectorOpen(true);
          // Highlight and center node
          const target = nodes.find((n) => n.id === nodeId);
          if (target) {
            fitView({
              nodes: [target],
              duration: 500,
              padding: 1.5,
            });
          }
        }}
        isTruncated={snapshot?.truncated}
        totalNodesCount={rawNodesList.length}
        totalEdgesCount={graphEdgesMap.size}
      />

      {/* Main Graph Area */}
      <div className="flex-1 flex overflow-hidden relative">
        {/* Canvas */}
        <div className="flex-1 h-full bg-brand-midnight relative">
          {isGraphLoading && (
            <div className="absolute inset-0 z-30 flex flex-col items-center justify-center bg-brand-midnight/80 backdrop-blur-sm gap-3 text-slate-400">
              <Loader2 className="w-8 h-8 animate-spin text-brand-cyan" />
              <p className="text-sm font-mono">Projecting case evidence graph...</p>
            </div>
          )}

          {graphError && (
            <div className="absolute inset-0 z-30 flex flex-col items-center justify-center bg-brand-midnight/90 p-6 text-center">
              <AlertTriangle className="w-8 h-8 text-red-400 mb-2" />
              <h4 className="text-base font-semibold text-white mb-1">Failed to Project Graph</h4>
              <p className="text-xs text-slate-400 mb-4 font-mono">
                {(graphError as any)?.message || 'An error occurred loading the Evidence Graph.'}
              </p>
              <button
                type="button"
                onClick={() => refetch()}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-brand-blue hover:bg-brand-blue-hover text-white text-xs font-medium rounded transition-colors"
              >
                <RefreshCw className="w-3.5 h-3.5" />
                <span>Retry Query</span>
              </button>
            </div>
          )}

          {!isGraphLoading && !graphError && rawNodesList.length === 0 && (
            <div className="absolute inset-0 z-20 flex flex-col items-center justify-center p-6 text-center select-none pointer-events-none">
              <div className="w-12 h-12 rounded-full bg-brand-charcoal border border-brand-slate flex items-center justify-center mb-3 text-brand-slate-light">
                <Network className="w-6 h-6 text-brand-cyan opacity-60" />
              </div>
              <h4 className="text-sm font-semibold text-white mb-1">No Evidence Graph Projected</h4>
              <p className="text-xs text-brand-slate-light max-w-sm">
                No documents, entities, or forensic findings have been registered in this case yet. Ingest documents and run forensic pipelines to populate the graph.
              </p>
            </div>
          )}

          <ReactFlow
            nodes={nodes}
            edges={edges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onNodeClick={onNodeClick}
            onEdgeClick={onEdgeClick}
            onPaneClick={onPaneClick}
            nodeTypes={nodeTypes}
            edgeTypes={edgeTypes}
            minZoom={0.15}
            maxZoom={2.5}
            defaultViewport={{ x: 0, y: 0, zoom: 0.85 }}
            proOptions={{ hideAttribution: true }}
            className="bg-brand-midnight"
          >
            <Background
              variant={BackgroundVariant.Dots}
              gap={24}
              size={1.5}
              color="#2E3856"
              className="bg-brand-midnight"
            />
            <Controls className="!bg-brand-charcoal !border !border-brand-slate !rounded-lg !shadow-xl [&>button]:!bg-brand-charcoal [&>button]:!border-b [&>button]:!border-brand-slate [&>button]:!text-slate-300 [&>button:hover]:!text-brand-cyan" />
            <MiniMap
              nodeColor={() => '#00E5FF'}
              maskColor="rgba(11, 19, 43, 0.85)"
              className="!bg-brand-charcoal !border !border-brand-slate !rounded-lg !overflow-hidden !shadow-2xl"
              pannable
              zoomable
            />
          </ReactFlow>
        </div>

        {/* Right Details Inspector */}
        {inspectorOpen && (selectedNode || selectedEdge) && (
          <GraphDetailsInspector
            selectedNode={selectedNode}
            selectedEdge={selectedEdge}
            allNodes={rawNodesList}
            caseId={caseId}
            onClose={() => setInspectorOpen(false)}
            onSelectNode={(id) => {
              setSelectedNodeId(id);
              setSelectedEdgeId(null);
            }}
            onSelectEdge={(id) => {
              setSelectedEdgeId(id);
              setSelectedNodeId(null);
            }}
            onExpandNeighborhood={handleExpandNeighborhood}
            onSetPathSource={(id) => {
              setPathSourceId(id);
              setPathFinderOpen(true);
            }}
            onSetPathTarget={(id) => {
              setPathTargetId(id);
              setPathFinderOpen(true);
            }}
            isExpanding={isExpanding}
          />
        )}
      </div>

      {/* Path Exploration Modal */}
      <PathExplorationPanel
        isOpen={pathFinderOpen}
        onClose={() => setPathFinderOpen(false)}
        caseId={caseId}
        allNodes={rawNodesList}
        initialSourceId={pathSourceId}
        initialTargetId={pathTargetId}
        onHighlightPath={(path) => {
          setHighlightedPath(path);
          synchronizeReactFlow(graphNodesMap, graphEdgesMap, path);
        }}
      />
    </div>
  );
};

export const EvidenceGraphPage: React.FC = () => {
  const { caseId } = useParams<{ caseId: string }>();

  if (!caseId) {
    return (
      <div className="p-8 text-center text-slate-400">
        <p>No active case identifier provided.</p>
      </div>
    );
  }

  return (
    <ReactFlowProvider>
      <InnerGraphCanvas caseId={caseId} />
    </ReactFlowProvider>
  );
};
