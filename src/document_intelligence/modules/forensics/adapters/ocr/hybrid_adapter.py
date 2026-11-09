"""Hybrid Document Understanding and OCR Adapter coordinating PDFium and RapidOCR.

Implements intelligent page-level extraction routing:
1. Native digital PDF pages are extracted via Google PDFium (fast, 100% vector precision).
2. Scanned, image-only, or sparse-text pages are recognized via RapidOCR (ONNX).
3. Mixed documents are processed per-page with complete engine and routing provenance.
4. If optical fallback is performed, original PDFium output is preserved without duplicate merging.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any

import pypdfium2 as pdfium

from document_intelligence.domain.enums import (
    CoordinateSystem,
    PipelineStatus,
)
from document_intelligence.domain.models.bounding_box import PageGeometry
from document_intelligence.domain.models.ocr import (
    ExtractedDocumentText,
    ExtractedPage,
    OcrEngineMetadata,
)
from document_intelligence.infrastructure.storage.filesystem import FilesystemDocumentStorage
from document_intelligence.infrastructure.storage.interface import DocumentStorageProtocol
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


class HybridOcrAdapter(ForensicAnalyzer):
    """Unified hybrid OCR analyzer combining PDFium programmatic extraction and RapidOCR optical recognition."""

    def __init__(
        self,
        storage: DocumentStorageProtocol | None = None,
        max_pages: int = MAX_PAGES_DEFAULT,
        default_dpi: float = 150.0,
        sparse_char_threshold: int = DEFAULT_SPARSE_CHAR_THRESHOLD,
        intra_op_num_threads: int | None = None,
        inter_op_num_threads: int | None = None,
    ) -> None:
        self.storage = storage or FilesystemDocumentStorage()
        self.max_pages = max_pages
        self.default_dpi = default_dpi
        self.sparse_char_threshold = sparse_char_threshold
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
        return "1.0.0"

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
            "token-bounding-boxes",
            "reading-order",
            "layout-parsing",
            "table-extraction",
            "page-level-routing",
            "hybrid-provenance",
        ]

    def can_analyze(self, media_type: str) -> bool:
        return media_type.lower() in self.supported_media_types

    def analyze(self, input_data: AnalyzerInput) -> AnalyzerOutput:
        """Execute hybrid document analysis with intelligent page-level routing."""
        t0 = time.perf_counter()
        capabilities_executed: list[AnalyzerCapabilityResult] = []
        observations: list[AnalyzerObservation] = []
        errors: list[str] = []
        artifact_key: str | None = None
        artifact_sha256: str | None = None
        limitations: list[str] = [
            "Native vector text is extracted with PDFium; scanned and sparse pages route to RapidOCR.",
            "Coordinates from both engines reside in canonical top-left NORMALIZED_0_1 space.",
            "When optical OCR fallback occurs, original PDFium output is preserved under alternative_extractions without duplicate text concatenation.",
            "Page-level routing operates at the page boundary: digital pages containing both sparse vector text (>30 chars) and embedded scanned images will extract vector text unless force_ocr=True is set. Region-level OCR segmentation is not performed.",
            "Token probabilities from RapidOCR are uncalibrated model scores (confidence_calibration_method='uncalibrated_model_score'), whereas PDFium confidence is None.",
            "In-process ONNX Runtime execution cannot be safely terminated across Python threads without process-level isolation.",
            "Bundled PP-OCRv4 model does not support Devanagari (Hindi) recognition; non-Latin glyphs require dedicated models.",
        ]

        media_type = input_data.detected_media_type or input_data.declared_media_type

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

            # Capability results
            digital_pages_count = sum(
                1 for p in extracted_doc.pages if p.routing_decision == "DIGITAL_VECTOR_PRIMARY"
            )
            scanned_pages_count = len(extracted_doc.pages) - digital_pages_count - len(failed_pages)

            capabilities_executed.append(
                AnalyzerCapabilityResult(
                    capability_id="hybrid-ocr-routing",
                    status=cap_status,
                    summary=(
                        f"Processed {extracted_doc.total_pages} page(s): {digital_pages_count} digital, "
                        f"{scanned_pages_count} scanned/fallback"
                        + (f", {len(failed_pages)} failed." if failed_pages else ".")
                        + f" Total tokens: {extracted_doc.total_tokens}."
                    ),
                    details={
                        "total_pages": extracted_doc.total_pages,
                        "digital_pages": digital_pages_count,
                        "scanned_pages": scanned_pages_count,
                        "failed_pages": len(failed_pages),
                        "total_tokens": extracted_doc.total_tokens,
                    },
                )
            )

            # Summary observation
            doc_obs = AnalyzerObservation(
                observation_type="ocr_text",
                title=f"Hybrid OCR: {extracted_doc.total_tokens} Tokens Across {extracted_doc.total_pages} Page(s)",
                description=(
                    f"Hybrid document extraction complete using {self.display_name} v{self.version}. "
                    f"Digital pages: {digital_pages_count}, Scanned/OCR pages: {scanned_pages_count}."
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
                    "digital_pages": digital_pages_count,
                    "scanned_pages": scanned_pages_count,
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
                        "token_count": len(page.tokens),
                        "line_count": len(page.lines),
                        "table_count": len(page.tables),
                        "has_vector_text": page.has_vector_text,
                        "alternative_extractions": list(page.alternative_extractions.keys()),
                        "text_sample": page.raw_text[:200],
                    },
                )
                observations.append(page_obs)

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
        """Execute page-level extraction routing across PDFium and RapidOCR."""
        if not file_path.exists():
            raise FileNotFoundError(f"File not found for extraction: {file_path}")

        opts = options or {}
        force_ocr = bool(opts.get("force_ocr", False))
        dpi = float(opts.get("dpi", self.default_dpi))
        max_pages = int(opts.get("max_pages", self.max_pages))
        sparse_threshold = int(opts.get("sparse_threshold", self.sparse_char_threshold))
        intra_threads = opts.get("intra_op_num_threads", self.intra_op_num_threads)
        inter_threads = opts.get("inter_op_num_threads", self.inter_op_num_threads)

        engine_meta = OcrEngineMetadata(
            engine_name="Hybrid PDFium & RapidOCR Pipeline",
            engine_version="1.0.0",
            model_id="pypdfium2-v5.15.0+PP-OCRv4",
            language=str(opts.get("language", "en")),
            dpi=dpi,
            execution_params={
                "force_ocr": force_ocr,
                "sparse_threshold": sparse_threshold,
                "max_pages": max_pages,
                "intra_op_num_threads": intra_threads,
                "inter_op_num_threads": inter_threads,
            },
        )

        pages: list[ExtractedPage] = []

        if media_type.lower() == "application/pdf":
            doc = None
            try:
                doc = pdfium.PdfDocument(file_path)
                total_pages = len(doc)
                if total_pages > max_pages:
                    raise ValueError(
                        f"PDF page count ({total_pages}) exceeds maximum permitted limit ({max_pages})."
                    )

                rapid_engine = self.rapidocr_adapter._get_engine(
                    intra_op_num_threads=intra_threads,
                    inter_op_num_threads=inter_threads,
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
                            rapid_engine=rapid_engine,
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
                            routing_decision="FAILED",
                            routing_reason=f"Processing failed on page {page_num}: {exc}",
                        )
                    pages.append(extracted_page)
                    pdf_page.close()

            finally:
                if doc is not None:
                    doc.close()
        else:
            # Direct raster image
            rapid_engine = self.rapidocr_adapter._get_engine(
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
                    img_page = self.rapidocr_adapter.recognize_rendered_page(
                        engine=rapid_engine,
                        rendered_page=rendered_page,
                    )
                    img_page.routing_decision = "DIRECT_IMAGE_OPTICAL_OCR"
                    img_page.routing_reason = (
                        "Direct raster image format; recognized via optical OCR"
                    )
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
                        routing_decision="DIRECT_IMAGE_OPTICAL_OCR",
                        routing_reason=f"Optical OCR failed on rendered image: {exc}",
                    )
                pages.append(img_page)

        total_tokens = sum(len(p.tokens) for p in pages)
        full_raw_text = "\n\n".join(p.raw_text for p in pages if p.raw_text)
        full_norm_text = "\n\n".join(p.normalized_text for p in pages if p.normalized_text)

        return ExtractedDocumentText(
            document_id=document_id,
            processing_run_id=processing_run_id,
            engine_metadata=engine_meta,
            pages=pages,
            total_pages=len(pages),
            total_tokens=total_tokens,
            full_raw_text=full_raw_text,
            full_normalized_text=full_norm_text,
        )

    def _process_hybrid_page(
        self,
        pdf_page: pdfium.PdfPage,
        page_number: int,
        dpi: float,
        force_ocr: bool,
        sparse_threshold: int,
        rapid_engine: Any,
    ) -> ExtractedPage:
        """Route an individual PDF page between PDFium and RapidOCR."""
        # Step 1: Always extract PDFium vector text first
        pdfium_page = self.pdfium_adapter._extract_pdf_page(pdf_page, page_number=page_number)
        char_count = len(pdfium_page.raw_text.strip())

        needs_optical_ocr = False
        decision = "DIGITAL_VECTOR_PRIMARY"
        reason = f"Native vector text recovered ({char_count} chars); PDFium primary"

        if force_ocr:
            needs_optical_ocr = True
            decision = "FORCED_OPTICAL_OCR"
            reason = "Forced optical OCR requested via execution options"
        elif not pdfium_page.has_vector_text or char_count == 0:
            needs_optical_ocr = True
            decision = "IMAGE_ONLY_SCANNED_PAGE"
            reason = "Page contains no embedded vector text; routed to optical OCR"
        elif char_count < sparse_threshold:
            needs_optical_ocr = True
            decision = "SPARSE_TEXT_FALLBACK"
            reason = f"Sparse vector text ({char_count} chars < {sparse_threshold} threshold); optical OCR fallback executed"

        if not needs_optical_ocr:
            # Use PDFium result directly
            pdfium_page.engine_name = "pypdfium2"
            pdfium_page.routing_decision = decision
            pdfium_page.routing_reason = reason
            return pdfium_page

        # Render the page to image and execute RapidOCR
        rendered = self._render_single_pdf_page(pdf_page, page_number=page_number, dpi=dpi)
        optical_page = self.rapidocr_adapter.recognize_rendered_page(
            engine=rapid_engine,
            rendered_page=rendered,
        )

        optical_page.routing_decision = decision
        optical_page.routing_reason = reason
        optical_page.engine_name = "rapidocr-onnxruntime"

        # Preserve the PDFium extraction in alternative_extractions without text concatenation
        if char_count > 0:
            optical_page.alternative_extractions["pdfium"] = {
                "raw_text": pdfium_page.raw_text,
                "token_count": len(pdfium_page.tokens),
                "line_count": len(pdfium_page.lines),
                "sparse_threshold": sparse_threshold,
            }

        return optical_page

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
