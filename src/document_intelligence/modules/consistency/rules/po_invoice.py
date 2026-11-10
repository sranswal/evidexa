"""Rule Family B: Purchase Order and Invoice cross-document consistency rules."""

from __future__ import annotations

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
    parse_decimal,
)
from document_intelligence.modules.consistency.rules.base import BaseConsistencyRule


class PurchaseOrderInvoiceReferenceRule(BaseConsistencyRule):
    """Verifies that an Invoice explicitly and accurately references the Purchase Order."""

    @property
    def rule_id(self) -> str:
        return "po_invoice_reference_consistency"

    @property
    def rule_version(self) -> str:
        return "1.0.0"

    @property
    def rule_name(self) -> str:
        return "Purchase Order and Invoice Reference Consistency"

    @property
    def description(self) -> str:
        return (
            "Checks that the invoice references the correct PO number and that the PO "
            "corresponds to the billed transaction."
        )

    @property
    def supported_document_types(self) -> list[DocumentClass]:
        return [DocumentClass.PURCHASE_ORDER, DocumentClass.INVOICE]

    def evaluate(self, context: ConsistencyContext) -> list[ConsistencyFinding]:
        findings: list[ConsistencyFinding] = []
        pos = [d for d in context.documents if d.document_type == DocumentClass.PURCHASE_ORDER]
        invoices = [d for d in context.documents if d.document_type == DocumentClass.INVOICE]

        for po in pos:
            po_num_f = context.get_field(po.id, "po_number")
            po_num = po_num_f.normalized_value or po_num_f.raw_text if po_num_f else None

            for inv in invoices:
                inv_po_f = context.get_field(inv.id, "purchase_order_number") or context.get_field(
                    inv.id, "po_reference"
                )
                inv_po_ref = inv_po_f.normalized_value or inv_po_f.raw_text if inv_po_f else None
                inv_text = context.raw_document_texts.get(inv.id, "")

                loc_po = self.create_location_from_field(po.id, po_num_f, "po_number")
                loc_inv = self.create_location_from_field(inv.id, inv_po_f, "po_reference")

                if not po_num:
                    outcome = ConsistencyOutcome.INSUFFICIENT_EVIDENCE
                    explanation = (
                        f"Purchase Order '{po.original_filename}' has no extracted PO number."
                    )
                elif inv_po_ref and inv_po_ref.strip().upper() == po_num.strip().upper():
                    outcome = ConsistencyOutcome.CONSISTENT
                    explanation = f"Invoice explicitly references Purchase Order '{po_num}'."
                elif po_num.strip().upper() in inv_text.upper():
                    outcome = ConsistencyOutcome.CONSISTENT
                    explanation = f"Purchase Order number '{po_num}' is cited within invoice text."
                elif inv_po_ref and inv_po_ref.strip().upper() != po_num.strip().upper():
                    outcome = ConsistencyOutcome.INCONSISTENT
                    explanation = (
                        f"Purchase order reference conflict: Invoice cites PO '{inv_po_ref}', "
                        f"which contradicts Purchase Order number '{po_num}'."
                    )
                else:
                    outcome = ConsistencyOutcome.INSUFFICIENT_EVIDENCE
                    explanation = f"Invoice '{inv.original_filename}' does not cite Purchase Order '{po_num}'."

                comparison = ConsistencyComparison(
                    field_key="po_reference",
                    source_doc_id=po.id,
                    source_value=po_num,
                    target_doc_id=inv.id,
                    target_value=inv_po_ref,
                    comparison_type="STRING_EXACT",
                    outcome=outcome,
                    difference=f"PO: {po_num} vs Inv: {inv_po_ref}"
                    if outcome == ConsistencyOutcome.INCONSISTENT
                    else None,
                    explanation=explanation,
                )

                finding = self.build_finding(
                    context=context,
                    outcome=outcome,
                    title=f"PO and Invoice Reference: {outcome.value}",
                    explanation=explanation,
                    affected_document_ids=[po.id, inv.id],
                    compared_fields=["po_number", "po_reference"],
                    original_values={
                        f"{po.id}:po_number": po_num,
                        f"{inv.id}:po_reference": inv_po_ref,
                    },
                    normalized_values={
                        f"{po.id}:po_number": po_num,
                        f"{inv.id}:po_reference": inv_po_ref,
                    },
                    locations=[loc_po, loc_inv],
                    comparisons=[comparison],
                    severity=FindingSeverity.MEDIUM
                    if outcome == ConsistencyOutcome.INCONSISTENT
                    else FindingSeverity.INFO,
                )
                findings.append(finding)

        return findings


class PurchaseOrderInvoicePartiesRule(BaseConsistencyRule):
    """Verifies that the Supplier and Buyer parties on a PO match the parties on the Invoice."""

    @property
    def rule_id(self) -> str:
        return "po_invoice_parties_consistency"

    @property
    def rule_version(self) -> str:
        return "1.0.0"

    @property
    def rule_name(self) -> str:
        return "Purchase Order and Invoice Parties Consistency"

    @property
    def description(self) -> str:
        return (
            "Compares buyer and supplier organizational identities between PO and Invoice. "
            "Detects conflicting counterparties or entity misalignments."
        )

    @property
    def supported_document_types(self) -> list[DocumentClass]:
        return [DocumentClass.PURCHASE_ORDER, DocumentClass.INVOICE]

    @property
    def detection_method(self) -> ConsistencyDetectionMethod:
        return ConsistencyDetectionMethod.IDENTITY_RECORD_ALIGNMENT

    def evaluate(self, context: ConsistencyContext) -> list[ConsistencyFinding]:
        findings: list[ConsistencyFinding] = []
        pos = [d for d in context.documents if d.document_type == DocumentClass.PURCHASE_ORDER]
        invoices = [d for d in context.documents if d.document_type == DocumentClass.INVOICE]

        for po in pos:
            po_supp_f = context.get_field(po.id, "supplier_name")
            po_buyer_f = context.get_field(po.id, "buyer_name")
            po_supp = po_supp_f.normalized_value or po_supp_f.raw_text if po_supp_f else None
            po_buyer = po_buyer_f.normalized_value or po_buyer_f.raw_text if po_buyer_f else None

            for inv in invoices:
                inv_supp_f = context.get_field(inv.id, "supplier_name")
                inv_buyer_f = context.get_field(inv.id, "buyer_name")
                inv_supp = (
                    inv_supp_f.normalized_value or inv_supp_f.raw_text if inv_supp_f else None
                )
                inv_buyer = (
                    inv_buyer_f.normalized_value or inv_buyer_f.raw_text if inv_buyer_f else None
                )

                comparisons: list[ConsistencyComparison] = []
                locations = [
                    self.create_location_from_field(po.id, po_supp_f, "supplier_name"),
                    self.create_location_from_field(po.id, po_buyer_f, "buyer_name"),
                    self.create_location_from_field(inv.id, inv_supp_f, "supplier_name"),
                    self.create_location_from_field(inv.id, inv_buyer_f, "buyer_name"),
                ]

                # Evaluate supplier
                supp_outcome = ConsistencyOutcome.INSUFFICIENT_EVIDENCE
                supp_expl = "Supplier names unstated on one or both records."
                if po_supp and inv_supp:
                    norm_p = "".join(ch.lower() for ch in po_supp if ch.isalnum())
                    norm_i = "".join(ch.lower() for ch in inv_supp if ch.isalnum())
                    if norm_p == norm_i or norm_p in norm_i or norm_i in norm_p:
                        supp_outcome = ConsistencyOutcome.CONSISTENT
                        supp_expl = f"Supplier '{po_supp}' matches invoice supplier '{inv_supp}'."
                    else:
                        supp_outcome = ConsistencyOutcome.INCONSISTENT
                        supp_expl = f"Supplier mismatch: PO names '{po_supp}' but Invoice names '{inv_supp}'."

                comparisons.append(
                    ConsistencyComparison(
                        field_key="supplier_name",
                        source_doc_id=po.id,
                        source_value=po_supp,
                        target_doc_id=inv.id,
                        target_value=inv_supp,
                        comparison_type="NORMALIZED_IDENTITY",
                        outcome=supp_outcome,
                        difference=f"{po_supp} != {inv_supp}"
                        if supp_outcome == ConsistencyOutcome.INCONSISTENT
                        else None,
                        explanation=supp_expl,
                    )
                )

                # Evaluate buyer
                buyer_outcome = ConsistencyOutcome.INSUFFICIENT_EVIDENCE
                buyer_expl = "Buyer names unstated on one or both records."
                if po_buyer and inv_buyer:
                    norm_pb = "".join(ch.lower() for ch in po_buyer if ch.isalnum())
                    norm_ib = "".join(ch.lower() for ch in inv_buyer if ch.isalnum())
                    if norm_pb == norm_ib or norm_pb in norm_ib or norm_ib in norm_pb:
                        buyer_outcome = ConsistencyOutcome.CONSISTENT
                        buyer_expl = f"Buyer '{po_buyer}' matches invoice buyer '{inv_buyer}'."
                    else:
                        buyer_outcome = ConsistencyOutcome.INCONSISTENT
                        buyer_expl = f"Buyer mismatch: PO buyer '{po_buyer}' differs from Invoice buyer '{inv_buyer}'."

                comparisons.append(
                    ConsistencyComparison(
                        field_key="buyer_name",
                        source_doc_id=po.id,
                        source_value=po_buyer,
                        target_doc_id=inv.id,
                        target_value=inv_buyer,
                        comparison_type="NORMALIZED_IDENTITY",
                        outcome=buyer_outcome,
                        difference=f"{po_buyer} != {inv_buyer}"
                        if buyer_outcome == ConsistencyOutcome.INCONSISTENT
                        else None,
                        explanation=buyer_expl,
                    )
                )

                overall_outcome = (
                    ConsistencyOutcome.INCONSISTENT
                    if (
                        supp_outcome == ConsistencyOutcome.INCONSISTENT
                        or buyer_outcome == ConsistencyOutcome.INCONSISTENT
                    )
                    else (
                        ConsistencyOutcome.CONSISTENT
                        if (
                            supp_outcome == ConsistencyOutcome.CONSISTENT
                            and buyer_outcome == ConsistencyOutcome.CONSISTENT
                        )
                        else ConsistencyOutcome.INSUFFICIENT_EVIDENCE
                    )
                )

                explanation = f"Parties evaluation: {supp_expl} {buyer_expl}"
                finding = self.build_finding(
                    context=context,
                    outcome=overall_outcome,
                    title=f"PO and Invoice Parties: {overall_outcome.value}",
                    explanation=explanation,
                    affected_document_ids=[po.id, inv.id],
                    compared_fields=["supplier_name", "buyer_name"],
                    original_values={
                        f"{po.id}:supplier": po_supp,
                        f"{po.id}:buyer": po_buyer,
                        f"{inv.id}:supplier": inv_supp,
                        f"{inv.id}:buyer": inv_buyer,
                    },
                    normalized_values={
                        f"{po.id}:supplier": po_supp,
                        f"{po.id}:buyer": po_buyer,
                        f"{inv.id}:supplier": inv_supp,
                        f"{inv.id}:buyer": inv_buyer,
                    },
                    locations=locations,
                    comparisons=comparisons,
                    severity=FindingSeverity.HIGH
                    if overall_outcome == ConsistencyOutcome.INCONSISTENT
                    else FindingSeverity.INFO,
                )
                findings.append(finding)

        return findings


class PurchaseOrderInvoiceFinancialsRule(BaseConsistencyRule):
    """Verifies totals, unit prices, and quantities between Purchase Order and Invoice."""

    @property
    def rule_id(self) -> str:
        return "po_invoice_financials_consistency"

    @property
    def rule_version(self) -> str:
        return "1.0.0"

    @property
    def rule_name(self) -> str:
        return "Purchase Order and Invoice Financials and Line Items Consistency"

    @property
    def description(self) -> str:
        return (
            "Compares subtotal, tax, total, unit price, and quantity between PO and Invoice using Decimal precision. "
            "Differences are highlighted with exact discrepancies."
        )

    @property
    def supported_document_types(self) -> list[DocumentClass]:
        return [DocumentClass.PURCHASE_ORDER, DocumentClass.INVOICE]

    @property
    def category(self) -> FindingCategory:
        return FindingCategory.FINANCIAL_VALIDATION

    @property
    def detection_method(self) -> ConsistencyDetectionMethod:
        return ConsistencyDetectionMethod.MONETARY_RECONCILIATION_CHECK

    def evaluate(self, context: ConsistencyContext) -> list[ConsistencyFinding]:
        findings: list[ConsistencyFinding] = []
        pos = [d for d in context.documents if d.document_type == DocumentClass.PURCHASE_ORDER]
        invoices = [d for d in context.documents if d.document_type == DocumentClass.INVOICE]

        for po in pos:
            po_f = context.get_field_dict(po.id)
            for inv in invoices:
                inv_f = context.get_field_dict(inv.id)

                comparisons: list[ConsistencyComparison] = []
                locations = []

                # 1. Total Amount Comparison
                po_tot_f = po_f.get("total_amount")
                inv_tot_f = inv_f.get("total_amount")
                po_curr_f = po_f.get("currency")
                inv_curr_f = inv_f.get("currency")

                locations.append(self.create_location_from_field(po.id, po_tot_f, "total_amount"))
                locations.append(self.create_location_from_field(inv.id, inv_tot_f, "total_amount"))

                tot_res = compare_monetary_amounts(
                    amount_a_val=po_tot_f.normalized_value or po_tot_f.raw_text
                    if po_tot_f
                    else None,
                    currency_a_val=po_curr_f.normalized_value or po_curr_f.raw_text
                    if po_curr_f
                    else None,
                    amount_b_val=inv_tot_f.normalized_value or inv_tot_f.raw_text
                    if inv_tot_f
                    else None,
                    currency_b_val=inv_curr_f.normalized_value or inv_curr_f.raw_text
                    if inv_curr_f
                    else None,
                    tolerance=context.monetary_tolerance,
                    label_a=f"PO '{po.original_filename}'",
                    label_b=f"Invoice '{inv.original_filename}'",
                )

                comparisons.append(
                    ConsistencyComparison(
                        field_key="total_amount",
                        source_doc_id=po.id,
                        source_value=str(tot_res.amount_a)
                        if tot_res.amount_a is not None
                        else None,
                        target_doc_id=inv.id,
                        target_value=str(tot_res.amount_b)
                        if tot_res.amount_b is not None
                        else None,
                        comparison_type="DECIMAL_MONETARY",
                        outcome=tot_res.outcome,
                        difference=tot_res.difference_formatted,
                        explanation=tot_res.explanation,
                    )
                )

                # 2. Line Item Quantity Comparison (if both present)
                po_qty_f = po_f.get("line_item_quantity")
                inv_qty_f = inv_f.get("line_item_quantity") or inv_f.get("quantity")
                qty_outcome = ConsistencyOutcome.NOT_APPLICABLE
                qty_expl = "Line-item quantities not present on both documents."
                if po_qty_f and inv_qty_f:
                    locations.append(
                        self.create_location_from_field(po.id, po_qty_f, "line_item_quantity")
                    )
                    locations.append(
                        self.create_location_from_field(inv.id, inv_qty_f, "line_item_quantity")
                    )
                    q_po = parse_decimal(po_qty_f.normalized_value or po_qty_f.raw_text)
                    q_inv = parse_decimal(inv_qty_f.normalized_value or inv_qty_f.raw_text)
                    if q_po is not None and q_inv is not None:
                        if q_po == q_inv:
                            qty_outcome = ConsistencyOutcome.CONSISTENT
                            qty_expl = f"Quantities match exactly: {q_po} units."
                        else:
                            qty_outcome = ConsistencyOutcome.INCONSISTENT
                            qty_expl = f"Quantity mismatch: PO specifies {q_po} units, but Invoice bills {q_inv} units."
                        comparisons.append(
                            ConsistencyComparison(
                                field_key="line_item_quantity",
                                source_doc_id=po.id,
                                source_value=str(q_po),
                                target_doc_id=inv.id,
                                target_value=str(q_inv),
                                comparison_type="DECIMAL_QUANTITY",
                                outcome=qty_outcome,
                                difference=f"{q_po} != {q_inv}"
                                if qty_outcome == ConsistencyOutcome.INCONSISTENT
                                else None,
                                explanation=qty_expl,
                            )
                        )

                # 3. Unit Price Comparison (if both present)
                po_price_f = po_f.get("line_item_unit_price")
                inv_price_f = inv_f.get("line_item_unit_price") or inv_f.get("unit_price")
                price_outcome = ConsistencyOutcome.NOT_APPLICABLE
                price_expl = "Unit prices not present on both documents."
                if po_price_f and inv_price_f:
                    locations.append(
                        self.create_location_from_field(po.id, po_price_f, "line_item_unit_price")
                    )
                    locations.append(
                        self.create_location_from_field(inv.id, inv_price_f, "line_item_unit_price")
                    )
                    price_res = compare_monetary_amounts(
                        amount_a_val=po_price_f.normalized_value or po_price_f.raw_text,
                        currency_a_val=po_curr_f.normalized_value if po_curr_f else None,
                        amount_b_val=inv_price_f.normalized_value or inv_price_f.raw_text,
                        currency_b_val=inv_curr_f.normalized_value if inv_curr_f else None,
                        tolerance=context.monetary_tolerance,
                        label_a="PO Unit Price",
                        label_b="Invoice Unit Price",
                    )
                    price_outcome = price_res.outcome
                    price_expl = price_res.explanation
                    comparisons.append(
                        ConsistencyComparison(
                            field_key="line_item_unit_price",
                            source_doc_id=po.id,
                            source_value=str(price_res.amount_a)
                            if price_res.amount_a is not None
                            else None,
                            target_doc_id=inv.id,
                            target_value=str(price_res.amount_b)
                            if price_res.amount_b is not None
                            else None,
                            comparison_type="DECIMAL_MONETARY",
                            outcome=price_res.outcome,
                            difference=price_res.difference_formatted,
                            explanation=price_res.explanation,
                        )
                    )

                # Aggregate overall financial outcome
                overall_outcome = tot_res.outcome
                if (
                    qty_outcome == ConsistencyOutcome.INCONSISTENT
                    or price_outcome == ConsistencyOutcome.INCONSISTENT
                ):
                    overall_outcome = ConsistencyOutcome.INCONSISTENT

                finding = self.build_finding(
                    context=context,
                    outcome=overall_outcome,
                    title=f"PO and Invoice Financials: {overall_outcome.value}",
                    explanation=f"{tot_res.explanation} {qty_expl} {price_expl}".strip(),
                    affected_document_ids=[po.id, inv.id],
                    compared_fields=["total_amount", "line_item_quantity", "line_item_unit_price"],
                    original_values={
                        f"{po.id}:total": po_tot_f.raw_text if po_tot_f else None,
                        f"{inv.id}:total": inv_tot_f.raw_text if inv_tot_f else None,
                    },
                    normalized_values={
                        f"{po.id}:total": str(tot_res.amount_a)
                        if tot_res.amount_a is not None
                        else None,
                        f"{inv.id}:total": str(tot_res.amount_b)
                        if tot_res.amount_b is not None
                        else None,
                    },
                    locations=locations,
                    comparisons=comparisons,
                    severity=FindingSeverity.HIGH
                    if overall_outcome == ConsistencyOutcome.INCONSISTENT
                    else FindingSeverity.INFO,
                )
                findings.append(finding)

        return findings
