"""Mapping utilities transforming raw upstream Report objects into normalized AnalyzerOutput."""

from typing import Any

from document_intelligence.domain.enums import PipelineStatus
from document_intelligence.modules.forensics.adapters.pdf_structural.capabilities import (
    PdfCapability,
)
from document_intelligence.modules.forensics.schemas.analyzer_output import (
    AnalyzerCapabilityResult,
    AnalyzerObservation,
    AnalyzerOutput,
)


def map_upstream_report(
    report_dict: dict[str, Any],
    analyzer_id: str = "pdf-structural-analyzer",
    analyzer_name: str = "PDF Structural & Byte-Level Forensics Analyzer",
    analyzer_version: str = "0.6.0",
    duration_ms: float = 0.0,
    **kwargs: Any,
) -> AnalyzerOutput:
    """Transform upstream pdf-forensics-kit report dictionary into typed AnalyzerOutput.

    Categorical confidence labels from the source engine are preserved verbatim.
    No artificial numeric probabilities are fabricated.
    """
    if "execution_time_ms" in kwargs:
        duration_ms = float(kwargs["execution_time_ms"])

    raw_findings = report_dict.get("findings", [])
    raw_facts = report_dict.get("facts", {})
    raw_errors = report_dict.get("errors", [])
    verdict = report_dict.get("verdict", {})

    observations: list[AnalyzerObservation] = []
    for f in raw_findings:
        evidence = f.get("evidence", {}) or {}

        # Extract source references if present
        page_num: int | None = None
        if "page" in evidence and isinstance(evidence["page"], int):
            page_num = evidence["page"]
        elif (
            "text_added" in evidence
            and isinstance(evidence["text_added"], list)
            and evidence["text_added"]
        ):
            first_text = evidence["text_added"][0]
            if isinstance(first_text, dict) and "page" in first_text:
                page_num = first_text.get("page")

        pdf_obj_ref: str | None = None
        if (
            "changed_objects" in evidence
            and isinstance(evidence["changed_objects"], list)
            and evidence["changed_objects"]
        ):
            pdf_obj_ref = str(evidence["changed_objects"][0])
        elif "object" in evidence:
            pdf_obj_ref = str(evidence["object"])

        # Preserve source categorical confidence verbatim without manufacturing probabilities
        raw_conf = f.get("confidence")
        conf_label = str(raw_conf).lower().strip() if raw_conf is not None else "unknown"

        obs = AnalyzerObservation(
            observation_type=f.get("category", "structure"),
            title=f.get("title", "Structural observation"),
            description=f.get("explanation", ""),
            severity=str(f.get("severity", "info")).lower(),
            categorical_confidence=conf_label,
            confidence_source="upstream:pdf-forensics-kit",
            confidence=None,  # No empirical calibration available from pdf-forensics-kit
            page_number=page_num,
            pdf_object_reference=pdf_obj_ref,
            capability_id=f.get("id", "structure.unknown"),
            evidence_payload=evidence,
            benign_explanations=list(f.get("benign_explanations", []) or []),
        )
        observations.append(obs)

    # Map capabilities executed
    capabilities_executed: list[AnalyzerCapabilityResult] = []
    for cap in PdfCapability:
        subsystem = cap.value.removeprefix("pdf.")
        if subsystem in raw_facts:
            # Check if there are findings for this subsystem
            cap_findings = [
                o
                for o in observations
                if o.observation_type == subsystem or o.capability_id.startswith(subsystem)
            ]
            has_error = any(e.get("analyzer") == subsystem for e in raw_errors)

            if has_error:
                status = "ERROR"
            elif cap_findings:
                status = "FINDING"
            else:
                status = "PASS"

            capabilities_executed.append(
                AnalyzerCapabilityResult(
                    capability_id=cap.value,
                    status=status,
                    details=raw_facts[subsystem]
                    if isinstance(raw_facts[subsystem], dict)
                    else {"data": raw_facts[subsystem]},
                )
            )
        else:
            capabilities_executed.append(
                AnalyzerCapabilityResult(
                    capability_id=cap.value,
                    status="UNSUPPORTED",
                    details={},
                )
            )

    # Determine overall pipeline status
    is_complete = verdict.get("complete", True)
    if raw_errors and not is_complete:
        pipeline_status = (
            PipelineStatus.PARTIALLY_SUCCEEDED if observations else PipelineStatus.FAILED
        )
    else:
        pipeline_status = PipelineStatus.SUCCEEDED

    error_messages = [f"{e.get('analyzer')}: {e.get('error')}" for e in raw_errors]

    return AnalyzerOutput(
        analyzer_id=analyzer_id,
        analyzer_name=analyzer_name,
        analyzer_version=analyzer_version,
        status=pipeline_status,
        execution_duration_ms=duration_ms,
        capabilities_executed=capabilities_executed,
        observations=observations,
        raw_metadata={
            "verdict": verdict,
            "summary": report_dict.get("summary", {}),
            "tool": report_dict.get("tool", {}),
        },
        limitations=[
            "Structural and byte analysis only.",
            "Cannot prove semantic truth of content or document authenticity.",
            "A clean result is not affirmative proof that a document is authentic.",
        ],
        errors=error_messages,
    )
