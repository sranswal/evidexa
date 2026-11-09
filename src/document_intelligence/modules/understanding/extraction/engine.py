"""Structured field extractor matching schema definitions against extracted OCR text."""

from __future__ import annotations

import logging
import re
import time
from typing import Any

from document_intelligence.domain.enums import (
    CoordinateSystem,
    DocumentClass,
    FieldDataType,
    FieldValidationStatus,
)
from document_intelligence.domain.models.bounding_box import BoundingBox
from document_intelligence.domain.models.extraction import (
    CandidateValue,
    DocumentExtractionResult,
    ExtractedFieldValue,
    ExtractionSchema,
    FieldDefinition,
)
from document_intelligence.domain.models.ocr import (
    ExtractedDocumentText,
    ExtractedPage,
    TextToken,
)
from document_intelligence.modules.understanding.extraction.validators import (
    mask_sensitive_account_number,
    normalize_and_validate_currency,
    normalize_and_validate_date,
    normalize_and_validate_decimal,
    validate_invoice_arithmetic,
)

logger = logging.getLogger(__name__)


# Field extraction regex patterns: list of (pattern, score_bonus)
# Pattern capturing group 1 is extracted value
FIELD_PATTERNS: dict[str, list[tuple[re.Pattern[str], float]]] = {
    # Invoice fields
    "invoice_number": [
        (
            re.compile(
                r"\b(?:invoice\s*(?:no|num|number|#)|inv\s*(?:no|num|number|#))\b[:\s]*([A-Za-z0-9\-_/]+)",
                re.IGNORECASE,
            ),
            1.0,
        ),
        (
            re.compile(
                r"\b(?:invoice|inv)\b\s*#[:\s]*([A-Za-z0-9\-_/]+)",
                re.IGNORECASE,
            ),
            1.0,
        ),
        (re.compile(r"\b(INV-[0-9A-Za-z\-_/]+)\b", re.IGNORECASE), 0.95),
    ],
    "invoice_date": [
        (
            re.compile(
                r"(?:invoice\s*date|date\s*of\s*issue|issue\s*date)[:\s]*([0-9A-Za-z\s,\.\-/]+?)(?:\s*(?:due|terms|po|client|$|\n))",
                re.IGNORECASE,
            ),
            1.0,
        ),
        (
            re.compile(
                r"(?:^|\n)\s*date[:\s]*([0-9A-Za-z\s,\.\-/]+?)(?:\s*(?:due|terms|client|$|\n))",
                re.IGNORECASE,
            ),
            0.7,
        ),
    ],
    "due_date": [
        (
            re.compile(
                r"(?:due\s*date|payment\s*due)[:\s]*([0-9A-Za-z\s,\.\-/]+?)(?:\s*(?:terms|po|client|$|\n))",
                re.IGNORECASE,
            ),
            1.0,
        ),
        (
            re.compile(
                r"(?:pay\s*by)[:\s]*([0-9A-Za-z\s,\.\-/]+?)(?:\s*(?:terms|$|\n))", re.IGNORECASE
            ),
            0.8,
        ),
    ],
    "supplier_name": [
        (re.compile(r"(?:from|vendor|supplier|issued\s*by)[:\s]*([^\n\r]+)", re.IGNORECASE), 0.8),
    ],
    "supplier_tax_id": [
        (
            re.compile(
                r"(?:gstin|vat\s*(?:no|reg|number)?|tin|tax\s*id)[:\s]*([A-Za-z0-9\-_/]+)",
                re.IGNORECASE,
            ),
            1.0,
        ),
    ],
    "buyer_name": [
        (
            re.compile(r"(?:bill\s*to|sold\s*to|client|customer)[:\s]*([^\n\r]+)", re.IGNORECASE),
            0.9,
        ),
    ],
    "buyer_tax_id": [
        (
            re.compile(
                r"(?:buyer\s*(?:tax\s*id|gstin|vat)|client\s*(?:gstin|vat))[:\s]*([A-Za-z0-9\-_/]+)",
                re.IGNORECASE,
            ),
            1.0,
        ),
    ],
    "subtotal": [
        (
            re.compile(
                r"(?:subtotal|sub-total|net\s*amount)[:\s]*([$€£₹\w\s]*[0-9]+[0-9,\.\s]*)",
                re.IGNORECASE,
            ),
            1.0,
        ),
    ],
    "tax_amount": [
        (
            re.compile(
                r"(?:tax|vat|gst|sales\s*tax)(?:\s*amount)?[:\s]*([$€£₹\w\s]*[0-9]+[0-9,\.\s]*)",
                re.IGNORECASE,
            ),
            0.9,
        ),
    ],
    "total_amount": [
        (
            re.compile(
                r"(?:total\s*amount(?:\s*due)?|amount\s*due|grand\s*total|balance\s*due)[:\s]*([$€£₹\w\s]*[0-9]+[0-9,\.\s]*)",
                re.IGNORECASE,
            ),
            1.0,
        ),
        (re.compile(r"(?:^|\n)\s*total[:\s]*([$€£₹\w\s]*[0-9]+[0-9,\.\s]*)", re.IGNORECASE), 0.8),
    ],
    "currency": [
        (re.compile(r"([$€£¥₹]|USD|EUR|GBP|INR|CAD|AUD)", re.IGNORECASE), 0.8),
    ],
    # Receipt fields
    "merchant_name": [
        (re.compile(r"(?:merchant|store|vendor)[:\s]*([^\n\r]+)", re.IGNORECASE), 0.8),
    ],
    "transaction_date": [
        (
            re.compile(
                r"(?:date|time)[:\s]*([0-9A-Za-z\s,\.\-/]+?)(?:\s*(?:time|cashier|slip|$|\n))",
                re.IGNORECASE,
            ),
            0.9,
        ),
    ],
    "receipt_number": [
        (
            re.compile(
                r"(?:receipt\s*(?:no|num|#)|ticket\s*(?:no|#)|trans(?:action)?\s*(?:no|#))[:\s]*([A-Za-z0-9\-_/]+)",
                re.IGNORECASE,
            ),
            1.0,
        ),
    ],
    "payment_method": [
        (
            re.compile(
                r"(?:payment\s*(?:method|type)|paid\s*by)[:\s]*([A-Za-z\s]+)", re.IGNORECASE
            ),
            0.9,
        ),
        (
            re.compile(
                r"\b(CASH|VISA|MASTERCARD|AMEX|DEBIT\s*CARD|CREDIT\s*CARD)\b", re.IGNORECASE
            ),
            0.8,
        ),
    ],
    # Bank statement fields
    "account_holder": [
        (
            re.compile(r"(?:account\s*holder|customer\s*name|name)[:\s]*([^\n\r]+)", re.IGNORECASE),
            0.9,
        ),
    ],
    "bank_name": [
        (re.compile(r"(?:bank(?:\s*name)?|institution)[:\s]*([^\n\r]+)", re.IGNORECASE), 0.8),
    ],
    "account_number_masked": [
        (
            re.compile(
                r"(?:account\s*(?:number|num|no|#)|a/c\s*(?:no|num|number|#)?)[:\s]*([A-Za-z0-9\-_/\*X ]{4,30})",
                re.IGNORECASE,
            ),
            1.0,
        ),
        (re.compile(r"\b(?:A/C|ACC)[:\s]*([A-Za-z0-9\-_/\*X ]{4,30})", re.IGNORECASE), 0.9),
    ],
    "statement_period_start": [
        (
            re.compile(
                r"(?:period\s*from|statement\s*period[:\s]*from|from)[:\s]*([0-9A-Za-z\s,\.\-/]+?)(?:\s*(?:to|-|until))",
                re.IGNORECASE,
            ),
            0.9,
        ),
    ],
    "statement_period_end": [
        (
            re.compile(
                r"(?:to|period\s*to|ending)[:\s]*([0-9A-Za-z\s,\.\-/]+?)(?:\s*(?:statement|$|\n))",
                re.IGNORECASE,
            ),
            0.9,
        ),
    ],
    "opening_balance": [
        (
            re.compile(
                r"(?:opening\s*balance|starting\s*balance|previous\s*balance)[:\s]*([$€£₹\w\s]*[0-9]+[0-9,\.\s]*)",
                re.IGNORECASE,
            ),
            1.0,
        ),
    ],
    "closing_balance": [
        (
            re.compile(
                r"(?:closing\s*balance|ending\s*balance|new\s*balance|available\s*balance)[:\s]*([$€£₹\w\s]*[0-9]+[0-9,\.\s]*)",
                re.IGNORECASE,
            ),
            1.0,
        ),
    ],
}


class StructuredFieldExtractor:
    """Extracts structured fields from ExtractedDocumentText against an ExtractionSchema."""

    def __init__(self) -> None:
        self.extractor_version = "1.0.0"
        self.extraction_method = "deterministic_pattern_v1"

    def extract_fields(
        self,
        extracted_doc: ExtractedDocumentText,
        schema: ExtractionSchema,
        options: dict[str, Any] | None = None,
    ) -> DocumentExtractionResult:
        """Execute schema field extraction across document pages and return structured result."""
        t0 = time.perf_counter()

        extracted_fields: dict[str, ExtractedFieldValue] = {}
        target_page = options.get("page_number") if options else None

        for field_def in schema.fields:
            field_val = self._extract_field(extracted_doc, field_def, target_page=target_page)
            if field_val is not None:
                extracted_fields[field_def.field_key] = field_val

        # Cross-field validation
        validation_warnings: list[str] = []
        if schema.document_class == DocumentClass.INVOICE:
            curr_code = (
                str(extracted_fields["currency"].normalized_value)
                if "currency" in extracted_fields and extracted_fields["currency"].normalized_value
                else None
            )
            arith_warnings = validate_invoice_arithmetic(extracted_fields, currency=curr_code)
            validation_warnings.extend(arith_warnings)

        # Check required fields
        for field_def in schema.fields:
            if field_def.is_required and field_def.field_key not in extracted_fields:
                missing_msg = f"Missing required field: '{field_def.label}' ({field_def.field_key})"
                validation_warnings.append(missing_msg)

        elapsed_ms = (time.perf_counter() - t0) * 1000.0

        return DocumentExtractionResult(
            document_id=extracted_doc.document_id,
            processing_run_id=extracted_doc.processing_run_id,
            document_class=schema.document_class,
            schema_id=schema.schema_id,
            schema_version=schema.version,
            fields=extracted_fields,
            validation_summary={
                "total_fields_extracted": len(extracted_fields),
                "required_fields_total": sum(1 for f in schema.fields if f.is_required),
                "warnings": validation_warnings,
                "is_valid": len(validation_warnings) == 0,
            },
            execution_duration_ms=round(elapsed_ms, 2),
        )

    def _extract_field(
        self,
        extracted_doc: ExtractedDocumentText,
        field_def: FieldDefinition,
        target_page: int | None = None,
    ) -> ExtractedFieldValue | None:
        """Scan document pages for candidate values for a specific field definition."""
        patterns = FIELD_PATTERNS.get(field_def.field_key, [])
        if not patterns:
            # Fallback label matching
            label_regex = re.compile(
                rf"{re.escape(field_def.label)}[:\s]*([^\n\r]+)", re.IGNORECASE
            )
            patterns = [(label_regex, 0.7)]

        candidates: list[CandidateValue] = []
        pages_to_scan = (
            [p for p in extracted_doc.pages if p.page_number == target_page]
            if target_page is not None
            else extracted_doc.pages
        )

        for page in pages_to_scan:
            text_to_scan = page.raw_text

            for regex, score_weight in patterns:
                for match in regex.finditer(text_to_scan):
                    raw_val = match.group(1).strip()
                    if not raw_val:
                        continue

                    # Validate and normalize using full document context
                    norm_val, warnings = self._normalize_value(
                        raw_val, field_def.data_type, document_context=extracted_doc.full_raw_text
                    )
                    if norm_val is None and field_def.data_type != FieldDataType.STRING:
                        continue

                    # Find source bounding boxes and tokens on this page
                    boxes, token_ids = self._locate_tokens_and_boxes(page, raw_val)

                    # Privacy invariant: Sensitive masked strings must NEVER be stored unmasked in candidates
                    safe_raw = (
                        mask_sensitive_account_number(raw_val)
                        if field_def.data_type == FieldDataType.MASKED_STRING
                        else raw_val
                    )

                    cand = CandidateValue(
                        raw_text=safe_raw,
                        normalized_value=norm_val if norm_val is not None else safe_raw,
                        score=score_weight,
                        page_number=page.page_number,
                        bounding_box=boxes[0] if boxes else None,
                        token_ids=token_ids,
                        data_type=field_def.data_type,
                    )
                    candidates.append(cand)

        # Fallback heuristic for supplier / merchant name from first lines
        if not candidates and field_def.field_key in {
            "supplier_name",
            "merchant_name",
            "bank_name",
        }:
            header_cand = self._extract_header_entity(extracted_doc, field_def)
            if header_cand:
                candidates.append(header_cand)

        if not candidates:
            return None

        # Sort candidates descending by score
        candidates.sort(key=lambda c: c.score, reverse=True)
        primary = candidates[0]
        alternatives = candidates[1:]

        # Validate primary
        norm_val, val_warnings = self._normalize_value(
            primary.raw_text, field_def.data_type, document_context=extracted_doc.full_raw_text
        )

        val_status = (
            FieldValidationStatus.VALID if not val_warnings else FieldValidationStatus.WARNING
        )

        boxes = [primary.bounding_box] if primary.bounding_box else []

        # Ensure primary and alternatives have strictly masked raw_text and normalized_value for MASKED_STRING
        safe_primary_raw = (
            mask_sensitive_account_number(primary.raw_text)
            if field_def.data_type == FieldDataType.MASKED_STRING
            else primary.raw_text
        )
        safe_primary_norm = (
            mask_sensitive_account_number(str(norm_val))
            if field_def.data_type == FieldDataType.MASKED_STRING
            else (norm_val if norm_val is not None else primary.raw_text)
        )

        return ExtractedFieldValue(
            field_key=field_def.field_key,
            label=field_def.label,
            normalized_value=safe_primary_norm,
            raw_text=safe_primary_raw,
            data_type=field_def.data_type,
            extraction_method=self.extraction_method,
            score=primary.score,
            confidence=None,  # Explicitly None for deterministic extraction
            confidence_explanation="Deterministic pattern extraction has no calibrated probabilistic confidence.",
            source_document_id=extracted_doc.document_id,
            source_page_number=primary.page_number,
            source_bounding_boxes=boxes,
            source_token_ids=primary.token_ids,
            validation_status=val_status,
            warnings=val_warnings,
            alternative_candidates=alternatives,
        )

    def _normalize_value(
        self,
        raw_text: str,
        data_type: FieldDataType,
        document_context: str = "",
    ) -> tuple[Any, list[str]]:
        """Normalize value according to its data type with document context disambiguation."""
        if data_type == FieldDataType.DATE:
            norm_date, warnings, _ = normalize_and_validate_date(
                raw_text, document_context=document_context
            )
            return norm_date, warnings
        elif data_type in (FieldDataType.DECIMAL, FieldDataType.NUMBER):
            return normalize_and_validate_decimal(raw_text)
        elif data_type == FieldDataType.CURRENCY:
            return normalize_and_validate_currency(raw_text, document_context=document_context)
        elif data_type == FieldDataType.MASKED_STRING:
            return mask_sensitive_account_number(raw_text), []
        else:
            # String / other: clean whitespace
            clean = " ".join(raw_text.strip().split())
            return clean, []

    def _locate_tokens_and_boxes(
        self, page: ExtractedPage, match_text: str
    ) -> tuple[list[BoundingBox], list[str]]:
        """Identify supporting OCR tokens and bounding box coordinates for a matched text fragment."""
        matched_tokens: list[TextToken] = []
        tokens_text_lower = match_text.lower().split()

        if not tokens_text_lower:
            return [], []

        for token in page.tokens:
            if not token.raw_text:
                continue
            token_lower = token.raw_text.lower().strip(",.:;-#")
            if token_lower in tokens_text_lower:
                matched_tokens.append(token)

        if not matched_tokens:
            return [], []

        token_ids = [t.id for t in matched_tokens]
        boxes_with_coords = [t.bounding_box for t in matched_tokens if t.bounding_box]

        if not boxes_with_coords:
            # Do NOT fabricate bounding boxes when coordinates are unavailable
            return [], token_ids

        # Enclosing bounding box
        min_x = min(b.x for b in boxes_with_coords)
        min_y = min(b.y for b in boxes_with_coords)
        max_r = max(b.x + b.width for b in boxes_with_coords)
        max_b = max(b.y + b.height for b in boxes_with_coords)

        enclosing = BoundingBox(
            x=round(min_x, 4),
            y=round(min_y, 4),
            width=round(max_r - min_x, 4),
            height=round(max_b - min_y, 4),
            coordinate_system=CoordinateSystem.NORMALIZED_0_1,
        )

        return [enclosing], token_ids

    def _extract_header_entity(
        self, extracted_doc: ExtractedDocumentText, field_def: FieldDefinition
    ) -> CandidateValue | None:
        """Heuristic fallback for header company/merchant name from first page lines."""
        if not extracted_doc.pages:
            return None
        p1 = extracted_doc.pages[0]
        for line in p1.lines[:3]:
            text = line.raw_text.strip()
            # Skip lines that look like generic headers
            if len(text) > 3 and not re.search(
                r"\b(?:invoice|receipt|statement|tax|bill|page)\b", text, re.IGNORECASE
            ):
                boxes = [line.bounding_box] if line.bounding_box else []
                token_ids = [t.id for t in line.tokens]
                return CandidateValue(
                    raw_text=text,
                    normalized_value=text,
                    score=0.6,
                    page_number=1,
                    bounding_box=boxes[0] if boxes else None,
                    token_ids=token_ids,
                )
        return None
