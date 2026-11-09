"""Deterministic organization name normalization with legal suffix signal extraction."""

from __future__ import annotations

import re
import unicodedata

# Canonical legal suffix map (suffix regex -> canonical identifier)
LEGAL_SUFFIX_MAP: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\b(pvt\.?\s*ltd\.?|private\s+limited)\b", re.IGNORECASE), "PVT_LTD"),
    (re.compile(r"\b(pty\.?\s*ltd\.?|proprietary\s+limited)\b", re.IGNORECASE), "PTY_LTD"),
    (re.compile(r"\b(incorporated|inc\.?)\b", re.IGNORECASE), "INC"),
    (re.compile(r"\b(corporation|corp\.?)\b", re.IGNORECASE), "CORP"),
    (re.compile(r"\b(limited|ltd\.?)\b", re.IGNORECASE), "LTD"),
    (re.compile(r"\b(llc|l\.l\.c\.?)\b", re.IGNORECASE), "LLC"),
    (re.compile(r"\b(plc|p\.l\.c\.?)\b", re.IGNORECASE), "PLC"),
    (re.compile(r"\b(gmbh)\b", re.IGNORECASE), "GMBH"),
    (re.compile(r"\b(s\.a\.?)\b", re.IGNORECASE), "SA"),
    (re.compile(r"\b(company|co\.?)\b", re.IGNORECASE), "CO"),
]


def normalize_organization_name(
    raw_name: str,
) -> tuple[str, str, str | None]:
    """Normalize organization name and extract legal suffix as a separate comparison signal.

    Returns:
        tuple[normalized_value, base_name, legal_suffix]
        - normalized_value: Canonical full representation (e.g. "acme corp").
        - base_name: Suffix-stripped base name (e.g. "acme").
        - legal_suffix: Extracted legal suffix enum string (e.g. "CORP"), or None.
    """
    if not raw_name or not raw_name.strip():
        return "", "", None

    # 1. Unicode normalization (NFKC)
    text = unicodedata.normalize("NFKC", raw_name)

    # 2. Case folding
    text = text.lower().strip()

    # 3. Standardize and conserve meaningful characters (keep letters, numbers, spaces, hyphens, and ampersands)
    text = re.sub(r"[,/\\|#*]", " ", text)
    # Remove periods only when not part of abbreviation or sentence structure
    text = re.sub(r"\.(?=\s|$)", "", text)
    text = re.sub(r"\s+", " ", text).strip()

    # 4. Extract legal suffix as a separate signal
    legal_suffix: str | None = None
    base_name = text

    for pattern, canonical_suffix in LEGAL_SUFFIX_MAP:
        match = pattern.search(text)
        if match:
            legal_suffix = canonical_suffix
            # Remove the matched suffix from base_name, ensuring boundary safety
            base_candidate = pattern.sub("", text).strip()
            # Clean up residual trailing punctuation or whitespace
            base_candidate = re.sub(r"[\s,\.\-]+$", "", base_candidate).strip()
            if base_candidate:
                base_name = base_candidate
            break

    # Re-normalize whitespace on base_name
    base_name = re.sub(r"\s+", " ", base_name).strip()

    # Canonical full normalized value
    normalized_value = f"{base_name} {legal_suffix.lower()}" if legal_suffix else base_name

    return normalized_value, base_name, legal_suffix
