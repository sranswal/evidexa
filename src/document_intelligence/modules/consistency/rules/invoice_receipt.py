"""Rule Family A: Invoice and Receipt cross-document consistency rules."""

from __future__ import annotations

from datetime import date

from document_intelligence.domain.enums import (
    ConsistencyDetectionMethod,
    ConsistencyOutcome,
    DocumentClass,
    FindingCategory,
    FindingSeverity,
)
from document_intelligence.domain.models.consistency import (
    ConsistencyComparison,
    ConsistencyFinding,
)
from document_intelligence.modules.consistency.context import ConsistencyContext
from document_intelligence.modules.consistency.financial import (
    compare_monetary_amounts,
)
from document_intelligence.modules.consistency.rules.base import BaseConsistencyRule


class InvoiceReceiptTotalConsistencyRule(BaseConsistencyRule):
    """Verifies monetary consistency between Invoice total and Receipt payment total."""

    @property
    def rule_id(self) -> str:
        return "invoice_receipt_total_consistency"

    @property
    def rule_version(self) -> str:
        return "1.0.0"

    @property
    def rule_name(self) -> str:
        return "Invoice and Receipt Total Amount Consistency"

    @property
    def description(self) -> str:
        return (
            "Compares invoice gross total amount against receipt payment total using strict Decimal arithmetic. "
            "Differences indicate analytical inconsistencies, not automated fraud."
        )

    @property
    def supported_document_types(self) -> list[DocumentClass]:
        return [DocumentClass.INVOICE, DocumentClass.RECEIPT]

    @property
    def required_field_keys(self) -> list[str]:
        return ["total_amount"]

    @property
    def category(self) -> FindingCategory:
        return FindingCategory.FINANCIAL_VALIDATION

    @property
    def default_severity(self) -> FindingSeverity:
        return FindingSeverity.HIGH

    @property
    def detection_method(self) -> ConsistencyDetectionMethod:
        return ConsistencyDetectionMethod.MONETARY_RECONCILIATION_CHECK

    def evaluate(self, context: ConsistencyContext) -> list[ConsistencyFinding]:
        findings: list[ConsistencyFinding] = []
        invoices = [d for d in context.documents if d.document_type == DocumentClass.INVOICE]
        receipts = [d for d in context.documents if d.document_type == DocumentClass.RECEIPT]

        for inv in invoices:
            inv_fields = context.get_field_dict(inv.id)
            inv_total_field = inv_fields.get("total_amount")
            inv_curr_field = inv_fields.get("currency")

            for rcpt in receipts:
                rcpt_fields = context.get_field_dict(rcpt.id)
                rcpt_total_field = rcpt_fields.get("total_amount")
                rcpt_curr_field = rcpt_fields.get("currency")

                comp_res = compare_monetary_amounts(
                    amount_a_val=inv_total_field.normalized_value or inv_total_field.raw_text
                    if inv_total_field
                    else None,
                    currency_a_val=inv_curr_field.normalized_value or inv_curr_field.raw_text
                    if inv_curr_field
                    else None,
                    amount_b_val=rcpt_total_field.normalized_value or rcpt_total_field.raw_text
                    if rcpt_total_field
                    else None,
                    currency_b_val=rcpt_curr_field.normalized_value or rcpt_curr_field.raw_text
                    if rcpt_curr_field
                    else None,
                    tolerance=context.monetary_tolerance,
                    label_a=f"Invoice '{inv.original_filename}'",
                    label_b=f"Receipt '{rcpt.original_filename}'",
                )

                loc_inv = self.create_location_from_field(inv.id, inv_total_field, "total_amount")
                loc_rcpt = self.create_location_from_field(
                    rcpt.id, rcpt_total_field, "total_amount"
                )

                supporting_ids: list[str] = []
                contradicting_ids: list[str] = []

                if inv_total_field and inv_total_field.evidence_node_id:
                    if comp_res.outcome == ConsistencyOutcome.CONSISTENT:
                        supporting_ids.append(inv_total_field.evidence_node_id)
                    elif comp_res.outcome == ConsistencyOutcome.INCONSISTENT:
                        contradicting_ids.append(inv_total_field.evidence_node_id)

                if rcpt_total_field and rcpt_total_field.evidence_node_id:
                    if comp_res.outcome == ConsistencyOutcome.CONSISTENT:
                        supporting_ids.append(rcpt_total_field.evidence_node_id)
                    elif comp_res.outcome == ConsistencyOutcome.INCONSISTENT:
                        contradicting_ids.append(rcpt_total_field.evidence_node_id)

                comparison = ConsistencyComparison(
                    field_key="total_amount",
                    source_doc_id=inv.id,
                    source_value=str(comp_res.amount_a) if comp_res.amount_a is not None else None,
                    target_doc_id=rcpt.id,
                    target_value=str(comp_res.amount_b) if comp_res.amount_b is not None else None,
                    comparison_type="DECIMAL_MONETARY",
                    outcome=comp_res.outcome,
                    difference=comp_res.difference_formatted,
                    explanation=comp_res.explanation,
                )

                title = f"Invoice vs Receipt Total: {comp_res.outcome.value}"
                finding = self.build_finding(
                    context=context,
                    outcome=comp_res.outcome,
                    title=title,
                    explanation=comp_res.explanation,
                    affected_document_ids=[inv.id, rcpt.id],
                    compared_fields=["total_amount", "currency"],
                    original_values={
                        f"{inv.id}:total_amount": inv_total_field.raw_text
                        if inv_total_field
                        else None,
                        f"{rcpt.id}:total_amount": rcpt_total_field.raw_text
                        if rcpt_total_field
                        else None,
                    },
                    normalized_values={
                        f"{inv.id}:total_amount": str(comp_res.amount_a)
                        if comp_res.amount_a is not None
                        else None,
                        f"{rcpt.id}:total_amount": str(comp_res.amount_b)
                        if comp_res.amount_b is not None
                        else None,
                    },
                    locations=[loc_inv, loc_rcpt],
                    comparisons=[comparison],
                    supporting_evidence_ids=supporting_ids,
                    contradicting_evidence_ids=contradicting_ids,
                    severity=self.default_severity
                    if comp_res.outcome == ConsistencyOutcome.INCONSISTENT
                    else FindingSeverity.INFO,
                    rule_parameters={"monetary_tolerance": str(context.monetary_tolerance)},
                    limitations=[
                        "Total amount matching does not prove settlement without verified payment ledger confirmation.",
                        "Discrepancies may reflect partial payments, surcharges, or discounts not captured in extracted fields.",
                    ],
                )
                findings.append(finding)

        return findings


class InvoiceReceiptReferenceConsistencyRule(BaseConsistencyRule):
    """Verifies explicit cross-reference consistency between Invoice number and Receipt invoice reference."""

    @property
    def rule_id(self) -> str:
        return "invoice_receipt_reference_consistency"

    @property
    def rule_version(self) -> str:
        return "1.0.0"

    @property
    def rule_name(self) -> str:
        return "Invoice and Receipt Reference Consistency"

    @property
    def description(self) -> str:
        return (
            "Compares invoice number with reference strings extracted or mentioned in receipt. "
            "Confirms matching references or reports contradictory identifiers."
        )

    @property
    def supported_document_types(self) -> list[DocumentClass]:
        return [DocumentClass.INVOICE, DocumentClass.RECEIPT]

    @property
    def required_field_keys(self) -> list[str]:
        return ["invoice_number"]

    def evaluate(self, context: ConsistencyContext) -> list[ConsistencyFinding]:
        findings: list[ConsistencyFinding] = []
        invoices = [d for d in context.documents if d.document_type == DocumentClass.INVOICE]
        receipts = [d for d in context.documents if d.document_type == DocumentClass.RECEIPT]

        for inv in invoices:
            inv_fields = context.get_field_dict(inv.id)
            inv_num_f = inv_fields.get("invoice_number")
            inv_num = inv_num_f.normalized_value or inv_num_f.raw_text if inv_num_f else None

            for rcpt in receipts:
                rcpt_fields = context.get_field_dict(rcpt.id)
                rcpt_ref_f = rcpt_fields.get("invoice_reference") or rcpt_fields.get(
                    "receipt_number"
                )
                rcpt_ref = (
                    rcpt_ref_f.normalized_value or rcpt_ref_f.raw_text if rcpt_ref_f else None
                )
                rcpt_text = context.raw_document_texts.get(rcpt.id, "")

                loc_inv = self.create_location_from_field(inv.id, inv_num_f, "invoice_number")
                loc_rcpt = self.create_location_from_field(rcpt.id, rcpt_ref_f, "invoice_reference")

                if not inv_num:
                    outcome = ConsistencyOutcome.INSUFFICIENT_EVIDENCE
                    explanation = (
                        f"Invoice '{inv.original_filename}' has no extracted invoice number."
                    )
                elif rcpt_ref and rcpt_ref.strip().upper() == inv_num.strip().upper():
                    outcome = ConsistencyOutcome.CONSISTENT
                    explanation = f"Receipt explicitly references invoice number '{inv_num}'."
                elif inv_num.strip().upper() in rcpt_text.upper():
                    outcome = ConsistencyOutcome.CONSISTENT
                    explanation = (
                        f"Invoice number '{inv_num}' is cited within receipt text content."
                    )
                elif rcpt_ref and rcpt_ref.strip().upper() != inv_num.strip().upper():
                    # Receipt explicitly mentions a DIFFERENT invoice reference
                    if "INV" in rcpt_ref.upper():
                        outcome = ConsistencyOutcome.INCONSISTENT
                        explanation = (
                            f"Reference conflict: Receipt references '{rcpt_ref}', "
                            f"which contradicts Invoice number '{inv_num}'."
                        )
                    else:
                        outcome = ConsistencyOutcome.INSUFFICIENT_EVIDENCE
                        explanation = (
                            f"Receipt has reference '{rcpt_ref}', but it does not establish explicit link "
                            f"to Invoice '{inv_num}'."
                        )
                else:
                    outcome = ConsistencyOutcome.INSUFFICIENT_EVIDENCE
                    explanation = f"Receipt '{rcpt.original_filename}' contains no reference to invoice '{inv_num}'."

                comparison = ConsistencyComparison(
                    field_key="invoice_number",
                    source_doc_id=inv.id,
                    source_value=inv_num,
                    target_doc_id=rcpt.id,
                    target_value=rcpt_ref,
                    comparison_type="STRING_EXACT",
                    outcome=outcome,
                    difference=f"Invoice: {inv_num} vs Receipt: {rcpt_ref}"
                    if outcome == ConsistencyOutcome.INCONSISTENT
                    else None,
                    explanation=explanation,
                )

                finding = self.build_finding(
                    context=context,
                    outcome=outcome,
                    title=f"Invoice and Receipt Reference: {outcome.value}",
                    explanation=explanation,
                    affected_document_ids=[inv.id, rcpt.id],
                    compared_fields=["invoice_number", "invoice_reference"],
                    original_values={
                        f"{inv.id}:invoice_number": inv_num,
                        f"{rcpt.id}:reference": rcpt_ref,
                    },
                    normalized_values={
                        f"{inv.id}:invoice_number": inv_num,
                        f"{rcpt.id}:reference": rcpt_ref,
                    },
                    locations=[loc_inv, loc_rcpt],
                    comparisons=[comparison],
                    severity=FindingSeverity.MEDIUM
                    if outcome == ConsistencyOutcome.INCONSISTENT
                    else FindingSeverity.INFO,
                )
                findings.append(finding)

        return findings


class InvoiceReceiptMerchantConsistencyRule(BaseConsistencyRule):
    """Verifies identity consistency between Invoice supplier and Receipt merchant."""

    @property
    def rule_id(self) -> str:
        return "invoice_receipt_merchant_consistency"

    @property
    def rule_version(self) -> str:
        return "1.0.0"

    @property
    def rule_name(self) -> str:
        return "Invoice Supplier and Receipt Merchant Consistency"

    @property
    def description(self) -> str:
        return (
            "Compares invoice supplier name against receipt merchant trading name. "
            "Evaluates exact strings, normalization, and resolved cross-document entities."
        )

    @property
    def supported_document_types(self) -> list[DocumentClass]:
        return [DocumentClass.INVOICE, DocumentClass.RECEIPT]

    def evaluate(self, context: ConsistencyContext) -> list[ConsistencyFinding]:
        findings: list[ConsistencyFinding] = []
        invoices = [d for d in context.documents if d.document_type == DocumentClass.INVOICE]
        receipts = [d for d in context.documents if d.document_type == DocumentClass.RECEIPT]

        for inv in invoices:
            inv_supp_f = context.get_field(inv.id, "supplier_name")
            supp_name = inv_supp_f.normalized_value or inv_supp_f.raw_text if inv_supp_f else None

            for rcpt in receipts:
                rcpt_merch_f = context.get_field(rcpt.id, "merchant_name")
                merch_name = (
                    rcpt_merch_f.normalized_value or rcpt_merch_f.raw_text if rcpt_merch_f else None
                )

                loc_inv = self.create_location_from_field(inv.id, inv_supp_f, "supplier_name")
                loc_rcpt = self.create_location_from_field(rcpt.id, rcpt_merch_f, "merchant_name")

                if not supp_name or not merch_name:
                    outcome = ConsistencyOutcome.INSUFFICIENT_EVIDENCE
                    explanation = (
                        "Cannot verify party identity: "
                        + ("Invoice supplier unstated. " if not supp_name else "")
                        + ("Receipt merchant unstated." if not merch_name else "")
                    )
                else:
                    norm_supp = "".join(ch.lower() for ch in supp_name if ch.isalnum())
                    norm_merch = "".join(ch.lower() for ch in merch_name if ch.isalnum())

                    if (
                        norm_supp == norm_merch
                        or norm_supp in norm_merch
                        or norm_merch in norm_supp
                    ):
                        outcome = ConsistencyOutcome.CONSISTENT
                        explanation = f"Supplier '{supp_name}' matches merchant '{merch_name}'."
                    else:
                        outcome = ConsistencyOutcome.POTENTIAL_ANOMALY
                        explanation = (
                            f"Supplier/merchant name variation: Invoice specifies '{supp_name}' "
                            f"whereas Receipt specifies '{merch_name}'. May indicate third-party billing, "
                            "franchise trading name, or unrelated payment."
                        )

                comparison = ConsistencyComparison(
                    field_key="supplier_name",
                    source_doc_id=inv.id,
                    source_value=supp_name,
                    target_doc_id=rcpt.id,
                    target_value=merch_name,
                    comparison_type="NORMALIZED_IDENTITY",
                    outcome=outcome,
                    difference=f"Supplier: {supp_name} vs Merchant: {merch_name}"
                    if outcome != ConsistencyOutcome.CONSISTENT
                    else None,
                    explanation=explanation,
                )

                finding = self.build_finding(
                    context=context,
                    outcome=outcome,
                    title=f"Supplier / Merchant Identity: {outcome.value}",
                    explanation=explanation,
                    affected_document_ids=[inv.id, rcpt.id],
                    compared_fields=["supplier_name", "merchant_name"],
                    original_values={
                        f"{inv.id}:supplier": supp_name,
                        f"{rcpt.id}:merchant": merch_name,
                    },
                    normalized_values={
                        f"{inv.id}:supplier": supp_name,
                        f"{rcpt.id}:merchant": merch_name,
                    },
                    locations=[loc_inv, loc_rcpt],
                    comparisons=[comparison],
                    severity=FindingSeverity.LOW
                    if outcome == ConsistencyOutcome.POTENTIAL_ANOMALY
                    else FindingSeverity.INFO,
                )
                findings.append(finding)

        return findings


class InvoiceReceiptTimingConsistencyRule(BaseConsistencyRule):
    """Verifies chronological order between Invoice issue date and Receipt transaction date."""

    @property
    def rule_id(self) -> str:
        return "invoice_receipt_timing_consistency"

    @property
    def rule_version(self) -> str:
        return "1.0.0"

    @property
    def rule_name(self) -> str:
        return "Invoice and Receipt Chronological Timing Consistency"

    @property
    def description(self) -> str:
        return (
            "Checks that payment receipt date logically follows or coincides with invoice issue date. "
            "A receipt dated significantly prior to invoice issuance is flagged as a potential anomaly."
        )

    @property
    def supported_document_types(self) -> list[DocumentClass]:
        return [DocumentClass.INVOICE, DocumentClass.RECEIPT]

    @property
    def category(self) -> FindingCategory:
        return FindingCategory.DOCUMENT_INCONSISTENCY

    @property
    def detection_method(self) -> ConsistencyDetectionMethod:
        return ConsistencyDetectionMethod.TEMPORAL_SEQUENCE_CHECK

    def evaluate(self, context: ConsistencyContext) -> list[ConsistencyFinding]:
        findings: list[ConsistencyFinding] = []
        invoices = [d for d in context.documents if d.document_type == DocumentClass.INVOICE]
        receipts = [d for d in context.documents if d.document_type == DocumentClass.RECEIPT]

        for inv in invoices:
            inv_date_f = context.get_field(inv.id, "invoice_date")
            inv_date_str = (
                inv_date_f.normalized_value or inv_date_f.raw_text if inv_date_f else None
            )

            for rcpt in receipts:
                rcpt_date_f = context.get_field(rcpt.id, "transaction_date")
                rcpt_date_str = (
                    rcpt_date_f.normalized_value or rcpt_date_f.raw_text if rcpt_date_f else None
                )

                loc_inv = self.create_location_from_field(inv.id, inv_date_f, "invoice_date")
                loc_rcpt = self.create_location_from_field(rcpt.id, rcpt_date_f, "transaction_date")

                d_inv: date | None = None
                d_rcpt: date | None = None

                if inv_date_str:
                    try:
                        d_inv = date.fromisoformat(inv_date_str[:10])
                    except (ValueError, TypeError):
                        pass

                if rcpt_date_str:
                    try:
                        d_rcpt = date.fromisoformat(rcpt_date_str[:10])
                    except (ValueError, TypeError):
                        pass

                if not d_inv or not d_rcpt:
                    outcome = ConsistencyOutcome.INSUFFICIENT_EVIDENCE
                    explanation = (
                        "Cannot verify date sequence: one or both dates missing or unparseable."
                    )
                else:
                    delta_days = (d_rcpt - d_inv).days
                    if delta_days >= 0:
                        outcome = ConsistencyOutcome.CONSISTENT
                        explanation = (
                            f"Chronologically consistent: Receipt payment date ({d_rcpt}) "
                            f"is {delta_days} day(s) after invoice date ({d_inv})."
                        )
                    else:
                        # Receipt is before invoice
                        outcome = ConsistencyOutcome.POTENTIAL_ANOMALY
                        explanation = (
                            f"Temporal anomaly: Receipt date ({d_rcpt}) is {abs(delta_days)} day(s) "
                            f"prior to invoice issue date ({d_inv}). While advance deposits occur, "
                            "pre-invoice settlement requires verification."
                        )

                comparison = ConsistencyComparison(
                    field_key="date_sequence",
                    source_doc_id=inv.id,
                    source_value=str(d_inv) if d_inv else inv_date_str,
                    target_doc_id=rcpt.id,
                    target_value=str(d_rcpt) if d_rcpt else rcpt_date_str,
                    comparison_type="DATE_SEQUENCE",
                    outcome=outcome,
                    difference=f"{d_rcpt} precedes {d_inv}"
                    if outcome == ConsistencyOutcome.POTENTIAL_ANOMALY
                    else None,
                    explanation=explanation,
                )

                finding = self.build_finding(
                    context=context,
                    outcome=outcome,
                    title=f"Invoice and Receipt Date Order: {outcome.value}",
                    explanation=explanation,
                    affected_document_ids=[inv.id, rcpt.id],
                    compared_fields=["invoice_date", "transaction_date"],
                    original_values={
                        f"{inv.id}:date": inv_date_str,
                        f"{rcpt.id}:date": rcpt_date_str,
                    },
                    normalized_values={
                        f"{inv.id}:date": str(d_inv) if d_inv else None,
                        f"{rcpt.id}:date": str(d_rcpt) if d_rcpt else None,
                    },
                    locations=[loc_inv, loc_rcpt],
                    comparisons=[comparison],
                    severity=FindingSeverity.LOW
                    if outcome == ConsistencyOutcome.POTENTIAL_ANOMALY
                    else FindingSeverity.INFO,
                )
                findings.append(finding)

        return findings
