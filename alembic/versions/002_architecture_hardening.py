"""Architecture hardening: head checkpointing, finding-evidence links, and unique constraints.

Revision ID: 002_architecture_hardening
Revises: 001_initial_schema
Create Date: 2026-11-07 15:00:00.000000

"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "002_architecture_hardening"
down_revision: Union[str, None] = "001_initial_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Audit Checkpoints table
    op.create_table(
        "audit_checkpoints",
        sa.Column(
            "case_id",
            sa.String(36),
            sa.ForeignKey("cases.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("head_event_id", sa.String(36), nullable=False),
        sa.Column("head_event_hash", sa.String(64), nullable=False),
        sa.Column("event_count", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    # 2. Finding Evidence Links association table
    op.create_table(
        "finding_evidence_links",
        sa.Column(
            "finding_id",
            sa.String(36),
            sa.ForeignKey("forensic_findings.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "evidence_id",
            sa.String(36),
            sa.ForeignKey("evidence_nodes.id", ondelete="CASCADE"),
            primary_key=True,
        ),
    )

    # 3. Add sequence_number and unique constraint to audit_events
    with op.batch_alter_table("audit_events") as batch_op:
        batch_op.add_column(
            sa.Column("sequence_number", sa.Integer(), nullable=False, server_default="1")
        )
        batch_op.create_unique_constraint("uq_audit_case_seq", ["case_id", "sequence_number"])

    # 4. Add unique constraint to investigation_dossiers
    with op.batch_alter_table("investigation_dossiers") as batch_op:
        batch_op.create_unique_constraint("uq_dossier_case_version", ["case_id", "version"])


def downgrade() -> None:
    with op.batch_alter_table("investigation_dossiers") as batch_op:
        batch_op.drop_constraint("uq_dossier_case_version", type_="unique")

    with op.batch_alter_table("audit_events") as batch_op:
        batch_op.drop_constraint("uq_audit_case_seq", type_="unique")
        batch_op.drop_column("sequence_number")

    op.drop_table("finding_evidence_links")
    op.drop_table("audit_checkpoints")
