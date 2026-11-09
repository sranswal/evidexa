"""Unit tests for domain models, value objects, and lifecycle invariants."""

from datetime import UTC

import pytest
from pydantic import ValidationError

from document_intelligence.core.exceptions import InvalidStatusTransitionException
from document_intelligence.domain.enums import (
    CaseStatus,
    DossierStatus,
    EvidenceType,
    FindingCategory,
    FindingSeverity,
)
from document_intelligence.domain.identifiers import generate_case_reference, generate_id, utc_now
from document_intelligence.domain.models import (
    BoundingBox,
    Case,
    EvidenceNode,
    ForensicFinding,
    InvestigationDossier,
)


class TestDomainIdentifiers:
    """Test UUID and timestamp generators."""

    def test_generate_id_format(self) -> None:
        val = generate_id()
        assert isinstance(val, str)
        assert len(val) == 36
        assert val.count("-") == 4

    def test_generate_case_reference(self) -> None:
        ref = generate_case_reference()
        assert ref.startswith("CASE-")
        assert len(ref) >= 15

    def test_utc_now_is_timezone_aware(self) -> None:
        now = utc_now()
        assert now.tzinfo is not None
        assert now.tzinfo == UTC


class TestBoundingBox:
    """Test BoundingBox validation and calculations."""

    def test_valid_bounding_box(self) -> None:
        box = BoundingBox(x=0.1, y=0.2, width=0.3, height=0.4)
        assert box.x == 0.1
        assert box.y == 0.2
        assert box.width == 0.3
        assert box.height == 0.4
        assert round(box.area, 4) == 0.12
        assert round(box.x2, 4) == 0.4
        assert round(box.y2, 4) == 0.6

    def test_negative_dimensions_rejected(self) -> None:
        with pytest.raises(ValueError, match="width must be non-negative"):
            BoundingBox(x=0.1, y=0.1, width=-0.5, height=0.5)

        with pytest.raises(ValueError, match="height must be non-negative"):
            BoundingBox(x=0.1, y=0.1, width=0.5, height=-0.5)

        with pytest.raises(ValueError, match="x coordinate must be non-negative"):
            BoundingBox(x=-0.1, y=0.1, width=0.5, height=0.5)


class TestCaseLifecycle:
    """Test Case transitions and invariants."""

    def test_case_creation_defaults(self) -> None:
        case = Case(title="Suspicious Loan Application")
        assert case.status == CaseStatus.DRAFT
        assert case.case_reference.startswith("CASE-")
        assert case.created_at.tzinfo == UTC

    def test_legal_status_transitions(self) -> None:
        case = Case(title="Test Case")
        assert case.status == CaseStatus.DRAFT

        # DRAFT -> ACTIVE
        case.transition_to(CaseStatus.ACTIVE)
        assert case.status == CaseStatus.ACTIVE

        # ACTIVE -> UNDER_REVIEW
        case.transition_to(CaseStatus.UNDER_REVIEW)
        assert case.status == CaseStatus.UNDER_REVIEW

        # UNDER_REVIEW -> COMPLETED
        case.transition_to(CaseStatus.COMPLETED)
        assert case.status == CaseStatus.COMPLETED

        # COMPLETED -> ARCHIVED
        case.transition_to(CaseStatus.ARCHIVED)
        assert case.status == CaseStatus.ARCHIVED

    def test_illegal_status_transition_raises_exception(self) -> None:
        case = Case(title="Test Case")
        assert case.status == CaseStatus.DRAFT

        # DRAFT cannot jump directly to COMPLETED
        with pytest.raises(InvalidStatusTransitionException) as exc_info:
            case.transition_to(CaseStatus.COMPLETED)
        assert "Cannot transition Case from 'DRAFT' to 'COMPLETED'" in str(exc_info.value)


class TestEvidenceNodeAndFinding:
    """Test EvidenceNode confidence, raw_value protection, and ForensicFinding evidence validation."""

    def test_evidence_node_confidence_bounds(self) -> None:
        node = EvidenceNode(
            case_id="case-1",
            processing_run_id="run-1",
            evidence_type=EvidenceType.OCR_TEXT,
            title="Date token",
            description="Extracted invoice date",
            source_component="docling",
            source_version="2.0",
            confidence=0.95,
        )
        assert node.confidence == 0.95

        # None is allowed when upstream engine does not supply confidence
        node_none = EvidenceNode(
            case_id="case-1",
            processing_run_id="run-1",
            evidence_type=EvidenceType.PDF_STRUCTURAL,
            title="Xref audit",
            description="No confidence supplied",
            source_component="pdfforensics",
            source_version="1.0",
            confidence=None,
        )
        assert node_none.confidence is None

        # Invalid bounds
        with pytest.raises(ValidationError):
            EvidenceNode(
                case_id="case-1",
                processing_run_id="run-1",
                evidence_type=EvidenceType.OCR_TEXT,
                title="Invalid",
                description="Invalid confidence",
                source_component="test",
                source_version="1.0",
                confidence=1.5,
            )

    def test_raw_value_is_hidden_from_repr(self) -> None:
        node = EvidenceNode(
            case_id="case-1",
            processing_run_id="run-1",
            evidence_type=EvidenceType.OCR_TEXT,
            title="Aadhaar",
            description="PII token",
            source_component="ocr",
            source_version="1.0",
            raw_value="1234-5678-9012",
        )
        repr_str = repr(node)
        assert "1234-5678-9012" not in repr_str

    def test_finding_requires_evidence_for_non_other_categories(self) -> None:
        # Non-OTHER with evidence passes
        finding = ForensicFinding(
            case_id="case-1",
            processing_run_id="run-1",
            category=FindingCategory.VISUAL_ANOMALY,
            title="ELA Splicing Discrepancy",
            description="High compression variance detected",
            severity=FindingSeverity.HIGH,
            source_component="ela_detector",
            evidence_ids=["ev-node-123"],
        )
        assert finding.evidence_ids == ["ev-node-123"]

        # Non-OTHER with empty evidence raises error
        with pytest.raises(ValueError, match="must reference at least one supporting evidence ID"):
            ForensicFinding(
                case_id="case-1",
                processing_run_id="run-1",
                category=FindingCategory.FINANCIAL_VALIDATION,
                title="Balance mismatch",
                description="Unbacked assertion",
                severity=FindingSeverity.HIGH,
                source_component="finance_rule",
                evidence_ids=[],
            )

        # OTHER category can be created without evidence IDs
        other_finding = ForensicFinding(
            case_id="case-1",
            processing_run_id="run-1",
            category=FindingCategory.OTHER,
            title="General Note",
            description="Investigator procedural remark",
            severity=FindingSeverity.INFO,
            source_component="manual",
            evidence_ids=[],
        )
        assert other_finding.category == FindingCategory.OTHER


class TestDossierVersioning:
    """Test InvestigationDossier state transitions and version superseding."""

    def test_dossier_approval(self) -> None:
        dossier = InvestigationDossier(
            case_id="case-1",
            version=1,
            executive_summary="Preliminary investigation summary",
            created_by="investigator-1",
        )
        assert dossier.status == DossierStatus.DRAFT
        dossier.approve()
        assert dossier.status == DossierStatus.APPROVED
        assert dossier.finalized_at is not None

    def test_dossier_version_superseding(self) -> None:
        d1 = InvestigationDossier(
            case_id="case-1",
            version=1,
            executive_summary="Draft 1",
            created_by="investigator-1",
        )
        d1.approve()

        d2 = d1.create_next_version(created_by="lead-investigator")
        assert d1.status == DossierStatus.SUPERSEDED
        assert d2.version == 2
        assert d2.status == DossierStatus.DRAFT
        assert d2.created_by == "lead-investigator"
