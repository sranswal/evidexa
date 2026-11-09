"""Normalizer converting AnalyzerOutput observations into platform EvidenceNode and ForensicFinding entities."""

import json

from document_intelligence.domain.enums import (
    EvidenceType,
    FindingCategory,
    FindingSeverity,
    FindingStatus,
)
from document_intelligence.domain.models.evidence_node import EvidenceNode
from document_intelligence.domain.models.forensic_finding import ForensicFinding
from document_intelligence.modules.forensics.schemas.analyzer_output import (
    AnalyzerObservation,
    AnalyzerOutput,
)

SEVERITY_MAP: dict[str, FindingSeverity] = {
    "info": FindingSeverity.INFO,
    "low": FindingSeverity.LOW,
    "medium": FindingSeverity.MEDIUM,
    "high": FindingSeverity.HIGH,
    "critical": FindingSeverity.CRITICAL,
}

CATEGORY_MAP: dict[str, FindingCategory] = {
    "structure": FindingCategory.PDF_STRUCTURE,
    "revisions": FindingCategory.PDF_STRUCTURE,
    "signatures": FindingCategory.IDENTITY_VALIDATION,
    "pdfsig": FindingCategory.IDENTITY_VALIDATION,
    "metadata": FindingCategory.DOCUMENT_INCONSISTENCY,
    "content": FindingCategory.PDF_STRUCTURE,
    "active_content": FindingCategory.PDF_STRUCTURE,
    "fingerprint": FindingCategory.DOCUMENT_INCONSISTENCY,
    "timeline": FindingCategory.DOCUMENT_INCONSISTENCY,
    "visual_ela": FindingCategory.VISUAL_ANOMALY,
    "visual_copymove": FindingCategory.DUPLICATE_CONTENT,
    "visual_region": FindingCategory.VISUAL_ANOMALY,
    "ocr_text": FindingCategory.DOCUMENT_INCONSISTENCY,
    "ocr_table": FindingCategory.DOCUMENT_INCONSISTENCY,
    "ocr_layout": FindingCategory.DOCUMENT_INCONSISTENCY,
}


class ForensicResultNormalizer:
    """Normalizes raw analyzer observations into domain EvidenceNode and ForensicFinding entities."""

    def normalize(
        self,
        output: AnalyzerOutput,
        case_id: str,
        document_id: str,
        processing_run_id: str,
    ) -> tuple[list[EvidenceNode], list[ForensicFinding], list[tuple[str, str]]]:
        """Convert AnalyzerOutput into domain models and association links.

        Returns:
            Tuple of (evidence_nodes, findings, finding_evidence_link_pairs)
        """
        evidence_nodes: list[EvidenceNode] = []
        findings: list[ForensicFinding] = []
        links: list[tuple[str, str]] = []

        for obs in output.observations:
            # 1. Create underlying EvidenceNode
            evidence = self._create_evidence_node(
                obs=obs,
                case_id=case_id,
                document_id=document_id,
                processing_run_id=processing_run_id,
                analyzer_id=output.analyzer_id,
                analyzer_version=output.analyzer_version,
            )
            evidence_nodes.append(evidence)

            # 2. Create supporting ForensicFinding
            finding = self._create_finding(
                obs=obs,
                case_id=case_id,
                document_id=document_id,
                processing_run_id=processing_run_id,
                analyzer_id=output.analyzer_id,
                supporting_evidence_id=evidence.id,
            )
            findings.append(finding)

            # 3. Relational association link
            links.append((finding.id, evidence.id))

        return evidence_nodes, findings, links

    def _create_evidence_node(
        self,
        obs: AnalyzerObservation,
        case_id: str,
        document_id: str,
        processing_run_id: str,
        analyzer_id: str,
        analyzer_version: str,
    ) -> EvidenceNode:
        # Determine evidence type
        if obs.observation_type in ("visual_ela", "visual_copymove", "visual_region"):
            etype = EvidenceType.VISUAL_REGION
        elif obs.observation_type == "metadata":
            etype = EvidenceType.METADATA
        elif obs.observation_type in ("ocr_text", "ocr_page"):
            etype = EvidenceType.OCR_TEXT
        elif obs.observation_type == "ocr_table":
            etype = EvidenceType.TABLE
        elif obs.observation_type == "ocr_layout":
            etype = EvidenceType.LAYOUT_REGION
        elif obs.observation_type == "ocr_token":
            etype = EvidenceType.TEXT_TOKEN
        else:
            etype = EvidenceType.PDF_STRUCTURAL

        # Preserve bounding box if present, otherwise None (do not manufacture)
        coord_sys = obs.coordinate_system
        if coord_sys is None and obs.bounding_box is not None:
            coord_sys = obs.bounding_box.coordinate_system

        raw_val = None
        if obs.evidence_payload:
            try:
                raw_val = json.dumps(obs.evidence_payload, sort_keys=True)
            except (TypeError, ValueError):
                raw_val = str(obs.evidence_payload)

        return EvidenceNode(
            case_id=case_id,
            document_id=document_id,
            processing_run_id=processing_run_id,
            evidence_type=etype,
            title=f"Observation: {obs.title}",
            description=obs.description or obs.title,
            source_component=analyzer_id,
            source_version=analyzer_version,
            page_number=obs.page_number,
            bounding_box=obs.bounding_box,
            coordinate_system=coord_sys,
            pdf_object_reference=obs.pdf_object_reference,
            byte_offset_start=obs.byte_offset_start,
            byte_offset_end=obs.byte_offset_end,
            raw_value=raw_val,
            normalized_value=obs.observed_value,
            categorical_confidence=obs.categorical_confidence,
            confidence_source=obs.confidence_source or analyzer_id,
            confidence=obs.confidence,
            metadata={
                "capability_id": obs.capability_id,
                "evidence_payload": obs.evidence_payload,
                "benign_explanations": obs.benign_explanations,
            },
        )

    def _create_finding(
        self,
        obs: AnalyzerObservation,
        case_id: str,
        document_id: str,
        processing_run_id: str,
        analyzer_id: str,
        supporting_evidence_id: str,
    ) -> ForensicFinding:
        severity = SEVERITY_MAP.get(obs.severity.lower(), FindingSeverity.INFO)
        category = CATEGORY_MAP.get(obs.observation_type.lower(), FindingCategory.PDF_STRUCTURE)

        return ForensicFinding(
            case_id=case_id,
            document_id=document_id,
            processing_run_id=processing_run_id,
            category=category,
            title=obs.title,
            description=obs.description or obs.title,
            severity=severity,
            categorical_confidence=obs.categorical_confidence,
            confidence_source=obs.confidence_source or analyzer_id,
            confidence_calibration_method="categorical_uncalibrated"
            if obs.confidence is None
            else "calibrated",
            confidence=obs.confidence,
            status=FindingStatus.DETECTED,
            evidence_ids=[supporting_evidence_id],
            source_component=analyzer_id,
            limitations=list(
                obs.benign_explanations
                or [
                    "Preliminary technical observation.",
                    "Requires human review in context before reaching investigative conclusions.",
                ]
            ),
            metadata={
                "capability_id": obs.capability_id,
                "evidence_payload": obs.evidence_payload,
            },
        )
