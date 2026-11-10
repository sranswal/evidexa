"""Provider-neutral Optical Character Recognition adapter using RapidOCR (ONNX Runtime).

Renders scanned and image-based document pages into raster images and applies PP-OCRv4
deep learning models for text detection, angle classification, and recognition with
token-level bounding boxes and uncalibrated probabilities.
"""

from __future__ import annotations

import logging
import threading
import time
from pathlib import Path
from typing import Any

import numpy as np

from document_intelligence.domain.enums import (
    CoordinateSystem,
    LayoutRegionType,
    PipelineStatus,
)
from document_intelligence.domain.models.bounding_box import BoundingBox
from document_intelligence.domain.models.ocr import (
    ExtractedDocumentText,
    ExtractedPage,
    ExtractedTable,
    ExtractedTableCell,
    LayoutRegion,
    OcrEngineMetadata,
    TextBlock,
    TextLine,
    TextToken,
    create_traceable_token,
)
from document_intelligence.infrastructure.storage.filesystem import FilesystemDocumentStorage
from document_intelligence.infrastructure.storage.interface import DocumentStorageProtocol
from document_intelligence.modules.forensics.adapters.visual.page_renderer import (
    MAX_PAGES_DEFAULT,
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


class RapidOcrAdapter(ForensicAnalyzer):
    """Forensic analyzer adapter performing optical character recognition via RapidOCR ONNX."""

    def __init__(
        self,
        storage: DocumentStorageProtocol | None = None,
        max_pages: int = MAX_PAGES_DEFAULT,
        default_dpi: float = 150.0,
        intra_op_num_threads: int | None = None,
        inter_op_num_threads: int | None = None,
    ) -> None:
        self.storage = storage or FilesystemDocumentStorage()
        self.max_pages = max_pages
        self.default_dpi = default_dpi
        self.intra_op_num_threads = intra_op_num_threads
        self.inter_op_num_threads = inter_op_num_threads
        self.renderer = DocumentPageRenderer(max_pages=max_pages, default_dpi=default_dpi)
        self._engine: Any = None
        self._init_lock = threading.Lock()
        self._inference_lock = threading.Lock()

    def _get_engine(
        self,
        intra_op_num_threads: int | None = None,
        inter_op_num_threads: int | None = None,
    ) -> Any:
        """Lazy initialization of RapidOCR engine to avoid startup delay and memory use.

        Configures ONNX Runtime CPU execution controls (intra/inter op threads) when provided.
        """
        intra_threads = (
            intra_op_num_threads if intra_op_num_threads is not None else self.intra_op_num_threads
        )
        inter_threads = (
            inter_op_num_threads if inter_op_num_threads is not None else self.inter_op_num_threads
        )

        if self._engine is None:
            with self._init_lock:
                if self._engine is None:
                    try:
                        from rapidocr_onnxruntime import RapidOCR  # type: ignore[import-untyped]

                        kwargs: dict[str, Any] = {}
                        if intra_threads is not None:
                            kwargs["intra_op_num_threads"] = intra_threads
                        if inter_threads is not None:
                            kwargs["inter_op_num_threads"] = inter_threads

                        self._engine = RapidOCR(**kwargs)
                    except ImportError as exc:
                        raise RuntimeError(
                            "rapidocr-onnxruntime is not installed. Install it via 'pip install rapidocr-onnxruntime'."
                        ) from exc
                    except Exception as exc:
                        raise RuntimeError(f"RapidOCR engine initialization failed: {exc}") from exc
        return self._engine

    @property
    def analyzer_id(self) -> str:
        return "rapidocr-optical-engine"

    @property
    def display_name(self) -> str:
        return "RapidOCR Optical Character Recognition Engine"

    @property
    def name(self) -> str:
        return "RapidOCR Scanned Document Recognition Pipeline"

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
            "optical-character-recognition",
            "token-bounding-boxes",
            "reading-order",
            "layout-parsing",
            "table-extraction",
            "scanned-document-processing",
        ]

    def can_analyze(self, media_type: str) -> bool:
        return media_type.lower() in self.supported_media_types

    def analyze(self, input_data: AnalyzerInput) -> AnalyzerOutput:
        """Execute optical character recognition on rendered pages of the document."""
        t0 = time.perf_counter()
        capabilities_executed: list[AnalyzerCapabilityResult] = []
        observations: list[AnalyzerObservation] = []
        errors: list[str] = []
        artifact_key: str | None = None
        artifact_sha256: str | None = None
        limitations: list[str] = [
            "Optical OCR operates on rendered raster images. Resolution and scan noise affect accuracy.",
            "Coordinates are computed in canonical top-left NORMALIZED_0_1 space.",
            "Token probabilities are uncalibrated model scores (confidence_calibration_method='uncalibrated_model_score') and must not be treated as calibrated fraud confidence.",
            "In-process ONNX Runtime C++ execution cannot be preemptively terminated across Python threads without process-level isolation. Hard timeouts require process boundary execution.",
            "Bundled PP-OCRv4 recognition dictionary supports Latin/English and alphanumeric characters. Devanagari/Hindi glyphs are not supported by the default model.",
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
            capabilities_executed.append(
                AnalyzerCapabilityResult(
                    capability_id="optical-character-recognition",
                    status=cap_status,
                    summary=f"Recognized {extracted_doc.total_tokens} tokens across {extracted_doc.total_pages} page(s)"
                    + (f" ({len(failed_pages)} page(s) failed)." if failed_pages else "."),
                    details={
                        "total_pages": extracted_doc.total_pages,
                        "successful_pages": len(succeeded_pages),
                        "failed_pages": len(failed_pages),
                        "total_tokens": extracted_doc.total_tokens,
                        "raw_char_count": len(extracted_doc.full_raw_text),
                        "engine": "rapidocr_onnxruntime",
                        "model": "PP-OCRv4",
                    },
                )
            )

            # Summary observation
            doc_obs = AnalyzerObservation(
                observation_type="ocr_text",
                title=f"Optical OCR: {extracted_doc.total_tokens} Tokens Across {extracted_doc.total_pages} Page(s)",
                description=(
                    f"Optical character recognition complete using {self.display_name} v{self.version}. "
                    f"Recognized {extracted_doc.total_tokens} word tokens."
                    + (
                        f" Warning: {len(failed_pages)} page(s) failed recognition."
                        if failed_pages
                        else ""
                    )
                ),
                severity="warning" if failed_pages else "info",
                categorical_confidence="high" if extracted_doc.total_tokens > 0 else "unknown",
                confidence=None,
                capability_id="optical-character-recognition",
                evidence_payload={
                    "total_pages": extracted_doc.total_pages,
                    "successful_pages": len(succeeded_pages),
                    "failed_pages": len(failed_pages),
                    "total_tokens": extracted_doc.total_tokens,
                    "artifact_key": artifact_key,
                    "artifact_sha256": artifact_sha256,
                    "engine_name": "rapidocr-onnxruntime",
                    "text_preview": extracted_doc.full_raw_text[:300],
                },
            )
            observations.append(doc_obs)

            # Page observations
            for page in extracted_doc.pages:
                page_obs = AnalyzerObservation(
                    observation_type="ocr_page",
                    title=f"Page {page.page_number} Optical OCR ({len(page.tokens)} tokens)",
                    description=(
                        f"Page {page.page_number} optical recognition yielded {len(page.lines)} lines, "
                        f"{len(page.tokens)} tokens, and {len(page.tables)} table(s)."
                    ),
                    severity="info",
                    categorical_confidence="high" if page.tokens else "low",
                    confidence=None,
                    page_number=page.page_number,
                    capability_id="scanned-document-processing",
                    evidence_payload={
                        "page_number": page.page_number,
                        "token_count": len(page.tokens),
                        "line_count": len(page.lines),
                        "table_count": len(page.tables),
                        "has_vector_text": page.has_vector_text,
                        "extraction_status": page.extraction_status,
                        "engine_name": page.engine_name,
                        "routing_decision": page.routing_decision,
                        "routing_reason": page.routing_reason,
                        "text_sample": page.raw_text[:200],
                    },
                )
                observations.append(page_obs)

                for tbl_idx, tbl in enumerate(page.tables):
                    tbl_obs = AnalyzerObservation(
                        observation_type="ocr_table",
                        title=f"Page {page.page_number} Table {tbl_idx + 1} ({tbl.num_rows}x{tbl.num_cols})",
                        description=f"Structured table recognized with {tbl.num_rows} rows and {tbl.num_cols} columns.",
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
            logger.exception("RapidOCR optical recognition failed")
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
        """Internal sequential page extraction using RapidOCR on rendered images."""
        if not file_path.exists():
            raise FileNotFoundError(f"File not found for optical recognition: {file_path}")

        opts = options or {}
        dpi = float(opts.get("dpi", self.default_dpi))
        max_pages = int(opts.get("max_pages", self.max_pages))
        intra_threads = opts.get("intra_op_num_threads", self.intra_op_num_threads)
        inter_threads = opts.get("inter_op_num_threads", self.inter_op_num_threads)

        engine_meta = OcrEngineMetadata(
            engine_name="RapidOCR ONNX Engine",
            engine_version="1.4.4",
            model_id="PP-OCRv4",
            language=str(opts.get("language", "en")),
            dpi=dpi,
            execution_params={
                "max_pages": max_pages,
                "intra_op_num_threads": intra_threads,
                "inter_op_num_threads": inter_threads,
                "det_model": "ch_PP-OCRv4_det_infer.onnx",
                "rec_model": "ch_PP-OCRv4_rec_infer.onnx",
                "cls_model": "ch_ppocr_mobile_v2.0_cls_infer.onnx",
            },
        )

        pages: list[ExtractedPage] = []
        engine = self._get_engine(
            intra_op_num_threads=intra_threads,
            inter_op_num_threads=inter_threads,
        )

        # Render each page sequentially via DocumentPageRenderer
        for rendered_page in self.renderer.render_pages(
            file_path=file_path,
            media_type=media_type,
            max_pages=max_pages,
            dpi=dpi,
        ):
            try:
                extracted_page = self.recognize_rendered_page(
                    engine=engine,
                    rendered_page=rendered_page,
                )
            except Exception as exc:
                logger.exception(f"RapidOCR failed on page {rendered_page.page_number}")
                extracted_page = ExtractedPage(
                    page_number=rendered_page.page_number,
                    geometry=rendered_page.geometry,
                    raw_text="",
                    normalized_text="",
                    has_vector_text=False,
                    extraction_status="FAILED",
                    error_message=str(exc),
                    engine_name="rapidocr-onnxruntime",
                    routing_decision="OPTICAL_OCR",
                    routing_reason=f"Optical OCR execution failed: {exc}",
                )
            pages.append(extracted_page)

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

    def recognize_rendered_page(
        self,
        engine: Any,
        rendered_page: Any,
    ) -> ExtractedPage:
        """Execute RapidOCR on a single RenderedPage and reconstruct tokens, lines, and layout."""
        img = rendered_page.image
        width_px = rendered_page.pixel_width
        height_px = rendered_page.pixel_height

        geom = rendered_page.geometry

        # Convert PIL image to numpy RGB array for RapidOCR
        img_arr = np.array(img)

        # Run RapidOCR inference (thread-safe)
        with self._inference_lock:
            result, elapse = engine(img_arr)

        if not result:
            return ExtractedPage(
                page_number=rendered_page.page_number,
                geometry=geom,
                raw_text="",
                normalized_text="",
                has_vector_text=False,
                extraction_status="NO_TEXT_DETECTED",
                engine_name="rapidocr-onnxruntime",
                routing_decision="OPTICAL_OCR",
                routing_reason="Optical OCR yielded zero text on rendered canvas",
            )

        # result is a list of tuples: [ (poly_4pts, text, confidence), ... ]
        # poly_4pts: [[x0, y0], [x1, y1], [x2, y2], [x3, y3]] in pixel coordinates
        tokens: list[TextToken] = []
        raw_lines_list: list[str] = []

        for idx, item in enumerate(result):
            box_pts = item[0]
            text = str(item[1])
            conf = float(item[2])

            raw_lines_list.append(text)

            # Map 4-point polygon to axis-aligned canonical NORMALIZED_0_1 bounding box
            xs = [pt[0] for pt in box_pts]
            ys = [pt[1] for pt in box_pts]
            min_x_px = min(xs)
            max_x_px = max(xs)
            min_y_px = min(ys)
            max_y_px = max(ys)

            norm_x = max(0.0, min(1.0, min_x_px / float(width_px)))
            norm_y = max(0.0, min(1.0, min_y_px / float(height_px)))
            norm_w = max(0.0, min(1.0 - norm_x, (max_x_px - min_x_px) / float(width_px)))
            norm_h = max(0.0, min(1.0 - norm_y, (max_y_px - min_y_px) / float(height_px)))

            token_box = BoundingBox(
                x=round(norm_x, 4),
                y=round(norm_y, 4),
                width=round(norm_w, 4),
                height=round(norm_h, 4),
                coordinate_system=CoordinateSystem.NORMALIZED_0_1,
            )

            token = create_traceable_token(
                raw_text=text,
                bounding_box=token_box,
                confidence=round(conf, 4),
                reading_order_index=idx,
                metadata={
                    "polygon": box_pts,
                    "model": "PP-OCRv4",
                    "confidence_calibration_method": "uncalibrated_model_score",
                },
            )
            tokens.append(token)

        # Cluster tokens into lines
        lines = self._cluster_tokens_into_lines(tokens)

        # Blocks and layout regions
        blocks, layout_regions = self._segment_blocks_and_layout(lines)

        # Tables
        tables = self._detect_tables_from_lines(lines)

        page_raw_text = "\n".join(ln.raw_text for ln in lines)
        page_norm_text = "\n".join(ln.normalized_text or ln.raw_text for ln in lines)

        return ExtractedPage(
            page_number=rendered_page.page_number,
            geometry=geom,
            raw_text=page_raw_text,
            normalized_text=page_norm_text,
            tokens=tokens,
            lines=lines,
            blocks=blocks,
            tables=tables,
            layout_regions=layout_regions,
            has_vector_text=False,
            extraction_status="SUCCEEDED",
            engine_name="rapidocr-onnxruntime",
            routing_decision="OPTICAL_OCR",
            routing_reason="Optical OCR executed on rendered page image",
        )

    def _cluster_tokens_into_lines(self, tokens: list[TextToken]) -> list[TextLine]:
        """Group recognized tokens into lines based on vertical overlap and horizontal position."""
        if not tokens:
            return []

        valid_tokens = [t for t in tokens if t.bounding_box is not None]
        uncertain_tokens = [t for t in tokens if t.bounding_box is None]

        sorted_tokens = sorted(
            valid_tokens,
            key=lambda t: (t.bounding_box.y, t.bounding_box.x),  # type: ignore[union-attr]
        )

        lines: list[TextLine] = []
        y_tolerance = 0.015  # ~1.5% of page height

        current_line_tokens: list[TextToken] = []
        current_y = 0.0

        for token in sorted_tokens:
            box = token.bounding_box
            assert box is not None
            y_center = box.y + box.height / 2.0

            if not current_line_tokens:
                current_line_tokens.append(token)
                current_y = y_center
            elif abs(y_center - current_y) <= y_tolerance:
                current_line_tokens.append(token)
            else:
                line = self._create_line_from_tokens(
                    current_line_tokens, reading_order_idx=len(lines)
                )
                lines.append(line)
                current_line_tokens = [token]
                current_y = y_center

        if current_line_tokens:
            line = self._create_line_from_tokens(current_line_tokens, reading_order_idx=len(lines))
            lines.append(line)

        for u in uncertain_tokens:
            lines.append(
                TextLine(
                    raw_text=u.raw_text,
                    normalized_text=u.normalized_text,
                    bounding_box=None,
                    confidence=u.confidence,
                    tokens=[u],
                    reading_order_index=len(lines),
                )
            )

        return lines

    def _create_line_from_tokens(self, tokens: list[TextToken], reading_order_idx: int) -> TextLine:
        """Create a TextLine enclosing a group of horizontally ordered tokens."""
        sorted_tokens = sorted(
            tokens,
            key=lambda t: t.bounding_box.x if t.bounding_box else 0.0,
        )
        raw_text = " ".join(t.raw_text for t in sorted_tokens)
        norm_text = " ".join(t.normalized_text or t.raw_text for t in sorted_tokens).strip()

        boxes = [t.bounding_box for t in sorted_tokens if t.bounding_box]
        line_box = None
        avg_conf = None

        confs = [t.confidence for t in sorted_tokens if t.confidence is not None]
        if confs:
            avg_conf = round(sum(confs) / len(confs), 4)

        if boxes:
            min_x = min(b.x for b in boxes)
            min_y = min(b.y for b in boxes)
            max_r = max(b.x + b.width for b in boxes)
            max_b = max(b.y + b.height for b in boxes)
            line_box = BoundingBox(
                x=min_x,
                y=min_y,
                width=max_r - min_x,
                height=max_b - min_y,
                coordinate_system=CoordinateSystem.NORMALIZED_0_1,
            )

        return TextLine(
            raw_text=raw_text,
            normalized_text=norm_text,
            bounding_box=line_box,
            confidence=avg_conf,
            tokens=sorted_tokens,
            reading_order_index=reading_order_idx,
            metadata={"confidence_calibration_method": "uncalibrated_model_score"},
        )

    def _segment_blocks_and_layout(
        self, lines: list[TextLine]
    ) -> tuple[list[TextBlock], list[LayoutRegion]]:
        """Group lines into paragraphs/blocks and identify high-level layout regions."""
        blocks: list[TextBlock] = []
        layout_regions: list[LayoutRegion] = []

        if not lines:
            return blocks, layout_regions

        for line in lines:
            box = line.bounding_box
            if not box:
                continue

            region_type = LayoutRegionType.PARAGRAPH
            if box.y < 0.12:
                region_type = LayoutRegionType.HEADER
            elif box.y > 0.88:
                region_type = LayoutRegionType.FOOTER
            elif box.height > 0.035:
                region_type = LayoutRegionType.TITLE

            block = TextBlock(
                block_type=region_type,
                raw_text=line.raw_text,
                normalized_text=line.normalized_text,
                bounding_box=line.bounding_box,
                lines=[line],
                reading_order_index=len(blocks),
            )
            blocks.append(block)

            region = LayoutRegion(
                region_type=region_type,
                bounding_box=line.bounding_box,
                reading_order_index=len(layout_regions),
                associated_block_ids=[block.id],
            )
            layout_regions.append(region)

        return blocks, layout_regions

    def _detect_tables_from_lines(self, lines: list[TextLine]) -> list[ExtractedTable]:
        """Detect tabular line rows aligned across multiple distinct columns."""
        tables: list[ExtractedTable] = []
        if len(lines) < 3:
            return tables

        multi_col_lines = []
        for line in lines:
            if len(line.tokens) >= 3 and line.bounding_box:
                multi_col_lines.append(line)

        if len(multi_col_lines) >= 3:
            num_rows = len(multi_col_lines)
            max_cols = max(len(ln.tokens) for ln in multi_col_lines)

            cells: list[ExtractedTableCell] = []
            for r_idx, line in enumerate(multi_col_lines):
                for c_idx, token in enumerate(line.tokens):
                    cell = ExtractedTableCell(
                        row_index=r_idx,
                        col_index=c_idx,
                        raw_text=token.raw_text,
                        normalized_text=token.normalized_text,
                        bounding_box=token.bounding_box,
                        confidence=token.confidence,
                        is_header=(r_idx == 0),
                        tokens=[token],
                    )
                    cells.append(cell)

            min_x = min(ln.bounding_box.x for ln in multi_col_lines if ln.bounding_box)
            min_y = min(ln.bounding_box.y for ln in multi_col_lines if ln.bounding_box)
            max_r = max(
                ln.bounding_box.x + ln.bounding_box.width
                for ln in multi_col_lines
                if ln.bounding_box
            )
            max_b = max(
                ln.bounding_box.y + ln.bounding_box.height
                for ln in multi_col_lines
                if ln.bounding_box
            )

            tbl_box = BoundingBox(
                x=min_x,
                y=min_y,
                width=max_r - min_x,
                height=max_b - min_y,
                coordinate_system=CoordinateSystem.NORMALIZED_0_1,
            )

            confs = [c.confidence for c in cells if c.confidence is not None]
            tbl_conf = round(sum(confs) / len(confs), 4) if confs else None

            table = ExtractedTable(
                num_rows=num_rows,
                num_cols=max_cols,
                cells=cells,
                bounding_box=tbl_box,
                confidence=tbl_conf,
                reading_order_index=0,
            )
            tables.append(table)

        return tables
