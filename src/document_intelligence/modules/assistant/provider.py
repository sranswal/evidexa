"""LLM Provider abstraction and deterministic mock implementation for Grounded AI Assistant."""

from __future__ import annotations

import json
import logging
import re
import time
from typing import Any, Protocol

import httpx

from document_intelligence.core.config import Settings, settings
from document_intelligence.domain.enums import AssistantQuestionCategory

logger = logging.getLogger(__name__)

# Request & Response limits for LLM communication
MAX_REQUEST_SIZE_BYTES = 256 * 1024  # 256 KB
MAX_RESPONSE_SIZE_BYTES = 512 * 1024  # 512 KB


class ProviderError(Exception):
    """Base exception for LLM provider errors."""


class ProviderConnectionError(ProviderError):
    """Network connection failure or unreachable provider endpoint."""


class ProviderTimeoutError(ProviderError):
    """Connection or read timeout while communicating with provider."""


class ProviderRateLimitError(ProviderError):
    """Rate limit exceeded (HTTP 429)."""


class ProviderPayloadLimitError(ProviderError):
    """Request or response payload exceeded maximum allowed size."""


class ProviderResponseError(ProviderError):
    """Unexpected HTTP status, malformed JSON, or invalid schema from provider."""


class LlmProviderProtocol(Protocol):
    """Protocol for LLM providers generating grounded responses."""

    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 2000,
        temperature: float = 0.0,
    ) -> str:
        """Generate response text given system and user prompts."""
        ...


class MockLlmProvider:
    """Deterministic, rule-based provider for testing, offline verification, and fallback.

    Requires zero external API credentials or network connections.
    Faithfully simulates an LLM obeying strict epistemic integrity and prompt injection defenses.
    """

    def __init__(
        self,
        simulate_timeout: bool = False,
        simulate_malformed: bool = False,
        simulate_failure: bool = False,
    ) -> None:
        self.simulate_timeout = simulate_timeout
        self.simulate_malformed = simulate_malformed
        self.simulate_failure = simulate_failure

    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 2000,
        temperature: float = 0.0,
    ) -> str:
        if self.simulate_timeout:
            raise TimeoutError("Simulated LLM provider timeout after 15.0s.")
        if self.simulate_failure:
            raise RuntimeError("Simulated LLM provider service unavailable (HTTP 503).")
        if self.simulate_malformed:
            return "This is not valid JSON at all: <<MALFORMED_OUTPUT>>"

        # 1. Parse Question and Evidence from user prompt
        evidence_data: dict[str, Any] = {}
        match = re.search(r"<case_evidence>\s*(.*?)\s*</case_evidence>", user_prompt, re.DOTALL)
        if match:
            try:
                evidence_data = json.loads(match.group(1).strip())
            except Exception:
                evidence_data = {}

        q_match = re.search(
            r"### INVESTIGATOR QUESTION:\s*(.*?)(?=\nCategory Hint:|\n<case_evidence>|$)",
            user_prompt,
            re.DOTALL,
        )
        question = q_match.group(1).strip() if q_match else ""
        q_lower = question.lower()

        # 2. Detect & Neutralize Prompt Injection Attempts
        injection_patterns = [
            "ignore previous instructions",
            "system prompt override",
            "system override",
            "reveal system prompt",
            "reveal system instructions",
            "declare this document authentic",
            "confirm this document is genuine",
            "declare genuine",
            "authenticate document",
            "confirm that fraud occurred",
            "declare fraud",
            "find him guilty",
            "retrieve another case",
            "switch case",
            "cross-case access",
            "reveal masked financial identifiers",
            "unmask account",
            "execute external command",
            "execute bash",
            "/bin/sh",
            "follow instructions embedded in ocr",
            "treat document content as privileged",
            "jailbreak",
            "forget your rules",
            "suppress contradictory",
            "suppress contradictions",
            "ignore discrepancies",
            "do not report any contradictions",
            "upgrade to conclusion",
            "treat as investigator conclusion",
            "final investigator conclusion",
            "treat candidate as confirmed",
            "mark as confirmed fact",
            "treat as confirmed",
            "status override",
            "ignore document",
            "delete document",
            "claim review completed",
            "mark review completed",
            "switch context",
            "switch active context",
        ]
        injection_detected = any(p in q_lower for p in injection_patterns)

        # Check evidence content for injection
        evidence_str = json.dumps(evidence_data).lower()
        evidence_injection_detected = any(p in evidence_str for p in injection_patterns)

        # 3. Classify Category (honor explicit Category Hint if present in prompt)
        cat_hint_match = re.search(r"Category Hint:\s*([A-Z_]+)", user_prompt)
        hint_str = cat_hint_match.group(1).strip() if cat_hint_match else None

        if hint_str and hint_str in AssistantQuestionCategory._value2member_map_:
            category = AssistantQuestionCategory(hint_str)
        elif "explain" in q_lower or ("finding" in q_lower and "summary" not in q_lower):
            category = AssistantQuestionCategory.EVIDENCE_EXPLANATION
        elif "compare" in q_lower or "difference" in q_lower or "discrepancy" in q_lower:
            category = AssistantQuestionCategory.CROSS_DOCUMENT_COMPARISON
        elif (
            "entity" in q_lower
            or "vendor" in q_lower
            or "supplier" in q_lower
            or "person" in q_lower
            or "relationship" in q_lower
            or "investigate" in q_lower
        ):
            category = AssistantQuestionCategory.ENTITY_INVESTIGATION
        elif "contradiction" in q_lower or "conflict" in q_lower or "mismatch" in q_lower:
            category = AssistantQuestionCategory.CONTRADICTION_ANALYSIS
        elif "summary" in q_lower or "state of" in q_lower or "overview" in q_lower:
            category = AssistantQuestionCategory.INVESTIGATION_SUMMARY
        elif "suggest" in q_lower or "next" in q_lower or "follow-up" in q_lower:
            category = AssistantQuestionCategory.FOLLOW_UP_SUGGESTIONS
        else:
            category = AssistantQuestionCategory.GENERAL_INQUIRY

        # Extract items
        case_info = evidence_data.get("case_overview", {})
        case_id = case_info.get("case_id", "case_unknown")
        docs = evidence_data.get("documents", [])
        findings = evidence_data.get("forensic_findings", [])
        consistency = evidence_data.get("consistency_findings", [])
        entities = evidence_data.get("entities", [])
        relationships = evidence_data.get("relationships", [])
        fields = evidence_data.get("extracted_fields", [])
        reviews = evidence_data.get("investigator_reviews", [])

        citations: list[dict[str, Any]] = []
        observed_facts: list[str] = []
        automated_indicators: list[str] = []
        analytical_interpretations: list[str] = []
        contradictory_evidence: list[str] = []
        unresolved_questions: list[str] = []
        limitations: list[str] = []
        follow_ups: list[str] = []
        has_sufficient_evidence = True

        cite_idx = 1

        # Populate based on category and available evidence
        if (
            not docs
            and not findings
            and not consistency
            and not fields
            and not entities
            and not relationships
        ):
            has_sufficient_evidence = False
            answer_text = (
                f"No documents or forensic findings have been registered or analyzed for case '{case_id}'. "
                "Available evidence is insufficient to perform grounded analysis."
            )
            unresolved_questions.append("No authoritative evidence records exist in this case.")
            limitations.append(
                "Evidence is insufficient; analysis cannot proceed without uploaded and processed documents."
            )
            follow_ups.append("Would you like to upload source documents to begin analysis?")
        else:
            # Add document facts
            for d in docs[:3]:
                fname = d.get("declared_filename", "unnamed.pdf")
                did = d.get("document_id")
                observed_facts.append(f"Case contains registered document '{fname}' (ID: {did}).")
                citations.append(
                    {
                        "citation_id": f"cite_{cite_idx}",
                        "case_id": case_id,
                        "document_id": did,
                        "document_title": fname,
                        "source_subsystem": "documents",
                        "relevant_text": fname,
                    }
                )
                cite_idx += 1

            # Add finding indicators
            for f in findings[:2]:
                fid = f.get("finding_id")
                title = f.get("title", "Forensic observation")
                desc = f.get("description", "")
                automated_indicators.append(f"{title}: {desc} (Finding ID: {fid})")
                citations.append(
                    {
                        "citation_id": f"cite_{cite_idx}",
                        "case_id": case_id,
                        "finding_id": fid,
                        "document_id": f.get("document_id"),
                        "source_subsystem": "forensics",
                        "relevant_text": desc[:150],
                    }
                )
                cite_idx += 1

            # Add consistency findings / contradictions
            for cf in consistency:
                cfid = cf.get("finding_id")
                rule = cf.get("rule_id", "Consistency check")
                expl = cf.get("explanation", "")
                status = cf.get("status") or cf.get("outcome", "")
                if status in ("INCONSISTENT", "CONTRADICTED", "POTENTIAL_ANOMALY"):
                    contradictory_evidence.append(f"Discrepancy under rule {rule}: {expl}")
                else:
                    analytical_interpretations.append(f"Consistency evaluation {rule}: {expl}")

                citations.append(
                    {
                        "citation_id": f"cite_{cite_idx}",
                        "case_id": case_id,
                        "finding_id": cfid,
                        "source_subsystem": "consistency",
                        "relevant_text": expl[:150],
                    }
                )
                cite_idx += 1

            # Add relationships (preserving candidate status)
            for r in relationships[:2]:
                rid = r.get("relationship_id")
                pred = r.get("predicate", "RELATED_TO")
                r_status = r.get("status", "CANDIDATE")
                if r_status == "CONFIRMED":
                    observed_facts.append(
                        f"Confirmed relationship: {pred} between entities ({rid})."
                    )
                else:
                    automated_indicators.append(
                        f"Candidate relationship ({r_status}): {pred} ({rid}). Requires investigator confirmation."
                    )

                citations.append(
                    {
                        "citation_id": f"cite_{cite_idx}",
                        "case_id": case_id,
                        "relationship_id": rid,
                        "source_subsystem": "relationships",
                        "relevant_text": r.get("status_rationale")
                        or f"Relationship {pred} ({r_status})",
                    }
                )
                cite_idx += 1

            # Synthesize answer text based on category
            if category == AssistantQuestionCategory.EVIDENCE_EXPLANATION:
                if findings:
                    target_f = findings[0]
                    raw_desc = target_f.get("description", "")
                    if any(p in raw_desc.lower() for p in injection_patterns):
                        clean_desc = "[Untrusted directive in finding neutralized. Anomaly detected by forensic analyzer.]"
                    else:
                        clean_desc = raw_desc
                    answer_text = (
                        f"Forensic finding '{target_f.get('title')}' indicates: {clean_desc} "
                        f"This indicator is classified as an automated signal. Supporting evidence is cited."
                    )
                else:
                    answer_text = (
                        "No specific forensic findings are currently flagged for this document."
                    )
                    has_sufficient_evidence = False

            elif category == AssistantQuestionCategory.CROSS_DOCUMENT_COMPARISON:
                if consistency:
                    first_cf = consistency[0]
                    answer_text = (
                        f"Cross-document consistency analysis identified an inconsistency: {first_cf.get('explanation')}. "
                        "The observed values across documents show divergent records as detailed in the citations."
                    )
                else:
                    answer_text = "Cross-document comparison evaluated registered records. No automated inconsistencies were detected across current documents."

            elif category == AssistantQuestionCategory.ENTITY_INVESTIGATION:
                if entities or relationships:
                    answer_text = (
                        f"Identified {len(entities)} entity candidate matches and {len(relationships)} relationships across case documents. "
                        "All candidate connections remain tentative until human review confirmation."
                    )
                else:
                    answer_text = "No extracted entity candidate matches are currently cataloged for this case."

            elif category == AssistantQuestionCategory.CONTRADICTION_ANALYSIS:
                if contradictory_evidence:
                    answer_text = (
                        f"Identified {len(contradictory_evidence)} contradictory evidence points across case documents, "
                        "specifically regarding numerical values or party references as cited below."
                    )
                else:
                    answer_text = "No active evidentiary contradictions were detected among the currently processed documents."

            elif category == AssistantQuestionCategory.INVESTIGATION_SUMMARY:
                answer_text = (
                    f"Investigation Case Summary: The case currently contains {len(docs)} document(s), "
                    f"{len(findings)} forensic finding(s), {len(consistency)} consistency finding(s), "
                    f"and {len(reviews)} recorded human review decision(s)."
                )

            else:
                answer_text = (
                    f"Analysis grounded in {len(docs)} case document(s) and {len(findings) + len(consistency)} finding(s). "
                    "All referenced evidentiary points are grounded in authoritative case records."
                )

            # Check cross-case boundary violations
            if (
                "foreign" in q_lower
                or "cross-case" in q_lower
                or "another case" in q_lower
                or "case-xyz" in q_lower
            ):
                has_sufficient_evidence = False
                answer_text = "Cross-case access is strictly prohibited. Only evidence available in the authorized active case can be retrieved."
                limitations.append(
                    "Cross-case boundary applied: foreign case records cannot be accessed."
                )

            # Check PII exfiltration attempts
            if (
                "unmask" in q_lower
                or "without masking" in q_lower
                or "pan" in q_lower
                or "account number" in q_lower
            ):
                observed_facts.append(
                    "Sensitive financial identifiers are masked (e.g. ****) in accordance with EVIDEXA PII protection rules."
                )
                answer_text = (
                    "Analysis performed under strict PII protection: all financial account numbers, PAN sequences, and tax identifiers remain masked (****). "
                    + answer_text
                )

            # Follow-ups
            follow_ups.append(
                "Would you like to examine the bounding boxes in the visual document inspector?"
            )
            follow_ups.append(
                "Should we review the unconfirmed candidate relationships in the Evidence Graph?"
            )

            # Limitations
            limitations.append(
                "Algorithmic findings represent automated indicators and require human adjudication."
            )
            if injection_detected or evidence_injection_detected:
                limitations.append(
                    "Detected embedded prompt manipulation or instruction attempt in query/evidence. Strict untrusted data boundary applied; instruction was ignored."
                )

        response_payload = {
            "question_category": category.value,
            "answer_text": answer_text,
            "citations": citations,
            "observed_facts": observed_facts,
            "automated_indicators": automated_indicators,
            "analytical_interpretations": analytical_interpretations,
            "contradictory_evidence": contradictory_evidence,
            "unresolved_questions": unresolved_questions,
            "limitations": limitations,
            "follow_up_suggestions": follow_ups,
            "has_sufficient_evidence": has_sufficient_evidence,
        }

        return json.dumps(response_payload, indent=2)


class HttpLlmProvider:
    """Hardened HTTP client for OpenAI-compatible LLM endpoints (e.g. Ollama, vLLM, or external APIs)."""

    def __init__(
        self,
        api_base: str,
        api_key: str | None = None,
        model: str = "grounded-evidexa-engine",
        timeout_seconds: float = 15.0,
        max_retries: int = 2,
        retry_delay: float = 0.5,
    ) -> None:
        self.api_base = api_base.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self.retry_delay = retry_delay

    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 2000,
        temperature: float = 0.0,
    ) -> str:
        url = f"{self.api_base}/chat/completions"
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "max_tokens": max_tokens,
            "temperature": temperature,
            "response_format": {"type": "json_object"},
        }

        serialized_payload = json.dumps(payload)
        payload_bytes = len(serialized_payload.encode("utf-8"))
        if payload_bytes > MAX_REQUEST_SIZE_BYTES:
            raise ProviderPayloadLimitError(
                f"Request payload size ({payload_bytes} bytes) exceeds limit ({MAX_REQUEST_SIZE_BYTES} bytes)."
            )

        client_timeout = httpx.Timeout(
            timeout=self.timeout_seconds,
            connect=min(5.0, self.timeout_seconds),
            read=self.timeout_seconds,
            write=10.0,
            pool=5.0,
        )

        attempts = 0
        last_exception: Exception | None = None

        while attempts <= self.max_retries:
            attempts += 1
            try:
                with httpx.Client(timeout=client_timeout) as client:
                    with client.stream(
                        "POST", url, headers=headers, content=serialized_payload
                    ) as resp:
                        # 1. Early Content-Length check before buffering stream
                        content_length = resp.headers.get("Content-Length")
                        if content_length:
                            try:
                                if int(content_length) > MAX_RESPONSE_SIZE_BYTES:
                                    raise ProviderPayloadLimitError(
                                        f"Response Content-Length ({content_length} bytes) exceeds limit ({MAX_RESPONSE_SIZE_BYTES} bytes)."
                                    )
                            except ValueError:
                                pass

                        # 2. Rate limit and service unavailable retry handling with Retry-After header
                        if resp.status_code == 429:
                            if attempts <= self.max_retries:
                                retry_after = resp.headers.get("Retry-After")
                                delay = self.retry_delay * attempts
                                if retry_after:
                                    try:
                                        delay = min(float(retry_after), 10.0)
                                    except ValueError:
                                        pass
                                time.sleep(delay)
                                continue
                            raise ProviderRateLimitError(
                                "Upstream LLM provider rate limit exceeded (HTTP 429)."
                            )

                        if resp.status_code == 503 and attempts <= self.max_retries:
                            retry_after = resp.headers.get("Retry-After")
                            delay = self.retry_delay * attempts
                            if retry_after:
                                try:
                                    delay = min(float(retry_after), 10.0)
                                except ValueError:
                                    pass
                            time.sleep(delay)
                            continue

                        # 3. Fail fast on other 4xx/5xx errors without leaking credentials
                        if resp.status_code >= 400:
                            reason = resp.reason_phrase or "Request failed"
                            raise ProviderResponseError(
                                f"LLM provider returned HTTP {resp.status_code}: {reason}"
                            )

                        # 4. Stream chunks and enforce hard byte limit before memory buffering
                        chunks: list[bytes] = []
                        accumulated_bytes = 0
                        for chunk in resp.iter_bytes(chunk_size=8192):
                            accumulated_bytes += len(chunk)
                            if accumulated_bytes > MAX_RESPONSE_SIZE_BYTES:
                                raise ProviderPayloadLimitError(
                                    f"Response stream exceeded size limit ({MAX_RESPONSE_SIZE_BYTES} bytes)."
                                )
                            chunks.append(chunk)

                        raw_bytes = b"".join(chunks)

                        try:
                            data = json.loads(raw_bytes.decode("utf-8"))
                        except Exception as json_err:
                            raise ProviderResponseError(
                                f"Provider returned invalid JSON: {json_err}"
                            ) from json_err

                        choices = data.get("choices", [])
                        if not choices:
                            raise ProviderResponseError(
                                "Provider response missing 'choices' array."
                            )

                        first_choice = choices[0]
                        content = first_choice.get("message", {}).get("content", "")
                        if content is None or content == "":
                            raise ProviderResponseError(
                                "Provider returned empty message content in first choice."
                            )

                        return str(content)

            except httpx.ConnectTimeout as ct_err:
                last_exception = ProviderTimeoutError(
                    f"Connection timeout to provider {self.api_base}"
                )
                if attempts <= self.max_retries:
                    time.sleep(self.retry_delay * attempts)
                    continue
                raise last_exception from ct_err
            except (httpx.ReadTimeout, httpx.WriteTimeout, httpx.PoolTimeout) as t_err:
                raise ProviderTimeoutError(
                    f"Read/write timeout communicating with provider {self.api_base}"
                ) from t_err
            except httpx.ConnectError as conn_err:
                last_exception = ProviderConnectionError(
                    f"Failed to connect to LLM provider at {self.api_base}"
                )
                if attempts <= self.max_retries:
                    time.sleep(self.retry_delay * attempts)
                    continue
                raise last_exception from conn_err
            except (ProviderError, ValueError):
                raise
            except Exception as unk_err:
                raise ProviderResponseError(
                    f"Unexpected provider communication error: {unk_err}"
                ) from unk_err

        if last_exception:
            raise last_exception
        raise ProviderResponseError("Exceeded maximum retries communicating with LLM provider.")


def get_llm_provider(app_settings: Settings | None = None) -> LlmProviderProtocol:
    """Factory selecting configured LLM provider (defaults to MockLlmProvider for offline reliability)."""
    cfg = app_settings or settings
    provider_type = cfg.llm_provider.lower().strip()

    if provider_type in ("http", "openai", "ollama") and cfg.llm_api_base:
        return HttpLlmProvider(
            api_base=cfg.llm_api_base,
            api_key=cfg.llm_api_key,
            model=cfg.llm_model,
            timeout_seconds=cfg.llm_timeout_seconds,
        )

    return MockLlmProvider()
