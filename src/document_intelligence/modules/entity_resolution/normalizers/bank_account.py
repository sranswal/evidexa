"""Deterministic bank account reference normalization strictly enforcing privacy masking."""

from __future__ import annotations

import unicodedata

from document_intelligence.modules.understanding.extraction.validators import (
    mask_sensitive_account_number,
)


def normalize_bank_account_reference(raw_ref: str) -> str:
    """Normalize bank account reference ensuring only masked representations are generated.

    Guarantees:
    - Zero plaintext storage or exposure.
    - Always formatted as '****{last4}' (or '****' if < 4 characters).
    - Idempotent on already masked inputs.
    """
    if not raw_ref or not raw_ref.strip():
        return "****"

    clean = unicodedata.normalize("NFKC", raw_ref).strip()
    return mask_sensitive_account_number(clean)
