"""ForensicAnalyzer adapter wrapping Error Level Analysis (ELA)."""

import logging
import time
from pathlib import Path

from document_intelligence.domain.enums import CoordinateSystem, PipelineStatus
from document_intelligence.infrastructure.storage.filesystem import FilesystemDocumentStorage
from document_intelligence.infrastructure.storage.interface import DocumentStorageProtocol
from document_intelligence.modules.forensics.adapters.visual.ela import (
    compute_ela_image,
    generate_ela_heatmap_bytes,
    localize_ela_anomalies,
)
from document_intelligence.modules.forensics.adapters.visual.page_renderer import (
    DocumentPageRenderer,
)
from document_intelligence.modules.forensics.interfaces.analyzer import ForensicAnalyzer
from document_intelligence.modules.forensics.schemas.analyzer_input import AnalyzerInput
from document_intelligence.modules.forensics.schemas.analyzer_output import (
    AnalyzerCapabilityResult,
    AnalyzerObservation,
    AnalyzerOutput,
)

logger = logging.getLogger(__name__)

SUPPORTED_MEDIA_TYPES = {
    "application/pdf",
    "image/png",
    "image/jpeg",
    "image/jpg",
    "image/tiff",
    "image/webp",
    "image/bmp",
}

DEFAULT_ARTIFACTS_DIR = Path("data/artifacts")


class ElaAnalyzer(ForensicAnalyzer):
    """ForensicAnalyzer adapter implementing Visual Error Level Analysis (ELA).

    Produces indicative candidate visual regions exhibiting compression discrepancies.
    Does not produce definitive fraud or tampering verdicts.
    """

    analyzer_id: str = "ela-analyzer"
    display_name: str = "Visual Error Level Analysis (ELA) Engine"
    version: str = "0.2.0"

    def __init__(
        self,
        renderer: DocumentPageRenderer | None = None,
        storage: DocumentStorageProtocol | None = None,
        artifacts_dir: Path | None = None,
        default_quality: int = 90,
    ) -> None:
        self.renderer = renderer or DocumentPageRenderer()
        self.storage = storage or FilesystemDocumentStorage()
        self.artifacts_dir = artifacts_dir or DEFAULT_ARTIFACTS_DIR
        self.default_quality = default_quality

    @property
    def name(self) -> str:
        return self.display_name

    @property
    def supported_media_types(self) -> set[str]:
        return SUPPORTED_MEDIA_TYPES

    @property
    def supported_capabilities(self) -> list[str]:
        return ["visual.ela.compression_delta"]

    def can_analyze(self, media_type: str) -> bool:
        """Check whether the analyzer supports the given media type."""
        return media_type.lower() in SUPPORTED_MEDIA_TYPES or media_type.lower().startswith(
            "image/"
        )

    def analyze(self, input_data: AnalyzerInput) -> AnalyzerOutput:
        """Execute Error Level Analysis on the provided document snapshot."""
        start_time = time.perf_counter()
        observations: list[AnalyzerObservation] = []
        capabilities: list[AnalyzerCapabilityResult] = []
        errors: list[str] = []
        pages_processed = 0

        quality = int(input_data.options.get("ela_quality", self.default_quality))

        try:
            for page in self.renderer.render_pages(
                file_path=input_data.file_path,
                media_type=input_data.detected_media_type,
            ):
                pages_processed += 1
                enhanced_img, gray_energy = compute_ela_image(page.image, quality=quality)

                mean_val, std_val, max_val, high_ratio, regions = localize_ela_anomalies(
                    gray_energy=gray_energy,
                    page_geometry=page.geometry,
                    pixel_width=page.pixel_width,
                    pixel_height=page.pixel_height,
                )

                artifact_key_str: str | None = None
                artifact_sha256_str: str | None = None

                if regions or high_ratio > 0.01:
                    art_bytes = generate_ela_heatmap_bytes(enhanced_img, regions)
                    art_filename = f"ela_{input_data.processing_run_id}_p{page.page_number}.png"

                    if self.storage:
                        try:
                            artifact_key_str, artifact_sha256_str = self.storage.store_artifact(
                                case_id=input_data.case_id,
                                document_id=input_data.document_id,
                                processing_run_id=input_data.processing_run_id,
                                artifact_filename=art_filename,
                                data=art_bytes,
                            )
                        except Exception as storage_err:
                            logger.warning(
                                "Failed storing artifact via storage protocol: %s", storage_err
                            )

                    # Fallback to direct directory write if storage is absent or failed
                    if not artifact_key_str:
                        self.artifacts_dir.mkdir(parents=True, exist_ok=True)
                        direct_path = self.artifacts_dir / art_filename
                        with open(direct_path, "wb") as f:
                            f.write(art_bytes)
                        artifact_key_str = str(direct_path).replace("\\", "/")

                # Record candidate visual regions
                for idx, reg in enumerate(regions):
                    # Severity represents heuristic visual triage priority, NOT fraud probability
                    severity = "medium" if high_ratio > 0.05 or reg.mean_energy > 30.0 else "low"

                    obs = AnalyzerObservation(
                        observation_type="visual_ela",
                        title=f"Candidate visual region with local compression inconsistency on page {page.page_number} (Region #{idx + 1})",
                        description=(
                            f"Compression difference indicator (mean_energy={reg.mean_energy:.1f}, max_energy={reg.max_energy:.1f}) "
                            f"detected in candidate region on page {page.page_number}. Triage priority: {severity.upper()}."
                        ),
                        severity=severity,
                        categorical_confidence="low",  # Indicative heuristic signal; uncalibrated
                        confidence_source="local:ela",
                        confidence=None,  # Strictly None: no fabricated numeric probability
                        page_number=page.page_number,
                        bounding_box=reg.bounding_box,
                        coordinate_system=CoordinateSystem.NORMALIZED_0_1,
                        capability_id="visual.ela.compression_delta",
                        observed_value=f"mean_delta={reg.mean_energy:.2f}",
                        expected_value=f"mean_delta<={mean_val + std_val:.2f}",
                        evidence_payload={
                            "page_number": page.page_number,
                            "pixel_coords": {
                                "x": reg.pixel_x,
                                "y": reg.pixel_y,
                                "w": reg.pixel_w,
                                "h": reg.pixel_h,
                            },
                            "mean_energy": round(reg.mean_energy, 2),
                            "max_energy": round(reg.max_energy, 2),
                            "page_mean": round(mean_val, 2),
                            "page_std": round(std_val, 2),
                            "page_high_energy_ratio": round(high_ratio, 4),
                            "algorithm_parameters": {
                                "quality": quality,
                                "sigma_threshold": 3.0,
                            },
                            "artifact_key": artifact_key_str,
                            "artifact_path": artifact_key_str,  # Preserved relative key for compatibility
                            "artifact_sha256": artifact_sha256_str,
                        },
                        benign_explanations=[
                            "High-contrast text boundaries, barcode glyphs, and line art naturally produce elevated JPEG error rates.",
                            "Legitimate document resaving with different encoder quantization tables or compression factors.",
                            "Embedded raster images or photographs saved at different original compression levels than the host canvas.",
                            "Scanned document background noise and paper grain variations.",
                        ],
                    )
                    observations.append(obs)

            capabilities.append(
                AnalyzerCapabilityResult(
                    capability_id="visual.ela.compression_delta",
                    status="FINDING" if observations else "PASS",
                    summary=(
                        f"Analyzed {pages_processed} pages with ELA quality={quality}. "
                        f"Identified {len(observations)} candidate regions with compression inconsistencies."
                    ),
                    details={
                        "pages_processed": pages_processed,
                        "quality": quality,
                        "candidate_regions_count": len(observations),
                    },
                )
            )
            status = PipelineStatus.SUCCEEDED

        except Exception as e:
            logger.exception("ELA analysis failed on %s: %s", input_data.file_path, e)
            errors.append(str(e))
            capabilities.append(
                AnalyzerCapabilityResult(
                    capability_id="visual.ela.compression_delta",
                    status="ERROR",
                    summary=f"Analysis failed: {e}",
                    error_message=str(e),
                )
            )
            status = PipelineStatus.FAILED

        duration = (time.perf_counter() - start_time) * 1000.0

        return AnalyzerOutput(
            analyzer_id=self.analyzer_id,
            analyzer_name=self.display_name,
            analyzer_version=self.version,
            status=status,
            execution_duration_ms=round(duration, 2),
            capabilities_executed=capabilities,
            observations=observations,
            raw_metadata={
                "pages_processed": pages_processed,
                "options": input_data.options,
            },
            limitations=[
                "ELA provides heuristic visual anomaly indicators only; it is NOT conclusive proof of intentional tampering.",
                "Uncompressed PNG/TIFF sources converted to JPEG may exhibit uniform high error levels across the entire canvas.",
                "Text boundaries and high-frequency patterns naturally produce elevated ELA responses without malicious modification.",
                "False positives can occur on legitimate multi-source document composites and scanned forms.",
            ],
            errors=errors,
        )
