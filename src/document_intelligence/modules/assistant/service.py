"""Application service coordinating grounded retrieval, LLM synthesis, and citation verification."""

from __future__ import annotations

import json
import logging
import time
from typing import Any

from document_intelligence.domain.enums import (
    AssistantQuestionCategory,
    AuditEventType,
    EntityType,
)
from document_intelligence.domain.models.assistant import (
    MANDATORY_AI_NOTICE,
    AssistantQueryRequest,
    AssistantQueryResponse,
    EvidenceCitation,
)
from document_intelligence.modules.assistant.grounding import ClaimGroundingValidator
from document_intelligence.modules.assistant.prompts import (
    ASSISTANT_SYSTEM_INSTRUCTION,
    build_user_prompt,
)
from document_intelligence.modules.assistant.provider import LlmProviderProtocol
from document_intelligence.modules.assistant.retriever import CaseEvidenceRetriever
from document_intelligence.modules.audit.ledger import AuditLedgerService

logger = logging.getLogger(__name__)


class AssistantService:
    """Coordinates evidence retrieval, safety-bounded generation, and citation grounding."""

    def __init__(
        self,
        retriever: CaseEvidenceRetriever,
        provider: LlmProviderProtocol,
        audit_service: AuditLedgerService | None = None,
        grounding_validator: ClaimGroundingValidator | None = None,
    ) -> None:
        self.retriever = retriever
        self.provider = provider
        self.audit_service = audit_service
        self.grounding_validator = grounding_validator or ClaimGroundingValidator()

    def query(self, case_id: str, request: AssistantQueryRequest) -> AssistantQueryResponse:
        """Execute a grounded query over authoritative case evidence."""
        start_time = time.perf_counter()

        # 1. Retrieve authoritative context
        context = self.retriever.retrieve(
            case_id=case_id,
            question=request.question,
            explicit_evidence_ids=request.explicit_evidence_ids,
        )

        # 2. Build hardened user prompt
        history_dicts = [
            {"role": m.role, "content": m.content} for m in request.conversation_context
        ]
        user_prompt = build_user_prompt(
            question=request.question,
            context=context,
            category_hint=request.category_hint,
            conversation_history=history_dicts,
        )

        # 3. Invoke LLM provider with fault tolerance
        raw_output = ""
        provider_error: str | None = None
        try:
            raw_output = self.provider.generate(
                system_prompt=ASSISTANT_SYSTEM_INSTRUCTION,
                user_prompt=user_prompt,
            )
        except Exception as e:
            logger.warning("LLM provider execution failed: %s", e)
            provider_error = str(e)

        # 4. Parse output or build grounded fallback
        parsed_data: dict[str, Any] = {}
        if not provider_error and raw_output:
            try:
                clean_json = raw_output.strip()
                if clean_json.startswith("```json"):
                    clean_json = clean_json[7:]
                if clean_json.startswith("```"):
                    clean_json = clean_json[3:]
                if clean_json.endswith("```"):
                    clean_json = clean_json[:-3]
                parsed_data = json.loads(clean_json.strip())
            except Exception as json_err:
                logger.warning("Failed to parse LLM JSON output: %s", json_err)
                provider_error = f"Malformed model output: {json_err}"

        latency_ms = int((time.perf_counter() - start_time) * 1000)

        # 5. Handle fallback if provider failed or output was invalid
        if provider_error or not parsed_data:
            cat = request.category_hint or AssistantQuestionCategory.GENERAL_INQUIRY
            response = AssistantQueryResponse(
                case_id=case_id,
                question_category=cat,
                answer_text=(
                    f"Unable to complete generative synthesis: {provider_error or 'Empty response from model'}. "
                    f"Case contains {len(context.documents)} document(s) and {len(context.findings) + len(context.consistency_findings)} finding(s)."
                ),
                citations=[],
                observed_facts=[
                    f"Document: {d.get('declared_filename')}" for d in context.documents[:3]
                ],
                automated_indicators=[],
                analytical_interpretations=[],
                contradictory_evidence=[],
                unresolved_questions=["Model synthesis encountered an error or timeout."],
                limitations=[f"Provider error: {provider_error}"],
                follow_up_suggestions=[
                    "Please retry your question or consult the Findings Workbench."
                ],
                has_sufficient_evidence=False,
                ai_notice=MANDATORY_AI_NOTICE,
                retrieval_stats={
                    "total_retrieved": context.total_retrieved_items,
                    "provider_error": True,
                    "provider_name": self.provider.__class__.__name__,
                    "latency_ms": latency_ms,
                    "error_details": provider_error,
                },
            )
            eval_result = None
        else:
            # 6. Validate & Normalize Citations against actual retrieved evidence
            valid_doc_ids = {
                d.get("document_id") for d in context.documents if d.get("document_id")
            }
            valid_finding_ids = {
                f.get("finding_id") for f in context.findings if f.get("finding_id")
            } | {
                cf.get("finding_id") for cf in context.consistency_findings if cf.get("finding_id")
            }
            valid_rel_ids = {
                r.get("relationship_id") for r in context.relationships if r.get("relationship_id")
            }
            valid_ev_ids = {
                ev.get("evidence_id") for ev in context.extracted_fields if ev.get("evidence_id")
            } | {ev.get("evidence_id") for ev in context.text_snippets if ev.get("evidence_id")}

            validated_citations: list[EvidenceCitation] = []
            for raw_cite in parsed_data.get("citations", []):
                doc_id = raw_cite.get("document_id")
                finding_id = raw_cite.get("finding_id")
                rel_id = raw_cite.get("relationship_id")
                ev_id = raw_cite.get("evidence_id")

                is_grounded = bool(
                    (doc_id and doc_id in valid_doc_ids)
                    or (finding_id and finding_id in valid_finding_ids)
                    or (rel_id and rel_id in valid_rel_ids)
                    or (ev_id and ev_id in valid_ev_ids)
                )

                if not is_grounded:
                    continue

                target_route = None
                if doc_id:
                    target_route = f"/cases/{case_id}/documents/{doc_id}/examine"
                elif finding_id:
                    target_route = f"/cases/{case_id}/findings"
                elif rel_id:
                    target_route = f"/cases/{case_id}/graph"

                validated_citations.append(
                    EvidenceCitation(
                        citation_id=raw_cite.get(
                            "citation_id", f"cite_{len(validated_citations) + 1}"
                        ),
                        case_id=case_id,
                        document_id=doc_id,
                        document_title=raw_cite.get("document_title"),
                        evidence_id=ev_id,
                        finding_id=finding_id,
                        relationship_id=rel_id,
                        entity_id=raw_cite.get("entity_id"),
                        source_subsystem=raw_cite.get("source_subsystem", "forensics"),
                        page_number=raw_cite.get("page_number"),
                        bounding_box=raw_cite.get("bounding_box"),
                        relevant_text=raw_cite.get("relevant_text"),
                        target_route=target_route,
                    )
                )

            # Determine category safely
            cat_val = parsed_data.get("question_category")
            if isinstance(cat_val, str) and cat_val in AssistantQuestionCategory._value2member_map_:
                question_category = AssistantQuestionCategory(cat_val)
            else:
                question_category = (
                    request.category_hint or AssistantQuestionCategory.GENERAL_INQUIRY
                )

            initial_response = AssistantQueryResponse(
                case_id=case_id,
                question_category=question_category,
                answer_text=parsed_data.get("answer_text", "No response text generated."),
                citations=validated_citations,
                observed_facts=parsed_data.get("observed_facts", []),
                automated_indicators=parsed_data.get("automated_indicators", []),
                analytical_interpretations=parsed_data.get("analytical_interpretations", []),
                contradictory_evidence=parsed_data.get("contradictory_evidence", []),
                unresolved_questions=parsed_data.get("unresolved_questions", []),
                limitations=parsed_data.get("limitations", []),
                follow_up_suggestions=parsed_data.get("follow_up_suggestions", []),
                has_sufficient_evidence=bool(parsed_data.get("has_sufficient_evidence", True)),
                ai_notice=MANDATORY_AI_NOTICE,
            )

            # Run claim-level grounding and contradiction verification
            eval_result = self.grounding_validator.evaluate(
                response=initial_response,
                context=context,
                target_case_id=case_id,
            )

            # Filter citations to only verified ones
            valid_ids = {r.citation_id for r in eval_result.citation_reports if r.is_valid}
            verified_citations = [c for c in validated_citations if c.citation_id in valid_ids]

            limitations = list(initial_response.limitations)
            if eval_result.contradiction_omission_rate > 0:
                limitations.append(
                    "Notice: Unresolved contradictory evidence exists in case records that was not addressed in response."
                )
            if eval_result.contradicted_claims:
                limitations.append(
                    f"Warning: {len(eval_result.contradicted_claims)} claim(s) directly contradict authoritative case evidence."
                )
            if eval_result.unverified_claims:
                limitations.append(
                    f"Notice: {len(eval_result.unverified_claims)} claim(s) lack deterministic documentary support and require manual verification."
                )

            response = initial_response.model_copy(
                update={
                    "citations": verified_citations,
                    "limitations": limitations,
                    "retrieval_stats": {
                        "total_retrieved": context.total_retrieved_items,
                        "documents_count": len(context.documents),
                        "findings_count": len(context.findings),
                        "consistency_count": len(context.consistency_findings),
                        "valid_citations_count": len(verified_citations),
                        "latency_ms": latency_ms,
                        "provider_name": self.provider.__class__.__name__,
                        "citation_resolution_rate": eval_result.citation_resolution_rate,
                        "text_grounding_rate": eval_result.text_relevance_rate,
                        "claim_support_rate": eval_result.claim_support_rate,
                        "claim_unverified_rate": eval_result.claim_unverified_rate,
                        "claim_contradiction_rate": eval_result.claim_contradiction_rate,
                        "contradiction_omission_rate": eval_result.contradiction_omission_rate,
                        "is_faithful": eval_result.is_faithful,
                    },
                }
            )

        # 7. Audit Logging
        if self.audit_service:
            try:
                self.audit_service.record_event(
                    case_id=case_id,
                    event_type=AuditEventType.ASSISTANT_QUERY_EXECUTED,
                    entity_type=EntityType.ASSISTANT_SESSION,
                    entity_id=f"assistant-{case_id}",
                    payload={
                        "question_length": len(request.question),
                        "category": response.question_category.value,
                        "citations_count": len(response.citations),
                        "has_sufficient_evidence": response.has_sufficient_evidence,
                        "total_retrieved": context.total_retrieved_items,
                        "latency_ms": latency_ms,
                        "provider": self.provider.__class__.__name__,
                        "is_faithful": eval_result.is_faithful if eval_result else False,
                        "claim_support_rate": eval_result.claim_support_rate
                        if eval_result
                        else 0.0,
                        "citation_resolution_rate": eval_result.citation_resolution_rate
                        if eval_result
                        else 0.0,
                        "unverified_claims_count": len(eval_result.unverified_claims)
                        if eval_result
                        else 0,
                        "contradicted_claims_count": len(eval_result.contradicted_claims)
                        if eval_result
                        else 0,
                    },
                    actor_id=request.reviewer_id,
                )
            except Exception as audit_err:
                logger.warning("Failed to record assistant audit event: %s", audit_err)

        return response

    def get_context_summary(self, case_id: str) -> dict[str, Any]:
        """Provide a lightweight summary of available case evidence for assistant initialization."""
        context = self.retriever.retrieve(case_id=case_id, question="", max_documents=50)
        return {
            "case_id": context.case_id,
            "case_title": context.case_title,
            "case_status": context.case_status,
            "counts": {
                "documents": len(context.documents),
                "forensic_findings": len(context.findings),
                "consistency_findings": len(context.consistency_findings),
                "entities": len(context.entities),
                "relationships": len(context.relationships),
                "reviews": len(context.reviews),
                "total_items": context.total_retrieved_items,
            },
            "document_titles": [d["declared_filename"] for d in context.documents],
            "unavailable_subsystems": context.unavailable_subsystems,
        }
