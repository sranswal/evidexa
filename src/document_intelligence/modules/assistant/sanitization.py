"""Sensitive data protection, PII minimization, and evidence utility preservation.

Ensures sensitive financial identifiers (bank accounts, PANs, Aadhaar numbers, SSNs,
credit card numbers, and EINs) are masked prior to external LLM prompt serialization
or audit logging, while preserving legitimate evidence identifiers (invoice numbers,
transaction references, dates, and currency amounts).

Known Limitations & Boundary Notice:
- Regex-based heuristic masking is a deterministic defense-in-depth layer, NOT a guarantee
  of comprehensive semantic entity recognition.
- Unstructured personal names and non-standard international tax schemes are not masked by regex alone.
- EVIDEXA combines regex minimization with architectural case isolation, least-privilege retrieval,
  and ephemeral snapshot processing to protect case integrity.
"""

from __future__ import annotations

import re
from typing import Any

# 1. Protected legitimate evidence patterns (Protected from accidental over-masking)
# Dates: YYYY-MM-DD, DD-MM-YYYY, YYYY/MM/DD, DD/MM/YYYY
_RE_PROTECTED_DATE = re.compile(
    r"\b(?:19|20)\d{2}[-/](?:0[1-9]|1[0-2])[-/](?:0[1-9]|[12]\d|3[01])\b|"
    r"\b(?:0[1-9]|[12]\d|3[01])[-/](?:0[1-9]|1[0-2])[-/](?:19|20)\d{2}\b"
)
# Evidence references: INV-..., PO-..., TXN-..., REF-..., CASE-..., DOC-...
_RE_PROTECTED_REF = re.compile(
    r"\b(?:INV|TXN|PO|REF|CASE|DOC)[-_][A-Za-z0-9-_]{3,24}\b", re.IGNORECASE
)

# 2. Sensitive identifier patterns
# Indian PAN: 5 letters, 4 digits, 1 letter (handles spaces/dashes: ABCDE 1234 F or ABCDE1234F)
_RE_PAN = re.compile(r"\b[A-Z]{5}[ -]?[0-9]{4}[ -]?[A-Z]\b", re.IGNORECASE)
# Indian Aadhaar: 12 digits (4-4-4 or spaced)
_RE_AADHAAR = re.compile(r"\b\d{4}[ -]\d{4}[ -]\d{4}\b")
# US SSN: 3-2-4 digits
_RE_SSN = re.compile(r"\b\d{3}[ -]\d{2}[ -]\d{4}\b")
# Credit Card: 16 digits formatted in 4-4-4-4
_RE_CREDIT_CARD = re.compile(r"\b(?:\d{4}[ -]){3}\d{4}\b")
# US EIN: 2-7 digits
_RE_EIN = re.compile(r"\b\d{2}-\d{7}\b")
# Formatted bank account: 3-5 digits grouped with dashes/spaces
_RE_FORMATTED_ACCOUNT = re.compile(r"\b(?:\d{3,5}[ -]){2,4}\d{2,6}\b")
# OCR-split digits (e.g., "1 2 3 4  5 6 7 8" or "1 2 3 4 5 6 7 8 9 0")
_RE_OCR_SPLIT_DIGITS = re.compile(r"\b(?:\d[ ]+){7,17}\d\b")
# Raw unformatted digit sequences (8-18 digits)
_RE_RAW_DIGIT_SEQUENCE = re.compile(r"\b\d{8,18}\b")
# International Bank Account Number (IBAN)
_RE_IBAN = re.compile(r"\b[A-Z]{2}\d{2}[A-Z0-9]{4}\d{7,16}\b", re.IGNORECASE)


def mask_sensitive_value(val: str) -> str:
    """Mask a single identifier preserving up to 4 terminal characters."""
    cleaned_digits = re.sub(r"[ -]", "", val)
    if len(cleaned_digits) >= 4:
        return f"****{cleaned_digits[-4:]}"
    return "****"


def sanitize_text(text: str | None) -> str:
    """Apply multi-pattern sanitization to arbitrary prose, OCR strings, or extracted fields.

    Preserves legitimate dates, invoice numbers, and transaction codes using placeholder tokens.
    """
    if not text:
        return ""

    # Temporary protection stash for legitimate evidence references
    stash: dict[str, str] = {}
    stash_counter = 0

    def _stash_match(m: re.Match[str]) -> str:
        nonlocal stash_counter
        placeholder = f"__EVIDEXA_PROTECTED_{stash_counter}__"
        stash[placeholder] = m.group(0)
        stash_counter += 1
        return placeholder

    # 1. Protect legitimate dates
    sanitized = _RE_PROTECTED_DATE.sub(_stash_match, text)

    # 2. Protect legitimate evidence reference codes (e.g. INV-2026-0042, TXN-98765432)
    sanitized = _RE_PROTECTED_REF.sub(_stash_match, sanitized)

    # 3. Mask credit card numbers
    sanitized = _RE_CREDIT_CARD.sub(lambda m: mask_sensitive_value(m.group(0)), sanitized)

    # 4. Mask Aadhaar numbers
    sanitized = _RE_AADHAAR.sub(lambda m: mask_sensitive_value(m.group(0)), sanitized)

    # 5. Mask US SSN
    sanitized = _RE_SSN.sub(lambda m: mask_sensitive_value(m.group(0)), sanitized)

    # 6. Mask EIN
    sanitized = _RE_EIN.sub(lambda m: mask_sensitive_value(m.group(0)), sanitized)

    # 7. Mask PAN identifiers (including space/dash separated)
    sanitized = _RE_PAN.sub(lambda m: mask_sensitive_value(m.group(0)), sanitized)

    # 8. Mask IBAN
    sanitized = _RE_IBAN.sub(lambda m: mask_sensitive_value(m.group(0)), sanitized)

    # 9. Mask OCR-split space-separated digits (e.g. "1 2 3 4 5 6 7 8 9 0")
    sanitized = _RE_OCR_SPLIT_DIGITS.sub(lambda m: mask_sensitive_value(m.group(0)), sanitized)

    # 10. Mask formatted spaced/dashed account numbers
    sanitized = _RE_FORMATTED_ACCOUNT.sub(lambda m: mask_sensitive_value(m.group(0)), sanitized)

    # 11. Mask raw unformatted digit sequences (8-18 digits)
    sanitized = _RE_RAW_DIGIT_SEQUENCE.sub(lambda m: mask_sensitive_value(m.group(0)), sanitized)

    # 12. Restore protected legitimate evidence tokens
    for placeholder, original in stash.items():
        sanitized = sanitized.replace(placeholder, original)

    return sanitized


def sanitize_data_structure(data: Any) -> Any:
    """Recursively sanitize all string leaves within nested dicts, lists, or primitives."""
    if isinstance(data, str):
        return sanitize_text(data)
    if isinstance(data, dict):
        return {k: sanitize_data_structure(v) for k, v in data.items()}
    if isinstance(data, list):
        return [sanitize_data_structure(item) for item in data]
    return data
