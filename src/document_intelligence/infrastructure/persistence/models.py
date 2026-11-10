"""SQLAlchemy ORM models defining the database schema."""

from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
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

from document_intelligence.domain.identifiers import utc_now
from document_intelligence.infrastructure.persistence.database import Base


class OrganizationModel(Base):
    """Organizations table for multi-tenant isolation."""

    __tablename__ = "organizations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

    # Relationships
    cases: Mapped[list["CaseModel"]] = relationship("CaseModel", back_populates="organization")
    memberships: Mapped[list["OrganizationMembershipModel"]] = relationship(
        "OrganizationMembershipModel", back_populates="organization", cascade="all, delete-orphan"
    )


class UserModel(Base):
    """User accounts table."""

    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    username: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    system_role: Mapped[str] = mapped_column(String(32), default="USER", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )

    # Relationships
    case_memberships: Mapped[list["CaseMembershipModel"]] = relationship(
        "CaseMembershipModel", back_populates="user", cascade="all, delete-orphan"
    )
    refresh_tokens: Mapped[list["RefreshTokenModel"]] = relationship(
        "RefreshTokenModel", back_populates="user", cascade="all, delete-orphan"
    )


class OrganizationMembershipModel(Base):
    """Organization membership table."""

    __tablename__ = "organization_memberships"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(String(32), default="MEMBER", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

    __table_args__ = (UniqueConstraint("organization_id", "user_id", name="uq_org_member"),)

    organization: Mapped["OrganizationModel"] = relationship(
        "OrganizationModel", back_populates="memberships"
    )


class CaseMembershipModel(Base):
    """Case-scoped RBAC membership table."""

    __tablename__ = "case_memberships"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    case_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("cases.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(String(32), default="VIEWER", nullable=False, index=True)
    assigned_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

    __table_args__ = (UniqueConstraint("case_id", "user_id", name="uq_case_member"),)

    case: Mapped["CaseModel"] = relationship("CaseModel", back_populates="memberships")
    user: Mapped["UserModel"] = relationship("UserModel", back_populates="case_memberships")


class RefreshTokenModel(Base):
    """Cryptographically hashed refresh tokens with single-use rotation."""

    __tablename__ = "refresh_tokens"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    is_revoked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    replaced_by_token_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(500), nullable=True)

    user: Mapped["UserModel"] = relationship("UserModel", back_populates="refresh_tokens")


class AuthenticationEventModel(Base):
    """Authentication and security audit event log."""

    __tablename__ = "authentication_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    event_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    username_attempted: Mapped[str | None] = mapped_column(String(255), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(500), nullable=True)
    details: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )


class CaseModel(Base):
    """Cases table."""

    __tablename__ = "cases"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    organization_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="SET NULL"), nullable=True, index=True
    )
    case_reference: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )
    created_by: Mapped[str | None] = mapped_column(String(100), nullable=True)
    case_metadata: Mapped[dict[str, Any]] = mapped_column("metadata", JSON, default=dict)

    # Relationships
    organization: Mapped["OrganizationModel | None"] = relationship(
        "OrganizationModel", back_populates="cases"
    )
    memberships: Mapped[list["CaseMembershipModel"]] = relationship(
        "CaseMembershipModel", back_populates="case", cascade="all, delete-orphan"
    )
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
    title: Mapped[str] = mapped_column(
        String(255), default="Investigation Evidence Dossier", nullable=False
    )
    scope_and_purpose: Mapped[str] = mapped_column(Text, default="", nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    executive_summary: Mapped[str] = mapped_column(Text, nullable=False)
    document_summaries: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    finding_ids: Mapped[list[str]] = mapped_column(JSON, default=list)
    evidence_ids: Mapped[list[str]] = mapped_column(JSON, default=list)
    review_decisions: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    limitations: Mapped[list[str]] = mapped_column(JSON, default=list)
    unresolved_questions: Mapped[list[str]] = mapped_column(JSON, default=list)
    sections: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    dossier_payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_by: Mapped[str] = mapped_column(String(100), nullable=False)
    finalized_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (UniqueConstraint("case_id", "version", name="uq_dossier_case_version"),)


class AggregatedFindingReviewModel(Base):
    """Investigator review decisions table for unified cross-domain findings."""

    __tablename__ = "aggregated_finding_reviews"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    case_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("cases.id", ondelete="CASCADE"), nullable=False, index=True
    )
    finding_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    reviewer_id: Mapped[str] = mapped_column(String(100), nullable=False)
    comment: Mapped[str] = mapped_column(Text, nullable=False)
    reviewed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    previous_status: Mapped[str] = mapped_column(String(50), nullable=False)
    new_status: Mapped[str] = mapped_column(String(50), nullable=False)


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


class ConsistencyFindingModel(Base):
    """Consistency findings table for cross-document deterministic comparisons."""

    __tablename__ = "consistency_findings"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    case_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("cases.id", ondelete="CASCADE"), nullable=False, index=True
    )
    analysis_run_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    rule_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    rule_version: Mapped[str] = mapped_column(String(20), nullable=False, default="1.0.0")
    category: Mapped[str] = mapped_column(String(50), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[str] = mapped_column(String(32), nullable=False)
    outcome: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    score: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    score_semantics: Mapped[str] = mapped_column(
        String(255), nullable=False, default="rule_deterministic_confidence"
    )
    affected_document_ids: Mapped[list[str]] = mapped_column(JSON, default=list)
    compared_fields: Mapped[list[str]] = mapped_column(JSON, default=list)
    original_values: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    normalized_values: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    supporting_evidence_ids: Mapped[list[str]] = mapped_column(JSON, default=list)
    contradicting_evidence_ids: Mapped[list[str]] = mapped_column(JSON, default=list)
    locations_payload: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    detection_method: Mapped[str] = mapped_column(String(100), nullable=False)
    rule_parameters: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    limitations: Mapped[list[str]] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="DETECTED", index=True)
    review_status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="UNREVIEWED", index=True
    )
    is_human_reviewed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    comparisons_payload: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )

    __table_args__ = (
        Index("ix_consistency_findings_case_outcome", "case_id", "outcome"),
        Index("ix_consistency_findings_case_status", "case_id", "status"),
        Index("ix_consistency_findings_case_rule", "case_id", "rule_id"),
    )


class ConsistencyReviewModel(Base):
    """Human review decision audit trail for consistency findings."""

    __tablename__ = "consistency_reviews"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    case_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("cases.id", ondelete="CASCADE"), nullable=False, index=True
    )
    finding_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("consistency_findings.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    decision: Mapped[str] = mapped_column(String(32), nullable=False)
    reviewer_id: Mapped[str] = mapped_column(String(100), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    reviewed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
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
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )

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


class CrossCaseScopeModel(Base):
    """Explicit cross-case investigation scope bounding case participation."""

    __tablename__ = "cross_case_scopes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    case_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    created_by: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    scope_metadata: Mapped[dict[str, Any]] = mapped_column("metadata", JSON, default=dict)


class CrossCaseCandidateMatchModel(Base):
    """Persisted cross-case candidate correlation match between entity mentions."""

    __tablename__ = "cross_case_candidate_matches"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    scope_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("cross_case_scopes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    organization_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    target_case_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    candidate_case_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    target_value_display: Mapped[str] = mapped_column(String(500), nullable=False)
    candidate_value_display: Mapped[str] = mapped_column(String(500), nullable=False)
    raw_target_value_masked: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    raw_candidate_value_masked: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    matching_method: Mapped[str] = mapped_column(String(50), nullable=False)
    match_classification: Mapped[str] = mapped_column(String(50), nullable=False)
    match_score: Mapped[float] = mapped_column(Float, nullable=False)
    decision_status: Mapped[str] = mapped_column(
        String(50), default="PENDING_REVIEW", nullable=False
    )
    evidence_payload: Mapped[dict[str, Any]] = mapped_column("evidence", JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

    __table_args__ = (
        Index("ix_cross_case_matches_scope_status", "scope_id", "decision_status"),
        Index("ix_cross_case_matches_cases", "target_case_id", "candidate_case_id"),
    )


class CrossCaseCandidateReviewModel(Base):
    """Audit log of human review decisions on cross-case correlation candidates."""

    __tablename__ = "cross_case_candidate_reviews"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    match_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("cross_case_candidate_matches.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    scope_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    decision: Mapped[str] = mapped_column(String(50), nullable=False)
    reviewer_id: Mapped[str] = mapped_column(String(36), nullable=False)
    reviewer_username: Mapped[str | None] = mapped_column(String(100), nullable=True)
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    previous_status: Mapped[str] = mapped_column(String(50), nullable=False)
    new_status: Mapped[str] = mapped_column(String(50), nullable=False)
    reviewed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
