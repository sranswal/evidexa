"""Google Gemini Multimodal Forensic Analyzer Adapter.

Leverages Google Gemini Vision (e.g. Gemini 2.5 Flash / Pro) to perform deep multimodal
document examination: detecting visual splicing, font anomalies, forged signatures,
altered numerical amounts, and cross-field semantic contradictions.
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any

from document_intelligence.core.ai_config import ai_config_manager
from document_intelligence.core.exceptions import ValidationException
from document_intelligence.domain.enums import CoordinateSystem, PipelineStatus
from document_intelligence.domain.models.bounding_box import BoundingBox
from document_intelligence.modules.forensics.interfaces.analyzer import ForensicAnalyzer
from document_intelligence.modules.forensics.schemas.analyzer_input import AnalyzerInput
from document_intelligence.modules.forensics.schemas.analyzer_output import (
    AnalyzerCapabilityResult,
    AnalyzerObservation,
    AnalyzerOutput,
)

logger = logging.getLogger(__name__)


class GeminiMultimodalAnalyzer(ForensicAnalyzer):
    """Forensic analyzer utilizing Google Gemini Multimodal Vision models."""

    ANALYZER_ID = "gemini-multimodal-analyzer"
    DISPLAY_NAME = "Google Gemini Multimodal Forensic Analyzer"
    VERSION = "1.0.0"
    SUPPORTED_MEDIA_TYPES = {
        "application/pdf",
        "image/png",
        "image/jpeg",
        "image/tiff",
    }
    SUPPORTED_CAPABILITIES = [
        "visual_tampering",
        "font_anomaly",
        "stamp_signature_verification",
        "semantic_contradiction",
        "unstructured_fact_extraction",
    ]

    @property
    def analyzer_id(self) -> str:
        return self.ANALYZER_ID

    @property
    def display_name(self) -> str:
        return self.DISPLAY_NAME

    @property
    def name(self) -> str:
        return self.DISPLAY_NAME

    @property
    def version(self) -> str:
        return self.VERSION

    @property
    def supported_media_types(self) -> set[str]:
        return self.SUPPORTED_MEDIA_TYPES

    @property
    def supported_capabilities(self) -> list[str]:
        return self.SUPPORTED_CAPABILITIES

    def can_analyze(self, media_type: str) -> bool:
        return media_type.lower() in self.SUPPORTED_MEDIA_TYPES

    def _render_document_to_image(self, file_path: Path, media_type: str) -> tuple[bytes, str]:
        """Convert target document or first page of PDF into PNG bytes for multimodal inspection."""
        if media_type == "application/pdf":
            import fitz  # type: ignore[import-not-found]

            doc = fitz.open(file_path)
            if doc.page_count < 1:
                raise ValidationException("PDF contains zero pages.")
            page = doc.load_page(0)
            # Render at 150 DPI for crisp visual inspection
            pix = page.get_pixmap(dpi=150)
            img_bytes = pix.tobytes("png")
            doc.close()
            return img_bytes, "image/png"

        # Raster image formats
        with open(file_path, "rb") as f:
            data = f.read()
        return data, media_type

    def analyze(self, input_data: AnalyzerInput) -> AnalyzerOutput:
        """Execute multimodal forensic inspection using active Google Gemini model."""
        start_time = time.perf_counter()
        target_path = Path(input_data.file_path)

        if not target_path.exists():
            return AnalyzerOutput(
                analyzer_id=self.ANALYZER_ID,
                analyzer_name=self.DISPLAY_NAME,
                analyzer_version=self.VERSION,
                status=PipelineStatus.FAILED,
                errors=[f"Target evidence file missing at: {target_path}"],
                execution_duration_ms=0.0,
            )

        # Check if Online AI mode is active
        if not ai_config_manager.is_online:
            return AnalyzerOutput(
                analyzer_id=self.ANALYZER_ID,
                analyzer_name=self.DISPLAY_NAME,
                analyzer_version=self.VERSION,
                status=PipelineStatus.SUCCEEDED,
                observations=[
                    AnalyzerObservation(
                        observation_type="system_limitation",
                        title="Gemini Multimodal AI Inactive (Offline Air-Gapped Mode)",
                        description=(
                            "The Gemini Multimodal Forensic Analyzer requires Online AI Mode with a valid "
                            "Google Gemini API key. Enable 'Online Mode' in the top navigation bar to activate "
                            "deep neural vision tampering inspection."
                        ),
                        severity="info",
                        capability_id="visual_tampering",
                        categorical_confidence="high",
                    )
                ],
                capabilities_executed=[
                    AnalyzerCapabilityResult(
                        capability_id=cap,
                        status="UNSUPPORTED",
                        summary="Skipped due to offline air-gapped configuration.",
                    )
                    for cap in self.SUPPORTED_CAPABILITIES
                ],
                raw_metadata={"operating_mode": "OFFLINE"},
                execution_duration_ms=round((time.perf_counter() - start_time) * 1000, 2),
            )

        # Online Mode: Execute Gemini Multimodal Vision Inspection
        try:
            from google import genai
            from google.genai import types

            image_bytes, mime_type = self._render_document_to_image(
                target_path, input_data.detected_media_type
            )
            image_part = types.Part.from_bytes(data=image_bytes, mime_type=mime_type)

            system_instruction = (
                "You are an expert digital document forensics examiner adhering to Federal Rules of Evidence (FRE 902). "
                "Inspect this document image with rigorous precision for signs of digital tampering, editing, or fraud:\n"
                "1. Numerical & Balance Tampering: Spliced digits, altered invoice totals, edited dates, whiteout artifacts.\n"
                "2. Typography & Font Inconsistencies: Differences in font family, weight, kerning, baseline alignment, or artificial digital overlay on paper grain.\n"
                "3. Stamp & Signature Manipulation: Duplicated, cloned, copy-pasted, or misaligned signatures, seals, or corporate stamps.\n"
                "4. Layout & Semantic Contradictions: Inconsistent addresses, abnormal tax calculation, contradictory dates (e.g., invoice prior to order).\n\n"
                "Format your response as a strict JSON object with this exact schema:\n"
                "{\n"
                '  "findings": [\n'
                "    {\n"
                '      "title": "Short descriptive title of the anomaly",\n'
                '      "description": "Detailed factual evidentiary description of what is visible",\n'
                '      "severity": "CRITICAL" | "HIGH" | "MEDIUM" | "LOW" | "INFORMATIONAL",\n'
                '      "category": "VISUAL_ANOMALY" | "METADATA_DISCREPANCY" | "FINANCIAL_VALIDATION",\n'
                '      "bounding_box": [ymin, xmin, ymax, xmax] (normalized between 0.0 and 1.0) or null,\n'
                '      "benign_explanations": ["Alternative non-fraudulent explanations (e.g. scanner artifact)"]\n'
                "    }\n"
                "  ],\n"
                '  "document_summary": "One sentence summary of the document and overall visual authenticity."\n'
                "}"
            )

            client = genai.Client(api_key=ai_config_manager.api_key)
            model_to_use = ai_config_manager.model or "gemini-2.5-flash"

            request_contents: Any = [
                image_part,
                "Analyze this document image for forensic alterations, digital tampering, and structural discrepancies.",
            ]

            response = client.models.generate_content(
                model=model_to_use,
                contents=request_contents,
                config=types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    response_mime_type="application/json",
                    temperature=0.1,
                ),
            )

            raw_text = response.text or "{}"
            result_json = json.loads(raw_text)

            observations: list[AnalyzerObservation] = []
            findings_data = result_json.get("findings", [])

            for item in findings_data:
                bbox: BoundingBox | None = None
                coords = item.get("bounding_box")
                if coords and isinstance(coords, list) and len(coords) == 4:
                    try:
                        ymin = float(coords[0])
                        xmin = float(coords[1])
                        ymax = float(coords[2])
                        xmax = float(coords[3])
                        w = max(0.001, xmax - xmin)
                        h = max(0.001, ymax - ymin)
                        bbox = BoundingBox(
                            x=xmin,
                            y=ymin,
                            width=w,
                            height=h,
                            coordinate_system=CoordinateSystem.NORMALIZED_0_1,
                        )
                    except Exception:
                        bbox = None

                obs = AnalyzerObservation(
                    observation_type="visual_ai_anomaly",
                    title=item.get("title", "Visual Forensic Anomaly Detected"),
                    description=item.get(
                        "description", "Potential tampering identified by Gemini Vision."
                    ),
                    severity=item.get("severity", "medium").lower(),
                    categorical_confidence="high",
                    confidence_source=f"Google Gemini Vision ({model_to_use})",
                    page_number=1,
                    bounding_box=bbox,
                    coordinate_system=CoordinateSystem.NORMALIZED_0_1 if bbox else None,
                    capability_id="visual_tampering",
                    benign_explanations=item.get("benign_explanations", []),
                    evidence_payload={
                        "model": model_to_use,
                        "analysis_engine": "Google Gemini Multimodal Vision",
                        "analyzed_mime_type": mime_type,
                    },
                )
                observations.append(obs)

            if not observations:
                observations.append(
                    AnalyzerObservation(
                        observation_type="visual_ai_clean",
                        title="Gemini Multimodal Forensic Scan: No Blatant Tampering Detected",
                        description=result_json.get(
                            "document_summary",
                            "Visual inspection by Gemini Vision found standard layout consistency without apparent digital splicing.",
                        ),
                        severity="info",
                        categorical_confidence="high",
                        confidence_source=f"Google Gemini Vision ({model_to_use})",
                        capability_id="visual_tampering",
                        evidence_payload={"model": model_to_use},
                    )
                )

            duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
            return AnalyzerOutput(
                analyzer_id=self.ANALYZER_ID,
                analyzer_name=self.DISPLAY_NAME,
                analyzer_version=self.VERSION,
                status=PipelineStatus.SUCCEEDED,
                observations=observations,
                capabilities_executed=[
                    AnalyzerCapabilityResult(
                        capability_id=cap,
                        status="PASS" if observations else "WARNING",
                        summary="Evaluated via Gemini Multimodal Vision.",
                    )
                    for cap in self.SUPPORTED_CAPABILITIES
                ],
                raw_metadata={
                    "model": model_to_use,
                    "document_summary": result_json.get("document_summary"),
                    "execution_mode": "ONLINE",
                },
                execution_duration_ms=duration_ms,
            )

        except Exception as exc:
            duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
            logger.error("Gemini Multimodal Forensic Analysis failed: %s", exc, exc_info=True)
            return AnalyzerOutput(
                analyzer_id=self.ANALYZER_ID,
                analyzer_name=self.DISPLAY_NAME,
                analyzer_version=self.VERSION,
                status=PipelineStatus.FAILED,
                errors=[f"Gemini analysis error: {exc}"],
                execution_duration_ms=duration_ms,
            )
