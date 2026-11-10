"""Rule Family C: Invoice and Bank Statement cross-document consistency rules."""

from __future__ import annotations

from datetime import date
from typing import Any

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


class BankStatementInvoiceSettlementRule(BaseConsistencyRule):
    """Evaluates potential bank statement settlement records against invoices.

    Preserves explicit limitations: matching transaction amounts do not prove payment identity.
    """

    @property
    def rule_id(self) -> str:
        return "bank_statement_invoice_settlement"

    @property
    def rule_version(self) -> str:
        return "1.0.0"

    @property
    def rule_name(self) -> str:
        return "Bank Statement Transaction and Invoice Association Consistency"

    @property
    def description(self) -> str:
        return (
            "Compares bank statement ledger transactions against unpaid or billed invoices. "
            "Evaluates amount coincidence, currency compatibility, transaction timing relative to invoice date, "
            "and highlights ambiguous one-to-many or many-to-one potential associations."
        )

    @property
    def supported_document_types(self) -> list[DocumentClass]:
        return [DocumentClass.INVOICE, DocumentClass.BANK_STATEMENT]

    @property
    def category(self) -> FindingCategory:
        return FindingCategory.FINANCIAL_VALIDATION

    @property
    def detection_method(self) -> ConsistencyDetectionMethod:
        return ConsistencyDetectionMethod.MONETARY_RECONCILIATION_CHECK

    def evaluate(self, context: ConsistencyContext) -> list[ConsistencyFinding]:
        findings: list[ConsistencyFinding] = []
        invoices = [d for d in context.documents if d.document_type == DocumentClass.INVOICE]
        bank_statements = [
            d for d in context.documents if d.document_type == DocumentClass.BANK_STATEMENT
        ]

        if not invoices or not bank_statements:
            return findings

        # Collect candidate transactions from context synthetic_transactions or bank statement metadata
        transactions: list[dict[str, Any]] = list(context.synthetic_transactions)
        for bs in bank_statements:
            bs_txs = bs.metadata.get("transactions", [])
            for tx in bs_txs:
                tx_copy = dict(tx)
                tx_copy["bank_statement_id"] = bs.id
                transactions.append(tx_copy)

        for inv in invoices:
            inv_f = context.get_field_dict(inv.id)
            inv_num_f = inv_f.get("invoice_number")
            inv_tot_f = inv_f.get("total_amount")
            inv_curr_f = inv_f.get("currency")
            inv_date_f = inv_f.get("invoice_date")

            inv_num = inv_num_f.normalized_value or inv_num_f.raw_text if inv_num_f else ""
            inv_tot = parse_decimal(
                inv_tot_f.normalized_value or inv_tot_f.raw_text if inv_tot_f else None
            )
            inv_curr = inv_curr_f.normalized_value or inv_curr_f.raw_text if inv_curr_f else None
            inv_date_str = (
                inv_date_f.normalized_value or inv_date_f.raw_text if inv_date_f else None
            )

            d_inv: date | None = None
            if inv_date_str:
                try:
                    d_inv = date.fromisoformat(inv_date_str[:10])
                except (ValueError, TypeError):
                    pass

            loc_inv = self.create_location_from_field(inv.id, inv_tot_f, "total_amount")

            if inv_tot is None:
                continue

            # Check all transactions across bank statements
            matching_amount_txs: list[dict[str, Any]] = []
            matching_ref_txs: list[dict[str, Any]] = []

            for tx in transactions:
                tx_amt = parse_decimal(tx.get("amount"))
                tx_desc = str(tx.get("description", ""))
                tx_ref = str(tx.get("reference", ""))

                if (
                    tx_amt is not None
                    and (tx_amt - inv_tot).copy_abs() <= context.monetary_tolerance
                ):
                    matching_amount_txs.append(tx)

                if inv_num and (
                    inv_num.upper() in tx_desc.upper() or inv_num.upper() in tx_ref.upper()
                ):
                    matching_ref_txs.append(tx)

            # Case 1: Multiple transactions matching the exact amount (Ambiguity)
            if len(matching_amount_txs) > 1:
                affected_bs_ids: list[str] = [
                    str(tx.get("bank_statement_id"))
                    for tx in matching_amount_txs
                    if tx.get("bank_statement_id")
                ]
                finding = self.build_finding(
                    context=context,
                    outcome=ConsistencyOutcome.POTENTIAL_ANOMALY,
                    title="Ambiguous Multiple Bank Transactions for Single Invoice Amount",
                    explanation=(
                        f"Found {len(matching_amount_txs)} distinct bank transactions with amount {inv_tot} {inv_curr or ''} "
                        f"matching Invoice '{inv_num or inv.original_filename}'. Without unique remittance references, "
                        "amount coincidence alone cannot establish which transaction settles this invoice."
                    ),
                    affected_document_ids=[inv.id] + affected_bs_ids,
                    compared_fields=["total_amount", "transaction_amount"],
                    original_values={f"{inv.id}:total": str(inv_tot)},
                    normalized_values={f"{inv.id}:total": str(inv_tot)},
                    locations=[loc_inv],
                    comparisons=[],
                    severity=FindingSeverity.LOW,
                    limitations=[
                        "Coinciding transaction amounts do not prove payment identity.",
                        "Manual review or structured remittance matching is required.",
                    ],
                )
                findings.append(finding)

            # Case 2: Reference match with amount conflict
            for tx in matching_ref_txs:
                tx_amt = parse_decimal(tx.get("amount"))
                tx_curr = tx.get("currency") or inv_curr
                bs_id = tx.get("bank_statement_id") or (
                    bank_statements[0].id if bank_statements else "bs-1"
                )

                comp_res = compare_monetary_amounts(
                    amount_a_val=inv_tot,
                    currency_a_val=inv_curr,
                    amount_b_val=tx_amt,
                    currency_b_val=tx_curr,
                    tolerance=context.monetary_tolerance,
                    label_a=f"Invoice '{inv.original_filename}'",
                    label_b=f"Bank Tx '{tx.get('reference', 'TX')}'",
                )

                if comp_res.outcome == ConsistencyOutcome.INCONSISTENT:
                    finding = self.build_finding(
                        context=context,
                        outcome=ConsistencyOutcome.INCONSISTENT,
                        title="Referenced Bank Transaction Amount Discrepancy",
                        explanation=(
                            f"Transaction explicitly cites invoice '{inv_num}', but transaction amount "
                            f"({tx_amt} {tx_curr}) does not match billed invoice total ({inv_tot} {inv_curr}). "
                            f"{comp_res.explanation}"
                        ),
                        affected_document_ids=[inv.id, bs_id],
                        compared_fields=["total_amount", "amount"],
                        original_values={f"{inv.id}:total": str(inv_tot), "tx:amount": str(tx_amt)},
                        normalized_values={
                            f"{inv.id}:total": str(inv_tot),
                            "tx:amount": str(tx_amt),
                        },
                        locations=[loc_inv],
                        comparisons=[
                            ConsistencyComparison(
                                field_key="total_amount",
                                source_doc_id=inv.id,
                                source_value=str(inv_tot),
                                target_doc_id=bs_id,
                                target_value=str(tx_amt),
                                comparison_type="DECIMAL_MONETARY",
                                outcome=ConsistencyOutcome.INCONSISTENT,
                                difference=comp_res.difference_formatted,
                                explanation=comp_res.explanation,
                            )
                        ],
                        severity=FindingSeverity.HIGH,
                        limitations=[
                            "Discrepancy may reflect partial payment, installment, withholding tax, or bank fee deduction.",
                        ],
                    )
                    findings.append(finding)

            # Case 3: Exactly one transaction matching amount and currency
            if len(matching_amount_txs) == 1 and not matching_ref_txs:
                tx = matching_amount_txs[0]
                tx_amt = parse_decimal(tx.get("amount"))
                tx_date_str = tx.get("date")
                bs_id = tx.get("bank_statement_id") or (
                    bank_statements[0].id if bank_statements else "bs-1"
                )

                d_tx: date | None = None
                if tx_date_str:
                    try:
                        d_tx = date.fromisoformat(tx_date_str[:10])
                    except (ValueError, TypeError):
                        pass

                timing_outcome = ConsistencyOutcome.CONSISTENT
                timing_expl = ""
                if d_inv and d_tx:
                    if d_tx < d_inv:
                        timing_outcome = ConsistencyOutcome.POTENTIAL_ANOMALY
                        timing_expl = (
                            f" However, transaction date ({d_tx}) precedes invoice date ({d_inv}), "
                            "indicating potential prepayment or unrelated transaction."
                        )

                final_outcome = (
                    ConsistencyOutcome.POTENTIAL_ANOMALY
                    if timing_outcome == ConsistencyOutcome.POTENTIAL_ANOMALY
                    else ConsistencyOutcome.CONSISTENT
                )

                finding = self.build_finding(
                    context=context,
                    outcome=final_outcome,
                    title=f"Potential Bank Settlement for Invoice: {final_outcome.value}",
                    explanation=(
                        f"Found single bank transaction with matching amount ({inv_tot} {inv_curr or ''})."
                        f"{timing_expl} Note: Amount correspondence indicates potential association only, "
                        "not confirmed legal settlement."
                    ),
                    affected_document_ids=[inv.id, bs_id],
                    compared_fields=["total_amount", "amount", "date"],
                    original_values={f"{inv.id}:total": str(inv_tot), "tx:amount": str(tx_amt)},
                    normalized_values={f"{inv.id}:total": str(inv_tot), "tx:amount": str(tx_amt)},
                    locations=[loc_inv],
                    comparisons=[
                        ConsistencyComparison(
                            field_key="total_amount",
                            source_doc_id=inv.id,
                            source_value=str(inv_tot),
                            target_doc_id=bs_id,
                            target_value=str(tx_amt),
                            comparison_type="DECIMAL_MONETARY",
                            outcome=final_outcome,
                            difference=None,
                            explanation="Single transaction amount aligns with invoice gross total.",
                        )
                    ],
                    severity=FindingSeverity.LOW
                    if final_outcome == ConsistencyOutcome.POTENTIAL_ANOMALY
                    else FindingSeverity.INFO,
                    limitations=[
                        "Matching amounts establish analytical association candidate only.",
                        "Reconciliation requires verified bank ledger statement or remittance advice.",
                    ],
                )
                findings.append(finding)

        return findings
