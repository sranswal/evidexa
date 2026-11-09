"""Unit tests for exact financial Decimal arithmetic, precision, and currency policies."""

from __future__ import annotations

from decimal import Decimal

from document_intelligence.domain.enums import FieldValidationStatus
from document_intelligence.domain.models.extraction import ExtractedFieldValue
from document_intelligence.modules.understanding.extraction.validators import (
    CURRENCY_MINOR_UNITS,
    normalize_and_validate_decimal,
    validate_invoice_arithmetic,
)


class TestFinancialPrecision:
    """Verifies that all monetary amounts use exact Python Decimal without binary float conversion."""

    def test_exact_decimal_addition_no_float_imprecision(self) -> None:
        """Verifies 0.1 + 0.2 == 0.3 exact decimal arithmetic (which fails in binary float: 0.30000000000000004)."""
        d1, w1 = normalize_and_validate_decimal("0.10")
        d2, w2 = normalize_and_validate_decimal("0.20")
        assert d1 is not None and d2 is not None
        assert isinstance(d1, Decimal)
        assert isinstance(d2, Decimal)
        assert d1 + d2 == Decimal("0.30")
        assert float(d1) + float(d2) != d1 + d2 or d1 + d2 == Decimal("0.30")

    def test_large_monetary_values(self) -> None:
        """Verifies large financial amounts retain exact precision without floating-point overflow/loss."""
        val_str = "100,000,000,000.99"
        d, w = normalize_and_validate_decimal(val_str)
        assert d is not None
        assert d == Decimal("100000000000.99")
        assert not w

    def test_negative_amounts_and_accounting_parentheses(self) -> None:
        """Verifies negative numbers in standard and accounting formats (e.g. (1,250.00))."""
        d1, _ = normalize_and_validate_decimal("(1,250.50)")
        assert d1 == Decimal("-1250.50")

        d2, _ = normalize_and_validate_decimal("-1,250.50")
        assert d2 == Decimal("-1250.50")

        d3, _ = normalize_and_validate_decimal("1,250.50-")
        assert d3 == Decimal("-1250.50")

    def test_european_decimal_notation(self) -> None:
        """Verifies European period-thousands, comma-decimal notation (e.g. 1.250,50)."""
        d, _ = normalize_and_validate_decimal("1.250,50")
        assert d == Decimal("1250.50")

        d_large, _ = normalize_and_validate_decimal("12.345.678,95")
        assert d_large == Decimal("12345678.95")

    def test_space_thousands_separators(self) -> None:
        """Verifies space-separated thousands (e.g. 1 250.50 or 5 000 000)."""
        d, _ = normalize_and_validate_decimal("1 250.50")
        assert d == Decimal("1250.50")

        d2, _ = normalize_and_validate_decimal("5 000 000.00")
        assert d2 == Decimal("5000000.00")

    def test_currency_minor_unit_precision_policies(self) -> None:
        """Verifies minor-unit precision definitions across global currencies."""
        assert CURRENCY_MINOR_UNITS["USD"] == 2
        assert CURRENCY_MINOR_UNITS["EUR"] == 2
        assert CURRENCY_MINOR_UNITS["GBP"] == 2
        assert CURRENCY_MINOR_UNITS["INR"] == 2
        assert CURRENCY_MINOR_UNITS["JPY"] == 0  # Zero decimal currency
        assert CURRENCY_MINOR_UNITS["KRW"] == 0
        assert CURRENCY_MINOR_UNITS["KWD"] == 3  # Three decimal currency

    def test_invoice_arithmetic_exact_match(self) -> None:
        """Verifies subtotal + tax == total exact match produces no warnings."""
        fields = {
            "subtotal": ExtractedFieldValue(
                field_key="subtotal",
                label="Subtotal",
                data_type="DECIMAL",
                normalized_value=Decimal("100.00"),
                source_document_id="doc-1",
                source_page_number=1,
            ),
            "tax_amount": ExtractedFieldValue(
                field_key="tax_amount",
                label="Tax",
                data_type="DECIMAL",
                normalized_value=Decimal("8.00"),
                source_document_id="doc-1",
                source_page_number=1,
            ),
            "total_amount": ExtractedFieldValue(
                field_key="total_amount",
                label="Total",
                data_type="DECIMAL",
                normalized_value=Decimal("108.00"),
                source_document_id="doc-1",
                source_page_number=1,
            ),
        }
        warnings = validate_invoice_arithmetic(fields, currency="USD")
        assert not warnings
        assert fields["total_amount"].validation_status != FieldValidationStatus.WARNING

    def test_invoice_arithmetic_discrepancy_warning(self) -> None:
        """Verifies discrepancy triggers validation warning without claiming fraud."""
        fields = {
            "subtotal": ExtractedFieldValue(
                field_key="subtotal",
                label="Subtotal",
                data_type="DECIMAL",
                normalized_value=Decimal("100.00"),
                source_document_id="doc-1",
                source_page_number=1,
            ),
            "tax_amount": ExtractedFieldValue(
                field_key="tax_amount",
                label="Tax",
                data_type="DECIMAL",
                normalized_value=Decimal("8.00"),
                source_document_id="doc-1",
                source_page_number=1,
            ),
            "total_amount": ExtractedFieldValue(
                field_key="total_amount",
                label="Total",
                data_type="DECIMAL",
                normalized_value=Decimal("120.00"),  # Discrepancy
                source_document_id="doc-1",
                source_page_number=1,
            ),
        }
        warnings = validate_invoice_arithmetic(fields, currency="USD")
        assert len(warnings) == 1
        assert "Arithmetic discrepancy" in warnings[0]
        assert "subtotal (100.00) + tax (8.00) = 108.00, but total is 120.00" in warnings[0]
        assert fields["total_amount"].validation_status == FieldValidationStatus.WARNING

    def test_invoice_arithmetic_minor_unit_jpy_tolerance(self) -> None:
        """Verifies JPY minor-unit (0 decimals) tolerance policy."""
        fields = {
            "subtotal": ExtractedFieldValue(
                field_key="subtotal",
                label="Subtotal",
                data_type="DECIMAL",
                normalized_value=Decimal("1000"),
                source_document_id="doc-1",
                source_page_number=1,
            ),
            "tax_amount": ExtractedFieldValue(
                field_key="tax_amount",
                label="Tax",
                data_type="DECIMAL",
                normalized_value=Decimal("100"),
                source_document_id="doc-1",
                source_page_number=1,
            ),
            "total_amount": ExtractedFieldValue(
                field_key="total_amount",
                label="Total",
                data_type="DECIMAL",
                normalized_value=Decimal("1100"),
                source_document_id="doc-1",
                source_page_number=1,
            ),
        }
        warnings = validate_invoice_arithmetic(fields, currency="JPY")
        assert not warnings

    def test_unknown_currency_reconciliation_policy(self) -> None:
        """Verifies unknown currency uses documented default tolerance (0.05)."""
        fields = {
            "subtotal": ExtractedFieldValue(
                field_key="subtotal",
                label="Subtotal",
                data_type="DECIMAL",
                normalized_value=Decimal("50.00"),
                source_document_id="doc-1",
                source_page_number=1,
            ),
            "tax_amount": ExtractedFieldValue(
                field_key="tax_amount",
                label="Tax",
                data_type="DECIMAL",
                normalized_value=Decimal("5.00"),
                source_document_id="doc-1",
                source_page_number=1,
            ),
            "total_amount": ExtractedFieldValue(
                field_key="total_amount",
                label="Total",
                data_type="DECIMAL",
                normalized_value=Decimal("55.03"),  # Within 0.05 tolerance
                source_document_id="doc-1",
                source_page_number=1,
            ),
        }
        warnings = validate_invoice_arithmetic(fields, currency=None)
        assert not warnings
