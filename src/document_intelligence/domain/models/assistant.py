"""Domain models for Grounded AI Investigation Assistant."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from document_intelligence.domain.enums import AssistantQuestionCategory

MANDATORY_AI_NOTICE = (
    "AI-generated investigative support output. Derived strictly from retrieved case records. "
    "Does not constitute an autonomous forensic determination, proof of fraud, or legal conclusion."
)


class EvidenceCitation(BaseModel):
    """Traceable citation pointing to an authoritative piece of evidence in the case."""

    citation_id: str = Field(description="Unique reference marker, e.g. cite_1, cite_2")
    case_id: str = Field(description="Case identifier")
    document_id: str | None = Field(default=None, description="Referenced document identifier")
    document_title: str | None = Field(
        default=None, description="Human-readable document title or filename"
    )
    evidence_id: str | None = Field(default=None, description="Referenced evidence node identifier")
    finding_id: str | None = Field(
        default=None, description="Referenced forensic or consistency finding identifier"
    )
    entity_id: str | None = Field(default=None, description="Referenced entity identifier")
    relationship_id: str | None = Field(
        default=None, description="Referenced relationship identifier"
    )
    source_subsystem: str = Field(
        default="forensics",
        description="Originating subsystem (e.g. forensics, consistency, extraction, ocr, relationship, review)",
    )
    page_number: int | None = Field(default=None, description="1-indexed document page number")
    bounding_box: dict[str, float] | None = Field(
        default=None, description="Normalized coordinates [x1, y1, x2, y2] if spatially grounded"
    )
    relevant_text: str | None = Field(
        default=None, description="Verbatim or summarized relevant text snippet"
    )
    target_route: str | None = Field(default=None, description="Frontend navigational deep link")


class AssistantMessage(BaseModel):
    """Message item in conversation history."""

    role: str = Field(description="Role: user or assistant")
    content: str = Field(description="Textual content of the message")


class AssistantQueryRequest(BaseModel):
    """Payload to submit an investigative query to the grounded AI assistant."""

    question: str = Field(min_length=1, max_length=2000, description="Investigator query or prompt")
    conversation_context: list[AssistantMessage] = Field(
        default_factory=list, description="Prior conversation history scoped to this case"
    )
    explicit_evidence_ids: list[str] = Field(
        default_factory=list,
        description="Optional list of specific evidence/finding IDs to focus on",
    )
    category_hint: AssistantQuestionCategory | None = Field(
        default=None, description="Optional investigative category classification hint"
    )
    reviewer_id: str = Field(
        default="investigator",
        min_length=1,
        max_length=100,
        description="Asserted user or examiner identifier",
    )


class AssistantQueryResponse(BaseModel):
    """Structured, evidence-grounded response conforming to EVIDEXA epistemic boundaries."""

    case_id: str
    question_category: AssistantQuestionCategory
    answer_text: str = Field(
        description="Factual, grounded narrative synthesized from retrieved case records"
    )
    citations: list[EvidenceCitation] = Field(
        default_factory=list,
        description="Traceable citations supporting statements in the response",
    )
    observed_facts: list[str] = Field(
        default_factory=list,
        description="Directly observed facts verified in documents or authoritative records",
    )
    automated_indicators: list[str] = Field(
        default_factory=list,
        description="Automated algorithmic signals, ELA heatmaps, or OCR heuristics",
    )
    analytical_interpretations: list[str] = Field(
        default_factory=list,
        description="System or statistical interpretations derived across documents",
    )
    contradictory_evidence: list[str] = Field(
        default_factory=list, description="Divergent or conflicting evidentiary points identified"
    )
    unresolved_questions: list[str] = Field(
        default_factory=list,
        description="Evidence gaps, missing records, or unconfirmed connections",
    )
    limitations: list[str] = Field(
        default_factory=list,
        description="Known heuristic limitations, OCR noise, or lack of corroboration",
    )
    follow_up_suggestions: list[str] = Field(
        default_factory=list,
        description="Optional evidence-grounded questions for investigator follow-up",
    )
    has_sufficient_evidence: bool = Field(
        default=True,
        description="Whether available case records were sufficient to answer without speculation",
    )
    ai_notice: str = Field(
        default=MANDATORY_AI_NOTICE, description="Mandatory non-verdict evidentiary disclaimer"
    )
    retrieval_stats: dict[str, Any] = Field(
        default_factory=dict,
        description="Metadata describing retrieved items count and search metrics",
    )
    model_name: str = Field(
        default="grounded-evidexa-engine", description="Identifier of the answering provider engine"
    )


class RetrievedCaseContext(BaseModel):
    """Bounded, case-isolated context assembled from authoritative repositories."""

    case_id: str
    case_title: str
    case_status: str
    documents: list[dict[str, Any]] = Field(default_factory=list)
    findings: list[dict[str, Any]] = Field(default_factory=list)
    consistency_findings: list[dict[str, Any]] = Field(default_factory=list)
    extracted_fields: list[dict[str, Any]] = Field(default_factory=list)
    entities: list[dict[str, Any]] = Field(default_factory=list)
    relationships: list[dict[str, Any]] = Field(default_factory=list)
    reviews: list[dict[str, Any]] = Field(default_factory=list)
    text_snippets: list[dict[str, Any]] = Field(default_factory=list)
    total_retrieved_items: int = 0
    unavailable_subsystems: list[str] = Field(default_factory=list)
