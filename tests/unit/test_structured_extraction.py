"""Unit tests for structured field extraction engine, validators, and schemas."""

from __future__ import annotations

from decimal import Decimal

from document_intelligence.domain.enums import (
    CoordinateSystem,
    FieldDataType,
    FieldValidationStatus,
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
from document_intelligence.modules.understanding.extraction.engine import (
    StructuredFieldExtractor,
)
from document_intelligence.modules.understanding.extraction.schemas.bank_statement import (
    BANK_STATEMENT_SCHEMA_V1,
)
from document_intelligence.modules.understanding.extraction.schemas.invoice import (
    INVOICE_SCHEMA_V1,
)
from document_intelligence.modules.understanding.extraction.schemas.receipt import (
    RECEIPT_SCHEMA_V1,
)
from document_intelligence.modules.understanding.extraction.validators import (
    mask_sensitive_account_number,
    normalize_and_validate_currency,
    normalize_and_validate_date,
    normalize_and_validate_decimal,
)


def _build_ocr_doc_with_boxes(
    lines_text: list[str],
    doc_id: str = "doc-ext-test-1",
) -> ExtractedDocumentText:
    """Construct an ExtractedDocumentText fixture with valid bounding boxes and token IDs."""
    lines: list[TextLine] = []
    all_tokens: list[TextToken] = []

    for l_idx, line_str in enumerate(lines_text):
        line_clean = line_str.strip()
        if not line_clean:
            continue
        words = line_clean.split()
        tokens: list[TextToken] = []
        for w_idx, word in enumerate(words):
            col = w_idx % 10
            tok = TextToken(
                id=f"p1_l{l_idx}_t{w_idx}",
                raw_text=word,
                reading_order_index=len(all_tokens),
                bounding_box=BoundingBox(
                    x=round(0.05 + col * 0.08, 3),
                    y=round(0.05 + min(0.85, l_idx * 0.04), 3),
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
                raw_text=line_clean,
                reading_order_index=l_idx,
                tokens=tokens,
                bounding_box=BoundingBox(
                    x=0.05,
                    y=round(0.05 + min(0.85, l_idx * 0.04), 3),
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
        processing_run_id="run-ext-1",
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


class TestStructuredFieldExtractor:
    """Validation suite for structured field extraction engine."""

    def setup_method(self) -> None:
        self.extractor = StructuredFieldExtractor()

    def test_invoice_field_extraction_and_provenance(self) -> None:
        lines = [
            "ACME Industrial Supplies Ltd.",
            "COMMERCIAL INVOICE",
            "United States Operations",
            "Invoice Number: INV-2024-9901",
            "Invoice Date: 2024-03-15",
            "Due Date: 2024-04-15",
            "Bill To: Nexus Global Systems Inc.",
            "Purchase Order: PO-44820",
            "Payment Terms: Net 30",
            "Subtotal: $1,000.00",
            "Tax: $80.00",
            "Total Amount: $1,080.00",
        ]
        doc = _build_ocr_doc_with_boxes(lines)
        result = self.extractor.extract_fields(doc, INVOICE_SCHEMA_V1)

        assert result.schema_id == "invoice_v1"
        assert result.schema_version == "1.0.0"
        assert len(result.fields) >= 8

        # Verify invoice_number
        inv_num = result.fields.get("invoice_number")
        assert inv_num is not None
        assert "INV-2024-9901" in inv_num.raw_text
        assert inv_num.data_type == FieldDataType.STRING
        assert inv_num.validation_status == FieldValidationStatus.VALID
        assert inv_num.source_page_number == 1
        assert len(inv_num.source_bounding_boxes) > 0
        assert len(inv_num.source_token_ids) > 0

        # Verify dates normalized to ISO 8601
        inv_date = result.fields.get("invoice_date")
        assert inv_date is not None
        assert inv_date.normalized_value == "2024-03-15"
        assert inv_date.data_type == FieldDataType.DATE

        due_date = result.fields.get("due_date")
        assert due_date is not None
        assert due_date.normalized_value == "2024-04-15"

        # Verify exact Decimal financial amounts
        subtotal = result.fields.get("subtotal")
        assert subtotal is not None
        assert subtotal.normalized_value == Decimal("1000.00")

        tax = result.fields.get("tax_amount")
        assert tax is not None
        assert tax.normalized_value == Decimal("80.00")

        total = result.fields.get("total_amount")
        assert total is not None
        assert total.normalized_value == Decimal("1080.00")
        # Arithmetic check passed: 1000.00 + 80.00 == 1080.00
        assert total.validation_status == FieldValidationStatus.VALID
        assert not any("Arithmetic discrepancy" in w for w in total.warnings)

        # Verify currency
        currency = result.fields.get("currency")
        assert currency is not None
        assert currency.normalized_value == "USD"

    def test_invoice_arithmetic_discrepancy_warning(self) -> None:
        lines = [
            "ACME Corp",
            "United States",
            "Invoice #: INV-1234",
            "Invoice Date: 2024-01-10",
            "Subtotal: $1,000.00",
            "Tax: $50.00",
            "Total Amount: $1,200.00",  # Discrepancy: 1000 + 50 != 1200
        ]
        doc = _build_ocr_doc_with_boxes(lines)
        result = self.extractor.extract_fields(doc, INVOICE_SCHEMA_V1)

        total = result.fields.get("total_amount")
        assert total is not None
        assert total.normalized_value == Decimal("1200.00")
        assert total.validation_status == FieldValidationStatus.WARNING
        assert any("Arithmetic discrepancy" in w for w in total.warnings)

    def test_receipt_field_extraction(self) -> None:
        lines = [
            "STARBUCKS COFFEE #104",
            "Receipt Number: REC-88319",
            "Date: 2024-02-14",
            "Subtotal: $12.50",
            "Tax Amount: $1.25",
            "Total Amount: $13.75",
            "Payment Method: VISA",
        ]
        doc = _build_ocr_doc_with_boxes(lines)
        result = self.extractor.extract_fields(doc, RECEIPT_SCHEMA_V1)

        assert result.schema_id == "receipt_v1"
        assert result.fields.get("receipt_number") is not None
        assert result.fields.get("total_amount") is not None
        assert result.fields["total_amount"].normalized_value == Decimal("13.75")

    def test_bank_statement_extraction_and_account_masking(self) -> None:
        lines = [
            "CHASE BANK",
            "MONTHLY STATEMENT",
            "Statement Period: 2024-01-01 through 2024-01-31",
            "Account Number: 987654321098",
            "Opening Balance: $5,000.00",
            "Closing Balance: $7,500.00",
        ]
        doc = _build_ocr_doc_with_boxes(lines)
        result = self.extractor.extract_fields(doc, BANK_STATEMENT_SCHEMA_V1)

        assert result.schema_id == "bank_statement_v1"

        # Verify masked account number
        acct_field = result.fields.get("account_number_masked")
        assert acct_field is not None
        # Masked value must preserve only last 4 digits
        assert acct_field.normalized_value == "****1098"
        assert "987654321098" not in str(acct_field.normalized_value)
        assert "987654321098" not in str(acct_field.raw_text)

        # Verify balances as exact Decimals
        open_bal = result.fields.get("opening_balance")
        assert open_bal is not None
        assert open_bal.normalized_value == Decimal("5000.00")

        close_bal = result.fields.get("closing_balance")
        assert close_bal is not None
        assert close_bal.normalized_value == Decimal("7500.00")

    def test_missing_fields_gracefully_handled(self) -> None:
        lines = [
            "INVOICE",
            "Invoice Number: INV-001",
        ]
        doc = _build_ocr_doc_with_boxes(lines)
        result = self.extractor.extract_fields(doc, INVOICE_SCHEMA_V1)

        assert "invoice_number" in result.fields
        # Optional fields missing are simply omitted
        assert "purchase_order" not in result.fields
        assert "payment_terms" not in result.fields

    def test_no_fabricated_bounding_boxes(self) -> None:
        # Create doc where tokens have NO bounding boxes
        doc = _build_ocr_doc_with_boxes(["Invoice Number: INV-990"])
        # Clear bounding boxes
        for p in doc.pages:
            for t in p.tokens:
                t.bounding_box = None
            for line in p.lines:
                line.bounding_box = None

        result = self.extractor.extract_fields(doc, INVOICE_SCHEMA_V1)
        inv_field = result.fields.get("invoice_number")
        assert inv_field is not None
        # Must be empty list, NOT fabricated or filled with dummy 0,0,0,0
        assert inv_field.source_bounding_boxes == []


class TestFieldValidators:
    """Validation suite for data type normalizers and security masking."""

    def test_date_normalizer_formats(self) -> None:
        # ISO
        val, w, _ = normalize_and_validate_date("2024-03-15")
        assert val == "2024-03-15" and not w

        # Unambiguous US format MM/DD/YYYY (day > 12)
        val, w, _ = normalize_and_validate_date("03/15/2024")
        assert val == "2024-03-15" and not w

        # Unambiguous UK/EU format DD-MM-YYYY (day > 12)
        val, w, _ = normalize_and_validate_date("15-03-2024")
        assert val == "2024-03-15" and not w

        # Verbose month
        val, w, _ = normalize_and_validate_date("15 March 2024")
        assert val == "2024-03-15" and not w

        # Ambiguous date without context returns None with ambiguity warning and candidate options
        val, w, cands = normalize_and_validate_date("03/04/2024")
        assert val is None
        assert len(cands) == 2
        assert "2024-03-04" in cands and "2024-04-03" in cands

        # Unparseable date returns None with warning
        val, w, _ = normalize_and_validate_date("NotADate")
        assert val is None and len(w) > 0

    def test_currency_normalizer(self) -> None:
        # With explicit document context
        assert (
            normalize_and_validate_currency(
                "$", document_context="Invoice from United States Supplier"
            )[0]
            == "USD"
        )
        assert (
            normalize_and_validate_currency("$", document_context="Invoice from Canada Supplier")[0]
            == "CAD"
        )
        # Without context, $ is unresolved/ambiguous
        val, w = normalize_and_validate_currency("$")
        assert val is None and "Ambiguous" in w[0]

        # Explicit codes
        assert normalize_and_validate_currency("USD")[0] == "USD"
        assert normalize_and_validate_currency("€")[0] == "EUR"
        assert normalize_and_validate_currency("EUR")[0] == "EUR"
        assert normalize_and_validate_currency("£")[0] == "GBP"
        assert normalize_and_validate_currency("GBP")[0] == "GBP"
        assert normalize_and_validate_currency("₹")[0] == "INR"

    def test_decimal_normalizer(self) -> None:
        assert normalize_and_validate_decimal("$1,250.50")[0] == Decimal("1250.50")
        assert normalize_and_validate_decimal("1250.50")[0] == Decimal("1250.50")
        assert normalize_and_validate_decimal("500")[0] == Decimal("500")
        assert normalize_and_validate_decimal("-45.20")[0] == Decimal("-45.20")
        assert normalize_and_validate_decimal("(100.50)")[0] == Decimal("-100.50")
        assert normalize_and_validate_decimal("1.250,50")[0] == Decimal("1250.50")
        assert normalize_and_validate_decimal("1 250.50")[0] == Decimal("1250.50")

    def test_account_number_masking_security(self) -> None:
        assert mask_sensitive_account_number("123456789012") == "****9012"
        assert mask_sensitive_account_number("9988776655") == "****6655"
        assert mask_sensitive_account_number("123") == "****"
