"""Detected relationships and relationship reviews relational tables for cross-document intelligence.

Revision ID: 005_relationship_detection
Revises: 004_entity_resolution
Create Date: 2026-11-09 18:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "005_relationship_detection"
down_revision: str | None = "004_entity_resolution"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Detected Relationships table
    op.create_table(
        "detected_relationships",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "case_id",
            sa.String(36),
            sa.ForeignKey("cases.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("detection_run_id", sa.String(36), nullable=False),
        sa.Column("relationship_type", sa.String(50), nullable=False),
        sa.Column("source_id", sa.String(100), nullable=False),
        sa.Column("source_type", sa.String(50), nullable=False),
        sa.Column("source_label", sa.String(255), nullable=False),
        sa.Column("target_id", sa.String(100), nullable=False),
        sa.Column("target_type", sa.String(50), nullable=False),
        sa.Column("target_label", sa.String(255), nullable=False),
        sa.Column("direction_display", sa.String(500), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("score_semantics", sa.String(255), nullable=False),
        sa.Column("detection_method", sa.String(100), nullable=False),
        sa.Column("detection_version", sa.String(50), nullable=False),
        sa.Column("status_rationale", sa.Text(), nullable=False),
        sa.Column("evidence_payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_detected_relationships_case_id", "detected_relationships", ["case_id"])
    op.create_index(
        "ix_detected_relationships_run_id",
        "detected_relationships",
        ["detection_run_id"],
    )
    op.create_index(
        "ix_detected_relationships_type",
        "detected_relationships",
        ["relationship_type"],
    )
    op.create_index("ix_detected_relationships_status", "detected_relationships", ["status"])
    op.create_index(
        "ix_detected_relationships_source_id",
        "detected_relationships",
        ["source_id"],
    )
    op.create_index(
        "ix_detected_relationships_target_id",
        "detected_relationships",
        ["target_id"],
    )
    op.create_index(
        "ix_relationships_case_status",
        "detected_relationships",
        ["case_id", "status"],
    )
    op.create_index(
        "ix_relationships_case_type",
        "detected_relationships",
        ["case_id", "relationship_type"],
    )
    op.create_index(
        "ix_relationships_source",
        "detected_relationships",
        ["case_id", "source_id"],
    )
    op.create_index(
        "ix_relationships_target",
        "detected_relationships",
        ["case_id", "target_id"],
    )

    # 2. Relationship Reviews table
    op.create_table(
        "relationship_reviews",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "case_id",
            sa.String(36),
            sa.ForeignKey("cases.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "relationship_id",
            sa.String(36),
            sa.ForeignKey("detected_relationships.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("decision", sa.String(32), nullable=False),
        sa.Column("reviewer_id", sa.String(100), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("previous_status", sa.String(32), nullable=False),
        sa.Column("new_status", sa.String(32), nullable=False),
    )
    op.create_index("ix_relationship_reviews_case_id", "relationship_reviews", ["case_id"])
    op.create_index(
        "ix_relationship_reviews_relationship_id",
        "relationship_reviews",
        ["relationship_id"],
    )


def downgrade() -> None:
    op.drop_table("relationship_reviews")
    op.drop_table("detected_relationships")
