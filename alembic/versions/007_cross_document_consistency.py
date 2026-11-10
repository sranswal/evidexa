"""Cross-document consistency findings and human reviews relational tables.

Revision ID: 007_cross_document_consistency
Revises: 006_relationship_semantics
Create Date: 2026-11-09 22:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "007_cross_document_consistency"
down_revision: str | None = "006_relationship_semantics"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Consistency Findings Table
    op.create_table(
        "consistency_findings",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "case_id",
            sa.String(36),
            sa.ForeignKey("cases.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("analysis_run_id", sa.String(36), nullable=False),
        sa.Column("rule_id", sa.String(100), nullable=False),
        sa.Column("rule_version", sa.String(20), server_default="1.0.0", nullable=False),
        sa.Column("category", sa.String(50), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=False),
        sa.Column("severity", sa.String(32), nullable=False),
        sa.Column("outcome", sa.String(32), nullable=False),
        sa.Column("score", sa.Float(), server_default="1.0", nullable=False),
        sa.Column(
            "score_semantics",
            sa.String(255),
            server_default="rule_deterministic_confidence",
            nullable=False,
        ),
        sa.Column("affected_document_ids", sa.JSON(), nullable=False),
        sa.Column("compared_fields", sa.JSON(), nullable=False),
        sa.Column("original_values", sa.JSON(), nullable=False),
        sa.Column("normalized_values", sa.JSON(), nullable=False),
        sa.Column("supporting_evidence_ids", sa.JSON(), nullable=False),
        sa.Column("contradicting_evidence_ids", sa.JSON(), nullable=False),
        sa.Column("locations_payload", sa.JSON(), nullable=False),
        sa.Column("detection_method", sa.String(100), nullable=False),
        sa.Column("rule_parameters", sa.JSON(), nullable=False),
        sa.Column("limitations", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(32), server_default="DETECTED", nullable=False),
        sa.Column("review_status", sa.String(32), server_default="UNREVIEWED", nullable=False),
        sa.Column("is_human_reviewed", sa.Boolean(), server_default="0", nullable=False),
        sa.Column("comparisons_payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_consistency_findings_case_id", "consistency_findings", ["case_id"])
    op.create_index("ix_consistency_findings_run_id", "consistency_findings", ["analysis_run_id"])
    op.create_index("ix_consistency_findings_rule_id", "consistency_findings", ["rule_id"])
    op.create_index("ix_consistency_findings_outcome", "consistency_findings", ["outcome"])
    op.create_index("ix_consistency_findings_status", "consistency_findings", ["status"])
    op.create_index(
        "ix_consistency_findings_review_status", "consistency_findings", ["review_status"]
    )
    op.create_index(
        "ix_consistency_findings_case_outcome", "consistency_findings", ["case_id", "outcome"]
    )
    op.create_index(
        "ix_consistency_findings_case_status", "consistency_findings", ["case_id", "status"]
    )
    op.create_index(
        "ix_consistency_findings_case_rule", "consistency_findings", ["case_id", "rule_id"]
    )

    # 2. Consistency Reviews Table
    op.create_table(
        "consistency_reviews",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "case_id",
            sa.String(36),
            sa.ForeignKey("cases.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "finding_id",
            sa.String(36),
            sa.ForeignKey("consistency_findings.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("decision", sa.String(32), nullable=False),
        sa.Column("reviewer_id", sa.String(100), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("previous_status", sa.String(32), nullable=False),
        sa.Column("new_status", sa.String(32), nullable=False),
    )
    op.create_index("ix_consistency_reviews_case_id", "consistency_reviews", ["case_id"])
    op.create_index("ix_consistency_reviews_finding_id", "consistency_reviews", ["finding_id"])


def downgrade() -> None:
    op.drop_table("consistency_reviews")
    op.drop_table("consistency_findings")
