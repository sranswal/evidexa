"""Financial precision utilities for deterministic, currency-aware Decimal arithmetic."""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any

from document_intelligence.domain.enums import ConsistencyOutcome

# Standard minor-unit decimal precision mappings (ISO 4217 standard)
CURRENCY_MINOR_UNITS: dict[str, int] = {
    "USD": 2,
    "EUR": 2,
    "GBP": 2,
    "INR": 2,
    "CAD": 2,
    "AUD": 2,
    "SGD": 2,
    "CHF": 2,
    "JPY": 0,
    "KRW": 0,
    "VND": 0,
    "BHD": 3,
    "KWD": 3,
    "OMR": 3,
    "JOD": 3,
}

CURRENCY_SYMBOLS: dict[str, str] = {
    "$": "USD",
    "€": "EUR",
    "£": "GBP",
    "₹": "INR",
    "¥": "JPY",
    "₩": "KRW",
}


def parse_decimal(value: Any) -> Decimal | None:
    """Safely parse a numerical or string value into a Decimal without floating-point distortion.

    Returns None if value is None, empty, or cannot be parsed into a finite Decimal.
    """
    if value is None:
        return None
    if isinstance(value, Decimal):
        return value
    if isinstance(value, (int, float)):
        # Convert float via str to prevent float binary representation artifacts
        return Decimal(str(value))

    val_str = str(value).strip()
    if not val_str:
        return None

    # Strip currency symbols and extraneous whitespace
    for sym in CURRENCY_SYMBOLS:
        val_str = val_str.replace(sym, "")
    val_str = re.sub(r"[^\d.,\-+]", "", val_str)

    # Handle comma as decimal separator if format is e.g. "1.250,50" or "1250,50"
    if "," in val_str and "." in val_str:
        if val_str.rfind(",") > val_str.rfind("."):
            # European: 1.250,50 -> 1250.50
            val_str = val_str.replace(".", "").replace(",", ".")
        else:
            # Anglo-American: 1,250.50 -> 1250.50
            val_str = val_str.replace(",", "")
    elif "," in val_str and "." not in val_str:
        # Check if single comma is decimal separator (e.g. "25,50") or thousands ("1,000")
        parts = val_str.split(",")
        if len(parts) == 2 and len(parts[1]) in (2, 3):
            # Treat as decimal separator
            val_str = val_str.replace(",", ".")
        else:
            val_str = val_str.replace(",", "")

    try:
        parsed = Decimal(val_str)
        if parsed.is_nan() or parsed.is_infinite():
            return None
        return parsed
    except (InvalidOperation, ValueError):
        return None


def normalize_currency_code(currency: str | None) -> str | None:
    """Normalize currency string to ISO 4217 uppercase code if recognizable."""
    if not currency:
        return None
    curr = currency.strip().upper()
    if curr in CURRENCY_SYMBOLS.values():
        return curr
    if curr in CURRENCY_SYMBOLS:
        return CURRENCY_SYMBOLS[curr]
    if len(curr) == 3 and curr.isalpha():
        return curr
    return None


@dataclass(frozen=True)
class MonetaryComparisonResult:
    """Explainable result of comparing two monetary amounts with currency and tolerance awareness."""

    amount_a: Decimal | None
    currency_a: str | None
    amount_b: Decimal | None
    currency_b: str | None
    difference: Decimal | None
    is_currency_compatible: bool
    within_tolerance: bool
    outcome: ConsistencyOutcome
    explanation: str
    difference_formatted: str | None = None


def compare_monetary_amounts(
    amount_a_val: Any,
    currency_a_val: str | None,
    amount_b_val: Any,
    currency_b_val: str | None,
    tolerance: Decimal = Decimal("0.00"),
    label_a: str = "Document A",
    label_b: str = "Document B",
) -> MonetaryComparisonResult:
    """Strict Decimal monetary comparison preserving currency semantics and configurable tolerance.

    Policies:
    - If either amount is None -> INSUFFICIENT_EVIDENCE.
    - If currencies are specified and differ -> INCONSISTENT (never compared as numeric difference).
    - If currencies match or one is unspecified:
        - If abs(diff) <= tolerance -> CONSISTENT.
        - If abs(diff) > tolerance -> INCONSISTENT.
    - Exact difference is always computed as Decimal.
    """
    amount_a = parse_decimal(amount_a_val)
    amount_b = parse_decimal(amount_b_val)
    curr_a = normalize_currency_code(currency_a_val)
    curr_b = normalize_currency_code(currency_b_val)

    if amount_a is None or amount_b is None:
        missing = []
        if amount_a is None:
            missing.append(f"{label_a} amount missing or invalid")
        if amount_b is None:
            missing.append(f"{label_b} amount missing or invalid")
        return MonetaryComparisonResult(
            amount_a=amount_a,
            currency_a=curr_a,
            amount_b=amount_b,
            currency_b=curr_b,
            difference=None,
            is_currency_compatible=True,
            within_tolerance=False,
            outcome=ConsistencyOutcome.INSUFFICIENT_EVIDENCE,
            explanation=f"Cannot compare monetary amounts: {'; '.join(missing)}.",
            difference_formatted=None,
        )

    # Currency compatibility check
    if curr_a and curr_b and curr_a != curr_b:
        return MonetaryComparisonResult(
            amount_a=amount_a,
            currency_a=curr_a,
            amount_b=amount_b,
            currency_b=curr_b,
            difference=None,
            is_currency_compatible=False,
            within_tolerance=False,
            outcome=ConsistencyOutcome.INCONSISTENT,
            explanation=(
                f"Currency mismatch: {label_a} is in {curr_a} while {label_b} is in {curr_b}. "
                "Cross-currency amounts cannot be compared without explicit exchange rate evidence."
            ),
            difference_formatted=f"Currency mismatch ({curr_a} vs {curr_b})",
        )

    # Same currency or at least one currency code unstated
    active_currency = curr_a or curr_b or "UNSPECIFIED"
    diff = (amount_a - amount_b).copy_abs()
    within_tol = diff <= tolerance

    diff_str = f"{diff} {active_currency}"

    if within_tol:
        if diff == Decimal("0.00"):
            explanation = (
                f"Monetary amounts match exactly: {amount_a} {active_currency} on both documents."
            )
        else:
            explanation = (
                f"Monetary amounts are consistent within allowed tolerance of {tolerance} {active_currency}: "
                f"{label_a}={amount_a}, {label_b}={amount_b}, difference={diff_str}."
            )
        return MonetaryComparisonResult(
            amount_a=amount_a,
            currency_a=curr_a,
            amount_b=amount_b,
            currency_b=curr_b,
            difference=diff,
            is_currency_compatible=True,
            within_tolerance=True,
            outcome=ConsistencyOutcome.CONSISTENT,
            explanation=explanation,
            difference_formatted=diff_str,
        )
    else:
        explanation = (
            f"Monetary discrepancy detected: {label_a} has {amount_a} {active_currency} "
            f"whereas {label_b} has {amount_b} {active_currency} (difference of {diff_str})."
        )
        return MonetaryComparisonResult(
            amount_a=amount_a,
            currency_a=curr_a,
            amount_b=amount_b,
            currency_b=curr_b,
            difference=diff,
            is_currency_compatible=True,
            within_tolerance=False,
            outcome=ConsistencyOutcome.INCONSISTENT,
            explanation=explanation,
            difference_formatted=diff_str,
        )
