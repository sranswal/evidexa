"""Entity candidate matches and match reviews relational tables for cross-document resolution.

Revision ID: 004_entity_resolution
Revises: 003_confidence_and_snapshot_provenance
Create Date: 2026-11-09 17:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "004_entity_resolution"
down_revision: str | None = "003_confidence_and_snapshot_provenance"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Entity Candidate Matches table
    op.create_table(
        "entity_candidate_matches",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "case_id",
            sa.String(36),
            sa.ForeignKey("cases.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("processing_run_id", sa.String(36), nullable=False),
        sa.Column("entity_type", sa.String(50), nullable=False),
        sa.Column("target_mention_id", sa.String(36), nullable=False),
        sa.Column("candidate_mention_id", sa.String(36), nullable=False),
        sa.Column("target_value_display", sa.Text(), nullable=False),
        sa.Column("candidate_value_display", sa.Text(), nullable=False),
        sa.Column("matching_method", sa.String(50), nullable=False),
        sa.Column("match_classification", sa.String(50), nullable=False),
        sa.Column("match_score", sa.Float(), nullable=False),
        sa.Column("score_semantics", sa.String(255), nullable=False),
        sa.Column("decision_status", sa.String(50), nullable=False),
        sa.Column("review_status", sa.String(50), nullable=False),
        sa.Column("evidence_payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_entity_candidate_matches_case_id", "entity_candidate_matches", ["case_id"])
    op.create_index(
        "ix_entity_candidate_matches_run_id",
        "entity_candidate_matches",
        ["processing_run_id"],
    )
    op.create_index(
        "ix_entity_candidate_matches_entity_type",
        "entity_candidate_matches",
        ["entity_type"],
    )
    op.create_index(
        "ix_entity_candidate_matches_classification",
        "entity_candidate_matches",
        ["match_classification"],
    )
    op.create_index(
        "ix_entity_candidate_matches_decision_status",
        "entity_candidate_matches",
        ["decision_status"],
    )
    op.create_index(
        "ix_entity_candidate_matches_review_status",
        "entity_candidate_matches",
        ["review_status"],
    )
    op.create_index(
        "ix_entity_matches_case_status",
        "entity_candidate_matches",
        ["case_id", "decision_status"],
    )
    op.create_index(
        "ix_entity_matches_case_type",
        "entity_candidate_matches",
        ["case_id", "entity_type"],
    )

    # 2. Entity Match Reviews table
    op.create_table(
        "entity_match_reviews",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "case_id",
            sa.String(36),
            sa.ForeignKey("cases.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "match_id",
            sa.String(36),
            sa.ForeignKey("entity_candidate_matches.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("decision", sa.String(32), nullable=False),
        sa.Column("reviewer_id", sa.String(100), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("previous_status", sa.String(32), nullable=False),
        sa.Column("new_status", sa.String(32), nullable=False),
    )
    op.create_index("ix_entity_match_reviews_case_id", "entity_match_reviews", ["case_id"])
    op.create_index("ix_entity_match_reviews_match_id", "entity_match_reviews", ["match_id"])


def downgrade() -> None:
    op.drop_table("entity_match_reviews")
    op.drop_table("entity_candidate_matches")
