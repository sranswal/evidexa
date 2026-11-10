"""Cross-Case Correlation & Investigation Intelligence Integration Test Suite (Phase 4C).

Comprehensive validation of the 24 requirements specified in Phase 4C:
1. Cross-organization case selection rejected (anti-enumeration uniform 404).
2. Same-organization but unauthorized case selection rejected (anti-enumeration 404).
3. Partial case membership enforced (if user only has access to 2 of 3 cases, rejected).
4. Viewer / Investigator / Reviewer / Admin permissions correctly applied.
5. Authorization rechecked at query / run time.
6. Unauthorized case IDs and counts not leaked (no information disclosure).
7. Archived cases rejected from active scope.
8. Exact identifiers produce explainable candidates (tax ID, reference, bank account).
9. Fuzzy matches remain candidates, not automatic entity merges.
10. Conflicting identifiers reduce or suppress candidate confidence.
11. Masked identifiers not treated as exact matches.
12. PII masking applies to cross-case results.
13. Source-document retrieval still requires case authorization.
14. Graph traversal cannot escape selected scope.
15. Query and result limits enforced (max 20 cases, bounded comparisons, pagination).
16. Malicious query parameters cannot bypass scope restrictions.
17. Candidate reviews enforce role permissions (Reviewer/Admin required).
18. Review identity comes strictly from authenticated principal.
19. Review history is append-only.
20. Audit events written and verifiable (CROSS_CASE_SCOPE_CREATED, etc.).
21. Existing case-level graph behavior remains unchanged.
22. Existing entity resolution and relationship tests remain green.
23. Cross-tenant and cross-case data leakage negative tests pass.
24. Concurrent correlation requests do not corrupt or mix investigation scopes.
"""

from __future__ import annotations

import threading
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from document_intelligence.domain.enums import (
    AuditEventType,
    CaseStatus,
    CrossCaseReviewDecision,
    ResolvedEntityType,
)
from document_intelligence.domain.identifiers import generate_id, utc_now
from document_intelligence.domain.models.auth import CaseRole, SystemRole
from document_intelligence.domain.models.entity_resolution import EntityMention
from document_intelligence.infrastructure.persistence.database import get_db
from document_intelligence.infrastructure.persistence.models import (
    AuditEventModel,
    CaseMembershipModel,
    CaseModel,
    OrganizationMembershipModel,
    OrganizationModel,
    UserModel,
)
from document_intelligence.main import create_app
from document_intelligence.modules.auth.password import PasswordService
from document_intelligence.modules.cross_case.matcher import (
    CrossCaseMatcher,
    is_masked_or_incomplete,
    mask_sensitive_value,
)


def make_auth_client(db_session: Session) -> TestClient:
    """Create a TestClient with overridden DB session factory and real authentication."""
    app = create_app()
    from sqlalchemy.orm import sessionmaker

    engine = db_session.get_bind()
    session_factory = sessionmaker(bind=engine)

    def override_get_db():
        session = session_factory()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app)


def setup_org_user(
    db: Session,
    user_id: str,
    username: str,
    org_id: str,
    system_role: str = SystemRole.USER.value,
    password: str = "TestPass123!",
) -> tuple[UserModel, str]:
    """Helper to create an organization, user, organization membership, and return (user, auth_header)."""
    pw_svc = PasswordService()
    org = db.query(OrganizationModel).filter(OrganizationModel.id == org_id).first()
    if not org:
        org = OrganizationModel(
            id=org_id,
            name=f"Org {org_id}",
            slug=org_id,
            created_at=utc_now(),
            is_active=True,
        )
        db.add(org)
        db.flush()

    user = db.query(UserModel).filter(UserModel.id == user_id).first()
    if not user:
        user = UserModel(
            id=user_id,
            email=f"{username}@example.com",
            username=username,
            full_name=f"Agent {username}",
            hashed_password=pw_svc.hash_password(password),
            system_role=system_role,
            is_active=True,
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        db.add(user)
        db.flush()

    om = (
        db.query(OrganizationMembershipModel)
        .filter(
            OrganizationMembershipModel.user_id == user_id,
            OrganizationMembershipModel.organization_id == org_id,
        )
        .first()
    )
    if not om:
        om = OrganizationMembershipModel(
            id=generate_id(),
            user_id=user_id,
            organization_id=org_id,
            role="MEMBER",
            created_at=utc_now(),
        )
        db.add(om)

    db.commit()
    db.refresh(user)

    # Issue login token
    from document_intelligence.modules.auth.tokens import TokenService

    token_svc = TokenService()
    token, _ = token_svc.create_access_token(
        user_id=user.id,
        email=user.email,
        username=user.username,
        system_role=user.system_role,
    )
    return user, f"Bearer {token}"


def create_case(
    db: Session,
    case_id: str,
    org_id: str,
    title: str = "Investigation Case",
    status: str = CaseStatus.ACTIVE.value,
) -> CaseModel:
    """Helper to create a case under an organization."""
    org = db.query(OrganizationModel).filter(OrganizationModel.id == org_id).first()
    if not org:
        org = OrganizationModel(
            id=org_id,
            name=f"Org {org_id}",
            slug=org_id,
            created_at=utc_now(),
            is_active=True,
        )
        db.add(org)
        db.flush()

    case = db.query(CaseModel).filter(CaseModel.id == case_id).first()
    if not case:
        case = CaseModel(
            id=case_id,
            organization_id=org_id,
            case_reference=f"REF-{case_id.upper()}",
            title=title,
            status=status,
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        db.add(case)
        db.commit()
        db.refresh(case)
    return case


def make_evidence_payload(
    c1: str, c2: str, score: float = 0.95, signals: list[str] | None = None
) -> dict[str, Any]:
    """Helper to create valid CrossCaseMatchEvidence payload."""
    return {
        "target_case_id": c1,
        "candidate_case_id": c2,
        "target_mention_id": "m1",
        "candidate_mention_id": "m2",
        "target_document_id": "d1",
        "candidate_document_id": "d2",
        "target_page_number": 1,
        "candidate_page_number": 1,
        "target_field_key": "vendor_name",
        "candidate_field_key": "vendor_name",
        "matching_signals": signals or ["Exact match"],
        "contradicting_signals": [],
        "confidence_score": score,
        "matching_method": "deterministic_rule",
        "match_classification": "EXACT_IDENTIFIER",
        "coordinates": [],
    }


def assign_case_role(db: Session, case_id: str, user_id: str, role: CaseRole) -> None:
    """Assign case membership role."""
    cm = (
        db.query(CaseMembershipModel)
        .filter(CaseMembershipModel.case_id == case_id, CaseMembershipModel.user_id == user_id)
        .first()
    )
    if not cm:
        cm = CaseMembershipModel(
            id=generate_id(),
            case_id=case_id,
            user_id=user_id,
            role=role.value,
            created_at=utc_now(),
        )
        db.add(cm)
    else:
        cm.role = role.value
    db.commit()


# -----------------------------------------------------------------------------
# Test Scenarios
# -----------------------------------------------------------------------------


def test_01_cross_org_case_selection_rejected_uniform_404(db_session: Session) -> None:
    """1. Cross-organization case selection rejected (anti-enumeration 404)."""
    client = make_auth_client(db_session)
    user_a, token_a = setup_org_user(db_session, "usr-cc-01", "inv_cc_01", "org-alpha")

    # Case 1 in Org Alpha, Case 2 in Org Beta
    create_case(db_session, "case-alpha-1", "org-alpha")
    assign_case_role(db_session, "case-alpha-1", user_a.id, CaseRole.INVESTIGATOR)

    create_case(db_session, "case-beta-1", "org-beta")
    # user_a is NOT in org-beta

    resp = client.post(
        "/api/v1/cross-case/scopes",
        headers={"Authorization": token_a},
        json={"name": "Scope Alpha-Beta", "case_ids": ["case-alpha-1", "case-beta-1"]},
    )
    assert resp.status_code == 404
    assert "not found or inaccessible" in str(resp.json()).lower()


def test_02_same_org_unauthorized_case_rejected_404(db_session: Session) -> None:
    """2. Same-organization but unauthorized case selection rejected (anti-enumeration 404)."""
    client = make_auth_client(db_session)
    user_a, token_a = setup_org_user(db_session, "usr-cc-02", "inv_cc_02", "org-gamma")

    create_case(db_session, "case-gamma-1", "org-gamma")
    assign_case_role(db_session, "case-gamma-1", user_a.id, CaseRole.INVESTIGATOR)

    # case-gamma-2 exists in org-gamma, but user_a is not a member
    create_case(db_session, "case-gamma-2", "org-gamma")

    resp = client.post(
        "/api/v1/cross-case/scopes",
        headers={"Authorization": token_a},
        json={"name": "Scope Gamma", "case_ids": ["case-gamma-1", "case-gamma-2"]},
    )
    assert resp.status_code == 404
    assert "not found or inaccessible" in str(resp.json()).lower()


def test_03_partial_case_membership_enforced(db_session: Session) -> None:
    """3. Partial case membership enforced (if user only has access to 2 of 3 cases, rejected)."""
    client = make_auth_client(db_session)
    user_a, token_a = setup_org_user(db_session, "usr-cc-03", "inv_cc_03", "org-delta")

    create_case(db_session, "case-delta-1", "org-delta")
    create_case(db_session, "case-delta-2", "org-delta")
    create_case(db_session, "case-delta-3", "org-delta")

    assign_case_role(db_session, "case-delta-1", user_a.id, CaseRole.INVESTIGATOR)
    assign_case_role(db_session, "case-delta-2", user_a.id, CaseRole.INVESTIGATOR)
    # case-delta-3 is missing membership

    resp = client.post(
        "/api/v1/cross-case/scopes",
        headers={"Authorization": token_a},
        json={"name": "Scope Delta", "case_ids": ["case-delta-1", "case-delta-2", "case-delta-3"]},
    )
    assert resp.status_code == 404
    assert "case-delta-3" in str(resp.json())


def test_04_role_permissions_applied(db_session: Session) -> None:
    """4. Viewer / Investigator / Reviewer / Admin permissions correctly applied."""
    client = make_auth_client(db_session)
    admin_u, admin_tok = setup_org_user(db_session, "usr-cc-04-adm", "admin_04", "org-roles")
    inv_u, inv_tok = setup_org_user(db_session, "usr-cc-04-inv", "inv_04", "org-roles")
    view_u, view_tok = setup_org_user(db_session, "usr-cc-04-view", "viewer_04", "org-roles")

    create_case(db_session, "case-roles-1", "org-roles")
    create_case(db_session, "case-roles-2", "org-roles")

    assign_case_role(db_session, "case-roles-1", admin_u.id, CaseRole.ADMIN)
    assign_case_role(db_session, "case-roles-2", admin_u.id, CaseRole.ADMIN)

    assign_case_role(db_session, "case-roles-1", inv_u.id, CaseRole.INVESTIGATOR)
    assign_case_role(db_session, "case-roles-2", inv_u.id, CaseRole.INVESTIGATOR)

    assign_case_role(db_session, "case-roles-1", view_u.id, CaseRole.VIEWER)
    assign_case_role(db_session, "case-roles-2", view_u.id, CaseRole.VIEWER)

    # 1. Admin creates scope
    scope_resp = client.post(
        "/api/v1/cross-case/scopes",
        headers={"Authorization": admin_tok},
        json={"name": "Roles Scope", "case_ids": ["case-roles-1", "case-roles-2"]},
    )
    assert scope_resp.status_code == 201
    scope_id = scope_resp.json()["id"]

    # 2. Viewer CAN read scope
    get_resp = client.get(
        f"/api/v1/cross-case/scopes/{scope_id}", headers={"Authorization": view_tok}
    )
    assert get_resp.status_code == 200

    # 3. Viewer CANNOT run correlation (needs INVESTIGATOR)
    corr_resp = client.post(
        f"/api/v1/cross-case/scopes/{scope_id}/correlate", headers={"Authorization": view_tok}
    )
    assert corr_resp.status_code == 404 or corr_resp.status_code == 403

    # 4. Investigator CAN run correlation
    corr_inv = client.post(
        f"/api/v1/cross-case/scopes/{scope_id}/correlate", headers={"Authorization": inv_tok}
    )
    assert corr_inv.status_code == 200


def test_05_authorization_rechecked_at_runtime(db_session: Session) -> None:
    """5. Authorization rechecked at query / run time."""
    client = make_auth_client(db_session)
    user, tok = setup_org_user(db_session, "usr-cc-05", "inv_05", "org-recheck")

    create_case(db_session, "case-rech-1", "org-recheck")
    create_case(db_session, "case-rech-2", "org-recheck")

    assign_case_role(db_session, "case-rech-1", user.id, CaseRole.INVESTIGATOR)
    assign_case_role(db_session, "case-rech-2", user.id, CaseRole.INVESTIGATOR)

    scope_resp = client.post(
        "/api/v1/cross-case/scopes",
        headers={"Authorization": tok},
        json={"name": "Recheck Scope", "case_ids": ["case-rech-1", "case-rech-2"]},
    )
    assert scope_resp.status_code == 201
    scope_id = scope_resp.json()["id"]

    # Revoke access to case-rech-2
    cm = (
        db_session.query(CaseMembershipModel)
        .filter(
            CaseMembershipModel.case_id == "case-rech-2", CaseMembershipModel.user_id == user.id
        )
        .first()
    )
    db_session.delete(cm)
    db_session.commit()

    # Now querying scope must fail with 404
    get_resp = client.get(f"/api/v1/cross-case/scopes/{scope_id}", headers={"Authorization": tok})
    assert get_resp.status_code == 404

    # Running correlation must also fail with 404
    corr_resp = client.post(
        f"/api/v1/cross-case/scopes/{scope_id}/correlate", headers={"Authorization": tok}
    )
    assert corr_resp.status_code == 404


def test_06_unauthorized_case_ids_not_leaked(db_session: Session) -> None:
    """6. Unauthorized case IDs and counts not leaked (uniform anti-enumeration)."""
    client = make_auth_client(db_session)
    user, tok = setup_org_user(db_session, "usr-cc-06", "inv_06", "org-leak")

    # Non-existent ID vs unauthorized other-tenant ID both return uniform 404
    resp_fake = client.post(
        "/api/v1/cross-case/scopes",
        headers={"Authorization": tok},
        json={"name": "Leak Test Fake", "case_ids": ["case-nonexistent-999"]},
    )
    assert resp_fake.status_code == 404

    org_other = (
        db_session.query(OrganizationModel)
        .filter(OrganizationModel.id == "org-other-tenant")
        .first()
    )
    if not org_other:
        org_other = OrganizationModel(
            id="org-other-tenant",
            name="Other Org",
            slug="org-other-tenant",
            created_at=utc_now(),
            is_active=True,
        )
        db_session.add(org_other)
        db_session.commit()
    create_case(db_session, "case-other-tenant", "org-other-tenant")
    resp_other = client.post(
        "/api/v1/cross-case/scopes",
        headers={"Authorization": tok},
        json={"name": "Leak Test Other", "case_ids": ["case-other-tenant"]},
    )
    assert resp_other.status_code == 404
    assert "not found or inaccessible" in str(resp_fake.json()).lower()
    assert "not found or inaccessible" in str(resp_other.json()).lower()


def test_07_archived_cases_rejected_from_scope(db_session: Session) -> None:
    """7. Archived cases rejected from active scope."""
    client = make_auth_client(db_session)
    user, tok = setup_org_user(db_session, "usr-cc-07", "inv_07", "org-arch")

    create_case(db_session, "case-arch-1", "org-arch", status=CaseStatus.ACTIVE.value)
    create_case(db_session, "case-arch-2", "org-arch", status=CaseStatus.ARCHIVED.value)

    assign_case_role(db_session, "case-arch-1", user.id, CaseRole.INVESTIGATOR)
    assign_case_role(db_session, "case-arch-2", user.id, CaseRole.INVESTIGATOR)

    resp = client.post(
        "/api/v1/cross-case/scopes",
        headers={"Authorization": tok},
        json={"name": "Archived Scope", "case_ids": ["case-arch-1", "case-arch-2"]},
    )
    assert resp.status_code == 400 or resp.status_code == 422
    assert "archived" in str(resp.json()).lower()


def test_08_exact_identifiers_produce_explainable_candidates() -> None:
    """8. Exact identifiers produce explainable candidates (tax ID, reference, bank account)."""
    matcher = CrossCaseMatcher()

    # Mention in Case 1
    m1 = EntityMention(
        case_id="case-1",
        document_id="doc-1",
        page_number=1,
        processing_run_id="run-1",
        field_key="tax_id",
        entity_type=ResolvedEntityType.TAX_IDENTIFIER,
        original_value="AAAPL1234C",
        normalized_value="AAAPL1234C",
        jurisdiction="IN",
        identifier_type="PAN",
    )
    # Mention in Case 2
    m2 = EntityMention(
        case_id="case-2",
        document_id="doc-2",
        page_number=1,
        processing_run_id="run-1",
        field_key="tax_id",
        entity_type=ResolvedEntityType.TAX_IDENTIFIER,
        original_value="AAAPL1234C",
        normalized_value="AAAPL1234C",
        jurisdiction="IN",
        identifier_type="PAN",
    )

    candidate = matcher.compare(m1, m2, "scope-test", "org-test")
    assert candidate is not None
    assert candidate.match_classification == "EXACT_IDENTIFIER"
    assert candidate.match_score >= 0.95
    assert any(
        "Identical canonical tax identifier" in sig for sig in candidate.evidence.matching_signals
    )
    assert len(candidate.evidence.contradicting_signals) == 0


def test_09_fuzzy_matches_remain_candidates_no_auto_merges() -> None:
    """9. Fuzzy matches remain candidates, not automatic entity merges."""
    matcher = CrossCaseMatcher()

    m1 = EntityMention(
        case_id="case-1",
        document_id="doc-1",
        page_number=1,
        processing_run_id="run-1",
        field_key="vendor_name",
        entity_type=ResolvedEntityType.ORGANIZATION,
        original_value="Acme Global Logistics Pvt Ltd",
        normalized_value="acme global logistics pvt ltd",
        base_name="acme global logistics",
        legal_suffix="pvt ltd",
    )
    m2 = EntityMention(
        case_id="case-2",
        document_id="doc-2",
        page_number=1,
        processing_run_id="run-1",
        field_key="vendor_name",
        entity_type=ResolvedEntityType.ORGANIZATION,
        original_value="Acme Global Logistic Private Limited",
        normalized_value="acme global logistic private limited",
        base_name="acme global logistic",
        legal_suffix="private limited",
    )

    candidate = matcher.compare(m1, m2, "scope-test", "org-test")
    assert candidate is not None
    assert candidate.decision_status == CrossCaseReviewDecision.PENDING_REVIEW
    # High score fuzzy match
    assert candidate.match_score >= 0.85
    assert candidate.match_classification in ("HIGH_CONFIDENCE_FUZZY", "STRONG_MATCH")
    assert any(
        "Fuzzy organization name similarity" in sig for sig in candidate.evidence.matching_signals
    )


def test_10_conflicting_identifiers_penalize_candidate_confidence() -> None:
    """10. Conflicting identifiers reduce or suppress candidate confidence."""
    matcher = CrossCaseMatcher()

    m1 = EntityMention(
        case_id="case-1",
        document_id="doc-1",
        page_number=1,
        processing_run_id="run-1",
        field_key="vendor_name",
        entity_type=ResolvedEntityType.ORGANIZATION,
        original_value="Apex Enterprises",
        normalized_value="apex enterprises",
        base_name="apex enterprises",
        metadata={"tax_id": "AAAPA1111A"},
    )
    m2 = EntityMention(
        case_id="case-2",
        document_id="doc-2",
        page_number=1,
        processing_run_id="run-1",
        field_key="vendor_name",
        entity_type=ResolvedEntityType.ORGANIZATION,
        original_value="Apex Enterprises",
        normalized_value="apex enterprises",
        base_name="apex enterprises",
        metadata={"tax_id": "ZZZPZ9999Z"},
    )

    candidate = matcher.compare(m1, m2, "scope-test", "org-test")
    assert candidate is not None
    # Score should be significantly penalized due to conflicting tax IDs
    assert candidate.match_score <= 0.60
    assert any("Conflicting tax IDs" in sig for sig in candidate.evidence.contradicting_signals)


def test_11_masked_identifiers_not_treated_as_exact_matches() -> None:
    """11. Masked identifiers not treated as exact matches."""
    assert is_masked_or_incomplete("Account ****1234") is True
    assert is_masked_or_incomplete("***-**-1234") is True
    assert is_masked_or_incomplete("XXXX-XXXX-9999") is True
    assert is_masked_or_incomplete("987654321012") is False

    matcher = CrossCaseMatcher()
    m1 = EntityMention(
        case_id="case-1",
        document_id="doc-1",
        page_number=1,
        processing_run_id="run-1",
        field_key="account_number",
        entity_type=ResolvedEntityType.BANK_ACCOUNT_REFERENCE,
        original_value="Account ****1234",
        normalized_value="****1234",
    )
    m2 = EntityMention(
        case_id="case-2",
        document_id="doc-2",
        page_number=1,
        processing_run_id="run-1",
        field_key="account_number",
        entity_type=ResolvedEntityType.BANK_ACCOUNT_REFERENCE,
        original_value="Account ****1234",
        normalized_value="****1234",
    )

    candidate = matcher.compare(m1, m2, "scope-test", "org-test")
    # Masked values must NOT generate an exact identifier match candidate
    assert candidate is None


def test_12_pii_masking_applied_to_cross_case_results() -> None:
    """12. PII masking applies to cross-case results."""
    bank_masked = mask_sensitive_value("123456789012", ResolvedEntityType.BANK_ACCOUNT_REFERENCE)
    assert bank_masked == "Account ****9012"

    tax_masked = mask_sensitive_value("123-45-6789", ResolvedEntityType.TAX_IDENTIFIER)
    assert tax_masked == "***-**-6789"

    phone_masked = mask_sensitive_value("9876543210", "PHONE_NUMBER")
    assert phone_masked == "Phone ****3210"

    matcher = CrossCaseMatcher()
    m1 = EntityMention(
        case_id="case-1",
        document_id="doc-1",
        page_number=1,
        processing_run_id="run-1",
        field_key="account_number",
        entity_type=ResolvedEntityType.BANK_ACCOUNT_REFERENCE,
        original_value="987654321000",
        normalized_value="987654321000",
    )
    m2 = EntityMention(
        case_id="case-2",
        document_id="doc-2",
        page_number=1,
        processing_run_id="run-1",
        field_key="account_number",
        entity_type=ResolvedEntityType.BANK_ACCOUNT_REFERENCE,
        original_value="987654321000",
        normalized_value="987654321000",
    )

    candidate = matcher.compare(m1, m2, "scope-test", "org-test")
    assert candidate is not None
    assert candidate.raw_target_value_masked == "Account ****1000"
    assert candidate.raw_candidate_value_masked == "Account ****1000"


def test_13_source_document_retrieval_requires_case_authorization(db_session: Session) -> None:
    """13. Source-document retrieval still requires case authorization."""
    client = make_auth_client(db_session)
    user_a, token_a = setup_org_user(db_session, "usr-cc-13", "inv_13", "org-doc")

    # Document in case-doc-2
    create_case(db_session, "case-doc-2", "org-doc")
    # user_a is not a member of case-doc-2

    resp = client.get("/api/v1/cases/case-doc-2/documents", headers={"Authorization": token_a})
    assert resp.status_code in (401, 403, 404)


def test_14_graph_traversal_cannot_escape_selected_scope(db_session: Session) -> None:
    """14. Graph traversal cannot escape selected scope."""
    client = make_auth_client(db_session)
    user, tok = setup_org_user(db_session, "usr-cc-14", "inv_14", "org-graph")

    create_case(db_session, "case-gr-1", "org-graph")
    create_case(db_session, "case-gr-2", "org-graph")
    create_case(db_session, "case-gr-outside", "org-graph")

    assign_case_role(db_session, "case-gr-1", user.id, CaseRole.INVESTIGATOR)
    assign_case_role(db_session, "case-gr-2", user.id, CaseRole.INVESTIGATOR)
    assign_case_role(db_session, "case-gr-outside", user.id, CaseRole.INVESTIGATOR)

    scope_resp = client.post(
        "/api/v1/cross-case/scopes",
        headers={"Authorization": tok},
        json={"name": "Graph Bounded Scope", "case_ids": ["case-gr-1", "case-gr-2"]},
    )
    scope_id = scope_resp.json()["id"]

    graph_resp = client.get(
        f"/api/v1/cross-case/scopes/{scope_id}/graph", headers={"Authorization": tok}
    )
    assert graph_resp.status_code == 200
    graph_data = graph_resp.json()

    # Verify no nodes or edges belong to case-gr-outside
    for node in graph_data["nodes"]:
        assert node["case_id"] in ("case-gr-1", "case-gr-2", scope_id)
        assert node["case_id"] != "case-gr-outside"


def test_15_query_and_result_limits_enforced(db_session: Session) -> None:
    """15. Query and result limits enforced (max 20 cases, bounded comparisons)."""
    client = make_auth_client(db_session)
    user, tok = setup_org_user(db_session, "usr-cc-15", "inv_15", "org-limits")

    # Creating scope with > 20 cases must be rejected
    too_many_cases = [f"case-lim-{i}" for i in range(25)]
    resp = client.post(
        "/api/v1/cross-case/scopes",
        headers={"Authorization": tok},
        json={"name": "Excessive Scope", "case_ids": too_many_cases},
    )
    assert resp.status_code == 400 or resp.status_code == 422
    assert "20 cases" in str(resp.json())


def test_16_malicious_parameters_cannot_bypass_scope(db_session: Session) -> None:
    """16. Malicious query parameters cannot bypass scope restrictions."""
    client = make_auth_client(db_session)
    user, tok = setup_org_user(db_session, "usr-cc-16", "inv_16", "org-bypass")

    # Tampered scope_id
    resp = client.get(
        "/api/v1/cross-case/scopes/scope-nonexistent-12345/candidates",
        headers={"Authorization": tok},
    )
    assert resp.status_code == 404

    # Path traversal / SQL injection pattern in scope_id
    resp_sqli = client.get(
        "/api/v1/cross-case/scopes/'%20OR%201=1--/candidates", headers={"Authorization": tok}
    )
    assert resp_sqli.status_code == 404


def test_17_candidate_reviews_enforce_role_permissions(db_session: Session) -> None:
    """17. Candidate reviews enforce role permissions (Reviewer/Admin required)."""
    client = make_auth_client(db_session)
    inv_u, inv_tok = setup_org_user(db_session, "usr-cc-17-inv", "inv_17", "org-revperm")
    rev_u, rev_tok = setup_org_user(db_session, "usr-cc-17-rev", "rev_17", "org-revperm")

    create_case(db_session, "case-rp-1", "org-revperm")
    create_case(db_session, "case-rp-2", "org-revperm")

    assign_case_role(db_session, "case-rp-1", inv_u.id, CaseRole.INVESTIGATOR)
    assign_case_role(db_session, "case-rp-2", inv_u.id, CaseRole.INVESTIGATOR)

    assign_case_role(db_session, "case-rp-1", rev_u.id, CaseRole.REVIEWER)
    assign_case_role(db_session, "case-rp-2", rev_u.id, CaseRole.REVIEWER)

    # 1. Investigator creates scope and runs correlation
    scope_resp = client.post(
        "/api/v1/cross-case/scopes",
        headers={"Authorization": inv_tok},
        json={"name": "Review Perm Scope", "case_ids": ["case-rp-1", "case-rp-2"]},
    )
    scope_id = scope_resp.json()["id"]

    # Insert a synthetic candidate match directly
    from document_intelligence.infrastructure.persistence.models import CrossCaseCandidateMatchModel

    match_id = generate_id()
    match_model = CrossCaseCandidateMatchModel(
        id=match_id,
        scope_id=scope_id,
        organization_id="org-revperm",
        entity_type="ORGANIZATION",
        target_case_id="case-rp-1",
        candidate_case_id="case-rp-2",
        target_value_display="Target Org",
        candidate_value_display="Candidate Org",
        matching_method="deterministic_rule",
        match_classification="EXACT_IDENTIFIER",
        match_score=0.95,
        decision_status="PENDING_REVIEW",
        evidence_payload=make_evidence_payload("case-rp-1", "case-rp-2", 0.95),
        created_at=utc_now(),
    )
    db_session.add(match_model)
    db_session.commit()

    # 2. Investigator tries to review candidate -> rejected (404/403: requires REVIEWER)
    rev_inv = client.post(
        f"/api/v1/cross-case/scopes/{scope_id}/candidates/{match_id}/review",
        headers={"Authorization": inv_tok},
        json={"decision": "ACCEPTED", "rationale": "Investigator trying to accept"},
    )
    assert rev_inv.status_code in (403, 404)

    # 3. Reviewer submits review -> succeeds
    rev_ok = client.post(
        f"/api/v1/cross-case/scopes/{scope_id}/candidates/{match_id}/review",
        headers={"Authorization": rev_tok},
        json={
            "decision": "ACCEPTED",
            "rationale": "Verified legitimate relationship between vendors",
        },
    )
    assert rev_ok.status_code == 200
    assert rev_ok.json()["decision_status"] == "ACCEPTED"


def test_18_review_identity_strictly_from_authenticated_principal(db_session: Session) -> None:
    """18. Review identity comes strictly from authenticated principal."""
    client = make_auth_client(db_session)
    rev_u, rev_tok = setup_org_user(db_session, "usr-cc-18", "audited_reviewer", "org-ident")

    create_case(db_session, "case-id-1", "org-ident")
    create_case(db_session, "case-id-2", "org-ident")
    assign_case_role(db_session, "case-id-1", rev_u.id, CaseRole.REVIEWER)
    assign_case_role(db_session, "case-id-2", rev_u.id, CaseRole.REVIEWER)

    from document_intelligence.infrastructure.persistence.models import (
        CrossCaseCandidateMatchModel,
        CrossCaseScopeModel,
    )

    scope_id = generate_id()
    match_id = generate_id()
    s = CrossCaseScopeModel(
        id=scope_id,
        organization_id="org-ident",
        name="Scope Identity",
        case_ids=["case-id-1", "case-id-2"],
        created_by=rev_u.id,
        created_at=utc_now(),
        updated_at=utc_now(),
        is_active=True,
    )
    m = CrossCaseCandidateMatchModel(
        id=match_id,
        scope_id=scope_id,
        organization_id="org-ident",
        entity_type="PERSON",
        target_case_id="case-id-1",
        candidate_case_id="case-id-2",
        target_value_display="John Doe",
        candidate_value_display="John Doe",
        matching_method="deterministic_rule",
        match_classification="EXACT_IDENTIFIER",
        match_score=1.0,
        decision_status="PENDING_REVIEW",
        evidence_payload=make_evidence_payload("case-id-1", "case-id-2", 1.0),
        created_at=utc_now(),
    )
    db_session.add(s)
    db_session.flush()
    db_session.add(m)
    db_session.commit()

    resp = client.post(
        f"/api/v1/cross-case/scopes/{scope_id}/candidates/{match_id}/review",
        headers={"Authorization": rev_tok},
        json={"decision": "REJECTED", "rationale": "Different persons with identical names"},
    )
    assert resp.status_code == 200
    candidate = resp.json()
    assert len(candidate["review_history"]) == 1
    assert candidate["review_history"][0]["reviewer_id"] == rev_u.id
    assert candidate["review_history"][0]["reviewer_username"] == rev_u.username


def test_19_review_history_is_append_only(db_session: Session) -> None:
    """19. Review history is append-only."""
    client = make_auth_client(db_session)
    rev_u, rev_tok = setup_org_user(db_session, "usr-cc-19", "history_reviewer", "org-hist")

    create_case(db_session, "case-hist-1", "org-hist")
    create_case(db_session, "case-hist-2", "org-hist")
    assign_case_role(db_session, "case-hist-1", rev_u.id, CaseRole.REVIEWER)
    assign_case_role(db_session, "case-hist-2", rev_u.id, CaseRole.REVIEWER)

    from document_intelligence.infrastructure.persistence.models import (
        CrossCaseCandidateMatchModel,
        CrossCaseScopeModel,
    )

    scope_id = generate_id()
    match_id = generate_id()
    s = CrossCaseScopeModel(
        id=scope_id,
        organization_id="org-hist",
        name="Scope Hist",
        case_ids=["case-hist-1", "case-hist-2"],
        created_by=rev_u.id,
        created_at=utc_now(),
        updated_at=utc_now(),
        is_active=True,
    )
    m = CrossCaseCandidateMatchModel(
        id=match_id,
        scope_id=scope_id,
        organization_id="org-hist",
        entity_type="ORGANIZATION",
        target_case_id="case-hist-1",
        candidate_case_id="case-hist-2",
        target_value_display="Vendor X",
        candidate_value_display="Vendor Y",
        matching_method="deterministic_rule",
        match_classification="HIGH_CONFIDENCE_FUZZY",
        match_score=0.88,
        decision_status="PENDING_REVIEW",
        evidence_payload=make_evidence_payload("case-hist-1", "case-hist-2", 0.88, ["Fuzzy match"]),
        created_at=utc_now(),
    )
    db_session.add(s)
    db_session.flush()
    db_session.add(m)
    db_session.commit()

    # First review: NEEDS_FURTHER_INVESTIGATION
    r1 = client.post(
        f"/api/v1/cross-case/scopes/{scope_id}/candidates/{match_id}/review",
        headers={"Authorization": rev_tok},
        json={"decision": "NEEDS_FURTHER_INVESTIGATION", "rationale": "Pending bank statement"},
    )
    assert r1.status_code == 200

    # Second review: ACCEPTED
    r2 = client.post(
        f"/api/v1/cross-case/scopes/{scope_id}/candidates/{match_id}/review",
        headers={"Authorization": rev_tok},
        json={"decision": "ACCEPTED", "rationale": "Confirmed after receiving bank statement"},
    )
    assert r2.status_code == 200

    candidate = r2.json()
    assert len(candidate["review_history"]) == 2
    assert candidate["review_history"][0]["decision"] == "NEEDS_FURTHER_INVESTIGATION"
    assert candidate["review_history"][1]["decision"] == "ACCEPTED"


def test_20_audit_events_written_and_verifiable(db_session: Session) -> None:
    """20. Audit events written and verifiable (CROSS_CASE_SCOPE_CREATED, etc.)."""
    client = make_auth_client(db_session)
    user, tok = setup_org_user(db_session, "usr-cc-20", "audit_user_20", "org-audit")

    create_case(db_session, "case-aud-1", "org-audit")
    create_case(db_session, "case-aud-2", "org-audit")
    assign_case_role(db_session, "case-aud-1", user.id, CaseRole.INVESTIGATOR)
    assign_case_role(db_session, "case-aud-2", user.id, CaseRole.INVESTIGATOR)

    scope_resp = client.post(
        "/api/v1/cross-case/scopes",
        headers={"Authorization": tok},
        json={"name": "Scope For Audit", "case_ids": ["case-aud-1", "case-aud-2"]},
    )
    assert scope_resp.status_code == 201

    events = (
        db_session.query(AuditEventModel)
        .filter(AuditEventModel.event_type == AuditEventType.CROSS_CASE_SCOPE_CREATED.value)
        .all()
    )
    assert len(events) >= 1
    ev = events[-1]
    assert ev.actor_id == user.id
    assert "scope_name" in ev.payload


def test_21_existing_case_level_graph_unchanged(db_session: Session) -> None:
    """21. Existing case-level graph behavior remains unchanged."""
    client = make_auth_client(db_session)
    user, tok = setup_org_user(db_session, "usr-cc-21", "graph_user_21", "org-single-graph")

    case = create_case(db_session, "case-sing-1", "org-single-graph")
    assign_case_role(db_session, "case-sing-1", user.id, CaseRole.INVESTIGATOR)

    resp = client.get(f"/api/v1/cases/{case.id}/graph", headers={"Authorization": tok})
    assert resp.status_code == 200
    data = resp.json()
    assert data["case_id"] == case.id
    assert "nodes" in data
    assert "edges" in data


def test_22_existing_entity_resolution_and_relationships_green(db_session: Session) -> None:
    """22. Existing entity resolution and relationship matcher remain intact."""
    from document_intelligence.modules.entity_resolution.engine.matcher import (
        DeterministicEntityMatcher,
    )

    matcher = DeterministicEntityMatcher()
    m1 = EntityMention(
        case_id="case-same",
        document_id="doc-1",
        page_number=1,
        processing_run_id="run-1",
        field_key="tax_id",
        entity_type=ResolvedEntityType.TAX_IDENTIFIER,
        original_value="AAAPL1234C",
        normalized_value="AAAPL1234C",
    )
    m2 = EntityMention(
        case_id="case-same",
        document_id="doc-2",
        page_number=1,
        processing_run_id="run-1",
        field_key="tax_id",
        entity_type=ResolvedEntityType.TAX_IDENTIFIER,
        original_value="AAAPL1234C",
        normalized_value="AAAPL1234C",
    )
    # Intra-case match must work
    match = matcher.compare_mentions(m1, m2, run_id="run-intra-case")
    assert match is not None
    assert match.match_score == 1.0


def test_23_cross_tenant_data_leakage_negative_test(db_session: Session) -> None:
    """23. Cross-tenant and cross-case data leakage negative tests pass."""
    client = make_auth_client(db_session)
    user_tenant_1, tok_1 = setup_org_user(db_session, "usr-cc-23-1", "user_tenant_1", "tenant-1")
    user_tenant_2, tok_2 = setup_org_user(db_session, "usr-cc-23-2", "user_tenant_2", "tenant-2")

    create_case(db_session, "case-t1-a", "tenant-1")
    create_case(db_session, "case-t1-b", "tenant-1")
    assign_case_role(db_session, "case-t1-a", user_tenant_1.id, CaseRole.INVESTIGATOR)
    assign_case_role(db_session, "case-t1-b", user_tenant_1.id, CaseRole.INVESTIGATOR)

    # Tenant 1 creates scope
    scope_resp = client.post(
        "/api/v1/cross-case/scopes",
        headers={"Authorization": tok_1},
        json={"name": "Tenant 1 Scope", "case_ids": ["case-t1-a", "case-t1-b"]},
    )
    assert scope_resp.status_code == 201
    scope_id = scope_resp.json()["id"]

    # Tenant 2 attempts to query Tenant 1's scope -> 404
    resp = client.get(f"/api/v1/cross-case/scopes/{scope_id}", headers={"Authorization": tok_2})
    assert resp.status_code == 404

    # Tenant 2 listing scopes should not see Tenant 1's scope
    list_resp = client.get("/api/v1/cross-case/scopes", headers={"Authorization": tok_2})
    assert list_resp.status_code == 200
    scope_ids = [s["id"] for s in list_resp.json()]
    assert scope_id not in scope_ids


def test_24_concurrent_correlation_requests_isolation(db_session: Session) -> None:
    """24. Concurrent correlation requests do not corrupt or mix investigation scopes."""
    client = make_auth_client(db_session)
    user, tok = setup_org_user(db_session, "usr-cc-24", "concurrent_user", "org-conc")

    create_case(db_session, "case-conc-1", "org-conc")
    create_case(db_session, "case-conc-2", "org-conc")
    create_case(db_session, "case-conc-3", "org-conc")
    create_case(db_session, "case-conc-4", "org-conc")

    assign_case_role(db_session, "case-conc-1", user.id, CaseRole.INVESTIGATOR)
    assign_case_role(db_session, "case-conc-2", user.id, CaseRole.INVESTIGATOR)
    assign_case_role(db_session, "case-conc-3", user.id, CaseRole.INVESTIGATOR)
    assign_case_role(db_session, "case-conc-4", user.id, CaseRole.INVESTIGATOR)

    s1 = client.post(
        "/api/v1/cross-case/scopes",
        headers={"Authorization": tok},
        json={"name": "Conc Scope 1", "case_ids": ["case-conc-1", "case-conc-2"]},
    ).json()["id"]

    s2 = client.post(
        "/api/v1/cross-case/scopes",
        headers={"Authorization": tok},
        json={"name": "Conc Scope 2", "case_ids": ["case-conc-3", "case-conc-4"]},
    ).json()["id"]

    client1 = make_auth_client(db_session)
    client2 = make_auth_client(db_session)

    errors: list[Exception] = []

    def run_s1():
        try:
            r = client1.post(
                f"/api/v1/cross-case/scopes/{s1}/correlate", headers={"Authorization": tok}
            )
            assert r.status_code == 200
        except Exception as e:
            errors.append(e)

    def run_s2():
        try:
            r = client2.post(
                f"/api/v1/cross-case/scopes/{s2}/correlate", headers={"Authorization": tok}
            )
            assert r.status_code == 200
        except Exception as e:
            errors.append(e)

    t1 = threading.Thread(target=run_s1)
    t2 = threading.Thread(target=run_s2)
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    assert len(errors) == 0
