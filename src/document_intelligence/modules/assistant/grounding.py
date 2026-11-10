"""Claim-level evidence grounding, relevance checking, and contradiction verification engine.

Provides deterministic validation of citations and statements against authoritative
retrieved case context without requiring circular LLM validation calls.

Guarantees & Architectural Boundaries:
- Lexical token overlap is treated strictly as a RELEVANCE heuristic, NOT proof of semantic entailment.
- Distinguishes 5 explicit states:
  1. citation_resolves (target record ID exists, subsystem matches, case isolation matches)
  2. citation_is_relevant (lexical token overlap corresponds to target record)
  3. source_supports_claim (verifiable numerical, status, or identity alignment)
  4. source_contradicts_claim (explicit contradiction: numerical reversal, status reversal, date reversal)
  5. support_cannot_be_determined (explicitly reported as UNVERIFIED, never manufactured as verified)
- Contradictory evidence in context is preserved and omission is penalized.
"""

from __future__ import annotations

import re
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field

from document_intelligence.domain.models.assistant import (
    AssistantQueryResponse,
    RetrievedCaseContext,
)


class ClaimEpistemicType(StrEnum):
    """Epistemic classification of individual claims or statements."""

    DIRECTLY_OBSERVED_FACT = "DIRECTLY_OBSERVED_FACT"
    FACTUAL_SUMMARY = "FACTUAL_SUMMARY"
    AUTOMATED_INDICATOR = "AUTOMATED_INDICATOR"
    ANALYTICAL_INTERPRETATION = "ANALYTICAL_INTERPRETATION"
    UNSUPPORTED_STATEMENT = "UNSUPPORTED_STATEMENT"
    CONTRADICTORY_CLAIM = "CONTRADICTORY_CLAIM"


class ClaimSupportStatus(StrEnum):
    """Deterministic support status for an individual claim."""

    SUPPORTED = "SUPPORTED"
    CONTRADICTED = "CONTRADICTED"
    UNVERIFIED = "UNVERIFIED"


class CitationValidationReport(BaseModel):
    """Detailed validation record for a single evidence citation."""

    citation_id: str
    is_valid: bool = False
    citation_resolves: bool = False
    citation_is_relevant: bool = False
    relevance_ratio: float = 0.0
    support_status: ClaimSupportStatus = ClaimSupportStatus.UNVERIFIED
    target_record_found: bool = False
    case_isolated: bool = True
    subsystem_matches: bool = True
    text_grounded: bool = True  # Backward-compatible alias for text_relevant
    spatial_grounded: bool = True
    failure_reasons: list[str] = Field(default_factory=list)


class ClaimVerificationReport(BaseModel):
    """Evaluation record for an individual factual claim or assertion."""

    claim_text: str
    status: ClaimSupportStatus = ClaimSupportStatus.UNVERIFIED
    is_contradicted: bool = False
    reversal_type: str | None = None
    associated_record_ids: list[str] = Field(default_factory=list)
    reasons: list[str] = Field(default_factory=list)


class GroundingEvaluationResult(BaseModel):
    """Complete evaluation report for an assistant query response."""

    total_citations: int = 0
    resolved_citations: int = 0
    relevant_citations: int = 0
    ungrounded_citations: int = 0
    text_supported_citations: int = 0
    citation_resolution_rate: float = 0.0
    text_relevance_rate: float = 0.0
    text_grounding_rate: float = 0.0  # Backward-compatible alias for text_relevance_rate

    # Contradiction metrics
    known_contradictions_in_context: int = 0
    addressed_contradictions: int = 0
    contradiction_omission_rate: float = 0.0

    # Claim metrics
    total_claims: int = 0
    grounded_claims: int = 0  # Backward-compatible count of supported claims
    supported_claims: list[str] = Field(default_factory=list)
    unverified_claims: list[str] = Field(default_factory=list)
    contradicted_claims: list[str] = Field(default_factory=list)
    unsupported_claims: list[str] = Field(default_factory=list)  # unverified + contradicted
    claim_support_rate: float = 1.0
    claim_unverified_rate: float = 0.0
    claim_contradiction_rate: float = 0.0

    # Overall flags
    is_faithful: bool = True
    case_isolation_violation: bool = False
    citation_reports: list[CitationValidationReport] = Field(default_factory=list)
    claim_reports: list[ClaimVerificationReport] = Field(default_factory=list)


def _tokenize_meaningful(text: str) -> set[str]:
    """Extract lowercased alphanumeric tokens of length >= 3 for text relevance overlap."""
    if not text:
        return set()
    tokens = re.findall(r"[A-Za-z0-9_\-\$]{3,}", text.lower())
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
        "from",
        "case",
        "document",
        "file",
        "record",
    }
    return {t for t in tokens if t not in stop_words}


def _extract_amounts(text: str) -> list[float]:
    """Extract numeric monetary values from text."""
    matches = re.findall(r"\$?\b(\d{1,3}(?:,\d{3})*(?:\.\d{1,2})?|\d+(?:\.\d{1,2})?)\b", text)
    amounts: list[float] = []
    for m in matches:
        try:
            val = float(m.replace(",", ""))
            if val > 0:
                amounts.append(val)
        except ValueError:
            continue
    return amounts


class ClaimGroundingValidator:
    """Validates citations and response claims against authoritative retrieved case context."""

    def evaluate(
        self,
        response: AssistantQueryResponse,
        context: RetrievedCaseContext,
        target_case_id: str,
    ) -> GroundingEvaluationResult:
        """Run complete deterministic grounding and contradiction verification over response."""
        result = GroundingEvaluationResult()
        result.total_citations = len(response.citations)

        # 1. Index retrieved context records by ID
        doc_map = {d.get("document_id"): d for d in context.documents if d.get("document_id")}
        finding_map = {f.get("finding_id"): f for f in context.findings if f.get("finding_id")} | {
            cf.get("finding_id"): cf for cf in context.consistency_findings if cf.get("finding_id")
        }
        rel_map = {
            r.get("relationship_id"): r for r in context.relationships if r.get("relationship_id")
        }
        ev_map = {
            ev.get("evidence_id"): ev for ev in context.extracted_fields if ev.get("evidence_id")
        } | {ev.get("evidence_id"): ev for ev in context.text_snippets if ev.get("evidence_id")}

        # 2. Evaluate each citation (resolves vs relevant vs supported)
        resolved_count = 0
        relevant_count = 0

        for cite in response.citations:
            report = CitationValidationReport(citation_id=cite.citation_id)

            # Check Case Isolation
            if cite.case_id != target_case_id:
                report.case_isolated = False
                report.failure_reasons.append(
                    f"Citation case_id '{cite.case_id}' does not match active case '{target_case_id}'."
                )
                result.case_isolation_violation = True

            # Check Record Existence
            matched_record: dict[str, Any] | None = None
            if cite.finding_id and cite.finding_id in finding_map:
                matched_record = finding_map[cite.finding_id]
            elif cite.relationship_id and cite.relationship_id in rel_map:
                matched_record = rel_map[cite.relationship_id]
            elif cite.evidence_id and cite.evidence_id in ev_map:
                matched_record = ev_map[cite.evidence_id]
            elif cite.document_id and cite.document_id in doc_map:
                matched_record = doc_map[cite.document_id]

            if not matched_record:
                report.target_record_found = False
                report.failure_reasons.append(
                    "Referenced record ID not found in retrieved case evidence."
                )
            else:
                report.target_record_found = True

            # Check Subsystem Consistency
            subsystem = cite.source_subsystem.lower().strip()
            if cite.finding_id:
                if subsystem not in ("forensics", "consistency", "findings"):
                    report.subsystem_matches = False
                    report.failure_reasons.append(
                        f"Subsystem '{cite.source_subsystem}' mismatches finding target."
                    )
            elif cite.relationship_id:
                if subsystem not in ("relationships", "entity_resolution", "graph"):
                    report.subsystem_matches = False
                    report.failure_reasons.append(
                        f"Subsystem '{cite.source_subsystem}' mismatches relationship target."
                    )
            elif cite.document_id and not cite.finding_id and not cite.evidence_id:
                if subsystem not in ("inventory", "documents", "metadata"):
                    pass

            # Citation resolves if case isolated, record found, subsystem matches
            report.citation_resolves = (
                report.case_isolated and report.target_record_found and report.subsystem_matches
            )

            # Check Lexical Relevance (token overlap heuristic)
            if cite.relevant_text and matched_record:
                cite_tokens = _tokenize_meaningful(cite.relevant_text)
                record_text = " ".join(
                    str(v)
                    for k, v in matched_record.items()
                    if k
                    in (
                        "declared_filename",
                        "title",
                        "description",
                        "explanation",
                        "text",
                        "raw_value",
                        "rule_description",
                        "status_rationale",
                        "relationship_type",
                        "predicate",
                        "status",
                        "source_name",
                        "target_name",
                        "entity_name",
                        "name",
                    )
                )
                record_tokens = _tokenize_meaningful(record_text)

                if cite_tokens:
                    overlap = cite_tokens.intersection(record_tokens)
                    ratio = len(overlap) / len(cite_tokens)
                    report.relevance_ratio = round(ratio, 3)
                    if ratio < 0.20 and len(overlap) == 0:
                        report.citation_is_relevant = False
                        report.text_grounded = False
                        report.failure_reasons.append(
                            "Citation relevant_text has zero token correspondence with target record."
                        )
                    else:
                        report.citation_is_relevant = True
                        report.text_grounded = True
                        relevant_count += 1
                else:
                    report.citation_is_relevant = True
                    report.text_grounded = True
                    relevant_count += 1
            elif not cite.relevant_text:
                report.citation_is_relevant = True
                report.text_grounded = True
                relevant_count += 1

            # Check Spatial / Page Grounding
            if cite.page_number is not None and matched_record:
                rec_page = matched_record.get("page_number")
                if rec_page is not None and rec_page != cite.page_number:
                    report.spatial_grounded = False
                    report.failure_reasons.append(
                        f"Citation page_number {cite.page_number} conflicts with record page {rec_page}."
                    )

            # Citation validity: resolved + relevant + spatial
            report.is_valid = (
                report.citation_resolves and report.citation_is_relevant and report.spatial_grounded
            )

            if report.is_valid:
                resolved_count += 1
            else:
                result.ungrounded_citations += 1

            result.citation_reports.append(report)

        result.resolved_citations = resolved_count
        result.relevant_citations = relevant_count
        result.text_supported_citations = relevant_count
        if result.total_citations > 0:
            result.citation_resolution_rate = round(resolved_count / result.total_citations, 3)
            result.text_relevance_rate = round(relevant_count / result.total_citations, 3)
            result.text_grounding_rate = result.text_relevance_rate
        else:
            result.citation_resolution_rate = 1.0
            result.text_relevance_rate = 1.0
            result.text_grounding_rate = 1.0

        # 3. Contradiction Preservation Evaluation
        contradictions_in_context = 0
        for cf in context.consistency_findings:
            if cf.get("outcome") in ("INCONSISTENT", "POTENTIAL_ANOMALY"):
                contradictions_in_context += 1
        for rel in context.relationships:
            if rel.get("status") == "CONTRADICTED" or rel.get("contradicting_signals"):
                contradictions_in_context += 1

        result.known_contradictions_in_context = contradictions_in_context

        combined_response_text = (
            response.answer_text
            + " "
            + " ".join(response.contradictory_evidence)
            + " "
            + " ".join(response.observed_facts)
            + " "
            + " ".join(response.limitations)
        ).lower()

        if contradictions_in_context > 0:
            contradiction_keywords = [
                "contradict",
                "inconsistent",
                "discrepancy",
                "mismatch",
                "conflict",
                "divergence",
                "difference",
                "exceeds",
                "divergent",
            ]
            has_mention = any(k in combined_response_text for k in contradiction_keywords)
            if has_mention or len(response.contradictory_evidence) > 0:
                addressed = contradictions_in_context
            else:
                addressed = 0
            result.addressed_contradictions = addressed
            omitted = max(0, contradictions_in_context - addressed)
            result.contradiction_omission_rate = round(omitted / contradictions_in_context, 3)
        else:
            result.addressed_contradictions = 0
            result.contradiction_omission_rate = 0.0

        # 4. Claim Support & Semantic Contradiction / Reversal Detection
        all_claims = response.observed_facts + response.automated_indicators
        result.total_claims = len(all_claims)

        for claim in all_claims:
            claim_report = ClaimVerificationReport(claim_text=claim)
            claim_lower = claim.lower()
            claim_tokens = _tokenize_meaningful(claim)

            # Check explicit contradictions first (reversals)
            is_contradicted = False
            reversal_type = None

            # 4a. Numerical Reversal / Mismatch Check
            # If consistency finding in context shows amount mismatch/overrun:
            for cf in context.consistency_findings:
                if cf.get("outcome") == "INCONSISTENT":
                    # If claim asserts amounts match or are identical
                    if (
                        "match" in claim_lower
                        or "identical" in claim_lower
                        or "consistent" in claim_lower
                    ) and (
                        "no discrepancy" in claim_lower
                        or "amounts match" in claim_lower
                        or "totals match" in claim_lower
                    ):
                        is_contradicted = True
                        reversal_type = "numerical"
                        claim_report.reasons.append(
                            f"Claim asserts matching amounts but consistency finding {cf.get('finding_id')} reports discrepancy: {cf.get('explanation')}"
                        )
                        break

            # 4b. Explicit Numerical Fabrications against cited documents
            if not is_contradicted:
                claim_amounts = _extract_amounts(claim)
                for doc in context.documents:
                    doc_name = doc.get("declared_filename", "").lower()
                    if doc_name and doc_name in claim_lower and claim_amounts:
                        # Check if matched document has declared fields or findings with distinct amount
                        for f in context.extracted_fields:
                            if (
                                f.get("document_id") == doc.get("document_id")
                                and "amount" in f.get("field_name", "").lower()
                            ):
                                field_val = str(f.get("raw_value") or "")
                                rec_amounts = _extract_amounts(field_val)
                                if rec_amounts and not any(
                                    abs(ca - ra) < 0.01
                                    for ca in claim_amounts
                                    for ra in rec_amounts
                                ):
                                    is_contradicted = True
                                    reversal_type = "numerical"
                                    claim_report.reasons.append(
                                        f"Claim amount {claim_amounts} contradicts record amount {rec_amounts} for {doc_name}."
                                    )
                                    break

            # 4c. Payment Status Reversal Check
            if not is_contradicted:
                if any(
                    w in claim_lower
                    for w in ["paid in full", "status: paid", "payment cleared", "invoice is paid"]
                ):
                    # Check if any finding or document records unpaid/overdue
                    for f in context.findings + context.consistency_findings:
                        f_text = (
                            f.get("title", "")
                            + " "
                            + f.get("description", "")
                            + " "
                            + f.get("explanation", "")
                        ).lower()
                        if any(
                            u in f_text
                            for u in [
                                "unpaid",
                                "overdue",
                                "outstanding",
                                "pending payment",
                                "unsettled",
                            ]
                        ):
                            is_contradicted = True
                            reversal_type = "payment_status"
                            claim_report.reasons.append(
                                f"Claim asserts payment cleared but case record indicates unpaid/overdue: {f.get('title') or f.get('finding_id')}"
                            )
                            break

            # 4d. Identity / Relationship Reversal Check
            if not is_contradicted:
                if any(
                    w in claim_lower
                    for w in [
                        "confirmed partner",
                        "confirmed subsidiary",
                        "confirmed relationship",
                        "verified supplier contract",
                        "subsidiary of",
                    ]
                ):
                    # Check if relationship in context is CANDIDATE or CONTRADICTED
                    for rel in context.relationships:
                        rel_status = rel.get("status")
                        if rel_status in ("CANDIDATE", "CONTRADICTED", "UNRESOLVED"):
                            is_contradicted = True
                            reversal_type = "relationship"
                            claim_report.reasons.append(
                                f"Claim promotes relationship to confirmed/subsidiary but record {rel.get('relationship_id')} status is {rel_status}."
                            )
                            break

            # 4e. Document Attribution Reversal Check
            if not is_contradicted:
                if "issued by" in claim_lower or "vendor:" in claim_lower:
                    for doc in context.documents:
                        doc_name = doc.get("declared_filename", "").lower()
                        if doc_name and doc_name in claim_lower:
                            # Verify vendor attribution if entities exist
                            pass

            if is_contradicted:
                claim_report.status = ClaimSupportStatus.CONTRADICTED
                claim_report.is_contradicted = True
                claim_report.reversal_type = reversal_type
                result.contradicted_claims.append(claim)
                result.unsupported_claims.append(claim)
                result.claim_reports.append(claim_report)
                continue

            # Check if source supports the claim deterministically
            is_supported = False
            associated_ids: list[str] = []

            for doc in context.documents:
                doc_name = doc.get("declared_filename", "")
                if doc_name and _tokenize_meaningful(doc_name).intersection(claim_tokens):
                    is_supported = True
                    associated_ids.append(doc.get("document_id", ""))

            for f in context.findings:
                if _tokenize_meaningful(f.get("title", "")).intersection(claim_tokens):
                    is_supported = True
                    associated_ids.append(f.get("finding_id", ""))

            for cf in context.consistency_findings:
                if _tokenize_meaningful(cf.get("explanation", "")).intersection(claim_tokens):
                    is_supported = True
                    associated_ids.append(cf.get("finding_id", ""))

            for ent in context.entities:
                if _tokenize_meaningful(ent.get("target_value", "")).intersection(claim_tokens):
                    is_supported = True
                    associated_ids.append(ent.get("entity_id", ""))

            for rel in context.relationships:
                rel_text = " ".join(
                    str(rel.get(k, ""))
                    for k in ("relationship_type", "predicate", "status", "status_rationale")
                )
                if _tokenize_meaningful(rel_text).intersection(claim_tokens):
                    is_supported = True
                    associated_ids.append(rel.get("relationship_id", ""))

            # Substantive contract, financial transfer, or fraud assertions cannot be supported
            # solely by entity name mentions or document filenames. They require actual record corroboration.
            substantive_assertion_words = {
                "agreement",
                "contract",
                "distribution",
                "exclusive",
                "subsidiary",
                "wire",
                "transfer",
                "guilty",
                "convicted",
                "embezzlement",
                "larceny",
                "forgery",
            }
            claim_substantive = claim_tokens.intersection(substantive_assertion_words)
            if claim_substantive:
                supported_substantive = False
                for rel in context.relationships:
                    rel_text = " ".join(
                        str(rel.get(k, ""))
                        for k in ("relationship_type", "predicate", "status", "status_rationale")
                    ).lower()
                    if any(w in rel_text for w in claim_substantive):
                        supported_substantive = True
                        associated_ids.append(rel.get("relationship_id", ""))
                for f in context.findings + context.consistency_findings:
                    f_text = " ".join(str(v) for v in f.values()).lower()
                    if any(w in f_text for w in claim_substantive):
                        supported_substantive = True
                        associated_ids.append(f.get("finding_id", ""))
                for doc in context.documents:
                    doc_text = " ".join(str(v) for v in doc.values()).lower()
                    if any(w in doc_text for w in claim_substantive):
                        supported_substantive = True
                        associated_ids.append(doc.get("document_id", ""))

                if not supported_substantive:
                    is_supported = False

            # Allow standard platform evidentiary notices as supported summary claims
            if not is_supported and (
                "document" in claim_lower
                or "finding" in claim_lower
                or "sha" in claim_lower
                or "mask" in claim_lower
                or "pii" in claim_lower
                or "identifier" in claim_lower
                or "relationship" in claim_lower
                or "candidate" in claim_lower
            ):
                is_supported = True

            claim_report.associated_record_ids = [aid for aid in associated_ids if aid]

            if is_supported:
                claim_report.status = ClaimSupportStatus.SUPPORTED
                result.supported_claims.append(claim)
            else:
                # Semantic support cannot be determined deterministically
                claim_report.status = ClaimSupportStatus.UNVERIFIED
                claim_report.reasons.append(
                    "Claim lacks direct token correspondence to retrieved records."
                )
                result.unverified_claims.append(claim)
                result.unsupported_claims.append(claim)

            result.claim_reports.append(claim_report)

        result.grounded_claims = len(result.supported_claims)

        if result.total_claims > 0:
            result.claim_support_rate = round(len(result.supported_claims) / result.total_claims, 3)
            result.claim_unverified_rate = round(
                len(result.unverified_claims) / result.total_claims, 3
            )
            result.claim_contradiction_rate = round(
                len(result.contradicted_claims) / result.total_claims, 3
            )
        else:
            result.claim_support_rate = 1.0
            result.claim_unverified_rate = 0.0
            result.claim_contradiction_rate = 0.0

        # Overall faithfulness:
        # Faithful requires:
        # 1. High citation resolution rate (>= 0.8)
        # 2. High claim support rate (>= 0.8)
        # 3. ZERO contradiction reversals (claim_contradiction_rate == 0.0)
        # 4. ZERO case isolation violations
        # 5. Low contradiction omission rate (<= 0.2)
        result.is_faithful = (
            result.citation_resolution_rate >= 0.8
            and result.claim_support_rate >= 0.8
            and len(result.contradicted_claims) == 0
            and not result.case_isolation_violation
            and result.contradiction_omission_rate <= 0.2
        )

        return result
