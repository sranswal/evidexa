"""Deterministic currency amount normalization with exact Decimal precision and minor units."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

from document_intelligence.modules.understanding.extraction.validators import (
    CURRENCY_MINOR_UNITS,
    normalize_and_validate_decimal,
)


def normalize_currency_amount(
    raw_amount: str | Decimal,
    currency_code: str | None = None,
) -> tuple[str, Decimal, str]:
    """Normalize monetary amount into canonical key, exact Decimal, and ISO currency code.

    Returns:
        tuple[canonical_key, decimal_amount, currency_code]
        - canonical_key: e.g. 'USD:1250.00' (currency strictly part of key).
        - decimal_amount: Exact Decimal quantized to currency minor units.
        - currency_code: Normalized ISO 4217 currency code (or 'UNKNOWN').
    """
    curr = (currency_code or "UNKNOWN").upper().strip()

    dec_val: Decimal
    if isinstance(raw_amount, Decimal):
        dec_val = raw_amount
    else:
        norm_dec, _ = normalize_and_validate_decimal(str(raw_amount))
        dec_val = norm_dec if norm_dec is not None else Decimal("0.00")

    # Quantize to defined minor units
    minor_units = CURRENCY_MINOR_UNITS.get(curr, 2)
    step = Decimal("1") if minor_units == 0 else Decimal("10") ** (-minor_units)
    try:
        quantized = dec_val.quantize(step)
    except InvalidOperation:
        quantized = dec_val

    canonical_key = f"{curr}:{quantized}"
    return canonical_key, quantized, curr
