"""Entity role relationship detector for corporate representation and organizational relationships."""

from __future__ import annotations

import re

from document_intelligence.domain.enums import (
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

ROLE_EXPLICIT_REGEX = re.compile(
    r"\b([A-Z][a-zA-Z\.\s]{2,40}?)\s*,\s*(Director|CEO|Chief Executive Officer|Officer|Authorized Signatory|President|Managing Director|Partner|General Counsel)\s*(?:of|at|for)\s*([A-Z0-9\.\s&,]{3,60}?)(?:\.|\n|\r|$)",
    re.IGNORECASE,
)
ROLE_PREFIX_REGEX = re.compile(
    r"\b(Director|CEO|Chief Executive Officer|Officer|Authorized Signatory|President|Managing Director|Partner|General Counsel)[:\s]+([A-Z][a-zA-Z\.\s]{2,40})",
    re.IGNORECASE,
)


class EntityRoleRelationshipDetector(BaseRelationshipDetector):
    """Detects corporate representation and affiliation relationships between persons and organizations."""

    @property
    def detector_name(self) -> str:
        return "entity_role_relationship_detector"

    @property
    def detector_version(self) -> str:
        return "2.0.0"

    def detect(self, context: DetectionContext) -> list[DetectedRelationship]:
        relationships: list[DetectedRelationship] = []
        docs_by_id = {d.id: d for d in context.documents}

        for doc_id, text in context.raw_document_texts.items():
            doc = docs_by_id.get(doc_id)
            doc_label = f"Document '{doc.original_filename}'" if doc else doc_id

            # 1. Search for explicit role statements: "John Doe, Director of Acme Corp"
            found_explicit = False
            for match in ROLE_EXPLICIT_REGEX.finditer(text):
                person_name = match.group(1).strip()
                role_title = match.group(2).strip()
                org_name = match.group(3).strip()

                person_id = f"PERSON:{person_name.upper()}"
                org_id = f"ORG:{org_name.upper()}"

                found_explicit = True
                rep_rel = DetectedRelationship(
                    id=generate_id(),
                    case_id=context.case_id,
                    detection_run_id=context.detection_run_id,
                    relationship_type=RelationshipType.REPRESENTS,
                    ontology_version="2.0",
                    source_id=person_id,
                    source_type="PERSON",
                    source_label=person_name,
                    target_id=org_id,
                    target_type="ORGANIZATION",
                    target_label=org_name,
                    direction_display=f"{person_name} --REPRESENTS--> {org_name}",
                    status=RelationshipStatus.CONFIRMED,
                    status_determination_method=StatusDeterminationMethod.EVIDENTIARY_RULE,
                    score=0.95,
                    score_semantics="evidence_strength",
                    detection_method=RelationshipDetectionMethod.ROLE_REPRESENTATION_RULE,
                    detection_version=self.detector_version,
                    status_rationale=f"Explicit corporate representation: '{person_name}' is stated as {role_title} of '{org_name}'.",
                    evidence=RelationshipEvidence(
                        relationship_type=RelationshipType.REPRESENTS,
                        ontology_version="2.0",
                        source_id=person_id,
                        target_id=org_id,
                        source_case_id=context.case_id,
                        source_field_keys=["role_statement"],
                        supporting_evidence_node_ids=[],
                        source_page_references=[1],
                        bounding_boxes=[],
                        detection_method=RelationshipDetectionMethod.ROLE_REPRESENTATION_RULE,
                        detection_version=self.detector_version,
                        matching_signals=[
                            f"Explicit role clause: '{person_name}' acts as {role_title} for '{org_name}'"
                        ],
                        contradicting_signals=[],
                        score=0.95,
                        score_semantics="evidence_strength",
                        status=RelationshipStatus.CONFIRMED,
                        status_determination_method=StatusDeterminationMethod.EVIDENTIARY_RULE,
                        status_rationale="Explicit legal/corporate role statement found.",
                    ),
                    created_at=utc_now(),
                    updated_at=utc_now(),
                )
                relationships.append(rep_rel)

            # 2. Check for co-occurrence without explicit role:
            # If doc has person mentions and org mentions but no explicit role connecting them:
            if not found_explicit:
                doc_persons = [
                    m
                    for m in context.entity_mentions
                    if m.document_id == doc_id and m.entity_type.value == "PERSON"
                ]
                doc_orgs = [
                    m
                    for m in context.entity_mentions
                    if m.document_id == doc_id and m.entity_type.value == "ORGANIZATION"
                ]

                for p in doc_persons:
                    for org in doc_orgs:
                        person_name = p.original_value
                        org_name = org.original_value
                        person_id = f"PERSON:{person_name.upper()}"
                        org_id = f"ORG:{org_name.upper()}"

                        cooccur_rel = DetectedRelationship(
                            id=generate_id(),
                            case_id=context.case_id,
                            detection_run_id=context.detection_run_id,
                            relationship_type=RelationshipType.REPRESENTS,
                            ontology_version="2.0",
                            source_id=person_id,
                            source_type="PERSON",
                            source_label=person_name,
                            target_id=org_id,
                            target_type="ORGANIZATION",
                            target_label=org_name,
                            direction_display=f"{person_name} --REPRESENTS--> {org_name}",
                            status=RelationshipStatus.UNRESOLVED,
                            status_determination_method=StatusDeterminationMethod.EVIDENTIARY_RULE,
                            score=0.25,
                            score_semantics="similarity_score",
                            detection_method=RelationshipDetectionMethod.ROLE_REPRESENTATION_RULE,
                            detection_version=self.detector_version,
                            status_rationale=(
                                f"Person '{person_name}' and organization '{org_name}' co-occur within {doc_label}, "
                                "but lack explicit representation or employment evidence. Name co-occurrence alone does not establish representation."
                            ),
                            evidence=RelationshipEvidence(
                                relationship_type=RelationshipType.REPRESENTS,
                                ontology_version="2.0",
                                source_id=person_id,
                                target_id=org_id,
                                source_case_id=context.case_id,
                                source_field_keys=[],
                                supporting_evidence_node_ids=p.supporting_evidence_node_ids,
                                source_page_references=[p.page_number] if p.page_number else [1],
                                bounding_boxes=p.bounding_boxes,
                                detection_method=RelationshipDetectionMethod.ROLE_REPRESENTATION_RULE,
                                detection_version=self.detector_version,
                                matching_signals=[f"Co-occurrence within document {doc_label}"],
                                contradicting_signals=[
                                    "Absence of explicit role, title, or representation clause"
                                ],
                                score=0.25,
                                score_semantics="similarity_score",
                                status=RelationshipStatus.UNRESOLVED,
                                status_determination_method=StatusDeterminationMethod.EVIDENTIARY_RULE,
                                status_rationale="Name co-occurrence without role evidence.",
                            ),
                            created_at=utc_now(),
                            updated_at=utc_now(),
                        )
                        relationships.append(cooccur_rel)

        return relationships
