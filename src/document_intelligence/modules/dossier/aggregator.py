"""Findings aggregation engine.

Unifies heterogeneous forensic findings, cross-document consistency results,
relationship anomalies, and identity conflicts into a coherent, provenance-tracked
investigation findings model without mutating or duplicating source records.
"""

from __future__ import annotations

from document_intelligence.domain.enums import (
    AggregatedFindingCategory,
    EntityMatchClassification,
    EvidentiaryClassification,
    FindingCategory,
    FindingSeverity,
    MatchDecisionStatus,
    RelationshipStatus,
)
from document_intelligence.domain.models.aggregated_finding import (
    AggregatedFinding,
    AggregatedFindingReview,
)
from document_intelligence.domain.models.consistency import ConsistencyFinding
from document_intelligence.domain.models.entity_resolution import EntityCandidateMatch
from document_intelligence.domain.models.forensic_finding import ForensicFinding
from document_intelligence.domain.models.relationship import DetectedRelationship
from document_intelligence.modules.graph.projector import sanitize_display_label

# Map individual forensic finding categories to unified aggregated categories
_CATEGORY_MAPPING: dict[FindingCategory, AggregatedFindingCategory] = {
    FindingCategory.PDF_STRUCTURE: AggregatedFindingCategory.STRUCTURAL_ANOMALY,
    FindingCategory.VISUAL_ANOMALY: AggregatedFindingCategory.VISUAL_ANOMALY,
    FindingCategory.DOCUMENT_INCONSISTENCY: AggregatedFindingCategory.DOCUMENT_INTEGRITY,
    FindingCategory.FINANCIAL_VALIDATION: AggregatedFindingCategory.EXTRACTION_ANOMALY,
    FindingCategory.IDENTITY_VALIDATION: AggregatedFindingCategory.ENTITY_IDENTITY_CONFLICT,
    FindingCategory.CROSS_DOCUMENT_MISMATCH: AggregatedFindingCategory.CROSS_DOCUMENT_INCONSISTENCY,
    FindingCategory.DUPLICATE_CONTENT: AggregatedFindingCategory.DUPLICATE_OR_CONFLICTING_RECORD,
    FindingCategory.OTHER: AggregatedFindingCategory.OTHER,
}


class FindingsAggregator:
    """Aggregates and standardizes findings across all forensic and intelligence subsystems."""

    def aggregate(
        self,
        case_id: str,
        forensic_findings: list[ForensicFinding],
        consistency_findings: list[ConsistencyFinding],
        detected_relationships: list[DetectedRelationship],
        entity_matches: list[EntityCandidateMatch],
        reviews: list[AggregatedFindingReview] | None = None,
    ) -> list[AggregatedFinding]:
        """Compile a deterministic list of unified investigation findings with review history."""
        aggregated: list[AggregatedFinding] = []
        review_map: dict[str, list[AggregatedFindingReview]] = {}
        if reviews:
            for r in reviews:
                review_map.setdefault(r.finding_id, []).append(r)

        # 1. Forensic Findings
        for ff in forensic_findings:
            cat = _CATEGORY_MAPPING.get(ff.category, AggregatedFindingCategory.OTHER)
            is_reviewed = bool(
                ff.status.value in ("CONFIRMED_OBSERVATION", "DISMISSED", "RESOLVED")
                or ff.id in review_map
            )
            classification = (
                EvidentiaryClassification.INVESTIGATOR_CONCLUSION
                if is_reviewed
                else EvidentiaryClassification.AUTOMATED_INDICATOR
            )

            ff_reviews = review_map.get(ff.id, [])
            latest_status = ff_reviews[-1].new_status if ff_reviews else ff.status.value

            aggregated.append(
                AggregatedFinding(
                    id=ff.id,
                    case_id=case_id,
                    source_type="FORENSIC_FINDING",
                    source_id=ff.id,
                    category=cat,
                    evidentiary_classification=classification,
                    source_status=ff.status.value,
                    review_status=latest_status,
                    title=sanitize_display_label(ff.title, "FORENSIC_FINDING"),
                    description=ff.description,
                    explanation=f"Detected by {ff.source_component} with confidence {ff.confidence or 'uncalibrated'}",
                    severity=ff.severity,
                    confidence=ff.confidence,
                    affected_document_ids=[ff.document_id] if ff.document_id else [],
                    supporting_evidence_ids=list(ff.evidence_ids),
                    contradicting_evidence_ids=[],
                    locations=[],
                    limitations=list(ff.limitations),
                    is_reviewed=is_reviewed,
                    review_history=ff_reviews,
                    created_at=ff.created_at,
                )
            )

        # 2. Consistency Findings
        for cf in consistency_findings:
            # Map rule ID / outcome to appropriate category
            if "DUPLICATE" in cf.rule_id or "E0" in cf.rule_id:
                cat = AggregatedFindingCategory.DUPLICATE_OR_CONFLICTING_RECORD
            elif "TAX" in cf.rule_id or "IDENTITY" in cf.rule_id or "D0" in cf.rule_id:
                cat = AggregatedFindingCategory.ENTITY_IDENTITY_CONFLICT
            else:
                cat = AggregatedFindingCategory.CROSS_DOCUMENT_INCONSISTENCY

            is_reviewed = bool(cf.is_human_reviewed or cf.id in review_map)
            classification = (
                EvidentiaryClassification.INVESTIGATOR_CONCLUSION
                if is_reviewed
                else EvidentiaryClassification.ANALYTICAL_INTERPRETATION
            )

            cf_reviews = review_map.get(cf.id, [])
            latest_status = cf_reviews[-1].new_status if cf_reviews else cf.status.value

            locs = [loc.model_dump(mode="json") for loc in cf.locations]

            aggregated.append(
                AggregatedFinding(
                    id=cf.id,
                    case_id=case_id,
                    source_type="CONSISTENCY_FINDING",
                    source_id=cf.id,
                    category=cat,
                    evidentiary_classification=classification,
                    source_status=cf.status.value,
                    review_status=latest_status,
                    title=sanitize_display_label(cf.title, "CONSISTENCY_FINDING"),
                    description=cf.explanation,
                    explanation=f"Evaluated by rule {cf.rule_id} (outcome: {cf.outcome.value})",
                    severity=cf.severity,
                    confidence=cf.score,
                    affected_document_ids=list(cf.affected_document_ids),
                    supporting_evidence_ids=list(cf.supporting_evidence_ids),
                    contradicting_evidence_ids=list(cf.contradicting_evidence_ids),
                    locations=locs,
                    limitations=list(cf.limitations),
                    is_reviewed=is_reviewed,
                    review_history=cf_reviews,
                    created_at=cf.created_at,
                )
            )

        # 3. Relationship Anomalies (Contradicted or Duplicate records)
        for rel in detected_relationships:
            is_anomaly = bool(
                rel.status == RelationshipStatus.CONTRADICTED
                or rel.duplicate_kind is not None
                or rel.evidence.contradicting_signals
            )
            if not is_anomaly:
                continue

            rel_cat = (
                AggregatedFindingCategory.DUPLICATE_OR_CONFLICTING_RECORD
                if rel.duplicate_kind is not None
                else AggregatedFindingCategory.RELATIONSHIP_ANOMALY
            )

            is_reviewed = bool(rel.is_human_reviewed or rel.id in review_map)
            classification = (
                EvidentiaryClassification.INVESTIGATOR_CONCLUSION
                if is_reviewed
                else EvidentiaryClassification.ANALYTICAL_INTERPRETATION
            )

            rel_reviews = review_map.get(rel.id, [])
            latest_status = rel_reviews[-1].new_status if rel_reviews else rel.status.value

            doc_ids = []
            if rel.source_type == "DOCUMENT":
                doc_ids.append(rel.source_id)
            if rel.target_type == "DOCUMENT":
                doc_ids.append(rel.target_id)

            entity_ids = []
            if rel.source_type != "DOCUMENT":
                entity_ids.append(rel.source_id)
            if rel.target_type != "DOCUMENT":
                entity_ids.append(rel.target_id)

            severity = (
                FindingSeverity.HIGH
                if rel.status == RelationshipStatus.CONTRADICTED
                else FindingSeverity.MEDIUM
            )

            aggregated.append(
                AggregatedFinding(
                    id=rel.id,
                    case_id=case_id,
                    source_type="RELATIONSHIP_ANOMALY",
                    source_id=rel.id,
                    category=rel_cat,
                    evidentiary_classification=classification,
                    source_status=rel.status.value,
                    review_status=latest_status,
                    title=f"Relationship Anomaly: {rel.direction_display}",
                    description=rel.status_rationale,
                    explanation=f"Status: {rel.status.value} (determination method: {rel.status_determination_method.value})",
                    severity=severity,
                    confidence=rel.score,
                    affected_document_ids=doc_ids,
                    affected_entity_ids=entity_ids,
                    supporting_evidence_ids=list(rel.evidence.supporting_evidence_node_ids),
                    contradicting_evidence_ids=list(rel.evidence.contradicting_signals),
                    locations=[],
                    is_reviewed=is_reviewed,
                    review_history=rel_reviews,
                    created_at=rel.created_at,
                )
            )

        # 4. Entity Resolution Conflicts
        for match in entity_matches:
            is_conflict = bool(
                match.match_classification == EntityMatchClassification.CONFLICTING_IDENTITY
                or match.decision_status == MatchDecisionStatus.REJECTED
                or match.evidence.contradicting_signals
            )
            if not is_conflict:
                continue

            is_reviewed = bool(match.review_status.value != "UNREVIEWED" or match.id in review_map)
            classification = (
                EvidentiaryClassification.INVESTIGATOR_CONCLUSION
                if is_reviewed
                else EvidentiaryClassification.ANALYTICAL_INTERPRETATION
            )

            em_reviews = review_map.get(match.id, [])
            latest_status = em_reviews[-1].new_status if em_reviews else match.decision_status.value

            affected_docs = list(
                {match.evidence.target_document_id, match.evidence.candidate_document_id}
            )

            aggregated.append(
                AggregatedFinding(
                    id=match.id,
                    case_id=case_id,
                    source_type="ENTITY_IDENTITY_CONFLICT",
                    source_id=match.id,
                    category=AggregatedFindingCategory.ENTITY_IDENTITY_CONFLICT,
                    evidentiary_classification=classification,
                    source_status=match.decision_status.value,
                    review_status=latest_status,
                    title=f"Identity Conflict: '{match.target_value_display}' vs '{match.candidate_value_display}'",
                    description=f"Candidate match between mentions classified as {match.match_classification.value}",
                    explanation=f"Contradicting signals: {', '.join(match.evidence.contradicting_signals) if match.evidence.contradicting_signals else 'Identity divergence'}",
                    severity=FindingSeverity.HIGH,
                    confidence=match.match_score,
                    affected_document_ids=affected_docs,
                    supporting_evidence_ids=list(
                        match.evidence.target_evidence_node_ids
                        + match.evidence.candidate_evidence_node_ids
                    ),
                    contradicting_evidence_ids=list(match.evidence.contradicting_signals),
                    locations=[],
                    is_reviewed=is_reviewed,
                    review_history=em_reviews,
                    created_at=match.created_at,
                )
            )

        # Deterministic sort: Severity (CRITICAL > HIGH > MEDIUM > LOW > INFO), then Category, then ID
        _severity_order = {
            FindingSeverity.CRITICAL: 0,
            FindingSeverity.HIGH: 1,
            FindingSeverity.MEDIUM: 2,
            FindingSeverity.LOW: 3,
            FindingSeverity.INFO: 4,
        }
        aggregated.sort(
            key=lambda f: (
                _severity_order.get(f.severity, 5),
                f.category.value,
                f.id,
            )
        )

        return aggregated
