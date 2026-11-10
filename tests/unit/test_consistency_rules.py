"""Unit tests verifying all 6 deterministic cross-document consistency rule families."""

from decimal import Decimal

from document_intelligence.domain.enums import (
    ConsistencyOutcome,
    DocumentClass,
    FieldDataType,
    FindingSeverity,
)
from document_intelligence.domain.models.bounding_box import BoundingBox
from document_intelligence.domain.models.document import Document
from document_intelligence.domain.models.extraction import ExtractedFieldValue
from document_intelligence.modules.consistency.context import ConsistencyContext
from document_intelligence.modules.consistency.rules.bank_statement_invoice import (
    BankStatementInvoiceSettlementRule,
)
from document_intelligence.modules.consistency.rules.duplicate_conflicts import (
    DuplicateInvoiceReferenceConflictRule,
)
from document_intelligence.modules.consistency.rules.identity_consistency import (
    CrossDocumentSupplierIdentityRule,
)
from document_intelligence.modules.consistency.rules.invoice_receipt import (
    InvoiceReceiptMerchantConsistencyRule,
    InvoiceReceiptReferenceConsistencyRule,
    InvoiceReceiptTotalConsistencyRule,
)
from document_intelligence.modules.consistency.rules.po_invoice import (
    PurchaseOrderInvoiceFinancialsRule,
)
from document_intelligence.modules.consistency.rules.temporal_consistency import (
    CrossDocumentTemporalSequenceRule,
)


def _make_doc(
    doc_id: str, doc_class: DocumentClass, filename: str, sha256: str | None = None
) -> Document:
    return Document(
        id=doc_id,
        case_id="case-100",
        original_filename=filename,
        media_type="application/pdf",
        file_extension=".pdf",
        file_size_bytes=1024,
        sha256=sha256 or ("a" * 64),
        storage_key=f"case-100/{filename}",
        document_type=doc_class.value,
    )


def _make_field(
    doc_id: str,
    key: str,
    raw: str,
    norm: str | Decimal,
    page: int = 1,
    data_type: FieldDataType = FieldDataType.STRING,
) -> ExtractedFieldValue:
    return ExtractedFieldValue(
        field_key=key,
        label=key.replace("_", " ").title(),
        raw_text=raw,
        normalized_value=norm,
        data_type=data_type,
        source_document_id=doc_id,
        source_page_number=page,
        source_bounding_boxes=[BoundingBox(x=0.1, y=0.1, width=0.4, height=0.1)],
        evidence_node_id=f"ev-{doc_id}-{key}",
    )


class TestInvoiceReceiptRules:
    """Tests for Rule Family A: Invoice and Receipt."""

    def test_invoice_receipt_matching_totals_consistent(self) -> None:
        inv = _make_doc("inv-1", DocumentClass.INVOICE, "invoice.pdf")
        rcpt = _make_doc("rcpt-1", DocumentClass.RECEIPT, "receipt.pdf")

        fields_inv = [
            _make_field(
                "inv-1",
                "total_amount",
                "85000.00",
                Decimal("85000.00"),
                data_type=FieldDataType.DECIMAL,
            ),
            _make_field("inv-1", "currency", "INR", "INR", data_type=FieldDataType.CURRENCY),
        ]
        fields_rcpt = [
            _make_field(
                "rcpt-1",
                "total_amount",
                "85000.00",
                Decimal("85000.00"),
                data_type=FieldDataType.DECIMAL,
            ),
            _make_field("rcpt-1", "currency", "INR", "INR", data_type=FieldDataType.CURRENCY),
        ]

        ctx = ConsistencyContext(
            case_id="case-100",
            analysis_run_id="run-1",
            documents=[inv, rcpt],
            extracted_fields_by_doc={"inv-1": fields_inv, "rcpt-1": fields_rcpt},
        )

        rule = InvoiceReceiptTotalConsistencyRule()
        findings = rule.evaluate(ctx)

        assert len(findings) == 1
        finding = findings[0]
        assert finding.outcome == ConsistencyOutcome.CONSISTENT
        assert finding.affected_document_ids == ["inv-1", "rcpt-1"]
        assert len(finding.locations) == 2
        assert finding.locations[0].page_number == 1
        assert finding.locations[0].bounding_box is not None

    def test_invoice_receipt_differing_totals_inconsistent(self) -> None:
        inv = _make_doc("inv-1", DocumentClass.INVOICE, "invoice.pdf")
        rcpt = _make_doc("rcpt-1", DocumentClass.RECEIPT, "receipt.pdf")

        fields_inv = [
            _make_field(
                "inv-1",
                "total_amount",
                "85000.00",
                Decimal("85000.00"),
                data_type=FieldDataType.DECIMAL,
            ),
            _make_field("inv-1", "currency", "INR", "INR"),
        ]
        fields_rcpt = [
            _make_field(
                "rcpt-1",
                "total_amount",
                "95000.00",
                Decimal("95000.00"),
                data_type=FieldDataType.DECIMAL,
            ),
            _make_field("rcpt-1", "currency", "INR", "INR"),
        ]

        ctx = ConsistencyContext(
            case_id="case-100",
            analysis_run_id="run-1",
            documents=[inv, rcpt],
            extracted_fields_by_doc={"inv-1": fields_inv, "rcpt-1": fields_rcpt},
        )

        rule = InvoiceReceiptTotalConsistencyRule()
        findings = rule.evaluate(ctx)

        assert len(findings) == 1
        f = findings[0]
        assert f.outcome == ConsistencyOutcome.INCONSISTENT
        assert f.severity == FindingSeverity.HIGH
        assert "10000.00 INR" in f.explanation
        assert len(f.contradicting_evidence_ids) == 2

    def test_invoice_receipt_reference_match_and_contradiction(self) -> None:
        inv = _make_doc("inv-1", DocumentClass.INVOICE, "invoice.pdf")
        rcpt_match = _make_doc("rcpt-1", DocumentClass.RECEIPT, "receipt.pdf")
        rcpt_mismatch = _make_doc("rcpt-2", DocumentClass.RECEIPT, "receipt_mismatch.pdf")

        fields_inv = [_make_field("inv-1", "invoice_number", "INV-2026-001", "INV-2026-001")]
        fields_rcpt1 = [_make_field("rcpt-1", "invoice_reference", "INV-2026-001", "INV-2026-001")]
        fields_rcpt2 = [_make_field("rcpt-2", "invoice_reference", "INV-9999-999", "INV-9999-999")]

        rule = InvoiceReceiptReferenceConsistencyRule()

        # Matching reference
        ctx1 = ConsistencyContext(
            case_id="case-100",
            analysis_run_id="run-1",
            documents=[inv, rcpt_match],
            extracted_fields_by_doc={"inv-1": fields_inv, "rcpt-1": fields_rcpt1},
        )
        findings1 = rule.evaluate(ctx1)
        assert len(findings1) == 1
        assert findings1[0].outcome == ConsistencyOutcome.CONSISTENT

        # Contradicting reference
        ctx2 = ConsistencyContext(
            case_id="case-100",
            analysis_run_id="run-1",
            documents=[inv, rcpt_mismatch],
            extracted_fields_by_doc={"inv-1": fields_inv, "rcpt-2": fields_rcpt2},
        )
        findings2 = rule.evaluate(ctx2)
        assert len(findings2) == 1
        assert findings2[0].outcome == ConsistencyOutcome.INCONSISTENT
        assert "contradicts Invoice number 'INV-2026-001'" in findings2[0].explanation

    def test_invoice_receipt_merchant_consistency_and_variation(self) -> None:
        inv = _make_doc("inv-1", DocumentClass.INVOICE, "invoice.pdf")
        rcpt1 = _make_doc("rcpt-1", DocumentClass.RECEIPT, "receipt1.pdf")
        rcpt2 = _make_doc("rcpt-2", DocumentClass.RECEIPT, "receipt2.pdf")

        fields_inv = [
            _make_field("inv-1", "supplier_name", "Acme Logistics Inc.", "Acme Logistics Inc.")
        ]
        fields_rcpt1 = [_make_field("rcpt-1", "merchant_name", "Acme Logistics", "Acme Logistics")]
        fields_rcpt2 = [
            _make_field("rcpt-2", "merchant_name", "Global Fuel Station", "Global Fuel Station")
        ]

        rule = InvoiceReceiptMerchantConsistencyRule()

        # Consistent name
        ctx1 = ConsistencyContext(
            case_id="case-100",
            analysis_run_id="run-1",
            documents=[inv, rcpt1],
            extracted_fields_by_doc={"inv-1": fields_inv, "rcpt-1": fields_rcpt1},
        )
        f1 = rule.evaluate(ctx1)
        assert f1[0].outcome == ConsistencyOutcome.CONSISTENT

        # Potential anomaly (variation)
        ctx2 = ConsistencyContext(
            case_id="case-100",
            analysis_run_id="run-1",
            documents=[inv, rcpt2],
            extracted_fields_by_doc={"inv-1": fields_inv, "rcpt-2": fields_rcpt2},
        )
        f2 = rule.evaluate(ctx2)
        assert f2[0].outcome == ConsistencyOutcome.POTENTIAL_ANOMALY
        assert f2[0].severity == FindingSeverity.LOW


class TestPurchaseOrderInvoiceRules:
    """Tests for Rule Family B: Purchase Order and Invoice."""

    def test_po_invoice_quantity_and_price_mismatch(self) -> None:
        po = _make_doc("po-1", DocumentClass.PURCHASE_ORDER, "po.pdf")
        inv = _make_doc("inv-1", DocumentClass.INVOICE, "inv.pdf")

        fields_po = [
            _make_field(
                "po-1",
                "total_amount",
                "5000.00",
                Decimal("5000.00"),
                data_type=FieldDataType.DECIMAL,
            ),
            _make_field("po-1", "currency", "USD", "USD"),
            _make_field(
                "po-1", "line_item_quantity", "50", Decimal("50"), data_type=FieldDataType.DECIMAL
            ),
            _make_field(
                "po-1",
                "line_item_unit_price",
                "100.00",
                Decimal("100.00"),
                data_type=FieldDataType.DECIMAL,
            ),
        ]
        fields_inv = [
            _make_field(
                "inv-1",
                "total_amount",
                "6000.00",
                Decimal("6000.00"),
                data_type=FieldDataType.DECIMAL,
            ),
            _make_field("inv-1", "currency", "USD", "USD"),
            _make_field(
                "inv-1", "line_item_quantity", "60", Decimal("60"), data_type=FieldDataType.DECIMAL
            ),  # Mismatch: 60 vs 50
            _make_field(
                "inv-1",
                "line_item_unit_price",
                "100.00",
                Decimal("100.00"),
                data_type=FieldDataType.DECIMAL,
            ),
        ]

        ctx = ConsistencyContext(
            case_id="case-100",
            analysis_run_id="run-1",
            documents=[po, inv],
            extracted_fields_by_doc={"po-1": fields_po, "inv-1": fields_inv},
        )

        rule = PurchaseOrderInvoiceFinancialsRule()
        findings = rule.evaluate(ctx)

        assert len(findings) == 1
        f = findings[0]
        assert f.outcome == ConsistencyOutcome.INCONSISTENT
        assert "Quantity mismatch" in f.explanation
        assert len(f.comparisons) >= 2


class TestBankStatementInvoiceRules:
    """Tests for Rule Family C: Invoice and Bank Statement."""

    def test_ambiguous_multiple_matching_transactions(self) -> None:
        inv = _make_doc("inv-1", DocumentClass.INVOICE, "inv.pdf")
        bs = _make_doc("bs-1", DocumentClass.BANK_STATEMENT, "bank_statement.pdf")

        fields_inv = [
            _make_field("inv-1", "invoice_number", "INV-888", "INV-888"),
            _make_field(
                "inv-1",
                "total_amount",
                "4500.00",
                Decimal("4500.00"),
                data_type=FieldDataType.DECIMAL,
            ),
            _make_field("inv-1", "currency", "USD", "USD"),
            _make_field("inv-1", "invoice_date", "2026-05-10", "2026-05-10"),
        ]

        # Two distinct transactions with matching amount of 4500.00 without reference
        synthetic_txs = [
            {
                "amount": "4500.00",
                "currency": "USD",
                "date": "2026-05-12",
                "description": "WIRE TRANSFER 1",
                "reference": "TX-001",
                "bank_statement_id": "bs-1",
            },
            {
                "amount": "4500.00",
                "currency": "USD",
                "date": "2026-05-15",
                "description": "WIRE TRANSFER 2",
                "reference": "TX-002",
                "bank_statement_id": "bs-1",
            },
        ]

        ctx = ConsistencyContext(
            case_id="case-100",
            analysis_run_id="run-1",
            documents=[inv, bs],
            extracted_fields_by_doc={"inv-1": fields_inv},
            synthetic_transactions=synthetic_txs,
        )

        rule = BankStatementInvoiceSettlementRule()
        findings = rule.evaluate(ctx)

        assert len(findings) == 1
        f = findings[0]
        assert f.outcome == ConsistencyOutcome.POTENTIAL_ANOMALY
        assert "Ambiguous Multiple Bank Transactions" in f.title
        assert "cannot establish which transaction settles this invoice" in f.explanation


class TestIdentityAndDuplicateRules:
    """Tests for Rule Families D & E: Identity consistency and Duplicate records."""

    def test_supplier_conflicting_tax_identifiers(self) -> None:
        inv1 = _make_doc("inv-1", DocumentClass.INVOICE, "inv1.pdf")
        inv2 = _make_doc("inv-2", DocumentClass.INVOICE, "inv2.pdf")

        fields1 = [
            _make_field("inv-1", "supplier_name", "Global Energy Corp", "Global Energy Corp"),
            _make_field("inv-1", "supplier_tax_id", "TAX-US-11111", "TAX-US-11111"),
        ]
        fields2 = [
            _make_field("inv-2", "supplier_name", "Global Energy Corp", "Global Energy Corp"),
            _make_field("inv-2", "supplier_tax_id", "TAX-US-99999", "TAX-US-99999"),  # Conflict!
        ]

        ctx = ConsistencyContext(
            case_id="case-100",
            analysis_run_id="run-1",
            documents=[inv1, inv2],
            extracted_fields_by_doc={"inv-1": fields1, "inv-2": fields2},
        )

        rule = CrossDocumentSupplierIdentityRule()
        findings = rule.evaluate(ctx)

        assert len(findings) == 1
        assert findings[0].outcome == ConsistencyOutcome.INCONSISTENT
        assert "Conflicting Tax Identifiers" in findings[0].title
        assert "TAX-US-11111" in findings[0].explanation
        assert "TAX-US-99999" in findings[0].explanation

    def test_missing_tax_id_is_insufficient_evidence_not_contradiction(self) -> None:
        inv1 = _make_doc("inv-1", DocumentClass.INVOICE, "inv1.pdf")
        inv2 = _make_doc("inv-2", DocumentClass.INVOICE, "inv2.pdf")

        fields1 = [
            _make_field("inv-1", "supplier_name", "Global Energy Corp", "Global Energy Corp"),
            _make_field("inv-1", "supplier_tax_id", "TAX-US-11111", "TAX-US-11111"),
        ]
        fields2 = [
            _make_field("inv-2", "supplier_name", "Global Energy Corp", "Global Energy Corp"),
            # No tax id extracted on second invoice
        ]

        ctx = ConsistencyContext(
            case_id="case-100",
            analysis_run_id="run-1",
            documents=[inv1, inv2],
            extracted_fields_by_doc={"inv-1": fields1, "inv-2": fields2},
        )

        rule = CrossDocumentSupplierIdentityRule()
        findings = rule.evaluate(ctx)

        assert len(findings) == 1
        assert findings[0].outcome == ConsistencyOutcome.INSUFFICIENT_EVIDENCE
        assert "A missing tax ID is not a contradiction" in findings[0].explanation

    def test_duplicate_invoice_reference_with_conflicting_content(self) -> None:
        inv1 = _make_doc("inv-1", DocumentClass.INVOICE, "inv1.pdf", sha256="1" * 64)
        inv2 = _make_doc("inv-2", DocumentClass.INVOICE, "inv2.pdf", sha256="2" * 64)

        fields1 = [
            _make_field("inv-1", "invoice_number", "INV-REC-100", "INV-REC-100"),
            _make_field("inv-1", "supplier_name", "Vendor Alpha", "Vendor Alpha"),
            _make_field(
                "inv-1",
                "total_amount",
                "1000.00",
                Decimal("1000.00"),
                data_type=FieldDataType.DECIMAL,
            ),
            _make_field("inv-1", "invoice_date", "2026-01-01", "2026-01-01"),
        ]
        fields2 = [
            _make_field("inv-2", "invoice_number", "INV-REC-100", "INV-REC-100"),  # Same reference
            _make_field(
                "inv-2", "supplier_name", "Vendor Omega", "Vendor Omega"
            ),  # Different vendor!
            _make_field(
                "inv-2",
                "total_amount",
                "2500.00",
                Decimal("2500.00"),
                data_type=FieldDataType.DECIMAL,
            ),  # Different total!
            _make_field("inv-2", "invoice_date", "2026-01-01", "2026-01-01"),
        ]

        ctx = ConsistencyContext(
            case_id="case-100",
            analysis_run_id="run-1",
            documents=[inv1, inv2],
            extracted_fields_by_doc={"inv-1": fields1, "inv-2": fields2},
        )

        rule = DuplicateInvoiceReferenceConflictRule()
        findings = rule.evaluate(ctx)

        assert len(findings) == 1
        f = findings[0]
        assert f.outcome == ConsistencyOutcome.INCONSISTENT
        assert f.severity == FindingSeverity.CRITICAL
        assert "Conflicting Duplicate Invoice Reference" in f.title
        assert "Disparate suppliers" in f.explanation


class TestTemporalConsistencyRules:
    """Tests for Rule Family F: Temporal Consistency."""

    def test_invoice_predating_purchase_order_is_inconsistent(self) -> None:
        po = _make_doc("po-1", DocumentClass.PURCHASE_ORDER, "po.pdf")
        inv = _make_doc("inv-1", DocumentClass.INVOICE, "inv.pdf")

        fields_po = [_make_field("po-1", "po_date", "2026-06-15", "2026-06-15")]
        fields_inv = [
            _make_field("inv-1", "invoice_date", "2026-06-01", "2026-06-01")
        ]  # 14 days BEFORE PO!

        ctx = ConsistencyContext(
            case_id="case-100",
            analysis_run_id="run-1",
            documents=[po, inv],
            extracted_fields_by_doc={"po-1": fields_po, "inv-1": fields_inv},
        )

        rule = CrossDocumentTemporalSequenceRule()
        findings = rule.evaluate(ctx)

        assert len(findings) == 1
        f = findings[0]
        assert f.outcome == ConsistencyOutcome.INCONSISTENT
        assert f.severity == FindingSeverity.HIGH
        assert "Temporal contradiction detected" in f.explanation
        assert (
            "precedes Purchase Order authorization date (2026-06-15) by 14 day(s)" in f.explanation
        )
