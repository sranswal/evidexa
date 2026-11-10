"""Deterministic, versioned normalization pipeline for multilingual document intelligence.

Preserves original raw text byte-for-byte, applies Unicode NFC composition,
converts Devanagari numerals to ASCII digits in normalized representations,
preserves currency symbols, punctuation, identifiers, and digit groupings,
and flags ambiguous or lossy transformations for forensic review.
"""

from __future__ import annotations

import unicodedata
from typing import Any

from document_intelligence.domain.enums import NormalizationForm
from document_intelligence.domain.models.bounding_box import BoundingBox
from document_intelligence.domain.models.ocr import (
    TextToken,
    classify_text_script,
    convert_devanagari_numerals,
)

NORMALIZATION_PIPELINE_VERSION = "2.0.0"


class TextNormalizer:
    """Deterministic, versioned text normalizer supporting multilingual forensics."""

    def __init__(self, version: str = NORMALIZATION_PIPELINE_VERSION) -> None:
        self.version = version

    def normalize_text(self, raw_text: str) -> tuple[str, list[str], bool, str | None]:
        """Normalize raw text using Unicode NFC and Devanagari numeral translation.

        Returns:
            (normalized_text, applied_transformations, is_uncertain, uncertainty_reason)
        """
        if not raw_text:
            return "", [], False, None

        applied_transformations: list[str] = []
        is_uncertain = False
        uncertainty_reason: str | None = None

        # 1. Check for ambiguity or lossy characters
        if "\ufffd" in raw_text:
            is_uncertain = True
            uncertainty_reason = (
                "Ambiguous Unicode replacement character (U+FFFD) detected in raw text."
            )
        else:
            # Check for unassigned or invalid control characters (excluding standard whitespace)
            for ch in raw_text:
                if unicodedata.category(ch) == "Cc" and ch not in ("\n", "\r", "\t"):
                    is_uncertain = True
                    uncertainty_reason = f"Control character (U+{ord(ch):04X}) detected in text."
                    break

        # 2. Canonical Unicode NFC composition (never NFKC which destroys fractions/symbols)
        nfc_text = unicodedata.normalize("NFC", raw_text)
        if nfc_text != raw_text:
            applied_transformations.append("unicode_nfc")

        # 3. Devanagari numeral conversion to ASCII digits (only in normalized representation)
        converted_text, had_numeral_conversion = convert_devanagari_numerals(nfc_text)
        if had_numeral_conversion:
            applied_transformations.append("devanagari_numerals")

        return converted_text, applied_transformations, is_uncertain, uncertainty_reason

    def normalize_token(
        self,
        raw_text: str,
        bounding_box: BoundingBox | None = None,
        confidence: float | None = None,
        reading_order_index: int = 0,
        is_coordinate_uncertain: bool = False,
        coordinate_uncertainty_reason: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> TextToken:
        """Construct a TextToken with full forensic provenance and versioned normalization trace."""
        norm_text, transforms, is_uncertain, uncertainty_reason = self.normalize_text(raw_text)

        # Classify script based on raw text
        script = classify_text_script(raw_text)

        token_meta = dict(metadata or {})
        token_meta["normalization_version"] = self.version
        if transforms:
            token_meta["applied_transformations"] = transforms

        had_conversion = "devanagari_numerals" in transforms
        if had_conversion:
            token_meta["original_numeral_system"] = "DEVANAGARI"
            token_meta["raw_numeral_value"] = raw_text

        if is_coordinate_uncertain and not coordinate_uncertainty_reason:
            coordinate_uncertainty_reason = "Uncertain bounding box coordinates."

        final_uncertain = is_uncertain or is_coordinate_uncertain
        final_reason = uncertainty_reason or coordinate_uncertainty_reason
        if final_uncertain and not final_reason:
            final_reason = "Uncertain character normalization or bounding box coordinates."

        return TextToken(
            raw_text=raw_text,
            normalized_text=norm_text,
            bounding_box=bounding_box,
            confidence=confidence,
            reading_order_index=reading_order_index,
            is_coordinate_uncertain=is_coordinate_uncertain,
            coordinate_uncertainty_reason=coordinate_uncertainty_reason,
            detected_script=script,
            is_numeral_converted=had_conversion,
            normalization_form=NormalizationForm.NFC,
            original_numeral_system="DEVANAGARI" if had_conversion else None,
            original_raw_value=raw_text if had_conversion else None,
            is_uncertain=final_uncertain,
            uncertainty_reason=final_reason,
            metadata=token_meta,
        )


# Global default normalizer instance
default_normalizer = TextNormalizer()
