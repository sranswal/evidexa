"""Rule registry and execution engine for cross-document consistency analysis."""

from __future__ import annotations

import logging

from document_intelligence.domain.models.consistency import (
    ConsistencyFinding,
    ConsistencyRule,
)
from document_intelligence.modules.consistency.context import ConsistencyContext
from document_intelligence.modules.consistency.rules.bank_statement_invoice import (
    BankStatementInvoiceSettlementRule,
)
from document_intelligence.modules.consistency.rules.base import BaseConsistencyRule
from document_intelligence.modules.consistency.rules.duplicate_conflicts import (
    DuplicateInvoiceReferenceConflictRule,
)
from document_intelligence.modules.consistency.rules.identity_consistency import (
    CrossDocumentSupplierIdentityRule,
)
from document_intelligence.modules.consistency.rules.invoice_receipt import (
    InvoiceReceiptMerchantConsistencyRule,
    InvoiceReceiptReferenceConsistencyRule,
    InvoiceReceiptTimingConsistencyRule,
    InvoiceReceiptTotalConsistencyRule,
)
from document_intelligence.modules.consistency.rules.po_invoice import (
    PurchaseOrderInvoiceFinancialsRule,
    PurchaseOrderInvoicePartiesRule,
    PurchaseOrderInvoiceReferenceRule,
)
from document_intelligence.modules.consistency.rules.temporal_consistency import (
    CrossDocumentTemporalSequenceRule,
)

logger = logging.getLogger(__name__)


class ConsistencyRuleRegistry:
    """Registry maintaining active cross-document consistency rules."""

    def __init__(self) -> None:
        self._rules: dict[str, BaseConsistencyRule] = {}
        self._register_default_rules()

    def _register_default_rules(self) -> None:
        # Rule Family A: Invoice and Receipt
        self.register_rule(InvoiceReceiptTotalConsistencyRule())
        self.register_rule(InvoiceReceiptReferenceConsistencyRule())
        self.register_rule(InvoiceReceiptMerchantConsistencyRule())
        self.register_rule(InvoiceReceiptTimingConsistencyRule())

        # Rule Family B: Purchase Order and Invoice
        self.register_rule(PurchaseOrderInvoiceReferenceRule())
        self.register_rule(PurchaseOrderInvoicePartiesRule())
        self.register_rule(PurchaseOrderInvoiceFinancialsRule())

        # Rule Family C: Invoice and Bank Statement
        self.register_rule(BankStatementInvoiceSettlementRule())

        # Rule Family D: Supplier and Identity Consistency
        self.register_rule(CrossDocumentSupplierIdentityRule())

        # Rule Family E: Duplicate and Conflicting Records
        self.register_rule(DuplicateInvoiceReferenceConflictRule())

        # Rule Family F: Temporal Sequence Consistency
        self.register_rule(CrossDocumentTemporalSequenceRule())

    def register_rule(self, rule: BaseConsistencyRule) -> None:
        """Register a new or updated consistency rule."""
        self._rules[rule.rule_id] = rule

    def get_rule(self, rule_id: str) -> BaseConsistencyRule | None:
        """Retrieve a rule by its rule_id."""
        return self._rules.get(rule_id)

    def list_rules(self) -> list[BaseConsistencyRule]:
        """List all active registered rules."""
        return list(self._rules.values())

    def get_rule_metadata(self) -> list[ConsistencyRule]:
        """Export domain metadata models for all registered rules."""
        return [
            ConsistencyRule(
                rule_id=r.rule_id,
                rule_version=r.rule_version,
                rule_name=r.rule_name,
                description=r.description,
                supported_document_types=r.supported_document_types,
                required_field_keys=r.required_field_keys,
                category=r.category,
                default_severity=r.default_severity,
            )
            for r in self._rules.values()
        ]


default_consistency_rule_registry = ConsistencyRuleRegistry()


class ConsistencyAnalysisEngine:
    """Deterministic analysis engine evaluating cross-document consistency rules."""

    def __init__(self, registry: ConsistencyRuleRegistry | None = None) -> None:
        self._registry = registry or default_consistency_rule_registry

    def analyze(
        self,
        context: ConsistencyContext,
        rule_ids: list[str] | None = None,
    ) -> list[ConsistencyFinding]:
        """Execute selected or all registered consistency rules against the provided case context."""
        selected_rules: list[BaseConsistencyRule] = []
        if rule_ids:
            for rid in rule_ids:
                rule = self._registry.get_rule(rid)
                if rule:
                    selected_rules.append(rule)
                else:
                    logger.warning("Requested unknown consistency rule '%s'", rid)
        else:
            selected_rules = self._registry.list_rules()

        all_findings: list[ConsistencyFinding] = []

        for rule in selected_rules:
            try:
                rule_findings = rule.evaluate(context)
                all_findings.extend(rule_findings)
            except Exception as e:
                logger.error(
                    "Error executing consistency rule '%s' on case '%s': %s",
                    rule.rule_id,
                    context.case_id,
                    str(e),
                    exc_info=True,
                )
                # Partial failure resilience: record rule error without halting the entire run

        return all_findings
