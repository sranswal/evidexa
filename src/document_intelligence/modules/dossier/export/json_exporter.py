"""JSON Dossier Exporter.

Serializes an InvestigationDossier to a structured, audit-ready JSON document
conforming to evidentiary exchange schemas.
"""

from __future__ import annotations

import json
from typing import Any

from document_intelligence.domain.models.investigation_dossier import InvestigationDossier


class JsonDossierExporter:
    """Exports investigation dossiers as standardized JSON artifacts."""

    def export(self, dossier: InvestigationDossier, indent: int = 2) -> str:
        """Serialize dossier model into an indented, standardized JSON string."""
        payload: dict[str, Any] = {
            "dossier_id": dossier.id,
            "case_id": dossier.case_id,
            "title": dossier.title,
            "scope_and_purpose": dossier.scope_and_purpose,
            "version": dossier.version,
            "status": dossier.status.value
            if hasattr(dossier.status, "value")
            else str(dossier.status),
            "content_hash": dossier.content_hash,
            "executive_summary": dossier.executive_summary,
            "created_at": dossier.created_at.isoformat() if dossier.created_at else None,
            "created_by": dossier.created_by,
            "finalized_at": dossier.finalized_at.isoformat() if dossier.finalized_at else None,
            "document_summaries": dossier.document_summaries,
            "finding_ids": dossier.finding_ids,
            "evidence_ids": dossier.evidence_ids,
            "review_decisions": dossier.review_decisions,
            "unresolved_questions": dossier.unresolved_questions,
            "limitations": dossier.limitations,
            "sections": [
                {
                    "section_id": s.section_id,
                    "title": s.title,
                    "order": s.order,
                    "content": s.content,
                    "items": s.items,
                }
                for s in dossier.sections
            ],
            "legal_disclaimer": (
                "This dossier represents a structured compilation of automated forensic indicators, "
                "deterministic consistency rules, and recorded investigator reviews. "
                "It does NOT constitute an autonomous fraud determination, accusation, or binding legal conclusion."
            ),
        }
        return json.dumps(payload, indent=indent, default=str, ensure_ascii=True)
