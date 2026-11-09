"""Invoice relationship detector for commercial issuance, buyer billing, and purchase order references."""

from __future__ import annotations

import re

from document_intelligence.domain.enums import (
    EntityMatchClassification,
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

PO_REGEX = re.compile(
    r"\b(?:P\.?O\.?\s*(?:#|no|num|number)?|purchase\s*order\s*(?:#|no|num|number)?)[:\s]*([A-Za-z0-9\-_/]+)",
    re.IGNORECASE,
)
AMENDMENT_REGEX = re.compile(
    r"\b(?:amends|amendment\s*to|revises|revision\s*of|supersedes)\b[:\s]*([A-Za-z0-9\-_/]+)",
    re.IGNORECASE,
)
SUPPLY_CONTRACT_REGEX = re.compile(
    r"\b(?:supply\s+agreement|supplier\s+agreement|master\s+(?:supply|services)\s+agreement|exclusive\s+supplier\s+of|contract\s+for\s+the\s+supply\s+of)\b",
    re.IGNORECASE,
)


class InvoiceRelationshipDetector(BaseRelationshipDetector):
    """Detects commercial issuance, buyer billing, single-invoice invoicing, and reference relationships."""

    @property
    def detector_name(self) -> str:
        return "invoice_relationship_detector"

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
            raw_text = context.raw_document_texts.get(doc_id, "")

            # 1. Supplier organization -> ISSUED -> Invoice
            supplier_field = field_dict.get("supplier_name")
            tax_field = field_dict.get("supplier_tax_id")
            supplier_name: str | None = None
            supplier_id: str | None = None

            if supplier_field and supplier_field.normalized_value:
                supplier_name = str(supplier_field.normalized_value).strip()
                supplier_id = f"ORG:{supplier_name.upper()}"

                matching_signals = [f"Explicit supplier_name field: '{supplier_name}'"]
                contradicting_signals: list[str] = []
                evidence_node_ids = []
                if supplier_field.evidence_node_id:
                    evidence_node_ids.append(supplier_field.evidence_node_id)
                page_refs = [supplier_field.source_page_number]
                bboxes = list(supplier_field.source_bounding_boxes)

                status = RelationshipStatus.CONFIRMED
                score = 0.95
                score_semantics = "evidence_strength"

                if tax_field and tax_field.normalized_value:
                    tax_id = str(tax_field.normalized_value).strip()
                    matching_signals.append(f"Supplier tax ID: '{tax_id}'")
                    score = 1.0
                    if tax_field.evidence_node_id:
                        evidence_node_ids.append(tax_field.evidence_node_id)
                    if tax_field.source_page_number not in page_refs:
                        page_refs.append(tax_field.source_page_number)
                    bboxes.extend(tax_field.source_bounding_boxes)

                # Check entity resolution contradiction
                for match in context.candidate_matches:
                    if match.match_classification == EntityMatchClassification.CONFLICTING_IDENTITY:
                        if (
                            supplier_name.lower() in match.target_value_display.lower()
                            or supplier_name.lower() in match.candidate_value_display.lower()
                        ):
                            contradicting_signals.append(
                                f"Conflicting tax identifier in entity resolution match {match.id}"
                            )
                            status = RelationshipStatus.CONTRADICTED
                            score = 0.0

                rel = DetectedRelationship(
                    id=generate_id(),
                    case_id=context.case_id,
                    detection_run_id=context.detection_run_id,
                    relationship_type=RelationshipType.ISSUED,
                    ontology_version="2.0",
                    legacy_relationship_type=RelationshipType.ISSUED_BY.value,
                    source_id=supplier_id,
                    source_type="ORGANIZATION",
                    source_label=supplier_name,
                    target_id=doc.id,
                    target_type="INVOICE",
                    target_label=doc_label,
                    direction_display=f"{supplier_name} --ISSUED--> {doc_label}",
                    status=status,
                    status_determination_method=StatusDeterminationMethod.EVIDENTIARY_RULE,
                    score=score,
                    score_semantics=score_semantics,
                    detection_method=RelationshipDetectionMethod.EXPLICIT_FIELD_REFERENCE,
                    detection_version=self.detector_version,
                    status_rationale=(
                        f"Supplier '{supplier_name}' explicitly identified as issuer on invoice."
                        if status == RelationshipStatus.CONFIRMED
                        else f"Supplier '{supplier_name}' contradicted by conflicting tax identifier."
                    ),
                    evidence=RelationshipEvidence(
                        relationship_type=RelationshipType.ISSUED,
                        ontology_version="2.0",
                        legacy_relationship_type=RelationshipType.ISSUED_BY.value,
                        source_id=supplier_id,
                        target_id=doc.id,
                        source_case_id=context.case_id,
                        source_field_keys=["supplier_name"]
                        + (["supplier_tax_id"] if tax_field else []),
                        supporting_evidence_node_ids=evidence_node_ids,
                        source_page_references=page_refs,
                        bounding_boxes=bboxes,
                        detection_method=RelationshipDetectionMethod.EXPLICIT_FIELD_REFERENCE,
                        detection_version=self.detector_version,
                        matching_signals=matching_signals,
                        contradicting_signals=contradicting_signals,
                        score=score,
                        score_semantics=score_semantics,
                        status=status,
                        status_determination_method=StatusDeterminationMethod.EVIDENTIARY_RULE,
                        status_rationale="Supplier extracted with field provenance.",
                    ),
                    created_at=utc_now(),
                    updated_at=utc_now(),
                )
                relationships.append(rel)

            # 2. Invoice -> BILLED_TO -> Buyer organization
            buyer_field = field_dict.get("buyer_name")
            buyer_tax_field = field_dict.get("buyer_tax_id")
            buyer_name: str | None = None
            buyer_id: str | None = None

            if buyer_field and buyer_field.normalized_value:
                buyer_name = str(buyer_field.normalized_value).strip()
                buyer_id = f"ORG:{buyer_name.upper()}"

                matching_signals = [f"Explicit buyer_name field: '{buyer_name}'"]
                evidence_node_ids = []
                if buyer_field.evidence_node_id:
                    evidence_node_ids.append(buyer_field.evidence_node_id)
                page_refs = [buyer_field.source_page_number]
                bboxes = list(buyer_field.source_bounding_boxes)
                score = 0.90
                if buyer_tax_field and buyer_tax_field.normalized_value:
                    matching_signals.append(f"Buyer tax ID: '{buyer_tax_field.normalized_value}'")
                    score = 0.98
                    if buyer_tax_field.evidence_node_id:
                        evidence_node_ids.append(buyer_tax_field.evidence_node_id)

                rel = DetectedRelationship(
                    id=generate_id(),
                    case_id=context.case_id,
                    detection_run_id=context.detection_run_id,
                    relationship_type=RelationshipType.BILLED_TO,
                    ontology_version="2.0",
                    legacy_relationship_type=RelationshipType.ISSUED_TO.value,
                    source_id=doc.id,
                    source_type="INVOICE",
                    source_label=doc_label,
                    target_id=buyer_id,
                    target_type="ORGANIZATION",
                    target_label=buyer_name,
                    direction_display=f"{doc_label} --BILLED_TO--> {buyer_name}",
                    status=RelationshipStatus.CONFIRMED,
                    status_determination_method=StatusDeterminationMethod.EVIDENTIARY_RULE,
                    score=score,
                    score_semantics="evidence_strength",
                    detection_method=RelationshipDetectionMethod.EXPLICIT_FIELD_REFERENCE,
                    detection_version=self.detector_version,
                    status_rationale=f"Invoice explicitly bills recipient '{buyer_name}'.",
                    evidence=RelationshipEvidence(
                        relationship_type=RelationshipType.BILLED_TO,
                        ontology_version="2.0",
                        legacy_relationship_type=RelationshipType.ISSUED_TO.value,
                        source_id=doc.id,
                        target_id=buyer_id,
                        source_case_id=context.case_id,
                        source_field_keys=["buyer_name"],
                        supporting_evidence_node_ids=evidence_node_ids,
                        source_page_references=page_refs,
                        bounding_boxes=bboxes,
                        detection_method=RelationshipDetectionMethod.EXPLICIT_FIELD_REFERENCE,
                        detection_version=self.detector_version,
                        matching_signals=matching_signals,
                        contradicting_signals=[],
                        score=score,
                        score_semantics="evidence_strength",
                        status=RelationshipStatus.CONFIRMED,
                        status_determination_method=StatusDeterminationMethod.EVIDENTIARY_RULE,
                        status_rationale="Buyer extracted with field provenance.",
                    ),
                    created_at=utc_now(),
                    updated_at=utc_now(),
                )
                relationships.append(rel)

            # 3. Commercial billing event: Supplier -> INVOICED -> Buyer
            # Note: Single-invoice co-occurrence establishes INVOICED, NEVER ongoing SUPPLIES.
            if supplier_name and buyer_name and supplier_id and buyer_id:
                invoiced_rel = DetectedRelationship(
                    id=generate_id(),
                    case_id=context.case_id,
                    detection_run_id=context.detection_run_id,
                    relationship_type=RelationshipType.INVOICED,
                    ontology_version="2.0",
                    legacy_relationship_type="SUPPLIES",
                    source_id=supplier_id,
                    source_type="ORGANIZATION",
                    source_label=supplier_name,
                    target_id=buyer_id,
                    target_type="ORGANIZATION",
                    target_label=buyer_name,
                    direction_display=f"{supplier_name} --INVOICED--> {buyer_name}",
                    status=RelationshipStatus.CONFIRMED,
                    status_determination_method=StatusDeterminationMethod.EVIDENTIARY_RULE,
                    score=0.90,
                    score_semantics="evidence_strength",
                    detection_method=RelationshipDetectionMethod.INVOICE_BILLING_EVENT_RULE,
                    detection_version=self.detector_version,
                    status_rationale=(
                        f"Supplier '{supplier_name}' issued invoice {doc.original_filename} to buyer '{buyer_name}'. "
                        "This establishes a specific billing transaction, not an ongoing supply contract."
                    ),
                    evidence=RelationshipEvidence(
                        relationship_type=RelationshipType.INVOICED,
                        ontology_version="2.0",
                        legacy_relationship_type="SUPPLIES",
                        source_id=supplier_id,
                        target_id=buyer_id,
                        source_case_id=context.case_id,
                        source_field_keys=["supplier_name", "buyer_name"],
                        supporting_evidence_node_ids=evidence_node_ids,
                        source_page_references=page_refs,
                        bounding_boxes=[],
                        detection_method=RelationshipDetectionMethod.INVOICE_BILLING_EVENT_RULE,
                        detection_version=self.detector_version,
                        matching_signals=[
                            f"Invoice {doc.original_filename} links billing supplier '{supplier_name}' to recipient '{buyer_name}'"
                        ],
                        contradicting_signals=[],
                        score=0.90,
                        score_semantics="evidence_strength",
                        status=RelationshipStatus.CONFIRMED,
                        status_determination_method=StatusDeterminationMethod.EVIDENTIARY_RULE,
                        status_rationale="Single commercial invoice billing party relationship.",
                    ),
                    created_at=utc_now(),
                    updated_at=utc_now(),
                )
                relationships.append(invoiced_rel)

                # Check if explicit supply contract/arrangement evidence exists
                if SUPPLY_CONTRACT_REGEX.search(raw_text):
                    supplies_rel = DetectedRelationship(
                        id=generate_id(),
                        case_id=context.case_id,
                        detection_run_id=context.detection_run_id,
                        relationship_type=RelationshipType.SUPPLIES,
                        ontology_version="2.0",
                        source_id=supplier_id,
                        source_type="ORGANIZATION",
                        source_label=supplier_name,
                        target_id=buyer_id,
                        target_type="ORGANIZATION",
                        target_label=buyer_name,
                        direction_display=f"{supplier_name} --SUPPLIES--> {buyer_name}",
                        status=RelationshipStatus.CONFIRMED,
                        status_determination_method=StatusDeterminationMethod.EVIDENTIARY_RULE,
                        score=0.95,
                        score_semantics="evidence_strength",
                        detection_method=RelationshipDetectionMethod.CONTRACT_CLAUSE_RULE,
                        detection_version=self.detector_version,
                        status_rationale=(
                            f"Explicit contractual supply clause in {doc.original_filename} confirms ongoing supply arrangement "
                            f"between '{supplier_name}' and '{buyer_name}'."
                        ),
                        evidence=RelationshipEvidence(
                            relationship_type=RelationshipType.SUPPLIES,
                            ontology_version="2.0",
                            source_id=supplier_id,
                            target_id=buyer_id,
                            source_case_id=context.case_id,
                            source_field_keys=["contract_clause"],
                            supporting_evidence_node_ids=evidence_node_ids,
                            source_page_references=page_refs,
                            bounding_boxes=[],
                            detection_method=RelationshipDetectionMethod.CONTRACT_CLAUSE_RULE,
                            detection_version=self.detector_version,
                            matching_signals=[
                                f"Contract clause found establishing ongoing supply arrangement in {doc.original_filename}"
                            ],
                            contradicting_signals=[],
                            score=0.95,
                            score_semantics="evidence_strength",
                            status=RelationshipStatus.CONFIRMED,
                            status_determination_method=StatusDeterminationMethod.EVIDENTIARY_RULE,
                            status_rationale="Explicit contractual supply clause verified.",
                        ),
                        created_at=utc_now(),
                        updated_at=utc_now(),
                    )
                    relationships.append(supplies_rel)

            # 4. References Purchase Order: Invoice -> REFERENCES_PURCHASE_ORDER -> PO
            po_match = PO_REGEX.search(raw_text)
            if po_match:
                po_ref = po_match.group(1).strip()
                po_target_id = f"PO:{po_ref.upper()}"
                po_label = f"Purchase Order {po_ref}"

                for other_doc in context.documents:
                    if (
                        other_doc.id != doc.id
                        and po_ref.lower() in other_doc.original_filename.lower()
                    ):
                        po_target_id = other_doc.id
                        po_label = f"Document '{other_doc.original_filename}'"
                        break

                po_rel = DetectedRelationship(
                    id=generate_id(),
                    case_id=context.case_id,
                    detection_run_id=context.detection_run_id,
                    relationship_type=RelationshipType.REFERENCES_PURCHASE_ORDER,
                    ontology_version="2.0",
                    source_id=doc.id,
                    source_type="INVOICE",
                    source_label=doc_label,
                    target_id=po_target_id,
                    target_type="PURCHASE_ORDER",
                    target_label=po_label,
                    direction_display=f"{doc_label} --REFERENCES_PURCHASE_ORDER--> {po_label}",
                    status=RelationshipStatus.CONFIRMED,
                    status_determination_method=StatusDeterminationMethod.EVIDENTIARY_RULE,
                    score=1.0,
                    score_semantics="evidence_strength",
                    detection_method=RelationshipDetectionMethod.EXPLICIT_FIELD_REFERENCE,
                    detection_version=self.detector_version,
                    status_rationale=f"Invoice explicitly references purchase order '{po_ref}'.",
                    evidence=RelationshipEvidence(
                        relationship_type=RelationshipType.REFERENCES_PURCHASE_ORDER,
                        ontology_version="2.0",
                        source_id=doc.id,
                        target_id=po_target_id,
                        source_case_id=context.case_id,
                        source_field_keys=["po_reference"],
                        supporting_evidence_node_ids=[],
                        source_page_references=[1],
                        bounding_boxes=[],
                        detection_method=RelationshipDetectionMethod.EXPLICIT_FIELD_REFERENCE,
                        detection_version=self.detector_version,
                        matching_signals=[
                            f"Explicit purchase order citation '{po_ref}' in invoice text"
                        ],
                        contradicting_signals=[],
                        score=1.0,
                        score_semantics="evidence_strength",
                        status=RelationshipStatus.CONFIRMED,
                        status_determination_method=StatusDeterminationMethod.EVIDENTIARY_RULE,
                        status_rationale="Explicit textual reference found.",
                    ),
                    created_at=utc_now(),
                    updated_at=utc_now(),
                )
                relationships.append(po_rel)

            # 5. References Prior Invoice or Amendment: Invoice -> AMENDS_DOCUMENT -> Prior Invoice
            amend_match = AMENDMENT_REGEX.search(raw_text)
            if amend_match:
                prior_ref = amend_match.group(1).strip()
                prior_target_id = f"INV:{prior_ref.upper()}"
                prior_label = f"Invoice {prior_ref}"

                for other_doc_id, other_fields in context.extracted_fields_by_doc.items():
                    if other_doc_id == doc.id:
                        continue
                    for of in other_fields:
                        if (
                            of.field_key == "invoice_number"
                            and str(of.normalized_value).upper() == prior_ref.upper()
                        ):
                            matched_doc = docs_by_id.get(other_doc_id)
                            if matched_doc:
                                prior_target_id = matched_doc.id
                                prior_label = f"Document '{matched_doc.original_filename}'"
                            break

                amend_rel = DetectedRelationship(
                    id=generate_id(),
                    case_id=context.case_id,
                    detection_run_id=context.detection_run_id,
                    relationship_type=RelationshipType.AMENDS_DOCUMENT,
                    ontology_version="2.0",
                    source_id=doc.id,
                    source_type="INVOICE",
                    source_label=doc_label,
                    target_id=prior_target_id,
                    target_type="INVOICE",
                    target_label=prior_label,
                    direction_display=f"{doc_label} --AMENDS_DOCUMENT--> {prior_label}",
                    status=RelationshipStatus.CONFIRMED,
                    status_determination_method=StatusDeterminationMethod.EVIDENTIARY_RULE,
                    score=0.95,
                    score_semantics="evidence_strength",
                    detection_method=RelationshipDetectionMethod.EXPLICIT_DOCUMENT_REFERENCE,
                    detection_version=self.detector_version,
                    status_rationale=f"Document explicitly cites amendment/revision of prior document '{prior_ref}'.",
                    evidence=RelationshipEvidence(
                        relationship_type=RelationshipType.AMENDS_DOCUMENT,
                        ontology_version="2.0",
                        source_id=doc.id,
                        target_id=prior_target_id,
                        source_case_id=context.case_id,
                        source_field_keys=["amendment_reference"],
                        supporting_evidence_node_ids=[],
                        source_page_references=[1],
                        bounding_boxes=[],
                        detection_method=RelationshipDetectionMethod.EXPLICIT_DOCUMENT_REFERENCE,
                        detection_version=self.detector_version,
                        matching_signals=[f"Explicit amendment clause referencing '{prior_ref}'"],
                        contradicting_signals=[],
                        score=0.95,
                        score_semantics="evidence_strength",
                        status=RelationshipStatus.CONFIRMED,
                        status_determination_method=StatusDeterminationMethod.EVIDENTIARY_RULE,
                        status_rationale="Explicit amendment reference found in text.",
                    ),
                    created_at=utc_now(),
                    updated_at=utc_now(),
                )
                relationships.append(amend_rel)

        return relationships
