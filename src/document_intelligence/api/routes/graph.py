"""REST API routes for the unified investigation Evidence Graph."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query, status

from document_intelligence.api.dependencies import (
    get_evidence_graph_service,
    require_case_access,
)
from document_intelligence.domain.enums import GraphNodeType
from document_intelligence.domain.models.auth import CaseRole
from document_intelligence.domain.models.graph import (
    GraphNeighborhoodResult,
    GraphPathsResult,
    GraphSnapshot,
)
from document_intelligence.modules.graph.service import EvidenceGraphService

router = APIRouter(
    prefix="/cases/{case_id}/graph",
    tags=["Unified Evidence Graph"],
)


@router.get(
    "",
    response_model=GraphSnapshot,
    status_code=status.HTTP_200_OK,
    summary="Retrieve unified Evidence Graph for a case",
    description="Projects existing relational case documents, evidence, forensic findings, consistency findings, relationships, and entity matches as a unified, bounded graph.",
)
def get_case_graph(
    case_id: str,
    node_types: list[str] | None = Query(
        None,
        description="Filter by node types (e.g. DOCUMENT, EVIDENCE, FORENSIC_FINDING, CONSISTENCY_FINDING, ORGANIZATION, INVOICE)",
    ),
    relationship_types: list[str] | None = Query(
        None,
        description="Filter by relationship predicates (e.g. ISSUED, INVOICED, HAS_EVIDENCE, SUPPORTED_BY)",
    ),
    statuses: list[str] | None = Query(
        None,
        description="Filter by evidentiary statuses (e.g. CONFIRMED, CANDIDATE, CONTRADICTED, UNRESOLVED, REJECTED)",
    ),
    document_ids: list[str] | None = Query(
        None, description="Filter nodes and connections pertaining to specific document IDs"
    ),
    limit: int = Query(
        500,
        ge=1,
        le=2000,
        description="Maximum number of graph nodes to return (default: 500, max: 2000)",
    ),
    offset: int = Query(0, ge=0, description="Offset for node pagination"),
    _: CaseRole = Depends(require_case_access(min_role=CaseRole.VIEWER)),
    graph_service: EvidenceGraphService = Depends(get_evidence_graph_service),
) -> GraphSnapshot:
    """Execute bounded query over projected case Evidence Graph."""
    parsed_node_types: set[GraphNodeType] | None = None
    if node_types:
        parsed_node_types = set()
        for nt in node_types:
            try:
                parsed_node_types.add(GraphNodeType(nt.upper()))
            except ValueError:
                pass

    parsed_rel_types = set(relationship_types) if relationship_types else None
    parsed_statuses = set(statuses) if statuses else None
    parsed_doc_ids = set(document_ids) if document_ids else None

    return graph_service.get_case_graph(
        case_id=case_id,
        node_types=parsed_node_types,
        relationship_types=parsed_rel_types,
        statuses=parsed_statuses,
        document_ids=parsed_doc_ids,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/nodes/{node_id}",
    response_model=dict[str, Any],
    status_code=status.HTTP_200_OK,
    summary="Retrieve graph node details and incident edges",
    description="Retrieves a specific graph node along with its incoming and outgoing edges and degree.",
)
def get_graph_node(
    case_id: str,
    node_id: str,
    _: CaseRole = Depends(require_case_access(min_role=CaseRole.VIEWER)),
    graph_service: EvidenceGraphService = Depends(get_evidence_graph_service),
) -> dict[str, Any]:
    """Retrieve single node with incident edges."""
    return graph_service.get_node(case_id=case_id, node_id=node_id)


@router.get(
    "/nodes/{node_id}/neighbors",
    response_model=GraphNeighborhoodResult,
    status_code=status.HTTP_200_OK,
    summary="Retrieve bounded k-hop graph neighborhood",
    description="Performs cycle-safe BFS traversal around a seed node up to max_hops.",
)
def get_graph_neighborhood(
    case_id: str,
    node_id: str,
    max_hops: int = Query(
        2,
        ge=1,
        le=5,
        description="Maximum traversal depth (hops) from the center node (default: 2, max: 5)",
    ),
    limit: int = Query(
        200, ge=1, le=1000, description="Maximum total nodes to return in neighborhood"
    ),
    relationship_types: list[str] | None = Query(None, description="Filter traversed edge types"),
    statuses: list[str] | None = Query(None, description="Filter traversed edge statuses"),
    _: CaseRole = Depends(require_case_access(min_role=CaseRole.VIEWER)),
    graph_service: EvidenceGraphService = Depends(get_evidence_graph_service),
) -> GraphNeighborhoodResult:
    """Retrieve neighborhood subgraph around a target node."""
    parsed_rel_types = set(relationship_types) if relationship_types else None
    parsed_statuses = set(statuses) if statuses else None

    return graph_service.get_neighborhood(
        case_id=case_id,
        node_id=node_id,
        max_hops=max_hops,
        limit=limit,
        relationship_types=parsed_rel_types,
        statuses=parsed_statuses,
    )


@router.get(
    "/paths",
    response_model=GraphPathsResult,
    status_code=status.HTTP_200_OK,
    summary="Find directed paths between two nodes",
    description="Finds bounded directed evidentiary paths between a source and target node, preventing cycles.",
)
def find_graph_paths(
    case_id: str,
    source_node_id: str = Query(..., description="Starting node ID"),
    target_node_id: str = Query(..., description="Destination node ID"),
    max_depth: int = Query(
        4, ge=1, le=6, description="Maximum path depth (edge count) (default: 4, max: 6)"
    ),
    max_paths: int = Query(
        10, ge=1, le=50, description="Maximum number of distinct paths to discover"
    ),
    confirmed_only: bool = Query(
        False, description="When true, only traverse edges with status=CONFIRMED"
    ),
    relationship_types: list[str] | None = Query(
        None, description="Filter allowed edge predicates in path traversal"
    ),
    _: CaseRole = Depends(require_case_access(min_role=CaseRole.VIEWER)),
    graph_service: EvidenceGraphService = Depends(get_evidence_graph_service),
) -> GraphPathsResult:
    """Find directed paths between two graph nodes."""
    parsed_rel_types = set(relationship_types) if relationship_types else None

    return graph_service.find_paths(
        case_id=case_id,
        source_node_id=source_node_id,
        target_node_id=target_node_id,
        max_depth=max_depth,
        max_paths=max_paths,
        confirmed_only=confirmed_only,
        relationship_types=parsed_rel_types,
    )
