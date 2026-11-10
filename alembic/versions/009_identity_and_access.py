"""Enterprise Identity, Authentication & Case RBAC Authorization Foundation.

Revision ID: 009_identity_and_access
Revises: 008_evidence_dossier
Create Date: 2026-11-10 16:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "009_identity_and_access"
down_revision: str | None = "008_evidence_dossier"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Create organizations table
    op.create_table(
        "organizations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(100), unique=True, nullable=False),
        sa.Column("slug", sa.String(100), unique=True, nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="1", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_organizations_slug", "organizations", ["slug"])

    # 2. Create users table
    op.create_table(
        "users",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("email", sa.String(255), unique=True, nullable=False),
        sa.Column("username", sa.String(100), unique=True, nullable=False),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("full_name", sa.String(255), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="1", nullable=False),
        sa.Column("system_role", sa.String(32), server_default="USER", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_users_email", "users", ["email"])
    op.create_index("ix_users_username", "users", ["username"])

    # 3. Create organization_memberships table
    op.create_table(
        "organization_memberships",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "organization_id",
            sa.String(36),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("role", sa.String(32), server_default="MEMBER", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("organization_id", "user_id", name="uq_org_member"),
    )
    op.create_index("ix_org_members_org_id", "organization_memberships", ["organization_id"])
    op.create_index("ix_org_members_user_id", "organization_memberships", ["user_id"])

    # 4. Create case_memberships table
    op.create_table(
        "case_memberships",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "case_id",
            sa.String(36),
            sa.ForeignKey("cases.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("role", sa.String(32), server_default="VIEWER", nullable=False),
        sa.Column("assigned_by", sa.String(36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("case_id", "user_id", name="uq_case_member"),
    )
    op.create_index("ix_case_members_case_id", "case_memberships", ["case_id"])
    op.create_index("ix_case_members_user_id", "case_memberships", ["user_id"])
    op.create_index("ix_case_members_role", "case_memberships", ["role"])

    # 5. Create refresh_tokens table
    op.create_table(
        "refresh_tokens",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "user_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("token_hash", sa.String(64), unique=True, nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_revoked", sa.Boolean(), server_default="0", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("replaced_by_token_id", sa.String(36), nullable=True),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("user_agent", sa.String(500), nullable=True),
    )
    op.create_index("ix_refresh_tokens_user_id", "refresh_tokens", ["user_id"])
    op.create_index("ix_refresh_tokens_token_hash", "refresh_tokens", ["token_hash"])

    # 6. Create authentication_events table
    op.create_table(
        "authentication_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), nullable=True),
        sa.Column("event_type", sa.String(50), nullable=False),
        sa.Column("username_attempted", sa.String(255), nullable=True),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("user_agent", sa.String(500), nullable=True),
        sa.Column("details", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_auth_events_user_id", "authentication_events", ["user_id"])
    op.create_index("ix_auth_events_event_type", "authentication_events", ["event_type"])

    # 7. Add organization_id to cases table
    with op.batch_alter_table("cases") as batch_op:
        batch_op.add_column(
            sa.Column(
                "organization_id",
                sa.String(36),
                sa.ForeignKey("organizations.id", ondelete="SET NULL", name="fk_cases_organization_id"),
                nullable=True,
            )
        )
        batch_op.create_index("ix_cases_organization_id", ["organization_id"])


def downgrade() -> None:
    with op.batch_alter_table("cases") as batch_op:
        batch_op.drop_index("ix_cases_organization_id")
        batch_op.drop_constraint("fk_cases_organization_id", type_="foreignkey")
        batch_op.drop_column("organization_id")

    op.drop_index("ix_auth_events_event_type", table_name="authentication_events")
    op.drop_index("ix_auth_events_user_id", table_name="authentication_events")
    op.drop_table("authentication_events")

    op.drop_index("ix_refresh_tokens_token_hash", table_name="refresh_tokens")
    op.drop_index("ix_refresh_tokens_user_id", table_name="refresh_tokens")
    op.drop_table("refresh_tokens")

    op.drop_index("ix_case_members_role", table_name="case_memberships")
    op.drop_index("ix_case_members_user_id", table_name="case_memberships")
    op.drop_index("ix_case_members_case_id", table_name="case_memberships")
    op.drop_table("case_memberships")

    op.drop_index("ix_org_members_user_id", table_name="organization_memberships")
    op.drop_index("ix_org_members_org_id", table_name="organization_memberships")
    op.drop_table("organization_memberships")

    op.drop_index("ix_users_username", table_name="users")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")

    op.drop_index("ix_organizations_slug", table_name="organizations")
    op.drop_table("organizations")

