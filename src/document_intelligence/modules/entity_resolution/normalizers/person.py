"""Deterministic person name normalization with conservative punctuation and honorific extraction."""

from __future__ import annotations

import re
import unicodedata

PERSON_TITLE_PATTERN = re.compile(
    r"\b(mr\.?|mrs\.?|ms\.?|dr\.?|prof\.?|esq\.?|sir|madam)\b", re.IGNORECASE
)


def normalize_person_name(
    raw_name: str,
) -> tuple[str, str, str | None]:
    """Normalize person name and extract title/honorific as a separate signal.

    Returns:
        tuple[normalized_value, base_name, title]
        - normalized_value: Canonical full representation (e.g. "john doe").
        - base_name: Clean name with title removed (e.g. "john doe").
        - title: Extracted title/honorific (e.g. "DR"), or None.
    """
    if not raw_name or not raw_name.strip():
        return "", "", None

    # 1. Unicode normalization (NFKC)
    text = unicodedata.normalize("NFKC", raw_name)

    # 2. Case folding
    text = text.lower().strip()

    # 3. Conservative punctuation removal (retain hyphens and apostrophes inside names)
    text = re.sub(r"[,/\\|#*]", " ", text)
    text = re.sub(r"\.(?=\s|$)", "", text)
    text = re.sub(r"\s+", " ", text).strip()

    # 4. Extract honorific/title
    title: str | None = None
    title_match = PERSON_TITLE_PATTERN.search(text)
    base_name = text

    if title_match:
        title = title_match.group(1).replace(".", "").upper()
        base_candidate = PERSON_TITLE_PATTERN.sub("", text).strip()
        base_candidate = re.sub(r"\s+", " ", base_candidate).strip()
        if base_candidate:
            base_name = base_candidate

    normalized_value = base_name

    return normalized_value, base_name, title
