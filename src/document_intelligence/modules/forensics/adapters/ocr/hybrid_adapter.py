"""Hybrid Document Understanding and OCR Adapter coordinating PDFium and RapidOCR.

Implements geometry-aware page-level extraction routing:
1. Native digital PDF pages are extracted via Google PDFium (fast, 100% vector precision).
2. Scanned, image-only, or sparse-text pages are recognized via RapidOCR or Devanagari RapidOCR.
3. Hybrid composite pages (significant raster + vector) undergo hybrid fusion, preserving both
   layers independently with explicit disagreement recording and duplicate token detection.
4. Multilingual OCR engine selection deterministically chooses between Latin and Devanagari
   models based on script evidence.
5. Non-overlapping raster coverage is computed via Shapely unary_union over PDF image bounding boxes.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any, cast

import pypdfium2 as pdfium
from shapely.geometry import box  # type: ignore[import-untyped]
from shapely.ops import unary_union  # type: ignore[import-untyped]

from document_intelligence.domain.enums import (
    CoordinateSystem,
    PageRoutingDecision,
    PipelineStatus,
)
from document_intelligence.domain.models.bounding_box import BoundingBox, PageGeometry
from document_intelligence.domain.models.ocr import (
    CURRENT_ARTIFACT_SCHEMA_VERSION,
    AlternativeExtractionObservation,
    ExtractedDocumentText,
    ExtractedPage,
    OcrEngineMetadata,
)
from document_intelligence.infrastructure.storage.filesystem import FilesystemDocumentStorage
from document_intelligence.infrastructure.storage.interface import DocumentStorageProtocol
from document_intelligence.modules.forensics.adapters.ocr.devanagari_adapter import (
    DevanagariRapidOcrAdapter,
)
from document_intelligence.modules.forensics.adapters.ocr.pdfium_adapter import PdfiumOcrAdapter
from document_intelligence.modules.forensics.adapters.ocr.rapidocr_adapter import RapidOcrAdapter
from document_intelligence.modules.forensics.adapters.visual.page_renderer import (
    MAX_PAGES_DEFAULT,
    MAX_PIXEL_DIMENSION,
    MAX_TOTAL_PIXELS,
    DocumentPageRenderer,
    RenderedPage,
)
from document_intelligence.modules.forensics.interfaces.analyzer import ForensicAnalyzer
from document_intelligence.modules.forensics.schemas.analyzer_input import AnalyzerInput
from document_intelligence.modules.forensics.schemas.analyzer_output import (
    AnalyzerCapabilityResult,
    AnalyzerObservation,
    AnalyzerOutput,
)

logger = logging.getLogger(__name__)

DEFAULT_SPARSE_CHAR_THRESHOLD = 30
DEFAULT_RASTER_COVERAGE_THRESHOLD = 0.35
DEFAULT_MAX_IMAGE_REGIONS = 200


class RoutingDecision(str):
    """Routing decision string with bidirectional equality support for legacy decision names."""

    _LEGACY_MAP: dict[str, set[str]] = {
        "VECTOR_ONLY": {"DIGITAL_VECTOR_PRIMARY"},
        "OCR_ONLY": {
            "IMAGE_ONLY_SCANNED_PAGE",
            "OPTICAL_OCR",
            "SPARSE_TEXT_FALLBACK",
            "FORCED_OPTICAL_OCR",
            "DIRECT_IMAGE_OPTICAL_OCR",
        },
        "NO_TEXT": {"INSUFFICIENT_EVIDENCE", "NO_TEXT_DETECTED"},
    }

    def __eq__(self, other: object) -> bool:
        if super().__eq__(other):
            return True
        s = str(self)
        o = str(other)
        if s in self._LEGACY_MAP and o in self._LEGACY_MAP[s]:
            return True
        for canon, leg_set in self._LEGACY_MAP.items():
            if o == canon and s in leg_set:
                return True
        return False

    def __hash__(self) -> int:
        return super().__hash__()


def compute_box_iou(box1: BoundingBox | None, box2: BoundingBox | None) -> float:
    """Compute Intersection over Union (IoU) of two canonical bounding boxes."""
    if not box1 or not box2:
        return 0.0
    x1 = max(box1.x, box2.x)
    y1 = max(box1.y, box2.y)
    x2 = min(box1.x + box1.width, box2.x + box2.width)
    y2 = min(box1.y + box1.height, box2.y + box2.height)

    if x2 <= x1 or y2 <= y1:
        return 0.0

    inter_area = (x2 - x1) * (y2 - y1)
    area1 = box1.width * box1.height
    area2 = box2.width * box2.height
    union_area = area1 + area2 - inter_area
    if union_area <= 0.0:
        return 0.0
    return inter_area / union_area


class HybridOcrAdapter(ForensicAnalyzer):
    """Unified hybrid OCR analyzer combining PDFium programmatic extraction and RapidOCR/Devanagari OCR."""

    def __init__(
        self,
        storage: DocumentStorageProtocol | None = None,
        max_pages: int = MAX_PAGES_DEFAULT,
        default_dpi: float = 150.0,
        sparse_char_threshold: int = DEFAULT_SPARSE_CHAR_THRESHOLD,
        raster_coverage_threshold: float = DEFAULT_RASTER_COVERAGE_THRESHOLD,
        max_image_regions: int = DEFAULT_MAX_IMAGE_REGIONS,
        intra_op_num_threads: int | None = None,
        inter_op_num_threads: int | None = None,
    ) -> None:
        self.storage = storage or FilesystemDocumentStorage()
        self.max_pages = max_pages
        self.default_dpi = default_dpi
        self.sparse_char_threshold = sparse_char_threshold
        self.raster_coverage_threshold = raster_coverage_threshold
        self.max_image_regions = max_image_regions
        self.intra_op_num_threads = intra_op_num_threads
        self.inter_op_num_threads = inter_op_num_threads
        self.renderer = DocumentPageRenderer(max_pages=max_pages, default_dpi=default_dpi)
        self.pdfium_adapter = PdfiumOcrAdapter(
            storage=self.storage, max_pages=max_pages, default_dpi=default_dpi
        )
        self.rapidocr_adapter = RapidOcrAdapter(
            storage=self.storage,
            max_pages=max_pages,
            default_dpi=default_dpi,
            intra_op_num_threads=intra_op_num_threads,
            inter_op_num_threads=inter_op_num_threads,
        )
        self.devanagari_adapter = DevanagariRapidOcrAdapter(
            storage=self.storage,
            max_pages=max_pages,
            default_dpi=default_dpi,
            intra_op_num_threads=intra_op_num_threads,
            inter_op_num_threads=inter_op_num_threads,
        )

    @property
    def analyzer_id(self) -> str:
        return "hybrid-ocr-pipeline"

    @property
    def display_name(self) -> str:
        return "Hybrid PDFium & RapidOCR Document Intelligence Pipeline"

    @property
    def name(self) -> str:
        return "Hybrid Document OCR & Understanding Pipeline"

    @property
    def version(self) -> str:
        return "2.0.0"

    @property
    def supported_media_types(self) -> set[str]:
        return {
            "application/pdf",
            "image/png",
            "image/jpeg",
            "image/tiff",
            "image/bmp",
            "image/webp",
        }

    @property
    def supported_capabilities(self) -> list[str]:
        return [
            "text-extraction",
            "optical-character-recognition",
            "multilingual-devanagari",
            "token-bounding-boxes",
            "reading-order",
            "layout-parsing",
            "table-extraction",
            "page-level-routing",
            "geometry-aware-routing",
            "hybrid-provenance",
            "dual-layer-preservation",
        ]

    def can_analyze(self, media_type: str) -> bool:
        return media_type.lower() in self.supported_media_types

    def _compute_raster_coverage(
        self,
        pdf_page: pdfium.PdfPage,
    ) -> tuple[float, list[BoundingBox], int]:
        """Detect embedded raster image regions and calculate non-overlapping raster coverage ratio.

        Uses Shapely unary_union to merge overlapping image regions, ensuring that overlapping
        or duplicated raster stamps do not artificially inflate the coverage calculation.

        Returns:
            (raster_coverage_ratio, bounding_boxes_in_normalized_coords, total_image_count)
        """
        page_w = float(pdf_page.get_width())
        page_h = float(pdf_page.get_height())
        page_area = page_w * page_h

        if page_area <= 0.0:
            return 0.0, [], 0

        try:
            raw_image_objs = list(pdf_page.get_objects(filter=[pdfium.raw.FPDF_PAGEOBJ_IMAGE]))
        except Exception as exc:
            logger.warning(f"Failed to query PDF image objects via PDFium geometry: {exc}")
            raise RuntimeError(f"Geometry extraction failed on PDF page: {exc}") from exc

        total_image_count = len(raw_image_objs)
        if total_image_count > self.max_image_regions:
            logger.warning(
                f"Page image region count ({total_image_count}) exceeds safety limit ({self.max_image_regions}); truncating."
            )
            raw_image_objs = raw_image_objs[: self.max_image_regions]

        image_polygons = []
        image_boxes: list[BoundingBox] = []

        for obj in raw_image_objs:
            try:
                b = obj.get_bounds()  # (left, bottom, right, top) in PDF coordinates
                x0, x1 = min(b[0], b[2]), max(b[0], b[2])
                y0, y1 = min(b[1], b[3]), max(b[1], b[3])

                # Clip coordinates to unrotated page boundaries
                cl_x0 = max(0.0, min(page_w, x0))
                cl_x1 = max(0.0, min(page_w, x1))
                cl_y0 = max(0.0, min(page_h, y0))
                cl_y1 = max(0.0, min(page_h, y1))

                w = cl_x1 - cl_x0
                h = cl_y1 - cl_y0

                # Skip degenerate or sub-pixel noise
                if w > 1.0 and h > 1.0:
                    image_polygons.append(box(cl_x0, cl_y0, cl_x1, cl_y1))

                    # Canonical NORMALIZED_0_1 bounding box (top-left origin)
                    norm_x = cl_x0 / page_w
                    norm_y = (page_h - cl_y1) / page_h
                    norm_w = w / page_w
                    norm_h = h / page_h

                    image_boxes.append(
                        BoundingBox(
                            x=round(max(0.0, min(1.0, norm_x)), 4),
                            y=round(max(0.0, min(1.0, norm_y)), 4),
                            width=round(max(0.0, min(1.0 - norm_x, norm_w)), 4),
                            height=round(max(0.0, min(1.0 - norm_y, norm_h)), 4),
                            coordinate_system=CoordinateSystem.NORMALIZED_0_1,
                        )
                    )
            except Exception as obj_err:
                logger.debug(f"Skipping malformed image object: {obj_err}")

        if not image_polygons:
            return 0.0, [], total_image_count

        try:
            merged_union = unary_union(image_polygons)
            raster_union_area = float(merged_union.area)
        except Exception as union_err:
            logger.warning(
                f"Unary union area calculation failed ({union_err}); falling back to polygon sum."
            )
            raster_union_area = sum(p.area for p in image_polygons)

        raster_ratio = min(1.0, max(0.0, raster_union_area / page_area))
        return round(raster_ratio, 4), image_boxes, total_image_count

    def _select_ocr_engine(
        self,
        vector_text: str,
        options: dict[str, Any] | None = None,
    ) -> tuple[Any, str, list[str]]:
        """Explicit, deterministic engine selection using available script evidence.

        Returns:
            (adapter_instance, engine_name, limitations_list)
        """
        opts = options or {}
        lang_opt = str(opts.get("language", "")).lower()
        script_opt = str(opts.get("script", "")).lower()
        engine_opt = str(opts.get("engine", "")).lower()

        limitations: list[str] = []

        # 1. Check for explicit Devanagari evidence
        has_devanagari = (
            "devanagari" in lang_opt
            or "hi" in lang_opt
            or "devanagari" in script_opt
            or "devanagari" in engine_opt
        )

        if not has_devanagari and vector_text:
            devanagari_chars = [
                ch
                for ch in vector_text
                if (0x0900 <= ord(ch) <= 0x097F) or (0xA8E0 <= ord(ch) <= 0xA8FF)
            ]
            if len(devanagari_chars) > 0:
                has_devanagari = True

        if has_devanagari:
            return (
                self.devanagari_adapter,
                "ppocrv5-devanagari-engine",
                limitations,
            )

        # 2. Check for ambiguous or unsupported script
        is_ambiguous = False
        if vector_text:
            for ch in vector_text:
                cp = ord(ch)
                # Cyrillic, Arabic, Hebrew, CJK, Thai
                if (
                    (0x0400 <= cp <= 0x052F)
                    or (0x0590 <= cp <= 0x05FF)
                    or (0x0600 <= cp <= 0x06FF)
                    or (0x4E00 <= cp <= 0x9FFF)
                    or (0x0E00 <= cp <= 0x0E7F)
                ):
                    is_ambiguous = True
                    break

        if is_ambiguous:
            limitations.append(
                "Ambiguous or unsupported script detected; retained available observations and reported engine limitation."
            )

        # 3. Default to Latin / English RapidOCR
        return (
            self.rapidocr_adapter,
            "rapidocr-optical-engine",
            limitations,
        )

    def analyze(self, input_data: AnalyzerInput) -> AnalyzerOutput:
        """Execute hybrid document analysis with geometry-aware page-level routing."""
        t0 = time.perf_counter()
        capabilities_executed: list[AnalyzerCapabilityResult] = []
        observations: list[AnalyzerObservation] = []
        errors: list[str] = []
        artifact_key: str | None = None
        artifact_sha256: str | None = None
        limitations: list[str] = [
            "Native vector text is extracted with PDFium; scanned and hybrid pages route to RapidOCR or PP-OCRv5 Devanagari.",
            "Coordinates from both engines reside in canonical top-left NORMALIZED_0_1 space.",
            "When HYBRID_FUSION or OCR fallback occurs, original PDFium output is preserved under alternative_extractions without destructive text merging.",
            "Non-overlapping raster coverage is calculated via polygon union; overlapping image regions do not artificially inflate coverage.",
            "Token probabilities from optical OCR are uncalibrated model scores, whereas PDFium confidence is None.",
            "Processing operates sequentially per page to ensure ONNX and PDFium memory bounds.",
        ]

        media_type = input_data.detected_media_type or input_data.declared_media_type
        opts = input_data.options or {}
        raster_threshold = float(opts.get("raster_threshold", self.raster_coverage_threshold))

        try:
            extracted_doc = self._extract_document(
                file_path=input_data.file_path,
                media_type=media_type,
                case_id=input_data.case_id,
                document_id=input_data.document_id,
                processing_run_id=input_data.processing_run_id,
                options=input_data.options,
            )

            # Persist full extracted document model as storage artifact
            if input_data.document_id and input_data.processing_run_id:
                doc_json = extracted_doc.model_dump_json(indent=2).encode("utf-8")
                filename = f"ocr_{input_data.processing_run_id}_extracted.json"
                try:
                    artifact_key, artifact_sha256 = self.storage.store_artifact(
                        case_id=input_data.case_id,
                        document_id=input_data.document_id,
                        processing_run_id=input_data.processing_run_id,
                        artifact_filename=filename,
                        data=doc_json,
                    )
                    extracted_doc.storage_artifact_key = artifact_key
                    extracted_doc.storage_artifact_sha256 = artifact_sha256
                except Exception as e:
                    logger.warning(f"Failed storing OCR JSON artifact: {e}")

            # Collect any page-level engine limitations
            for p in extracted_doc.pages:
                alt_pdfium = p.alternative_extractions.get("pdfium")
                if alt_pdfium and alt_pdfium.metadata:
                    eng_lims = alt_pdfium.metadata.get("engine_limitations")
                    if eng_lims:
                        for lim in eng_lims:
                            if lim not in limitations:
                                limitations.append(lim)

            failed_pages = [p for p in extracted_doc.pages if p.extraction_status == "FAILED"]
            succeeded_pages = [p for p in extracted_doc.pages if p.extraction_status != "FAILED"]

            if failed_pages and succeeded_pages:
                status = PipelineStatus.PARTIALLY_SUCCEEDED
                cap_status = "PARTIAL"
            elif failed_pages and not succeeded_pages:
                status = PipelineStatus.FAILED
                cap_status = "FAIL"
            else:
                status = PipelineStatus.SUCCEEDED
                cap_status = "PASS"

            # Categorize page routing counts
            vector_only_count = sum(
                1
                for p in extracted_doc.pages
                if p.routing_decision in ("VECTOR_ONLY", "DIGITAL_VECTOR_PRIMARY")
            )
            hybrid_count = sum(
                1 for p in extracted_doc.pages if p.routing_decision == "HYBRID_FUSION"
            )
            ocr_only_count = sum(
                1
                for p in extracted_doc.pages
                if p.routing_decision
                in (
                    "OCR_ONLY",
                    "IMAGE_ONLY_SCANNED_PAGE",
                    "SPARSE_TEXT_FALLBACK",
                    "FORCED_OPTICAL_OCR",
                    "DIRECT_IMAGE_OPTICAL_OCR",
                    "OPTICAL_OCR",
                )
            )
            no_text_count = sum(
                1
                for p in extracted_doc.pages
                if p.routing_decision in ("NO_TEXT", "INSUFFICIENT_EVIDENCE")
            )

            capabilities_executed.append(
                AnalyzerCapabilityResult(
                    capability_id="hybrid-ocr-routing",
                    status=cap_status,
                    summary=(
                        f"Processed {extracted_doc.total_pages} page(s): {vector_only_count} vector-only, "
                        f"{ocr_only_count} ocr-only, {hybrid_count} hybrid fusion"
                        + (f", {no_text_count} empty/no-text" if no_text_count else "")
                        + (f", {len(failed_pages)} failed." if failed_pages else ".")
                        + f" Total tokens: {extracted_doc.total_tokens}."
                    ),
                    details={
                        "total_pages": extracted_doc.total_pages,
                        "vector_only_pages": vector_only_count,
                        "ocr_only_pages": ocr_only_count,
                        "hybrid_fusion_pages": hybrid_count,
                        "no_text_pages": no_text_count,
                        "failed_pages": len(failed_pages),
                        "total_tokens": extracted_doc.total_tokens,
                        "raster_threshold": raster_threshold,
                    },
                )
            )

            # Summary observation
            doc_obs = AnalyzerObservation(
                observation_type="ocr_text",
                title=f"Hybrid Geometry OCR: {extracted_doc.total_tokens} Tokens Across {extracted_doc.total_pages} Page(s)",
                description=(
                    f"Hybrid document extraction complete using {self.display_name} v{self.version}. "
                    f"Vector-only pages: {vector_only_count}, OCR-only pages: {ocr_only_count}, "
                    f"Hybrid fusion pages: {hybrid_count}."
                    + (
                        f" Warning: {len(failed_pages)} page(s) failed extraction."
                        if failed_pages
                        else ""
                    )
                ),
                severity="warning" if failed_pages else "info",
                categorical_confidence="high" if extracted_doc.total_tokens > 0 else "unknown",
                confidence=None,
                capability_id="hybrid-ocr-routing",
                evidence_payload={
                    "total_pages": extracted_doc.total_pages,
                    "vector_only_pages": vector_only_count,
                    "ocr_only_pages": ocr_only_count,
                    "hybrid_fusion_pages": hybrid_count,
                    "no_text_pages": no_text_count,
                    "failed_pages": len(failed_pages),
                    "total_tokens": extracted_doc.total_tokens,
                    "artifact_key": artifact_key,
                    "artifact_sha256": artifact_sha256,
                    "text_preview": extracted_doc.full_raw_text[:300],
                },
            )
            observations.append(doc_obs)

            # Per-page observations
            for page in extracted_doc.pages:
                page_obs = AnalyzerObservation(
                    observation_type="ocr_page",
                    title=f"Page {page.page_number} Extraction ({page.engine_name} - {page.routing_decision})",
                    description=(
                        f"Page {page.page_number} processed by {page.engine_name} "
                        f"({len(page.tokens)} tokens, {len(page.tables)} tables). Reason: {page.routing_reason}"
                    ),
                    severity="info",
                    categorical_confidence="high" if page.tokens else "low",
                    confidence=None,
                    page_number=page.page_number,
                    capability_id="page-level-routing",
                    evidence_payload={
                        "page_number": page.page_number,
                        "engine_name": page.engine_name,
                        "routing_decision": page.routing_decision,
                        "routing_reason": page.routing_reason,
                        "raster_area_ratio": page.raster_area_ratio,
                        "vector_char_count": page.vector_char_count,
                        "token_count": len(page.tokens),
                        "line_count": len(page.lines),
                        "table_count": len(page.tables),
                        "has_vector_text": page.has_vector_text,
                        "alternative_extractions": list(page.alternative_extractions.keys()),
                        "text_sample": page.raw_text[:200],
                    },
                )
                observations.append(page_obs)

                # Check for observation disagreements on hybrid pages
                disagreements = page.inspect_observation_disagreements()
                for dis in disagreements:
                    if dis.has_disagreement:
                        dis_obs = AnalyzerObservation(
                            observation_type="extraction_disagreement",
                            title=f"Page {page.page_number} Layer Conflict: {dis.primary_engine} vs {dis.alternative_key}",
                            description="; ".join(dis.disagreement_reasons),
                            severity="warning",
                            categorical_confidence="medium",
                            confidence=None,
                            page_number=page.page_number,
                            capability_id="dual-layer-preservation",
                            evidence_payload={
                                "page_number": page.page_number,
                                "primary_engine": dis.primary_engine,
                                "alternative_key": dis.alternative_key,
                                "primary_chars": dis.primary_char_count,
                                "alternative_chars": dis.alternative_char_count,
                                "char_delta": dis.char_count_delta,
                                "primary_tokens": dis.primary_token_count,
                                "alternative_tokens": dis.alternative_token_count,
                                "reasons": dis.disagreement_reasons,
                            },
                        )
                        observations.append(dis_obs)

                # Tables
                for tbl_idx, tbl in enumerate(page.tables):
                    tbl_obs = AnalyzerObservation(
                        observation_type="ocr_table",
                        title=f"Page {page.page_number} Table {tbl_idx + 1} ({tbl.num_rows}x{tbl.num_cols})",
                        description=f"Structured table extracted with {tbl.num_rows} rows and {tbl.num_cols} columns.",
                        severity="info",
                        categorical_confidence="medium",
                        confidence=None,
                        page_number=page.page_number,
                        bounding_box=tbl.bounding_box,
                        coordinate_system=CoordinateSystem.NORMALIZED_0_1,
                        capability_id="table-extraction",
                        evidence_payload={
                            "table_id": tbl.id,
                            "num_rows": tbl.num_rows,
                            "num_cols": tbl.num_cols,
                            "cell_count": len(tbl.cells),
                        },
                    )
                    observations.append(tbl_obs)

        except Exception as e:
            logger.exception("Hybrid OCR pipeline execution failed")
            errors.append(str(e))
            status = PipelineStatus.FAILED

        elapsed_ms = (time.perf_counter() - t0) * 1000.0

        return AnalyzerOutput(
            analyzer_id=self.analyzer_id,
            analyzer_name=self.name,
            analyzer_version=self.version,
            status=status,
            execution_duration_ms=round(elapsed_ms, 2),
            capabilities_executed=capabilities_executed,
            observations=observations,
            raw_metadata={
                "storage_artifact_key": artifact_key,
                "storage_artifact_sha256": artifact_sha256,
            },
            limitations=limitations,
            errors=errors,
        )

    def _extract_document(
        self,
        file_path: Path,
        media_type: str,
        case_id: str,
        document_id: str,
        processing_run_id: str,
        options: dict[str, Any] | None = None,
    ) -> ExtractedDocumentText:
        """Execute page-level extraction routing across PDFium, RapidOCR, and Devanagari OCR."""
        if not file_path.exists():
            raise FileNotFoundError(f"File not found for extraction: {file_path}")

        opts = options or {}
        force_ocr = bool(opts.get("force_ocr", False))
        dpi = float(opts.get("dpi", self.default_dpi))
        max_pages = int(opts.get("max_pages", self.max_pages))
        sparse_threshold = int(opts.get("sparse_threshold", self.sparse_char_threshold))
        raster_threshold = float(opts.get("raster_threshold", self.raster_coverage_threshold))
        intra_threads = opts.get("intra_op_num_threads", self.intra_op_num_threads)
        inter_threads = opts.get("inter_op_num_threads", self.inter_op_num_threads)

        engine_meta = OcrEngineMetadata(
            engine_name="Hybrid Geometry & Multilingual OCR Pipeline",
            engine_version="2.0.0",
            model_id="pypdfium2-v5.15.0+PP-OCRv4+PP-OCRv5-Devanagari",
            language=str(opts.get("language", "auto")),
            dpi=dpi,
            execution_params={
                "force_ocr": force_ocr,
                "sparse_threshold": sparse_threshold,
                "raster_threshold": raster_threshold,
                "max_pages": max_pages,
                "intra_op_num_threads": intra_threads,
                "inter_op_num_threads": inter_threads,
            },
        )

        pages: list[ExtractedPage] = []
        doc_script_chars: dict[str, int] = {}

        if media_type.lower() == "application/pdf":
            doc = None
            try:
                doc = pdfium.PdfDocument(file_path)
                total_pages = len(doc)
                if total_pages > max_pages:
                    raise ValueError(
                        f"PDF page count ({total_pages}) exceeds maximum permitted limit ({max_pages})."
                    )

                for p_idx in range(total_pages):
                    page_num = p_idx + 1
                    pdf_page = doc[p_idx]

                    try:
                        extracted_page = self._process_hybrid_page(
                            pdf_page=pdf_page,
                            page_number=page_num,
                            dpi=dpi,
                            force_ocr=force_ocr,
                            sparse_threshold=sparse_threshold,
                            raster_threshold=raster_threshold,
                            options=opts,
                        )
                    except Exception as exc:
                        logger.exception(f"Hybrid OCR failed on page {page_num}")
                        extracted_page = ExtractedPage(
                            page_number=page_num,
                            geometry=PageGeometry(
                                width=float(pdf_page.get_width()),
                                height=float(pdf_page.get_height()),
                            ),
                            raw_text="",
                            normalized_text="",
                            has_vector_text=False,
                            extraction_status="FAILED",
                            error_message=str(exc),
                            engine_name="hybrid-ocr-pipeline",
                            routing_decision=RoutingDecision("FAILED"),
                            routing_reason=f"Processing failed on page {page_num}: {exc}",
                        )
                    pages.append(extracted_page)

                    for s_k, r_v in extracted_page.script_distribution.items():
                        c_count = int(round(r_v * len(extracted_page.raw_text.strip())))
                        doc_script_chars[s_k] = doc_script_chars.get(s_k, 0) + c_count

                    pdf_page.close()

            finally:
                if doc is not None:
                    doc.close()
        else:
            # Direct raster image
            adapter, engine_name, _ = self._select_ocr_engine(vector_text="", options=opts)
            rapid_engine = adapter._get_engine(
                intra_op_num_threads=intra_threads,
                inter_op_num_threads=inter_threads,
            )
            for rendered_page in self.renderer.render_pages(
                file_path=file_path,
                media_type=media_type,
                max_pages=max_pages,
                dpi=dpi,
            ):
                try:
                    img_page = adapter.recognize_rendered_page(
                        engine=rapid_engine,
                        rendered_page=rendered_page,
                    )
                    img_page.routing_decision = RoutingDecision(PageRoutingDecision.OCR_ONLY)
                    img_page.routing_reason = (
                        "Direct raster image format; recognized via optical OCR"
                    )
                    img_page.raster_area_ratio = 1.0
                    img_page.vector_char_count = 0
                except Exception as exc:
                    logger.exception(f"Direct image OCR failed on page {rendered_page.page_number}")
                    img_page = ExtractedPage(
                        page_number=rendered_page.page_number,
                        geometry=rendered_page.geometry,
                        raw_text="",
                        normalized_text="",
                        has_vector_text=False,
                        extraction_status="FAILED",
                        error_message=str(exc),
                        engine_name="rapidocr-onnxruntime",
                        routing_decision=RoutingDecision("FAILED"),
                        routing_reason=f"Optical OCR failed on rendered image: {exc}",
                        raster_area_ratio=1.0,
                        vector_char_count=0,
                    )
                pages.append(img_page)

                for s_k, r_v in img_page.script_distribution.items():
                    c_count = int(round(r_v * len(img_page.raw_text.strip())))
                    doc_script_chars[s_k] = doc_script_chars.get(s_k, 0) + c_count

        total_tokens = sum(len(p.tokens) for p in pages)
        full_raw_text = "\n\n".join(p.raw_text for p in pages if p.raw_text)
        full_norm_text = "\n\n".join(p.normalized_text for p in pages if p.normalized_text)

        total_chars = sum(doc_script_chars.values())
        script_summary: dict[str, float] = {}
        if total_chars > 0:
            for s_k, c_v in doc_script_chars.items():
                script_summary[s_k] = round(c_v / total_chars, 4)

        return ExtractedDocumentText(
            schema_version=CURRENT_ARTIFACT_SCHEMA_VERSION,
            document_id=document_id,
            processing_run_id=processing_run_id,
            engine_metadata=engine_meta,
            pages=pages,
            total_pages=len(pages),
            total_tokens=total_tokens,
            full_raw_text=full_raw_text,
            full_normalized_text=full_norm_text,
            script_summary=script_summary,
        )

    def _process_hybrid_page(
        self,
        pdf_page: pdfium.PdfPage,
        page_number: int,
        dpi: float,
        force_ocr: bool,
        sparse_threshold: int,
        raster_threshold: float,
        options: dict[str, Any] | None = None,
    ) -> ExtractedPage:
        """Route an individual PDF page with geometry-aware raster coverage and evidence preservation."""
        opts = options or {}

        # Step 1: Always extract PDFium vector text first
        pdfium_page = self.pdfium_adapter._extract_pdf_page(pdf_page, page_number=page_number)
        clean_vector_text = pdfium_page.raw_text.strip()
        vector_char_count = len(clean_vector_text)

        # Step 2: Extract PDF geometry and compute non-overlapping raster coverage
        geometry_available = True
        raster_ratio = 0.0
        image_boxes: list[BoundingBox] = []
        total_images = 0

        if opts.get("geometry_available") is False:
            geometry_available = False
        else:
            try:
                raster_ratio, image_boxes, total_images = self._compute_raster_coverage(pdf_page)
            except Exception as geom_err:
                logger.warning(
                    f"Page {page_number} geometry calculation failed: {geom_err}; using fallback heuristic."
                )
                geometry_available = False

        # Step 3: Routing Decision Matrix
        has_meaningful_vector = vector_char_count >= sparse_threshold
        has_significant_raster = raster_ratio >= raster_threshold
        has_any_raster = raster_ratio >= 0.05 or total_images > 0

        if force_ocr:
            decision = RoutingDecision(PageRoutingDecision.OCR_ONLY)
            reason = "Forced optical OCR requested via execution options"
        elif not geometry_available:
            # Fallback to 30-character heuristic when geometry is unavailable
            if vector_char_count < sparse_threshold:
                decision = RoutingDecision(PageRoutingDecision.OCR_ONLY)
                reason = (
                    f"Geometry unavailable; fallback heuristic triggered: sparse vector text "
                    f"({vector_char_count} < {sparse_threshold} chars); optical OCR fallback"
                )
            else:
                decision = RoutingDecision(PageRoutingDecision.VECTOR_ONLY)
                reason = (
                    f"Geometry unavailable; fallback heuristic triggered: vector text "
                    f"({vector_char_count} >= {sparse_threshold} chars); PDFium primary"
                )
        elif vector_char_count == 0 and not has_any_raster:
            decision = RoutingDecision(PageRoutingDecision.NO_TEXT)
            reason = (
                f"No vector text (0 chars) and no raster content "
                f"({raster_ratio:.1%} coverage); empty page"
            )
        elif not has_meaningful_vector and not has_any_raster:
            decision = RoutingDecision(PageRoutingDecision.SPARSE_TEXT_FALLBACK)
            reason = (
                f"Sparse vector text ({vector_char_count} < {sparse_threshold} chars) with no raster content; "
                f"optical OCR fallback"
            )
        elif has_meaningful_vector and not has_significant_raster:
            decision = RoutingDecision(PageRoutingDecision.VECTOR_ONLY)
            reason = (
                f"Meaningful vector text ({vector_char_count} chars) and negligible raster coverage "
                f"({raster_ratio:.1%} < {raster_threshold:.1%}); PDFium primary"
            )
        elif has_meaningful_vector and has_significant_raster:
            decision = RoutingDecision(PageRoutingDecision.HYBRID_FUSION)
            reason = (
                f"Meaningful vector text ({vector_char_count} chars) and significant raster content "
                f"({raster_ratio:.1%} >= {raster_threshold:.1%}); hybrid fusion executed"
            )
        else:
            # Raster content requiring recognition, with little useful vector text
            decision = RoutingDecision(PageRoutingDecision.OCR_ONLY)
            reason = (
                f"Raster content requiring recognition ({raster_ratio:.1%} coverage) with little useful "
                f"vector text ({vector_char_count} chars < {sparse_threshold}); optical OCR primary"
            )

        # Step 4: Execute Engine Dispatch based on Decision
        if decision == PageRoutingDecision.NO_TEXT:
            # Blank / empty page - do NOT render image
            return ExtractedPage(
                page_number=page_number,
                geometry=pdfium_page.geometry,
                raw_text="",
                normalized_text="",
                tokens=[],
                lines=[],
                blocks=[],
                tables=[],
                layout_regions=[],
                has_vector_text=False,
                extraction_status="NO_TEXT_DETECTED",
                engine_name="hybrid-geometry-router",
                routing_decision=decision,
                routing_reason=reason,
                raster_area_ratio=raster_ratio,
                vector_char_count=vector_char_count,
            )

        if decision == PageRoutingDecision.VECTOR_ONLY:
            # Native vector text - do NOT render image
            pdfium_page.engine_name = "pypdfium2"
            pdfium_page.routing_decision = decision
            pdfium_page.routing_reason = reason
            pdfium_page.raster_area_ratio = raster_ratio
            pdfium_page.vector_char_count = vector_char_count
            return pdfium_page

        # For OCR_ONLY and HYBRID_FUSION:
        # Select OCR engine deterministically
        adapter, engine_name, engine_limitations = self._select_ocr_engine(
            vector_text=pdfium_page.raw_text,
            options=opts,
        )
        intra_threads = opts.get("intra_op_num_threads", self.intra_op_num_threads)
        inter_threads = opts.get("inter_op_num_threads", self.inter_op_num_threads)
        ocr_engine = adapter._get_engine(
            intra_op_num_threads=intra_threads,
            inter_op_num_threads=inter_threads,
        )

        # Render the page image
        rendered = self._render_single_pdf_page(pdf_page, page_number=page_number, dpi=dpi)
        optical_page = adapter.recognize_rendered_page(
            engine=ocr_engine,
            rendered_page=rendered,
        )

        optical_page.routing_decision = decision
        optical_page.routing_reason = reason
        optical_page.raster_area_ratio = raster_ratio
        optical_page.vector_char_count = vector_char_count

        # Step 5: Dual-Layer Non-Destructive Preservation
        if vector_char_count > 0:
            # Identify duplicate observations between OCR and PDFium without deleting either
            potential_duplicates: list[dict[str, Any]] = []
            for o_tok in optical_page.tokens:
                o_text = o_tok.raw_text.strip().lower()
                for p_tok in pdfium_page.tokens:
                    p_text = p_tok.raw_text.strip().lower()
                    if o_text and o_text == p_text:
                        iou = compute_box_iou(o_tok.bounding_box, p_tok.bounding_box)
                        if iou > 0.2:
                            potential_duplicates.append(
                                {
                                    "text": o_tok.raw_text,
                                    "ocr_token_id": o_tok.id,
                                    "pdfium_token_id": p_tok.id,
                                    "spatial_iou": round(iou, 3),
                                }
                            )
                            break

            alt_meta: dict[str, Any] = {
                "raster_area_ratio": raster_ratio,
                "vector_char_count": vector_char_count,
                "routing_decision": str(decision),
                "potential_duplicate_tokens": potential_duplicates,
                "sparse_threshold": sparse_threshold,
            }
            if engine_limitations:
                alt_meta["engine_limitations"] = engine_limitations

            optical_page.alternative_extractions["pdfium"] = AlternativeExtractionObservation(
                engine_name="pypdfium2",
                raw_text=pdfium_page.raw_text,
                normalized_text=pdfium_page.normalized_text,
                confidence=None,  # NEVER fabricate confidence for PDFium
                token_count=len(pdfium_page.tokens),
                line_count=len(pdfium_page.lines),
                tokens=pdfium_page.tokens,
                lines=pdfium_page.lines,
                metadata=alt_meta,
            )

        return cast(ExtractedPage, optical_page)

    def _render_single_pdf_page(
        self,
        page: pdfium.PdfPage,
        page_number: int,
        dpi: float,
    ) -> RenderedPage:
        """Render a single PDFium page with strict dimension and pixel bounds checks."""
        pt_width = float(page.get_width())
        pt_height = float(page.get_height())
        rotation = int(page.get_rotation()) % 360
        if rotation not in {0, 90, 180, 270}:
            rotation = 0

        scale = dpi / 72.0
        target_w = int(round(pt_width * scale))
        target_h = int(round(pt_height * scale))

        if target_w > MAX_PIXEL_DIMENSION or target_h > MAX_PIXEL_DIMENSION:
            raise ValueError(
                f"Rendered page dimension ({target_w}x{target_h}) exceeds maximum limit ({MAX_PIXEL_DIMENSION} px)."
            )
        if (target_w * target_h) > MAX_TOTAL_PIXELS:
            raise ValueError(
                f"Rendered page total pixels ({target_w * target_h}) exceeds maximum limit ({MAX_TOTAL_PIXELS} px)."
            )

        pil_image = page.render(scale=scale).to_pil()
        if pil_image.mode != "RGB":
            pil_image = pil_image.convert("RGB")

        geometry = PageGeometry(
            width=pt_width,
            height=pt_height,
            rotation=rotation,
            dpi=dpi,
        )

        return RenderedPage(
            page_number=page_number,
            image=pil_image,
            geometry=geometry,
            pixel_width=pil_image.width,
            pixel_height=pil_image.height,
        )
