"""Rule Family E: Duplicate and Conflicting Records cross-document rules."""

from __future__ import annotations

import re

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


class DuplicateInvoiceReferenceConflictRule(BaseConsistencyRule):
    """Detects reuse of identical invoice numbers with conflicting financial or supplier content.

    Distinguishes legitimate exact duplicates from suspiciously contradictory records.
    """

    @property
    def rule_id(self) -> str:
        return "duplicate_invoice_reference_conflict"

    @property
    def rule_version(self) -> str:
        return "1.0.0"

    @property
    def rule_name(self) -> str:
        return "Duplicate Invoice Reference and Conflict Detection"

    @property
    def description(self) -> str:
        return (
            "Examines instances where identical invoice reference numbers appear across multiple documents. "
            "Evaluates whether the documents represent legitimate duplicates or contradictory records with "
            "divergent totals, dates, or vendor identities."
        )

    @property
    def supported_document_types(self) -> list[DocumentClass]:
        return [DocumentClass.INVOICE]

    @property
    def category(self) -> FindingCategory:
        return FindingCategory.DOCUMENT_INCONSISTENCY

    @property
    def default_severity(self) -> FindingSeverity:
        return FindingSeverity.CRITICAL

    @property
    def detection_method(self) -> ConsistencyDetectionMethod:
        return ConsistencyDetectionMethod.DUPLICATE_RECORD_ANALYSIS

    def evaluate(self, context: ConsistencyContext) -> list[ConsistencyFinding]:
        findings: list[ConsistencyFinding] = []
        invoices = [d for d in context.documents if d.document_type == DocumentClass.INVOICE]

        # Group invoices by extracted normalized invoice number
        invoices_by_ref: dict[str, list[str]] = {}
        for inv in invoices:
            num_f = context.get_field(inv.id, "invoice_number")
            raw_num = num_f.normalized_value or num_f.raw_text if num_f else None
            if raw_num:
                norm_num = re.sub(r"[^A-Za-z0-9]", "", raw_num.upper())
                if len(norm_num) >= 3:
                    invoices_by_ref.setdefault(norm_num, []).append(inv.id)

        # Check reference collisions
        for ref_key, doc_ids in invoices_by_ref.items():
            if len(doc_ids) < 2:
                continue

            for i in range(len(doc_ids)):
                for j in range(i + 1, len(doc_ids)):
                    doc_a = context.get_document(doc_ids[i])
                    doc_b = context.get_document(doc_ids[j])
                    if not doc_a or not doc_b:
                        continue

                    # Check byte identity
                    is_byte_identical = bool(
                        doc_a.sha256 and doc_b.sha256 and doc_a.sha256 == doc_b.sha256
                    )

                    fields_a = context.get_field_dict(doc_a.id)
                    fields_b = context.get_field_dict(doc_b.id)

                    tot_a_f = fields_a.get("total_amount")
                    tot_b_f = fields_b.get("total_amount")
                    supp_a_f = fields_a.get("supplier_name")
                    supp_b_f = fields_b.get("supplier_name")
                    date_a_f = fields_a.get("invoice_date")
                    date_b_f = fields_b.get("invoice_date")

                    tot_a = tot_a_f.normalized_value or tot_a_f.raw_text if tot_a_f else None
                    tot_b = tot_b_f.normalized_value or tot_b_f.raw_text if tot_b_f else None
                    supp_a = supp_a_f.normalized_value or supp_a_f.raw_text if supp_a_f else None
                    supp_b = supp_b_f.normalized_value or supp_b_f.raw_text if supp_b_f else None
                    date_a = date_a_f.normalized_value or date_a_f.raw_text if date_a_f else None
                    date_b = date_b_f.normalized_value or date_b_f.raw_text if date_b_f else None

                    # Evaluate totals
                    curr_a_f = fields_a.get("currency")
                    curr_b_f = fields_b.get("currency")
                    tot_comp = compare_monetary_amounts(
                        amount_a_val=tot_a,
                        currency_a_val=curr_a_f.normalized_value or curr_a_f.raw_text
                        if curr_a_f
                        else None,
                        amount_b_val=tot_b,
                        currency_b_val=curr_b_f.normalized_value or curr_b_f.raw_text
                        if curr_b_f
                        else None,
                        tolerance=context.monetary_tolerance,
                        label_a=f"Doc '{doc_a.original_filename}'",
                        label_b=f"Doc '{doc_b.original_filename}'",
                    )

                    # Evaluate suppliers
                    norm_s_a = re.sub(r"[^A-Za-z0-9]", "", supp_a.upper()) if supp_a else ""
                    norm_s_b = re.sub(r"[^A-Za-z0-9]", "", supp_b.upper()) if supp_b else ""
                    suppliers_conflict = bool(norm_s_a and norm_s_b and norm_s_a != norm_s_b)

                    # Evaluate dates
                    dates_conflict = bool(date_a and date_b and date_a != date_b)

                    comparisons: list[ConsistencyComparison] = []
                    locations = [
                        self.create_location_from_field(
                            doc_a.id, fields_a.get("invoice_number"), "invoice_number"
                        ),
                        self.create_location_from_field(
                            doc_b.id, fields_b.get("invoice_number"), "invoice_number"
                        ),
                    ]

                    # Branch 1: Byte-identical duplicate
                    if is_byte_identical:
                        outcome = ConsistencyOutcome.CONSISTENT
                        title = "Byte-Identical Duplicate Invoice Verified"
                        explanation = (
                            f"Documents '{doc_a.original_filename}' and '{doc_b.original_filename}' share reference "
                            f"'{ref_key}' and have identical cryptographic SHA-256 hashes ({doc_a.sha256[:12]}...). "
                            "This represents an exact duplicate file upload."
                        )
                        severity = FindingSeverity.INFO

                    # Branch 2: Contradictory content with same reference
                    elif (
                        suppliers_conflict
                        or tot_comp.outcome == ConsistencyOutcome.INCONSISTENT
                        or dates_conflict
                    ):
                        outcome = ConsistencyOutcome.INCONSISTENT
                        discrepancies = []
                        if suppliers_conflict:
                            discrepancies.append(f"Disparate suppliers ('{supp_a}' vs '{supp_b}')")
                        if tot_comp.outcome == ConsistencyOutcome.INCONSISTENT:
                            discrepancies.append(
                                f"Disparate totals ({tot_comp.difference_formatted})"
                            )
                        if dates_conflict:
                            discrepancies.append(f"Disparate dates ('{date_a}' vs '{date_b}')")

                        title = "Conflicting Duplicate Invoice Reference"
                        explanation = (
                            f"Invoice reference '{ref_key}' is reused across two distinct files with contradictory content: "
                            f"{'; '.join(discrepancies)}. Distinct invoices reusing the same invoice number indicate "
                            "potential invoice recycling, re-billing collision, or altered copy."
                        )
                        severity = FindingSeverity.CRITICAL

                        comparisons.append(
                            ConsistencyComparison(
                                field_key="invoice_number",
                                source_doc_id=doc_a.id,
                                source_value=ref_key,
                                target_doc_id=doc_b.id,
                                target_value=ref_key,
                                comparison_type="DUPLICATE_COLLISION",
                                outcome=ConsistencyOutcome.INCONSISTENT,
                                difference="; ".join(discrepancies),
                                explanation=explanation,
                            )
                        )

                    # Branch 3: Semantically identical fields without byte identity (e.g. re-scanned or re-exported)
                    elif (
                        tot_comp.outcome == ConsistencyOutcome.CONSISTENT
                        and not suppliers_conflict
                        and not dates_conflict
                    ):
                        outcome = ConsistencyOutcome.CONSISTENT
                        title = "Semantically Duplicate Invoice Verified"
                        explanation = (
                            f"Documents '{doc_a.original_filename}' and '{doc_b.original_filename}' share invoice reference "
                            f"'{ref_key}' with matching vendor ('{supp_a}'), matching total ({tot_a}), and matching date ({date_a}). "
                            "Represents a visual or formatting duplicate rather than a fraudulent collision."
                        )
                        severity = FindingSeverity.INFO

                    else:
                        outcome = ConsistencyOutcome.POTENTIAL_ANOMALY
                        title = "Duplicate Invoice Reference with Insufficient Field Provenance"
                        explanation = (
                            f"Invoice reference '{ref_key}' appears on multiple documents, but one or more critical fields "
                            "(totals, suppliers, or dates) could not be fully extracted to determine exact consistency."
                        )
                        severity = FindingSeverity.LOW

                    finding = self.build_finding(
                        context=context,
                        outcome=outcome,
                        title=title,
                        explanation=explanation,
                        affected_document_ids=[doc_a.id, doc_b.id],
                        compared_fields=[
                            "invoice_number",
                            "total_amount",
                            "supplier_name",
                            "invoice_date",
                        ],
                        original_values={
                            f"{doc_a.id}:ref": ref_key,
                            f"{doc_b.id}:ref": ref_key,
                            f"{doc_a.id}:total": tot_a,
                            f"{doc_b.id}:total": tot_b,
                        },
                        normalized_values={
                            f"{doc_a.id}:ref": ref_key,
                            f"{doc_b.id}:ref": ref_key,
                            f"{doc_a.id}:total": str(tot_comp.amount_a)
                            if tot_comp.amount_a is not None
                            else None,
                            f"{doc_b.id}:total": str(tot_comp.amount_b)
                            if tot_comp.amount_b is not None
                            else None,
                        },
                        locations=locations,
                        comparisons=comparisons,
                        severity=severity,
                        limitations=[
                            "Shared invoice numbers across distinct corporate divisions or fiscal years may occur legitimately.",
                        ],
                    )
                    findings.append(finding)

        return findings
