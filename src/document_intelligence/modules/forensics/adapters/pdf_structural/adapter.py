"""Forensic adapter implementing ForensicAnalyzer for PDF structural analysis using a subprocess worker."""

import json
import subprocess
import sys
import time
from pathlib import Path

from document_intelligence.core.exceptions import SecurityException, ValidationException
from document_intelligence.domain.enums import PipelineStatus
from document_intelligence.modules.forensics.adapters.pdf_structural.capabilities import (
    PdfCapability,
)
from document_intelligence.modules.forensics.adapters.pdf_structural.mapper import (
    map_upstream_report,
)
from document_intelligence.modules.forensics.interfaces.analyzer import ForensicAnalyzer
from document_intelligence.modules.forensics.schemas.analyzer_input import AnalyzerInput
from document_intelligence.modules.forensics.schemas.analyzer_output import (
    AnalyzerCapabilityResult,
    AnalyzerOutput,
)


class PdfStructuralAnalyzer(ForensicAnalyzer):
    """Adapter wrapping pdf-forensics-kit in a process-isolated worker with enforceable timeouts."""

    ANALYZER_ID = "pdf-structural-analyzer"
    DISPLAY_NAME = "PDF Structural & Byte-Level Forensics Analyzer"
    VERSION = "0.6.0"
    SUPPORTED_MEDIA_TYPES = {"application/pdf"}

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
        return [c.value for c in PdfCapability]

    def can_analyze(self, media_type: str) -> bool:
        return media_type.lower() in self.SUPPORTED_MEDIA_TYPES

    def analyze(self, input_data: AnalyzerInput) -> AnalyzerOutput:
        """Execute structural inspection over target PDF snapshot via an isolated subprocess."""
        if not self.can_analyze(input_data.detected_media_type):
            raise ValidationException(
                f"Analyzer '{self.analyzer_id}' does not support media type '{input_data.detected_media_type}'.",
                details={"supported": list(self.SUPPORTED_MEDIA_TYPES)},
            )

        target_path = Path(input_data.file_path)
        if not target_path.exists() or not target_path.is_file():
            raise ValidationException(
                f"Document file does not exist at path: {target_path}",
                details={"file_path": str(target_path)},
            )

        # Inspect magic bytes to confirm it begins with standard PDF header
        with open(target_path, "rb") as f:
            header = f.read(16)
        if not header.startswith(b"%PDF-"):
            raise SecurityException(
                "File signature mismatch: document does not begin with standard PDF header (%PDF-).",
                details={"header_bytes": header[:8].hex()},
            )

        cmd = [
            sys.executable,
            "-m",
            "document_intelligence.modules.forensics.adapters.pdf_structural.worker",
            "--snapshot",
            str(target_path),
            "--options",
            json.dumps(input_data.options),
        ]

        timeout_sec = float(input_data.timeout_seconds)
        start_time = time.perf_counter()

        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout_sec,
                check=False,
            )
            duration_ms = (time.perf_counter() - start_time) * 1000.0

            # Bounded output extraction (max 1 MB stdout, max 64 KB stderr)
            raw_stdout = proc.stdout[:1048576].strip()
            raw_stderr = proc.stderr[:65536].strip()

            if not raw_stdout:
                err_msg = raw_stderr or f"Worker exited with code {proc.returncode} with no output."
                return AnalyzerOutput(
                    analyzer_id=self.analyzer_id,
                    analyzer_name=self.display_name,
                    analyzer_version=self.version,
                    status=PipelineStatus.FAILED,
                    execution_duration_ms=round(duration_ms, 2),
                    capabilities_executed=[
                        AnalyzerCapabilityResult(
                            capability_id=PdfCapability.STRUCTURE.value,
                            status="ERROR",
                            error_message=err_msg[:2000],
                        )
                    ],
                    observations=[],
                    raw_metadata={},
                    limitations=["Subprocess worker terminated without output."],
                    errors=[err_msg[:2000]],
                )

            try:
                result = json.loads(raw_stdout)
            except json.JSONDecodeError:
                err_msg = f"Failed parsing worker JSON output: {raw_stdout[:500]}"
                return AnalyzerOutput(
                    analyzer_id=self.analyzer_id,
                    analyzer_name=self.display_name,
                    analyzer_version=self.version,
                    status=PipelineStatus.FAILED,
                    execution_duration_ms=round(duration_ms, 2),
                    capabilities_executed=[
                        AnalyzerCapabilityResult(
                            capability_id=PdfCapability.STRUCTURE.value,
                            status="ERROR",
                            error_message=err_msg,
                        )
                    ],
                    observations=[],
                    raw_metadata={},
                    limitations=["Worker output was malformed."],
                    errors=[err_msg],
                )

            if result.get("success"):
                report_dict = result.get("report", {})
                return map_upstream_report(
                    report_dict=report_dict,
                    analyzer_id=self.analyzer_id,
                    analyzer_name=self.display_name,
                    analyzer_version=self.version,
                    duration_ms=round(duration_ms, 2),
                )
            else:
                err_msg = result.get("error_message", "Unknown parser error")
                is_encrypted = bool(result.get("is_encrypted", False))
                return AnalyzerOutput(
                    analyzer_id=self.analyzer_id,
                    analyzer_name=self.display_name,
                    analyzer_version=self.version,
                    status=PipelineStatus.FAILED,
                    execution_duration_ms=round(duration_ms, 2),
                    capabilities_executed=[
                        AnalyzerCapabilityResult(
                            capability_id=PdfCapability.STRUCTURE.value,
                            status="ERROR",
                            error_message=err_msg,
                        )
                    ],
                    observations=[],
                    raw_metadata={},
                    limitations=[
                        "Document is password-protected or encrypted."
                        if is_encrypted
                        else "Malformed PDF structure prevented analysis."
                    ],
                    errors=[err_msg],
                )

        except subprocess.TimeoutExpired:
            duration_ms = (time.perf_counter() - start_time) * 1000.0
            timeout_msg = f"Parser execution timed out after {timeout_sec} seconds."
            return AnalyzerOutput(
                analyzer_id=self.analyzer_id,
                analyzer_name=self.display_name,
                analyzer_version=self.version,
                status=PipelineStatus.FAILED,
                execution_duration_ms=round(duration_ms, 2),
                capabilities_executed=[
                    AnalyzerCapabilityResult(
                        capability_id=PdfCapability.STRUCTURE.value,
                        status="ERROR",
                        error_message=timeout_msg,
                    )
                ],
                observations=[],
                raw_metadata={},
                limitations=["Parser execution exceeded configured timeout window."],
                errors=[timeout_msg],
            )
        except Exception as exc:
            duration_ms = (time.perf_counter() - start_time) * 1000.0
            err_msg = f"{type(exc).__name__}: {exc}"
            return AnalyzerOutput(
                analyzer_id=self.analyzer_id,
                analyzer_name=self.display_name,
                analyzer_version=self.version,
                status=PipelineStatus.FAILED,
                execution_duration_ms=round(duration_ms, 2),
                capabilities_executed=[
                    AnalyzerCapabilityResult(
                        capability_id=PdfCapability.STRUCTURE.value,
                        status="ERROR",
                        error_message=err_msg,
                    )
                ],
                observations=[],
                raw_metadata={},
                limitations=["Unexpected adapter exception encountered."],
                errors=[err_msg],
            )
