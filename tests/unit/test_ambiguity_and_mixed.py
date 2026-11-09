"""Unit tests for ambiguous date/currency handling and mixed-document multi-page behavior."""

from __future__ import annotations

from document_intelligence.domain.enums import (
    CoordinateSystem,
    DocumentClass,
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
from document_intelligence.modules.understanding.classification.classifier import (
    RuleBasedDocumentClassifier,
)
from document_intelligence.modules.understanding.extraction.engine import (
    StructuredFieldExtractor,
)
from document_intelligence.modules.understanding.extraction.schemas.invoice import (
    INVOICE_SCHEMA_V1,
)
from document_intelligence.modules.understanding.extraction.schemas.receipt import (
    RECEIPT_SCHEMA_V1,
)
from document_intelligence.modules.understanding.extraction.validators import (
    normalize_and_validate_currency,
    normalize_and_validate_date,
)


def _make_page(page_num: int, text: str) -> ExtractedPage:
    """Helper creating an ExtractedPage with tokens."""
    lines_str = text.strip().split("\n")
    lines: list[TextLine] = []
    tokens: list[TextToken] = []

    for l_idx, l_str in enumerate(lines_str):
        clean = l_str.strip()
        if not clean:
            continue
        words = clean.split()
        line_tokens: list[TextToken] = []
        for w_idx, w in enumerate(words):
            col = w_idx % 10
            tok = TextToken(
                id=f"p{page_num}_l{l_idx}_t{w_idx}",
                raw_text=w,
                reading_order_index=len(tokens),
                page_number=page_num,
                bounding_box=BoundingBox(
                    x=round(0.05 + col * 0.08, 3),
                    y=round(0.05 + l_idx * 0.04, 3),
                    width=0.07,
                    height=0.03,
                    coordinate_system=CoordinateSystem.NORMALIZED_0_1,
                ),
            )
            line_tokens.append(tok)
            tokens.append(tok)

        lines.append(
            TextLine(
                id=f"p{page_num}_l{l_idx}",
                raw_text=clean,
                reading_order_index=l_idx,
                page_number=page_num,
                tokens=line_tokens,
                bounding_box=BoundingBox(
                    x=0.05,
                    y=round(0.05 + l_idx * 0.04, 3),
                    width=0.85,
                    height=0.03,
                    coordinate_system=CoordinateSystem.NORMALIZED_0_1,
                ),
            )
        )

    return ExtractedPage(
        page_number=page_num,
        geometry=PageGeometry(width=612.0, height=792.0),
        raw_text=text,
        normalized_text=text,
        lines=lines,
        blocks=[TextBlock(id=f"p{page_num}_b0", raw_text=text, reading_order_index=0, lines=lines)],
        tokens=tokens,
    )


class TestAmbiguousDateAndCurrency:
    """Validation of ambiguous vs unambiguous date and currency resolution."""

    def test_ambiguous_date_without_context_preserves_candidates(self) -> None:
        val, warnings, candidates = normalize_and_validate_date("03/04/2024")
        assert val is None
        assert len(warnings) == 1
        assert "Ambiguous date" in warnings[0]
        assert "could represent 2024-03-04 (US format) or 2024-04-03 (UK/EU format)" in warnings[0]
        assert candidates == ["2024-03-04", "2024-04-03"]

    def test_ambiguous_date_resolved_by_us_context(self) -> None:
        val, warnings, candidates = normalize_and_validate_date(
            "03/04/2024", document_context="Supplier located in New York, United States."
        )
        assert val == "2024-03-04"
        assert len(warnings) == 1
        assert "Resolved ambiguous date" in warnings[0]
        assert "US format" in warnings[0]

    def test_ambiguous_date_resolved_by_eu_context(self) -> None:
        val, warnings, candidates = normalize_and_validate_date(
            "03/04/2024",
            document_context="London Office, United Kingdom. VAT Registration GB99214.",
        )
        assert val == "2024-04-03"
        assert len(warnings) == 1
        assert "Resolved ambiguous date" in warnings[0]
        assert "UK/EU format" in warnings[0]

    def test_unambiguous_dates_pass_cleanly(self) -> None:
        # Day > 12 is unambiguous
        assert normalize_and_validate_date("15/03/2024")[0] == "2024-03-15"
        assert normalize_and_validate_date("03/15/2024")[0] == "2024-03-15"
        # ISO is unambiguous
        assert normalize_and_validate_date("2024-03-15")[0] == "2024-03-15"
        # Verbose month is unambiguous
        assert normalize_and_validate_date("15 March 2024")[0] == "2024-03-15"

    def test_invalid_dates_distinct_from_ambiguous(self) -> None:
        val, warnings, candidates = normalize_and_validate_date("32/13/2024")
        assert val is None
        assert not candidates
        assert "Invalid" in warnings[0] or "Unrecognized" in warnings[0]

    def test_ambiguous_dollar_symbol_without_context(self) -> None:
        val, warnings = normalize_and_validate_currency("$")
        assert val is None
        assert "Ambiguous currency symbol '$'" in warnings[0]

    def test_ambiguous_dollar_symbol_with_context(self) -> None:
        assert (
            normalize_and_validate_currency("$", document_context="United States Corp, USD")[0]
            == "USD"
        )
        assert (
            normalize_and_validate_currency("$", document_context="Toronto, Canada, CAD")[0]
            == "CAD"
        )
        assert (
            normalize_and_validate_currency("$", document_context="Sydney, Australia, AUD")[0]
            == "AUD"
        )

    def test_ambiguous_yen_yuan_symbol(self) -> None:
        # Without context -> unresolved
        val, warnings = normalize_and_validate_currency("¥")
        assert val is None
        assert "Ambiguous currency symbol '¥'" in warnings[0]

        # With context -> resolved
        assert normalize_and_validate_currency("¥", document_context="Tokyo, Japan JPY")[0] == "JPY"
        assert (
            normalize_and_validate_currency("¥", document_context="Beijing, China CNY")[0] == "CNY"
        )

    def test_unknown_currency_never_fabricated(self) -> None:
        val, warnings = normalize_and_validate_currency("XYZ999")
        assert val is None
        assert "Unresolved or unrecognized" in warnings[0]


class TestMixedDocumentExtraction:
    """Verifies page-level classification and structured extraction across heterogeneous document pages."""

    def test_mixed_document_page_classifications_and_aggregation(self) -> None:
        p1_text = """
        ACME SUPPLIES INC.
        COMMERCIAL INVOICE
        Invoice Number: INV-9901
        Date: 2024-03-15
        Total Amount: $500.00
        """
        p2_text = """
        TARGET STORE #104
        SALES RECEIPT
        Cashier: Sarah
        Total: $42.50
        VISA TENDERED
        """
        p3_text = """
        CHASE BANK
        MONTHLY ACCOUNT STATEMENT
        Account Number: 987654321098
        Beginning Balance: $1,000.00
        Ending Balance: $1,457.50
        """

        p1 = _make_page(1, p1_text)
        p2 = _make_page(2, p2_text)
        p3 = _make_page(3, p3_text)

        doc = ExtractedDocumentText(
            document_id="doc-mixed-1",
            processing_run_id="run-mixed-1",
            engine_metadata=OcrEngineMetadata(engine_name="mock-ocr", engine_version="1.0.0"),
            pages=[p1, p2, p3],
            total_pages=3,
            full_raw_text=f"{p1_text}\n{p2_text}\n{p3_text}",
            full_normalized_text=f"{p1_text}\n{p2_text}\n{p3_text}",
        )

        classifier = RuleBasedDocumentClassifier()
        class_res = classifier.classify_document(doc)

        # 1. Verify page-level classification breakdown
        assert len(class_res.page_classifications) == 3
        assert class_res.page_classifications[0].page_number == 1
        assert class_res.page_classifications[0].predicted_class == DocumentClass.INVOICE

        assert class_res.page_classifications[1].page_number == 2
        assert class_res.page_classifications[1].predicted_class == DocumentClass.RECEIPT

        assert class_res.page_classifications[2].page_number == 3
        assert class_res.page_classifications[2].predicted_class == DocumentClass.BANK_STATEMENT

        # 2. Verify document-level extraction correctly tracks source page numbers
        extractor = StructuredFieldExtractor()
        inv_res = extractor.extract_fields(doc, INVOICE_SCHEMA_V1)
        assert inv_res.fields["invoice_number"].source_page_number == 1

        # 3. Targeted page extraction via options
        rec_res = extractor.extract_fields(doc, RECEIPT_SCHEMA_V1, options={"page_number": 2})
        assert "receipt_number" in rec_res.fields or "merchant_name" in rec_res.fields
        for f in rec_res.fields.values():
            assert f.source_page_number == 2
