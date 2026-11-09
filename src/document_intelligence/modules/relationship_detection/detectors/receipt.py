"""Receipt relationship detector for merchant issuance, invoice references, and payment recording."""

from __future__ import annotations

import re
from decimal import Decimal

from document_intelligence.domain.enums import (
    RelationshipDetectionMethod,
    RelationshipStatus,
    RelationshipType,
    StatusDeterminationMethod,
)
from document_intelligence.domain.identifiers import generate_id, utc_now
from document_intelligence.domain.models.relationship import (
    DetectedRelationship,
    RelationshipEvidence,
)
from document_intelligence.modules.relationship_detection.detectors.base import (
    BaseRelationshipDetector,
    DetectionContext,
)

INVOICE_REF_REGEX = re.compile(
    r"\b(?:invoice\s*(?:ref|no|num|number|#)?|inv\s*(?:no|#)?)\b[:\s]*([A-Za-z0-9\-_/]+)",
    re.IGNORECASE,
)
PAYMENT_AUTH_REGEX = re.compile(
    r"\b(?:auth(?:orization)?\s*(?:code|no|#)?|approval\s*code|trans(?:action)?\s*id)\b[:\s]*([A-Za-z0-9\-_/]+)",
    re.IGNORECASE,
)


class ReceiptRelationshipDetector(BaseRelationshipDetector):
    """Detects merchant issuance, payment records, and invoice cross-references from receipts."""

    @property
    def detector_name(self) -> str:
        return "receipt_relationship_detector"

    @property
    def detector_version(self) -> str:
        return "2.0.0"

    def detect(self, context: DetectionContext) -> list[DetectedRelationship]:
        relationships: list[DetectedRelationship] = []
        docs_by_id = {d.id: d for d in context.documents}

        for doc_id, fields in context.extracted_fields_by_doc.items():
            doc = docs_by_id.get(doc_id)
            if not doc:
                continue

            field_dict = {f.field_key: f for f in fields}
            doc_label = f"Document '{doc.original_filename}'"

            # Check if this document is a receipt or payment slip
            is_receipt = bool(
                field_dict.get("merchant_name")
                or field_dict.get("receipt_number")
                or field_dict.get("payment_method")
                or any(
                    term in doc.original_filename.lower()
                    for term in ("receipt", "slip", "ticket", "pos")
                )
                or doc.document_type == "RECEIPT"
            )
            if not is_receipt:
                continue

            # 1. Merchant organization -> ISSUED -> Receipt
            merchant_field = field_dict.get("merchant_name")
            if merchant_field and merchant_field.normalized_value:
                merchant_name = str(merchant_field.normalized_value).strip()
                merchant_id = f"ORG:{merchant_name.upper()}"

                evidence_nodes = (
                    [merchant_field.evidence_node_id] if merchant_field.evidence_node_id else []
                )
                rel = DetectedRelationship(
                    id=generate_id(),
                    case_id=context.case_id,
                    detection_run_id=context.detection_run_id,
                    relationship_type=RelationshipType.ISSUED,
                    ontology_version="2.0",
                    legacy_relationship_type=RelationshipType.ISSUED_BY.value,
                    source_id=merchant_id,
                    source_type="ORGANIZATION",
                    source_label=merchant_name,
                    target_id=doc.id,
                    target_type="RECEIPT",
                    target_label=doc_label,
                    direction_display=f"{merchant_name} --ISSUED--> {doc_label}",
                    status=RelationshipStatus.CONFIRMED,
                    status_determination_method=StatusDeterminationMethod.EVIDENTIARY_RULE,
                    score=0.95,
                    score_semantics="evidence_strength",
                    detection_method=RelationshipDetectionMethod.EXPLICIT_FIELD_REFERENCE,
                    detection_version=self.detector_version,
                    status_rationale=f"Merchant '{merchant_name}' explicitly named as issuer on receipt.",
                    evidence=RelationshipEvidence(
                        relationship_type=RelationshipType.ISSUED,
                        ontology_version="2.0",
                        legacy_relationship_type=RelationshipType.ISSUED_BY.value,
                        source_id=merchant_id,
                        target_id=doc.id,
                        source_case_id=context.case_id,
                        source_field_keys=["merchant_name"],
                        supporting_evidence_node_ids=evidence_nodes,
                        source_page_references=[merchant_field.source_page_number],
                        bounding_boxes=list(merchant_field.source_bounding_boxes),
                        detection_method=RelationshipDetectionMethod.EXPLICIT_FIELD_REFERENCE,
                        detection_version=self.detector_version,
                        matching_signals=[
                            f"Merchant '{merchant_name}' extracted from receipt header"
                        ],
                        contradicting_signals=[],
                        score=0.95,
                        score_semantics="evidence_strength",
                        status=RelationshipStatus.CONFIRMED,
                        status_determination_method=StatusDeterminationMethod.EVIDENTIARY_RULE,
                        status_rationale="Merchant extracted with field provenance.",
                    ),
                    created_at=utc_now(),
                    updated_at=utc_now(),
                )
                relationships.append(rel)

            # 2. Payment Record: Receipt -> RECORDS_PAYMENT -> Payment Reference
            raw_text = context.raw_document_texts.get(doc_id, "")
            auth_match = PAYMENT_AUTH_REGEX.search(raw_text)
            payment_method_field = field_dict.get("payment_method")

            if auth_match:
                auth_code = auth_match.group(1).strip()
                payment_ref_id = f"PAYMENT_AUTH:{auth_code.upper()}"
                payment_label = f"Payment Authorization {auth_code}"

                tender_signal = (
                    f"Tender: {payment_method_field.normalized_value}"
                    if payment_method_field
                    else "Payment slip"
                )
                pay_rel = DetectedRelationship(
                    id=generate_id(),
                    case_id=context.case_id,
                    detection_run_id=context.detection_run_id,
                    relationship_type=RelationshipType.RECORDS_PAYMENT,
                    ontology_version="2.0",
                    source_id=doc.id,
                    source_type="RECEIPT",
                    source_label=doc_label,
                    target_id=payment_ref_id,
                    target_type="PAYMENT_RECORD",
                    target_label=payment_label,
                    direction_display=f"{doc_label} --RECORDS_PAYMENT--> {payment_label}",
                    status=RelationshipStatus.CONFIRMED,
                    status_determination_method=StatusDeterminationMethod.EVIDENTIARY_RULE,
                    score=1.0,
                    score_semantics="evidence_strength",
                    detection_method=RelationshipDetectionMethod.PAYMENT_REFERENCE_RULE,
                    detection_version=self.detector_version,
                    status_rationale=f"Receipt contains explicit payment authorization code '{auth_code}'.",
                    evidence=RelationshipEvidence(
                        relationship_type=RelationshipType.RECORDS_PAYMENT,
                        ontology_version="2.0",
                        source_id=doc.id,
                        target_id=payment_ref_id,
                        source_case_id=context.case_id,
                        source_field_keys=["payment_authorization"],
                        supporting_evidence_node_ids=[],
                        source_page_references=[1],
                        bounding_boxes=[],
                        detection_method=RelationshipDetectionMethod.PAYMENT_REFERENCE_RULE,
                        detection_version=self.detector_version,
                        matching_signals=[
                            f"Payment authorization code '{auth_code}' with {tender_signal}"
                        ],
                        contradicting_signals=[],
                        score=1.0,
                        score_semantics="evidence_strength",
                        status=RelationshipStatus.CONFIRMED,
                        status_determination_method=StatusDeterminationMethod.EVIDENTIARY_RULE,
                        status_rationale="Explicit payment authorization record found.",
                    ),
                    created_at=utc_now(),
                    updated_at=utc_now(),
                )
                relationships.append(pay_rel)

            # 3. Cross-document reference to Invoice: Receipt -> REFERENCES_INVOICE -> Invoice
            inv_ref_match = INVOICE_REF_REGEX.search(raw_text)
            total_field = field_dict.get("total_amount")

            found_explicit_match = False
            if inv_ref_match:
                inv_num = inv_ref_match.group(1).strip()
                for other_doc_id, other_fields in context.extracted_fields_by_doc.items():
                    if other_doc_id == doc.id:
                        continue
                    other_doc = docs_by_id.get(other_doc_id)
                    if not other_doc:
                        continue

                    for of in other_fields:
                        if (
                            of.field_key == "invoice_number"
                            and str(of.normalized_value).upper() == inv_num.upper()
                        ):
                            found_explicit_match = True
                            other_label = f"Document '{other_doc.original_filename}'"
                            ref_rel = DetectedRelationship(
                                id=generate_id(),
                                case_id=context.case_id,
                                detection_run_id=context.detection_run_id,
                                relationship_type=RelationshipType.REFERENCES_INVOICE,
                                ontology_version="2.0",
                                source_id=doc.id,
                                source_type="RECEIPT",
                                source_label=doc_label,
                                target_id=other_doc.id,
                                target_type="INVOICE",
                                target_label=other_label,
                                direction_display=f"{doc_label} --REFERENCES_INVOICE--> {other_label}",
                                status=RelationshipStatus.CONFIRMED,
                                status_determination_method=StatusDeterminationMethod.EVIDENTIARY_RULE,
                                score=1.0,
                                score_semantics="evidence_strength",
                                detection_method=RelationshipDetectionMethod.EXPLICIT_FIELD_REFERENCE,
                                detection_version=self.detector_version,
                                status_rationale=f"Receipt explicitly cites invoice identifier '{inv_num}'.",
                                evidence=RelationshipEvidence(
                                    relationship_type=RelationshipType.REFERENCES_INVOICE,
                                    ontology_version="2.0",
                                    source_id=doc.id,
                                    target_id=other_doc.id,
                                    source_case_id=context.case_id,
                                    source_field_keys=["invoice_reference"],
                                    supporting_evidence_node_ids=[],
                                    source_page_references=[1],
                                    bounding_boxes=[],
                                    detection_method=RelationshipDetectionMethod.EXPLICIT_FIELD_REFERENCE,
                                    detection_version=self.detector_version,
                                    matching_signals=[
                                        f"Explicit citation of invoice '{inv_num}' on receipt"
                                    ],
                                    contradicting_signals=[],
                                    score=1.0,
                                    score_semantics="evidence_strength",
                                    status=RelationshipStatus.CONFIRMED,
                                    status_determination_method=StatusDeterminationMethod.EVIDENTIARY_RULE,
                                    status_rationale="Explicit invoice cross-reference identified.",
                                ),
                                created_at=utc_now(),
                                updated_at=utc_now(),
                            )
                            relationships.append(ref_rel)
                            break

            # 4. Fallback amount coincidence: Receipt --REFERENCES_INVOICE--> Invoice (UNRESOLVED)
            if not found_explicit_match and total_field and total_field.normalized_value:
                try:
                    receipt_total = Decimal(str(total_field.normalized_value))
                except Exception:
                    receipt_total = None

                if receipt_total is not None and receipt_total > Decimal("0"):
                    for other_doc_id, other_fields in context.extracted_fields_by_doc.items():
                        if other_doc_id == doc.id:
                            continue
                        other_doc = docs_by_id.get(other_doc_id)
                        if not other_doc:
                            continue

                        other_field_dict = {f.field_key: f for f in other_fields}
                        inv_total_field = other_field_dict.get("total_amount")
                        if inv_total_field and inv_total_field.normalized_value:
                            try:
                                inv_total = Decimal(str(inv_total_field.normalized_value))
                            except Exception:
                                inv_total = None

                            if inv_total is not None and receipt_total == inv_total:
                                other_label = f"Document '{other_doc.original_filename}'"
                                coin_rel = DetectedRelationship(
                                    id=generate_id(),
                                    case_id=context.case_id,
                                    detection_run_id=context.detection_run_id,
                                    relationship_type=RelationshipType.REFERENCES_INVOICE,
                                    ontology_version="2.0",
                                    source_id=doc.id,
                                    source_type="RECEIPT",
                                    source_label=doc_label,
                                    target_id=other_doc.id,
                                    target_type="INVOICE",
                                    target_label=other_label,
                                    direction_display=f"{doc_label} --REFERENCES_INVOICE--> {other_label}",
                                    status=RelationshipStatus.UNRESOLVED,
                                    status_determination_method=StatusDeterminationMethod.EVIDENTIARY_RULE,
                                    score=0.35,
                                    score_semantics="evidence_strength",
                                    detection_method=RelationshipDetectionMethod.AMOUNT_COINCIDENCE_HEURISTIC,
                                    detection_version=self.detector_version,
                                    status_rationale=(
                                        f"Receipt total ({receipt_total}) matches invoice total, but lacks explicit reference. "
                                        "Amount equality alone cannot confirm settlement."
                                    ),
                                    evidence=RelationshipEvidence(
                                        relationship_type=RelationshipType.REFERENCES_INVOICE,
                                        ontology_version="2.0",
                                        source_id=doc.id,
                                        target_id=other_doc.id,
                                        source_case_id=context.case_id,
                                        source_field_keys=["total_amount"],
                                        supporting_evidence_node_ids=[],
                                        source_page_references=[1],
                                        bounding_boxes=[],
                                        detection_method=RelationshipDetectionMethod.AMOUNT_COINCIDENCE_HEURISTIC,
                                        detection_version=self.detector_version,
                                        matching_signals=[
                                            f"Identical total amount: {receipt_total}"
                                        ],
                                        contradicting_signals=[
                                            "No explicit invoice citation or authorization linkage"
                                        ],
                                        score=0.35,
                                        score_semantics="evidence_strength",
                                        status=RelationshipStatus.UNRESOLVED,
                                        status_determination_method=StatusDeterminationMethod.EVIDENTIARY_RULE,
                                        status_rationale="Coincidental amount without explicit reference.",
                                    ),
                                    created_at=utc_now(),
                                    updated_at=utc_now(),
                                )
                                relationships.append(coin_rel)

        return relationships
