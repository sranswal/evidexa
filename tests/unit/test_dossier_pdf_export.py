"""Unit tests for PDF and JSON Dossier Exporters."""

from __future__ import annotations

import io
import json

import pikepdf

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
from document_intelligence.modules.dossier.export.json_exporter import JsonDossierExporter
from document_intelligence.modules.dossier.export.pdf_exporter import PdfDossierExporter
from document_intelligence.modules.dossier.generator import DossierGenerator


def _make_test_dossier():
    case = Case(
        id="case-export-001",
        title="Operation Aurora Case Dossier",
        description="Comprehensive audit and document forensics analysis",
        status=CaseStatus.ACTIVE,
    )
    doc1 = Document(
        id=generate_id(),
        case_id=case.id,
        original_filename="bank_statement_2026.pdf",
        storage_key=f"storage/{case.id}/bank_statement_2026.pdf",
        media_type="application/pdf",
        file_extension=".pdf",
        file_size_bytes=102400,
        page_count=5,
        sha256="1" * 64,
    )
    doc2 = Document(
        id=generate_id(),
        case_id=case.id,
        original_filename="invoice_march.pdf",
        storage_key=f"storage/{case.id}/invoice_march.pdf",
        media_type="application/pdf",
        file_extension=".pdf",
        file_size_bytes=42000,
        page_count=2,
        sha256="2" * 64,
    )

    finding = AggregatedFinding(
        id="agg-001",
        case_id=case.id,
        source_type="FORENSIC_FINDING",
        source_id="ff-101",
        category=AggregatedFindingCategory.DOCUMENT_INTEGRITY,
        evidentiary_classification=EvidentiaryClassification.INVESTIGATOR_CONCLUSION,
        source_status="DETECTED",
        review_status="CONFIRM_OBSERVATION",
        title="Discrepancy in Bank Statement Running Balance",
        description="Line item math does not sum to closing balance on page 2.",
        explanation="Detected by Financial Analysis Rule FA-101 with confidence 0.99",
        severity=FindingSeverity.HIGH,
        affected_document_ids=[doc1.id],
        is_reviewed=True,
    )

    review = AggregatedFindingReview(
        finding_id=finding.id,
        case_id=case.id,
        action=InvestigatorReviewAction.CONFIRM_OBSERVATION,
        reviewer_id="lead-investigator",
        comment="Confirmed arithmetic mismatch against bank counterparty confirmation.",
        previous_status="UNREVIEWED",
        new_status="CONFIRM_OBSERVATION",
    )

    generator = DossierGenerator()
    dossier = generator.generate(
        case=case,
        documents=[doc1, doc2],
        aggregated_findings=[finding],
        reviews=[review],
        created_by="lead-investigator",
    )
    return dossier


def test_pdf_dossier_exporter_generates_valid_pdf():
    dossier = _make_test_dossier()
    exporter = PdfDossierExporter()

    pdf_bytes = exporter.export(dossier)
    assert isinstance(pdf_bytes, bytes)
    assert len(pdf_bytes) > 500

    # Read back with pikepdf to verify PDF syntax and page structure
    with pikepdf.open(io.BytesIO(pdf_bytes)) as pdf:
        assert len(pdf.pages) >= 1
        page1 = pdf.pages[0]
        assert page1.MediaBox[2] == 612
        assert page1.MediaBox[3] == 792
        # Check fonts dictionary
        fonts = page1.Resources.Font
        assert pikepdf.Name.F1 in fonts
        assert pikepdf.Name.F2 in fonts


def test_json_dossier_exporter_generates_audit_ready_schema():
    dossier = _make_test_dossier()
    exporter = JsonDossierExporter()

    json_str = exporter.export(dossier)
    data = json.loads(json_str)

    assert data["dossier_id"] == dossier.id
    assert data["case_id"] == dossier.case_id
    assert len(data["sections"]) == 12
    assert "legal_disclaimer" in data
    assert "fraud determination" in data["legal_disclaimer"]
    assert len(data["document_summaries"]) == 2
