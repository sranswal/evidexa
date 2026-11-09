"""Deterministic tax identifier normalization with explicit jurisdiction and type preservation."""

from __future__ import annotations

import re
import unicodedata

# Known tax identifier pattern definitions
TAX_PATTERNS: list[tuple[str, str, re.Pattern[str], bool]] = [
    # (jurisdiction, identifier_type, regex, is_sensitive)
    ("US", "US_EIN", re.compile(r"^\b(\d{2})[- ]?(\d{7})\b$"), False),
    ("US", "US_SSN", re.compile(r"^\b(\d{3})[- ]?(\d{2})[- ]?(\d{4})\b$"), True),
    ("UK", "UK_VAT", re.compile(r"^\b(GB)?\s?(\d{3}\s?\d{4}\s?\d{2})\b$", re.IGNORECASE), False),
    ("IN", "IN_PAN", re.compile(r"^\b([A-Z]{5}\d{4}[A-Z])\b$", re.IGNORECASE), False),
    (
        "IN",
        "IN_GSTIN",
        re.compile(r"^\b(\d{2}[A-Z]{5}\d{4}[A-Z][1-9A-Z]Z[0-9A-Z])\b$", re.IGNORECASE),
        False,
    ),
    ("EU", "EU_VAT", re.compile(r"^\b([A-Z]{2})\s?([0-9A-Z]{8,12})\b$", re.IGNORECASE), False),
]


def normalize_tax_identifier(
    raw_val: str,
    declared_jurisdiction: str | None = None,
    declared_type: str | None = None,
) -> tuple[str, str | None, str | None, bool]:
    """Normalize tax and registration identifiers while preserving jurisdiction and typing.

    Returns:
        tuple[normalized_identifier, jurisdiction, identifier_type, is_sensitive]
        - normalized_identifier: Canonical representation without spaces/dashes (or masked if sensitive).
        - jurisdiction: ISO country/region code (e.g. "US", "UK", "IN").
        - identifier_type: Specific tax scheme (e.g. "US_EIN", "UK_VAT").
        - is_sensitive: Whether identifier is sensitive personal identifier (e.g. SSN).
    """
    if not raw_val or not raw_val.strip():
        return "", None, None, False

    clean = unicodedata.normalize("NFKC", raw_val).strip()

    # If identifier is already masked (e.g. "***-**-6789" or "****1234"), preserve it safely
    if "*" in clean:
        return clean, declared_jurisdiction, declared_type or "MASKED_TAX_ID", True

    clean_alnum = re.sub(r"[\s\-_]", "", clean).upper()

    # 1. Match against known patterns
    for jurisdiction, id_type, pattern, sensitive in TAX_PATTERNS:
        if pattern.match(clean):
            # Format according to known rules
            if sensitive:
                # Sensitive personal identifiers must be masked immediately
                last4 = clean_alnum[-4:] if len(clean_alnum) >= 4 else clean_alnum
                masked = f"***-**-{last4}"
                return masked, jurisdiction, id_type, True
            return clean_alnum, jurisdiction, id_type, False

    # 2. Unknown or unclassified tax identifier
    return clean_alnum, declared_jurisdiction, declared_type or "GENERIC_TAX_ID", False
