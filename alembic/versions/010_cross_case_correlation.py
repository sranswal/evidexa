"""Cross-Case Correlation and Investigation Intelligence Schema.

Revision ID: 010_cross_case_correlation
Revises: 009_identity_and_access
Create Date: 2026-11-10 17:30:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "010_cross_case_correlation"
down_revision: str | None = "009_identity_and_access"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Create cross_case_scopes table
    op.create_table(
        "cross_case_scopes",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "organization_id",
            sa.String(36),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("case_ids", sa.JSON(), nullable=False),
        sa.Column("created_by", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="1", nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=False),
    )
    op.create_index("ix_cross_case_scopes_org", "cross_case_scopes", ["organization_id"])

    # 2. Create cross_case_candidate_matches table
    op.create_table(
        "cross_case_candidate_matches",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "scope_id",
            sa.String(36),
            sa.ForeignKey("cross_case_scopes.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("organization_id", sa.String(36), nullable=False),
        sa.Column("entity_type", sa.String(50), nullable=False),
        sa.Column("target_case_id", sa.String(36), nullable=False),
        sa.Column("candidate_case_id", sa.String(36), nullable=False),
        sa.Column("target_value_display", sa.String(500), nullable=False),
        sa.Column("candidate_value_display", sa.String(500), nullable=False),
        sa.Column("raw_target_value_masked", sa.String(500), nullable=False, server_default=""),
        sa.Column("raw_candidate_value_masked", sa.String(500), nullable=False, server_default=""),
        sa.Column("matching_method", sa.String(50), nullable=False),
        sa.Column("match_classification", sa.String(50), nullable=False),
        sa.Column("match_score", sa.Float(), nullable=False),
        sa.Column("decision_status", sa.String(50), server_default="PENDING_REVIEW", nullable=False),
        sa.Column("evidence", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_cross_case_matches_scope", "cross_case_candidate_matches", ["scope_id"])
    op.create_index(
        "ix_cross_case_matches_scope_status",
        "cross_case_candidate_matches",
        ["scope_id", "decision_status"],
    )
    op.create_index(
        "ix_cross_case_matches_cases",
        "cross_case_candidate_matches",
        ["target_case_id", "candidate_case_id"],
    )

    # 3. Create cross_case_candidate_reviews table
    op.create_table(
        "cross_case_candidate_reviews",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "match_id",
            sa.String(36),
            sa.ForeignKey("cross_case_candidate_matches.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("scope_id", sa.String(36), nullable=False),
        sa.Column("decision", sa.String(50), nullable=False),
        sa.Column("reviewer_id", sa.String(36), nullable=False),
        sa.Column("reviewer_username", sa.String(100), nullable=True),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("previous_status", sa.String(50), nullable=False),
        sa.Column("new_status", sa.String(50), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_cross_case_reviews_match", "cross_case_candidate_reviews", ["match_id"])
    op.create_index("ix_cross_case_reviews_scope", "cross_case_candidate_reviews", ["scope_id"])


def downgrade() -> None:
    op.drop_table("cross_case_candidate_reviews")
    op.drop_table("cross_case_candidate_matches")
    op.drop_table("cross_case_scopes")

