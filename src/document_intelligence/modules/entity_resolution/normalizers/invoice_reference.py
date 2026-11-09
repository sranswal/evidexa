"""Deterministic invoice and transaction reference normalization preserving leading zeros."""

from __future__ import annotations

import re
import unicodedata


def normalize_invoice_reference(raw_ref: str) -> str:
    """Normalize invoice or transaction reference while strictly preserving leading zeros.

    Guarantees:
    - Unicode normalization (NFKC).
    - Conservative whitespace stripping.
    - Preserves internal alphanumeric structure, dashes, and slashes.
    - Strictly preserves leading zeros (e.g. '00123' remains '00123').
    """
    if not raw_ref or not raw_ref.strip():
        return ""

    text = unicodedata.normalize("NFKC", raw_ref).strip()
    # Normalize internal spaces around separators
    text = re.sub(r"\s*([-_/])\s*", r"\1", text)
    # Collapse remaining internal whitespace
    text = re.sub(r"\s+", " ", text)
    # Canonical uppercase for alphanumeric codes
    return text.upper()
