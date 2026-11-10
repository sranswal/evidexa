"""Rule Family D: Supplier and Identity Consistency cross-document rules."""

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
from document_intelligence.modules.consistency.rules.base import BaseConsistencyRule


class CrossDocumentSupplierIdentityRule(BaseConsistencyRule):
    """Verifies supplier identity and tax identifier consistency across all documents in a case."""

    @property
    def rule_id(self) -> str:
        return "cross_document_supplier_identity"

    @property
    def rule_version(self) -> str:
        return "1.0.0"

    @property
    def rule_name(self) -> str:
        return "Cross-Document Supplier Identity and Tax ID Consistency"

    @property
    def description(self) -> str:
        return (
            "Detects conflicting tax identifiers and conflicting legal identities for the same commercial supplier "
            "across invoices, purchase orders, and supporting documents. A missing tax ID is treated as "
            "INSUFFICIENT_EVIDENCE, never as an automatic contradiction."
        )

    @property
    def supported_document_types(self) -> list[DocumentClass]:
        return [
            DocumentClass.INVOICE,
            DocumentClass.PURCHASE_ORDER,
            DocumentClass.RECEIPT,
            DocumentClass.CONTRACT,
        ]

    @property
    def category(self) -> FindingCategory:
        return FindingCategory.IDENTITY_VALIDATION

    @property
    def default_severity(self) -> FindingSeverity:
        return FindingSeverity.HIGH

    @property
    def detection_method(self) -> ConsistencyDetectionMethod:
        return ConsistencyDetectionMethod.IDENTITY_RECORD_ALIGNMENT

    def evaluate(self, context: ConsistencyContext) -> list[ConsistencyFinding]:
        findings: list[ConsistencyFinding] = []
        docs = [d for d in context.documents if d.document_type in self.supported_document_types]

        # Pairwise comparison bounded to avoid unbounded N^2
        max_docs = min(len(docs), 50)
        docs_subset = docs[:max_docs]

        for i in range(len(docs_subset)):
            doc_a = docs_subset[i]
            fields_a = context.get_field_dict(doc_a.id)
            supp_a_f = fields_a.get("supplier_name") or fields_a.get("merchant_name")
            tax_a_f = fields_a.get("supplier_tax_id") or fields_a.get("tax_id")

            supp_a = supp_a_f.normalized_value or supp_a_f.raw_text if supp_a_f else None
            tax_a = tax_a_f.normalized_value or tax_a_f.raw_text if tax_a_f else None

            if not supp_a and not tax_a:
                continue

            for j in range(i + 1, len(docs_subset)):
                doc_b = docs_subset[j]
                fields_b = context.get_field_dict(doc_b.id)
                supp_b_f = fields_b.get("supplier_name") or fields_b.get("merchant_name")
                tax_b_f = fields_b.get("supplier_tax_id") or fields_b.get("tax_id")

                supp_b = supp_b_f.normalized_value or supp_b_f.raw_text if supp_b_f else None
                tax_b = tax_b_f.normalized_value or tax_b_f.raw_text if tax_b_f else None

                if not supp_b and not tax_b:
                    continue

                # Normalize strings for comparison
                norm_supp_a = re.sub(r"[^A-Za-z0-9]", "", supp_a.upper()) if supp_a else ""
                norm_supp_b = re.sub(r"[^A-Za-z0-9]", "", supp_b.upper()) if supp_b else ""
                norm_tax_a = re.sub(r"[^A-Za-z0-9]", "", tax_a.upper()) if tax_a else ""
                norm_tax_b = re.sub(r"[^A-Za-z0-9]", "", tax_b.upper()) if tax_b else ""

                same_name = bool(
                    norm_supp_a
                    and norm_supp_b
                    and (
                        norm_supp_a == norm_supp_b
                        or norm_supp_a in norm_supp_b
                        or norm_supp_b in norm_supp_a
                    )
                )

                # Condition 1: Same supplier name, but contradictory tax IDs
                if same_name and norm_tax_a and norm_tax_b and norm_tax_a != norm_tax_b:
                    finding = self.build_finding(
                        context=context,
                        outcome=ConsistencyOutcome.INCONSISTENT,
                        title="Conflicting Tax Identifiers for Same Supplier Name",
                        explanation=(
                            f"Supplier '{supp_a}' appears on '{doc_a.original_filename}' with Tax ID '{tax_a}', "
                            f"but on '{doc_b.original_filename}' with conflicting Tax ID '{tax_b}'. "
                            "A single corporate entity typically does not possess distinct tax identifiers in the same jurisdiction."
                        ),
                        affected_document_ids=[doc_a.id, doc_b.id],
                        compared_fields=["supplier_name", "supplier_tax_id"],
                        original_values={
                            f"{doc_a.id}:tax_id": tax_a,
                            f"{doc_b.id}:tax_id": tax_b,
                        },
                        normalized_values={
                            f"{doc_a.id}:tax_id": norm_tax_a,
                            f"{doc_b.id}:tax_id": norm_tax_b,
                        },
                        locations=[
                            self.create_location_from_field(doc_a.id, tax_a_f, "supplier_tax_id"),
                            self.create_location_from_field(doc_b.id, tax_b_f, "supplier_tax_id"),
                        ],
                        comparisons=[
                            ConsistencyComparison(
                                field_key="supplier_tax_id",
                                source_doc_id=doc_a.id,
                                source_value=tax_a,
                                target_doc_id=doc_b.id,
                                target_value=tax_b,
                                comparison_type="STRING_EXACT",
                                outcome=ConsistencyOutcome.INCONSISTENT,
                                difference=f"{tax_a} != {tax_b}",
                                explanation="Direct contradiction in recorded tax identification numbers.",
                            )
                        ],
                        severity=FindingSeverity.HIGH,
                        limitations=[
                            "Multi-jurisdictional entities or corporate groups with distinct operating subsidiaries may hold separate tax numbers.",
                        ],
                    )
                    findings.append(finding)

                # Condition 2: Same supplier name, one has tax ID, one is missing
                elif same_name and (norm_tax_a or norm_tax_b) and not (norm_tax_a and norm_tax_b):
                    stated_tax = tax_a or tax_b
                    finding = self.build_finding(
                        context=context,
                        outcome=ConsistencyOutcome.INSUFFICIENT_EVIDENCE,
                        title="Supplier Tax Identifier Missing on Supporting Record",
                        explanation=(
                            f"Supplier '{supp_a}' has Tax ID '{stated_tax}' on one document, but no tax identifier "
                            "was extracted from the supporting document. A missing tax ID is not a contradiction."
                        ),
                        affected_document_ids=[doc_a.id, doc_b.id],
                        compared_fields=["supplier_tax_id"],
                        original_values={
                            f"{doc_a.id}:tax_id": tax_a,
                            f"{doc_b.id}:tax_id": tax_b,
                        },
                        normalized_values={
                            f"{doc_a.id}:tax_id": norm_tax_a or None,
                            f"{doc_b.id}:tax_id": norm_tax_b or None,
                        },
                        locations=[
                            self.create_location_from_field(doc_a.id, tax_a_f, "supplier_tax_id"),
                            self.create_location_from_field(doc_b.id, tax_b_f, "supplier_tax_id"),
                        ],
                        comparisons=[
                            ConsistencyComparison(
                                field_key="supplier_tax_id",
                                source_doc_id=doc_a.id,
                                source_value=tax_a,
                                target_doc_id=doc_b.id,
                                target_value=tax_b,
                                comparison_type="STRING_EXACT",
                                outcome=ConsistencyOutcome.INSUFFICIENT_EVIDENCE,
                                difference=None,
                                explanation="Unstated tax identifier does not constitute evidence of contradiction.",
                            )
                        ],
                        severity=FindingSeverity.INFO,
                    )
                    findings.append(finding)

                # Condition 3: Same tax ID, but completely different supplier names
                elif (
                    norm_tax_a
                    and norm_tax_b
                    and norm_tax_a == norm_tax_b
                    and supp_a
                    and supp_b
                    and not same_name
                ):
                    finding = self.build_finding(
                        context=context,
                        outcome=ConsistencyOutcome.POTENTIAL_ANOMALY,
                        title="Identical Tax Identifier Shared by Distinct Supplier Names",
                        explanation=(
                            f"Documents cite identical Tax ID '{tax_a}', but declare different entity names: "
                            f"'{supp_a}' on '{doc_a.original_filename}' and '{supp_b}' on '{doc_b.original_filename}'. "
                            "May indicate legal name change, DBA trading alias, or entity misrepresentation."
                        ),
                        affected_document_ids=[doc_a.id, doc_b.id],
                        compared_fields=["supplier_name", "supplier_tax_id"],
                        original_values={
                            f"{doc_a.id}:name": supp_a,
                            f"{doc_b.id}:name": supp_b,
                        },
                        normalized_values={
                            f"{doc_a.id}:name": supp_a,
                            f"{doc_b.id}:name": supp_b,
                        },
                        locations=[
                            self.create_location_from_field(doc_a.id, supp_a_f, "supplier_name"),
                            self.create_location_from_field(doc_b.id, supp_b_f, "supplier_name"),
                        ],
                        comparisons=[
                            ConsistencyComparison(
                                field_key="supplier_name",
                                source_doc_id=doc_a.id,
                                source_value=supp_a,
                                target_doc_id=doc_b.id,
                                target_value=supp_b,
                                comparison_type="NORMALIZED_IDENTITY",
                                outcome=ConsistencyOutcome.POTENTIAL_ANOMALY,
                                difference=f"{supp_a} != {supp_b}",
                                explanation="Identical tax ID associated with disparate legal names.",
                            )
                        ],
                        severity=FindingSeverity.MEDIUM,
                    )
                    findings.append(finding)

        return findings
