"""Unit tests for ClaimGroundingValidator."""

from __future__ import annotations

import pytest

from document_intelligence.domain.enums import AssistantQuestionCategory
from document_intelligence.domain.models.assistant import (
    AssistantQueryResponse,
    EvidenceCitation,
    RetrievedCaseContext,
)
from document_intelligence.modules.assistant.grounding import ClaimGroundingValidator


@pytest.fixture
def sample_context() -> RetrievedCaseContext:
    return RetrievedCaseContext(
        case_id="case-100",
        case_title="Grounding Validation Case",
        case_status="ACTIVE",
        documents=[
            {
                "document_id": "doc-1",
                "declared_filename": "invoice_alpha.pdf",
                "page_count": 2,
            }
        ],
        findings=[
            {
                "finding_id": "find-1",
                "document_id": "doc-1",
                "title": "Font discrepancy in total amount",
                "description": "Embedded font Helvetica modified on page 1.",
                "page_number": 1,
            }
        ],
        consistency_findings=[
            {
                "finding_id": "cf-1",
                "rule_id": "INVOICE_TOTAL_MISMATCH",
                "outcome": "INCONSISTENT",
                "explanation": "Calculated subtotal plus tax does not equal grand total.",
                "affected_document_ids": ["doc-1"],
            }
        ],
        extracted_fields=[
            {
                "evidence_id": "ev-1",
                "document_id": "doc-1",
                "page_number": 1,
                "text": "Total: USD 1,250.00",
            }
        ],
        entities=[],
        relationships=[],
        reviews=[],
        text_snippets=[],
        total_retrieved_items=4,
    )


def test_validator_approves_grounded_citations(sample_context: RetrievedCaseContext) -> None:
    validator = ClaimGroundingValidator()

    citations = [
        EvidenceCitation(
            citation_id="cite_1",
            case_id="case-100",
            document_id="doc-1",
            document_title="invoice_alpha.pdf",
            source_subsystem="inventory",
            relevant_text="invoice_alpha.pdf",
        ),
        EvidenceCitation(
            citation_id="cite_2",
            case_id="case-100",
            finding_id="find-1",
            source_subsystem="forensics",
            page_number=1,
            relevant_text="Font discrepancy in total amount",
        ),
    ]

    response = AssistantQueryResponse(
        case_id="case-100",
        question_category=AssistantQuestionCategory.EVIDENCE_EXPLANATION,
        answer_text="Document invoice_alpha.pdf contains font discrepancy in total amount.",
        citations=citations,
        observed_facts=["Document invoice_alpha.pdf has 2 pages."],
        automated_indicators=["Font discrepancy in total amount"],
        contradictory_evidence=["Calculated subtotal does not equal grand total."],
    )

    report = validator.evaluate(response, sample_context, target_case_id="case-100")

    assert report.total_citations == 2
    assert report.resolved_citations == 2
    assert report.citation_resolution_rate == 1.0
    assert report.text_grounding_rate == 1.0
    assert report.case_isolation_violation is False
    assert report.is_faithful is True


def test_validator_detects_cross_case_citation(sample_context: RetrievedCaseContext) -> None:
    validator = ClaimGroundingValidator()

    citations = [
        EvidenceCitation(
            citation_id="cite_foreign",
            case_id="case-foreign-999",  # Cross-case leak attempt!
            document_id="doc-1",
            source_subsystem="inventory",
        )
    ]

    response = AssistantQueryResponse(
        case_id="case-100",
        question_category=AssistantQuestionCategory.EVIDENCE_EXPLANATION,
        answer_text="Referencing foreign document.",
        citations=citations,
    )

    report = validator.evaluate(response, sample_context, target_case_id="case-100")

    assert report.case_isolation_violation is True
    assert report.citation_resolution_rate == 0.0
    assert report.is_faithful is False
    assert any(
        "does not match active case" in r.failure_reasons[0] for r in report.citation_reports
    )


def test_validator_detects_fabricated_record_ids(sample_context: RetrievedCaseContext) -> None:
    validator = ClaimGroundingValidator()

    citations = [
        EvidenceCitation(
            citation_id="cite_ghost",
            case_id="case-100",
            document_id="doc-non-existent-999",
            source_subsystem="inventory",
        )
    ]

    response = AssistantQueryResponse(
        case_id="case-100",
        question_category=AssistantQuestionCategory.EVIDENCE_EXPLANATION,
        answer_text="Ghost document reference.",
        citations=citations,
    )

    report = validator.evaluate(response, sample_context, target_case_id="case-100")

    assert report.resolved_citations == 0
    assert report.ungrounded_citations == 1
    assert report.citation_resolution_rate == 0.0


def test_validator_detects_contradiction_omissions(sample_context: RetrievedCaseContext) -> None:
    validator = ClaimGroundingValidator()

    # Response completely ignores known consistency finding "INCONSISTENT"
    response = AssistantQueryResponse(
        case_id="case-100",
        question_category=AssistantQuestionCategory.INVESTIGATION_SUMMARY,
        answer_text="All documents look fine and regular with no discrepancies noted.",
        citations=[],
        observed_facts=[],
        automated_indicators=[],
        contradictory_evidence=[],  # Omitted!
    )

    report = validator.evaluate(response, sample_context, target_case_id="case-100")

    assert report.known_contradictions_in_context == 1
    assert report.addressed_contradictions == 0
    assert report.contradiction_omission_rate == 1.0
