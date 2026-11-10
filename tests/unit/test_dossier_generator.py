"""Unit tests for DossierGenerator."""

from __future__ import annotations

from document_intelligence.domain.enums import (
    AggregatedFindingCategory,
    CaseStatus,
    EvidentiaryClassification,
    FindingSeverity,
    InvestigatorReviewAction,
)
from document_intelligence.domain.identifiers import generate_id
from document_intelligence.domain.models.aggregated_finding import (
    AggregatedFinding,
    AggregatedFindingReview,
)
from document_intelligence.domain.models.case import Case
from document_intelligence.domain.models.document import Document
from document_intelligence.modules.dossier.generator import (
    DossierGenerator,
    compute_canonical_content_hash,
)


def _make_sample_case() -> Case:
    return Case(
        id="case-dossier-001",
        title="Project Falcon Investigation",
        description="Cross-border vendor invoice consistency and authenticity inquiry",
        status=CaseStatus.ACTIVE,
    )


def _make_sample_doc(case_id: str, name: str) -> Document:
    return Document(
        id=generate_id(),
        case_id=case_id,
        original_filename=name,
        storage_key=f"storage/{case_id}/{name}",
        media_type="application/pdf",
        file_extension=".pdf",
        file_size_bytes=45200,
        page_count=3,
        sha256="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    )


def test_dossier_generator_produces_twelve_canonical_sections():
    generator = DossierGenerator()
    case = _make_sample_case()
    doc1 = _make_sample_doc(case.id, "invoice_1001.pdf")
    doc2 = _make_sample_doc(case.id, "contract_v2.pdf")

    finding1 = AggregatedFinding(
        id="find-01",
        case_id=case.id,
        source_type="FORENSIC_FINDING",
        source_id="ff-01",
        category=AggregatedFindingCategory.STRUCTURAL_ANOMALY,
        evidentiary_classification=EvidentiaryClassification.AUTOMATED_INDICATOR,
        source_status="DETECTED",
        review_status="UNREVIEWED",
        title="Appended trailer signature invalidation",
        description="Objects appended after EOF marker",
        severity=FindingSeverity.HIGH,
        affected_document_ids=[doc1.id],
    )

    review1 = AggregatedFindingReview(
        finding_id=finding1.id,
        case_id=case.id,
        action=InvestigatorReviewAction.MARK_NEEDS_REVIEW,
        reviewer_id="inv-lead",
        comment="Requires corroboration with vendor contract.",
        previous_status="UNREVIEWED",
        new_status="MARK_NEEDS_REVIEW",
    )

    dossier = generator.generate(
        case=case,
        documents=[doc1, doc2],
        aggregated_findings=[finding1],
        reviews=[review1],
        created_by="inv-lead",
    )

    assert len(dossier.sections) == 12
    expected_ids = [
        "case_overview",
        "scope_and_methodology",
        "documents_examined",
        "processing_and_extraction_summary",
        "key_observations",
        "cross_document_consistency",
        "entity_and_relationship_analysis",
        "supporting_evidence",
        "contradictory_evidence",
        "investigator_reviews",
        "unresolved_questions",
        "limitations_and_disclaimers",
    ]
    actual_ids = [s.section_id for s in dossier.sections]
    assert actual_ids == expected_ids

    # Verify orders 1 to 12
    for idx, s in enumerate(dossier.sections, start=1):
        assert s.order == idx

    # Check disclaimer in section 12
    sec12 = dossier.sections[-1]
    assert "NOTICE:" in sec12.content
    assert "fraud determination" in sec12.content

    # Check unresolved questions
    assert len(dossier.unresolved_questions) >= 1
    assert any("requires evidentiary confirmation" in q for q in dossier.unresolved_questions)


def test_dossier_content_hash_is_deterministic():
    case = _make_sample_case()

    payload1 = {
        "case_id": case.id,
        "title": "Dossier 1",
        "summary": "Everything consistent",
    }
    payload2 = {
        "title": "Dossier 1",
        "case_id": case.id,
        "summary": "Everything consistent",
    }
    hash1 = compute_canonical_content_hash(payload1)
    hash2 = compute_canonical_content_hash(payload2)
    assert hash1 == hash2

    payload3 = dict(payload1)
    payload3["summary"] = "Tampering found"
    hash3 = compute_canonical_content_hash(payload3)
    assert hash1 != hash3
