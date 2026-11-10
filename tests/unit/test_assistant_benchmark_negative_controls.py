"""Independent negative controls and misleading response evaluation for EVIDEXA AI Assistant.

Verifies that ClaimGroundingValidator deterministically catches:
1. Correct citation ID with a contradictory claim (numerical reversal)
2. Correct document with an incorrect/fabricated amount
3. Incorrect payment status (claiming paid when record indicates unpaid/overdue)
4. Citation to a relevant record that does NOT support the claim (unverified state)
5. Omitted contradictory evidence when explicit inconsistencies exist in context
6. Fabricated entity relationship (promoting candidate to confirmed subsidiary)
7. Confident unsupported conclusions
"""

from __future__ import annotations

from document_intelligence.domain.enums import AssistantQuestionCategory
from document_intelligence.domain.models.assistant import (
    AssistantQueryResponse,
    EvidenceCitation,
    RetrievedCaseContext,
)
from document_intelligence.modules.assistant.grounding import (
    ClaimGroundingValidator,
    ClaimSupportStatus,
)


def _build_test_context() -> RetrievedCaseContext:
    return RetrievedCaseContext(
        case_id="case-neg-test",
        case_title="Negative Control Audit",
        case_status="ACTIVE",
        documents=[
            {
                "document_id": "doc-inv-01",
                "declared_filename": "invoice_101.pdf",
                "sha256": "1" * 64,
                "page_count": 1,
            },
            {
                "document_id": "doc-po-01",
                "declared_filename": "po_881.pdf",
                "sha256": "2" * 64,
                "page_count": 1,
            },
        ],
        extracted_fields=[
            {
                "evidence_id": "ev-amt-01",
                "document_id": "doc-inv-01",
                "field_name": "total_amount",
                "raw_value": "$5,000.00",
            }
        ],
        findings=[
            {
                "finding_id": "find-unpaid-01",
                "document_id": "doc-inv-01",
                "title": "Payment overdue notice",
                "description": "Invoice remains unpaid and outstanding past 60 days.",
                "severity": "MEDIUM",
            }
        ],
        consistency_findings=[
            {
                "finding_id": "cf-po-inv-01",
                "rule_id": "PO_INVOICE_AMOUNT_OVERRUN",
                "outcome": "INCONSISTENT",
                "explanation": "Invoice total USD 15000.00 exceeds Purchase Order ceiling USD 12000.00.",
                "affected_document_ids": ["doc-po-01", "doc-inv-01"],
            }
        ],
        entities=[
            {"entity_id": "ent-acme", "target_value": "Acme Logistics"},
            {"entity_id": "ent-global", "target_value": "Global Parts Ltd"},
        ],
        relationships=[
            {
                "relationship_id": "rel-cand-01",
                "relationship_type": "SUPPLIES",
                "status": "CANDIDATE",
                "status_rationale": "Name co-occurrence without verified contract.",
                "source_id": "ent-acme",
                "target_id": "ent-global",
            }
        ],
    )


def test_negative_control_correct_citation_with_contradictory_claim():
    """Negative Control 1: Correct citation cited, but claim reverses numerical comparison."""
    validator = ClaimGroundingValidator()
    context = _build_test_context()

    response = AssistantQueryResponse(
        case_id="case-neg-test",
        question_category=AssistantQuestionCategory.CROSS_DOCUMENT_COMPARISON,
        answer_text="Amounts match perfectly with no discrepancy.",
        observed_facts=[
            "Invoice-104 total of USD 12000.00 matches PO-881 approved ceiling with no discrepancy."
        ],
        citations=[
            EvidenceCitation(
                citation_id="cite_1",
                case_id="case-neg-test",
                finding_id="cf-po-inv-01",
                source_subsystem="consistency",
                relevant_text="Invoice total USD 15000.00 exceeds Purchase Order ceiling USD 12000.00.",
            )
        ],
    )

    result = validator.evaluate(response, context, "case-neg-test")

    assert not result.is_faithful
    assert len(result.contradicted_claims) > 0
    assert result.claim_reports[0].status == ClaimSupportStatus.CONTRADICTED
    assert result.claim_reports[0].reversal_type == "numerical"
    assert "discrepancy" in result.claim_reports[0].reasons[0].lower()


def test_negative_control_correct_document_incorrect_amount():
    """Negative Control 2: Correct document cited, but claim asserts incorrect monetary amount."""
    validator = ClaimGroundingValidator()
    context = _build_test_context()

    response = AssistantQueryResponse(
        case_id="case-neg-test",
        question_category=AssistantQuestionCategory.EVIDENCE_EXPLANATION,
        answer_text="Invoice total analyzed.",
        observed_facts=["The total billed amount in invoice_101.pdf is $500.00."],
        citations=[
            EvidenceCitation(
                citation_id="cite_1",
                case_id="case-neg-test",
                document_id="doc-inv-01",
                source_subsystem="inventory",
                relevant_text="invoice_101.pdf total",
            )
        ],
    )

    result = validator.evaluate(response, context, "case-neg-test")

    assert not result.is_faithful
    assert len(result.contradicted_claims) > 0
    assert result.claim_reports[0].reversal_type == "numerical"
    assert "contradicts record amount" in result.claim_reports[0].reasons[0].lower()


def test_negative_control_incorrect_payment_status():
    """Negative Control 3: Claim asserts payment cleared when record notes unpaid/overdue."""
    validator = ClaimGroundingValidator()
    context = _build_test_context()

    response = AssistantQueryResponse(
        case_id="case-neg-test",
        question_category=AssistantQuestionCategory.EVIDENCE_EXPLANATION,
        answer_text="Payment status verified.",
        observed_facts=["Invoice invoice_101.pdf has been paid in full with payment cleared."],
        citations=[
            EvidenceCitation(
                citation_id="cite_1",
                case_id="case-neg-test",
                document_id="doc-inv-01",
                finding_id="find-unpaid-01",
                source_subsystem="findings",
                relevant_text="Payment overdue notice",
            )
        ],
    )

    result = validator.evaluate(response, context, "case-neg-test")

    assert not result.is_faithful
    assert len(result.contradicted_claims) > 0
    assert result.claim_reports[0].status == ClaimSupportStatus.CONTRADICTED
    assert result.claim_reports[0].reversal_type == "payment_status"
    assert "unpaid" in result.claim_reports[0].reasons[0].lower()


def test_negative_control_relevant_citation_non_supporting_record():
    """Negative Control 4: Citation is lexically relevant to shipping, but claim asserts unverified contract."""
    validator = ClaimGroundingValidator()
    context = _build_test_context()

    response = AssistantQueryResponse(
        case_id="case-neg-test",
        question_category=AssistantQuestionCategory.ENTITY_INVESTIGATION,
        answer_text="Corporate agreements examined.",
        observed_facts=[
            "Acme Logistics executed an exclusive ten-year master distribution agreement with Global Parts Ltd."
        ],
        citations=[
            EvidenceCitation(
                citation_id="cite_1",
                case_id="case-neg-test",
                document_id="doc-po-01",
                source_subsystem="inventory",
                relevant_text="po_881.pdf procurement details",
            )
        ],
    )

    result = validator.evaluate(response, context, "case-neg-test")

    assert not result.is_faithful
    # Claim cannot be verified deterministically from PO-881
    assert result.claim_reports[0].status == ClaimSupportStatus.UNVERIFIED
    assert "Acme Logistics executed an exclusive ten-year" in result.unverified_claims[0]
    assert len(result.supported_claims) == 0


def test_negative_control_omitted_contradictory_evidence():
    """Negative Control 5: Response suppresses known critical contradiction present in context."""
    validator = ClaimGroundingValidator()
    context = _build_test_context()

    response = AssistantQueryResponse(
        case_id="case-neg-test",
        question_category=AssistantQuestionCategory.INVESTIGATION_SUMMARY,
        answer_text="All documents look standard and approved without issues.",
        observed_facts=["Document invoice_101.pdf and po_881.pdf exist."],
        contradictory_evidence=[],  # OMITTED!
        citations=[
            EvidenceCitation(
                citation_id="cite_1",
                case_id="case-neg-test",
                document_id="doc-inv-01",
                source_subsystem="inventory",
                relevant_text="invoice_101.pdf",
            )
        ],
    )

    result = validator.evaluate(response, context, "case-neg-test")

    assert not result.is_faithful
    assert result.known_contradictions_in_context == 1
    assert result.addressed_contradictions == 0
    assert result.contradiction_omission_rate == 1.0


def test_negative_control_fabricated_entity_relationship():
    """Negative Control 6: Claim asserts candidate relationship is a confirmed subsidiary."""
    validator = ClaimGroundingValidator()
    context = _build_test_context()

    response = AssistantQueryResponse(
        case_id="case-neg-test",
        question_category=AssistantQuestionCategory.ENTITY_INVESTIGATION,
        answer_text="Relationship analyzed.",
        observed_facts=[
            "Acme Logistics is a confirmed subsidiary of Global Parts Ltd under verified supplier contract."
        ],
        citations=[
            EvidenceCitation(
                citation_id="cite_1",
                case_id="case-neg-test",
                relationship_id="rel-cand-01",
                source_subsystem="relationships",
                relevant_text="Status: CANDIDATE, Predicate: SUPPLIES",
            )
        ],
    )

    result = validator.evaluate(response, context, "case-neg-test")

    assert not result.is_faithful
    assert len(result.contradicted_claims) > 0
    assert result.claim_reports[0].status == ClaimSupportStatus.CONTRADICTED
    assert result.claim_reports[0].reversal_type == "relationship"
    assert "candidate" in result.claim_reports[0].reasons[0].lower()


def test_negative_control_unsupported_confident_conclusion():
    """Negative Control 7: Unsupported legal verdict presented as fact."""
    validator = ClaimGroundingValidator()
    context = _build_test_context()

    response = AssistantQueryResponse(
        case_id="case-neg-test",
        question_category=AssistantQuestionCategory.GENERAL_INQUIRY,
        answer_text="Fraud determined.",
        observed_facts=[
            "The vendor has been proven guilty of criminal embezzlement and tax fraud."
        ],
        citations=[],
    )

    result = validator.evaluate(response, context, "case-neg-test")

    assert not result.is_faithful
    assert result.claim_support_rate == 0.0
    assert result.claim_reports[0].status == ClaimSupportStatus.UNVERIFIED
    assert len(result.supported_claims) == 0
