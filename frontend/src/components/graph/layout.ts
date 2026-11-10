import dagre from '@dagrejs/dagre';
import { Position } from '@xyflow/react';
import type { Node, Edge } from '@xyflow/react';
import type { GraphNode, GraphEdge } from '../../types/api';

export const NODE_WIDTH = 240;
export const NODE_HEIGHT = 90;

export interface EvidenceNodeData extends Record<string, unknown> {
  rawNode: GraphNode;
  isPathHighlighted?: boolean;
}

export interface EvidenceEdgeData extends Record<string, unknown> {
  rawEdge: GraphEdge;
  isPathHighlighted?: boolean;
}

/**
 * Apply Dagre hierarchical layout to React Flow nodes and edges.
 */
export function applyDagreLayout(
  nodes: Node<EvidenceNodeData>[],
  edges: Edge<EvidenceEdgeData>[],
  direction: 'LR' | 'TB' = 'LR'
): { nodes: Node<EvidenceNodeData>[]; edges: Edge<EvidenceEdgeData>[] } {
  if (nodes.length === 0) {
    return { nodes: [], edges: [] };
  }

  const g = new dagre.graphlib.Graph();
  g.setGraph({
    rankdir: direction,
    nodesep: 50,
    ranksep: 90,
    marginx: 40,
    marginy: 40,
  });
  g.setDefaultEdgeLabel(() => ({}));

  for (const node of nodes) {
    g.setNode(node.id, { width: NODE_WIDTH, height: NODE_HEIGHT });
  }

  for (const edge of edges) {
    g.setEdge(edge.source, edge.target);
  }

  dagre.layout(g);

  const layoutedNodes: Node<EvidenceNodeData>[] = nodes.map((node) => {
    const nodeWithPos = g.node(node.id);
    return {
      ...node,
      targetPosition: direction === 'LR' ? Position.Left : Position.Top,
      sourcePosition: direction === 'LR' ? Position.Right : Position.Bottom,
      position: {
        x: nodeWithPos ? nodeWithPos.x - NODE_WIDTH / 2 : 0,
        y: nodeWithPos ? nodeWithPos.y - NODE_HEIGHT / 2 : 0,
      },
    };
  });

  return { nodes: layoutedNodes, edges };
}

/**
 * Transform backend GraphNode into React Flow Node.
 */
export function toReactFlowNode(
  node: GraphNode,
  isPathHighlighted = false
): Node<EvidenceNodeData> {
  return {
    id: node.id,
    type: 'evidenceNode',
    position: { x: 0, y: 0 },
    data: {
      rawNode: node,
      isPathHighlighted,
    },
  };
}

/**
 * Transform backend GraphEdge into React Flow Edge.
 */
export function toReactFlowEdge(
  edge: GraphEdge,
  isPathHighlighted = false
): Edge<EvidenceEdgeData> {
  const source = edge.source_node_id || (edge as any).source_id || '';
  const target = edge.target_node_id || (edge as any).target_id || '';
  return {
    id: edge.id,
    source,
    target,
    type: 'evidenceEdge',
    data: {
      rawEdge: edge,
      isPathHighlighted,
    },
  };
}
