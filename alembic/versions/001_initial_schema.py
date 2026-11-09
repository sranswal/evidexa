"""Initial database schema migration.

Revision ID: 001_initial_schema
Revises:
Create Date: 2026-11-07 14:00:00.000000

"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "001_initial_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Cases
    op.create_table(
        "cases",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("case_reference", sa.String(64), nullable=False, unique=True),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.String(100), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=False),
    )
    op.create_index("ix_cases_case_reference", "cases", ["case_reference"])
    op.create_index("ix_cases_status", "cases", ["status"])

    # 2. Documents
    op.create_table(
        "documents",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "case_id", sa.String(36), sa.ForeignKey("cases.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("original_filename", sa.String(255), nullable=False),
        sa.Column("media_type", sa.String(100), nullable=False),
        sa.Column("file_extension", sa.String(20), nullable=False),
        sa.Column("file_size_bytes", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("storage_key", sa.String(500), nullable=False, unique=True),
        sa.Column("page_count", sa.Integer(), nullable=True),
        sa.Column("document_type", sa.String(50), nullable=False),
        sa.Column("ingestion_status", sa.String(32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.String(100), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=False),
    )
    op.create_index("ix_documents_case_id", "documents", ["case_id"])
    op.create_index("ix_documents_sha256", "documents", ["sha256"])

    # 3. Processing Runs
    op.create_table(
        "processing_runs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "case_id", sa.String(36), sa.ForeignKey("cases.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("document_ids", sa.JSON(), nullable=False),
        sa.Column("pipeline_name", sa.String(100), nullable=False),
        sa.Column("pipeline_version", sa.String(50), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_code", sa.String(50), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("configuration_snapshot", sa.JSON(), nullable=False),
        sa.Column("resource_metrics", sa.JSON(), nullable=True),
    )
    op.create_index("ix_processing_runs_case_id", "processing_runs", ["case_id"])

    # 4. Evidence Nodes
    op.create_table(
        "evidence_nodes",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "case_id", sa.String(36), sa.ForeignKey("cases.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("document_id", sa.String(36), nullable=True),
        sa.Column("processing_run_id", sa.String(36), nullable=False),
        sa.Column("evidence_type", sa.String(50), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("source_component", sa.String(100), nullable=False),
        sa.Column("source_version", sa.String(50), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=True),
        sa.Column("bounding_box", sa.JSON(), nullable=True),
        sa.Column("coordinate_system", sa.String(50), nullable=True),
        sa.Column("pdf_object_reference", sa.String(100), nullable=True),
        sa.Column("byte_offset_start", sa.Integer(), nullable=True),
        sa.Column("byte_offset_end", sa.Integer(), nullable=True),
        sa.Column("raw_value", sa.Text(), nullable=True),
        sa.Column("normalized_value", sa.Text(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=False),
    )
    op.create_index("ix_evidence_nodes_case_id", "evidence_nodes", ["case_id"])
    op.create_index("ix_evidence_nodes_document_id", "evidence_nodes", ["document_id"])
    op.create_index("ix_evidence_nodes_processing_run_id", "evidence_nodes", ["processing_run_id"])

    # 5. Forensic Findings
    op.create_table(
        "forensic_findings",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "case_id", sa.String(36), sa.ForeignKey("cases.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("document_id", sa.String(36), nullable=True),
        sa.Column("processing_run_id", sa.String(36), nullable=False),
        sa.Column("category", sa.String(50), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("severity", sa.String(32), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("evidence_ids", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source_component", sa.String(100), nullable=False),
        sa.Column("limitations", sa.JSON(), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=False),
    )
    op.create_index("ix_forensic_findings_case_id", "forensic_findings", ["case_id"])
    op.create_index("ix_forensic_findings_document_id", "forensic_findings", ["document_id"])

    # 6. Investigation Dossiers
    op.create_table(
        "investigation_dossiers",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "case_id", sa.String(36), sa.ForeignKey("cases.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("executive_summary", sa.Text(), nullable=False),
        sa.Column("document_summaries", sa.JSON(), nullable=False),
        sa.Column("finding_ids", sa.JSON(), nullable=False),
        sa.Column("evidence_ids", sa.JSON(), nullable=False),
        sa.Column("review_decisions", sa.JSON(), nullable=False),
        sa.Column("limitations", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.String(100), nullable=False),
        sa.Column("finalized_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_investigation_dossiers_case_id", "investigation_dossiers", ["case_id"])

    # 7. Review Decisions
    op.create_table(
        "review_decisions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "case_id", sa.String(36), sa.ForeignKey("cases.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column(
            "finding_id",
            sa.String(36),
            sa.ForeignKey("forensic_findings.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("reviewer_id", sa.String(100), nullable=False),
        sa.Column("decision", sa.String(32), nullable=False),
        sa.Column("comment", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("previous_status", sa.String(32), nullable=False),
        sa.Column("new_status", sa.String(32), nullable=False),
    )
    op.create_index("ix_review_decisions_case_id", "review_decisions", ["case_id"])
    op.create_index("ix_review_decisions_finding_id", "review_decisions", ["finding_id"])

    # 8. Audit Events
    op.create_table(
        "audit_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "case_id", sa.String(36), sa.ForeignKey("cases.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("actor_id", sa.String(100), nullable=True),
        sa.Column("event_type", sa.String(50), nullable=False),
        sa.Column("entity_type", sa.String(50), nullable=False),
        sa.Column("entity_id", sa.String(36), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("previous_event_hash", sa.String(64), nullable=True),
        sa.Column("event_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("schema_version", sa.String(10), nullable=False),
    )
    op.create_index("ix_audit_events_case_id", "audit_events", ["case_id"])
    op.create_index("ix_audit_events_event_type", "audit_events", ["event_type"])
    op.create_index("ix_audit_events_event_hash", "audit_events", ["event_hash"])
    op.create_index("ix_audit_events_case_timestamp", "audit_events", ["case_id", "timestamp"])


def downgrade() -> None:
    op.drop_table("audit_events")
    op.drop_table("review_decisions")
    op.drop_table("investigation_dossiers")
    op.drop_table("forensic_findings")
    op.drop_table("evidence_nodes")
    op.drop_table("processing_runs")
    op.drop_table("documents")
    op.drop_table("cases")
