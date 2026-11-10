"""Base contract for deterministic cross-document consistency rules."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from document_intelligence.domain.enums import (
    ConsistencyDetectionMethod,
    ConsistencyOutcome,
    DocumentClass,
    FindingCategory,
    FindingSeverity,
    FindingStatus,
)
from document_intelligence.domain.identifiers import generate_id, utc_now
from document_intelligence.domain.models.consistency import (
    ConsistencyComparison,
    ConsistencyEvidenceLocation,
    ConsistencyFinding,
)
from document_intelligence.domain.models.extraction import ExtractedFieldValue
from document_intelligence.modules.consistency.context import ConsistencyContext


class BaseConsistencyRule(ABC):
    """Abstract interface for a deterministic cross-document consistency rule."""

    @property
    @abstractmethod
    def rule_id(self) -> str:
        """Unique machine identifier for the rule."""
        pass

    @property
    @abstractmethod
    def rule_version(self) -> str:
        """Semantic version of the rule logic."""
        pass

    @property
    @abstractmethod
    def rule_name(self) -> str:
        """Human-readable display name for the rule."""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """Detailed technical summary of what this rule verifies."""
        pass

    @property
    @abstractmethod
    def supported_document_types(self) -> list[DocumentClass]:
        """Document classes this rule is capable of comparing."""
        pass

    @property
    def required_field_keys(self) -> list[str]:
        """Field keys typically required by this rule."""
        return []

    @property
    def category(self) -> FindingCategory:
        """Default category for findings emitted by this rule."""
        return FindingCategory.CROSS_DOCUMENT_MISMATCH

    @property
    def default_severity(self) -> FindingSeverity:
        """Default severity for inconsistent outcomes."""
        return FindingSeverity.MEDIUM

    @property
    def detection_method(self) -> ConsistencyDetectionMethod:
        """Method utilized by this rule."""
        return ConsistencyDetectionMethod.DETERMINISTIC_FIELD_COMPARISON

    @abstractmethod
    def evaluate(self, context: ConsistencyContext) -> list[ConsistencyFinding]:
        """Execute deterministic consistency checks across documents in the context."""
        pass

    def create_location_from_field(
        self,
        document_id: str,
        field: ExtractedFieldValue | None,
        fallback_field_key: str | None = None,
    ) -> ConsistencyEvidenceLocation:
        """Helper to create a traceable location from an extracted field value."""
        if field is None:
            return ConsistencyEvidenceLocation(
                document_id=document_id,
                field_key=fallback_field_key,
            )
        bbox = field.source_bounding_boxes[0] if field.source_bounding_boxes else None
        return ConsistencyEvidenceLocation(
            document_id=document_id,
            field_key=field.field_key,
            page_number=field.source_page_number,
            bounding_box=bbox,
            evidence_node_id=field.evidence_node_id,
            raw_value=field.raw_text,
            normalized_value=str(field.normalized_value)
            if field.normalized_value is not None
            else None,
        )

    def build_finding(
        self,
        context: ConsistencyContext,
        outcome: ConsistencyOutcome,
        title: str,
        explanation: str,
        affected_document_ids: list[str],
        compared_fields: list[str],
        original_values: dict[str, Any],
        normalized_values: dict[str, Any],
        locations: list[ConsistencyEvidenceLocation],
        comparisons: list[ConsistencyComparison],
        supporting_evidence_ids: list[str] | None = None,
        contradicting_evidence_ids: list[str] | None = None,
        severity: FindingSeverity | None = None,
        score: float = 1.0,
        score_semantics: str = "rule_deterministic_confidence",
        rule_parameters: dict[str, Any] | None = None,
        limitations: list[str] | None = None,
    ) -> ConsistencyFinding:
        """Construct a standardized ConsistencyFinding with complete evidence provenance."""
        resolved_severity = severity or (
            self.default_severity
            if outcome in (ConsistencyOutcome.INCONSISTENT, ConsistencyOutcome.POTENTIAL_ANOMALY)
            else FindingSeverity.INFO
        )

        return ConsistencyFinding(
            id=generate_id(),
            case_id=context.case_id,
            analysis_run_id=context.analysis_run_id,
            rule_id=self.rule_id,
            rule_version=self.rule_version,
            category=self.category,
            title=title,
            explanation=explanation,
            severity=resolved_severity,
            outcome=outcome,
            score=score,
            score_semantics=score_semantics,
            affected_document_ids=affected_document_ids,
            compared_fields=compared_fields,
            original_values=original_values,
            normalized_values=normalized_values,
            supporting_evidence_ids=supporting_evidence_ids or [],
            contradicting_evidence_ids=contradicting_evidence_ids or [],
            locations=locations,
            detection_method=self.detection_method,
            rule_parameters=rule_parameters or {},
            limitations=limitations
            or [
                "Analysis reflects extracted document data and does not assess external legal validity."
            ],
            status=FindingStatus.DETECTED,
            review_status="UNREVIEWED",
            is_human_reviewed=False,
            comparisons=comparisons,
            review_history=[],
            created_at=utc_now(),
            updated_at=utc_now(),
        )
