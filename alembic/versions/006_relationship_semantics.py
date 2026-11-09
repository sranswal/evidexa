"""Relationship ontology, directionality, and evidentiary semantics hardening.

Revision ID: 006_relationship_semantics
Revises: 005_relationship_detection
Create Date: 2026-11-09 19:30:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "006_relationship_semantics"
down_revision: str | None = "005_relationship_detection"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Add ontology versioning, legacy tracking, status determination, and duplicate kind columns
    with op.batch_alter_table("detected_relationships") as batch_op:
        batch_op.add_column(
            sa.Column(
                "ontology_version",
                sa.String(20),
                server_default="2.0",
                nullable=False,
            )
        )
        batch_op.add_column(
            sa.Column(
                "legacy_relationship_type",
                sa.String(50),
                nullable=True,
            )
        )
        batch_op.add_column(
            sa.Column(
                "status_determination_method",
                sa.String(50),
                server_default="EVIDENTIARY_RULE",
                nullable=False,
            )
        )
        batch_op.add_column(
            sa.Column(
                "duplicate_kind",
                sa.String(50),
                nullable=True,
            )
        )

    # Historical data migration for existing rows (if any exist)
    conn = op.get_bind()
    # Check if table has rows to migrate
    inspector = sa.inspect(conn)
    if "detected_relationships" in inspector.get_table_names():
        # Update legacy ISSUED_BY records
        conn.execute(
            sa.text(
                """
                UPDATE detected_relationships
                SET legacy_relationship_type = relationship_type,
                    relationship_type = 'ISSUED',
                    ontology_version = '2.0'
                WHERE relationship_type = 'ISSUED_BY'
                """
            )
        )
        # Update legacy ISSUED_TO records
        conn.execute(
            sa.text(
                """
                UPDATE detected_relationships
                SET legacy_relationship_type = relationship_type,
                    relationship_type = 'BILLED_TO',
                    ontology_version = '2.0'
                WHERE relationship_type = 'ISSUED_TO'
                """
            )
        )
        # Update legacy ACCOUNT_HELD_BY records
        conn.execute(
            sa.text(
                """
                UPDATE detected_relationships
                SET legacy_relationship_type = relationship_type,
                    relationship_type = 'HELD_BY',
                    ontology_version = '2.0'
                WHERE relationship_type = 'ACCOUNT_HELD_BY'
                """
            )
        )
        # Update legacy SUPPLIES records where evidence was commercial flow or invoice co-occurrence
        conn.execute(
            sa.text(
                """
                UPDATE detected_relationships
                SET legacy_relationship_type = 'SUPPLIES',
                    relationship_type = 'INVOICED',
                    ontology_version = '2.0'
                WHERE relationship_type = 'SUPPLIES'
                  AND detection_method = 'COMMERCIAL_FLOW_RULE'
                """
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("detected_relationships") as batch_op:
        batch_op.drop_column("duplicate_kind")
        batch_op.drop_column("status_determination_method")
        batch_op.drop_column("legacy_relationship_type")
        batch_op.drop_column("ontology_version")
