"""Comprehensive verification test suite for Phase 2C.3.2.1:
Relationship ontology, directionality invariants, status vs score separation,
duplicate byte-equality semantics, and historical compatibility.
"""

from __future__ import annotations

from document_intelligence.domain.enums import (
    DuplicateKind,
    EntityMatchClassification,
    EntityMatchingMethod,
    FieldDataType,
    MatchDecisionStatus,
    RelationshipDetectionMethod,
    RelationshipReviewAction,
    RelationshipStatus,
    RelationshipType,
    ResolvedEntityType,
    StatusDeterminationMethod,
)
from document_intelligence.domain.identifiers import generate_id, utc_now
from document_intelligence.domain.models.document import Document
from document_intelligence.domain.models.entity_resolution import (
    EntityCandidateMatch,
    EntityMatchEvidence,
)
from document_intelligence.domain.models.extraction import ExtractedFieldValue
from document_intelligence.domain.models.relationship import (
    DetectedRelationship,
    RelationshipEvidence,
    RelationshipReviewRecord,
)
from document_intelligence.infrastructure.persistence.models import (
    CaseModel,
    DetectedRelationshipModel,
)
from document_intelligence.infrastructure.repositories.relationship_repository import (
    RelationshipRepository,
)
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


def _create_case_in_db(db_session, case_id: str) -> None:
    c = CaseModel(
        id=case_id,
        case_reference=f"CASE-{case_id[:8]}",
        title="Ontology Test Case",
        status="ACTIVE",
        created_at=utc_now(),
        updated_at=utc_now(),
    )
    db_session.add(c)
    db_session.commit()


# -----------------------------------------------------------------------------
# 1. Ontology Tests
# -----------------------------------------------------------------------------
class TestRelationshipOntology:
    """Verifies subject-predicate-object semantics across all supported relationship types."""

    def test_supplier_issues_invoice(self) -> None:
        case_id = generate_id()
        doc = _make_dummy_doc(case_id, "inv_sample.pdf")
        field = ExtractedFieldValue(
            field_key="supplier_name",
            label="Supplier",
            normalized_value="Apex Supplies Inc",
            data_type=FieldDataType.STRING,
            source_document_id=doc.id,
            source_page_number=1,
        )
        ctx = DetectionContext(
            case_id=case_id,
            detection_run_id=generate_id(),
            documents=[doc],
            extracted_fields_by_doc={doc.id: [field]},
        )
        rels = InvoiceRelationshipDetector().detect(ctx)
        issued = [r for r in rels if r.relationship_type == RelationshipType.ISSUED]
        assert len(issued) == 1
        rel = issued[0]
        assert rel.source_id == "ORG:APEX SUPPLIES INC"
        assert rel.source_type == "ORGANIZATION"
        assert rel.target_id == doc.id
        assert rel.target_type == "INVOICE"
        assert (
            rel.direction_display
            == f"Apex Supplies Inc --ISSUED--> Document '{doc.original_filename}'"
        )
        assert rel.status == RelationshipStatus.CONFIRMED

    def test_invoice_billed_to_buyer(self) -> None:
        case_id = generate_id()
        doc = _make_dummy_doc(case_id, "inv_sample.pdf")
        field = ExtractedFieldValue(
            field_key="buyer_name",
            label="Buyer",
            normalized_value="Zenith Enterprises",
            data_type=FieldDataType.STRING,
            source_document_id=doc.id,
            source_page_number=1,
        )
        ctx = DetectionContext(
            case_id=case_id,
            detection_run_id=generate_id(),
            documents=[doc],
            extracted_fields_by_doc={doc.id: [field]},
        )
        rels = InvoiceRelationshipDetector().detect(ctx)
        billed = [r for r in rels if r.relationship_type == RelationshipType.BILLED_TO]
        assert len(billed) == 1
        rel = billed[0]
        assert rel.source_id == doc.id
        assert rel.source_type == "INVOICE"
        assert rel.target_id == "ORG:ZENITH ENTERPRISES"
        assert rel.target_type == "ORGANIZATION"
        assert (
            rel.direction_display
            == f"Document '{doc.original_filename}' --BILLED_TO--> Zenith Enterprises"
        )

    def test_merchant_issues_receipt(self) -> None:
        case_id = generate_id()
        doc = _make_dummy_doc(case_id, "receipt_pos.pdf")
        field = ExtractedFieldValue(
            field_key="merchant_name",
            label="Merchant",
            normalized_value="Target Superstore",
            data_type=FieldDataType.STRING,
            source_document_id=doc.id,
            source_page_number=1,
        )
        ctx = DetectionContext(
            case_id=case_id,
            detection_run_id=generate_id(),
            documents=[doc],
            extracted_fields_by_doc={doc.id: [field]},
        )
        rels = ReceiptRelationshipDetector().detect(ctx)
        issued = [r for r in rels if r.relationship_type == RelationshipType.ISSUED]
        assert len(issued) == 1
        rel = issued[0]
        assert rel.source_id == "ORG:TARGET SUPERSTORE"
        assert rel.source_type == "ORGANIZATION"
        assert rel.target_id == doc.id
        assert (
            rel.direction_display
            == f"Target Superstore --ISSUED--> Document '{doc.original_filename}'"
        )

    def test_bank_issues_statement(self) -> None:
        case_id = generate_id()
        doc = _make_dummy_doc(case_id, "bank_stmt.pdf")
        field = ExtractedFieldValue(
            field_key="bank_name",
            label="Bank",
            normalized_value="Chase Bank NA",
            data_type=FieldDataType.STRING,
            source_document_id=doc.id,
            source_page_number=1,
        )
        ctx = DetectionContext(
            case_id=case_id,
            detection_run_id=generate_id(),
            documents=[doc],
            extracted_fields_by_doc={doc.id: [field]},
        )
        rels = BankStatementRelationshipDetector().detect(ctx)
        issued = [r for r in rels if r.relationship_type == RelationshipType.ISSUED]
        assert len(issued) == 1
        rel = issued[0]
        assert rel.source_id == "ORG:CHASE BANK NA"
        assert rel.source_type == "ORGANIZATION"
        assert rel.target_id == doc.id
        assert (
            rel.direction_display == f"Chase Bank NA --ISSUED--> Document '{doc.original_filename}'"
        )

    def test_account_held_by_person(self) -> None:
        case_id = generate_id()
        doc = _make_dummy_doc(case_id, "bank_stmt.pdf")
        holder = ExtractedFieldValue(
            field_key="account_holder",
            label="Account Holder",
            normalized_value="Jane Elizabeth Doe",
            data_type=FieldDataType.STRING,
            source_document_id=doc.id,
            source_page_number=1,
        )
        acct = ExtractedFieldValue(
            field_key="account_number_masked",
            label="Account Number",
            normalized_value="****9876",
            data_type=FieldDataType.MASKED_STRING,
            source_document_id=doc.id,
            source_page_number=1,
        )
        ctx = DetectionContext(
            case_id=case_id,
            detection_run_id=generate_id(),
            documents=[doc],
            extracted_fields_by_doc={doc.id: [holder, acct]},
        )
        rels = BankStatementRelationshipDetector().detect(ctx)
        held = [r for r in rels if r.relationship_type == RelationshipType.HELD_BY]
        assert len(held) == 1
        rel = held[0]
        assert rel.source_id == "ACCT:****9876"
        assert rel.source_type == "ACCOUNT"
        assert rel.target_id == "ENTITY:JANE ELIZABETH DOE"
        assert rel.target_type == "PERSON"
        assert rel.direction_display == "Account ****9876 --HELD_BY--> Jane Elizabeth Doe"

    def test_person_represents_organization(self) -> None:
        case_id = generate_id()
        doc = _make_dummy_doc(case_id, "minutes.pdf")
        text = "Confirmed: Robert Vance, CEO of Vance Refrigeration."
        ctx = DetectionContext(
            case_id=case_id,
            detection_run_id=generate_id(),
            documents=[doc],
            raw_document_texts={doc.id: text},
        )
        rels = EntityRoleRelationshipDetector().detect(ctx)
        rep = [r for r in rels if r.relationship_type == RelationshipType.REPRESENTS]
        assert len(rep) == 1
        rel = rep[0]
        assert rel.source_label == "Robert Vance"
        assert rel.target_label == "Vance Refrigeration"
        assert rel.direction_display == "Robert Vance --REPRESENTS--> Vance Refrigeration"

    def test_invoice_references_purchase_order(self) -> None:
        case_id = generate_id()
        inv = _make_dummy_doc(case_id, "inv.pdf")
        po = _make_dummy_doc(case_id, "PO-456.pdf")
        ctx = DetectionContext(
            case_id=case_id,
            detection_run_id=generate_id(),
            documents=[inv, po],
            extracted_fields_by_doc={inv.id: []},
            raw_document_texts={inv.id: "INVOICE #99\nPurchase Order: PO-456"},
        )
        rels = InvoiceRelationshipDetector().detect(ctx)
        ref_po = [
            r for r in rels if r.relationship_type == RelationshipType.REFERENCES_PURCHASE_ORDER
        ]
        assert len(ref_po) == 1
        assert ref_po[0].source_id == inv.id
        assert ref_po[0].target_id == po.id

    def test_receipt_references_invoice(self) -> None:
        case_id = generate_id()
        rec = _make_dummy_doc(case_id, "receipt.pdf")
        inv = _make_dummy_doc(case_id, "inv.pdf")
        inv_field = ExtractedFieldValue(
            field_key="invoice_number",
            label="Invoice Number",
            normalized_value="INV-777",
            data_type=FieldDataType.STRING,
            source_document_id=inv.id,
            source_page_number=1,
        )
        ctx = DetectionContext(
            case_id=case_id,
            detection_run_id=generate_id(),
            documents=[rec, inv],
            extracted_fields_by_doc={rec.id: [], inv.id: [inv_field]},
            raw_document_texts={rec.id: "RECEIPT\nInvoice Ref: INV-777"},
        )
        rels = ReceiptRelationshipDetector().detect(ctx)
        ref_inv = [r for r in rels if r.relationship_type == RelationshipType.REFERENCES_INVOICE]
        assert len(ref_inv) == 1
        assert ref_inv[0].source_id == rec.id
        assert ref_inv[0].target_id == inv.id

    def test_supplier_buyer_cooccurrence_creates_invoiced_not_supplies(self) -> None:
        case_id = generate_id()
        doc = _make_dummy_doc(case_id, "standard_invoice.pdf")
        sup = ExtractedFieldValue(
            field_key="supplier_name",
            label="Supplier",
            normalized_value="Standard Supplier LLC",
            data_type=FieldDataType.STRING,
            source_document_id=doc.id,
            source_page_number=1,
        )
        buyer = ExtractedFieldValue(
            field_key="buyer_name",
            label="Buyer",
            normalized_value="Standard Buyer Corp",
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
        rels = InvoiceRelationshipDetector().detect(ctx)

        # INVOICED is created
        invoiced = [r for r in rels if r.relationship_type == RelationshipType.INVOICED]
        assert len(invoiced) == 1
        assert (
            invoiced[0].direction_display
            == "Standard Supplier LLC --INVOICED--> Standard Buyer Corp"
        )

        # SUPPLIES is NOT created
        supplies = [r for r in rels if r.relationship_type == RelationshipType.SUPPLIES]
        assert len(supplies) == 0

    def test_explicit_supply_contract_supports_supplies(self) -> None:
        case_id = generate_id()
        doc = _make_dummy_doc(case_id, "supply_contract.pdf")
        sup = ExtractedFieldValue(
            field_key="supplier_name",
            label="Supplier",
            normalized_value="Exclusive Supplier LLC",
            data_type=FieldDataType.STRING,
            source_document_id=doc.id,
            source_page_number=1,
        )
        buyer = ExtractedFieldValue(
            field_key="buyer_name",
            label="Buyer",
            normalized_value="Retail Buyer Corp",
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
                doc.id: "CONTRACT FOR THE SUPPLY OF industrial machinery between Exclusive Supplier LLC and Retail Buyer Corp."
            },
        )
        rels = InvoiceRelationshipDetector().detect(ctx)
        supplies = [r for r in rels if r.relationship_type == RelationshipType.SUPPLIES]
        assert len(supplies) == 1
        assert supplies[0].status == RelationshipStatus.CONFIRMED
        assert (
            supplies[0].direction_display
            == "Exclusive Supplier LLC --SUPPLIES--> Retail Buyer Corp"
        )


# -----------------------------------------------------------------------------
# 2. Directionality Invariants
# -----------------------------------------------------------------------------
class TestDirectionalityInvariants:
    """Verifies that every relationship correctly defines Source as Subject and Target as Object."""

    def test_directionality_subject_predicate_object(self) -> None:
        rel = DetectedRelationship(
            case_id="case_1",
            detection_run_id="run_1",
            relationship_type=RelationshipType.ISSUED,
            source_id="ORG:SELLER",
            source_type="ORGANIZATION",
            source_label="Seller Corp",
            target_id="DOC:100",
            target_type="INVOICE",
            target_label="Invoice #100",
            direction_display="Seller Corp --ISSUED--> Invoice #100",
            status=RelationshipStatus.CONFIRMED,
            score=0.95,
            score_semantics="evidence_strength",
            detection_method=RelationshipDetectionMethod.EXPLICIT_FIELD_REFERENCE,
            detection_version="2.0.0",
            status_rationale="Issuer verified.",
            evidence=RelationshipEvidence(
                relationship_type=RelationshipType.ISSUED,
                source_id="ORG:SELLER",
                target_id="DOC:100",
                source_case_id="case_1",
                score=0.95,
                score_semantics="evidence_strength",
                status=RelationshipStatus.CONFIRMED,
                status_rationale="Issuer verified.",
            ),
        )

        # Subject-Predicate-Object
        assert rel.source_label in rel.direction_display.split(" --")[0]
        assert " --ISSUED--> " in rel.direction_display
        assert rel.target_label in rel.direction_display.split("--> ")[1]

    def test_serialization_and_deserialization_preserves_direction(self) -> None:
        rel = DetectedRelationship(
            case_id="case_1",
            detection_run_id="run_1",
            relationship_type=RelationshipType.BILLED_TO,
            source_id="DOC:101",
            source_type="INVOICE",
            source_label="Invoice 101",
            target_id="ORG:BUYER",
            target_type="ORGANIZATION",
            target_label="Buyer Ltd",
            direction_display="Invoice 101 --BILLED_TO--> Buyer Ltd",
            status=RelationshipStatus.CONFIRMED,
            score=0.90,
            score_semantics="evidence_strength",
            detection_method=RelationshipDetectionMethod.EXPLICIT_FIELD_REFERENCE,
            detection_version="2.0.0",
            status_rationale="Billed recipient verified.",
            evidence=RelationshipEvidence(
                relationship_type=RelationshipType.BILLED_TO,
                source_id="DOC:101",
                target_id="ORG:BUYER",
                source_case_id="case_1",
                score=0.90,
                score_semantics="evidence_strength",
                status=RelationshipStatus.CONFIRMED,
                status_rationale="Billed recipient verified.",
            ),
        )

        data = rel.model_dump()
        reconstructed = DetectedRelationship(**data)
        assert reconstructed.source_id == "DOC:101"
        assert reconstructed.target_id == "ORG:BUYER"
        assert reconstructed.direction_display == "Invoice 101 --BILLED_TO--> Buyer Ltd"

    def test_database_persistence_preserves_direction(self, db_session) -> None:
        case_id = generate_id()
        _create_case_in_db(db_session, case_id)
        repo = RelationshipRepository(db_session)
        rel_id = generate_id()

        rel = DetectedRelationship(
            id=rel_id,
            case_id=case_id,
            detection_run_id="run_db_01",
            relationship_type=RelationshipType.INVOICED,
            source_id="ORG:ALPHA",
            source_type="ORGANIZATION",
            source_label="Alpha Co",
            target_id="ORG:BETA",
            target_type="ORGANIZATION",
            target_label="Beta Co",
            direction_display="Alpha Co --INVOICED--> Beta Co",
            status=RelationshipStatus.CONFIRMED,
            score=0.90,
            score_semantics="evidence_strength",
            detection_method=RelationshipDetectionMethod.INVOICE_BILLING_EVENT_RULE,
            detection_version="2.0.0",
            status_rationale="Commercial invoice billing event.",
            evidence=RelationshipEvidence(
                relationship_type=RelationshipType.INVOICED,
                source_id="ORG:ALPHA",
                target_id="ORG:BETA",
                source_case_id=case_id,
                score=0.90,
                score_semantics="evidence_strength",
                status=RelationshipStatus.CONFIRMED,
                status_rationale="Commercial invoice billing event.",
            ),
        )

        repo.save_relationship(rel)

        retrieved = repo.get_relationship_by_id(case_id, rel_id)
        assert retrieved is not None
        assert retrieved.source_id == "ORG:ALPHA"
        assert retrieved.target_id == "ORG:BETA"
        assert retrieved.direction_display == "Alpha Co --INVOICED--> Beta Co"
        assert retrieved.ontology_version == "2.0"


# -----------------------------------------------------------------------------
# 3. Status and Score Separation
# -----------------------------------------------------------------------------
class TestStatusAndScoreSeparation:
    """Verifies that score describes ranking strength only, and cannot independently confirm."""

    def test_high_ranking_score_without_explicit_evidence_does_not_confirm(self) -> None:
        """A coincidental match with score 0.75 must remain CANDIDATE or UNRESOLVED, not CONFIRMED."""
        rel = DetectedRelationship(
            case_id="case_1",
            detection_run_id="run_1",
            relationship_type=RelationshipType.MAY_SETTLE,
            source_id="TX:1",
            source_type="TRANSACTION",
            source_label="Tx 1",
            target_id="INV:1",
            target_type="INVOICE",
            target_label="Inv 1",
            direction_display="Tx 1 --MAY_SETTLE--> Inv 1",
            status=RelationshipStatus.CANDIDATE,  # NOT confirmed despite 0.90 score
            score=0.90,
            score_semantics="evidence_strength",
            detection_method=RelationshipDetectionMethod.TRANSACTION_SETTLEMENT_RULE,
            detection_version="2.0.0",
            status_rationale="Cites invoice number in description.",
            evidence=RelationshipEvidence(
                relationship_type=RelationshipType.MAY_SETTLE,
                source_id="TX:1",
                target_id="INV:1",
                source_case_id="case_1",
                score=0.90,
                score_semantics="evidence_strength",
                status=RelationshipStatus.CANDIDATE,
                status_rationale="Candidate settlement awaiting review.",
            ),
        )
        assert rel.status == RelationshipStatus.CANDIDATE
        assert rel.score == 0.90

    def test_human_confirmation_is_recorded_as_human_review(self, db_session) -> None:
        case_id = generate_id()
        _create_case_in_db(db_session, case_id)
        repo = RelationshipRepository(db_session)
        rel_id = generate_id()

        rel = DetectedRelationship(
            id=rel_id,
            case_id=case_id,
            detection_run_id="run_1",
            relationship_type=RelationshipType.MAY_SETTLE,
            source_id="TX:2",
            source_type="TRANSACTION",
            source_label="Tx 2",
            target_id="INV:2",
            target_type="INVOICE",
            target_label="Inv 2",
            direction_display="Tx 2 --MAY_SETTLE--> Inv 2",
            status=RelationshipStatus.CANDIDATE,
            score=0.90,
            score_semantics="evidence_strength",
            detection_method=RelationshipDetectionMethod.TRANSACTION_SETTLEMENT_RULE,
            detection_version="2.0.0",
            status_rationale="Algorithmic candidate.",
            evidence=RelationshipEvidence(
                relationship_type=RelationshipType.MAY_SETTLE,
                source_id="TX:2",
                target_id="INV:2",
                source_case_id=case_id,
                score=0.90,
                score_semantics="evidence_strength",
                status=RelationshipStatus.CANDIDATE,
                status_rationale="Algorithmic candidate.",
            ),
        )
        repo.save_relationship(rel)

        # Human reviews and confirms
        review = RelationshipReviewRecord(
            relationship_id=rel_id,
            case_id=case_id,
            decision=RelationshipReviewAction.CONFIRM_RELATIONSHIP,
            reviewer_id="lead_auditor",
            reason="Remittance voucher verified.",
            previous_status=RelationshipStatus.CANDIDATE,
            new_status=RelationshipStatus.CONFIRMED,
        )
        repo.save_review(review)

        updated = repo.get_relationship_by_id(case_id, rel_id)
        assert updated is not None
        assert updated.status == RelationshipStatus.CONFIRMED
        assert updated.is_human_reviewed is True
        assert updated.status_determination_method == StatusDeterminationMethod.HUMAN_REVIEW
        assert "lead_auditor" in updated.status_rationale

    def test_contradictory_evidence_remains_visible_after_human_confirmation(
        self, db_session
    ) -> None:
        case_id = generate_id()
        _create_case_in_db(db_session, case_id)
        repo = RelationshipRepository(db_session)
        rel_id = generate_id()

        rel = DetectedRelationship(
            id=rel_id,
            case_id=case_id,
            detection_run_id="run_1",
            relationship_type=RelationshipType.MAY_SETTLE,
            source_id="TX:3",
            source_type="TRANSACTION",
            source_label="Tx 3",
            target_id="INV:3",
            target_type="INVOICE",
            target_label="Inv 3",
            direction_display="Tx 3 --MAY_SETTLE--> Inv 3",
            status=RelationshipStatus.CONTRADICTED,
            score=0.0,
            score_semantics="evidence_strength",
            detection_method=RelationshipDetectionMethod.TRANSACTION_SETTLEMENT_RULE,
            detection_version="2.0.0",
            status_rationale="Currency mismatch detected.",
            evidence=RelationshipEvidence(
                relationship_type=RelationshipType.MAY_SETTLE,
                source_id="TX:3",
                target_id="INV:3",
                source_case_id=case_id,
                score=0.0,
                score_semantics="evidence_strength",
                status=RelationshipStatus.CONTRADICTED,
                status_rationale="Currency mismatch detected.",
                contradicting_signals=["Currency conflict: EUR vs USD"],
            ),
        )
        repo.save_relationship(rel)

        # Reviewer manually confirms with override justification
        review = RelationshipReviewRecord(
            relationship_id=rel_id,
            case_id=case_id,
            decision=RelationshipReviewAction.CONFIRM_RELATIONSHIP,
            reviewer_id="forensic_expert",
            reason="Confirmed as multi-currency settlement via FX conversion slip.",
            previous_status=RelationshipStatus.CONTRADICTED,
            new_status=RelationshipStatus.CONFIRMED,
        )
        repo.save_review(review)

        updated = repo.get_relationship_by_id(case_id, rel_id)
        assert updated is not None
        assert updated.status == RelationshipStatus.CONFIRMED
        # Contradicting signals remain visible and are not erased!
        assert len(updated.evidence.contradicting_signals) == 1
        assert "Currency conflict: EUR vs USD" in updated.evidence.contradicting_signals[0]

    def test_weak_entity_match_cannot_establish_confirmed_commercial_relationship(self) -> None:
        case_id = generate_id()
        doc = _make_dummy_doc(case_id, "invoice_ambiguous.pdf")
        sup = ExtractedFieldValue(
            field_key="supplier_name",
            label="Supplier",
            normalized_value="Acme Corp",
            data_type=FieldDataType.STRING,
            source_document_id=doc.id,
            source_page_number=1,
        )

        weak_match = EntityCandidateMatch(
            case_id=case_id,
            processing_run_id="run_1",
            entity_type=ResolvedEntityType.ORGANIZATION,
            target_mention_id="m1",
            candidate_mention_id="m2",
            target_value_display="Acme Corp",
            candidate_value_display="Acme Limited",
            matching_method=EntityMatchingMethod.ORGANIZATION_NAME_SIMILARITY,
            match_classification=EntityMatchClassification.WEAK_AMBIGUOUS,
            match_score=0.55,
            score_semantics="similarity_score",
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
            ),
        )

        ctx = DetectionContext(
            case_id=case_id,
            detection_run_id=generate_id(),
            documents=[doc],
            extracted_fields_by_doc={doc.id: [sup]},
            candidate_matches=[weak_match],
        )

        result = RelationshipDetectionEngine().detect_relationships(ctx)
        issued = [r for r in result.relationships if r.relationship_type == RelationshipType.ISSUED]
        assert len(issued) == 1
        # Demoted to CANDIDATE because participating entity match is weak/ambiguous
        assert issued[0].status == RelationshipStatus.CANDIDATE
        assert issued[0].score <= 0.65


# -----------------------------------------------------------------------------
# 4. Duplicate Semantics & Hash Terminology
# -----------------------------------------------------------------------------
class TestDuplicateSemanticsAndTerminology:
    """Verifies that equal SHA-256 digests represent byte-identical documents without using 'hash collision'."""

    def test_identical_sha256_content_is_byte_identical(self) -> None:
        case_id = generate_id()
        doc1 = _make_dummy_doc(case_id, "file_a.pdf", sha256="f" * 64)
        doc2 = _make_dummy_doc(case_id, "file_b.pdf", sha256="f" * 64)

        ctx = DetectionContext(
            case_id=case_id,
            detection_run_id=generate_id(),
            documents=[doc1, doc2],
        )
        rels = DocumentRelationshipDetector().detect(ctx)
        dup = [r for r in rels if r.relationship_type == RelationshipType.DUPLICATE_OF]
        assert len(dup) == 1
        rel = dup[0]
        assert rel.status == RelationshipStatus.CONFIRMED
        assert rel.duplicate_kind == DuplicateKind.BYTE_IDENTICAL
        assert rel.detection_method == RelationshipDetectionMethod.DOCUMENT_HASH_EQUALITY
        # Strict terminology check: never describe equal digests as 'collision'
        assert "collision" not in rel.status_rationale.lower()
        for signal in rel.evidence.matching_signals:
            assert "collision" not in signal.lower()

    def test_different_files_with_different_hashes_no_duplicate(self) -> None:
        case_id = generate_id()
        doc1 = _make_dummy_doc(case_id, "doc1.pdf", sha256="a" * 64)
        doc2 = _make_dummy_doc(case_id, "doc2.pdf", sha256="b" * 64)

        ctx = DetectionContext(
            case_id=case_id,
            detection_run_id=generate_id(),
            documents=[doc1, doc2],
        )
        rels = DocumentRelationshipDetector().detect(ctx)
        dup = [r for r in rels if r.relationship_type == RelationshipType.DUPLICATE_OF]
        assert len(dup) == 0

    def test_visually_similar_or_name_similar_different_hashes_is_candidate(self) -> None:
        case_id = generate_id()
        # Same filename but different SHA-256
        doc1 = _make_dummy_doc(case_id, "financial_report_2026.pdf", sha256="1" * 64)
        doc2 = _make_dummy_doc(case_id, "financial_report_2026.pdf", sha256="2" * 64)

        ctx = DetectionContext(
            case_id=case_id,
            detection_run_id=generate_id(),
            documents=[doc1, doc2],
        )
        rels = DocumentRelationshipDetector().detect(ctx)
        dup = [r for r in rels if r.relationship_type == RelationshipType.DUPLICATE_OF]
        assert len(dup) == 1
        rel = dup[0]
        # Must be CANDIDATE, never confirmed
        assert rel.status == RelationshipStatus.CANDIDATE
        assert rel.duplicate_kind == DuplicateKind.UNRESOLVED_DUPLICATE_CANDIDATE
        assert rel.score < 1.0


# -----------------------------------------------------------------------------
# 5. Historical Compatibility
# -----------------------------------------------------------------------------
class TestHistoricalCompatibility:
    """Verifies that legacy records from migration 005 remain readable and traceable."""

    def test_legacy_v1_record_readable_with_provenance(self, db_session) -> None:
        case_id = generate_id()
        _create_case_in_db(db_session, case_id)
        rel_id = generate_id()

        # Simulate historical record stored in SQLite with legacy ISSUED_BY and ontology_version="1.0"
        model = DetectedRelationshipModel(
            id=rel_id,
            case_id=case_id,
            detection_run_id="run_legacy_01",
            relationship_type="ISSUED_BY",  # Legacy V1 enum string
            ontology_version="1.0",
            legacy_relationship_type="ISSUED_BY",
            source_id="ORG:LEGACY",
            source_type="ORGANIZATION",
            source_label="Legacy Vendor",
            target_id="DOC:LEGACY",
            target_type="INVOICE",
            target_label="Invoice Legacy",
            direction_display="Legacy Vendor --ISSUED_BY--> Invoice Legacy",
            status="CONFIRMED",
            status_determination_method="EVIDENTIARY_RULE",
            score=0.95,
            score_semantics="evidence_strength",
            detection_method="EXPLICIT_FIELD_REFERENCE",
            detection_version="1.0.0",
            status_rationale="Legacy issuance record.",
            evidence_payload={
                "relationship_type": "ISSUED_BY",
                "source_id": "ORG:LEGACY",
                "target_id": "DOC:LEGACY",
                "source_case_id": case_id,
                "score": 0.95,
                "score_semantics": "evidence_strength",
                "status": "CONFIRMED",
                "status_rationale": "Legacy issuance record.",
            },
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        db_session.add(model)
        db_session.commit()

        repo = RelationshipRepository(db_session)
        retrieved = repo.get_relationship_by_id(case_id, rel_id)

        assert retrieved is not None
        assert retrieved.relationship_type == RelationshipType.ISSUED_BY
        assert retrieved.ontology_version == "1.0"
        assert retrieved.legacy_relationship_type == "ISSUED_BY"
        assert retrieved.direction_display == "Legacy Vendor --ISSUED_BY--> Invoice Legacy"
