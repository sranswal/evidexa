"""Unit tests for ForensicAnalyzer protocol, registry, mapper, and normalizer."""

from pathlib import Path

import pytest

from document_intelligence.core.exceptions import ValidationException
from document_intelligence.domain.enums import (
    EvidenceType,
    FindingCategory,
    FindingSeverity,
    FindingStatus,
    PipelineStatus,
)
from document_intelligence.modules.forensics.adapters.pdf_structural.adapter import (
    PdfStructuralAnalyzer,
)
from document_intelligence.modules.forensics.adapters.pdf_structural.capabilities import (
    PdfCapability,
)
from document_intelligence.modules.forensics.adapters.pdf_structural.mapper import (
    map_upstream_report,
)
from document_intelligence.modules.forensics.application.result_normalizer import (
    ForensicResultNormalizer,
)
from document_intelligence.modules.forensics.interfaces.analyzer import ForensicAnalyzer
from document_intelligence.modules.forensics.interfaces.registry import AnalyzerRegistry
from document_intelligence.modules.forensics.schemas.analyzer_input import AnalyzerInput
from document_intelligence.modules.forensics.schemas.analyzer_output import (
    AnalyzerObservation,
    AnalyzerOutput,
)


class TestForensicAdapterProtocolAndRegistry:
    """Validate protocol compliance and registry semantics."""

    def test_pdf_analyzer_implements_protocol(self) -> None:
        analyzer = PdfStructuralAnalyzer()
        assert isinstance(analyzer, ForensicAnalyzer)
        assert analyzer.analyzer_id == "pdf-structural-analyzer"
        assert analyzer.name == "PDF Structural & Byte-Level Forensics Analyzer"
        assert analyzer.version == "0.6.0"
        assert analyzer.supported_media_types == {"application/pdf"}
        assert analyzer.can_analyze("application/pdf") is True
        assert analyzer.can_analyze("image/png") is False
        assert analyzer.can_analyze("text/plain") is False

    def test_registry_registration_and_lookup(self) -> None:
        registry = AnalyzerRegistry()
        analyzer = PdfStructuralAnalyzer()

        registry.register(analyzer)
        assert registry.get("pdf-structural-analyzer") is analyzer
        assert len(registry.list_analyzers()) == 1

        pdf_analyzers = registry.get_for_media_type("application/pdf")
        assert len(pdf_analyzers) == 1
        assert pdf_analyzers[0].analyzer_id == "pdf-structural-analyzer"

        png_analyzers = registry.get_for_media_type("image/png")
        assert len(png_analyzers) == 0

    def test_registry_prevents_duplicate_id(self) -> None:
        registry = AnalyzerRegistry()
        analyzer1 = PdfStructuralAnalyzer()
        analyzer2 = PdfStructuralAnalyzer()

        registry.register(analyzer1)
        with pytest.raises(ValidationException) as exc_info:
            registry.register(analyzer2)
        assert "already registered" in str(exc_info.value)


class TestForensicResultNormalizer:
    """Validate normalization into domain models without fabricating spatial data."""

    def test_normalizer_creates_nodes_and_findings(self) -> None:
        normalizer = ForensicResultNormalizer()
        output = AnalyzerOutput(
            analyzer_id="test-analyzer",
            analyzer_name="Test Analyzer",
            analyzer_version="1.0.0",
            status=PipelineStatus.SUCCEEDED,
            execution_duration_ms=42.0,
            observations=[
                AnalyzerObservation(
                    capability_id=PdfCapability.REVISIONS.value,
                    observation_type="revisions",
                    severity="high",
                    confidence=0.95,
                    title="Content Changed in Revision 2",
                    description="Text was modified incrementally.",
                    page_number=1,
                    observed_value="change_type=text_edit",
                    evidence_payload={"text_added": ["900 SEK"], "text_removed": ["100 SEK"]},
                    benign_explanations=["Forms saved in Adobe Acrobat may append revisions."],
                ),
                AnalyzerObservation(
                    capability_id=PdfCapability.METADATA.value,
                    observation_type="metadata",
                    severity="low",
                    confidence=0.8,
                    title="Creation and Mod Date Mismatch",
                    description="ModDate is earlier than CreationDate.",
                    page_number=None,
                    observed_value="issue=temporal_inversion",
                ),
            ],
        )

        evidence_nodes, findings, links = normalizer.normalize(
            output=output,
            case_id="case-123",
            document_id="doc-456",
            processing_run_id="run-789",
        )

        assert len(evidence_nodes) == 2
        assert len(findings) == 2
        assert len(links) == 2

        # 1. First observation check (structural/revisions)
        ev1 = evidence_nodes[0]
        f1 = findings[0]
        l1 = links[0]

        assert ev1.case_id == "case-123"
        assert ev1.document_id == "doc-456"
        assert ev1.processing_run_id == "run-789"
        assert ev1.evidence_type == EvidenceType.PDF_STRUCTURAL
        assert ev1.bounding_box is None  # Guarantee zero fabricated bounding boxes
        assert ev1.coordinate_system is None
        assert ev1.confidence == 0.95

        assert f1.case_id == "case-123"
        assert f1.category == FindingCategory.PDF_STRUCTURE
        assert f1.severity == FindingSeverity.HIGH
        assert f1.confidence == 0.95
        assert f1.status == FindingStatus.DETECTED
        assert f1.evidence_ids == [ev1.id]  # Grounded to supporting evidence
        assert "Forms saved in Adobe Acrobat" in f1.limitations[0]

        assert l1 == (f1.id, ev1.id)

        # 2. Second observation check (metadata)
        ev2 = evidence_nodes[1]
        f2 = findings[1]
        assert ev2.evidence_type == EvidenceType.METADATA
        assert f2.category == FindingCategory.DOCUMENT_INCONSISTENCY
        assert f2.severity == FindingSeverity.LOW


class TestMapperAndExceptions:
    """Validate mapper behavior and exception handling."""

    def test_mapper_handles_empty_report(self) -> None:
        report = {
            "verdict": {"label": "no-indicators", "level": "info", "complete": True},
            "findings": [],
            "facts": {"revisions": {"revision_count": 1}},
            "errors": [],
        }
        output = map_upstream_report(report, duration_ms=10.0)
        assert output.analyzer_id == "pdf-structural-analyzer"
        assert output.status == PipelineStatus.SUCCEEDED
        assert len(output.observations) == 0
        assert len(output.capabilities_executed) > 0
        rev_cap = next(c for c in output.capabilities_executed if "revisions" in c.capability_id)
        assert rev_cap.status == "PASS"

    def test_analyzer_input_validation(self, tmp_path: Path) -> None:
        analyzer = PdfStructuralAnalyzer()
        dummy_file = tmp_path / "test.pdf"
        dummy_file.write_bytes(b"%PDF-1.4\n%%EOF")

        bad_input = AnalyzerInput(
            file_path=dummy_file,
            declared_media_type="image/jpeg",
            detected_media_type="image/jpeg",  # Incompatible MIME
            document_sha256="abc",
            document_id="doc-1",
            case_id="case-1",
            processing_run_id="run-1",
        )
        with pytest.raises(ValidationException):
            analyzer.analyze(bad_input)

    def test_categorical_confidence_preservation_and_null_numeric_confidence(self) -> None:
        """Verify upstream confidence strings are preserved verbatim without numeric fabrication."""
        report = {
            "verdict": {"label": "suspicious", "level": "warn", "complete": True},
            "findings": [
                {
                    "id": "revision.content_modification",
                    "category": "revisions",
                    "title": "Text Changed",
                    "explanation": "Text replaced between revisions.",
                    "severity": "high",
                    "confidence": "high",
                    "page": 1,
                    "evidence": {"added": ["Foo"]},
                },
                {
                    "id": "metadata.inconsistency",
                    "category": "metadata",
                    "title": "Date Order",
                    "explanation": "Dates inverted.",
                    "severity": "medium",
                    "confidence": "medium",
                    "page": None,
                    "evidence": {},
                },
            ],
            "facts": {},
            "errors": [],
        }

        output = map_upstream_report(report, duration_ms=15.0)
        assert len(output.observations) == 2

        obs1 = output.observations[0]
        assert obs1.categorical_confidence == "high"
        assert obs1.confidence is None
        assert obs1.confidence_source == "upstream:pdf-forensics-kit"

        obs2 = output.observations[1]
        assert obs2.categorical_confidence == "medium"
        assert obs2.confidence is None
        assert obs2.confidence_source == "upstream:pdf-forensics-kit"

        normalizer = ForensicResultNormalizer()
        nodes, findings, links = normalizer.normalize(
            output=output,
            case_id="case-1",
            document_id="doc-1",
            processing_run_id="run-1",
        )

        assert len(nodes) == 2
        assert len(findings) == 2

        # Check node 1 and finding 1
        assert nodes[0].categorical_confidence == "high"
        assert nodes[0].confidence is None
        assert nodes[0].confidence_source == "upstream:pdf-forensics-kit"

        assert findings[0].categorical_confidence == "high"
        assert findings[0].confidence is None
        assert findings[0].confidence_source == "upstream:pdf-forensics-kit"
        assert findings[0].confidence_calibration_method == "categorical_uncalibrated"

        # Check node 2 and finding 2
        assert nodes[1].categorical_confidence == "medium"
        assert nodes[1].confidence is None
        assert nodes[1].confidence_source == "upstream:pdf-forensics-kit"

        assert findings[1].categorical_confidence == "medium"
        assert findings[1].confidence is None
        assert findings[1].confidence_source == "upstream:pdf-forensics-kit"
        assert findings[1].confidence_calibration_method == "categorical_uncalibrated"
