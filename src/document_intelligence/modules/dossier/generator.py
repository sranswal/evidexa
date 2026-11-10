"""Dossier generator module.

Generates comprehensive, deterministic investigation dossiers structured across
12 distinct analytical sections with canonical content hashing for integrity verification.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from document_intelligence.domain.enums import (
    DossierStatus,
    EvidentiaryClassification,
    FindingSeverity,
)
from document_intelligence.domain.identifiers import generate_id, utc_now
from document_intelligence.domain.models.aggregated_finding import (
    AggregatedFinding,
    AggregatedFindingReview,
)
from document_intelligence.domain.models.case import Case
from document_intelligence.domain.models.consistency import ConsistencyCheck
from document_intelligence.domain.models.document import Document
from document_intelligence.domain.models.entity_resolution import ResolvedEntity
from document_intelligence.domain.models.evidence_node import EvidenceNode
from document_intelligence.domain.models.investigation_dossier import (
    DossierSection,
    InvestigationDossier,
)
from document_intelligence.domain.models.relationship import DetectedRelationship

STANDARD_DISCLAIMER: str = (
    "NOTICE: This dossier represents a structured compilation of automated digital forensic indicators, "
    "deterministic consistency rules, and recorded investigator reviews as of the generation timestamp. "
    "It does NOT constitute an autonomous fraud determination, criminal accusation, or binding legal conclusion. "
    "All automated indicators require independent corroboration and human investigative judgment."
)

TECHNICAL_LIMITATIONS: list[str] = [
    "Optical Character Recognition (OCR) error rates vary with scan resolution, skew, and document degradation.",
    "Visual forensics and clone detection algorithms may exhibit false positives on repeating document templates or letterheads.",
    "Consistency analysis rules are constrained by the documents currently ingested into this case workspace.",
    "Unreviewed findings represent automated indicators and analytical interpretations, not verified factual findings.",
]


def compute_canonical_content_hash(payload: dict[str, Any]) -> str:
    """Compute a deterministic SHA-256 hash over a canonical JSON serialization of the dossier payload."""
    canonical_json = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
        ensure_ascii=True,
    )
    return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()


def _doc_name(d: Document) -> str:
    name = getattr(d, "file_name", None) or getattr(d, "original_filename", "unnamed_document")
    return str(name)


def _doc_hash(d: Document) -> str:
    h = getattr(d, "hash_sha256", None) or getattr(d, "sha256", "")
    return str(h)


def _doc_mime(d: Document) -> str:
    m = getattr(d, "mime_type", None) or getattr(d, "media_type", "application/pdf")
    return str(getattr(m, "value", m))


def _doc_status(d: Document) -> str:
    s = getattr(d, "status", None) or getattr(d, "ingestion_status", "PROCESSED")
    return str(getattr(s, "value", s))


class DossierGenerator:
    """Compiles unified investigation evidence, findings, and reviews into a 12-section InvestigationDossier."""

    def generate(
        self,
        case: Case,
        documents: list[Document],
        aggregated_findings: list[AggregatedFinding],
        reviews: list[AggregatedFindingReview],
        evidence_nodes: list[EvidenceNode] | None = None,
        consistency_checks: list[ConsistencyCheck] | None = None,
        relationships: list[DetectedRelationship] | None = None,
        resolved_entities: list[ResolvedEntity] | None = None,
        scope_and_purpose: str | None = None,
        created_by: str = "investigator",
        version: int = 1,
    ) -> InvestigationDossier:
        """Construct an InvestigationDossier across all 12 formal sections."""
        evidence_nodes = evidence_nodes or []
        consistency_checks = consistency_checks or []
        relationships = relationships or []
        resolved_entities = resolved_entities or []

        case_title = getattr(case, "title", None) or getattr(case, "name", "Investigation Case")
        scope = (
            scope_and_purpose
            or f"Forensic analysis and consistency investigation for Case {case_title}"
        )

        # 1. Document summaries
        doc_summaries: list[dict[str, Any]] = [
            {
                "id": doc.id,
                "file_name": _doc_name(doc),
                "hash_sha256": _doc_hash(doc),
                "mime_type": _doc_mime(doc),
                "page_count": doc.page_count or 0,
                "status": _doc_status(doc),
                "created_at": doc.created_at.isoformat() if doc.created_at else None,
            }
            for doc in sorted(documents, key=_doc_name)
        ]

        # 2. Finding summaries & counts
        high_critical_findings = [
            f
            for f in aggregated_findings
            if f.severity in (FindingSeverity.CRITICAL, FindingSeverity.HIGH)
        ]
        unreviewed_findings = [f for f in aggregated_findings if not f.is_reviewed]
        reviewed_findings = [f for f in aggregated_findings if f.is_reviewed]

        # 3. Unresolved questions
        unresolved_questions: list[str] = []
        if unreviewed_findings:
            unresolved_questions.append(
                f"{len(unreviewed_findings)} aggregated finding(s) have not undergone formal investigator review."
            )
        for f in high_critical_findings:
            if not f.is_reviewed:
                unresolved_questions.append(
                    f"High-severity finding '{f.title}' ({f.category.value}) requires evidentiary confirmation."
                )
        if any(doc.page_count == 0 for doc in documents):
            unresolved_questions.append(
                "One or more ingested documents have an indeterminate page count."
            )

        # 4. Executive summary
        exec_summary = (
            f"Investigation Dossier for Case '{case_title}' (ID: {case.id}). "
            f"A total of {len(documents)} document(s) were examined using multi-stage digital forensics, "
            f"structured extraction, entity resolution, and cross-document consistency checks. "
            f"The analysis identified {len(aggregated_findings)} aggregated finding(s) "
            f"({len(high_critical_findings)} high/critical severity). "
            f"{len(reviewed_findings)} finding(s) have been reviewed by investigators, while "
            f"{len(unreviewed_findings)} remain unreviewed automated indicators."
        )

        # 5. Build 12 sections
        sections = self._build_sections(
            case=case,
            documents=documents,
            aggregated_findings=aggregated_findings,
            reviews=reviews,
            evidence_nodes=evidence_nodes,
            consistency_checks=consistency_checks,
            relationships=relationships,
            resolved_entities=resolved_entities,
            scope=scope,
            unresolved_questions=unresolved_questions,
        )

        # 6. Snapshot payload for hashing & export
        snapshot_payload = {
            "case_id": case.id,
            "case_name": case_title,
            "scope_and_purpose": scope,
            "version": version,
            "executive_summary": exec_summary,
            "document_summaries": doc_summaries,
            "finding_ids": [f.id for f in aggregated_findings],
            "evidence_ids": [e.id for e in evidence_nodes],
            "sections": [s.model_dump(mode="json") for s in sections],
            "limitations": list(TECHNICAL_LIMITATIONS),
            "unresolved_questions": unresolved_questions,
            "generated_at": utc_now().isoformat(),
            "generated_by": created_by,
        }
        content_hash = compute_canonical_content_hash(snapshot_payload)

        return InvestigationDossier(
            id=generate_id(),
            case_id=case.id,
            title=f"Investigation Evidence Dossier - {case_title}",
            scope_and_purpose=scope,
            version=version,
            status=DossierStatus.DRAFT,
            executive_summary=exec_summary,
            sections=sections,
            document_summaries=doc_summaries,
            finding_ids=[f.id for f in aggregated_findings],
            evidence_ids=[e.id for e in evidence_nodes],
            review_decisions=[r.model_dump(mode="json") for r in reviews],
            limitations=list(TECHNICAL_LIMITATIONS),
            unresolved_questions=unresolved_questions,
            content_hash=content_hash,
            dossier_payload=snapshot_payload,
            created_at=utc_now(),
            created_by=created_by,
        )

    def _build_sections(
        self,
        case: Case,
        documents: list[Document],
        aggregated_findings: list[AggregatedFinding],
        reviews: list[AggregatedFindingReview],
        evidence_nodes: list[EvidenceNode],
        consistency_checks: list[ConsistencyCheck],
        relationships: list[DetectedRelationship],
        resolved_entities: list[ResolvedEntity],
        scope: str,
        unresolved_questions: list[str],
    ) -> list[DossierSection]:
        """Construct the 12 canonical dossier sections."""
        # Section 1: Case Overview
        case_title = getattr(case, "title", None) or getattr(case, "name", "Investigation Case")
        sec1 = DossierSection(
            section_id="case_overview",
            title="1. Case Overview",
            order=1,
            content=(
                f"Case '{case_title}' (ID: {case.id})\n"
                f"Status: {case.status.value if hasattr(case.status, 'value') else str(case.status)}\n"
                f"Description: {case.description or 'No case description provided.'}\n"
                f"Total Ingested Documents: {len(documents)}\n"
                f"Total Aggregated Findings: {len(aggregated_findings)}"
            ),
            items=[
                {
                    "case_id": case.id,
                    "case_name": case_title,
                    "status": case.status.value
                    if hasattr(case.status, "value")
                    else str(case.status),
                    "document_count": len(documents),
                    "finding_count": len(aggregated_findings),
                }
            ],
        )

        # Section 2: Scope and Methodology
        sec2 = DossierSection(
            section_id="scope_and_methodology",
            title="2. Scope and Methodology",
            order=2,
            content=(
                f"Scope: {scope}\n\n"
                "Methodology:\n"
                "- PDF Structural Forensics: Incremental update parsing, xref table analysis, trailer inspection, and metadata timeline reconstruction.\n"
                "- Visual & Image Forensics: Error Level Analysis (ELA), copy-move forgery detection, and noise variance profiling.\n"
                "- Extraction & Parsing: Deterministic layout-aware text extraction, OCR fallback, and structured entity/table extraction.\n"
                "- Entity Resolution: Levenshtein distance, token overlap, and deterministic phonetic clustering.\n"
                "- Cross-Document Consistency Engine: Deterministic rule verification across document dates, totals, party tax IDs, and duplicate content."
            ),
            items=[
                {"pipeline_module": "pdf_structural_forensics", "status": "active"},
                {"pipeline_module": "visual_image_forensics", "status": "active"},
                {"pipeline_module": "entity_resolution", "status": "active"},
                {"pipeline_module": "cross_document_consistency", "status": "active"},
            ],
        )

        # Section 3: Documents Examined
        sec3_items = [
            {
                "document_id": d.id,
                "file_name": _doc_name(d),
                "sha256": _doc_hash(d),
                "mime_type": _doc_mime(d),
                "page_count": d.page_count or 0,
            }
            for d in documents
        ]
        sec3 = DossierSection(
            section_id="documents_examined",
            title="3. Documents Examined",
            order=3,
            content=f"An evidentiary inventory of {len(documents)} document(s) ingested into the case workspace.",
            items=sec3_items,
        )

        # Section 4: Processing and Extraction Summary
        sec4_items = [
            {
                "document_id": d.id,
                "file_name": _doc_name(d),
                "status": _doc_status(d),
                "is_processed": bool(getattr(d, "is_processed", True)),
            }
            for d in documents
        ]
        sec4 = DossierSection(
            section_id="processing_and_extraction_summary",
            title="4. Processing and Extraction Summary",
            order=4,
            content=(
                f"Summary of extraction and processing pipeline runs across {len(documents)} document(s). "
                f"All documents have undergone cryptographic hashing upon ingestion."
            ),
            items=sec4_items,
        )

        # Section 5: Key Observations
        key_findings = [
            f
            for f in aggregated_findings
            if f.severity in (FindingSeverity.CRITICAL, FindingSeverity.HIGH)
        ]
        sec5_items = [
            {
                "id": f.id,
                "title": f.title,
                "category": f.category.value,
                "severity": f.severity.value,
                "classification": f.evidentiary_classification.value,
                "reviewed": f.is_reviewed,
                "description": f.description,
            }
            for f in key_findings
        ]
        sec5 = DossierSection(
            section_id="key_observations",
            title="5. Key Observations",
            order=5,
            content=(
                f"Identified {len(key_findings)} high-priority or critical observation(s) requiring investigative focus."
            ),
            items=sec5_items,
        )

        # Section 6: Cross-Document Consistency
        consistency_findings = [
            f
            for f in aggregated_findings
            if f.category.value
            in ("CROSS_DOCUMENT_INCONSISTENCY", "DUPLICATE_OR_CONFLICTING_RECORD")
        ]
        sec6_items = [
            {
                "id": f.id,
                "title": f.title,
                "severity": f.severity.value,
                "affected_documents": f.affected_document_ids,
                "explanation": f.explanation,
            }
            for f in consistency_findings
        ]
        sec6 = DossierSection(
            section_id="cross_document_consistency",
            title="6. Cross-Document Consistency Analysis",
            order=6,
            content=(
                f"Evaluated deterministic cross-document consistency rules across the case portfolio. "
                f"Yielded {len(consistency_findings)} inconsistency finding(s) or conflicting record(s)."
            ),
            items=sec6_items,
        )

        # Section 7: Entity and Relationship Analysis
        sec7_items = [
            {
                "relationship_id": r.id,
                "source_type": r.source_type,
                "target_type": r.target_type,
                "relationship_type": r.relationship_type.value
                if hasattr(r.relationship_type, "value")
                else str(r.relationship_type),
                "status": r.status.value if hasattr(r.status, "value") else str(r.status),
                "rationale": r.status_rationale,
            }
            for r in relationships
        ]
        sec7 = DossierSection(
            section_id="entity_and_relationship_analysis",
            title="7. Entity and Relationship Analysis",
            order=7,
            content=(
                f"Analysis of {len(resolved_entities)} resolved entity record(s) and {len(relationships)} detected relationship(s) "
                f"across people, organizations, dates, and accounts."
            ),
            items=sec7_items,
        )

        # Section 8: Supporting Evidence
        supporting_nodes = [
            {
                "id": n.id,
                "evidence_type": n.evidence_type.value
                if hasattr(n.evidence_type, "value")
                else str(n.evidence_type),
                "title": n.title,
                "document_id": n.document_id,
                "page_number": n.page_number,
                "source_component": n.source_component,
            }
            for n in evidence_nodes
        ]
        sec8 = DossierSection(
            section_id="supporting_evidence",
            title="8. Supporting Evidence",
            order=8,
            content=(
                f"Catalog of {len(supporting_nodes)} traceable evidence node(s) with deterministic cryptographic hashes, "
                "page coordinates, and extraction provenance."
            ),
            items=supporting_nodes,
        )

        # Section 9: Contradictory Evidence
        contradicting_findings = [
            {
                "id": f.id,
                "title": f.title,
                "contradicting_evidence_ids": f.contradicting_evidence_ids,
                "limitations": f.limitations,
            }
            for f in aggregated_findings
            if f.contradicting_evidence_ids
            or f.evidentiary_classification == EvidentiaryClassification.INVESTIGATOR_CONCLUSION
        ]
        sec9 = DossierSection(
            section_id="contradictory_evidence",
            title="9. Contradictory Evidence and Counter-Indicators",
            order=9,
            content=(
                f"Identified {len(contradicting_findings)} observation(s) containing explicit contradictory evidence signals, "
                "rebuttals, or alternative hypotheses."
            ),
            items=contradicting_findings,
        )

        # Section 10: Investigator Reviews
        sec10_items = [
            {
                "review_id": r.id,
                "finding_id": r.finding_id,
                "reviewer_id": r.reviewer_id,
                "action": r.action.value if hasattr(r.action, "value") else str(r.action),
                "prior_status": r.prior_status,
                "new_status": r.new_status,
                "rationale": r.rationale,
                "reviewed_at": r.created_at.isoformat(),
            }
            for r in reviews
        ]
        sec10 = DossierSection(
            section_id="investigator_reviews",
            title="10. Investigator Review Decisions and Audit Record",
            order=10,
            content=(
                f"Append-only log of {len(reviews)} formal investigator review action(s) asserting human oversight."
            ),
            items=sec10_items,
        )

        # Section 11: Unresolved Questions
        sec11_items = [{"question": q, "status": "OPEN"} for q in unresolved_questions]
        sec11 = DossierSection(
            section_id="unresolved_questions",
            title="11. Unresolved Questions and Open Inquiries",
            order=11,
            content=(
                "Open items, pending document submissions, or unconfirmed automated indicators requiring "
                "further investigation."
            ),
            items=sec11_items,
        )

        # Section 12: Limitations and Disclaimers
        sec12_items = [{"limitation": lim} for lim in TECHNICAL_LIMITATIONS]
        sec12 = DossierSection(
            section_id="limitations_and_disclaimers",
            title="12. Limitations and Legal Disclaimers",
            order=12,
            content=f"{STANDARD_DISCLAIMER}\n\nTechnical Limitations:\n"
            + "\n".join(f"- {lim}" for lim in TECHNICAL_LIMITATIONS),
            items=sec12_items,
        )

        return [sec1, sec2, sec3, sec4, sec5, sec6, sec7, sec8, sec9, sec10, sec11, sec12]
