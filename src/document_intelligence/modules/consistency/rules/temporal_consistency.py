"""Rule Family F: Cross-Document Temporal Consistency rules."""

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
from document_intelligence.modules.consistency.rules.base import BaseConsistencyRule


class CrossDocumentTemporalSequenceRule(BaseConsistencyRule):
    """Verifies logical chronological order across commercial documents in the procurement and settlement lifecycle."""

    @property
    def rule_id(self) -> str:
        return "cross_document_temporal_sequence"

    @property
    def rule_version(self) -> str:
        return "1.0.0"

    @property
    def rule_name(self) -> str:
        return "Cross-Document Procurement and Payment Lifecycle Temporal Consistency"

    @property
    def description(self) -> str:
        return (
            "Checks that commercial documents follow legitimate chronological ordering: "
            "Purchase Orders must precede or coincide with Invoices; Invoices must precede or coincide with Payments. "
            "An invoice dated prior to its authorizing PO is flagged as an evidentiary anomaly."
        )

    @property
    def supported_document_types(self) -> list[DocumentClass]:
        return [
            DocumentClass.PURCHASE_ORDER,
            DocumentClass.INVOICE,
            DocumentClass.RECEIPT,
        ]

    @property
    def category(self) -> FindingCategory:
        return FindingCategory.DOCUMENT_INCONSISTENCY

    @property
    def default_severity(self) -> FindingSeverity:
        return FindingSeverity.MEDIUM

    @property
    def detection_method(self) -> ConsistencyDetectionMethod:
        return ConsistencyDetectionMethod.TEMPORAL_SEQUENCE_CHECK

    def evaluate(self, context: ConsistencyContext) -> list[ConsistencyFinding]:
        findings: list[ConsistencyFinding] = []
        pos = [d for d in context.documents if d.document_type == DocumentClass.PURCHASE_ORDER]
        invoices = [d for d in context.documents if d.document_type == DocumentClass.INVOICE]

        # 1. PO Date vs Invoice Date
        for po in pos:
            po_d_f = context.get_field(po.id, "po_date")
            po_d_str = po_d_f.normalized_value or po_d_f.raw_text if po_d_f else None
            d_po: date | None = None
            if po_d_str:
                try:
                    d_po = date.fromisoformat(po_d_str[:10])
                except (ValueError, TypeError):
                    pass

            for inv in invoices:
                inv_d_f = context.get_field(inv.id, "invoice_date")
                inv_d_str = inv_d_f.normalized_value or inv_d_f.raw_text if inv_d_f else None
                d_inv: date | None = None
                if inv_d_str:
                    try:
                        d_inv = date.fromisoformat(inv_d_str[:10])
                    except (ValueError, TypeError):
                        pass

                if not d_po or not d_inv:
                    continue

                delta_days = (d_inv - d_po).days
                loc_po = self.create_location_from_field(po.id, po_d_f, "po_date")
                loc_inv = self.create_location_from_field(inv.id, inv_d_f, "invoice_date")

                if delta_days >= 0:
                    outcome = ConsistencyOutcome.CONSISTENT
                    explanation = (
                        f"Chronologically consistent: Invoice issue date ({d_inv}) "
                        f"is {delta_days} day(s) after Purchase Order authorization date ({d_po})."
                    )
                    severity = FindingSeverity.INFO
                else:
                    outcome = ConsistencyOutcome.INCONSISTENT
                    explanation = (
                        f"Temporal contradiction detected: Invoice issue date ({d_inv}) precedes "
                        f"Purchase Order authorization date ({d_po}) by {abs(delta_days)} day(s). "
                        "An invoice cannot legitimately reference a purchase order issued in the future."
                    )
                    severity = FindingSeverity.HIGH

                comparison = ConsistencyComparison(
                    field_key="po_to_invoice_date",
                    source_doc_id=po.id,
                    source_value=str(d_po),
                    target_doc_id=inv.id,
                    target_value=str(d_inv),
                    comparison_type="DATE_SEQUENCE",
                    outcome=outcome,
                    difference=f"Invoice precedes PO by {abs(delta_days)} days"
                    if outcome == ConsistencyOutcome.INCONSISTENT
                    else None,
                    explanation=explanation,
                )

                finding = self.build_finding(
                    context=context,
                    outcome=outcome,
                    title=f"PO vs Invoice Temporal Order: {outcome.value}",
                    explanation=explanation,
                    affected_document_ids=[po.id, inv.id],
                    compared_fields=["po_date", "invoice_date"],
                    original_values={
                        f"{po.id}:po_date": po_d_str,
                        f"{inv.id}:invoice_date": inv_d_str,
                    },
                    normalized_values={
                        f"{po.id}:po_date": str(d_po),
                        f"{inv.id}:invoice_date": str(d_inv),
                    },
                    locations=[loc_po, loc_inv],
                    comparisons=[comparison],
                    severity=severity,
                    limitations=[
                        "Emergency or verbal authorizations later formalized with a post-dated PO can occur legitimately.",
                    ],
                )
                findings.append(finding)

        # 2. Invoice Due Date vs Payment/Receipt Date
        receipts = [d for d in context.documents if d.document_type == DocumentClass.RECEIPT]
        for inv in invoices:
            due_d_f = context.get_field(inv.id, "due_date")
            due_d_str = due_d_f.normalized_value or due_d_f.raw_text if due_d_f else None
            d_due: date | None = None
            if due_d_str:
                try:
                    d_due = date.fromisoformat(due_d_str[:10])
                except (ValueError, TypeError):
                    pass

            if not d_due:
                continue

            for rcpt in receipts:
                rcpt_d_f = context.get_field(rcpt.id, "transaction_date")
                rcpt_d_str = rcpt_d_f.normalized_value or rcpt_d_f.raw_text if rcpt_d_f else None
                d_rcpt: date | None = None
                if rcpt_d_str:
                    try:
                        d_rcpt = date.fromisoformat(rcpt_d_str[:10])
                    except (ValueError, TypeError):
                        pass

                if not d_rcpt:
                    continue

                loc_inv_due = self.create_location_from_field(inv.id, due_d_f, "due_date")
                loc_rcpt = self.create_location_from_field(rcpt.id, rcpt_d_f, "transaction_date")

                overdue_days = (d_rcpt - d_due).days
                if overdue_days > 0:
                    outcome = ConsistencyOutcome.POTENTIAL_ANOMALY
                    explanation = (
                        f"Late settlement observation: Payment receipt date ({d_rcpt}) is {overdue_days} day(s) "
                        f"after the invoice due date ({d_due})."
                    )
                    severity = FindingSeverity.LOW
                else:
                    outcome = ConsistencyOutcome.CONSISTENT
                    explanation = (
                        f"Timely payment: Payment receipt date ({d_rcpt}) is on or before "
                        f"invoice due date ({d_due})."
                    )
                    severity = FindingSeverity.INFO

                comparison = ConsistencyComparison(
                    field_key="due_date_to_payment",
                    source_doc_id=inv.id,
                    source_value=str(d_due),
                    target_doc_id=rcpt.id,
                    target_value=str(d_rcpt),
                    comparison_type="DATE_SEQUENCE",
                    outcome=outcome,
                    difference=f"Paid {overdue_days} days late" if overdue_days > 0 else None,
                    explanation=explanation,
                )

                finding = self.build_finding(
                    context=context,
                    outcome=outcome,
                    title=f"Invoice Due Date vs Payment Timing: {outcome.value}",
                    explanation=explanation,
                    affected_document_ids=[inv.id, rcpt.id],
                    compared_fields=["due_date", "transaction_date"],
                    original_values={
                        f"{inv.id}:due_date": due_d_str,
                        f"{rcpt.id}:date": rcpt_d_str,
                    },
                    normalized_values={
                        f"{inv.id}:due_date": str(d_due),
                        f"{rcpt.id}:date": str(d_rcpt),
                    },
                    locations=[loc_inv_due, loc_rcpt],
                    comparisons=[comparison],
                    severity=severity,
                )
                findings.append(finding)

        return findings
