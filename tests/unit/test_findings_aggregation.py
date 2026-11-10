"""Unit tests for FindingsAggregator."""

from __future__ import annotations

from document_intelligence.domain.enums import (
    AggregatedFindingCategory,
    ConsistencyOutcome,
    EvidentiaryClassification,
    FindingCategory,
    FindingSeverity,
    FindingStatus,
    InvestigatorReviewAction,
    RelationshipDetectionMethod,
    RelationshipStatus,
    RelationshipType,
    StatusDeterminationMethod,
)
from document_intelligence.domain.models.aggregated_finding import AggregatedFindingReview
from document_intelligence.domain.models.consistency import ConsistencyFinding
from document_intelligence.domain.models.forensic_finding import ForensicFinding
from document_intelligence.domain.models.relationship import (
    DetectedRelationship,
    RelationshipEvidence,
)
from document_intelligence.modules.dossier.aggregator import FindingsAggregator


def test_findings_aggregator_unifies_forensic_findings():
    aggregator = FindingsAggregator()
    case_id = "case-test-123"

    ff = ForensicFinding(
        id="ff-101",
        case_id=case_id,
        processing_run_id="run-1",
        document_id="doc-1",
        category=FindingCategory.PDF_STRUCTURE,
        severity=FindingSeverity.HIGH,
        status=FindingStatus.DETECTED,
        title="Incremental update tampering detected",
        description="Trailer dictionary contains appended objects after digital signature",
        confidence=0.95,
        source_component="pdf_structural_forensics",
        evidence_ids=["ev-node-1"],
    )

    aggregated = aggregator.aggregate(
        case_id=case_id,
        forensic_findings=[ff],
        consistency_findings=[],
        detected_relationships=[],
        entity_matches=[],
    )

    assert len(aggregated) == 1
    item = aggregated[0]
    assert item.id == "ff-101"
    assert item.source_type == "FORENSIC_FINDING"
    assert item.category == AggregatedFindingCategory.STRUCTURAL_ANOMALY
    assert item.evidentiary_classification == EvidentiaryClassification.AUTOMATED_INDICATOR
    assert item.severity == FindingSeverity.HIGH
    assert item.is_reviewed is False
    assert item.affected_document_ids == ["doc-1"]


def test_findings_aggregator_unifies_consistency_findings():
    aggregator = FindingsAggregator()
    case_id = "case-test-123"

    cf = ConsistencyFinding(
        id="cf-201",
        case_id=case_id,
        analysis_run_id="run-1",
        rule_id="RULE_DATE_SEQUENCE_CHECK",
        category=FindingCategory.CROSS_DOCUMENT_MISMATCH,
        severity=FindingSeverity.MEDIUM,
        outcome=ConsistencyOutcome.INCONSISTENT,
        title="Invoice date precedes purchase order date",
        explanation="Invoice dated 2026-01-01 precedes PO dated 2026-01-15 by 14 days",
        score=0.85,
        affected_document_ids=["doc-inv", "doc-po"],
        supporting_evidence_ids=["ev-1", "ev-2"],
    )

    aggregated = aggregator.aggregate(
        case_id=case_id,
        forensic_findings=[],
        consistency_findings=[cf],
        detected_relationships=[],
        entity_matches=[],
    )

    assert len(aggregated) == 1
    item = aggregated[0]
    assert item.id == "cf-201"
    assert item.source_type == "CONSISTENCY_FINDING"
    assert item.category == AggregatedFindingCategory.CROSS_DOCUMENT_INCONSISTENCY
    assert item.evidentiary_classification == EvidentiaryClassification.ANALYTICAL_INTERPRETATION
    assert item.affected_document_ids == ["doc-inv", "doc-po"]


def test_findings_aggregator_integrates_reviews_and_updates_classification():
    aggregator = FindingsAggregator()
    case_id = "case-test-123"

    ff = ForensicFinding(
        id="ff-102",
        case_id=case_id,
        processing_run_id="run-1",
        document_id="doc-2",
        category=FindingCategory.VISUAL_ANOMALY,
        severity=FindingSeverity.HIGH,
        status=FindingStatus.DETECTED,
        title="Copy-move duplicate stamp detected",
        description="Identical stamp geometry detected at page 1 and page 3",
        confidence=0.88,
        source_component="visual_image_forensics",
        evidence_ids=["ev-node-2"],
    )

    review = AggregatedFindingReview(
        finding_id="ff-102",
        case_id=case_id,
        reviewer_id="inv-agent-42",
        action=InvestigatorReviewAction.CONFIRM_OBSERVATION,
        prior_status="DETECTED",
        new_status="CONFIRM_OBSERVATION",
        rationale="Verified stamp pixel artifacts under high-resolution magnification.",
        evidentiary_classification=EvidentiaryClassification.INVESTIGATOR_CONCLUSION,
    )

    aggregated = aggregator.aggregate(
        case_id=case_id,
        forensic_findings=[ff],
        consistency_findings=[],
        detected_relationships=[],
        entity_matches=[],
        reviews=[review],
    )

    assert len(aggregated) == 1
    item = aggregated[0]
    assert item.is_reviewed is True
    assert item.evidentiary_classification == EvidentiaryClassification.INVESTIGATOR_CONCLUSION
    assert item.review_status == "CONFIRM_OBSERVATION"
    assert len(item.review_history) == 1
    assert item.review_history[0].reviewer_id == "inv-agent-42"


def test_findings_aggregator_unifies_relationship_anomalies():
    aggregator = FindingsAggregator()
    case_id = "case-test-123"

    rel = DetectedRelationship(
        id="rel-301",
        case_id=case_id,
        detection_run_id="run-rel-1",
        source_id="doc-1",
        source_type="DOCUMENT",
        source_label="Doc 1",
        target_id="doc-2",
        target_type="DOCUMENT",
        target_label="Doc 2",
        relationship_type=RelationshipType.AMENDS_DOCUMENT,
        direction_display="Doc 1 --AMENDS_DOCUMENT--> Doc 2",
        status=RelationshipStatus.CONTRADICTED,
        status_determination_method=StatusDeterminationMethod.EVIDENTIARY_RULE,
        status_rationale="Superseded document contains conflicting invoice amounts.",
        score=0.9,
        score_semantics="evidence_strength",
        detection_method=RelationshipDetectionMethod.EXPLICIT_FIELD_REFERENCE,
        evidence=RelationshipEvidence(
            relationship_type=RelationshipType.AMENDS_DOCUMENT,
            source_id="doc-1",
            target_id="doc-2",
            source_case_id=case_id,
            score=0.9,
            score_semantics="evidence_strength",
            status=RelationshipStatus.CONTRADICTED,
            status_rationale="Superseded document contains conflicting invoice amounts.",
            contradicting_signals=["amount mismatch: $100 vs $500"],
        ),
    )

    aggregated = aggregator.aggregate(
        case_id=case_id,
        forensic_findings=[],
        consistency_findings=[],
        detected_relationships=[rel],
        entity_matches=[],
    )

    assert len(aggregated) == 1
    item = aggregated[0]
    assert item.id == "rel-301"
    assert item.source_type == "RELATIONSHIP_ANOMALY"
    assert item.category == AggregatedFindingCategory.RELATIONSHIP_ANOMALY
    assert item.severity == FindingSeverity.HIGH
    assert item.contradicting_evidence_ids == ["amount mismatch: $100 vs $500"]
