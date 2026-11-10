"""Grounded Case Evidence Retriever.

Framework-neutral, deterministic retrieval service operating strictly over authoritative
EVIDEXA repositories within a single case boundary.
"""

from __future__ import annotations

import re
from typing import Any

from document_intelligence.core.exceptions import EntityNotFoundException
from document_intelligence.domain.models.assistant import RetrievedCaseContext
from document_intelligence.infrastructure.repositories.case_repository import CaseRepository
from document_intelligence.infrastructure.repositories.consistency_repository import (
    ConsistencyRepository,
)
from document_intelligence.infrastructure.repositories.document_repository import (
    DocumentRepository,
)
from document_intelligence.infrastructure.repositories.dossier_repository import (
    DossierRepository,
)
from document_intelligence.infrastructure.repositories.entity_match_repository import (
    EntityMatchRepository,
)
from document_intelligence.infrastructure.repositories.evidence_repository import (
    EvidenceRepository,
)
from document_intelligence.infrastructure.repositories.finding_repository import (
    FindingRepository,
)
from document_intelligence.infrastructure.repositories.relationship_repository import (
    RelationshipRepository,
)
from document_intelligence.modules.assistant.sanitization import sanitize_text
from document_intelligence.modules.graph.projector import sanitize_display_label


def _extract_query_terms(text: str) -> set[str]:
    """Extract normalized search keywords from investigator question."""
    tokens = re.findall(r"[A-Za-z0-9_\-\$]{3,}", text.lower())
    # Exclude trivial conversational stop words
    stop_words = {
        "the",
        "and",
        "for",
        "with",
        "what",
        "where",
        "which",
        "when",
        "does",
        "have",
        "this",
        "that",
        "these",
        "those",
        "from",
        "about",
        "show",
        "tell",
        "explain",
        "are",
        "was",
        "were",
        "been",
        "there",
        "their",
        "case",
        "document",
        "documents",
    }
    return {t for t in tokens if t not in stop_words}


def _score_text(text: str | None, terms: set[str]) -> int:
    """Compute keyword relevance score for lexical ranking."""
    if not text or not terms:
        return 0
    lower = text.lower()
    return sum(2 if re.search(rf"\b{re.escape(t)}\b", lower) else 1 for t in terms if t in lower)


class CaseEvidenceRetriever:
    """Retrieves and standardizes authoritative case evidence without cross-case leakage."""

    def __init__(
        self,
        case_repo: CaseRepository,
        document_repo: DocumentRepository,
        finding_repo: FindingRepository,
        consistency_repo: ConsistencyRepository,
        relationship_repo: RelationshipRepository,
        entity_match_repo: EntityMatchRepository,
        evidence_repo: EvidenceRepository,
        dossier_repo: DossierRepository | None = None,
    ) -> None:
        self.case_repo = case_repo
        self.document_repo = document_repo
        self.finding_repo = finding_repo
        self.consistency_repo = consistency_repo
        self.relationship_repo = relationship_repo
        self.entity_match_repo = entity_match_repo
        self.evidence_repo = evidence_repo
        self.dossier_repo = dossier_repo

    def retrieve(
        self,
        case_id: str,
        question: str = "",
        explicit_evidence_ids: list[str] | None = None,
        max_documents: int = 10,
        max_findings: int = 15,
        max_consistency_findings: int = 15,
        max_relationships: int = 15,
        max_entities: int = 15,
        max_evidence: int = 20,
    ) -> RetrievedCaseContext:
        """Deterministically retrieve and rank relevant case records."""
        # 1. Enforce Case Access and Ownership
        case = self.case_repo.get_by_id(case_id)
        if not case:
            raise EntityNotFoundException("Case", case_id)

        query_terms = _extract_query_terms(question)
        explicit_set = set(explicit_evidence_ids or [])
        unavailable_subsystems: list[str] = []

        # 2. Documents
        doc_models, _ = self.document_repo.list_by_case(case_id, skip=0, limit=100)
        docs_data: list[dict[str, Any]] = []
        for d in doc_models:
            docs_data.append(
                {
                    "document_id": d.id,
                    "declared_filename": d.original_filename,
                    "sha256_prefix": d.sha256[:12],
                    "media_type": d.media_type,
                    "page_count": d.page_count,
                    "ingestion_status": d.ingestion_status.value
                    if hasattr(d.ingestion_status, "value")
                    else str(d.ingestion_status),
                }
            )

        # Rank documents if query terms present
        if query_terms:
            docs_data.sort(
                key=lambda d: _score_text(d["declared_filename"], query_terms),
                reverse=True,
            )
        docs_data = docs_data[:max_documents]

        # 3. Forensic Findings
        findings_data: list[dict[str, Any]] = []
        try:
            finding_models, _ = self.finding_repo.list_by_case(case_id, skip=0, limit=100)
            for f in finding_models:
                score = (
                    10
                    if f.id in explicit_set
                    else _score_text(f"{f.title} {f.description}", query_terms)
                )
                findings_data.append(
                    {
                        "finding_id": f.id,
                        "document_id": f.document_id,
                        "title": f.title,
                        "description": f.description,
                        "category": f.category.value
                        if hasattr(f.category, "value")
                        else str(f.category),
                        "severity": f.severity.value
                        if hasattr(f.severity, "value")
                        else str(f.severity),
                        "status": f.status.value if hasattr(f.status, "value") else str(f.status),
                        "evidence_ids": f.evidence_ids,
                        "limitations": f.limitations,
                        "_score": score,
                    }
                )
            findings_data.sort(key=lambda item: item["_score"], reverse=True)
            for item in findings_data:
                item.pop("_score", None)
            findings_data = findings_data[:max_findings]
        except Exception:
            unavailable_subsystems.append("forensic_findings")

        # 4. Consistency Findings
        consistency_data: list[dict[str, Any]] = []
        try:
            consistency_models = self.consistency_repo.list_findings(case_id=case_id, limit=100)
            for cf in consistency_models:
                score = (
                    10
                    if cf.id in explicit_set
                    else _score_text(f"{cf.rule_id} {cf.explanation}", query_terms)
                )
                locations = [
                    {
                        "document_id": loc.document_id,
                        "page_number": loc.page_number,
                        "field_key": loc.field_key,
                        "bounding_box": loc.bounding_box.to_normalized_dict()
                        if loc.bounding_box
                        else None,
                        "raw_value": sanitize_text(
                            sanitize_display_label(loc.raw_value or "", "EVIDENCE")
                        ),
                    }
                    for loc in cf.locations
                ]
                consistency_data.append(
                    {
                        "finding_id": cf.id,
                        "rule_id": cf.rule_id,
                        "status": cf.outcome.value
                        if hasattr(cf.outcome, "value")
                        else str(cf.outcome),
                        "severity": cf.severity.value
                        if hasattr(cf.severity, "value")
                        else str(cf.severity),
                        "explanation": cf.explanation,
                        "document_ids": cf.affected_document_ids,
                        "locations": locations,
                        "_score": score,
                    }
                )
            consistency_data.sort(key=lambda item: item["_score"], reverse=True)
            for item in consistency_data:
                item.pop("_score", None)
            consistency_data = consistency_data[:max_consistency_findings]
        except Exception:
            unavailable_subsystems.append("consistency_findings")

        # 5. Entity Candidate Matches
        entities_data: list[dict[str, Any]] = []
        try:
            match_models, _ = self.entity_match_repo.list_matches(case_id=case_id, limit=100)
            for m in match_models:
                target_val = sanitize_text(sanitize_display_label(m.target_value_display, "ENTITY"))
                cand_val = sanitize_text(
                    sanitize_display_label(m.candidate_value_display, "ENTITY")
                )
                score = (
                    10
                    if m.id in explicit_set
                    else _score_text(f"{target_val} {cand_val}", query_terms)
                )
                entities_data.append(
                    {
                        "match_id": m.id,
                        "entity_type": m.entity_type.value
                        if hasattr(m.entity_type, "value")
                        else str(m.entity_type),
                        "target_value": target_val,
                        "candidate_value": cand_val,
                        "match_classification": m.match_classification.value
                        if hasattr(m.match_classification, "value")
                        else str(m.match_classification),
                        "decision_status": m.decision_status.value
                        if hasattr(m.decision_status, "value")
                        else str(m.decision_status),
                        "similarity_score": round(m.match_score, 3),
                        "_score": score,
                    }
                )
            entities_data.sort(key=lambda item: item["_score"], reverse=True)
            for item in entities_data:
                item.pop("_score", None)
            entities_data = entities_data[:max_entities]
        except Exception:
            unavailable_subsystems.append("entity_resolution")

        # 6. Relationships (Preserving Explicit Status vs Score)
        relationships_data: list[dict[str, Any]] = []
        try:
            rel_models, _ = self.relationship_repo.list_relationships(case_id=case_id, limit=100)
            for r in rel_models:
                score = (
                    10
                    if r.id in explicit_set
                    else _score_text(
                        f"{r.relationship_type.value} {r.status_rationale}", query_terms
                    )
                )
                contradictory_signals = [
                    sanitize_text(sanitize_display_label(sig, "EVIDENCE"))
                    for sig in r.evidence.contradicting_signals
                ]

                relationships_data.append(
                    {
                        "relationship_id": r.id,
                        "predicate": r.relationship_type.value
                        if hasattr(r.relationship_type, "value")
                        else str(r.relationship_type),
                        "source_id": r.source_id,
                        "target_id": r.target_id,
                        "status": r.status.value if hasattr(r.status, "value") else str(r.status),
                        "confidence_score": round(r.score, 3),
                        "status_rationale": r.status_rationale,
                        "contradictory_signals": contradictory_signals,
                        "_score": score,
                    }
                )
            relationships_data.sort(key=lambda item: item["_score"], reverse=True)
            for item in relationships_data:
                item.pop("_score", None)
            relationships_data = relationships_data[:max_relationships]
        except Exception:
            unavailable_subsystems.append("relationships")

        # 7. Evidence Nodes & OCR / Extracted Fields
        extracted_fields_data: list[dict[str, Any]] = []
        text_snippets_data: list[dict[str, Any]] = []
        try:
            ev_models, _ = self.evidence_repo.list_by_case(case_id, skip=0, limit=200)
            for node in ev_models:
                raw_text = node.raw_value or node.description
                if not raw_text:
                    continue
                sanitized_text = sanitize_text(sanitize_display_label(raw_text, "EVIDENCE"))
                bbox_dict = node.bounding_box.to_normalized_dict() if node.bounding_box else None
                score = 10 if node.id in explicit_set else _score_text(sanitized_text, query_terms)

                node_entry = {
                    "evidence_id": node.id,
                    "document_id": node.document_id,
                    "evidence_type": node.evidence_type.value
                    if hasattr(node.evidence_type, "value")
                    else str(node.evidence_type),
                    "title": node.title,
                    "page_number": node.page_number,
                    "bounding_box": bbox_dict,
                    "text": sanitized_text[:300],
                    "_score": score,
                }

                if node.evidence_type.value in ("EXTRACTED_FIELD", "TABLE_CELL"):
                    extracted_fields_data.append(node_entry)
                else:
                    text_snippets_data.append(node_entry)

            extracted_fields_data.sort(key=lambda item: item["_score"], reverse=True)
            text_snippets_data.sort(key=lambda item: item["_score"], reverse=True)

            for item in extracted_fields_data:
                item.pop("_score", None)
            for item in text_snippets_data:
                item.pop("_score", None)

            extracted_fields_data = extracted_fields_data[:max_evidence]
            text_snippets_data = text_snippets_data[:max_evidence]
        except Exception:
            unavailable_subsystems.append("evidence_nodes")

        # 8. Investigator Review History
        reviews_data: list[dict[str, Any]] = []
        if self.dossier_repo:
            try:
                review_models = self.dossier_repo.list_all_reviews_for_case(case_id)
                for rv in review_models:
                    reviews_data.append(
                        {
                            "review_id": rv.id,
                            "finding_id": rv.finding_id,
                            "reviewer_id": rv.reviewer_id,
                            "action": rv.action.value
                            if hasattr(rv.action, "value")
                            else str(rv.action),
                            "comment": rv.comment,
                            "reviewed_at": rv.reviewed_at.isoformat() if rv.reviewed_at else None,
                            "new_status": rv.new_status,
                        }
                    )
            except Exception:
                unavailable_subsystems.append("investigator_reviews")

        total_items = (
            len(docs_data)
            + len(findings_data)
            + len(consistency_data)
            + len(entities_data)
            + len(relationships_data)
            + len(extracted_fields_data)
            + len(text_snippets_data)
            + len(reviews_data)
        )

        return RetrievedCaseContext(
            case_id=case.id,
            case_title=case.title,
            case_status=case.status.value if hasattr(case.status, "value") else str(case.status),
            documents=docs_data,
            findings=findings_data,
            consistency_findings=consistency_data,
            extracted_fields=extracted_fields_data,
            entities=entities_data,
            relationships=relationships_data,
            reviews=reviews_data,
            text_snippets=text_snippets_data,
            total_retrieved_items=total_items,
            unavailable_subsystems=unavailable_subsystems,
        )
