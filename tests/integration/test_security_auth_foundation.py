"""Enterprise Security, Identity, Authentication & Case-Scoped RBAC Test Suite.

Comprehensive validation of the 20 security requirements specified in Phase 4E.1:
1. Valid login (Argon2id verification, issues JWT access token + secure refresh token)
2. Invalid login (generic error message prevents username enumeration)
3. Password hashing verification (Argon2id format, correct parameters, salt uniqueness)
4. Expired access token rejection (401 response)
5. Refresh rotation (refresh token single-use, returns new access token + new refresh token)
6. Refresh-token reuse detection (reusing revoked refresh token invalidates all sessions for user)
7. Logout invalidation (revokes refresh token, cannot be reused)
8. Disabled account denial (is_active=False blocked immediately)
9. Role-based access (ADMIN vs INVESTIGATOR vs REVIEWER vs VIEWER on case-scoped actions)
10. Case membership enforcement (non-members denied access to case data)
11. Cross-case access denial (user authorized for Case A denied access to Case B)
12. Cross-organization isolation (user in Org A denied access to Case in Org B)
13. Privilege escalation prevention (investigator cannot promote self to admin or assign roles)
14. Archived-case write restrictions (mutations rejected on archived case)
15. Authenticated audit attribution (mutating actions record authenticated user ID, not asserted body identity)
16. Unauthenticated API denial (401 on protected endpoints without token)
17. Rate-limit behavior (lockout triggered after max failed login attempts)
18. Migration upgrade and downgrade (Alembic migration 009 applies cleanly and reverts cleanly)
19. Existing lifecycle regression (end-to-end investigation lifecycle runs with authentication)
20. Frontend protected-route component test (referenced via AuthIntegration.test.tsx)
"""

from __future__ import annotations

import io
import sqlite3
from pathlib import Path

from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from alembic import command
from document_intelligence.domain.enums import CaseStatus
from document_intelligence.domain.models.auth import CaseRole, SystemRole
from document_intelligence.infrastructure.persistence.database import get_db
from document_intelligence.infrastructure.persistence.models import (
    AuthenticationEventModel,
    CaseMembershipModel,
    CaseModel,
    OrganizationMembershipModel,
    OrganizationModel,
    UserModel,
)
from document_intelligence.main import create_app
from document_intelligence.modules.auth.password import PasswordService
from document_intelligence.modules.auth.rate_limiter import AuthRateLimiter
from document_intelligence.modules.auth.tokens import TokenService


def make_clean_client(db_session: Session) -> TestClient:
    """Create a pristine TestClient that enforces real authentication without conftest overrides."""
    app = create_app()

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    # Intentionally do not override get_current_user
    return TestClient(app)


# -----------------------------------------------------------------------------
# Scenario 1: Valid Login
# -----------------------------------------------------------------------------


def test_01_valid_login_issues_access_and_refresh_tokens(db_session: Session) -> None:
    client = make_clean_client(db_session)
    pw_service = PasswordService()

    # Register/create user
    user = UserModel(
        id="usr-test-01",
        email="examiner1@agency.gov",
        username="examiner1",
        hashed_password=pw_service.hash_password("SuperSecret123!"),
        full_name="Special Agent Mulder",
        is_active=True,
        system_role=SystemRole.USER.value,
    )
    db_session.add(user)
    db_session.commit()

    # Authenticate via username
    res_user = client.post(
        "/api/v1/auth/login",
        json={"username_or_email": "examiner1", "password": "SuperSecret123!"},
    )
    assert res_user.status_code == 200
    data_user = res_user.json()
    assert "access_token" in data_user
    assert "refresh_token" in data_user
    assert data_user["token_type"] == "bearer"
    assert data_user["user"]["username"] == "examiner1"
    assert "access_token" in res_user.cookies
    assert "refresh_token" in res_user.cookies

    # Authenticate via email
    res_email = client.post(
        "/api/v1/auth/login",
        json={"username_or_email": "examiner1@agency.gov", "password": "SuperSecret123!"},
    )
    assert res_email.status_code == 200
    data_email = res_email.json()
    assert data_email["user"]["email"] == "examiner1@agency.gov"


# -----------------------------------------------------------------------------
# Scenario 2: Invalid Login (Generic Error, Username Enumeration Defense)
# -----------------------------------------------------------------------------


def test_02_invalid_login_generic_error_prevents_enumeration(db_session: Session) -> None:
    client = make_clean_client(db_session)
    pw_service = PasswordService()

    user = UserModel(
        id="usr-test-02",
        email="realuser@agency.gov",
        username="realuser",
        hashed_password=pw_service.hash_password("CorrectPassword!"),
        full_name="Real Agent",
        is_active=True,
        system_role=SystemRole.USER.value,
    )
    db_session.add(user)
    db_session.commit()

    # Case A: Real user, incorrect password
    res_wrong_pw = client.post(
        "/api/v1/auth/login",
        json={"username_or_email": "realuser", "password": "WrongPassword!"},
    )
    assert res_wrong_pw.status_code == 401
    err_wrong_pw = res_wrong_pw.json()["error"]["message"]

    # Case B: Non-existent user
    res_no_user = client.post(
        "/api/v1/auth/login",
        json={"username_or_email": "ghost_user", "password": "WrongPassword!"},
    )
    assert res_no_user.status_code == 401
    err_no_user = res_no_user.json()["error"]["message"]

    # Messages must be identical to prevent username enumeration attacks
    assert err_wrong_pw == err_no_user == "Invalid username or password."


# -----------------------------------------------------------------------------
# Scenario 3: Password Hashing Verification (Argon2id format & parameters)
# -----------------------------------------------------------------------------


def test_03_password_hashing_argon2id_format_and_salt_uniqueness() -> None:
    pw_service = PasswordService()
    raw = "ForensicSecurePassword2026!"

    hash1 = pw_service.hash_password(raw)
    hash2 = pw_service.hash_password(raw)

    # Must start with RFC 9106 Argon2id identifier
    assert hash1.startswith("$argon2id$")
    assert "$m=65536,t=3,p=4$" in hash1

    # Salts must be cryptographically distinct
    assert hash1 != hash2

    # Verification must succeed
    assert pw_service.verify_password(raw, hash1) is True
    assert pw_service.verify_password(raw, hash2) is True
    assert pw_service.verify_password("TamperedPassword!", hash1) is False


# -----------------------------------------------------------------------------
# Scenario 4: Expired Access Token Rejection
# -----------------------------------------------------------------------------


def test_04_expired_access_token_rejection(db_session: Session) -> None:
    client = make_clean_client(db_session)
    token_service = TokenService(access_token_expire_minutes=-10)  # already expired

    expired_token, _ = token_service.create_access_token(
        user_id="usr-expired",
        email="expired@test.com",
        username="expired_user",
        system_role="USER",
    )

    res = client.get("/api/v1/cases", headers={"Authorization": f"Bearer {expired_token}"})
    assert res.status_code == 401
    assert "expired" in res.json()["error"]["message"].lower()


# -----------------------------------------------------------------------------
# Scenario 5: Refresh Rotation (Single-Use Token Rotation)
# -----------------------------------------------------------------------------


def test_05_refresh_token_rotation_single_use(db_session: Session) -> None:
    client = make_clean_client(db_session)
    pw_service = PasswordService()

    user = UserModel(
        id="usr-test-05",
        email="rotate@agency.gov",
        username="rotate_user",
        hashed_password=pw_service.hash_password("Pass12345!"),
        full_name="Rotation Tester",
        is_active=True,
        system_role=SystemRole.USER.value,
    )
    db_session.add(user)
    db_session.commit()

    # 1. Login to obtain initial tokens
    login_res = client.post(
        "/api/v1/auth/login",
        json={"username_or_email": "rotate_user", "password": "Pass12345!"},
    )
    assert login_res.status_code == 200
    token1 = login_res.json()
    refresh_1 = token1["refresh_token"]

    # 2. Rotate refresh token
    refresh_res = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_1})
    assert refresh_res.status_code == 200
    token2 = refresh_res.json()
    refresh_2 = token2["refresh_token"]

    # New tokens must differ from original
    assert refresh_2 != refresh_1
    assert token2["access_token"] != token1["access_token"]

    # 3. Old refresh token cannot be used again normally
    old_res = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_1})
    assert old_res.status_code == 401


# -----------------------------------------------------------------------------
# Scenario 6: Refresh Token Reuse Detection (Invalidates All Sessions)
# -----------------------------------------------------------------------------


def test_06_refresh_token_reuse_detection_invalidates_all_sessions(db_session: Session) -> None:
    client = make_clean_client(db_session)
    pw_service = PasswordService()

    user = UserModel(
        id="usr-test-06",
        email="breach@agency.gov",
        username="breach_victim",
        hashed_password=pw_service.hash_password("Pass12345!"),
        full_name="Breach Target",
        is_active=True,
        system_role=SystemRole.USER.value,
    )
    db_session.add(user)
    db_session.commit()

    # Login
    l_res = client.post(
        "/api/v1/auth/login",
        json={"username_or_email": "breach_victim", "password": "Pass12345!"},
    )
    initial_refresh = l_res.json()["refresh_token"]

    # Legitimate rotation -> new active refresh token
    r1_res = client.post("/api/v1/auth/refresh", json={"refresh_token": initial_refresh})
    active_refresh = r1_res.json()["refresh_token"]

    # Attacker attempts to replay initial_refresh
    replay_res = client.post("/api/v1/auth/refresh", json={"refresh_token": initial_refresh})
    assert replay_res.status_code == 401
    assert "reuse detected" in replay_res.json()["error"]["message"].lower()

    # Verification: Legitimate active token must now ALSO be invalidated
    subsequent_res = client.post("/api/v1/auth/refresh", json={"refresh_token": active_refresh})
    assert subsequent_res.status_code == 401

    # Security event recorded in database
    security_events = (
        db_session.query(AuthenticationEventModel)
        .filter(
            AuthenticationEventModel.user_id == user.id,
            AuthenticationEventModel.event_type == "REFRESH_REUSE_DETECTED",
        )
        .all()
    )
    assert len(security_events) >= 1


# -----------------------------------------------------------------------------
# Scenario 7: Logout Invalidation
# -----------------------------------------------------------------------------


def test_07_logout_invalidation_revokes_refresh_token(db_session: Session) -> None:
    client = make_clean_client(db_session)
    pw_service = PasswordService()

    user = UserModel(
        id="usr-test-07",
        email="logout@agency.gov",
        username="logout_user",
        hashed_password=pw_service.hash_password("Pass12345!"),
        full_name="Logout User",
        is_active=True,
        system_role=SystemRole.USER.value,
    )
    db_session.add(user)
    db_session.commit()

    # Login
    l_res = client.post(
        "/api/v1/auth/login",
        json={"username_or_email": "logout_user", "password": "Pass12345!"},
    )
    refresh_token = l_res.json()["refresh_token"]

    # Logout
    logout_res = client.post("/api/v1/auth/logout", json={"refresh_token": refresh_token})
    assert logout_res.status_code == 200

    # Refresh token must be rejected
    r_res = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
    assert r_res.status_code == 401


# -----------------------------------------------------------------------------
# Scenario 8: Disabled Account Denial
# -----------------------------------------------------------------------------


def test_08_disabled_account_denied_login_and_api_access(db_session: Session) -> None:
    client = make_clean_client(db_session)
    pw_service = PasswordService()

    user = UserModel(
        id="usr-test-08",
        email="disabled@agency.gov",
        username="disabled_user",
        hashed_password=pw_service.hash_password("Pass12345!"),
        full_name="Disabled User",
        is_active=False,  # Suspended account
        system_role=SystemRole.USER.value,
    )
    db_session.add(user)
    db_session.commit()

    # Login attempt must fail
    res = client.post(
        "/api/v1/auth/login",
        json={"username_or_email": "disabled_user", "password": "Pass12345!"},
    )
    assert res.status_code == 401
    assert "disabled" in res.json()["error"]["message"].lower()

    # Token presented from before suspension must also be rejected
    token_service = TokenService()
    tok, _ = token_service.create_access_token(
        user_id=user.id,
        email=user.email,
        username=user.username,
        system_role=user.system_role,
    )
    api_res = client.get("/api/v1/cases", headers={"Authorization": f"Bearer {tok}"})
    assert api_res.status_code == 401
    assert "disabled" in api_res.json()["error"]["message"].lower()


# -----------------------------------------------------------------------------
# Scenario 9: Role-Based Access Control (ADMIN vs INVESTIGATOR vs REVIEWER vs VIEWER)
# -----------------------------------------------------------------------------


def test_09_case_scoped_rbac_hierarchy(db_session: Session) -> None:
    client = make_clean_client(db_session)
    pw_service = PasswordService()
    token_service = TokenService()

    # Create Case
    case = CaseModel(
        id="case-rbac-09",
        case_reference="CASE-RBAC-009",
        title="RBAC Tier Test Case",
        status=CaseStatus.ACTIVE.value,
    )
    db_session.add(case)

    # Helper to create user + token + membership
    def setup_user(user_id: str, role: CaseRole) -> str:
        u = UserModel(
            id=user_id,
            email=f"{user_id}@agency.gov",
            username=user_id,
            hashed_password=pw_service.hash_password("Password123!"),
            full_name=f"User {user_id}",
            is_active=True,
            system_role="USER",
        )
        m = CaseMembershipModel(
            id=f"mem-{user_id}",
            case_id=case.id,
            user_id=u.id,
            role=role.value,
        )
        db_session.add_all([u, m])
        db_session.commit()
        tok, _ = token_service.create_access_token(u.id, u.email, u.username, u.system_role)
        return tok

    viewer_tok = setup_user("usr_viewer", CaseRole.VIEWER)
    reviewer_tok = setup_user("usr_reviewer", CaseRole.REVIEWER)
    investigator_tok = setup_user("usr_investigator", CaseRole.INVESTIGATOR)
    admin_tok = setup_user("usr_admin", CaseRole.ADMIN)

    # 1. VIEWER tests:
    # Can read case details
    v_read = client.get(
        f"/api/v1/cases/{case.id}", headers={"Authorization": f"Bearer {viewer_tok}"}
    )
    assert v_read.status_code == 200

    # Cannot upload document (requires INVESTIGATOR)
    dummy_pdf = io.BytesIO(b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF")
    v_upload = client.post(
        f"/api/v1/cases/{case.id}/documents",
        files={"file": ("test.pdf", dummy_pdf, "application/pdf")},
        headers={"Authorization": f"Bearer {viewer_tok}"},
    )
    assert v_upload.status_code == 403

    # 2. REVIEWER tests:
    # Cannot upload document (requires INVESTIGATOR)
    dummy_pdf.seek(0)
    r_upload = client.post(
        f"/api/v1/cases/{case.id}/documents",
        files={"file": ("test.pdf", dummy_pdf, "application/pdf")},
        headers={"Authorization": f"Bearer {reviewer_tok}"},
    )
    assert r_upload.status_code == 403

    # Cannot archive case (requires ADMIN)
    r_archive = client.post(
        f"/api/v1/cases/{case.id}/archive",
        headers={"Authorization": f"Bearer {reviewer_tok}"},
    )
    assert r_archive.status_code == 403

    # 3. INVESTIGATOR tests:
    # Can upload document
    dummy_pdf.seek(0)
    i_upload = client.post(
        f"/api/v1/cases/{case.id}/documents",
        files={"file": ("test.pdf", dummy_pdf, "application/pdf")},
        headers={"Authorization": f"Bearer {investigator_tok}"},
    )
    assert i_upload.status_code == 201

    # Cannot add case members (requires ADMIN)
    i_add_member = client.post(
        f"/api/v1/cases/{case.id}/members",
        json={"user_id": "usr_viewer", "role": "ADMIN"},
        headers={"Authorization": f"Bearer {investigator_tok}"},
    )
    assert i_add_member.status_code == 403

    # 4. ADMIN tests:
    # Can add case members
    a_add_member = client.post(
        f"/api/v1/cases/{case.id}/members",
        json={"user_id": "usr_viewer", "role": "REVIEWER"},
        headers={"Authorization": f"Bearer {admin_tok}"},
    )
    assert a_add_member.status_code == 201
    assert a_add_member.json()["role"] == "REVIEWER"


# -----------------------------------------------------------------------------
# Scenario 10: Case Membership Enforcement (Non-members Denied)
# -----------------------------------------------------------------------------


def test_10_non_member_denied_access_to_case_data(db_session: Session) -> None:
    client = make_clean_client(db_session)
    token_service = TokenService()

    case = CaseModel(
        id="case-10-secret",
        case_reference="CASE-SECRET-010",
        title="Top Secret Investigation",
        status=CaseStatus.ACTIVE.value,
    )
    user = UserModel(
        id="usr-outsider-10",
        email="outsider@agency.gov",
        username="outsider",
        hashed_password="hashed_dummy",
        full_name="Outsider Agent",
        is_active=True,
        system_role="USER",
    )
    db_session.add_all([case, user])
    db_session.commit()

    token, _ = token_service.create_access_token(
        user.id, user.email, user.username, user.system_role
    )

    # Deny by default: 404 (does not leak existence to non-members)
    res = client.get(f"/api/v1/cases/{case.id}", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 404


# -----------------------------------------------------------------------------
# Scenario 11: Cross-Case Access Denial
# -----------------------------------------------------------------------------


def test_11_cross_case_access_denial(db_session: Session) -> None:
    client = make_clean_client(db_session)
    token_service = TokenService()

    case_a = CaseModel(
        id="case-11-a", case_reference="CASE-11-A", title="Case A", status=CaseStatus.ACTIVE.value
    )
    case_b = CaseModel(
        id="case-11-b", case_reference="CASE-11-B", title="Case B", status=CaseStatus.ACTIVE.value
    )
    user = UserModel(
        id="usr-case-a-only",
        email="case_a_only@agency.gov",
        username="case_a_only",
        hashed_password="pw",
        full_name="Case A Officer",
        is_active=True,
        system_role="USER",
    )
    mem_a = CaseMembershipModel(
        id="mem-11-a",
        case_id=case_a.id,
        user_id=user.id,
        role=CaseRole.INVESTIGATOR.value,
    )
    db_session.add_all([case_a, case_b, user, mem_a])
    db_session.commit()

    token, _ = token_service.create_access_token(
        user.id, user.email, user.username, user.system_role
    )

    # Access Case A: Allowed
    res_a = client.get(f"/api/v1/cases/{case_a.id}", headers={"Authorization": f"Bearer {token}"})
    assert res_a.status_code == 200

    # Access Case B: Denied (404)
    res_b = client.get(f"/api/v1/cases/{case_b.id}", headers={"Authorization": f"Bearer {token}"})
    assert res_b.status_code == 404


# -----------------------------------------------------------------------------
# Scenario 12: Cross-Organization Isolation
# -----------------------------------------------------------------------------


def test_12_cross_organization_isolation(db_session: Session) -> None:
    client = make_clean_client(db_session)
    token_service = TokenService()

    org_a = OrganizationModel(
        id="org-a", name="Department of Treasury", slug="treasury", is_active=True
    )
    org_b = OrganizationModel(id="org-b", name="Securities Commission", slug="sec", is_active=True)

    case_b = CaseModel(
        id="case-in-org-b",
        case_reference="CASE-ORG-B",
        title="SEC Private Case",
        organization_id=org_b.id,
        status=CaseStatus.ACTIVE.value,
    )
    user_a = UserModel(
        id="usr-in-org-a",
        email="treasury_agent@gov.org",
        username="treasury_agent",
        hashed_password="pw",
        full_name="Treasury Agent",
        is_active=True,
        system_role="USER",
    )
    mem_org_a = OrganizationMembershipModel(
        id="omem-a", organization_id=org_a.id, user_id=user_a.id, role="MEMBER"
    )

    db_session.add_all([org_a, org_b, case_b, user_a, mem_org_a])
    db_session.commit()

    token, _ = token_service.create_access_token(
        user_a.id, user_a.email, user_a.username, user_a.system_role
    )

    # User in Org A cannot access Case in Org B
    res = client.get(f"/api/v1/cases/{case_b.id}", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 404


# -----------------------------------------------------------------------------
# Scenario 13: Privilege Escalation Prevention
# -----------------------------------------------------------------------------


def test_13_privilege_escalation_prevention(db_session: Session) -> None:
    client = make_clean_client(db_session)
    token_service = TokenService()

    case = CaseModel(
        id="case-13",
        case_reference="CASE-13",
        title="Escalation Test",
        status=CaseStatus.ACTIVE.value,
    )
    investigator = UserModel(
        id="usr-inv-13",
        email="inv13@test.gov",
        username="inv13",
        hashed_password="pw",
        full_name="Investigator 13",
        is_active=True,
        system_role="USER",
    )
    mem = CaseMembershipModel(
        id="mem-inv-13",
        case_id=case.id,
        user_id=investigator.id,
        role=CaseRole.INVESTIGATOR.value,
    )
    db_session.add_all([case, investigator, mem])
    db_session.commit()

    token, _ = token_service.create_access_token(
        investigator.id, investigator.email, investigator.username, investigator.system_role
    )

    # Investigator attempts to promote self to ADMIN
    res = client.post(
        f"/api/v1/cases/{case.id}/members",
        json={"user_id": investigator.id, "role": "ADMIN"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 403


# -----------------------------------------------------------------------------
# Scenario 14: Archived-Case Write Restrictions
# -----------------------------------------------------------------------------


def test_14_archived_case_write_restrictions(db_session: Session) -> None:
    client = make_clean_client(db_session)
    token_service = TokenService()

    case = CaseModel(
        id="case-14-archived",
        case_reference="CASE-14-ARCH",
        title="Archived Investigation",
        status=CaseStatus.ARCHIVED.value,  # Terminal state
    )
    admin_user = UserModel(
        id="usr-admin-14",
        email="admin14@test.gov",
        username="admin14",
        hashed_password="pw",
        full_name="Case Administrator",
        is_active=True,
        system_role="USER",
    )
    mem = CaseMembershipModel(
        id="mem-14",
        case_id=case.id,
        user_id=admin_user.id,
        role=CaseRole.ADMIN.value,
    )
    db_session.add_all([case, admin_user, mem])
    db_session.commit()

    token, _ = token_service.create_access_token(
        admin_user.id, admin_user.email, admin_user.username, admin_user.system_role
    )

    # Read operations permitted
    read_res = client.get(f"/api/v1/cases/{case.id}", headers={"Authorization": f"Bearer {token}"})
    assert read_res.status_code == 200

    # Mutation operations strictly forbidden even for ADMIN
    dummy_pdf = io.BytesIO(b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF")
    write_res = client.post(
        f"/api/v1/cases/{case.id}/documents",
        files={"file": ("doc.pdf", dummy_pdf, "application/pdf")},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert write_res.status_code in (403, 422)
    assert "archived" in write_res.json()["error"]["message"].lower()


# -----------------------------------------------------------------------------
# Scenario 15: Authenticated Audit Attribution
# -----------------------------------------------------------------------------


def test_15_authenticated_audit_attribution(db_session: Session) -> None:
    client = make_clean_client(db_session)
    token_service = TokenService()

    case = CaseModel(
        id="case-15",
        case_reference="CASE-15-AUDIT",
        title="Audit Attribution Case",
        status=CaseStatus.ACTIVE.value,
    )
    investigator = UserModel(
        id="usr-principal-99",
        email="principal@agency.gov",
        username="special_agent_99",
        hashed_password="pw",
        full_name="Principal Investigator",
        is_active=True,
        system_role="USER",
    )
    mem = CaseMembershipModel(
        id="mem-15",
        case_id=case.id,
        user_id=investigator.id,
        role=CaseRole.INVESTIGATOR.value,
    )
    db_session.add_all([case, investigator, mem])
    db_session.commit()

    token, _ = token_service.create_access_token(
        investigator.id, investigator.email, investigator.username, investigator.system_role
    )

    # Upload document passing an asserted body value created_by="imposter_id"
    dummy_pdf = io.BytesIO(b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF")
    upload_res = client.post(
        f"/api/v1/cases/{case.id}/documents",
        data={"created_by": "imposter_attacker_identity"},
        files={"file": ("evidence.pdf", dummy_pdf, "application/pdf")},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert upload_res.status_code == 201
    doc_data = upload_res.json()

    # The persisted created_by must match the authenticated principal ID, NOT the imposter body string!
    assert doc_data["created_by"] == investigator.id


# -----------------------------------------------------------------------------
# Scenario 16: Unauthenticated API Denial
# -----------------------------------------------------------------------------


def test_16_unauthenticated_api_denial(db_session: Session) -> None:
    client = make_clean_client(db_session)

    # 1. No Authorization header -> 401
    res1 = client.get("/api/v1/cases")
    assert res1.status_code == 401

    # 2. Malformed token -> 401
    res2 = client.get("/api/v1/cases", headers={"Authorization": "Bearer bad.token.here"})
    assert res2.status_code == 401

    # 3. Random case endpoint without token -> 401
    res3 = client.get("/api/v1/cases/random-id/findings")
    assert res3.status_code == 401


# -----------------------------------------------------------------------------
# Scenario 17: Rate-Limit Behavior (Lockout After Max Attempts)
# -----------------------------------------------------------------------------


def test_17_auth_rate_limiting_lockout() -> None:
    limiter = AuthRateLimiter(max_attempts=3, window_seconds=60)
    key = "192.168.1.100:test_target"

    assert limiter.is_rate_limited(key) is False

    limiter.record_failure(key)
    limiter.record_failure(key)
    assert limiter.is_rate_limited(key) is False

    limiter.record_failure(key)
    # Threshold reached
    assert limiter.is_rate_limited(key) is True
    assert limiter.get_remaining_lockout_seconds(key) > 0

    # Successful login resets the counter
    limiter.record_success(key)
    assert limiter.is_rate_limited(key) is False


# -----------------------------------------------------------------------------
# Scenario 18: Migration Upgrade and Downgrade
# -----------------------------------------------------------------------------


def test_18_alembic_009_identity_migration_upgrade_and_downgrade(tmp_path: Path) -> None:
    db_file = tmp_path / "test_migration_009.db"
    db_url = f"sqlite:///{db_file.as_posix()}"

    alembic_cfg = Config("alembic.ini")
    alembic_cfg.set_main_option("sqlalchemy.url", db_url)

    # 1. Upgrade to head (009)
    command.upgrade(alembic_cfg, "head")

    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()

    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = {row[0] for row in cursor.fetchall()}
    assert "users" in tables
    assert "organizations" in tables
    assert "case_memberships" in tables
    assert "refresh_tokens" in tables
    assert "authentication_events" in tables

    # Verify columns in users table
    cursor.execute("PRAGMA table_info(users)")
    user_cols = {row[1] for row in cursor.fetchall()}
    assert "hashed_password" in user_cols
    assert "system_role" in user_cols
    conn.close()

    # 2. Downgrade to 008
    command.downgrade(alembic_cfg, "008")

    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    downgraded_tables = {row[0] for row in cursor.fetchall()}
    assert "users" not in downgraded_tables
    assert "case_memberships" not in downgraded_tables
    conn.close()

    # 3. Re-upgrade cleanly
    command.upgrade(alembic_cfg, "head")


# -----------------------------------------------------------------------------
# Scenario 19: Existing Lifecycle Regression Test
# -----------------------------------------------------------------------------


def test_19_complete_investigation_lifecycle_with_authentication(db_session: Session) -> None:
    client = make_clean_client(db_session)

    # 1. Register investigator
    reg_res = client.post(
        "/api/v1/auth/register",
        json={
            "email": "lifecycle_investigator@agency.gov",
            "username": "lifecycle_inv",
            "password": "SecurePassword123!",
            "full_name": "Lifecycle Investigator",
        },
    )
    assert reg_res.status_code == 201
    user_data = reg_res.json()

    # 2. Login
    login_res = client.post(
        "/api/v1/auth/login",
        json={"username_or_email": "lifecycle_inv", "password": "SecurePassword123!"},
    )
    assert login_res.status_code == 200
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 3. Create Case
    case_res = client.post(
        "/api/v1/cases",
        json={"title": "Authenticated Lifecycle Investigation"},
        headers=headers,
    )
    assert case_res.status_code == 201
    case_id = case_res.json()["id"]

    # 4. Upload Document
    dummy_pdf = io.BytesIO(b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF")
    doc_res = client.post(
        f"/api/v1/cases/{case_id}/documents",
        files={"file": ("invoice.pdf", dummy_pdf, "application/pdf")},
        headers=headers,
    )
    assert doc_res.status_code == 201

    # 5. Verify creator assigned as ADMIN member
    members_res = client.get(f"/api/v1/cases/{case_id}/members", headers=headers)
    assert members_res.status_code == 200
    members = members_res.json()
    assert len(members) == 1
    assert members[0]["user_id"] == user_data["id"]
    assert members[0]["role"] == "ADMIN"

    # 6. Archive Case
    archive_res = client.post(f"/api/v1/cases/{case_id}/archive", headers=headers)
    assert archive_res.status_code == 200
    assert archive_res.json()["status"] == "ARCHIVED"


# -----------------------------------------------------------------------------
# Scenario 20: Reference to Frontend Auth Integration Test
# -----------------------------------------------------------------------------


def test_20_frontend_auth_integration_test_verification() -> None:
    """Confirms that the dedicated frontend integration test file exists and contains

    the test suite for protected route redirection, login form submission, error banners,
    and Header profile display.
    """
    frontend_test_path = Path("frontend/src/test/AuthIntegration.test.tsx")
    assert frontend_test_path.exists(), "Frontend auth integration test file must exist."
    content = frontend_test_path.read_text(encoding="utf-8")
    assert "Enterprise Authentication & RBAC Frontend Integration" in content
    assert "redirects unauthenticated user to /login" in content
    assert "renders user profile, system role, and executes logout in Header" in content
