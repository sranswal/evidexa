"""Unit tests for deterministic entity normalization across all entity types."""

from __future__ import annotations

from decimal import Decimal

from document_intelligence.modules.entity_resolution.normalizers import (
    normalize_bank_account_reference,
    normalize_currency_amount,
    normalize_invoice_reference,
    normalize_organization_name,
    normalize_person_name,
    normalize_tax_identifier,
)


class TestOrganizationNormalization:
    """Test organization Unicode, whitespace, punctuation, and legal suffix extraction."""

    def test_case_and_whitespace_normalization(self) -> None:
        norm, base, suffix = normalize_organization_name("   ACME   CORP   ")
        assert norm == "acme corp"
        assert base == "acme"
        assert suffix == "CORP"

    def test_unicode_and_punctuation_variations(self) -> None:
        # Fullwidth unicode and non-breaking spaces
        norm, base, suffix = normalize_organization_name("ＡＣＭＥ，　Ｉｎｃ．")
        assert base == "acme"
        assert suffix == "INC"
        assert norm == "acme inc"

    def test_legal_suffix_extraction_signal(self) -> None:
        cases = [
            ("Global Logistics LLC", "global logistics", "LLC"),
            ("Wayne Enterprises, Ltd.", "wayne enterprises", "LTD"),
            ("Stark Industries Incorporated", "stark industries", "INC"),
            ("Bayerische Motoren Werke GmbH", "bayerische motoren werke", "GMBH"),
            ("Tata Consultancy Services Pvt. Ltd.", "tata consultancy services", "PVT_LTD"),
            ("Acme & Sons Company", "acme & sons", "CO"),
        ]
        for raw, exp_base, exp_suffix in cases:
            norm, base, suffix = normalize_organization_name(raw)
            assert base == exp_base
            assert suffix == exp_suffix

    def test_meaningful_tokens_not_blindly_stripped(self) -> None:
        # "General Motors" has no legal suffix and its tokens must be preserved
        norm, base, suffix = normalize_organization_name("General Motors")
        assert norm == "general motors"
        assert base == "general motors"
        assert suffix is None


class TestPersonNormalization:
    """Test person name normalization, case folding, and honorific extraction."""

    def test_person_name_case_and_whitespace(self) -> None:
        norm, base, title = normalize_person_name("  John   Q.   Public  ")
        assert norm == "john q public"
        assert base == "john q public"
        assert title is None

    def test_person_title_extraction(self) -> None:
        cases = [
            ("Dr. Alice Smith", "alice smith", "DR"),
            ("Prof. Robert Oppenheimer", "robert oppenheimer", "PROF"),
            ("Ms. Eleanor Vance", "eleanor vance", "MS"),
            ("Mr. Bruce Wayne, Esq.", "bruce wayne", "MR"),
        ]
        for raw, exp_base, exp_title in cases:
            norm, base, title = normalize_person_name(raw)
            assert base == exp_base
            assert title == exp_title


class TestTaxIdentifierNormalization:
    """Test jurisdiction preservation, identifier typing, and PII masking."""

    def test_us_ein_formatting(self) -> None:
        norm, jur, id_type, sensitive = normalize_tax_identifier("12-3456789")
        assert norm == "123456789"
        assert jur == "US"
        assert id_type == "US_EIN"
        assert not sensitive

    def test_us_ssn_immediately_masked(self) -> None:
        # Sensitive SSNs must never be preserved in unmasked plaintext
        norm, jur, id_type, sensitive = normalize_tax_identifier("123-45-6789")
        assert norm == "***-**-6789"
        assert jur == "US"
        assert id_type == "US_SSN"
        assert sensitive
        assert "123456789" not in norm

    def test_uk_vat_and_in_pan(self) -> None:
        norm, jur, id_type, _ = normalize_tax_identifier("GB 123 4567 89")
        assert jur == "UK"
        assert id_type == "UK_VAT"

        norm_pan, jur_pan, id_pan, _ = normalize_tax_identifier("ABCDE1234F")
        assert norm_pan == "ABCDE1234F"
        assert jur_pan == "IN"
        assert id_pan == "IN_PAN"


class TestInvoiceReferenceNormalization:
    """Test preservation of leading zeros and reference alphanumeric structure."""

    def test_leading_zeros_preserved(self) -> None:
        norm = normalize_invoice_reference("00123")
        assert norm == "00123"
        assert norm.startswith("00")

    def test_formatted_invoice_reference(self) -> None:
        norm = normalize_invoice_reference("  INV - 2024 / 0098  ")
        assert norm == "INV-2024/0098"


class TestBankAccountNormalization:
    """Test strict privacy masking of bank account references."""

    def test_bank_account_sanitized_to_masked(self) -> None:
        norm = normalize_bank_account_reference("987654321098")
        assert norm == "****1098"
        assert "98765432" not in norm

    def test_idempotent_on_masked(self) -> None:
        norm = normalize_bank_account_reference("****1098")
        assert norm == "****1098"


class TestCurrencyAmountNormalization:
    """Test exact Decimal conversion, minor unit quantization, and comparison keys."""

    def test_exact_decimal_and_currency_key(self) -> None:
        key, dec, curr = normalize_currency_amount("1,250.50", "USD")
        assert key == "USD:1250.50"
        assert dec == Decimal("1250.50")
        assert curr == "USD"

    def test_jpy_zero_minor_units(self) -> None:
        key, dec, curr = normalize_currency_amount("15000", "JPY")
        assert key == "JPY:15000"
        assert dec == Decimal("15000")
        assert curr == "JPY"

    def test_kwd_three_minor_units(self) -> None:
        key, dec, curr = normalize_currency_amount("12.345", "KWD")
        assert key == "KWD:12.345"
        assert dec == Decimal("12.345")
        assert curr == "KWD"
