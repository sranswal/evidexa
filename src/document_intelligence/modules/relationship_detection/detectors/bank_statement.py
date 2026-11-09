"""Bank statement relationship detector handling account ownership, summary statements, and transaction settlement."""

from __future__ import annotations

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


class BankStatementRelationshipDetector(BaseRelationshipDetector):
    """Detects account holder ownership, issuing banks, and optional transaction settlements."""

    @property
    def detector_name(self) -> str:
        return "bank_statement_relationship_detector"

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

            # 1. Bank organization -> ISSUED -> Bank Statement
            bank_name_field = field_dict.get("bank_name")
            if bank_name_field and bank_name_field.normalized_value:
                bank_name = str(bank_name_field.normalized_value).strip()
                bank_id = f"ORG:{bank_name.upper()}"
                evidence_nodes = (
                    [bank_name_field.evidence_node_id] if bank_name_field.evidence_node_id else []
                )

                bank_rel = DetectedRelationship(
                    id=generate_id(),
                    case_id=context.case_id,
                    detection_run_id=context.detection_run_id,
                    relationship_type=RelationshipType.ISSUED,
                    ontology_version="2.0",
                    legacy_relationship_type=RelationshipType.ISSUED_BY.value,
                    source_id=bank_id,
                    source_type="ORGANIZATION",
                    source_label=bank_name,
                    target_id=doc.id,
                    target_type="BANK_STATEMENT",
                    target_label=doc_label,
                    direction_display=f"{bank_name} --ISSUED--> {doc_label}",
                    status=RelationshipStatus.CONFIRMED,
                    status_determination_method=StatusDeterminationMethod.EVIDENTIARY_RULE,
                    score=0.95,
                    score_semantics="evidence_strength",
                    detection_method=RelationshipDetectionMethod.EXPLICIT_FIELD_REFERENCE,
                    detection_version=self.detector_version,
                    status_rationale=f"Financial institution '{bank_name}' issued bank statement.",
                    evidence=RelationshipEvidence(
                        relationship_type=RelationshipType.ISSUED,
                        ontology_version="2.0",
                        legacy_relationship_type=RelationshipType.ISSUED_BY.value,
                        source_id=bank_id,
                        target_id=doc.id,
                        source_case_id=context.case_id,
                        source_field_keys=["bank_name"],
                        supporting_evidence_node_ids=evidence_nodes,
                        source_page_references=[bank_name_field.source_page_number],
                        bounding_boxes=list(bank_name_field.source_bounding_boxes),
                        detection_method=RelationshipDetectionMethod.EXPLICIT_FIELD_REFERENCE,
                        detection_version=self.detector_version,
                        matching_signals=[f"Issuing bank entity '{bank_name}' extracted"],
                        contradicting_signals=[],
                        score=0.95,
                        score_semantics="evidence_strength",
                        status=RelationshipStatus.CONFIRMED,
                        status_determination_method=StatusDeterminationMethod.EVIDENTIARY_RULE,
                        status_rationale="Issuing institution identified.",
                    ),
                    created_at=utc_now(),
                    updated_at=utc_now(),
                )
                relationships.append(bank_rel)

            # 2. Account -> HELD_BY -> Account Holder
            holder_field = field_dict.get("account_holder")
            acct_num_field = field_dict.get("account_number_masked")

            if holder_field and holder_field.normalized_value:
                holder_name = str(holder_field.normalized_value).strip()
                holder_id = f"ENTITY:{holder_name.upper()}"

                masked_num = (
                    str(acct_num_field.normalized_value).strip()
                    if acct_num_field and acct_num_field.normalized_value
                    else None
                )
                acct_id = f"ACCT:{masked_num}" if masked_num else f"{doc.id}:ACCOUNT"
                acct_label = (
                    f"Account {masked_num}" if masked_num else f"Account on {doc.original_filename}"
                )

                matching_signals = [f"Account holder name '{holder_name}'"]
                evidence_nodes = (
                    [holder_field.evidence_node_id] if holder_field.evidence_node_id else []
                )
                page_refs = [holder_field.source_page_number]
                bboxes = list(holder_field.source_bounding_boxes)

                if acct_num_field and acct_num_field.normalized_value:
                    matching_signals.append(f"Masked account: '{masked_num}'")
                    if acct_num_field.evidence_node_id:
                        evidence_nodes.append(acct_num_field.evidence_node_id)
                    if acct_num_field.source_page_number not in page_refs:
                        page_refs.append(acct_num_field.source_page_number)
                    bboxes.extend(acct_num_field.source_bounding_boxes)

                rel = DetectedRelationship(
                    id=generate_id(),
                    case_id=context.case_id,
                    detection_run_id=context.detection_run_id,
                    relationship_type=RelationshipType.HELD_BY,
                    ontology_version="2.0",
                    legacy_relationship_type=RelationshipType.ACCOUNT_HELD_BY.value,
                    source_id=acct_id,
                    source_type="ACCOUNT",
                    source_label=acct_label,
                    target_id=holder_id,
                    target_type="PERSON",
                    target_label=holder_name,
                    direction_display=f"{acct_label} --HELD_BY--> {holder_name}",
                    status=RelationshipStatus.CONFIRMED,
                    status_determination_method=StatusDeterminationMethod.EVIDENTIARY_RULE,
                    score=0.95,
                    score_semantics="evidence_strength",
                    detection_method=RelationshipDetectionMethod.EXPLICIT_FIELD_REFERENCE,
                    detection_version=self.detector_version,
                    status_rationale=f"Account '{acct_label}' explicitly held by '{holder_name}'.",
                    evidence=RelationshipEvidence(
                        relationship_type=RelationshipType.HELD_BY,
                        ontology_version="2.0",
                        legacy_relationship_type=RelationshipType.ACCOUNT_HELD_BY.value,
                        source_id=acct_id,
                        target_id=holder_id,
                        source_case_id=context.case_id,
                        source_field_keys=["account_holder"]
                        + (["account_number_masked"] if acct_num_field else []),
                        supporting_evidence_node_ids=evidence_nodes,
                        source_page_references=page_refs,
                        bounding_boxes=bboxes,
                        detection_method=RelationshipDetectionMethod.EXPLICIT_FIELD_REFERENCE,
                        detection_version=self.detector_version,
                        matching_signals=matching_signals,
                        contradicting_signals=[],
                        score=0.95,
                        score_semantics="evidence_strength",
                        status=RelationshipStatus.CONFIRMED,
                        status_determination_method=StatusDeterminationMethod.EVIDENTIARY_RULE,
                        status_rationale="Account ownership extracted with field provenance.",
                    ),
                    created_at=utc_now(),
                    updated_at=utc_now(),
                )
                relationships.append(rel)

        # 3. Transaction-Level Settlements (ONLY if synthetic_transactions or explicit transaction records exist)
        # Note: In bank_statement_v1, no transaction rows exist. We never fabricate them.
        for tx in context.synthetic_transactions:
            tx_id = str(tx.get("transaction_id", generate_id()))
            tx_desc = str(tx.get("description", ""))
            tx_amount = Decimal(str(tx.get("amount", "0")))
            tx_currency = str(tx.get("currency", "USD")).upper()
            statement_doc_id = str(tx.get("statement_document_id", ""))
            tx_label = f"Transaction {tx_id}"

            # Bank Statement -> CONTAINS_TRANSACTION -> Transaction
            if statement_doc_id and statement_doc_id in docs_by_id:
                statement_doc = docs_by_id[statement_doc_id]
                stmt_label = f"Document '{statement_doc.original_filename}'"
                contains_rel = DetectedRelationship(
                    id=generate_id(),
                    case_id=context.case_id,
                    detection_run_id=context.detection_run_id,
                    relationship_type=RelationshipType.CONTAINS_TRANSACTION,
                    ontology_version="2.0",
                    source_id=statement_doc.id,
                    source_type="BANK_STATEMENT",
                    source_label=stmt_label,
                    target_id=tx_id,
                    target_type="TRANSACTION",
                    target_label=tx_label,
                    direction_display=f"{stmt_label} --CONTAINS_TRANSACTION--> {tx_label}",
                    status=RelationshipStatus.CONFIRMED,
                    status_determination_method=StatusDeterminationMethod.EVIDENTIARY_RULE,
                    score=1.0,
                    score_semantics="evidence_strength",
                    detection_method=RelationshipDetectionMethod.EXPLICIT_FIELD_REFERENCE,
                    detection_version=self.detector_version,
                    status_rationale=f"Bank statement explicitly contains transaction item {tx_id}.",
                    evidence=RelationshipEvidence(
                        relationship_type=RelationshipType.CONTAINS_TRANSACTION,
                        ontology_version="2.0",
                        source_id=statement_doc.id,
                        target_id=tx_id,
                        source_case_id=context.case_id,
                        source_field_keys=["transaction_line"],
                        supporting_evidence_node_ids=[],
                        source_page_references=[1],
                        bounding_boxes=[],
                        detection_method=RelationshipDetectionMethod.EXPLICIT_FIELD_REFERENCE,
                        detection_version=self.detector_version,
                        matching_signals=[f"Transaction row '{tx_id}' found in statement"],
                        contradicting_signals=[],
                        score=1.0,
                        score_semantics="evidence_strength",
                        status=RelationshipStatus.CONFIRMED,
                        status_determination_method=StatusDeterminationMethod.EVIDENTIARY_RULE,
                        status_rationale="Explicit ledger transaction line.",
                    ),
                    created_at=utc_now(),
                    updated_at=utc_now(),
                )
                relationships.append(contains_rel)

            # Check Transaction -> MAY_SETTLE -> Invoice
            for inv_doc_id, inv_fields in context.extracted_fields_by_doc.items():
                inv_doc = docs_by_id.get(inv_doc_id)
                if not inv_doc:
                    continue
                inv_dict = {f.field_key: f for f in inv_fields}
                inv_total_field = inv_dict.get("total_amount")
                inv_num_field = inv_dict.get("invoice_number")
                inv_currency_field = inv_dict.get("currency")

                if not inv_total_field or not inv_total_field.normalized_value:
                    continue

                try:
                    inv_total = Decimal(str(inv_total_field.normalized_value))
                    inv_curr = (
                        str(inv_currency_field.normalized_value).upper()
                        if inv_currency_field and inv_currency_field.normalized_value
                        else "USD"
                    )
                    inv_num = (
                        str(inv_num_field.normalized_value).strip()
                        if inv_num_field and inv_num_field.normalized_value
                        else ""
                    )

                    inv_label = f"Document '{inv_doc.original_filename}'"

                    # 1. Conflicting currency check
                    if tx_amount == inv_total and tx_currency != inv_curr:
                        contradicted_rel = DetectedRelationship(
                            id=generate_id(),
                            case_id=context.case_id,
                            detection_run_id=context.detection_run_id,
                            relationship_type=RelationshipType.MAY_SETTLE,
                            ontology_version="2.0",
                            source_id=tx_id,
                            source_type="TRANSACTION",
                            source_label=tx_label,
                            target_id=inv_doc.id,
                            target_type="INVOICE",
                            target_label=inv_label,
                            direction_display=f"{tx_label} --MAY_SETTLE--> {inv_label}",
                            status=RelationshipStatus.CONTRADICTED,
                            status_determination_method=StatusDeterminationMethod.EVIDENTIARY_RULE,
                            score=0.0,
                            score_semantics="evidence_strength",
                            detection_method=RelationshipDetectionMethod.TRANSACTION_SETTLEMENT_RULE,
                            detection_version=self.detector_version,
                            status_rationale=f"Currency mismatch between transaction ({tx_currency}) and invoice ({inv_curr}).",
                            evidence=RelationshipEvidence(
                                relationship_type=RelationshipType.MAY_SETTLE,
                                ontology_version="2.0",
                                source_id=tx_id,
                                target_id=inv_doc.id,
                                source_case_id=context.case_id,
                                source_field_keys=["total_amount", "currency"],
                                supporting_evidence_node_ids=[],
                                source_page_references=[1],
                                bounding_boxes=[],
                                detection_method=RelationshipDetectionMethod.TRANSACTION_SETTLEMENT_RULE,
                                detection_version=self.detector_version,
                                matching_signals=[f"Equal numeric quantity: {tx_amount}"],
                                contradicting_signals=[
                                    f"Currency conflict: transaction {tx_currency} vs invoice {inv_curr}"
                                ],
                                score=0.0,
                                score_semantics="evidence_strength",
                                status=RelationshipStatus.CONTRADICTED,
                                status_determination_method=StatusDeterminationMethod.EVIDENTIARY_RULE,
                                status_rationale="Currency contradiction prevents settlement.",
                            ),
                            created_at=utc_now(),
                            updated_at=utc_now(),
                        )
                        relationships.append(contradicted_rel)

                    # 2. Matching amount and currency
                    elif tx_amount == inv_total and tx_currency == inv_curr:
                        has_explicit_ref = bool(inv_num and inv_num.lower() in tx_desc.lower())

                        if has_explicit_ref:
                            # Strong candidate with explicit reference
                            settle_rel = DetectedRelationship(
                                id=generate_id(),
                                case_id=context.case_id,
                                detection_run_id=context.detection_run_id,
                                relationship_type=RelationshipType.MAY_SETTLE,
                                ontology_version="2.0",
                                source_id=tx_id,
                                source_type="TRANSACTION",
                                source_label=tx_label,
                                target_id=inv_doc.id,
                                target_type="INVOICE",
                                target_label=inv_label,
                                direction_display=f"{tx_label} --MAY_SETTLE--> {inv_label}",
                                status=RelationshipStatus.CANDIDATE,
                                status_determination_method=StatusDeterminationMethod.EVIDENTIARY_RULE,
                                score=0.90,
                                score_semantics="evidence_strength",
                                detection_method=RelationshipDetectionMethod.TRANSACTION_SETTLEMENT_RULE,
                                detection_version=self.detector_version,
                                status_rationale=f"Transaction matches invoice amount ({tx_currency} {tx_amount}) and cites invoice number '{inv_num}'.",
                                evidence=RelationshipEvidence(
                                    relationship_type=RelationshipType.MAY_SETTLE,
                                    ontology_version="2.0",
                                    source_id=tx_id,
                                    target_id=inv_doc.id,
                                    source_case_id=context.case_id,
                                    source_field_keys=["total_amount", "invoice_number"],
                                    supporting_evidence_node_ids=[],
                                    source_page_references=[1],
                                    bounding_boxes=[],
                                    detection_method=RelationshipDetectionMethod.TRANSACTION_SETTLEMENT_RULE,
                                    detection_version=self.detector_version,
                                    matching_signals=[
                                        f"Matching amount: {tx_currency} {tx_amount}",
                                        f"Transaction description cites invoice '{inv_num}'",
                                    ],
                                    contradicting_signals=[],
                                    score=0.90,
                                    score_semantics="evidence_strength",
                                    status=RelationshipStatus.CANDIDATE,
                                    status_determination_method=StatusDeterminationMethod.EVIDENTIARY_RULE,
                                    status_rationale="Strong multi-signal settlement candidate.",
                                ),
                                created_at=utc_now(),
                                updated_at=utc_now(),
                            )
                            relationships.append(settle_rel)
                        else:
                            # Amount coincidence only: UNRESOLVED
                            unresolved_rel = DetectedRelationship(
                                id=generate_id(),
                                case_id=context.case_id,
                                detection_run_id=context.detection_run_id,
                                relationship_type=RelationshipType.MAY_SETTLE,
                                ontology_version="2.0",
                                source_id=tx_id,
                                source_type="TRANSACTION",
                                source_label=tx_label,
                                target_id=inv_doc.id,
                                target_type="INVOICE",
                                target_label=inv_label,
                                direction_display=f"{tx_label} --MAY_SETTLE--> {inv_label}",
                                status=RelationshipStatus.UNRESOLVED,
                                status_determination_method=StatusDeterminationMethod.EVIDENTIARY_RULE,
                                score=0.35,
                                score_semantics="amount_coincidence_heuristic",
                                detection_method=RelationshipDetectionMethod.AMOUNT_COINCIDENCE_HEURISTIC,
                                detection_version=self.detector_version,
                                status_rationale=(
                                    f"Transaction matches invoice gross amount ({tx_currency} {tx_amount}), "
                                    "but lacks explicit invoice reference. Amount equality alone cannot establish payment."
                                ),
                                evidence=RelationshipEvidence(
                                    relationship_type=RelationshipType.MAY_SETTLE,
                                    ontology_version="2.0",
                                    source_id=tx_id,
                                    target_id=inv_doc.id,
                                    source_case_id=context.case_id,
                                    source_field_keys=["total_amount"],
                                    supporting_evidence_node_ids=[],
                                    source_page_references=[1],
                                    bounding_boxes=[],
                                    detection_method=RelationshipDetectionMethod.AMOUNT_COINCIDENCE_HEURISTIC,
                                    detection_version=self.detector_version,
                                    matching_signals=[f"Equal amount: {tx_currency} {tx_amount}"],
                                    contradicting_signals=[
                                        "No explicit invoice citation or remittance reference in transaction record"
                                    ],
                                    score=0.35,
                                    score_semantics="amount_coincidence_heuristic",
                                    status=RelationshipStatus.UNRESOLVED,
                                    status_determination_method=StatusDeterminationMethod.EVIDENTIARY_RULE,
                                    status_rationale="Amount coincidence alone cannot establish payment settlement.",
                                ),
                                created_at=utc_now(),
                                updated_at=utc_now(),
                            )
                            relationships.append(unresolved_rel)
                except Exception:
                    pass

        return relationships
