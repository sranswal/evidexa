"""Unit tests for deterministic cross-document relationship detection engine and detectors."""

from __future__ import annotations

from decimal import Decimal

from document_intelligence.domain.enums import (
    DuplicateKind,
    EntityMatchClassification,
    EntityMatchingMethod,
    FieldDataType,
    MatchDecisionStatus,
    RelationshipDetectionMethod,
    RelationshipStatus,
    RelationshipType,
    ResolvedEntityType,
    StatusDeterminationMethod,
)
from document_intelligence.domain.identifiers import generate_id
from document_intelligence.domain.models.bounding_box import BoundingBox
from document_intelligence.domain.models.document import Document
from document_intelligence.domain.models.entity_resolution import (
    EntityCandidateMatch,
    EntityMatchEvidence,
    EntityMention,
)
from document_intelligence.domain.models.extraction import ExtractedFieldValue
from document_intelligence.modules.relationship_detection.detectors.bank_statement import (
    BankStatementRelationshipDetector,
)
from document_intelligence.modules.relationship_detection.detectors.base import (
    DetectionContext,
)
from document_intelligence.modules.relationship_detection.detectors.document_similarity import (
    DocumentRelationshipDetector,
)
from document_intelligence.modules.relationship_detection.detectors.entity_role import (
    EntityRoleRelationshipDetector,
)
from document_intelligence.modules.relationship_detection.detectors.invoice import (
    InvoiceRelationshipDetector,
)
from document_intelligence.modules.relationship_detection.detectors.receipt import (
    ReceiptRelationshipDetector,
)
from document_intelligence.modules.relationship_detection.engine import (
    RelationshipDetectionEngine,
)


def _make_dummy_doc(case_id: str, filename: str, sha256: str = "a" * 64) -> Document:
    return Document(
        case_id=case_id,
        original_filename=filename,
        media_type="application/pdf",
        file_extension=".pdf",
        file_size_bytes=1024,
        sha256=sha256,
        storage_key=f"{case_id}/{filename}",
    )


class TestInvoiceRelationshipDetection:
    """Test suite for invoice-related commercial relationships."""

    def test_supplier_issues_invoice(self) -> None:
        case_id = generate_id()
        doc = _make_dummy_doc(case_id, "invoice_001.pdf")
        supplier_field = ExtractedFieldValue(
            field_key="supplier_name",
            label="Supplier",
            normalized_value="Acme Corp Industries",
            raw_text="Acme Corp Industries",
            data_type=FieldDataType.STRING,
            source_document_id=doc.id,
            source_page_number=1,
            source_bounding_boxes=[BoundingBox(x=0.1, y=0.1, width=0.3, height=0.05)],
            evidence_node_id="ev_sup_01",
        )
        tax_field = ExtractedFieldValue(
            field_key="supplier_tax_id",
            label="Tax ID",
            normalized_value="12-3456789",
            raw_text="12-3456789",
            data_type=FieldDataType.STRING,
            source_document_id=doc.id,
            source_page_number=1,
            evidence_node_id="ev_tax_01",
        )

        ctx = DetectionContext(
            case_id=case_id,
            detection_run_id=generate_id(),
            documents=[doc],
            extracted_fields_by_doc={doc.id: [supplier_field, tax_field]},
        )
        detector = InvoiceRelationshipDetector()
        rels = detector.detect(ctx)

        sup_rels = [r for r in rels if r.relationship_type == RelationshipType.ISSUED]
        assert len(sup_rels) == 1
        rel = sup_rels[0]
        assert rel.status == RelationshipStatus.CONFIRMED
        assert rel.status_determination_method == StatusDeterminationMethod.EVIDENTIARY_RULE
        assert rel.source_id == "ORG:ACME CORP INDUSTRIES"
        assert rel.target_id == doc.id
        assert (
            rel.direction_display
            == f"Acme Corp Industries --ISSUED--> Document '{doc.original_filename}'"
        )
        assert "ev_sup_01" in rel.evidence.supporting_evidence_node_ids
        assert "ev_tax_01" in rel.evidence.supporting_evidence_node_ids
        assert len(rel.evidence.bounding_boxes) == 1

    def test_buyer_receives_invoice_and_supplies_relationship(self) -> None:
        """Requirement: Invoice co-occurrence creates INVOICED, NEVER ongoing SUPPLIES."""
        case_id = generate_id()
        doc = _make_dummy_doc(case_id, "invoice_002.pdf")
        sup = ExtractedFieldValue(
            field_key="supplier_name",
            label="Supplier",
            normalized_value="Global Parts Ltd",
            data_type=FieldDataType.STRING,
            source_document_id=doc.id,
            source_page_number=1,
        )
        buyer = ExtractedFieldValue(
            field_key="buyer_name",
            label="Buyer",
            normalized_value="Omega Logistics Inc",
            data_type=FieldDataType.STRING,
            source_document_id=doc.id,
            source_page_number=1,
        )

        ctx = DetectionContext(
            case_id=case_id,
            detection_run_id=generate_id(),
            documents=[doc],
            extracted_fields_by_doc={doc.id: [sup, buyer]},
        )
        detector = InvoiceRelationshipDetector()
        rels = detector.detect(ctx)

        billed_to = [r for r in rels if r.relationship_type == RelationshipType.BILLED_TO]
        assert len(billed_to) == 1
        assert billed_to[0].source_id == doc.id
        assert billed_to[0].target_id == "ORG:OMEGA LOGISTICS INC"
        assert (
            billed_to[0].direction_display
            == f"Document '{doc.original_filename}' --BILLED_TO--> Omega Logistics Inc"
        )

        # Verified: INVOICED is created for single invoice billing
        invoiced = [r for r in rels if r.relationship_type == RelationshipType.INVOICED]
        assert len(invoiced) == 1
        assert invoiced[0].source_label == "Global Parts Ltd"
        assert invoiced[0].target_label == "Omega Logistics Inc"
        assert invoiced[0].direction_display == "Global Parts Ltd --INVOICED--> Omega Logistics Inc"

        # Verified: SUPPLIES is NOT created from invoice co-occurrence alone
        supplies = [r for r in rels if r.relationship_type == RelationshipType.SUPPLIES]
        assert len(supplies) == 0

    def test_explicit_supply_contract_supports_supplies(self) -> None:
        """Requirement: SUPPLIES is strictly reserved for explicit contract/arrangement evidence."""
        case_id = generate_id()
        doc = _make_dummy_doc(case_id, "master_agreement.pdf")
        sup = ExtractedFieldValue(
            field_key="supplier_name",
            label="Supplier",
            normalized_value="Global Parts Ltd",
            data_type=FieldDataType.STRING,
            source_document_id=doc.id,
            source_page_number=1,
        )
        buyer = ExtractedFieldValue(
            field_key="buyer_name",
            label="Buyer",
            normalized_value="Omega Logistics Inc",
            data_type=FieldDataType.STRING,
            source_document_id=doc.id,
            source_page_number=1,
        )

        ctx = DetectionContext(
            case_id=case_id,
            detection_run_id=generate_id(),
            documents=[doc],
            extracted_fields_by_doc={doc.id: [sup, buyer]},
            raw_document_texts={
                doc.id: "MASTER SUPPLY AGREEMENT between Global Parts Ltd and Omega Logistics Inc."
            },
        )
        detector = InvoiceRelationshipDetector()
        rels = detector.detect(ctx)

        supplies = [r for r in rels if r.relationship_type == RelationshipType.SUPPLIES]
        assert len(supplies) == 1
        assert supplies[0].source_label == "Global Parts Ltd"
        assert supplies[0].target_label == "Omega Logistics Inc"
        assert supplies[0].status == RelationshipStatus.CONFIRMED
        assert supplies[0].detection_method == RelationshipDetectionMethod.CONTRACT_CLAUSE_RULE

    def test_invoice_references_purchase_order(self) -> None:
        case_id = generate_id()
        inv_doc = _make_dummy_doc(case_id, "inv_101.pdf")
        po_doc = _make_dummy_doc(case_id, "PO-99420.pdf")

        ctx = DetectionContext(
            case_id=case_id,
            detection_run_id=generate_id(),
            documents=[inv_doc, po_doc],
            extracted_fields_by_doc={inv_doc.id: []},
            raw_document_texts={
                inv_doc.id: "INVOICE #INV-101\nPurchase Order: PO-99420\nTotal Due: $500.00"
            },
        )
        detector = InvoiceRelationshipDetector()
        rels = detector.detect(ctx)

        po_rels = [
            r for r in rels if r.relationship_type == RelationshipType.REFERENCES_PURCHASE_ORDER
        ]
        assert len(po_rels) == 1
        assert po_rels[0].source_id == inv_doc.id
        assert po_rels[0].target_id == po_doc.id
        assert po_rels[0].status == RelationshipStatus.CONFIRMED


class TestReceiptRelationshipDetection:
    """Test suite for receipt issuance, payment authorization, and invoice reference."""

    def test_merchant_issues_receipt(self) -> None:
        case_id = generate_id()
        doc = _make_dummy_doc(case_id, "receipt_88.pdf")
        merchant = ExtractedFieldValue(
            field_key="merchant_name",
            label="Merchant",
            normalized_value="Corner Store Retail",
            data_type=FieldDataType.STRING,
            source_document_id=doc.id,
            source_page_number=1,
        )
        ctx = DetectionContext(
            case_id=case_id,
            detection_run_id=generate_id(),
            documents=[doc],
            extracted_fields_by_doc={doc.id: [merchant]},
        )
        detector = ReceiptRelationshipDetector()
        rels = detector.detect(ctx)

        merch_rels = [r for r in rels if r.relationship_type == RelationshipType.ISSUED]
        assert len(merch_rels) == 1
        assert merch_rels[0].source_label == "Corner Store Retail"
        assert merch_rels[0].target_id == doc.id
        assert (
            merch_rels[0].direction_display
            == f"Corner Store Retail --ISSUED--> Document '{doc.original_filename}'"
        )
        assert merch_rels[0].status == RelationshipStatus.CONFIRMED

    def test_receipt_references_invoice_explicitly(self) -> None:
        case_id = generate_id()
        rec_doc = _make_dummy_doc(case_id, "receipt.pdf")
        inv_doc = _make_dummy_doc(case_id, "invoice.pdf")

        inv_num_field = ExtractedFieldValue(
            field_key="invoice_number",
            label="Invoice Number",
            normalized_value="INV-2026-X",
            data_type=FieldDataType.STRING,
            source_document_id=inv_doc.id,
            source_page_number=1,
        )

        ctx = DetectionContext(
            case_id=case_id,
            detection_run_id=generate_id(),
            documents=[rec_doc, inv_doc],
            extracted_fields_by_doc={
                rec_doc.id: [],
                inv_doc.id: [inv_num_field],
            },
            raw_document_texts={
                rec_doc.id: "RECEIPT PAYMENT\nInvoice Ref: INV-2026-X\nPaid: $150.00"
            },
        )
        detector = ReceiptRelationshipDetector()
        rels = detector.detect(ctx)

        ref_rels = [r for r in rels if r.relationship_type == RelationshipType.REFERENCES_INVOICE]
        assert len(ref_rels) == 1
        assert ref_rels[0].status == RelationshipStatus.CONFIRMED
        assert ref_rels[0].score == 1.0
        assert ref_rels[0].source_id == rec_doc.id
        assert ref_rels[0].target_id == inv_doc.id

    def test_receipt_and_invoice_matching_totals_without_explicit_reference(
        self,
    ) -> None:
        """Requirement: Matching totals alone must be classified as UNRESOLVED / amount coincidence."""
        case_id = generate_id()
        rec_doc = _make_dummy_doc(case_id, "pos_receipt.pdf")
        inv_doc = _make_dummy_doc(case_id, "corp_invoice.pdf")

        rec_total = ExtractedFieldValue(
            field_key="total_amount",
            label="Total",
            normalized_value=Decimal("450.00"),
            data_type=FieldDataType.DECIMAL,
            source_document_id=rec_doc.id,
            source_page_number=1,
        )
        inv_total = ExtractedFieldValue(
            field_key="total_amount",
            label="Total",
            normalized_value=Decimal("450.00"),
            data_type=FieldDataType.DECIMAL,
            source_document_id=inv_doc.id,
            source_page_number=1,
        )

        ctx = DetectionContext(
            case_id=case_id,
            detection_run_id=generate_id(),
            documents=[rec_doc, inv_doc],
            extracted_fields_by_doc={
                rec_doc.id: [rec_total],
                inv_doc.id: [inv_total],
            },
            raw_document_texts={
                rec_doc.id: "TOTAL: $450.00\nTHANK YOU FOR SHOPPING",
                inv_doc.id: "INVOICE #INV-888\nTOTAL: $450.00",
            },
        )
        detector = ReceiptRelationshipDetector()
        rels = detector.detect(ctx)

        coinc_rels = [r for r in rels if r.relationship_type == RelationshipType.REFERENCES_INVOICE]
        assert len(coinc_rels) == 1
        rel = coinc_rels[0]
        assert rel.status == RelationshipStatus.UNRESOLVED
        assert rel.score == 0.35
        assert rel.score_semantics == "evidence_strength"

    def test_receipt_records_payment_with_auth_code(self) -> None:
        case_id = generate_id()
        rec_doc = _make_dummy_doc(case_id, "terminal_slip.pdf")
        pay_method = ExtractedFieldValue(
            field_key="payment_method",
            label="Payment Method",
            normalized_value="VISA",
            data_type=FieldDataType.STRING,
            source_document_id=rec_doc.id,
            source_page_number=1,
        )
        ctx = DetectionContext(
            case_id=case_id,
            detection_run_id=generate_id(),
            documents=[rec_doc],
            extracted_fields_by_doc={rec_doc.id: [pay_method]},
            raw_document_texts={
                rec_doc.id: "TRANSACTION RECORD\nApproval Code: AUTH-88219\nVISA ****1199"
            },
        )
        detector = ReceiptRelationshipDetector()
        rels = detector.detect(ctx)

        pay_rels = [r for r in rels if r.relationship_type == RelationshipType.RECORDS_PAYMENT]
        assert len(pay_rels) == 1
        assert pay_rels[0].status == RelationshipStatus.CONFIRMED
        assert pay_rels[0].score == 1.0
        assert "PAYMENT_AUTH:AUTH-88219" in pay_rels[0].target_id


class TestBankStatementRelationshipDetection:
    """Test suite for bank statement summaries, non-fabrication of transactions, and settlement checks."""

    def test_bank_statement_summary_only_does_not_fabricate_transactions(
        self,
    ) -> None:
        """Requirement: Current bank statement schema contains only summary fields. Do NOT fabricate transactions."""
        case_id = generate_id()
        doc = _make_dummy_doc(case_id, "statement_jan.pdf")
        holder = ExtractedFieldValue(
            field_key="account_holder",
            label="Account Holder",
            normalized_value="Cyberdyne Systems Corp",
            data_type=FieldDataType.STRING,
            source_document_id=doc.id,
            source_page_number=1,
        )
        bank = ExtractedFieldValue(
            field_key="bank_name",
            label="Bank",
            normalized_value="First National Bank",
            data_type=FieldDataType.STRING,
            source_document_id=doc.id,
            source_page_number=1,
        )
        acct_masked = ExtractedFieldValue(
            field_key="account_number_masked",
            label="Account Number",
            normalized_value="****5432",
            data_type=FieldDataType.MASKED_STRING,
            source_document_id=doc.id,
            source_page_number=1,
        )

        ctx = DetectionContext(
            case_id=case_id,
            detection_run_id=generate_id(),
            documents=[doc],
            extracted_fields_by_doc={doc.id: [holder, bank, acct_masked]},
            synthetic_transactions=[],  # No transactions
        )
        detector = BankStatementRelationshipDetector()
        rels = detector.detect(ctx)

        # Verified: Account --HELD_BY--> Holder
        held_rels = [r for r in rels if r.relationship_type == RelationshipType.HELD_BY]
        assert len(held_rels) == 1
        assert held_rels[0].status == RelationshipStatus.CONFIRMED
        assert held_rels[0].source_id == "ACCT:****5432"
        assert held_rels[0].target_label == "Cyberdyne Systems Corp"
        assert (
            held_rels[0].direction_display == "Account ****5432 --HELD_BY--> Cyberdyne Systems Corp"
        )

        # Verified: Bank --ISSUED--> Statement
        bank_rels = [r for r in rels if r.relationship_type == RelationshipType.ISSUED]
        assert len(bank_rels) == 1
        assert bank_rels[0].source_label == "First National Bank"
        assert bank_rels[0].target_id == doc.id

        # Zero CONTAINS_TRANSACTION or MAY_SETTLE relationships fabricated
        tx_rels = [
            r
            for r in rels
            if r.relationship_type
            in (RelationshipType.CONTAINS_TRANSACTION, RelationshipType.MAY_SETTLE)
        ]
        assert len(tx_rels) == 0

    def test_transaction_may_settle_invoice_with_explicit_reference(self) -> None:
        case_id = generate_id()
        stmt_doc = _make_dummy_doc(case_id, "stmt.pdf")
        inv_doc = _make_dummy_doc(case_id, "inv.pdf")

        inv_total = ExtractedFieldValue(
            field_key="total_amount",
            label="Total",
            normalized_value=Decimal("1250.00"),
            data_type=FieldDataType.DECIMAL,
            source_document_id=inv_doc.id,
            source_page_number=1,
        )
        inv_num = ExtractedFieldValue(
            field_key="invoice_number",
            label="Invoice #",
            normalized_value="INV-990",
            data_type=FieldDataType.STRING,
            source_document_id=inv_doc.id,
            source_page_number=1,
        )

        tx = {
            "transaction_id": "TX-7711",
            "statement_document_id": stmt_doc.id,
            "amount": Decimal("1250.00"),
            "currency": "USD",
            "description": "Wire Pmt for INV-990 settlement",
        }

        ctx = DetectionContext(
            case_id=case_id,
            detection_run_id=generate_id(),
            documents=[stmt_doc, inv_doc],
            extracted_fields_by_doc={inv_doc.id: [inv_total, inv_num]},
            synthetic_transactions=[tx],
        )
        detector = BankStatementRelationshipDetector()
        rels = detector.detect(ctx)

        settle_rels = [r for r in rels if r.relationship_type == RelationshipType.MAY_SETTLE]
        assert len(settle_rels) == 1
        assert settle_rels[0].status == RelationshipStatus.CANDIDATE
        assert settle_rels[0].score == 0.90
        assert "cites invoice number 'INV-990'" in settle_rels[0].status_rationale

    def test_transaction_amount_coincidence_without_reference_is_unresolved(
        self,
    ) -> None:
        """Requirement: Amount equality alone cannot establish payment settlement."""
        case_id = generate_id()
        stmt_doc = _make_dummy_doc(case_id, "stmt.pdf")
        inv_doc = _make_dummy_doc(case_id, "inv.pdf")

        inv_total = ExtractedFieldValue(
            field_key="total_amount",
            label="Total",
            normalized_value=Decimal("1250.00"),
            data_type=FieldDataType.DECIMAL,
            source_document_id=inv_doc.id,
            source_page_number=1,
        )
        inv_num = ExtractedFieldValue(
            field_key="invoice_number",
            label="Invoice #",
            normalized_value="INV-990",
            data_type=FieldDataType.STRING,
            source_document_id=inv_doc.id,
            source_page_number=1,
        )

        tx = {
            "transaction_id": "TX-8800",
            "statement_document_id": stmt_doc.id,
            "amount": Decimal("1250.00"),
            "currency": "USD",
            "description": "General debit",  # No reference to INV-990
        }

        ctx = DetectionContext(
            case_id=case_id,
            detection_run_id=generate_id(),
            documents=[stmt_doc, inv_doc],
            extracted_fields_by_doc={inv_doc.id: [inv_total, inv_num]},
            synthetic_transactions=[tx],
        )
        detector = BankStatementRelationshipDetector()
        rels = detector.detect(ctx)

        settle_rels = [r for r in rels if r.relationship_type == RelationshipType.MAY_SETTLE]
        assert len(settle_rels) == 1
        rel = settle_rels[0]
        assert rel.status == RelationshipStatus.UNRESOLVED
        assert rel.score == 0.35
        assert rel.score_semantics == "amount_coincidence_heuristic"

    def test_transaction_currency_mismatch_is_contradicted(self) -> None:
        case_id = generate_id()
        stmt_doc = _make_dummy_doc(case_id, "stmt.pdf")
        inv_doc = _make_dummy_doc(case_id, "inv.pdf")

        inv_total = ExtractedFieldValue(
            field_key="total_amount",
            label="Total",
            normalized_value=Decimal("1250.00"),
            data_type=FieldDataType.DECIMAL,
            source_document_id=inv_doc.id,
            source_page_number=1,
        )
        inv_curr = ExtractedFieldValue(
            field_key="currency",
            label="Currency",
            normalized_value="USD",
            data_type=FieldDataType.CURRENCY,
            source_document_id=inv_doc.id,
            source_page_number=1,
        )

        tx = {
            "transaction_id": "TX-9999",
            "statement_document_id": stmt_doc.id,
            "amount": Decimal("1250.00"),
            "currency": "EUR",  # EUR vs USD
            "description": "Cross border payment",
        }

        ctx = DetectionContext(
            case_id=case_id,
            detection_run_id=generate_id(),
            documents=[stmt_doc, inv_doc],
            extracted_fields_by_doc={inv_doc.id: [inv_total, inv_curr]},
            synthetic_transactions=[tx],
        )
        detector = BankStatementRelationshipDetector()
        rels = detector.detect(ctx)

        contradicted = [r for r in rels if r.relationship_type == RelationshipType.MAY_SETTLE]
        assert len(contradicted) == 1
        assert contradicted[0].status == RelationshipStatus.CONTRADICTED
        assert contradicted[0].score == 0.0


class TestEntityRoleAndDocumentRelationships:
    """Test suite for corporate representation and document hash duplicate detection."""

    def test_person_represents_organization_explicit_role(self) -> None:
        case_id = generate_id()
        doc = _make_dummy_doc(case_id, "board_minutes.pdf")
        text = (
            "PRESENT AT MEETING:\n"
            "Arthur Pendelton, Director of Apex Global Technologies Inc.\n"
            "Action items discussed."
        )
        ctx = DetectionContext(
            case_id=case_id,
            detection_run_id=generate_id(),
            documents=[doc],
            raw_document_texts={doc.id: text},
        )
        detector = EntityRoleRelationshipDetector()
        rels = detector.detect(ctx)

        rep_rels = [r for r in rels if r.relationship_type == RelationshipType.REPRESENTS]
        assert len(rep_rels) == 1
        assert rep_rels[0].status == RelationshipStatus.CONFIRMED
        assert rep_rels[0].source_label == "Arthur Pendelton"
        assert rep_rels[0].target_label == "Apex Global Technologies Inc"
        assert (
            rep_rels[0].direction_display
            == "Arthur Pendelton --REPRESENTS--> Apex Global Technologies Inc"
        )

    def test_person_and_org_name_co_occurrence_without_role_is_unresolved(
        self,
    ) -> None:
        """Requirement: Do not infer representation from name co-occurrence alone."""
        case_id = generate_id()
        doc = _make_dummy_doc(case_id, "memo.pdf")
        p_mention = EntityMention(
            case_id=case_id,
            document_id=doc.id,
            page_number=1,
            processing_run_id="run_1",
            field_key="person_name",
            entity_type=ResolvedEntityType.PERSON,
            original_value="Alice Smith",
            normalized_value="alice smith",
        )
        org_mention = EntityMention(
            case_id=case_id,
            document_id=doc.id,
            page_number=1,
            processing_run_id="run_1",
            field_key="org_name",
            entity_type=ResolvedEntityType.ORGANIZATION,
            original_value="Beta Corp",
            normalized_value="beta corp",
        )

        ctx = DetectionContext(
            case_id=case_id,
            detection_run_id=generate_id(),
            documents=[doc],
            entity_mentions=[p_mention, org_mention],
            raw_document_texts={
                doc.id: "Dear Alice Smith, please review Beta Corp quarterly filings."
            },
        )
        detector = EntityRoleRelationshipDetector()
        rels = detector.detect(ctx)

        cooccur = [r for r in rels if r.relationship_type == RelationshipType.REPRESENTS]
        assert len(cooccur) == 1
        assert cooccur[0].status == RelationshipStatus.UNRESOLVED
        assert cooccur[0].score == 0.25
        assert (
            "Name co-occurrence alone does not establish representation"
            in cooccur[0].status_rationale
        )

    def test_duplicate_document_hash_equality_detection(self) -> None:
        """Requirement: SHA-256 digest equality establishes BYTE_IDENTICAL DUPLICATE_OF, not 'hash collision'."""
        case_id = generate_id()
        doc_a = _make_dummy_doc(case_id, "contract_v1.pdf", sha256="1" * 64)
        doc_b = _make_dummy_doc(case_id, "contract_copy.pdf", sha256="1" * 64)
        doc_c = _make_dummy_doc(case_id, "different_doc.pdf", sha256="2" * 64)

        ctx = DetectionContext(
            case_id=case_id,
            detection_run_id=generate_id(),
            documents=[doc_a, doc_b, doc_c],
        )
        detector = DocumentRelationshipDetector()
        rels = detector.detect(ctx)

        dup_rels = [r for r in rels if r.relationship_type == RelationshipType.DUPLICATE_OF]
        assert len(dup_rels) == 1
        rel = dup_rels[0]
        assert rel.status == RelationshipStatus.CONFIRMED
        assert rel.score == 1.0
        assert rel.source_id == doc_b.id
        assert rel.target_id == doc_a.id
        assert rel.duplicate_kind == DuplicateKind.BYTE_IDENTICAL
        assert rel.detection_method == RelationshipDetectionMethod.DOCUMENT_HASH_EQUALITY
        # Verified: No misleading terminology 'collision'
        assert "collision" not in rel.status_rationale.lower()
        for signal in rel.evidence.matching_signals:
            assert "collision" not in signal.lower()

    def test_explicit_amendment_reference(self) -> None:
        case_id = generate_id()
        doc_orig = _make_dummy_doc(case_id, "agreement_original.pdf")
        doc_amend = _make_dummy_doc(case_id, "agreement_amendment_1.pdf")

        ctx = DetectionContext(
            case_id=case_id,
            detection_run_id=generate_id(),
            documents=[doc_orig, doc_amend],
            raw_document_texts={
                doc_amend.id: "FIRST AMENDMENT TO agreement_original.pdf\nTerms amended."
            },
        )
        detector = DocumentRelationshipDetector()
        rels = detector.detect(ctx)

        amend_rels = [r for r in rels if r.relationship_type == RelationshipType.AMENDS_DOCUMENT]
        assert len(amend_rels) == 1
        assert amend_rels[0].status == RelationshipStatus.CONFIRMED
        assert amend_rels[0].source_id == doc_amend.id
        assert amend_rels[0].target_id == doc_orig.id


class TestEntityResolutionIntegrationAndSafeguards:
    """Test suite verifying that entity-resolution findings correctly guard relationships."""

    def test_conflicting_tax_id_suppresses_relationship(self) -> None:
        case_id = generate_id()
        doc = _make_dummy_doc(case_id, "invoice.pdf")
        sup = ExtractedFieldValue(
            field_key="supplier_name",
            label="Supplier",
            normalized_value="Contoso Supplies",
            data_type=FieldDataType.STRING,
            source_document_id=doc.id,
            source_page_number=1,
        )

        conflict_match = EntityCandidateMatch(
            case_id=case_id,
            processing_run_id="run_er",
            entity_type=ResolvedEntityType.ORGANIZATION,
            target_mention_id="m1",
            candidate_mention_id="m2",
            target_value_display="Contoso Supplies (EIN 11-1111111)",
            candidate_value_display="Contoso Supplies (EIN 22-2222222)",
            matching_method=EntityMatchingMethod.CONTRADICTION_DETECTED,
            match_classification=EntityMatchClassification.CONFLICTING_IDENTITY,
            match_score=0.0,
            score_semantics="rule_ranking_score",
            decision_status=MatchDecisionStatus.ALGORITHMIC_CANDIDATE,
            evidence=EntityMatchEvidence(
                target_mention_id="m1",
                candidate_mention_id="m2",
                target_document_id="d1",
                candidate_document_id="d2",
                target_page_number=1,
                candidate_page_number=1,
                target_field_key="supplier_name",
                candidate_field_key="supplier_name",
                contradicting_signals=["Conflicting tax identifiers"],
            ),
        )

        ctx = DetectionContext(
            case_id=case_id,
            detection_run_id=generate_id(),
            documents=[doc],
            extracted_fields_by_doc={doc.id: [sup]},
            candidate_matches=[conflict_match],
        )

        engine = RelationshipDetectionEngine()
        result = engine.detect_relationships(ctx)

        rels = [r for r in result.relationships if r.relationship_type == RelationshipType.ISSUED]
        assert len(rels) == 1
        assert rels[0].status == RelationshipStatus.CONTRADICTED
        assert rels[0].score == 0.0

    def test_human_rejected_entity_match_suppresses_relationship(self) -> None:
        case_id = generate_id()
        doc = _make_dummy_doc(case_id, "invoice.pdf")
        sup = ExtractedFieldValue(
            field_key="supplier_name",
            label="Supplier",
            normalized_value="Globex Corp",
            data_type=FieldDataType.STRING,
            source_document_id=doc.id,
            source_page_number=1,
        )

        rejected_match = EntityCandidateMatch(
            case_id=case_id,
            processing_run_id="run_er",
            entity_type=ResolvedEntityType.ORGANIZATION,
            target_mention_id="m1",
            candidate_mention_id="m2",
            target_value_display="Globex Corp",
            candidate_value_display="Globex Inc",
            matching_method=EntityMatchingMethod.ORGANIZATION_NAME_SIMILARITY,
            match_classification=EntityMatchClassification.STRONG_CANDIDATE,
            match_score=0.90,
            score_semantics="rule_ranking_score",
            decision_status=MatchDecisionStatus.REJECTED,
            evidence=EntityMatchEvidence(
                target_mention_id="m1",
                candidate_mention_id="m2",
                target_document_id="d1",
                candidate_document_id="d2",
                target_page_number=1,
                candidate_page_number=1,
                target_field_key="supplier_name",
                candidate_field_key="supplier_name",
            ),
        )

        ctx = DetectionContext(
            case_id=case_id,
            detection_run_id=generate_id(),
            documents=[doc],
            extracted_fields_by_doc={doc.id: [sup]},
            candidate_matches=[rejected_match],
        )

        engine = RelationshipDetectionEngine()
        result = engine.detect_relationships(ctx)

        rels = [r for r in result.relationships if r.relationship_type == RelationshipType.ISSUED]
        assert len(rels) == 1
        assert rels[0].status == RelationshipStatus.REJECTED
        assert rels[0].score == 0.0
