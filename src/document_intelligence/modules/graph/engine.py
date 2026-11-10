"""Evidence Graph traversal and query engine.

Provides bounded, cycle-safe, deterministic graph querying, neighborhood exploration,
and pathfinding over projected investigation records.
"""

from __future__ import annotations

from collections import deque

from document_intelligence.domain.enums import GraphNodeType
from document_intelligence.domain.models.graph import (
    GraphEdge,
    GraphNeighborhoodResult,
    GraphNode,
    GraphPath,
    GraphPathsResult,
    GraphSnapshot,
)
from document_intelligence.modules.graph.projector import ProjectedGraphData

# Hard system safety limits to prevent memory exhaustion and runaway recursion
DEFAULT_MAX_NODES_LIMIT = 500
HARD_MAX_NODES_LIMIT = 2000
DEFAULT_MAX_HOPS = 2
HARD_MAX_HOPS = 5
DEFAULT_MAX_PATH_DEPTH = 4
HARD_MAX_PATH_DEPTH = 6
DEFAULT_MAX_PATHS = 10
HARD_MAX_PATHS = 50


class EvidenceGraphEngine:
    """Executes deterministic, bounded queries and traversals on projected graph data."""

    def query_graph(
        self,
        graph: ProjectedGraphData,
        node_types: set[GraphNodeType] | None = None,
        relationship_types: set[str] | None = None,
        statuses: set[str] | None = None,
        document_ids: set[str] | None = None,
        limit: int = DEFAULT_MAX_NODES_LIMIT,
        offset: int = 0,
    ) -> GraphSnapshot:
        """Filter and paginate the case graph with explicit truncation indicators."""
        effective_limit = min(max(1, limit), HARD_MAX_NODES_LIMIT)

        # 1. Filter nodes
        candidate_nodes: list[GraphNode] = []
        for node in graph.nodes.values():
            if node_types and node.node_type not in node_types:
                continue

            if document_ids:
                doc_provenance = node.provenance.get("document_id")
                source_id = node.source_entity_id
                affected_docs = node.provenance.get("affected_document_ids", [])

                matches_doc = (
                    (doc_provenance in document_ids)
                    or (source_id in document_ids and node.node_type == GraphNodeType.DOCUMENT)
                    or any(ad in document_ids for ad in affected_docs)
                )
                if not matches_doc and node.node_type != GraphNodeType.CASE:
                    continue

            candidate_nodes.append(node)

        # Deterministic sort by node ID
        candidate_nodes.sort(key=lambda n: n.id)
        total_matching_nodes = len(candidate_nodes)

        paginated_nodes = candidate_nodes[offset : offset + effective_limit]
        truncated = (offset + effective_limit) < total_matching_nodes
        included_node_ids = {n.id for n in paginated_nodes}

        # 2. Filter edges connecting the included nodes
        filtered_edges: list[GraphEdge] = []
        for edge in graph.edges.values():
            if (
                edge.source_node_id not in included_node_ids
                or edge.target_node_id not in included_node_ids
            ):
                continue

            if relationship_types and edge.predicate not in relationship_types:
                continue

            if statuses and edge.status not in statuses:
                continue

            filtered_edges.append(edge)

        # Deterministic sort by edge ID
        filtered_edges.sort(key=lambda e: e.id)

        return GraphSnapshot(
            case_id=graph.case_id,
            nodes=paginated_nodes,
            edges=filtered_edges,
            total_nodes=total_matching_nodes,
            total_edges=len(filtered_edges),
            truncated=truncated,
            query_metadata={
                "limit": effective_limit,
                "offset": offset,
                "node_types": [nt.value for nt in node_types] if node_types else None,
                "relationship_types": list(relationship_types) if relationship_types else None,
                "statuses": list(statuses) if statuses else None,
                "document_ids": list(document_ids) if document_ids else None,
            },
        )

    def get_neighborhood(
        self,
        graph: ProjectedGraphData,
        center_node_id: str,
        max_hops: int = DEFAULT_MAX_HOPS,
        limit: int = 200,
        relationship_types: set[str] | None = None,
        statuses: set[str] | None = None,
    ) -> GraphNeighborhoodResult:
        """Perform a cycle-safe, bounded BFS expansion around a seed node."""
        if center_node_id not in graph.nodes:
            return GraphNeighborhoodResult(
                case_id=graph.case_id,
                center_node_id=center_node_id,
                hops=max_hops,
                nodes=[],
                edges=[],
                total_nodes=0,
                total_edges=0,
                truncated=False,
            )

        effective_hops = min(max(1, max_hops), HARD_MAX_HOPS)
        effective_limit = min(max(1, limit), HARD_MAX_NODES_LIMIT)

        visited_nodes: set[str] = {center_node_id}
        collected_edges: dict[str, GraphEdge] = {}
        queue: deque[tuple[str, int]] = deque([(center_node_id, 0)])

        truncated = False

        while queue:
            current_node_id, current_hop = queue.popleft()
            if current_hop >= effective_hops:
                continue

            # Gather all incident edge IDs (both outgoing and incoming for true neighborhood)
            outgoing_ids = graph.outgoing_edges.get(current_node_id, [])
            incoming_ids = graph.incoming_edges.get(current_node_id, [])
            incident_edge_ids = sorted(set(outgoing_ids + incoming_ids))

            for edge_id in incident_edge_ids:
                edge = graph.edges.get(edge_id)
                if not edge:
                    continue

                if relationship_types and edge.predicate not in relationship_types:
                    continue

                if statuses and edge.status not in statuses:
                    continue

                # Identify neighboring node
                neighbor_id = (
                    edge.target_node_id
                    if edge.source_node_id == current_node_id
                    else edge.source_node_id
                )

                collected_edges[edge.id] = edge

                if neighbor_id not in visited_nodes:
                    if len(visited_nodes) >= effective_limit:
                        truncated = True
                        break
                    visited_nodes.add(neighbor_id)
                    queue.append((neighbor_id, current_hop + 1))

            if truncated:
                break

        # Collect and sort nodes and edges deterministically
        result_nodes = [graph.nodes[nid] for nid in visited_nodes if nid in graph.nodes]
        result_nodes.sort(key=lambda n: n.id)

        result_edges = list(collected_edges.values())
        result_edges.sort(key=lambda e: e.id)

        return GraphNeighborhoodResult(
            case_id=graph.case_id,
            center_node_id=center_node_id,
            hops=effective_hops,
            nodes=result_nodes,
            edges=result_edges,
            total_nodes=len(result_nodes),
            total_edges=len(result_edges),
            truncated=truncated,
        )

    def find_paths(
        self,
        graph: ProjectedGraphData,
        source_node_id: str,
        target_node_id: str,
        max_depth: int = DEFAULT_MAX_PATH_DEPTH,
        max_paths: int = DEFAULT_MAX_PATHS,
        confirmed_only: bool = False,
        relationship_types: set[str] | None = None,
    ) -> GraphPathsResult:
        """Find directed paths between two nodes with cycle prevention and depth limits."""
        if source_node_id not in graph.nodes or target_node_id not in graph.nodes:
            return GraphPathsResult(
                case_id=graph.case_id,
                source_node_id=source_node_id,
                target_node_id=target_node_id,
                max_depth=max_depth,
                paths=[],
                total_paths_found=0,
                truncated=False,
            )

        effective_depth = min(max(1, max_depth), HARD_MAX_PATH_DEPTH)
        effective_max_paths = min(max(1, max_paths), HARD_MAX_PATHS)

        # BFS queue storing: (current_node_id, [visited_node_ids], [edge_ids])
        queue: deque[tuple[str, list[str], list[str]]] = deque(
            [(source_node_id, [source_node_id], [])]
        )

        found_paths: list[GraphPath] = []
        truncated = False

        while queue:
            current_node_id, path_node_ids, path_edge_ids = queue.popleft()

            if current_node_id == target_node_id and path_edge_ids:
                # Reconstruct path domain model
                path_nodes = [graph.nodes[nid] for nid in path_node_ids]
                path_edges = [graph.edges[eid] for eid in path_edge_ids]
                is_conf_only = all(e.status == "CONFIRMED" for e in path_edges)

                found_paths.append(
                    GraphPath(
                        nodes=path_nodes,
                        edges=path_edges,
                        length=len(path_edges),
                        is_confirmed_only=is_conf_only,
                    )
                )

                if len(found_paths) >= effective_max_paths:
                    truncated = True
                    break
                continue

            if len(path_edge_ids) >= effective_depth:
                continue

            # Traverse outgoing directed edges (preserving canonical direction)
            outgoing_edge_ids = sorted(graph.outgoing_edges.get(current_node_id, []))
            for edge_id in outgoing_edge_ids:
                edge = graph.edges.get(edge_id)
                if not edge:
                    continue

                if confirmed_only and edge.status != "CONFIRMED":
                    continue

                if relationship_types and edge.predicate not in relationship_types:
                    continue

                next_node_id = edge.target_node_id

                # Cycle prevention: do not revisit any node already in the current path
                if next_node_id in path_node_ids:
                    continue

                queue.append(
                    (
                        next_node_id,
                        [*path_node_ids, next_node_id],
                        [*path_edge_ids, edge_id],
                    )
                )

        # Deterministic sorting: shortest path first, then by node IDs
        found_paths.sort(key=lambda p: (p.length, [n.id for n in p.nodes]))

        return GraphPathsResult(
            case_id=graph.case_id,
            source_node_id=source_node_id,
            target_node_id=target_node_id,
            max_depth=effective_depth,
            paths=found_paths,
            total_paths_found=len(found_paths),
            truncated=truncated,
        )
