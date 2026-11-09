"""Categorical confidence preservation and snapshot provenance.

Revision ID: 003_confidence_and_snapshot_provenance
Revises: 002_architecture_hardening
Create Date: 2026-11-07 16:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "003_confidence_and_snapshot_provenance"
down_revision: str | None = "002_architecture_hardening"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Add categorical confidence and source to forensic_findings
    with op.batch_alter_table("forensic_findings") as batch_op:
        batch_op.add_column(sa.Column("categorical_confidence", sa.String(50), nullable=True))
        batch_op.add_column(sa.Column("confidence_source", sa.String(100), nullable=True))
        batch_op.add_column(
            sa.Column("confidence_calibration_method", sa.String(100), nullable=True)
        )

    # 2. Add categorical confidence and source to evidence_nodes
    with op.batch_alter_table("evidence_nodes") as batch_op:
        batch_op.add_column(sa.Column("categorical_confidence", sa.String(50), nullable=True))
        batch_op.add_column(sa.Column("confidence_source", sa.String(100), nullable=True))

    # 3. Add snapshot_sha256 to processing_runs
    with op.batch_alter_table("processing_runs") as batch_op:
        batch_op.add_column(sa.Column("snapshot_sha256", sa.String(64), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("processing_runs") as batch_op:
        batch_op.drop_column("snapshot_sha256")

    with op.batch_alter_table("evidence_nodes") as batch_op:
        batch_op.drop_column("confidence_source")
        batch_op.drop_column("categorical_confidence")

    with op.batch_alter_table("forensic_findings") as batch_op:
        batch_op.drop_column("confidence_calibration_method")
        batch_op.drop_column("confidence_source")
        batch_op.drop_column("categorical_confidence")
