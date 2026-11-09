"""ForensicAnalyzer adapter wrapping Copy-Move forgery detection."""

import logging
import time
from pathlib import Path

from document_intelligence.domain.enums import CoordinateSystem, PipelineStatus
from document_intelligence.infrastructure.storage.filesystem import FilesystemDocumentStorage
from document_intelligence.infrastructure.storage.interface import DocumentStorageProtocol
from document_intelligence.modules.forensics.adapters.visual.copy_move import (
    detect_copy_move_clusters,
    generate_copy_move_visualization_bytes,
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


class CopyMoveAnalyzer(ForensicAnalyzer):
    """ForensicAnalyzer adapter detecting localized copy-move cloning anomalies within pages.

    Identifies indicative duplicated visual regions. Does not produce definitive fraud verdicts.
    """

    analyzer_id: str = "copy-move-analyzer"
    display_name: str = "Visual Copy-Move Forgery Detection Engine"
    version: str = "0.2.0"

    def __init__(
        self,
        renderer: DocumentPageRenderer | None = None,
        storage: DocumentStorageProtocol | None = None,
        artifacts_dir: Path | None = None,
        default_max_features: int = 2500,
    ) -> None:
        self.renderer = renderer or DocumentPageRenderer()
        self.storage = storage or FilesystemDocumentStorage()
        self.artifacts_dir = artifacts_dir or DEFAULT_ARTIFACTS_DIR
        self.default_max_features = default_max_features

    @property
    def name(self) -> str:
        return self.display_name

    @property
    def supported_media_types(self) -> set[str]:
        return SUPPORTED_MEDIA_TYPES

    @property
    def supported_capabilities(self) -> list[str]:
        return ["visual.copymove.orb_displacement"]

    def can_analyze(self, media_type: str) -> bool:
        """Check whether the analyzer supports the given media type."""
        return media_type.lower() in SUPPORTED_MEDIA_TYPES or media_type.lower().startswith(
            "image/"
        )

    def analyze(self, input_data: AnalyzerInput) -> AnalyzerOutput:
        """Execute Copy-Move forgery detection on document pages."""
        start_time = time.perf_counter()
        observations: list[AnalyzerObservation] = []
        capabilities: list[AnalyzerCapabilityResult] = []
        errors: list[str] = []
        pages_processed = 0
        total_clusters_found = 0

        max_features = int(input_data.options.get("max_features", self.default_max_features))

        try:
            for page in self.renderer.render_pages(
                file_path=input_data.file_path,
                media_type=input_data.detected_media_type,
            ):
                pages_processed += 1
                (
                    total_kp,
                    total_matches,
                    clusters,
                    matched_pairs,
                ) = detect_copy_move_clusters(
                    image=page.image,
                    page_geometry=page.geometry,
                    pixel_width=page.pixel_width,
                    pixel_height=page.pixel_height,
                    max_features=max_features,
                )

                artifact_key_str: str | None = None
                artifact_sha256_str: str | None = None

                if clusters:
                    total_clusters_found += len(clusters)
                    art_bytes = generate_copy_move_visualization_bytes(
                        page.image, clusters, matched_pairs
                    )
                    art_filename = (
                        f"copymove_{input_data.processing_run_id}_p{page.page_number}.png"
                    )

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

                    if not artifact_key_str:
                        self.artifacts_dir.mkdir(parents=True, exist_ok=True)
                        direct_path = self.artifacts_dir / art_filename
                        with open(direct_path, "wb") as f:
                            f.write(art_bytes)
                        artifact_key_str = str(direct_path).replace("\\", "/")

                for idx, cluster in enumerate(clusters):
                    # Severity represents heuristic triage priority, NOT confirmed fraud probability
                    severity = "medium" if cluster.matched_keypoints_count >= 25 else "low"
                    categorical_conf = "low"  # Indicative heuristic signal; uncalibrated

                    obs = AnalyzerObservation(
                        observation_type="visual_copymove",
                        title=f"Potential duplicated visual region detected on page {page.page_number} (Cluster #{idx + 1})",
                        description=(
                            f"Identified {cluster.matched_keypoints_count} consistent keypoint matches between candidate "
                            f"regions with spatial displacement (dx={cluster.displacement_dx}, dy={cluster.displacement_dy}). "
                            f"Triage priority: {severity.upper()}."
                        ),
                        severity=severity,
                        categorical_confidence=categorical_conf,
                        confidence_source="local:copymove",
                        confidence=None,  # Strictly None: no fabricated numeric probability
                        page_number=page.page_number,
                        bounding_box=cluster.duplicate_box,  # Primary box records duplicate patch
                        coordinate_system=CoordinateSystem.NORMALIZED_0_1,
                        capability_id="visual.copymove.orb_displacement",
                        observed_value=f"matches={cluster.matched_keypoints_count}, displacement=({cluster.displacement_dx},{cluster.displacement_dy})",
                        expected_value="matches=0 (no duplicate visual clusters)",
                        evidence_payload={
                            "page_number": page.page_number,
                            "cluster_index": idx + 1,
                            "matched_keypoints_count": cluster.matched_keypoints_count,
                            "displacement_dx": cluster.displacement_dx,
                            "displacement_dy": cluster.displacement_dy,
                            "source_bounding_box": cluster.source_box.model_dump(),
                            "duplicate_bounding_box": cluster.duplicate_box.model_dump(),
                            "source_pixel_bbox": list(cluster.source_pixel_bbox),
                            "duplicate_pixel_bbox": list(cluster.duplicate_pixel_bbox),
                            "algorithm_parameters": {
                                "max_features": max_features,
                                "min_spatial_distance_px": 50.0,
                                "ratio_threshold": 0.75,
                                "min_cluster_matches": 10,
                            },
                            "artifact_key": artifact_key_str,
                            "artifact_path": artifact_key_str,  # Preserved relative key for compatibility
                            "artifact_sha256": artifact_sha256_str,
                        },
                        benign_explanations=[
                            "Repeated logos, seals, or organizational crests present in document headers or footers.",
                            "Recurring tabular borders, forms, or standardized document template glyphs.",
                            "Repeated structural icons, bullet points, or organizational letterheads.",
                            "Repeated legitimate signatures across authorized signatory blocks.",
                        ],
                    )
                    observations.append(obs)

            capabilities.append(
                AnalyzerCapabilityResult(
                    capability_id="visual.copymove.orb_displacement",
                    status="FINDING" if observations else "PASS",
                    summary=(
                        f"Analyzed {pages_processed} pages with ORB max_features={max_features}. "
                        f"Identified {total_clusters_found} duplicate candidate region clusters."
                    ),
                    details={
                        "pages_processed": pages_processed,
                        "max_features": max_features,
                        "clusters_detected": total_clusters_found,
                    },
                )
            )
            status = PipelineStatus.SUCCEEDED

        except Exception as e:
            logger.exception("Copy-Move detection failed on %s: %s", input_data.file_path, e)
            errors.append(str(e))
            capabilities.append(
                AnalyzerCapabilityResult(
                    capability_id="visual.copymove.orb_displacement",
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
                "Feature-based matching requires textured regions and cannot detect flat-color or low-texture duplications.",
                "Non-rigid deformations, non-affine rotations, or substantial scale variations may reduce keypoint matching recall.",
                "Examiner confirmation is required to distinguish legitimate repeated template elements from fraudulent manipulations.",
            ],
            errors=errors,
        )
