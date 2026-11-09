"""SQLAlchemy ORM models defining the database schema."""

from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from document_intelligence.infrastructure.persistence.database import Base


class CaseModel(Base):
    """Cases table."""

    __tablename__ = "cases"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    case_reference: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_by: Mapped[str | None] = mapped_column(String(100), nullable=True)
    case_metadata: Mapped[dict[str, Any]] = mapped_column("metadata", JSON, default=dict)

    # Relationships
    documents: Mapped[list["DocumentModel"]] = relationship(
        "DocumentModel", back_populates="case", cascade="all, delete-orphan"
    )
    findings: Mapped[list["ForensicFindingModel"]] = relationship(
        "ForensicFindingModel", back_populates="case", cascade="all, delete-orphan"
    )
    audit_events: Mapped[list["AuditEventModel"]] = relationship(
        "AuditEventModel", back_populates="case", cascade="all, delete-orphan"
    )


class DocumentModel(Base):
    """Documents table."""

    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    case_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("cases.id", ondelete="CASCADE"), nullable=False, index=True
    )
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    media_type: Mapped[str] = mapped_column(String(100), nullable=False)
    file_extension: Mapped[str] = mapped_column(String(20), nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    storage_key: Mapped[str] = mapped_column(String(500), nullable=False, unique=True)
    page_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    document_type: Mapped[str] = mapped_column(String(50), default="UNKNOWN")
    ingestion_status: Mapped[str] = mapped_column(String(32), default="STORED")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_by: Mapped[str | None] = mapped_column(String(100), nullable=True)
    doc_metadata: Mapped[dict[str, Any]] = mapped_column("metadata", JSON, default=dict)

    # Relationship
    case: Mapped["CaseModel"] = relationship("CaseModel", back_populates="documents")


class ProcessingRunModel(Base):
    """Processing runs table."""

    __tablename__ = "processing_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    case_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("cases.id", ondelete="CASCADE"), nullable=False, index=True
    )
    document_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    pipeline_name: Mapped[str] = mapped_column(String(100), nullable=False)
    pipeline_version: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    snapshot_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    configuration_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    resource_metrics: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)


class EvidenceNodeModel(Base):
    """Evidence nodes table."""

    __tablename__ = "evidence_nodes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    case_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("cases.id", ondelete="CASCADE"), nullable=False, index=True
    )
    document_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    processing_run_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    evidence_type: Mapped[str] = mapped_column(String(50), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    source_component: Mapped[str] = mapped_column(String(100), nullable=False)
    source_version: Mapped[str] = mapped_column(String(50), nullable=False)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    page_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    bounding_box: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    coordinate_system: Mapped[str | None] = mapped_column(String(50), nullable=True)
    pdf_object_reference: Mapped[str | None] = mapped_column(String(100), nullable=True)
    byte_offset_start: Mapped[int | None] = mapped_column(Integer, nullable=True)
    byte_offset_end: Mapped[int | None] = mapped_column(Integer, nullable=True)
    raw_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    normalized_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    categorical_confidence: Mapped[str | None] = mapped_column(String(50), nullable=True)
    confidence_source: Mapped[str | None] = mapped_column(String(100), nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    node_metadata: Mapped[dict[str, Any]] = mapped_column("metadata", JSON, default=dict)


class ForensicFindingModel(Base):
    """Forensic findings table."""

    __tablename__ = "forensic_findings"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    case_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("cases.id", ondelete="CASCADE"), nullable=False, index=True
    )
    document_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    processing_run_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    category: Mapped[str] = mapped_column(String(50), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[str] = mapped_column(String(32), nullable=False)
    categorical_confidence: Mapped[str | None] = mapped_column(String(50), nullable=True)
    confidence_source: Mapped[str | None] = mapped_column(String(100), nullable=True)
    confidence_calibration_method: Mapped[str | None] = mapped_column(String(100), nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    evidence_ids: Mapped[list[str]] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    source_component: Mapped[str] = mapped_column(String(100), nullable=False)
    limitations: Mapped[list[str]] = mapped_column(JSON, default=list)
    finding_metadata: Mapped[dict[str, Any]] = mapped_column("metadata", JSON, default=dict)

    # Relationship
    case: Mapped["CaseModel"] = relationship("CaseModel", back_populates="findings")


class FindingEvidenceLinkModel(Base):
    """Relational association between forensic findings and evidence nodes."""

    __tablename__ = "finding_evidence_links"

    finding_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("forensic_findings.id", ondelete="CASCADE"), primary_key=True
    )
    evidence_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("evidence_nodes.id", ondelete="CASCADE"), primary_key=True
    )


class InvestigationDossierModel(Base):
    """Investigation dossiers table."""

    __tablename__ = "investigation_dossiers"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    case_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("cases.id", ondelete="CASCADE"), nullable=False, index=True
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    executive_summary: Mapped[str] = mapped_column(Text, nullable=False)
    document_summaries: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    finding_ids: Mapped[list[str]] = mapped_column(JSON, default=list)
    evidence_ids: Mapped[list[str]] = mapped_column(JSON, default=list)
    review_decisions: Mapped[list[str]] = mapped_column(JSON, default=list)
    limitations: Mapped[list[str]] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_by: Mapped[str] = mapped_column(String(100), nullable=False)
    finalized_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (UniqueConstraint("case_id", "version", name="uq_dossier_case_version"),)


class ReviewDecisionModel(Base):
    """Review decisions table."""

    __tablename__ = "review_decisions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    case_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("cases.id", ondelete="CASCADE"), nullable=False, index=True
    )
    finding_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("forensic_findings.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    reviewer_id: Mapped[str] = mapped_column(String(100), nullable=False)
    decision: Mapped[str] = mapped_column(String(32), nullable=False)
    comment: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    previous_status: Mapped[str] = mapped_column(String(32), nullable=False)
    new_status: Mapped[str] = mapped_column(String(32), nullable=False)


class AuditEventModel(Base):
    """Audit events table (immutable append-only hash chain)."""

    __tablename__ = "audit_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    case_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("cases.id", ondelete="CASCADE"), nullable=False, index=True
    )
    sequence_number: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    actor_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    event_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(36), nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    previous_event_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    event_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    schema_version: Mapped[str] = mapped_column(String(10), default="1.0")

    # Relationship
    case: Mapped["CaseModel"] = relationship("CaseModel", back_populates="audit_events")

    __table_args__ = (
        Index("ix_audit_events_case_timestamp", "case_id", "timestamp"),
        UniqueConstraint("case_id", "sequence_number", name="uq_audit_case_seq"),
    )


class AuditCheckpointModel(Base):
    """Audit ledger checkpoint holding trusted head state per case."""

    __tablename__ = "audit_checkpoints"

    case_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("cases.id", ondelete="CASCADE"), primary_key=True
    )
    head_event_id: Mapped[str] = mapped_column(String(36), nullable=False)
    head_event_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    event_count: Mapped[int] = mapped_column(Integer, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class EntityCandidateMatchModel(Base):
    """Entity candidate matches table for cross-document resolution."""

    __tablename__ = "entity_candidate_matches"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    case_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("cases.id", ondelete="CASCADE"), nullable=False, index=True
    )
    processing_run_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    target_mention_id: Mapped[str] = mapped_column(String(36), nullable=False)
    candidate_mention_id: Mapped[str] = mapped_column(String(36), nullable=False)
    target_value_display: Mapped[str] = mapped_column(Text, nullable=False)
    candidate_value_display: Mapped[str] = mapped_column(Text, nullable=False)
    matching_method: Mapped[str] = mapped_column(String(50), nullable=False)
    match_classification: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    match_score: Mapped[float] = mapped_column(Float, nullable=False)
    score_semantics: Mapped[str] = mapped_column(String(255), nullable=False)
    decision_status: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    review_status: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    evidence_payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        Index("ix_entity_matches_case_status", "case_id", "decision_status"),
        Index("ix_entity_matches_case_type", "case_id", "entity_type"),
    )


class EntityMatchReviewModel(Base):
    """Human review decision audit trail for entity candidate matches."""

    __tablename__ = "entity_match_reviews"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    case_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("cases.id", ondelete="CASCADE"), nullable=False, index=True
    )
    match_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("entity_candidate_matches.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    decision: Mapped[str] = mapped_column(String(32), nullable=False)
    reviewer_id: Mapped[str] = mapped_column(String(100), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    reviewed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    previous_status: Mapped[str] = mapped_column(String(32), nullable=False)
    new_status: Mapped[str] = mapped_column(String(32), nullable=False)


class DetectedRelationshipModel(Base):
    """Detected relationships table for cross-document contextual connections."""

    __tablename__ = "detected_relationships"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    case_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("cases.id", ondelete="CASCADE"), nullable=False, index=True
    )
    detection_run_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    relationship_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    ontology_version: Mapped[str] = mapped_column(
        String(20), nullable=False, default="2.0", server_default="2.0"
    )
    legacy_relationship_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    source_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    source_type: Mapped[str] = mapped_column(String(50), nullable=False)
    source_label: Mapped[str] = mapped_column(String(255), nullable=False)
    target_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    target_type: Mapped[str] = mapped_column(String(50), nullable=False)
    target_label: Mapped[str] = mapped_column(String(255), nullable=False)
    direction_display: Mapped[str] = mapped_column(String(500), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    status_determination_method: Mapped[str] = mapped_column(
        String(50), nullable=False, default="EVIDENTIARY_RULE", server_default="EVIDENTIARY_RULE"
    )
    duplicate_kind: Mapped[str | None] = mapped_column(String(50), nullable=True)
    score: Mapped[float] = mapped_column(Float, nullable=False)
    score_semantics: Mapped[str] = mapped_column(String(255), nullable=False)
    detection_method: Mapped[str] = mapped_column(String(100), nullable=False)
    detection_version: Mapped[str] = mapped_column(String(50), nullable=False)
    status_rationale: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        Index("ix_relationships_case_status", "case_id", "status"),
        Index("ix_relationships_case_type", "case_id", "relationship_type"),
        Index("ix_relationships_source", "case_id", "source_id"),
        Index("ix_relationships_target", "case_id", "target_id"),
    )


class RelationshipReviewModel(Base):
    """Human review decision audit trail for detected relationships."""

    __tablename__ = "relationship_reviews"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    case_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("cases.id", ondelete="CASCADE"), nullable=False, index=True
    )
    relationship_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("detected_relationships.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    decision: Mapped[str] = mapped_column(String(32), nullable=False)
    reviewer_id: Mapped[str] = mapped_column(String(100), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    reviewed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    previous_status: Mapped[str] = mapped_column(String(32), nullable=False)
    new_status: Mapped[str] = mapped_column(String(32), nullable=False)
