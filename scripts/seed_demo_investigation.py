"""EVIDEXA Synthetic Investigation Dataset Seeder.

Populates a coherent, realistic, entirely synthetic multi-case digital forensics
and document intelligence scenario for hackathon demonstration.

Idempotent: can be re-run safely at any time to reset demo data.
"""

from __future__ import annotations

import hashlib
import io
import json
import os
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pikepdf
from PIL import Image, ImageDraw, ImageFont
from pikepdf import Array, Dictionary, Name
from sqlalchemy import text
from sqlalchemy.orm import Session

from document_intelligence.core.config import settings
from document_intelligence.domain.enums import (
    CaseStatus,
    DossierStatus,
)
from document_intelligence.domain.identifiers import generate_id, utc_now
from document_intelligence.domain.models.auth import CaseRole, SystemRole
from document_intelligence.infrastructure.persistence.database import SessionLocal
from document_intelligence.infrastructure.persistence.models import (
    AggregatedFindingReviewModel,
    AuditEventModel,
    CaseMembershipModel,
    CaseModel,
    ConsistencyFindingModel,
    ConsistencyReviewModel,
    CrossCaseCandidateMatchModel,
    CrossCaseCandidateReviewModel,
    CrossCaseScopeModel,
    DetectedRelationshipModel,
    DocumentModel,
    EvidenceNodeModel,
    ForensicFindingModel,
    InvestigationDossierModel,
    OrganizationMembershipModel,
    OrganizationModel,
    ProcessingRunModel,
    UserModel,
)
from document_intelligence.modules.auth.password import PasswordService
from document_intelligence.modules.dossier.generator import compute_canonical_content_hash

# Deterministic demo IDs
DEMO_ORG_ID = "org-evidexa-demo"
DEMO_CASE_1_ID = "case-demo-0881"
DEMO_CASE_2_ID = "case-demo-0942"
DEMO_DOC_1_ID = "doc-demo-inv-9001"
DEMO_DOC_2_ID = "doc-demo-rec-4402"
DEMO_DOC_3_ID = "doc-demo-stmt-nov26"
DEMO_DOC_4_ID = "doc-demo-inv-1044"
DEMO_SCOPE_ID = "scope-demo-procurement-logistics"
DEMO_MATCH_ID = "match-demo-acc-9941"
DEMO_DOSSIER_ID = "dossier-demo-0881"


# -----------------------------------------------------------------------------
# PDF Generation Helpers
# -----------------------------------------------------------------------------

def _create_digital_invoice_pdf(path: Path) -> bytes:
    """Create a digital invoice PDF with extractable vector text."""
    pdf = pikepdf.new()
    font = pdf.make_indirect(Dictionary(Type=Name.Font, Subtype=Name.Type1, BaseFont=Name.Helvetica))
    font_bold = pdf.make_indirect(Dictionary(Type=Name.Font, Subtype=Name.Type1, BaseFont=Name.Helvetica_Bold))
    resources = Dictionary(Font=Dictionary(F1=font, F2=font_bold))

    stream_content = (
        b"BT /F2 18 Tf 50 720 Td (TAX INVOICE - APEX TECHNICAL CONSULTING) Tj ET\n"
        b"BT /F1 12 Tf 50 690 Td (Invoice Number: INV-2026-9001) Tj ET\n"
        b"BT /F1 12 Tf 50 670 Td (Date of Issue: November 10, 2026) Tj ET\n"
        b"BT /F1 12 Tf 50 650 Td (Vendor: Apex Technical Consulting Ltd) Tj ET\n"
        b"BT /F1 12 Tf 50 630 Td (Managing Director: Vikram Malhotra) Tj ET\n"
        b"BT /F1 12 Tf 50 610 Td (Registered Office: 12 Nariman Point, Mumbai, MH) Tj ET\n"
        b"BT /F1 12 Tf 50 590 Td (Tax ID / GSTIN: 27AABCT9921M1Z8) Tj ET\n"
        b"BT /F1 12 Tf 50 560 Td (Remittance Account: Axis Bank ACC-9941-02) Tj ET\n"
        b"BT /F1 12 Tf 50 530 Td (Client: Global DataOps Corporation) Tj ET\n"
        b"BT /F1 12 Tf 50 500 Td (Description: Enterprise Data Pipeline & Forensic Audit) Tj ET\n"
        b"BT /F2 14 Tf 50 460 Td (Total Billed Amount: $12,500.00 USD) Tj ET\n"
        b"BT /F1 10 Tf 50 420 Td (Terms: Settlement due within 15 business days) Tj ET\n"
    )

    page = Dictionary(
        Type=Name.Page,
        MediaBox=Array([0, 0, 612, 792]),
        Contents=pdf.make_stream(stream_content),
        Resources=resources,
    )
    pdf.pages.append(pikepdf.Page(page))
    path.parent.mkdir(parents=True, exist_ok=True)
    pdf.save(path, deterministic_id=True)
    return path.read_bytes()


def _create_bilingual_hindi_receipt_pdf(path: Path) -> bytes:
    """Create a bilingual Hindi/English scanned receipt PDF."""
    w, h = 850, 1150
    img = Image.new("RGB", (w, h), color=(250, 248, 242))
    draw = ImageDraw.Draw(img)

    try:
        f_title = ImageFont.truetype("arial.ttf", 28)
        f_body = ImageFont.truetype("arial.ttf", 20)
        f_bold = ImageFont.truetype("arialbd.ttf", 22)
    except Exception:
        f_title = ImageFont.load_default()
        f_body = ImageFont.load_default()
        f_bold = ImageFont.load_default()

    draw.rectangle([(40, 40), (w - 40, h - 40)], outline=(180, 180, 180), width=2)
    draw.text((60, 60), "PAYMENT RECEIPT / bhugtan raseed", fill=(20, 20, 20), font=f_title)
    draw.text((60, 110), "Receipt Voucher: REC-2026-4402", fill=(40, 40, 40), font=f_bold)
    draw.text((60, 150), "Reference Invoice / beejak sandarbh: INV-2026-9001", fill=(40, 40, 40), font=f_body)
    draw.text((60, 190), "Beneficiary / praaptkarta: Apex Bharat Consulting Ltd", fill=(40, 40, 40), font=f_body)
    draw.text((60, 230), "Director: Vikram Malhotra", fill=(40, 40, 40), font=f_body)
    draw.text((60, 270), "Settlement Date / tithi: 2026-11-12", fill=(40, 40, 40), font=f_body)
    draw.text((60, 320), "Total Received / kul rashi: $11,000.00 USD (INR 9,18,500.00)", fill=(10, 10, 10), font=f_bold)
    draw.text((60, 370), "Payment Mode / madhyam: Commercial Wire Transfer", fill=(50, 50, 50), font=f_body)
    draw.text((60, 410), "Destination Account: Axis Bank ACC-9941-02", fill=(50, 50, 50), font=f_body)
    draw.text((60, 470), "Forensic Note: Withholding variance of $1,500 under review", fill=(120, 40, 40), font=f_body)

    # Realistic scan grain
    arr = np.array(img, dtype=np.float32)
    rng = np.random.RandomState(42)
    noise = rng.normal(0, 1.8, arr.shape)
    noisy = np.clip(arr + noise, 0, 255).astype(np.uint8)
    clean_img = Image.fromarray(noisy)

    pdf = pikepdf.new()
    img_byte_arr = io.BytesIO()
    clean_img.save(img_byte_arr, format="JPEG", quality=88)
    img_bytes = img_byte_arr.getvalue()

    image_obj = pdf.make_stream(img_bytes)
    image_obj.Type = Name.XObject
    image_obj.Subtype = Name.Image
    image_obj.Width = w
    image_obj.Height = h
    image_obj.ColorSpace = Name.DeviceRGB
    image_obj.BitsPerComponent = 8
    image_obj.Filter = Name.DCTDecode

    resources = Dictionary(XObject=Dictionary(Im1=image_obj))
    stream_content = f"q {w * 0.72} 0 0 {h * 0.72} 0 0 cm /Im1 Do Q\n".encode()

    page = Dictionary(
        Type=Name.Page,
        MediaBox=Array([0, 0, w * 0.72, h * 0.72]),
        Contents=pdf.make_stream(stream_content),
        Resources=resources,
    )
    pdf.pages.append(pikepdf.Page(page))
    path.parent.mkdir(parents=True, exist_ok=True)
    pdf.save(path, deterministic_id=True)
    return path.read_bytes()


def _create_bank_statement_pdf(path: Path) -> bytes:
    """Create a digital bank statement PDF with wire settlement records."""
    pdf = pikepdf.new()
    font = pdf.make_indirect(Dictionary(Type=Name.Font, Subtype=Name.Type1, BaseFont=Name.Helvetica))
    font_bold = pdf.make_indirect(Dictionary(Type=Name.Font, Subtype=Name.Type1, BaseFont=Name.Helvetica_Bold))
    resources = Dictionary(Font=Dictionary(F1=font, F2=font_bold))

    stream_content = (
        b"BT /F2 18 Tf 50 720 Td (FIRST METROPOLITAN COMMERCIAL BANK) Tj ET\n"
        b"BT /F1 12 Tf 50 690 Td (Commercial Clearing Account: ACC-9941-02) Tj ET\n"
        b"BT /F1 12 Tf 50 670 Td (Statement Window: November 1 to November 30, 2026) Tj ET\n"
        b"BT /F1 12 Tf 50 650 Td (Account Beneficiary: Apex Technical Consulting Ltd) Tj ET\n"
        b"BT /F2 12 Tf 50 610 Td (POSTING DATE     TRANSACTION DETAILS                 AMOUNT) Tj ET\n"
        b"BT /F1 11 Tf 50 580 Td (2026-11-12       WIRE IN - GLOBAL DATAOPS CORP        +$11,000.00 USD) Tj ET\n"
        b"BT /F1 11 Tf 50 550 Td (2026-11-15       INTERNAL TRANSFER TO APEX LOGISTICS  -$8,500.00 USD) Tj ET\n"
        b"BT /F2 12 Tf 50 510 Td (Closing Ledger Balance: $148,500.00 USD) Tj ET\n"
    )

    page = Dictionary(
        Type=Name.Page,
        MediaBox=Array([0, 0, 612, 792]),
        Contents=pdf.make_stream(stream_content),
        Resources=resources,
    )
    pdf.pages.append(pikepdf.Page(page))
    path.parent.mkdir(parents=True, exist_ok=True)
    pdf.save(path, deterministic_id=True)
    return path.read_bytes()


def _create_apex_logistics_invoice_pdf(path: Path) -> bytes:
    """Create a second case invoice from correlated entity Apex Logistics."""
    pdf = pikepdf.new()
    font = pdf.make_indirect(Dictionary(Type=Name.Font, Subtype=Name.Type1, BaseFont=Name.Helvetica))
    font_bold = pdf.make_indirect(Dictionary(Type=Name.Font, Subtype=Name.Type1, BaseFont=Name.Helvetica_Bold))
    resources = Dictionary(Font=Dictionary(F1=font, F2=font_bold))

    stream_content = (
        b"BT /F2 18 Tf 50 720 Td (COMMERCIAL INVOICE - APEX LOGISTICS SOLUTIONS) Tj ET\n"
        b"BT /F1 12 Tf 50 690 Td (Invoice Number: INV-2026-1044) Tj ET\n"
        b"BT /F1 12 Tf 50 670 Td (Invoice Date: November 18, 2026) Tj ET\n"
        b"BT /F1 12 Tf 50 650 Td (Entity: Apex Logistics Solutions Ltd) Tj ET\n"
        b"BT /F1 12 Tf 50 630 Td (Managing Director: Vikram Malhotra) Tj ET\n"
        b"BT /F1 12 Tf 50 610 Td (Registered Office: 44 Cyber City, Gurugram, Haryana) Tj ET\n"
        b"BT /F1 12 Tf 50 590 Td (Tax ID / GSTIN: 06AAACL1044K1ZV) Tj ET\n"
        b"BT /F1 12 Tf 50 560 Td (Settlement Account: Axis Bank ACC-9941-02) Tj ET\n"
        b"BT /F2 14 Tf 50 510 Td (Total Amount Due: $14,200.00 USD) Tj ET\n"
        b"BT /F1 10 Tf 50 470 Td (Logistics Freight & Cross-Dock Routing Services) Tj ET\n"
    )

    page = Dictionary(
        Type=Name.Page,
        MediaBox=Array([0, 0, 612, 792]),
        Contents=pdf.make_stream(stream_content),
        Resources=resources,
    )
    pdf.pages.append(pikepdf.Page(page))
    path.parent.mkdir(parents=True, exist_ok=True)
    pdf.save(path, deterministic_id=True)
    return path.read_bytes()


# -----------------------------------------------------------------------------
# Seeder Implementation
# -----------------------------------------------------------------------------

def seed_demo_data() -> None:
    print("=" * 80)
    print(" EVIDEXA SYNTHETIC INVESTIGATION DATASET SEEDER")
    print(" Populating multi-case forensic scenario for hackathon video recording")
    print("=" * 80)

    db: Session = SessionLocal()
    temp_dir = Path(tempfile.mkdtemp(prefix="evidexa_demo_seed_"))

    try:
        now = utc_now()
        pw_service = PasswordService()

        # 1. Ensure Demo Organization
        org = db.query(OrganizationModel).filter(OrganizationModel.id == DEMO_ORG_ID).first()
        if not org:
            org = OrganizationModel(
                id=DEMO_ORG_ID,
                name="National Financial Crime Investigation Bureau",
                slug="nfcib-forensics",
                created_at=now,
                is_active=True,
            )
            db.add(org)
            db.flush()
            print(f"[+] Created Demo Organization: {org.name} ({org.id})")
        else:
            print(f"[*] Reusing existing Organization: {org.name} ({org.id})")

        # 2. Ensure Examiner User
        user = db.query(UserModel).filter(UserModel.username == "examiner").first()
        if not user:
            user = UserModel(
                id=generate_id(),
                email="examiner@evidexa.local",
                username="examiner",
                full_name="Lead Forensic Examiner",
                hashed_password=pw_service.hash_password("Investigator2026!"),
                system_role=SystemRole.SYSTEM_ADMIN.value,
                is_active=True,
                created_at=now,
                updated_at=now,
            )
            db.add(user)
            db.flush()
            print(f"[+] Created Examiner User: {user.username} ({user.id})")
        else:
            user.system_role = SystemRole.SYSTEM_ADMIN.value
            user.hashed_password = pw_service.hash_password("Investigator2026!")
            user.is_active = True
            db.flush()
            print(f"[*] Reusing existing User: {user.username} ({user.id})")

        # Ensure User is exclusively in Demo Organization
        db.query(OrganizationMembershipModel).filter(
            OrganizationMembershipModel.user_id == user.id,
            OrganizationMembershipModel.organization_id != org.id,
        ).delete()
        om = (
            db.query(OrganizationMembershipModel)
            .filter(
                OrganizationMembershipModel.user_id == user.id,
                OrganizationMembershipModel.organization_id == org.id,
            )
            .first()
        )
        if not om:
            om = OrganizationMembershipModel(
                id=generate_id(),
                user_id=user.id,
                organization_id=org.id,
                role="ADMIN",
                created_at=now,
            )
            db.add(om)
            db.flush()

        # 3. Clean up existing demo data if present (Idempotency)
        print("[*] Cleaning previous demo entities for safe idempotent recreation...")
        db.query(CrossCaseCandidateReviewModel).filter(CrossCaseCandidateReviewModel.scope_id == DEMO_SCOPE_ID).delete()
        db.query(CrossCaseCandidateMatchModel).filter(CrossCaseCandidateMatchModel.scope_id == DEMO_SCOPE_ID).delete()
        db.query(CrossCaseScopeModel).filter(CrossCaseScopeModel.id == DEMO_SCOPE_ID).delete()
        db.query(InvestigationDossierModel).filter(InvestigationDossierModel.id == DEMO_DOSSIER_ID).delete()
        db.query(ConsistencyReviewModel).delete()
        db.query(ConsistencyFindingModel).filter(ConsistencyFindingModel.case_id.in_([DEMO_CASE_1_ID, DEMO_CASE_2_ID])).delete()
        db.query(ForensicFindingModel).filter(ForensicFindingModel.case_id.in_([DEMO_CASE_1_ID, DEMO_CASE_2_ID])).delete()
        db.query(DetectedRelationshipModel).filter(DetectedRelationshipModel.case_id.in_([DEMO_CASE_1_ID, DEMO_CASE_2_ID])).delete()
        db.query(EvidenceNodeModel).filter(EvidenceNodeModel.case_id.in_([DEMO_CASE_1_ID, DEMO_CASE_2_ID])).delete()
        db.query(ProcessingRunModel).filter(ProcessingRunModel.case_id.in_([DEMO_CASE_1_ID, DEMO_CASE_2_ID])).delete()
        db.query(DocumentModel).filter(DocumentModel.case_id.in_([DEMO_CASE_1_ID, DEMO_CASE_2_ID])).delete()
        db.query(CaseMembershipModel).filter(CaseMembershipModel.case_id.in_([DEMO_CASE_1_ID, DEMO_CASE_2_ID])).delete()
        db.query(CaseModel).filter(CaseModel.id.in_([DEMO_CASE_1_ID, DEMO_CASE_2_ID])).delete()
        db.commit()

        # 4. Create Cases
        case1 = CaseModel(
            id=DEMO_CASE_1_ID,
            organization_id=org.id,
            case_reference="CASE-2026-0881",
            title="Operation Northern Star: Procurement Discrepancy",
            description="Forensic investigation into cross-jurisdictional vendor invoicing, $1,500 withholding variance, and bank wire routing.",
            status=CaseStatus.ACTIVE.value,
            created_at=now,
            updated_at=now,
        )
        case2 = CaseModel(
            id=DEMO_CASE_2_ID,
            organization_id=org.id,
            case_reference="CASE-2026-0942",
            title="Operation Apex Logistics: Phoenix Entity Inquiry",
            description="Correlated inquiry into suspected corporate phoenix restructuring utilizing common Axis Bank settlement routing.",
            status=CaseStatus.ACTIVE.value,
            created_at=now,
            updated_at=now,
        )
        db.add_all([case1, case2])
        db.flush()

        # Assign user as ADMIN to both cases
        cm1 = CaseMembershipModel(id=generate_id(), case_id=case1.id, user_id=user.id, role=CaseRole.ADMIN.value, created_at=now)
        cm2 = CaseMembershipModel(id=generate_id(), case_id=case2.id, user_id=user.id, role=CaseRole.ADMIN.value, created_at=now)
        db.add_all([cm1, cm2])
        db.flush()
        print(f"[+] Seeded Case 1: {case1.case_reference} - {case1.title}")
        print(f"[+] Seeded Case 2: {case2.case_reference} - {case2.title}")

        # 5. Generate and Seed Documents
        storage_dir = Path("data/documents")
        storage_dir.mkdir(parents=True, exist_ok=True)
        originals_dir = Path("data/originals")
        originals_dir.mkdir(parents=True, exist_ok=True)

        inv1_path = temp_dir / "INV-2026-9001-APEX.pdf"
        rec1_path = temp_dir / "REC-4402-BILINGUAL-CHALLAN.pdf"
        stmt1_path = temp_dir / "BANK-STMT-METRO-NOV26.pdf"
        inv2_path = temp_dir / "INV-2026-1044-APEX-LOGISTICS.pdf"

        inv1_bytes = _create_digital_invoice_pdf(inv1_path)
        rec1_bytes = _create_bilingual_hindi_receipt_pdf(rec1_path)
        stmt1_bytes = _create_bank_statement_pdf(stmt1_path)
        inv2_bytes = _create_apex_logistics_invoice_pdf(inv2_path)

        def save_doc(doc_id: str, case_id: str, filename: str, content: bytes, doc_type: str) -> DocumentModel:
            sha = hashlib.sha256(content).hexdigest()
            dest_path = storage_dir / f"{doc_id}_{filename}"
            dest_path.write_bytes(content)

            orig_case_dir = originals_dir / case_id
            orig_case_dir.mkdir(parents=True, exist_ok=True)
            orig_file = orig_case_dir / f"{doc_id}.pdf"
            orig_file.write_bytes(content)
            rel_storage_key = f"{case_id}/{doc_id}.pdf"

            d = DocumentModel(
                id=doc_id,
                case_id=case_id,
                original_filename=filename,
                media_type="application/pdf",
                file_extension=".pdf",
                file_size_bytes=len(content),
                sha256=sha,
                storage_key=rel_storage_key,
                page_count=1,
                document_type=doc_type,
                ingestion_status="PROCESSED",
                created_at=now,
                created_by=user.id,
                doc_metadata={"synthetic_demo": True},
            )
            db.add(d)
            db.flush()
            return d

        doc1 = save_doc(DEMO_DOC_1_ID, case1.id, "INV-2026-9001-APEX.pdf", inv1_bytes, "INVOICE")
        doc2 = save_doc(DEMO_DOC_2_ID, case1.id, "REC-4402-BILINGUAL-CHALLAN.pdf", rec1_bytes, "RECEIPT")
        doc3 = save_doc(DEMO_DOC_3_ID, case1.id, "BANK-STMT-METRO-NOV26.pdf", stmt1_bytes, "BANK_STATEMENT")
        doc4 = save_doc(DEMO_DOC_4_ID, case2.id, "INV-2026-1044-APEX-LOGISTICS.pdf", inv2_bytes, "INVOICE")
        print(f"[+] Seeded 4 synthetic PDF documents with cryptographic SHA-256 provenance.")

        # 6. Seed Processing Runs
        run1 = ProcessingRunModel(
            id=generate_id(),
            case_id=case1.id,
            document_ids=[doc1.id, doc2.id],
            pipeline_name="hybrid_ocr_forensics",
            pipeline_version="1.0.0",
            status="SUCCEEDED",
            started_at=now,
            completed_at=now,
            snapshot_sha256=doc1.sha256,
            configuration_snapshot={"languages": ["en", "hi"], "optical_routing": "hybrid"},
            resource_metrics={"duration_ms": 420, "peak_memory_mb": 64},
        )
        db.add(run1)
        db.flush()

        # 7. Seed Unified Evidence Graph Nodes (Case 1)
        node_doc1 = EvidenceNodeModel(
            id=generate_id(),
            case_id=case1.id,
            document_id=doc1.id,
            processing_run_id=run1.id,
            evidence_type="DOCUMENT_PAGE",
            title="Tax Invoice INV-2026-9001",
            description="Original digital invoice from Apex Technical Consulting Ltd",
            source_component="pdf_ingestion",
            source_version="1.0.0",
            raw_value="INV-2026-9001",
            normalized_value="INV-2026-9001",
            confidence=1.0,
            observed_at=now,
        )
        node_doc2 = EvidenceNodeModel(
            id=generate_id(),
            case_id=case1.id,
            document_id=doc2.id,
            processing_run_id=run1.id,
            evidence_type="DOCUMENT_PAGE",
            title="Bilingual Receipt REC-2026-4402",
            description="Bilingual scanned voucher showing $11,000.00 settlement",
            source_component="devanagari_ocr",
            source_version="1.0.0",
            raw_value="REC-2026-4402",
            normalized_value="REC-2026-4402",
            confidence=0.96,
            observed_at=now,
        )
        node_vendor1 = EvidenceNodeModel(
            id=generate_id(),
            case_id=case1.id,
            document_id=doc1.id,
            processing_run_id=run1.id,
            evidence_type="RESOLVED_ENTITY",
            title="Apex Technical Consulting Ltd",
            description="Vendor entity registered in Mumbai, Maharashtra (GSTIN: 27AABCT9921M1Z8)",
            source_component="entity_resolution",
            source_version="1.0.0",
            raw_value="Apex Technical Consulting Ltd",
            normalized_value="APEX TECHNICAL CONSULTING LTD",
            confidence=0.98,
            observed_at=now,
        )
        node_director = EvidenceNodeModel(
            id=generate_id(),
            case_id=case1.id,
            document_id=doc1.id,
            processing_run_id=run1.id,
            evidence_type="RESOLVED_ENTITY",
            title="Vikram Malhotra",
            description="Managing Director and controlling officer",
            source_component="entity_resolution",
            source_version="1.0.0",
            raw_value="Vikram Malhotra",
            normalized_value="VIKRAM MALHOTRA",
            confidence=0.97,
            observed_at=now,
        )
        node_account = EvidenceNodeModel(
            id=generate_id(),
            case_id=case1.id,
            document_id=doc1.id,
            processing_run_id=run1.id,
            evidence_type="RESOLVED_ENTITY",
            title="Axis Bank ACC-9941-02",
            description="Commercial clearing account utilized for wire settlements",
            source_component="entity_resolution",
            source_version="1.0.0",
            raw_value="Axis Bank ACC-9941-02",
            normalized_value="ACC-9941-02",
            confidence=0.99,
            observed_at=now,
        )
        node_buyer = EvidenceNodeModel(
            id=generate_id(),
            case_id=case1.id,
            document_id=doc1.id,
            processing_run_id=run1.id,
            evidence_type="RESOLVED_ENTITY",
            title="Global DataOps Corporation",
            description="Audited purchasing organization",
            source_component="entity_resolution",
            source_version="1.0.0",
            raw_value="Global DataOps Corporation",
            normalized_value="GLOBAL DATAOPS CORPORATION",
            confidence=1.0,
            observed_at=now,
        )
        db.add_all([node_doc1, node_doc2, node_vendor1, node_director, node_account, node_buyer])
        db.flush()

        def make_rel_evidence(rel_type: str, src_id: str, tgt_id: str, case_id: str, method: str = "EXPLICIT_FIELD_REFERENCE", score: float = 0.99) -> dict[str, Any]:
            return {
                "relationship_type": rel_type,
                "ontology_version": "2.0",
                "source_id": src_id,
                "target_id": tgt_id,
                "source_case_id": case_id,
                "score": score,
                "score_semantics": "deterministic_rule_confidence",
                "status": "CONFIRMED",
                "status_determination_method": "EVIDENTIARY_RULE",
                "status_rationale": "Extracted document relationship linked by deterministic evidence rule.",
                "detection_method": method,
                "detection_version": "1.0.0",
                "supporting_evidence_node_ids": [src_id],
                "source_field_keys": [],
                "source_page_references": [1],
                "bounding_boxes": [],
                "matching_signals": ["Deterministic entity match"],
                "contradicting_signals": [],
                "review_history_references": [],
            }

        # Evidence Graph Edges (Case 1)
        rel1 = DetectedRelationshipModel(
            id=generate_id(),
            case_id=case1.id,
            detection_run_id=run1.id,
            relationship_type="ISSUED_BY",
            source_id=node_doc1.id,
            source_type="DOCUMENT",
            source_label="Tax Invoice INV-2026-9001",
            target_id=node_vendor1.id,
            target_type="ORGANIZATION",
            target_label="Apex Technical Consulting Ltd",
            direction_display="->",
            status="CONFIRMED",
            score=0.99,
            score_semantics="deterministic_rule_confidence",
            detection_method="COMMERCIAL_FLOW_RULE",
            detection_version="1.0.0",
            status_rationale="Extracted vendor name in header matches canonical organization record.",
            evidence_payload=make_rel_evidence("ISSUED_BY", node_doc1.id, node_vendor1.id, case1.id, "COMMERCIAL_FLOW_RULE", 0.99),
            created_at=now,
            updated_at=now,
        )
        rel2 = DetectedRelationshipModel(
            id=generate_id(),
            case_id=case1.id,
            detection_run_id=run1.id,
            relationship_type="REPRESENTS",
            source_id=node_director.id,
            source_type="PERSON",
            source_label="Vikram Malhotra",
            target_id=node_vendor1.id,
            target_type="ORGANIZATION",
            target_label="Apex Technical Consulting Ltd",
            direction_display="->",
            status="CONFIRMED",
            score=0.97,
            score_semantics="deterministic_rule_confidence",
            detection_method="ROLE_REPRESENTATION_RULE",
            detection_version="1.0.0",
            status_rationale="Named director in signatory block linked to corporate entity.",
            evidence_payload=make_rel_evidence("REPRESENTS", node_director.id, node_vendor1.id, case1.id, "ROLE_REPRESENTATION_RULE", 0.97),
            created_at=now,
            updated_at=now,
        )
        rel3 = DetectedRelationshipModel(
            id=generate_id(),
            case_id=case1.id,
            detection_run_id=run1.id,
            relationship_type="TRANSFERS_TO",
            source_id=node_vendor1.id,
            source_type="ORGANIZATION",
            source_label="Apex Technical Consulting Ltd",
            target_id=node_account.id,
            target_type="FINANCIAL_ACCOUNT",
            target_label="Axis Bank ACC-9941-02",
            direction_display="->",
            status="CONFIRMED",
            score=0.99,
            score_semantics="deterministic_rule_confidence",
            detection_method="TRANSACTION_SETTLEMENT_RULE",
            detection_version="1.0.0",
            status_rationale="Invoice remittance instructions designate Axis Bank clearing account.",
            evidence_payload=make_rel_evidence("TRANSFERS_TO", node_vendor1.id, node_account.id, case1.id, "TRANSACTION_SETTLEMENT_RULE", 0.99),
            created_at=now,
            updated_at=now,
        )
        rel4 = DetectedRelationshipModel(
            id=generate_id(),
            case_id=case1.id,
            detection_run_id=run1.id,
            relationship_type="REFERENCES_INVOICE",
            source_id=node_doc2.id,
            source_type="DOCUMENT",
            source_label="Bilingual Receipt REC-2026-4402",
            target_id=node_doc1.id,
            target_type="DOCUMENT",
            target_label="Tax Invoice INV-2026-9001",
            direction_display="->",
            status="CONFIRMED",
            score=0.95,
            score_semantics="deterministic_rule_confidence",
            detection_method="EXPLICIT_DOCUMENT_REFERENCE",
            detection_version="1.0.0",
            status_rationale="Receipt voucher explicit reference field cites invoice INV-2026-9001.",
            evidence_payload=make_rel_evidence("REFERENCES_INVOICE", node_doc2.id, node_doc1.id, case1.id, "EXPLICIT_DOCUMENT_REFERENCE", 0.95),
            created_at=now,
            updated_at=now,
        )
        db.add_all([rel1, rel2, rel3, rel4])
        db.flush()
        print(f"[+] Seeded Evidence Graph: 6 entities/documents and 4 verified relationship edges.")

        # 8. Seed Consistency Finding with Human Review
        find1 = ConsistencyFindingModel(
            id=generate_id(),
            case_id=case1.id,
            analysis_run_id=run1.id,
            rule_id="INVOICE_RECEIPT_AMOUNT_DISCREPANCY",
            rule_version="1.0.0",
            category="FINANCIAL_VALIDATION",
            title="Monetary Settlement Variance: $1,500.00 Discrepancy",
            explanation="Billed invoice amount ($12,500.00 USD) in INV-2026-9001 exceeds settled receipt amount ($11,000.00 USD) in REC-2026-4402 by $1,500.00 USD.",
            severity="HIGH",
            outcome="INCONSISTENT",
            score=0.98,
            score_semantics="rule_deterministic_confidence",
            affected_document_ids=[doc1.id, doc2.id],
            compared_fields=["total_amount", "settlement_amount"],
            original_values={"doc1_amount": "$12,500.00", "doc2_amount": "$11,000.00"},
            normalized_values={"doc1_amount": 12500.0, "doc2_amount": 11000.0},
            supporting_evidence_ids=[],
            contradicting_evidence_ids=[],
            locations_payload=[{"document_id": doc1.id, "page": 1}, {"document_id": doc2.id, "page": 1}],
            detection_method="MONETARY_RECONCILIATION_CHECK",
            rule_parameters={"tolerance": 0.0, "currency": "USD"},
            limitations=["Assumes standard Net-30 remittance without separate withholding advice"],
            status="CONFIRMED_OBSERVATION",
            review_status="CONFIRMED_OBSERVATION",
            is_human_reviewed=True,
            comparisons_payload=[{"field": "amount", "diff": 1500.0}],
            created_at=now,
            updated_at=now,
        )
        find2 = ForensicFindingModel(
            id=generate_id(),
            case_id=case1.id,
            document_id=doc1.id,
            processing_run_id=run1.id,
            category="PDF_STRUCTURE",
            title="PDF Vector Stream Linearization & Font Integrity",
            description="Document exhibits consistent font dictionary hierarchy and intact cross-reference structure.",
            severity="INFO",
            categorical_confidence="HIGH",
            confidence_source="rule_engine",
            confidence_calibration_method="deterministic",
            confidence=0.99,
            status="CONFIRMED_OBSERVATION",
            evidence_ids=[node_doc1.id],
            created_at=now,
            source_component="pdf_structural_analyzer",
            limitations=[],
            finding_metadata={"pdf_version": "1.7", "producer": "pikepdf_forensics"},
        )
        db.add_all([find1, find2])
        db.flush()

        # Human review on the Discrepancy Finding
        rev1 = ConsistencyReviewModel(
            id=generate_id(),
            case_id=case1.id,
            finding_id=find1.id,
            decision="CONFIRM_INCONSISTENCY",
            reviewer_id=user.id,
            reason="Verified $1,500 discrepancy against signed procurement ledger and bank wire settlement.",
            reviewed_at=now,
            previous_status="UNREVIEWED",
            new_status="CONFIRMED_OBSERVATION",
        )
        db.add(rev1)
        db.flush()
        print(f"[+] Seeded Consistency Finding with signed human review attribution: '{find1.title}'")

        # 9. Seed Investigation Dossier (Approved & Frozen with Content Hash)
        dossier_payload = {
            "case_id": case1.id,
            "case_reference": case1.case_reference,
            "title": case1.title,
            "scope_and_purpose": "Forensic audit of vendor invoicing, bilingual receipt reconciliation, and wire routing.",
            "generated_at": now.isoformat(),
            "generated_by": user.username,
            "summary_of_findings": [
                {
                    "finding_id": find1.id,
                    "type": "Monetary Variance",
                    "status": "CONFIRMED_OBSERVATION",
                    "discrepancy": "$1,500.00 USD",
                }
            ],
            "evidence_inventory": [
                {"document_id": doc1.id, "filename": doc1.original_filename, "sha256": doc1.sha256},
                {"document_id": doc2.id, "filename": doc2.original_filename, "sha256": doc2.sha256},
                {"document_id": doc3.id, "filename": doc3.original_filename, "sha256": doc3.sha256},
            ],
            "graph_summary": {"total_nodes": 6, "total_edges": 4},
        }
        canonical_hash = compute_canonical_content_hash(dossier_payload)

        dossier = InvestigationDossierModel(
            id=DEMO_DOSSIER_ID,
            case_id=case1.id,
            title="Executive Investigation Dossier: Operation Northern Star",
            scope_and_purpose="Forensic reconciliation of invoice-to-settlement ledgers and corporate control relationships.",
            version=1,
            status=DossierStatus.APPROVED.value,
            executive_summary="Forensic audit of vendor invoicing, bilingual receipt reconciliation, and wire routing.",
            document_summaries=[{"document_id": doc1.id, "filename": doc1.original_filename, "sha256": doc1.sha256}],
            finding_ids=[find1.id],
            evidence_ids=[node_doc1.id, node_vendor1.id],
            review_decisions=[{"finding_id": find1.id, "decision": "CONFIRM_OBSERVATION"}],
            limitations=[],
            unresolved_questions=[],
            sections=[
                {"title": "1. Executive Summary", "content": "Investigation confirmed $1,500.00 settlement variance."},
                {"title": "2. Evidence Inventory", "content": "3 primary forensic documents examined with cryptographic provenance."},
                {"title": "3. Entity Resolution", "content": "Apex Technical Consulting Ltd mapped to Director Vikram Malhotra and Axis Bank ACC-9941-02."},
            ],
            content_hash=canonical_hash,
            dossier_payload=dossier_payload,
            created_at=now,
            created_by=user.username,
            finalized_at=now,
        )
        db.add(dossier)
        db.flush()
        print(f"[+] Seeded Approved Investigation Dossier (Canonical SHA-256: {canonical_hash[:16]}...)")

        # 10. Seed Cross-Case Scope, Candidate Match & Review (Case 1 <-> Case 2)
        scope = CrossCaseScopeModel(
            id=DEMO_SCOPE_ID,
            organization_id=org.id,
            name="Scope: Northern Star & Apex Logistics Joint Inquiry",
            description="Cross-case correlation scope connecting procurement audit with phoenix entity inquiry.",
            case_ids=[case1.id, case2.id],
            created_by=user.id,
            created_at=now,
            updated_at=now,
            is_active=True,
            scope_metadata={"case_count": 2, "analysis_mode": "deterministic_identifier_link"},
        )
        db.add(scope)
        db.flush()

        match_evidence = {
            "target_case_id": case1.id,
            "candidate_case_id": case2.id,
            "target_mention_id": "mention-tgt-acc-9941",
            "candidate_mention_id": "mention-cand-acc-9941",
            "target_document_id": doc1.id,
            "candidate_document_id": doc4.id,
            "target_page_number": 1,
            "candidate_page_number": 1,
            "target_field_key": "remittance_account",
            "candidate_field_key": "settlement_account",
            "matching_signals": [
                "Exact Bank Account Match: Axis Bank ACC-9941-02",
                "Identical Controlling Principal: Vikram Malhotra",
                "Synchronized Billing Cadence: Q4 2026",
            ],
            "contradicting_signals": [
                "Conflicting Registered Address: 44 Cyber City, Gurugram vs 12 Nariman Point, Mumbai",
                "Disparate State GSTIN Registrations: 06 (HR) vs 27 (MH)",
            ],
            "confidence_score": 0.94,
            "matching_method": "deterministic_bank_routing_rule",
            "match_classification": "IDENTICAL_FINANCIAL_ACCOUNT",
        }

        match = CrossCaseCandidateMatchModel(
            id=DEMO_MATCH_ID,
            scope_id=scope.id,
            organization_id=org.id,
            entity_type="BANK_ACCOUNT_REFERENCE",
            target_case_id=case1.id,
            candidate_case_id=case2.id,
            target_value_display="ACC-9941-02 (Apex Technical Consulting)",
            candidate_value_display="ACC-9941-02 (Apex Logistics Solutions)",
            raw_target_value_masked="ACC-****-02",
            raw_candidate_value_masked="ACC-****-02",
            matching_method="deterministic_identifier_rule",
            match_classification="IDENTICAL_FINANCIAL_ACCOUNT",
            match_score=0.94,
            decision_status="ACCEPTED",
            evidence_payload=match_evidence,
            created_at=now,
        )
        db.add(match)
        db.flush()

        match_review = CrossCaseCandidateReviewModel(
            id=generate_id(),
            match_id=match.id,
            scope_id=scope.id,
            decision="ACCEPTED",
            reviewer_id=user.id,
            reviewer_username=user.username,
            rationale="Identical commercial clearing account identified across distinct entities. Strong phoenix entity indicator; recommend subpoena for beneficial ownership records.",
            previous_status="PENDING_REVIEW",
            new_status="ACCEPTED",
            reviewed_at=now,
        )
        db.add(match_review)
        db.flush()
        print(f"[+] Seeded Cross-Case Correlation Match with human review disposition.")

        # 11. Record Tamper-Evident Audit Event Trail
        event_payload = {"cases": [case1.case_reference, case2.case_reference], "documents_count": 4}
        event_hash = hashlib.sha256(json.dumps(event_payload, sort_keys=True).encode()).hexdigest()
        audit_event = AuditEventModel(
            id=generate_id(),
            case_id=case1.id,
            sequence_number=1,
            actor_id=user.id,
            event_type="DOCUMENT_INGESTED",
            entity_type="CASE",
            entity_id=case1.id,
            timestamp=now,
            payload=event_payload,
            previous_event_hash="0000000000000000000000000000000000000000000000000000000000000000",
            event_hash=event_hash,
            schema_version="1.0.0",
        )
        db.add(audit_event)

        db.commit()

        print("=" * 80)
        print(" [SUCCESS] DEMONSTRATION DATASET SEEDING COMPLETE!")
        print(f" Organization: {org.name} ({org.slug})")
        print(f" User:         {user.username} (Role: {user.system_role})")
        print(f" Primary Case: {case1.case_reference} - {case1.title}")
        print(f" Linked Case:  {case2.case_reference} - {case2.title}")
        print(f" Documents:    4 synthetic bilingual/digital PDFs loaded")
        print(f" Graph Nodes:  6 entities/documents + 4 verified relationships")
        print(f" Findings:     1 monetary conflict finding (reviewed) + 1 forensic metadata finding")
        print(f" Dossier:      1 finalized dossier (SHA-256 verified)")
        print(f" Cross-Case:   1 scope + 1 candidate match (reviewed & escalated)")
        print("=" * 80)

    finally:
        db.close()
        shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    seed_demo_data()
