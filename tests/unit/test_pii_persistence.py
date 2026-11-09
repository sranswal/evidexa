"""Unit tests verifying sensitive account number masking across ordinary persistence."""

from __future__ import annotations

import json
from pathlib import Path

from document_intelligence.core.config import Settings
from document_intelligence.domain.enums import (
    CoordinateSystem,
    FieldDataType,
)
from document_intelligence.domain.models.bounding_box import BoundingBox, PageGeometry
from document_intelligence.domain.models.ocr import (
    ExtractedDocumentText,
    ExtractedPage,
    OcrEngineMetadata,
    TextBlock,
    TextLine,
    TextToken,
)
from document_intelligence.infrastructure.persistence.models import EvidenceNodeModel
from document_intelligence.infrastructure.repositories.audit_repository import (
    AuditRepository,
)
from document_intelligence.infrastructure.repositories.case_repository import CaseRepository
from document_intelligence.infrastructure.repositories.document_repository import (
    DocumentRepository,
)
from document_intelligence.infrastructure.repositories.evidence_repository import (
    EvidenceRepository,
)
from document_intelligence.infrastructure.repositories.processing_run_repository import (
    ProcessingRunRepository,
)
from document_intelligence.infrastructure.storage.filesystem import FilesystemDocumentStorage
from document_intelligence.modules.audit.ledger import AuditLedgerService
from document_intelligence.modules.cases.service import CaseService
from document_intelligence.modules.understanding.extraction.engine import (
    StructuredFieldExtractor,
)
from document_intelligence.modules.understanding.extraction.schemas.bank_statement import (
    BANK_STATEMENT_SCHEMA_V1,
)
from document_intelligence.modules.understanding.extraction.validators import (
    mask_sensitive_account_number,
)
from document_intelligence.modules.understanding.service import (
    DocumentUnderstandingService,
)


def _build_ocr_doc_with_account_text(
    account_line: str,
    doc_id: str = "doc-pii-test-1",
) -> ExtractedDocumentText:
    """Helper creating mock OCR text with a specific synthetic account number."""
    lines_text = [
        "FIRST NATIONAL BANK",
        "STATEMENT OF ACCOUNT",
        "Statement Period: 2024-01-01 through 2024-01-31",
        account_line,
        "Opening Balance: $10,000.00",
        "Closing Balance: $12,500.00",
    ]
    lines: list[TextLine] = []
    all_tokens: list[TextToken] = []

    for l_idx, line_str in enumerate(lines_text):
        words = line_str.split()
        tokens: list[TextToken] = []
        for w_idx, word in enumerate(words):
            col = w_idx % 10
            tok = TextToken(
                id=f"p1_l{l_idx}_t{w_idx}",
                raw_text=word,
                reading_order_index=len(all_tokens),
                bounding_box=BoundingBox(
                    x=round(0.05 + col * 0.08, 3),
                    y=round(0.05 + l_idx * 0.04, 3),
                    width=0.07,
                    height=0.03,
                    coordinate_system=CoordinateSystem.NORMALIZED_0_1,
                ),
            )
            tokens.append(tok)
            all_tokens.append(tok)

        lines.append(
            TextLine(
                id=f"p1_l{l_idx}",
                raw_text=line_str,
                reading_order_index=l_idx,
                tokens=tokens,
                bounding_box=BoundingBox(
                    x=0.05,
                    y=round(0.05 + l_idx * 0.04, 3),
                    width=0.85,
                    height=0.03,
                    coordinate_system=CoordinateSystem.NORMALIZED_0_1,
                ),
            )
        )

    full_text = "\n".join(lines_text)
    page = ExtractedPage(
        page_number=1,
        geometry=PageGeometry(width=612.0, height=792.0),
        raw_text=full_text,
        normalized_text=full_text,
        lines=lines,
        blocks=[
            TextBlock(
                id="p1_b0",
                raw_text=full_text,
                reading_order_index=0,
                lines=lines,
            )
        ],
        tokens=all_tokens,
    )

    return ExtractedDocumentText(
        document_id=doc_id,
        processing_run_id="run-ocr-pii",
        engine_metadata=OcrEngineMetadata(
            engine_name="mock-ocr",
            engine_version="1.0.0",
        ),
        pages=[page],
        total_pages=1,
        total_tokens=len(all_tokens),
        full_raw_text=full_text,
        full_normalized_text=full_text,
    )


class TestPiiPersistenceHardening:
    """Verifies sensitive account numbers are never persisted in plaintext."""

    def test_mask_sensitive_account_number_formats(self) -> None:
        """Verifies masking rules across long, short, and formatted account numbers."""
        assert mask_sensitive_account_number("987654321098") == "****1098"
        assert mask_sensitive_account_number("1234-5678-9012") == "****9012"
        assert mask_sensitive_account_number("1234 5678 9012") == "****9012"
        assert mask_sensitive_account_number("ACC/44556677") == "****6677"
        assert mask_sensitive_account_number("123") == "****"
        assert mask_sensitive_account_number("****1098") == "****1098"

    def test_engine_masks_account_in_raw_and_candidates(self) -> None:
        """Verifies ExtractedFieldValue and candidate alternatives never retain unmasked plaintext."""
        synthetic_acct = "987654321098"
        doc = _build_ocr_doc_with_account_text(f"Account Number: {synthetic_acct}")

        extractor = StructuredFieldExtractor()
        result = extractor.extract_fields(doc, BANK_STATEMENT_SCHEMA_V1)

        acct_field = result.fields.get("account_number_masked")
        assert acct_field is not None
        assert acct_field.data_type == FieldDataType.MASKED_STRING

        # Invariant 1: normalized_value is masked
        assert acct_field.normalized_value == "****1098"
        assert synthetic_acct not in str(acct_field.normalized_value)

        # Invariant 2: raw_text in ExtractedFieldValue is masked
        assert acct_field.raw_text == "****1098"
        assert synthetic_acct not in acct_field.raw_text

        # Invariant 3: alternative_candidates have masked raw_text and normalized_value
        for alt in acct_field.alternative_candidates:
            assert synthetic_acct not in alt.raw_text
            assert synthetic_acct not in str(alt.normalized_value)

        # Invariant 4: JSON dump contains zero occurrences of synthetic account number
        json_output = result.model_dump_json()
        assert synthetic_acct not in json_output

    def test_end_to_end_persistence_audit_zero_plaintext_leak(
        self, db_session, tmp_path: Path
    ) -> None:
        """Inspects actual SQLite database rows and filesystem artifact bytes on disk."""
        synthetic_acct = "412356789988"
        doc = _build_ocr_doc_with_account_text(
            f"Account Number: {synthetic_acct}", doc_id="doc-e2e-pii"
        )

        custom_settings = Settings(DATA_DIR=tmp_path / "data")
        storage = FilesystemDocumentStorage(app_settings=custom_settings)
        case_repo = CaseRepository(db_session)
        doc_repo = DocumentRepository(db_session)
        run_repo = ProcessingRunRepository(db_session)
        ev_repo = EvidenceRepository(db_session)
        audit_repo = AuditRepository(db_session)
        audit_service = AuditLedgerService(audit_repo)

        case_service = CaseService(case_repo, audit_service)
        case = case_service.create_case(title="PII Persistence Case")

        # Save document entity and fake OCR artifact
        from document_intelligence.domain.enums import PipelineStatus
        from document_intelligence.domain.models.document import Document
        from document_intelligence.domain.models.processing_run import ProcessingRun

        doc_entity = Document(
            id="doc-e2e-pii",
            case_id=case.id,
            original_filename="statement.pdf",
            media_type="application/pdf",
            file_extension=".pdf",
            file_size_bytes=1024,
            sha256="0" * 64,
            storage_key=f"{case.id}/doc-e2e-pii.pdf",
        )
        doc_repo.save(doc_entity)

        ocr_run = ProcessingRun(
            case_id=case.id,
            document_ids=["doc-e2e-pii"],
            pipeline_name="pdfium-ocr-engine",
            pipeline_version="1.0.0",
            status=PipelineStatus.SUCCEEDED,
        )
        run_repo.save(ocr_run)

        # Store OCR artifact
        ocr_art_name = f"ocr_{ocr_run.id}_extracted.json"
        storage.store_artifact(
            case_id=case.id,
            document_id="doc-e2e-pii",
            processing_run_id=ocr_run.id,
            artifact_filename=ocr_art_name,
            data=doc.model_dump_json().encode("utf-8"),
        )

        service = DocumentUnderstandingService(
            case_service=case_service,
            document_repo=doc_repo,
            run_repo=run_repo,
            evidence_repo=ev_repo,
            audit_service=audit_service,
            storage=storage,
        )

        # Execute extraction
        res = service.extract_fields(case.id, "doc-e2e-pii", schema_id="bank_statement_v1")
        assert res.fields["account_number_masked"].normalized_value == "****9988"

        # 1. Inspect actual SQLite EvidenceNode row in database
        ev_model = (
            db_session.query(EvidenceNodeModel)
            .filter_by(
                case_id=case.id,
                document_id="doc-e2e-pii",
                evidence_type="EXTRACTED_FIELD",
            )
            .filter(EvidenceNodeModel.title.contains("account_number_masked"))
            .first()
        )
        assert ev_model is not None
        # Raw value column must NOT contain unmasked account number
        assert ev_model.raw_value == "****9988"
        assert synthetic_acct not in str(ev_model.raw_value)
        # Normalized value column must NOT contain unmasked account number
        assert ev_model.normalized_value == "****9988"
        assert synthetic_acct not in str(ev_model.normalized_value)
        # Metadata column must NOT contain unmasked account number
        assert synthetic_acct not in json.dumps(ev_model.node_metadata)

        # 2. Inspect filesystem JSON artifact bytes on disk
        art_path = storage.get_artifact_path(res.storage_artifact_key)
        assert art_path.exists()
        art_bytes = art_path.read_bytes()
        art_text = art_bytes.decode("utf-8")
        assert synthetic_acct not in art_text
        assert "****9988" in art_text
