"""Deterministic relationship detection engine orchestrating detectors and entity resolution inputs."""

from __future__ import annotations

import logging
import time

from document_intelligence.domain.enums import (
    EntityMatchClassification,
    MatchDecisionStatus,
    RelationshipStatus,
    RelationshipType,
)
from document_intelligence.domain.models.relationship import (
    DetectedRelationship,
    RelationshipDetectionResult,
)
from document_intelligence.modules.relationship_detection.detectors.bank_statement import (
    BankStatementRelationshipDetector,
)
from document_intelligence.modules.relationship_detection.detectors.base import (
    BaseRelationshipDetector,
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

logger = logging.getLogger(__name__)

ALL_RELATIONSHIP_TYPES = [t.value for t in RelationshipType]


class RelationshipDetectionEngine:
    """Orchestrates deterministic detectors, entity-resolution inputs, and contradiction precedence."""

    def __init__(
        self,
        detectors: list[BaseRelationshipDetector] | None = None,
        max_relationships: int = 1000,
    ) -> None:
        self.detectors: list[BaseRelationshipDetector] = detectors or [
            InvoiceRelationshipDetector(),
            ReceiptRelationshipDetector(),
            BankStatementRelationshipDetector(),
            EntityRoleRelationshipDetector(),
            DocumentRelationshipDetector(),
        ]
        self.max_relationships = max_relationships
        self.engine_version = "2.0.0"
        self.ontology_version = "2.0"

    def detect_relationships(self, context: DetectionContext) -> RelationshipDetectionResult:
        """Run all registered detectors and apply entity resolution and contradiction rules."""
        start_time = time.perf_counter()
        raw_relationships: list[DetectedRelationship] = []

        # 1. Execute each detector independently
        for detector in self.detectors:
            try:
                rels = detector.detect(context)
                raw_relationships.extend(rels)
            except Exception as e:
                logger.error("Detector %s failed: %s", detector.detector_name, e, exc_info=True)

        # 2. Integrate Entity Resolution Safeguards & Evidentiary Invariants
        processed_relationships = self._apply_entity_resolution_safeguards(
            raw_relationships, context
        )

        # 3. Deduplicate relationships by (relationship_type, source_id, target_id)
        deduped = self._deduplicate_relationships(processed_relationships)

        # 4. Enforce bounds
        if len(deduped) > self.max_relationships:
            logger.warning(
                "Relationship count %d exceeded bound %d. Truncating.",
                len(deduped),
                self.max_relationships,
            )
            deduped = deduped[: self.max_relationships]

        duration_ms = (time.perf_counter() - start_time) * 1000.0

        # Summarize by type and status
        summary_by_type: dict[str, int] = {}
        summary_by_status: dict[str, int] = {}
        for r in deduped:
            summary_by_type[r.relationship_type.value] = (
                summary_by_type.get(r.relationship_type.value, 0) + 1
            )
            summary_by_status[r.status.value] = summary_by_status.get(r.status.value, 0) + 1

        detected_types = set(summary_by_type.keys())
        unsupported = [t for t in ALL_RELATIONSHIP_TYPES if t not in detected_types]

        return RelationshipDetectionResult(
            case_id=context.case_id,
            detection_run_id=context.detection_run_id,
            ontology_version=self.ontology_version,
            relationships=deduped,
            summary_by_type=summary_by_type,
            summary_by_status=summary_by_status,
            unsupported_relationship_types=unsupported,
            detection_duration_ms=round(duration_ms, 2),
        )

    def _apply_entity_resolution_safeguards(
        self,
        relationships: list[DetectedRelationship],
        context: DetectionContext,
    ) -> list[DetectedRelationship]:
        """Apply entity match constraints: conflicting identities block relationships, weak matches cannot confirm."""
        rejected_entity_targets: set[str] = set()
        conflicting_entity_targets: set[str] = set()
        weak_entity_targets: set[str] = set()

        for match in context.candidate_matches:
            if match.decision_status == MatchDecisionStatus.REJECTED:
                rejected_entity_targets.add(match.target_value_display.lower())
                rejected_entity_targets.add(match.candidate_value_display.lower())
            elif match.match_classification == EntityMatchClassification.CONFLICTING_IDENTITY:
                conflicting_entity_targets.add(match.target_value_display.lower())
                conflicting_entity_targets.add(match.candidate_value_display.lower())
            elif match.match_classification == EntityMatchClassification.WEAK_AMBIGUOUS:
                weak_entity_targets.add(match.target_value_display.lower())
                weak_entity_targets.add(match.candidate_value_display.lower())

        adjusted: list[DetectedRelationship] = []
        for rel in relationships:
            src_str = rel.source_label.lower()
            tgt_str = rel.target_label.lower()

            # Rule 1: Rejected entity matches must not create new confirmed relationships
            if (
                src_str in rejected_entity_targets or tgt_str in rejected_entity_targets
            ) and rel.status == RelationshipStatus.CONFIRMED:
                rel.status = RelationshipStatus.REJECTED
                rel.status_rationale += " Suppressed due to human-rejected entity resolution match."
                rel.evidence.contradicting_signals.append(
                    "Participating entity has an active REJECTED decision status."
                )
                rel.score = 0.0
                rel.evidence.status = RelationshipStatus.REJECTED
                rel.evidence.score = 0.0

            # Rule 2: Conflicting entity identity matches block unsupported relationship formation
            elif src_str in conflicting_entity_targets or tgt_str in conflicting_entity_targets:
                rel.status = RelationshipStatus.CONTRADICTED
                rel.status_rationale += (
                    " Suppressed due to conflicting identity detected during entity resolution."
                )
                rel.evidence.contradicting_signals.append(
                    "Entity resolution flagged CONFLICTING_IDENTITY."
                )
                rel.score = 0.0
                rel.evidence.status = RelationshipStatus.CONTRADICTED
                rel.evidence.score = 0.0

            # Rule 3: Weak ambiguous entity matches must not be silently promoted to confirmed
            elif (
                src_str in weak_entity_targets or tgt_str in weak_entity_targets
            ) and rel.status == RelationshipStatus.CONFIRMED:
                rel.status = RelationshipStatus.CANDIDATE
                rel.status_rationale += (
                    " Demoted to CANDIDATE because participating entity match is weak/ambiguous."
                )
                rel.evidence.contradicting_signals.append(
                    "Weak entity match cannot substantiate confirmed relationship."
                )
                rel.score = min(rel.score, 0.65)
                rel.evidence.status = RelationshipStatus.CANDIDATE
                rel.evidence.score = rel.score

            adjusted.append(rel)

        return adjusted

    def _deduplicate_relationships(
        self, relationships: list[DetectedRelationship]
    ) -> list[DetectedRelationship]:
        """Deduplicate relationships with same type, source, and target, preserving status precedence."""
        seen: dict[tuple[str, str, str], DetectedRelationship] = {}

        # Status precedence ranking: CONTRADICTED is authoritative evidence of conflict,
        # CONFIRMED requires explicit evidence or human confirmation.
        status_rank = {
            RelationshipStatus.CONTRADICTED: 5,
            RelationshipStatus.REJECTED: 4,
            RelationshipStatus.CONFIRMED: 3,
            RelationshipStatus.CANDIDATE: 2,
            RelationshipStatus.UNRESOLVED: 1,
        }

        for r in relationships:
            key = (r.relationship_type.value, r.source_id, r.target_id)
            if key not in seen:
                seen[key] = r
            else:
                existing = seen[key]
                existing_rank = status_rank.get(existing.status, 0)
                new_rank = status_rank.get(r.status, 0)

                if new_rank > existing_rank:
                    seen[key] = r
                elif new_rank == existing_rank and r.score > existing.score:
                    seen[key] = r

        return list(seen.values())
