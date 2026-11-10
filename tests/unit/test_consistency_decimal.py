"""Unit tests verifying Decimal precision, currency semantics, and financial comparison correctness."""

from decimal import Decimal

from document_intelligence.domain.enums import ConsistencyOutcome
from document_intelligence.modules.consistency.financial import (
    compare_monetary_amounts,
    normalize_currency_code,
    parse_decimal,
)


class TestFinancialPrecision:
    """Rigorous verification of Decimal parsing and monetary comparisons."""

    def test_parse_decimal_clean_integers_and_decimals(self) -> None:
        assert parse_decimal("100") == Decimal("100")
        assert parse_decimal("100.50") == Decimal("100.50")
        assert parse_decimal(100) == Decimal("100")
        assert parse_decimal(100.5) == Decimal("100.5")
        assert parse_decimal(Decimal("45000.75")) == Decimal("45000.75")

    def test_parse_decimal_handles_currency_symbols_and_thousands_separators(self) -> None:
        assert parse_decimal("$1,250.75") == Decimal("1250.75")
        assert parse_decimal("€ 12.450,50") == Decimal("12450.50")
        assert parse_decimal("₹ 85,000.00") == Decimal("85000.00")
        assert parse_decimal("£ 3,450.25") == Decimal("3450.25")
        assert parse_decimal("¥ 50000") == Decimal("50000")

    def test_parse_decimal_empty_or_invalid_returns_none(self) -> None:
        assert parse_decimal(None) is None
        assert parse_decimal("") is None
        assert parse_decimal("   ") is None
        assert parse_decimal("N/A") is None
        assert parse_decimal("NOT_A_NUMBER") is None

    def test_normalize_currency_code(self) -> None:
        assert normalize_currency_code("$") == "USD"
        assert normalize_currency_code("€") == "EUR"
        assert normalize_currency_code("£") == "GBP"
        assert normalize_currency_code("₹") == "INR"
        assert normalize_currency_code("usd") == "USD"
        assert normalize_currency_code("EUR") == "EUR"
        assert normalize_currency_code(None) is None
        assert normalize_currency_code("INVALID_TOO_LONG") is None

    def test_monetary_comparison_exact_match(self) -> None:
        res = compare_monetary_amounts(
            amount_a_val="85000.00",
            currency_a_val="INR",
            amount_b_val="85000.00",
            currency_b_val="INR",
            tolerance=Decimal("0.00"),
        )
        assert res.outcome == ConsistencyOutcome.CONSISTENT
        assert res.difference == Decimal("0.00")
        assert res.within_tolerance is True
        assert res.is_currency_compatible is True

    def test_monetary_comparison_differing_totals_inconsistent(self) -> None:
        res = compare_monetary_amounts(
            amount_a_val="85000.00",
            currency_a_val="INR",
            amount_b_val="95000.00",
            currency_b_val="INR",
            tolerance=Decimal("0.00"),
            label_a="Invoice INV-104",
            label_b="Receipt REC-201",
        )
        assert res.outcome == ConsistencyOutcome.INCONSISTENT
        assert res.difference == Decimal("10000.00")
        assert res.within_tolerance is False
        assert (
            "Invoice INV-104 has 85000.00 INR whereas Receipt REC-201 has 95000.00 INR"
            in res.explanation
        )
        assert "10000.00 INR" in res.explanation

    def test_monetary_comparison_currency_mismatch_never_numeric_diff(self) -> None:
        res = compare_monetary_amounts(
            amount_a_val="1000.00",
            currency_a_val="USD",
            amount_b_val="1000.00",
            currency_b_val="EUR",
        )
        assert res.outcome == ConsistencyOutcome.INCONSISTENT
        assert res.is_currency_compatible is False
        assert res.difference is None  # Never computes cross-currency difference
        assert (
            "Currency mismatch: Document A is in USD while Document B is in EUR" in res.explanation
        )

    def test_monetary_comparison_configurable_tolerance(self) -> None:
        # Diff is 0.05; with 0.00 tolerance -> INCONSISTENT
        res_strict = compare_monetary_amounts(
            amount_a_val="100.05",
            currency_a_val="USD",
            amount_b_val="100.00",
            currency_b_val="USD",
            tolerance=Decimal("0.00"),
        )
        assert res_strict.outcome == ConsistencyOutcome.INCONSISTENT

        # With 0.10 tolerance -> CONSISTENT
        res_tolerant = compare_monetary_amounts(
            amount_a_val="100.05",
            currency_a_val="USD",
            amount_b_val="100.00",
            currency_b_val="USD",
            tolerance=Decimal("0.10"),
        )
        assert res_tolerant.outcome == ConsistencyOutcome.CONSISTENT
        assert res_tolerant.within_tolerance is True
        assert res_tolerant.difference == Decimal("0.05")

    def test_monetary_comparison_missing_field_insufficient_evidence(self) -> None:
        res = compare_monetary_amounts(
            amount_a_val="100.00",
            currency_a_val="USD",
            amount_b_val=None,
            currency_b_val="USD",
        )
        assert res.outcome == ConsistencyOutcome.INSUFFICIENT_EVIDENCE
        assert res.difference is None
        assert "missing or invalid" in res.explanation

    def test_no_float_distortion_on_subtraction(self) -> None:
        # Standard floating point trap: 0.1 + 0.2 != 0.3
        val_a = parse_decimal("0.30")
        val_b = parse_decimal("0.10") + parse_decimal("0.20")
        assert val_a == val_b
        assert str(val_b) == "0.30"
