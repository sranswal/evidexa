"""Document relationship detector for duplicates, amendments, and supporting exhibits."""

from __future__ import annotations

import re

from document_intelligence.domain.enums import (
    DuplicateKind,
    RelationshipDetectionMethod,
    RelationshipStatus,
    RelationshipType,
    StatusDeterminationMethod,
)
from document_intelligence.domain.identifiers import generate_id, utc_now
from document_intelligence.domain.models.relationship import (
    DetectedRelationship,
    RelationshipEvidence,
)
from document_intelligence.modules.relationship_detection.detectors.base import (
    BaseRelationshipDetector,
    DetectionContext,
)

SUPPORTING_DOC_REGEX = re.compile(
    r"\b(?:exhibit|attachment|appendix|schedule|annexure)\s*([A-Za-z0-9\-_]+)",
    re.IGNORECASE,
)
AMENDMENT_DOC_REGEX = re.compile(
    r"\b(?:amendment\s*(?:to|no)?|amends|supersedes|revision\s*(?:of|to)?)\s*([A-Za-z0-9\-_/]+)",
    re.IGNORECASE,
)


class DocumentRelationshipDetector(BaseRelationshipDetector):
    """Detects duplicate document hash equality, explicit amendments, and supporting attachments."""

    @property
    def detector_name(self) -> str:
        return "document_relationship_detector"

    @property
    def detector_version(self) -> str:
        return "2.0.0"

    def detect(self, context: DetectionContext) -> list[DetectedRelationship]:
        relationships: list[DetectedRelationship] = []
        docs = context.documents

        # 1. Duplicate Documents via Cryptographic SHA-256 Hash Equality & Byte Identity
        for i in range(len(docs)):
            for j in range(i + 1, len(docs)):
                doc_a = docs[i]
                doc_b = docs[j]

                label_a = f"Document '{doc_a.original_filename}'"
                label_b = f"Document '{doc_b.original_filename}'"

                # Byte-identical document identity: identical SHA-256 digests
                if doc_a.sha256 == doc_b.sha256:
                    dup_rel = DetectedRelationship(
                        id=generate_id(),
                        case_id=context.case_id,
                        detection_run_id=context.detection_run_id,
                        relationship_type=RelationshipType.DUPLICATE_OF,
                        ontology_version="2.0",
                        duplicate_kind=DuplicateKind.BYTE_IDENTICAL,
                        source_id=doc_b.id,
                        source_type="DOCUMENT",
                        source_label=label_b,
                        target_id=doc_a.id,
                        target_type="DOCUMENT",
                        target_label=label_a,
                        direction_display=f"{label_b} --DUPLICATE_OF--> {label_a}",
                        status=RelationshipStatus.CONFIRMED,
                        status_determination_method=StatusDeterminationMethod.EVIDENTIARY_RULE,
                        score=1.0,
                        score_semantics="evidence_strength",
                        detection_method=RelationshipDetectionMethod.DOCUMENT_HASH_EQUALITY,
                        detection_version=self.detector_version,
                        status_rationale=(
                            f"Identical SHA-256 digest ({doc_a.sha256[:16]}...) indicates byte-identical "
                            f"document content between '{doc_b.original_filename}' and '{doc_a.original_filename}'."
                        ),
                        evidence=RelationshipEvidence(
                            relationship_type=RelationshipType.DUPLICATE_OF,
                            ontology_version="2.0",
                            duplicate_kind=DuplicateKind.BYTE_IDENTICAL,
                            source_id=doc_b.id,
                            target_id=doc_a.id,
                            source_case_id=context.case_id,
                            source_field_keys=["sha256"],
                            supporting_evidence_node_ids=[],
                            source_page_references=[1],
                            bounding_boxes=[],
                            detection_method=RelationshipDetectionMethod.DOCUMENT_HASH_EQUALITY,
                            detection_version=self.detector_version,
                            matching_signals=[
                                f"Exact SHA-256 digest equality: {doc_a.sha256}",
                                "Byte-identical file content established",
                            ],
                            contradicting_signals=[],
                            score=1.0,
                            score_semantics="evidence_strength",
                            status=RelationshipStatus.CONFIRMED,
                            status_determination_method=StatusDeterminationMethod.EVIDENTIARY_RULE,
                            status_rationale="Exact SHA-256 digest equality establishes byte-identical document.",
                        ),
                        created_at=utc_now(),
                        updated_at=utc_now(),
                    )
                    relationships.append(dup_rel)

                # Different SHA-256 hashes but similar filename / semantic duplicate candidate
                elif doc_a.original_filename.lower() == doc_b.original_filename.lower() or (
                    len(doc_a.original_filename) > 8
                    and doc_a.original_filename.lower() in doc_b.original_filename.lower()
                ):
                    candidate_rel = DetectedRelationship(
                        id=generate_id(),
                        case_id=context.case_id,
                        detection_run_id=context.detection_run_id,
                        relationship_type=RelationshipType.DUPLICATE_OF,
                        ontology_version="2.0",
                        duplicate_kind=DuplicateKind.UNRESOLVED_DUPLICATE_CANDIDATE,
                        source_id=doc_b.id,
                        source_type="DOCUMENT",
                        source_label=label_b,
                        target_id=doc_a.id,
                        target_type="DOCUMENT",
                        target_label=label_a,
                        direction_display=f"{label_b} --DUPLICATE_OF--> {label_a}",
                        status=RelationshipStatus.CANDIDATE,
                        status_determination_method=StatusDeterminationMethod.EVIDENTIARY_RULE,
                        score=0.60,
                        score_semantics="similarity_heuristic",
                        detection_method=RelationshipDetectionMethod.SEMANTIC_SIMILARITY_HEURISTIC,
                        detection_version=self.detector_version,
                        status_rationale=(
                            f"Documents '{doc_b.original_filename}' and '{doc_a.original_filename}' share similar names, "
                            f"but have distinct SHA-256 digests ({doc_b.sha256[:8]}... vs {doc_a.sha256[:8]}...). "
                            "Retained as CANDIDATE requiring investigator review."
                        ),
                        evidence=RelationshipEvidence(
                            relationship_type=RelationshipType.DUPLICATE_OF,
                            ontology_version="2.0",
                            duplicate_kind=DuplicateKind.UNRESOLVED_DUPLICATE_CANDIDATE,
                            source_id=doc_b.id,
                            target_id=doc_a.id,
                            source_case_id=context.case_id,
                            source_field_keys=["filename"],
                            supporting_evidence_node_ids=[],
                            source_page_references=[1],
                            bounding_boxes=[],
                            detection_method=RelationshipDetectionMethod.SEMANTIC_SIMILARITY_HEURISTIC,
                            detection_version=self.detector_version,
                            matching_signals=[
                                f"Filename similarity between '{doc_b.original_filename}' and '{doc_a.original_filename}'"
                            ],
                            contradicting_signals=[
                                f"Distinct SHA-256 digests: {doc_b.sha256[:16]}... vs {doc_a.sha256[:16]}..."
                            ],
                            score=0.60,
                            score_semantics="similarity_heuristic",
                            status=RelationshipStatus.CANDIDATE,
                            status_determination_method=StatusDeterminationMethod.EVIDENTIARY_RULE,
                            status_rationale="Name similarity with distinct byte digests requires review.",
                        ),
                        created_at=utc_now(),
                        updated_at=utc_now(),
                    )
                    relationships.append(candidate_rel)

        # 2. Explicit Amendments and Supporting Document References
        for doc in docs:
            raw_text = context.raw_document_texts.get(doc.id, "")
            label_doc = f"Document '{doc.original_filename}'"

            # Check explicit amendment
            amend_match = AMENDMENT_DOC_REGEX.search(raw_text)
            if amend_match:
                ref_id = amend_match.group(1).strip()
                for other_doc in docs:
                    if other_doc.id != doc.id and (
                        ref_id.lower() in other_doc.original_filename.lower()
                        or ref_id.lower() in other_doc.id.lower()
                    ):
                        label_other = f"Document '{other_doc.original_filename}'"
                        amend_rel = DetectedRelationship(
                            id=generate_id(),
                            case_id=context.case_id,
                            detection_run_id=context.detection_run_id,
                            relationship_type=RelationshipType.AMENDS_DOCUMENT,
                            ontology_version="2.0",
                            source_id=doc.id,
                            source_type="DOCUMENT",
                            source_label=label_doc,
                            target_id=other_doc.id,
                            target_type="DOCUMENT",
                            target_label=label_other,
                            direction_display=f"{label_doc} --AMENDS_DOCUMENT--> {label_other}",
                            status=RelationshipStatus.CONFIRMED,
                            status_determination_method=StatusDeterminationMethod.EVIDENTIARY_RULE,
                            score=0.95,
                            score_semantics="evidence_strength",
                            detection_method=RelationshipDetectionMethod.EXPLICIT_DOCUMENT_REFERENCE,
                            detection_version=self.detector_version,
                            status_rationale=f"Document explicitly references prior version '{other_doc.original_filename}'.",
                            evidence=RelationshipEvidence(
                                relationship_type=RelationshipType.AMENDS_DOCUMENT,
                                ontology_version="2.0",
                                source_id=doc.id,
                                target_id=other_doc.id,
                                source_case_id=context.case_id,
                                source_field_keys=["amendment_reference"],
                                supporting_evidence_node_ids=[],
                                source_page_references=[1],
                                bounding_boxes=[],
                                detection_method=RelationshipDetectionMethod.EXPLICIT_DOCUMENT_REFERENCE,
                                detection_version=self.detector_version,
                                matching_signals=[f"Explicit amendment reference '{ref_id}'"],
                                contradicting_signals=[],
                                score=0.95,
                                score_semantics="evidence_strength",
                                status=RelationshipStatus.CONFIRMED,
                                status_determination_method=StatusDeterminationMethod.EVIDENTIARY_RULE,
                                status_rationale="Explicit document amendment reference.",
                            ),
                            created_at=utc_now(),
                            updated_at=utc_now(),
                        )
                        relationships.append(amend_rel)

            # Check explicit supporting attachment / exhibit
            sup_match = SUPPORTING_DOC_REGEX.search(raw_text)
            if sup_match:
                exhibit_id = sup_match.group(1).strip()
                for other_doc in docs:
                    if other_doc.id != doc.id and (
                        exhibit_id.lower() in other_doc.original_filename.lower()
                        or "exhibit" in other_doc.original_filename.lower()
                    ):
                        label_other = f"Document '{other_doc.original_filename}'"
                        sup_rel = DetectedRelationship(
                            id=generate_id(),
                            case_id=context.case_id,
                            detection_run_id=context.detection_run_id,
                            relationship_type=RelationshipType.SUPPORTS_DOCUMENT,
                            ontology_version="2.0",
                            source_id=other_doc.id,
                            source_type="DOCUMENT",
                            source_label=label_other,
                            target_id=doc.id,
                            target_type="DOCUMENT",
                            target_label=label_doc,
                            direction_display=f"{label_other} --SUPPORTS_DOCUMENT--> {label_doc}",
                            status=RelationshipStatus.CONFIRMED,
                            status_determination_method=StatusDeterminationMethod.EVIDENTIARY_RULE,
                            score=0.90,
                            score_semantics="evidence_strength",
                            detection_method=RelationshipDetectionMethod.EXPLICIT_DOCUMENT_REFERENCE,
                            detection_version=self.detector_version,
                            status_rationale=f"Document '{other_doc.original_filename}' attached as exhibit '{exhibit_id}' to '{doc.original_filename}'.",
                            evidence=RelationshipEvidence(
                                relationship_type=RelationshipType.SUPPORTS_DOCUMENT,
                                ontology_version="2.0",
                                source_id=other_doc.id,
                                target_id=doc.id,
                                source_case_id=context.case_id,
                                source_field_keys=["exhibit_reference"],
                                supporting_evidence_node_ids=[],
                                source_page_references=[1],
                                bounding_boxes=[],
                                detection_method=RelationshipDetectionMethod.EXPLICIT_DOCUMENT_REFERENCE,
                                detection_version=self.detector_version,
                                matching_signals=[
                                    f"Explicit attachment/exhibit citation '{exhibit_id}'"
                                ],
                                contradicting_signals=[],
                                score=0.90,
                                score_semantics="evidence_strength",
                                status=RelationshipStatus.CONFIRMED,
                                status_determination_method=StatusDeterminationMethod.EVIDENTIARY_RULE,
                                status_rationale="Explicit supporting document reference.",
                            ),
                            created_at=utc_now(),
                            updated_at=utc_now(),
                        )
                        relationships.append(sup_rel)

        return relationships
