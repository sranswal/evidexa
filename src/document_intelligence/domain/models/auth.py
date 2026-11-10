"""Domain models and schemas for Enterprise Identity, Authentication, and RBAC."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from document_intelligence.domain.identifiers import generate_id, utc_now


class CaseRole(StrEnum):
    """Case-scoped role-based access control tiers."""

    ADMIN = "ADMIN"
    INVESTIGATOR = "INVESTIGATOR"
    REVIEWER = "REVIEWER"
    VIEWER = "VIEWER"

    @classmethod
    def can_read(cls, role: CaseRole) -> bool:
        """All roles have read access."""
        return True

    @classmethod
    def can_mutate(cls, role: CaseRole) -> bool:
        """Only INVESTIGATOR and ADMIN can ingest and process documents."""
        return role in (cls.INVESTIGATOR, cls.ADMIN)

    @classmethod
    def can_review(cls, role: CaseRole) -> bool:
        """Only REVIEWER and ADMIN can record review decisions and approve dossiers."""
        return role in (cls.REVIEWER, cls.ADMIN)

    @classmethod
    def can_administer(cls, role: CaseRole) -> bool:
        """Only ADMIN can manage memberships, archive cases, or delete case resources."""
        return role == cls.ADMIN


class SystemRole(StrEnum):
    """Platform-wide system privileges."""

    SYSTEM_ADMIN = "SYSTEM_ADMIN"
    USER = "USER"


class AuthEventType(StrEnum):
    """Security and authentication audit events."""

    LOGIN_SUCCESS = "LOGIN_SUCCESS"
    LOGIN_FAILED = "LOGIN_FAILED"
    LOGOUT = "LOGOUT"
    TOKEN_REFRESH = "TOKEN_REFRESH"
    REFRESH_REUSE_DETECTED = "REFRESH_REUSE_DETECTED"
    ACCESS_DENIED = "ACCESS_DENIED"


class User(BaseModel):
    """Authenticated user principal."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(default_factory=generate_id)
    email: str
    username: str
    full_name: str
    is_active: bool = True
    system_role: SystemRole = SystemRole.USER
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class Organization(BaseModel):
    """Multi-tenant security boundary."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(default_factory=generate_id)
    name: str
    slug: str
    is_active: bool = True
    created_at: datetime = Field(default_factory=utc_now)


class OrganizationMembership(BaseModel):
    """User membership in an organization."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(default_factory=generate_id)
    organization_id: str
    user_id: str
    role: str = "MEMBER"
    created_at: datetime = Field(default_factory=utc_now)


class CaseMembership(BaseModel):
    """Explicit user membership and RBAC role assignment for a case."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(default_factory=generate_id)
    case_id: str
    user_id: str
    role: CaseRole = CaseRole.VIEWER
    assigned_by: str | None = None
    created_at: datetime = Field(default_factory=utc_now)


class TokenPayload(BaseModel):
    """Decoded JWT claims."""

    sub: str
    email: str
    username: str
    system_role: str
    exp: int
    iat: int
    jti: str
    iss: str | None = None
    aud: str | None = None


class TokenResponse(BaseModel):
    """Authentication token response payload."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user: User


class LoginRequest(BaseModel):
    """User login credentials payload."""

    username_or_email: str = Field(min_length=1, max_length=255)
    password: str = Field(min_length=1, max_length=128)


class RegisterRequest(BaseModel):
    """User registration credentials payload."""

    email: str = Field(min_length=3, max_length=255)
    username: str = Field(min_length=3, max_length=100)
    password: str = Field(min_length=8, max_length=128)
    full_name: str = Field(min_length=1, max_length=255)


class RefreshTokenRequest(BaseModel):
    """Refresh token request payload."""

    refresh_token: str | None = None


class ChangePasswordRequest(BaseModel):
    """Payload to update user password."""

    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)


class AddCaseMemberRequest(BaseModel):
    """Payload to grant case membership to a user."""

    user_id: str
    role: CaseRole = CaseRole.VIEWER


class CaseMemberResponse(BaseModel):
    """Representation of a case member with user profile."""

    id: str
    case_id: str
    user_id: str
    username: str
    email: str
    full_name: str
    role: CaseRole
    assigned_by: str | None = None
    created_at: datetime
