"""Field validation, date/currency normalization, arithmetic reconciliation, and PII masking."""

from __future__ import annotations

import re
from datetime import datetime
from decimal import Decimal, InvalidOperation

from document_intelligence.domain.enums import FieldValidationStatus
from document_intelligence.domain.models.extraction import ExtractedFieldValue

# ISO currency symbol and code mapping with minor-unit decimal precision
CURRENCY_MINOR_UNITS: dict[str, int] = {
    "JPY": 0,
    "KRW": 0,
    "VND": 0,
    "USD": 2,
    "EUR": 2,
    "GBP": 2,
    "INR": 2,
    "CAD": 2,
    "AUD": 2,
    "CHF": 2,
    "CNY": 2,
    "SGD": 2,
    "NZD": 2,
    "BHD": 3,
    "KWD": 3,
    "OMR": 3,
}

# Unambiguous symbol mappings
UNAMBIGUOUS_CURRENCIES: dict[str, str] = {
    "€": "EUR",
    "eur": "EUR",
    "euro": "EUR",
    "₹": "INR",
    "inr": "INR",
    "rs": "INR",
    "rs.": "INR",
    "rupee": "INR",
    "rupees": "INR",
    "gbp": "GBP",
    "cad": "CAD",
    "aud": "AUD",
    "chf": "CHF",
    "jpy": "JPY",
    "cny": "CNY",
    "usd": "USD",
}

DATE_FORMATS = [
    "%Y-%m-%d",
    "%Y/%m/%d",
    "%B %d, %Y",
    "%b %d, %Y",
    "%d %B %Y",
    "%d %b %Y",
    "%d-%b-%Y",
    "%d-%B-%Y",
]


def normalize_and_validate_date(
    raw_text: str,
    document_context: str = "",
) -> tuple[str | None, list[str], list[str]]:
    """Parse raw date string and convert to canonical ISO 8601 YYYY-MM-DD.

    Identifies ambiguous dates (e.g. 03/04/2024) where month and day are both <= 12.
    Returns (normalized_date_or_none, list_of_warnings, candidate_interpretations).
    """
    clean = re.sub(r"^[^\w]+|[^\w]+$", "", raw_text.strip())
    clean = re.sub(r"(\d+)(?:st|nd|rd|th)\b", r"\1", clean, flags=re.IGNORECASE)

    if not clean:
        return None, ["Empty date string"], []

    # 1. Inspect ambiguous numeric patterns: MM/DD/YYYY vs DD/MM/YYYY
    num_match = re.match(r"^(\d{1,2})[/\-\.](\d{1,2})[/\-\.](\d{4})$", clean)
    if num_match:
        p1 = int(num_match.group(1))
        p2 = int(num_match.group(2))
        year = int(num_match.group(3))

        if 1 <= p1 <= 12 and 1 <= p2 <= 12 and p1 != p2:
            iso_us = f"{year:04d}-{p1:02d}-{p2:02d}"
            iso_eu = f"{year:04d}-{p2:02d}-{p1:02d}"

            # Check document context for defensible locale disambiguation
            has_us_context = bool(
                re.search(
                    r"\b(?:usa?|united\s+states|new\s+york|california|irs|state\s+of)\b",
                    document_context,
                    re.IGNORECASE,
                )
            )
            has_eu_context = bool(
                re.search(
                    r"\b(?:uk|united\s+kingdom|europe|gstin|vat|london|germany|france|india)\b",
                    document_context,
                    re.IGNORECASE,
                )
            )

            if has_us_context and not has_eu_context:
                return (
                    iso_us,
                    [
                        f"Resolved ambiguous date '{raw_text}' to US format ({iso_us}) via document context."
                    ],
                    [iso_us, iso_eu],
                )
            elif has_eu_context and not has_us_context:
                return (
                    iso_eu,
                    [
                        f"Resolved ambiguous date '{raw_text}' to UK/EU format ({iso_eu}) via document context."
                    ],
                    [iso_us, iso_eu],
                )
            else:
                return (
                    None,
                    [
                        f"Ambiguous date '{raw_text}': could represent {iso_us} (US format) "
                        f"or {iso_eu} (UK/EU format). Unresolved without explicit document context."
                    ],
                    [iso_us, iso_eu],
                )

        elif p1 > 12 and 1 <= p2 <= 12:
            # Unambiguous DD/MM/YYYY
            try:
                dt = datetime(year, p2, p1)
                return dt.strftime("%Y-%m-%d"), [], []
            except ValueError:
                return None, [f"Invalid calendar date: '{raw_text}'"], []

        elif 1 <= p1 <= 12 and p2 > 12:
            # Unambiguous MM/DD/YYYY
            try:
                dt = datetime(year, p1, p2)
                return dt.strftime("%Y-%m-%d"), [], []
            except ValueError:
                return None, [f"Invalid calendar date: '{raw_text}'"], []

    # 2. Try standard unambiguous formats
    if not clean:
        return None, ["Empty date string"], []

    # 1. Inspect ambiguous numeric patterns: MM/DD/YYYY vs DD/MM/YYYY
    num_match = re.match(r"^(\d{1,2})[/\-\.](\d{1,2})[/\-\.](\d{4})$", clean)
    if num_match:
        p1 = int(num_match.group(1))
        p2 = int(num_match.group(2))
        year = int(num_match.group(3))

        if 1 <= p1 <= 12 and 1 <= p2 <= 12 and p1 != p2:
            iso_us = f"{year:04d}-{p1:02d}-{p2:02d}"
            iso_eu = f"{year:04d}-{p2:02d}-{p1:02d}"

            # Check document context for defensible locale disambiguation
            has_us_context = bool(
                re.search(
                    r"\b(?:usa?|united\s+states|new\s+york|california|irs|state\s+of)\b",
                    document_context,
                    re.IGNORECASE,
                )
            )
            has_eu_context = bool(
                re.search(
                    r"\b(?:uk|united\s+kingdom|europe|gstin|vat|london|germany|france|india)\b",
                    document_context,
                    re.IGNORECASE,
                )
            )

            if has_us_context and not has_eu_context:
                return (
                    iso_us,
                    [
                        f"Resolved ambiguous date '{raw_text}' to US format ({iso_us}) via document context."
                    ],
                    [iso_us, iso_eu],
                )
            elif has_eu_context and not has_us_context:
                return (
                    iso_eu,
                    [
                        f"Resolved ambiguous date '{raw_text}' to UK/EU format ({iso_eu}) via document context."
                    ],
                    [iso_us, iso_eu],
                )
            else:
                return (
                    None,
                    [
                        f"Ambiguous date '{raw_text}': could represent {iso_us} (US format) "
                        f"or {iso_eu} (UK/EU format). Unresolved without explicit document context."
                    ],
                    [iso_us, iso_eu],
                )

        elif p1 > 12 and 1 <= p2 <= 12:
            # Unambiguous DD/MM/YYYY
            try:
                dt = datetime(year, p2, p1)
                return dt.strftime("%Y-%m-%d"), [], []
            except ValueError:
                return None, [f"Invalid calendar date: '{raw_text}'"], []

        elif 1 <= p1 <= 12 and p2 > 12:
            # Unambiguous MM/DD/YYYY
            try:
                dt = datetime(year, p1, p2)
                return dt.strftime("%Y-%m-%d"), [], []
            except ValueError:
                return None, [f"Invalid calendar date: '{raw_text}'"], []

    # 2. Try standard unambiguous formats
    for fmt in DATE_FORMATS:
        try:
            dt = datetime.strptime(clean, fmt)
            return dt.strftime("%Y-%m-%d"), [], []
        except ValueError:
            continue

    return None, [f"Unrecognized or invalid date format: '{raw_text}'"], []


def normalize_and_validate_decimal(
    raw_text: str,
    currency: str | None = None,
) -> tuple[Decimal | None, list[str]]:
    """Clean and parse monetary decimal amount using exact Python Decimal arithmetic.

    Never converts through binary float.
    Preserves raw text separately from normalized values.
    Returns (normalized_decimal_or_none, list_of_warnings).
    """
    clean = raw_text.strip()
    if not clean:
        return None, ["Empty decimal string"]

    is_negative = False
    if clean.startswith("(") and clean.endswith(")"):
        is_negative = True
        clean = clean[1:-1].strip()
    elif clean.startswith("-"):
        is_negative = True
        clean = clean[1:].strip()
    elif clean.endswith("-"):
        is_negative = True
        clean = clean[:-1].strip()

    # Remove non-numeric characters except digits, commas, periods, spaces
    clean = re.sub(r"[^\d,\.\s]", "", clean)
    clean = re.sub(r"\s+", "", clean)  # Remove space thousands separators (e.g. 1 250.50)

    if not clean:
        return None, [f"Could not parse numeric amount from '{raw_text}'"]

    # Handle European format 1.234,50 vs standard 1,234.50
    if "," in clean and "." in clean:
        if clean.rfind(",") > clean.rfind("."):
            # European format: period is thousands, comma is decimal
            clean = clean.replace(".", "").replace(",", ".")
        else:
            # Standard format: comma is thousands
            clean = clean.replace(",", "")
    elif "," in clean:
        parts = clean.split(",")
        if len(parts[-1]) <= 2:  # Likely decimal separator like 1234,50
            clean = clean.replace(",", ".")
        else:  # Likely thousands separator like 1,000
            clean = clean.replace(",", "")

    try:
        val = Decimal(clean)
        if is_negative:
            val = -val
        return val, []
    except (InvalidOperation, ValueError) as exc:
        return None, [f"Could not parse decimal amount from '{raw_text}': {exc}"]


def normalize_and_validate_currency(
    raw_text: str,
    document_context: str = "",
) -> tuple[str | None, list[str]]:
    """Extract and normalize currency code.

    Avoids blindly assuming $ is USD or ¥ is JPY.
    Preserves ambiguous symbols as unresolved unless document context resolves them.
    If currency is unknown, returns None without fabricating one.
    """
    clean = raw_text.strip()
    if not clean:
        return None, ["Empty currency string"]

    clean_lower = clean.lower()

    # Check for unambiguous explicit names or codes
    for token, code in UNAMBIGUOUS_CURRENCIES.items():
        if token == clean_lower or re.search(rf"\b{re.escape(token)}\b", clean_lower):
            return code, []

    # Check 3-letter uppercase alphabetic ISO codes (e.g. USD, EUR, GBP, CAD)
    iso_match = re.search(r"\b([A-Za-z]{3})\b", clean)
    if iso_match:
        iso_cand = iso_match.group(1).upper()
        if iso_cand in CURRENCY_MINOR_UNITS or iso_cand in UNAMBIGUOUS_CURRENCIES.values():
            return iso_cand, []

    # Ambiguous symbol: Dollar ($)
    if "$" in clean:
        has_us = bool(
            re.search(
                r"\b(?:usd|u\.s\.a?|united\s+states|new\s+york|delaware|california)\b",
                document_context,
                re.IGNORECASE,
            )
        )
        has_cad = bool(
            re.search(
                r"\b(?:cad|canada|canadian|ontario|quebec)\b", document_context, re.IGNORECASE
            )
        )
        has_aud = bool(
            re.search(r"\b(?:aud|australia|australian|sydney)\b", document_context, re.IGNORECASE)
        )

        if has_us and not (has_cad or has_aud):
            return "USD", ["Resolved '$' to USD via document context."]
        elif has_cad and not (has_us or has_aud):
            return "CAD", ["Resolved '$' to CAD via document context."]
        elif has_aud and not (has_us or has_cad):
            return "AUD", ["Resolved '$' to AUD via document context."]
        else:
            return (
                None,
                [
                    "Ambiguous currency symbol '$': unresolved between USD, CAD, AUD without explicit document context."
                ],
            )

    # Ambiguous symbol: Yen / Yuan (¥)
    if "¥" in clean:
        has_jpy = bool(
            re.search(r"\b(?:jpy|japan|japanese|yen|tokyo)\b", document_context, re.IGNORECASE)
        )
        has_cny = bool(
            re.search(
                r"\b(?:cny|rmb|china|chinese|yuan|beijing)\b", document_context, re.IGNORECASE
            )
        )

        if has_jpy and not has_cny:
            return "JPY", ["Resolved '¥' to JPY via document context."]
        elif has_cny and not has_jpy:
            return "CNY", ["Resolved '¥' to CNY via document context."]
        else:
            return (
                None,
                [
                    "Ambiguous currency symbol '¥': unresolved between JPY and CNY without explicit document context."
                ],
            )

    # Ambiguous symbol: Pound (£)
    if "£" in clean:
        has_egp = bool(
            re.search(r"\b(?:egp|egypt|egyptian\s+pound)\b", document_context, re.IGNORECASE)
        )
        if has_egp:
            return "EGP", ["Resolved '£' to EGP via document context."]
        return "GBP", []

    return None, [f"Unresolved or unrecognized currency representation: '{raw_text}'"]

    # Ambiguous symbol: Dollar ($)
    if "$" in clean:
        has_us = bool(
            re.search(
                r"\b(?:usd|u\.s\.a?|united\s+states|new\s+york|delaware|california)\b",
                document_context,
                re.IGNORECASE,
            )
        )
        has_cad = bool(
            re.search(
                r"\b(?:cad|canada|canadian|ontario|quebec)\b", document_context, re.IGNORECASE
            )
        )
        has_aud = bool(
            re.search(r"\b(?:aud|australia|australian|sydney)\b", document_context, re.IGNORECASE)
        )

        if has_us and not (has_cad or has_aud):
            return "USD", ["Resolved '$' to USD via document context."]
        elif has_cad and not (has_us or has_aud):
            return "CAD", ["Resolved '$' to CAD via document context."]
        elif has_aud and not (has_us or has_cad):
            return "AUD", ["Resolved '$' to AUD via document context."]
        else:
            return (
                None,
                [
                    "Ambiguous currency symbol '$': unresolved between USD, CAD, AUD without explicit document context."
                ],
            )

    # Ambiguous symbol: Yen / Yuan (¥)
    if "¥" in clean:
        has_jpy = bool(
            re.search(r"\b(?:jpy|japan|japanese|yen|tokyo)\b", document_context, re.IGNORECASE)
        )
        has_cny = bool(
            re.search(
                r"\b(?:cny|rmb|china|chinese|yuan|beijing)\b", document_context, re.IGNORECASE
            )
        )

        if has_jpy and not has_cny:
            return "JPY", ["Resolved '¥' to JPY via document context."]
        elif has_cny and not has_jpy:
            return "CNY", ["Resolved '¥' to CNY via document context."]
        else:
            return (
                None,
                [
                    "Ambiguous currency symbol '¥': unresolved between JPY and CNY without explicit document context."
                ],
            )

    # Ambiguous symbol: Pound (£)
    if "£" in clean:
        has_egp = bool(
            re.search(r"\b(?:egp|egypt|egyptian\s+pound)\b", document_context, re.IGNORECASE)
        )
        if has_egp:
            return "EGP", ["Resolved '£' to EGP via document context."]
        return "GBP", []

    return None, [f"Unresolved or unrecognized currency representation: '{raw_text}'"]


def mask_sensitive_account_number(raw_text: str) -> str:
    """Mask account number preserving only trailing 4 characters.

    Never logs or exposes the unmasked account number.
    e.g. '123456789012' -> '****9012'
         '1234-5678-9012' -> '****9012'
         '****9012' -> '****9012'
         '123' -> '****'
    """
    clean = re.sub(r"[^\w]", "", raw_text.strip())
    if len(clean) < 4:
        return "****"
    last4 = clean[-4:]
    return f"****{last4}"


def validate_invoice_arithmetic(
    fields: dict[str, ExtractedFieldValue],
    currency: str | None = None,
) -> list[str]:
    """Perform cross-field arithmetic reconciliation on subtotal + tax = total.

    Uses exact Python Decimal arithmetic and currency minor-unit precision rules.
    Discrepancies are categorized as validation warnings, not fraud indicators.
    """
    warnings: list[str] = []
    subtotal_f = fields.get("subtotal")
    tax_f = fields.get("tax_amount")
    total_f = fields.get("total_amount")

    if (
        subtotal_f
        and subtotal_f.normalized_value is not None
        and tax_f
        and tax_f.normalized_value is not None
        and total_f
        and total_f.normalized_value is not None
    ):
        try:
            sub = Decimal(str(subtotal_f.normalized_value))
            tax = Decimal(str(tax_f.normalized_value))
            tot = Decimal(str(total_f.normalized_value))
        except (InvalidOperation, ValueError):
            return warnings

        expected_total = sub + tax
        diff = abs(expected_total - tot)

        # Minor-unit tolerance determination
        if currency and currency in CURRENCY_MINOR_UNITS:
            minor_units = CURRENCY_MINOR_UNITS[currency]
            if minor_units == 0:
                tolerance = Decimal("1.00")
            elif minor_units == 3:
                tolerance = Decimal("0.005")
            else:
                tolerance = Decimal("0.05")  # Standard penny rounding across line items
        else:
            # Universal documented default tolerance for unknown currency
            tolerance = Decimal("0.05")

        if diff > tolerance:
            msg = (
                f"Arithmetic discrepancy: subtotal ({sub}) + tax ({tax}) "
                f"= {expected_total}, but total is {tot} (difference: {diff}, "
                f"reconciliation tolerance: {tolerance})."
            )
            warnings.append(msg)
            total_f.warnings.append(msg)
            total_f.validation_status = FieldValidationStatus.WARNING

    return warnings
