"""Domain models for unified investigation evidence graph projection and traversal."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from document_intelligence.domain.enums import GraphEdgePredicate, GraphNodeType
from document_intelligence.domain.identifiers import generate_id, utc_now

EVIDEXA_GRAPH_NAMESPACE = uuid.UUID("e7b8c2d1-9f4a-4e2b-8c3d-1a2b3c4d5e6f")


def deterministic_node_id(case_id: str, node_type: str | GraphNodeType, source_id: str) -> str:
    """Generate a stable, deterministic UUID for a graph node."""
    type_str = node_type.value if hasattr(node_type, "value") else str(node_type)
    return str(uuid.uuid5(EVIDEXA_GRAPH_NAMESPACE, f"node:{case_id}:{type_str}:{source_id}"))


def deterministic_edge_id(
    case_id: str,
    source_node_id: str,
    predicate: str | GraphEdgePredicate,
    target_node_id: str,
    source_rel_id: str | None = None,
) -> str:
    """Generate a stable, deterministic UUID for a graph edge."""
    pred_str = predicate.value if hasattr(predicate, "value") else str(predicate)
    disambiguator = source_rel_id or ""
    return str(
        uuid.uuid5(
            EVIDEXA_GRAPH_NAMESPACE,
            f"edge:{case_id}:{source_node_id}:{pred_str}:{target_node_id}:{disambiguator}",
        )
    )


class GraphNode(BaseModel):
    """A projected node in the unified investigation Evidence Graph."""

    id: str = Field(default_factory=generate_id)
    case_id: str
    node_type: GraphNodeType
    source_entity_type: str = Field(
        description="Underlying domain entity type (e.g. Case, Document, EvidenceNode, ForensicFinding, ConsistencyFinding, DetectedRelationship, EntityMention)."
    )
    source_entity_id: str = Field(description="Authoritative ID in source relational database.")
    label: str = Field(
        description="Safe, sanitized display label for UI rendering and investigator inspection."
    )
    display_attributes: dict[str, Any] = Field(
        default_factory=dict,
        description="Safe summary attributes (e.g. classification, severity, status). Strictly no plaintext PII.",
    )
    provenance: dict[str, Any] = Field(
        default_factory=dict,
        description="Traceability links to source records, documents, pages, and components.",
    )
    created_at: datetime | None = Field(default_factory=utc_now)


class GraphEdge(BaseModel):
    """A directed evidentiary connection or relationship in the Evidence Graph."""

    id: str = Field(default_factory=generate_id)
    case_id: str
    source_node_id: str = Field(description="Subject node ID in directed relationship.")
    target_node_id: str = Field(description="Object node ID in directed relationship.")
    predicate: str = Field(
        description="Canonical relationship predicate (e.g. ISSUED, INVOICED, HAS_EVIDENCE, SUPPORTED_BY)."
    )
    status: str = Field(
        default="CONFIRMED",
        description="Evidentiary status: CONFIRMED, CANDIDATE, CONTRADICTED, UNRESOLVED, REJECTED.",
    )
    status_determination_method: str | None = Field(
        default=None,
        description="Method determining edge status: EVIDENTIARY_RULE, HUMAN_REVIEW, etc.",
    )
    score: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Deterministic heuristic strength or similarity score (never probability).",
    )
    supporting_evidence_ids: list[str] = Field(
        default_factory=list,
        description="Authoritative evidence node IDs directly corroborating this edge.",
    )
    contradicting_evidence_ids: list[str] = Field(
        default_factory=list,
        description="Authoritative evidence node IDs contradicting this edge.",
    )
    source_relationship_id: str | None = Field(
        default=None,
        description="Authoritative ID of underlying DetectedRelationship, Match, or Link if applicable.",
    )
    explanation: str | None = Field(
        default=None,
        description="Factual rationale explaining why this connection exists.",
    )
    metadata: dict[str, Any] = Field(default_factory=dict)


class GraphPath(BaseModel):
    """An ordered, directed path connecting two nodes in the Evidence Graph."""

    nodes: list[GraphNode]
    edges: list[GraphEdge]
    length: int
    is_confirmed_only: bool = True


class GraphSnapshot(BaseModel):
    """A bounded projection of the investigation Evidence Graph."""

    case_id: str
    nodes: list[GraphNode] = Field(default_factory=list)
    edges: list[GraphEdge] = Field(default_factory=list)
    total_nodes: int = 0
    total_edges: int = 0
    truncated: bool = False
    query_metadata: dict[str, Any] = Field(default_factory=dict)
    projection_version: str = "1.0.0"


class GraphNeighborhoodResult(BaseModel):
    """Result of a bounded k-hop neighborhood query centered on a target node."""

    case_id: str
    center_node_id: str
    hops: int
    nodes: list[GraphNode] = Field(default_factory=list)
    edges: list[GraphEdge] = Field(default_factory=list)
    total_nodes: int = 0
    total_edges: int = 0
    truncated: bool = False


class GraphPathsResult(BaseModel):
    """Result of a bounded path search between two graph nodes."""

    case_id: str
    source_node_id: str
    target_node_id: str
    max_depth: int
    paths: list[GraphPath] = Field(default_factory=list)
    total_paths_found: int = 0
    truncated: bool = False
