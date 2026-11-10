"""Application service for the unified investigation Evidence Graph."""

from __future__ import annotations

from typing import Any

from document_intelligence.core.exceptions import EntityNotFoundException
from document_intelligence.domain.enums import GraphNodeType
from document_intelligence.domain.models.graph import (
    GraphNeighborhoodResult,
    GraphPathsResult,
    GraphSnapshot,
)
from document_intelligence.infrastructure.repositories.case_repository import CaseRepository
from document_intelligence.infrastructure.repositories.consistency_repository import (
    ConsistencyRepository,
)
from document_intelligence.infrastructure.repositories.document_repository import (
    DocumentRepository,
)
from document_intelligence.infrastructure.repositories.entity_match_repository import (
    EntityMatchRepository,
)
from document_intelligence.infrastructure.repositories.evidence_repository import (
    EvidenceRepository,
)
from document_intelligence.infrastructure.repositories.finding_repository import (
    FindingRepository,
)
from document_intelligence.infrastructure.repositories.relationship_repository import (
    RelationshipRepository,
)
from document_intelligence.modules.graph.engine import (
    DEFAULT_MAX_HOPS,
    DEFAULT_MAX_NODES_LIMIT,
    DEFAULT_MAX_PATH_DEPTH,
    DEFAULT_MAX_PATHS,
    EvidenceGraphEngine,
)
from document_intelligence.modules.graph.projector import (
    EvidenceGraphProjector,
    ProjectedGraphData,
)


class EvidenceGraphService:
    """Coordinates relational data retrieval, graph projection, and query operations."""

    def __init__(
        self,
        case_repo: CaseRepository,
        document_repo: DocumentRepository,
        evidence_repo: EvidenceRepository,
        finding_repo: FindingRepository,
        consistency_repo: ConsistencyRepository,
        relationship_repo: RelationshipRepository,
        entity_match_repo: EntityMatchRepository,
        projector: EvidenceGraphProjector | None = None,
        engine: EvidenceGraphEngine | None = None,
    ) -> None:
        self.case_repo = case_repo
        self.document_repo = document_repo
        self.evidence_repo = evidence_repo
        self.finding_repo = finding_repo
        self.consistency_repo = consistency_repo
        self.relationship_repo = relationship_repo
        self.entity_match_repo = entity_match_repo
        self.projector = projector or EvidenceGraphProjector()
        self.engine = engine or EvidenceGraphEngine()

    def _load_and_project_case_graph(self, case_id: str) -> ProjectedGraphData:
        """Fetch all case records and project them into the unified Evidence Graph."""
        case = self.case_repo.get_by_id(case_id)
        if not case:
            raise EntityNotFoundException("Case", case_id)

        # Retrieve all relevant records bounded within the case
        documents, _ = self.document_repo.list_by_case(case_id, limit=1000)
        evidence_nodes, _ = self.evidence_repo.list_by_case(case_id, limit=2000)
        forensic_findings, _ = self.finding_repo.list_by_case(case_id, limit=1000)
        consistency_findings = self.consistency_repo.list_findings(case_id, limit=1000)
        relationships, _ = self.relationship_repo.list_relationships(case_id, limit=1000)
        entity_matches, _ = self.entity_match_repo.list_matches(case_id, limit=1000)

        return self.projector.project_case(
            case=case,
            documents=documents,
            evidence_nodes=evidence_nodes,
            forensic_findings=forensic_findings,
            consistency_findings=consistency_findings,
            detected_relationships=relationships,
            entity_matches=entity_matches,
        )

    def get_case_graph(
        self,
        case_id: str,
        node_types: set[GraphNodeType] | None = None,
        relationship_types: set[str] | None = None,
        statuses: set[str] | None = None,
        document_ids: set[str] | None = None,
        limit: int = DEFAULT_MAX_NODES_LIMIT,
        offset: int = 0,
    ) -> GraphSnapshot:
        """Retrieve a bounded case graph projection with filtering."""
        projected_graph = self._load_and_project_case_graph(case_id)
        return self.engine.query_graph(
            graph=projected_graph,
            node_types=node_types,
            relationship_types=relationship_types,
            statuses=statuses,
            document_ids=document_ids,
            limit=limit,
            offset=offset,
        )

    def get_node(self, case_id: str, node_id: str) -> dict[str, Any]:
        """Retrieve detailed information and incident edges for a single graph node."""
        projected_graph = self._load_and_project_case_graph(case_id)
        node = projected_graph.nodes.get(node_id)
        if not node:
            raise EntityNotFoundException("GraphNode", node_id)

        outgoing_edges = [
            projected_graph.edges[eid]
            for eid in projected_graph.outgoing_edges.get(node_id, [])
            if eid in projected_graph.edges
        ]
        incoming_edges = [
            projected_graph.edges[eid]
            for eid in projected_graph.incoming_edges.get(node_id, [])
            if eid in projected_graph.edges
        ]

        return {
            "node": node,
            "outgoing_edges": outgoing_edges,
            "incoming_edges": incoming_edges,
            "degree": len(outgoing_edges) + len(incoming_edges),
        }

    def get_neighborhood(
        self,
        case_id: str,
        node_id: str,
        max_hops: int = DEFAULT_MAX_HOPS,
        limit: int = 200,
        relationship_types: set[str] | None = None,
        statuses: set[str] | None = None,
    ) -> GraphNeighborhoodResult:
        """Retrieve a bounded k-hop neighborhood centered around a target node."""
        projected_graph = self._load_and_project_case_graph(case_id)
        if node_id not in projected_graph.nodes:
            raise EntityNotFoundException("GraphNode", node_id)

        return self.engine.get_neighborhood(
            graph=projected_graph,
            center_node_id=node_id,
            max_hops=max_hops,
            limit=limit,
            relationship_types=relationship_types,
            statuses=statuses,
        )

    def find_paths(
        self,
        case_id: str,
        source_node_id: str,
        target_node_id: str,
        max_depth: int = DEFAULT_MAX_PATH_DEPTH,
        max_paths: int = DEFAULT_MAX_PATHS,
        confirmed_only: bool = False,
        relationship_types: set[str] | None = None,
    ) -> GraphPathsResult:
        """Find directed paths between two nodes with cycle prevention."""
        projected_graph = self._load_and_project_case_graph(case_id)
        if source_node_id not in projected_graph.nodes:
            raise EntityNotFoundException("GraphNode", source_node_id)
        if target_node_id not in projected_graph.nodes:
            raise EntityNotFoundException("GraphNode", target_node_id)

        return self.engine.find_paths(
            graph=projected_graph,
            source_node_id=source_node_id,
            target_node_id=target_node_id,
            max_depth=max_depth,
            max_paths=max_paths,
            confirmed_only=confirmed_only,
            relationship_types=relationship_types,
        )
