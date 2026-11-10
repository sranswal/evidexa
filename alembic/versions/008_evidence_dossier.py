"""Evidence dossier schema extension and aggregated finding reviews table.

Revision ID: 008_evidence_dossier
Revises: 007_cross_document_consistency
Create Date: 2026-11-09 23:15:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "008_evidence_dossier"
down_revision: str | None = "007_cross_document_consistency"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Add structured sections, content hash, and payload columns to investigation_dossiers
    with op.batch_alter_table("investigation_dossiers") as batch_op:
        batch_op.add_column(
            sa.Column(
                "title",
                sa.String(255),
                server_default="Investigation Evidence Dossier",
                nullable=False,
            )
        )
        batch_op.add_column(
            sa.Column("scope_and_purpose", sa.Text(), server_default="", nullable=False)
        )
        batch_op.add_column(sa.Column("content_hash", sa.String(64), nullable=True))
        batch_op.add_column(
            sa.Column("sections", sa.JSON(), server_default="[]", nullable=False)
        )
        batch_op.add_column(
            sa.Column(
                "unresolved_questions", sa.JSON(), server_default="[]", nullable=False
            )
        )
        batch_op.add_column(
            sa.Column("dossier_payload", sa.JSON(), server_default="{}", nullable=False)
        )

    # 2. Create aggregated_finding_reviews table
    op.create_table(
        "aggregated_finding_reviews",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "case_id",
            sa.String(36),
            sa.ForeignKey("cases.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("finding_id", sa.String(100), nullable=False),
        sa.Column("action", sa.String(50), nullable=False),
        sa.Column("reviewer_id", sa.String(100), nullable=False),
        sa.Column("comment", sa.Text(), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("previous_status", sa.String(50), nullable=False),
        sa.Column("new_status", sa.String(50), nullable=False),
    )
    op.create_index(
        "ix_aggregated_finding_reviews_case_id",
        "aggregated_finding_reviews",
        ["case_id"],
    )
    op.create_index(
        "ix_aggregated_finding_reviews_finding_id",
        "aggregated_finding_reviews",
        ["finding_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_aggregated_finding_reviews_finding_id",
        table_name="aggregated_finding_reviews",
    )
    op.drop_index(
        "ix_aggregated_finding_reviews_case_id",
        table_name="aggregated_finding_reviews",
    )
    op.drop_table("aggregated_finding_reviews")

    with op.batch_alter_table("investigation_dossiers") as batch_op:
        batch_op.drop_column("dossier_payload")
        batch_op.drop_column("unresolved_questions")
        batch_op.drop_column("sections")
        batch_op.drop_column("content_hash")
        batch_op.drop_column("scope_and_purpose")
        batch_op.drop_column("title")

