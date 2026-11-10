"""Database repository for users, organizations, case memberships, tokens, and audit events."""

from __future__ import annotations

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from document_intelligence.domain.identifiers import generate_id, utc_now
from document_intelligence.infrastructure.persistence.models import (
    AuthenticationEventModel,
    CaseMembershipModel,
    CaseModel,
    OrganizationMembershipModel,
    OrganizationModel,
    RefreshTokenModel,
    UserModel,
)


class AuthRepository:
    """Persistence operations for authentication, organizations, and RBAC memberships."""

    def __init__(self, db: Session) -> None:
        self.db = db

    # -------------------------------------------------------------------------
    # Users
    # -------------------------------------------------------------------------

    def get_user_by_id(self, user_id: str) -> UserModel | None:
        return self.db.get(UserModel, user_id)

    def get_user_by_email(self, email: str) -> UserModel | None:
        stmt = select(UserModel).where(UserModel.email == email.strip().lower())
        return self.db.scalars(stmt).first()

    def get_user_by_username(self, username: str) -> UserModel | None:
        stmt = select(UserModel).where(UserModel.username == username.strip().lower())
        return self.db.scalars(stmt).first()

    def get_user_by_identifier(self, identifier: str) -> UserModel | None:
        """Find user by either username or email in a case-insensitive manner."""
        ident = identifier.strip().lower()
        stmt = select(UserModel).where(or_(UserModel.username == ident, UserModel.email == ident))
        return self.db.scalars(stmt).first()

    def create_user(self, user: UserModel) -> UserModel:
        user.email = user.email.strip().lower()
        user.username = user.username.strip().lower()
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    def update_user(self, user: UserModel) -> UserModel:
        user.updated_at = utc_now()
        self.db.commit()
        self.db.refresh(user)
        return user

    # -------------------------------------------------------------------------
    # Organizations
    # -------------------------------------------------------------------------

    def get_or_create_default_org(self) -> OrganizationModel:
        """Retrieve or initialize the default tenant organization."""
        stmt = select(OrganizationModel).where(OrganizationModel.slug == "default")
        org = self.db.scalars(stmt).first()
        if not org:
            org = OrganizationModel(
                id=generate_id(),
                name="Default Forensic Organization",
                slug="default",
                is_active=True,
                created_at=utc_now(),
            )
            self.db.add(org)
            self.db.commit()
            self.db.refresh(org)
        return org

    def get_organization_by_id(self, org_id: str) -> OrganizationModel | None:
        return self.db.get(OrganizationModel, org_id)

    def create_organization(self, org: OrganizationModel) -> OrganizationModel:
        self.db.add(org)
        self.db.commit()
        self.db.refresh(org)
        return org

    def get_org_membership(self, org_id: str, user_id: str) -> OrganizationMembershipModel | None:
        stmt = select(OrganizationMembershipModel).where(
            OrganizationMembershipModel.organization_id == org_id,
            OrganizationMembershipModel.user_id == user_id,
        )
        return self.db.scalars(stmt).first()

    def add_org_membership(
        self, org_id: str, user_id: str, role: str = "MEMBER"
    ) -> OrganizationMembershipModel:
        membership = self.get_org_membership(org_id, user_id)
        if not membership:
            membership = OrganizationMembershipModel(
                id=generate_id(),
                organization_id=org_id,
                user_id=user_id,
                role=role,
                created_at=utc_now(),
            )
            self.db.add(membership)
            self.db.commit()
            self.db.refresh(membership)
        return membership

    # -------------------------------------------------------------------------
    # Case RBAC Memberships
    # -------------------------------------------------------------------------

    def get_case(self, case_id: str) -> CaseModel | None:
        return self.db.get(CaseModel, case_id)

    def get_case_membership(self, case_id: str, user_id: str) -> CaseMembershipModel | None:
        stmt = select(CaseMembershipModel).where(
            CaseMembershipModel.case_id == case_id,
            CaseMembershipModel.user_id == user_id,
        )
        return self.db.scalars(stmt).first()

    def add_or_update_case_membership(
        self,
        case_id: str,
        user_id: str,
        role: str,
        assigned_by: str | None = None,
    ) -> CaseMembershipModel:
        membership = self.get_case_membership(case_id, user_id)
        if membership:
            membership.role = role
            membership.assigned_by = assigned_by
        else:
            membership = CaseMembershipModel(
                id=generate_id(),
                case_id=case_id,
                user_id=user_id,
                role=role,
                assigned_by=assigned_by,
                created_at=utc_now(),
            )
            self.db.add(membership)
        self.db.commit()
        self.db.refresh(membership)
        return membership

    def remove_case_membership(self, case_id: str, user_id: str) -> bool:
        membership = self.get_case_membership(case_id, user_id)
        if membership:
            self.db.delete(membership)
            self.db.commit()
            return True
        return False

    def list_case_memberships(self, case_id: str) -> list[CaseMembershipModel]:
        stmt = (
            select(CaseMembershipModel)
            .where(CaseMembershipModel.case_id == case_id)
            .order_by(CaseMembershipModel.created_at.asc())
        )
        return list(self.db.scalars(stmt).all())

    def list_accessible_case_ids(self, user: UserModel) -> list[str] | None:
        """Return list of case IDs accessible to user, or None if system admin (can see all)."""
        if user.system_role == "SYSTEM_ADMIN":
            return None

        # Direct case memberships
        stmt = select(CaseMembershipModel.case_id).where(CaseMembershipModel.user_id == user.id)
        case_ids = set(self.db.scalars(stmt).all())

        # Organizations where user is ADMIN
        org_stmt = select(OrganizationMembershipModel.organization_id).where(
            OrganizationMembershipModel.user_id == user.id,
            OrganizationMembershipModel.role == "ADMIN",
        )
        admin_org_ids = list(self.db.scalars(org_stmt).all())
        if admin_org_ids:
            case_stmt = select(CaseModel.id).where(CaseModel.organization_id.in_(admin_org_ids))
            case_ids.update(self.db.scalars(case_stmt).all())

        return list(case_ids)

    # -------------------------------------------------------------------------
    # Refresh Tokens
    # -------------------------------------------------------------------------

    def store_refresh_token(self, token_model: RefreshTokenModel) -> RefreshTokenModel:
        self.db.add(token_model)
        self.db.commit()
        self.db.refresh(token_model)
        return token_model

    def get_refresh_token_by_hash(self, token_hash: str) -> RefreshTokenModel | None:
        stmt = select(RefreshTokenModel).where(RefreshTokenModel.token_hash == token_hash)
        return self.db.scalars(stmt).first()

    def get_refresh_token_by_id(self, token_id: str) -> RefreshTokenModel | None:
        return self.db.get(RefreshTokenModel, token_id)

    def revoke_refresh_token(
        self, token_model: RefreshTokenModel, replaced_by_id: str | None = None
    ) -> None:
        token_model.is_revoked = True
        if replaced_by_id:
            token_model.replaced_by_token_id = replaced_by_id
        self.db.commit()

    def revoke_all_user_tokens(self, user_id: str) -> int:
        """Revoke all active refresh tokens for user (e.g. upon token reuse breach or logout all)."""
        stmt = select(RefreshTokenModel).where(
            RefreshTokenModel.user_id == user_id,
            RefreshTokenModel.is_revoked == False,  # noqa: E712
        )
        tokens = list(self.db.scalars(stmt).all())
        for t in tokens:
            t.is_revoked = True
        self.db.commit()
        return len(tokens)

    # -------------------------------------------------------------------------
    # Authentication Events
    # -------------------------------------------------------------------------

    def record_auth_event(self, event: AuthenticationEventModel) -> AuthenticationEventModel:
        self.db.add(event)
        self.db.commit()
        return event
