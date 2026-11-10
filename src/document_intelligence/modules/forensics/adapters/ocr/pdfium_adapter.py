"""Provider-neutral Document Understanding and OCR Engine adapter using Google PDFium.

Extracts searchable text, token-level bounding boxes, reading order, layout blocks,
and tabular structures with complete provenance and resource-limit enforcement.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path

import pypdfium2 as pdfium
from PIL import Image

from document_intelligence.domain.enums import (
    CoordinateSystem,
    LayoutRegionType,
    PipelineStatus,
)
from document_intelligence.domain.models.bounding_box import BoundingBox, PageGeometry
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


class PdfiumOcrAdapter(ForensicAnalyzer):
    """Engine-independent OCR and Document Understanding adapter backed by Google PDFium."""

    def __init__(
        self,
        storage: DocumentStorageProtocol | None = None,
        max_pages: int = MAX_PAGES_DEFAULT,
        default_dpi: float = 150.0,
    ) -> None:
        self.storage = storage or FilesystemDocumentStorage()
        self.max_pages = max_pages
        self.default_dpi = default_dpi
        self.renderer = DocumentPageRenderer(max_pages=max_pages, default_dpi=default_dpi)

    @property
    def analyzer_id(self) -> str:
        return "pdfium-ocr-engine"

    @property
    def display_name(self) -> str:
        return "PDFium Document Understanding & OCR Engine"

    @property
    def name(self) -> str:
        return "PDFium Document Understanding & OCR Pipeline"

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
        }

    @property
    def supported_capabilities(self) -> list[str]:
        return [
            "text-extraction",
            "token-bounding-boxes",
            "reading-order",
            "layout-parsing",
            "table-extraction",
        ]

    def can_analyze(self, media_type: str) -> bool:
        return media_type.lower() in self.supported_media_types

    def analyze(self, input_data: AnalyzerInput) -> AnalyzerOutput:
        """Execute document text and layout extraction on the verified snapshot."""
        t0 = time.perf_counter()
        capabilities_executed: list[AnalyzerCapabilityResult] = []
        observations: list[AnalyzerObservation] = []
        errors: list[str] = []
        artifact_key: str | None = None
        artifact_sha256: str | None = None
        limitations: list[str] = [
            "Programmatic vector extraction captures native PDF fonts. Scanned pages require optical OCR.",
            "Rotated text frames are mapped into canonical top-left normalized coordinates.",
            "Table extraction uses spatial grid alignment and line geometry heuristics.",
        ]

        media_type = input_data.detected_media_type or input_data.declared_media_type

        try:
            extracted_doc = self._extract_document(
                file_path=input_data.file_path,
                media_type=media_type,
                case_id=input_data.case_id,
                document_id=input_data.document_id,
                processing_run_id=input_data.processing_run_id,
            )

            # Persist full extracted document model as storage artifact
            artifact_key = None
            artifact_sha256 = None
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

            # Generate capability results
            capabilities_executed.append(
                AnalyzerCapabilityResult(
                    capability_id="text-extraction",
                    status="PASS",
                    summary=f"Extracted {extracted_doc.total_tokens} tokens across {extracted_doc.total_pages} page(s).",
                    details={
                        "total_pages": extracted_doc.total_pages,
                        "total_tokens": extracted_doc.total_tokens,
                        "raw_char_count": len(extracted_doc.full_raw_text),
                    },
                )
            )

            # Generate observations
            # 1. Document summary observation
            doc_obs = AnalyzerObservation(
                observation_type="ocr_text",
                title=f"Extracted Text: {extracted_doc.total_tokens} Tokens Across {extracted_doc.total_pages} Page(s)",
                description=(
                    f"Document text extraction complete using {self.display_name} v{self.version}. "
                    f"Recovered {extracted_doc.total_tokens} word tokens."
                ),
                severity="info",
                categorical_confidence="high" if extracted_doc.total_tokens > 0 else "unknown",
                confidence=None,  # Honest nullable confidence
                capability_id="text-extraction",
                evidence_payload={
                    "total_pages": extracted_doc.total_pages,
                    "total_tokens": extracted_doc.total_tokens,
                    "artifact_key": artifact_key,
                    "artifact_sha256": artifact_sha256,
                    "text_preview": extracted_doc.full_raw_text[:300],
                },
            )
            observations.append(doc_obs)

            # 2. Per-page and layout observations
            for page in extracted_doc.pages:
                page_obs = AnalyzerObservation(
                    observation_type="ocr_page",
                    title=f"Page {page.page_number} Text Content ({len(page.tokens)} tokens)",
                    description=(
                        f"Page {page.page_number} yielded {len(page.lines)} lines, "
                        f"{len(page.tokens)} tokens, and {len(page.tables)} table(s). "
                        f"Vector layer status: {'Native' if page.has_vector_text else 'Scanned/Raster'}."
                    ),
                    severity="info",
                    categorical_confidence="high" if page.has_vector_text else "low",
                    confidence=None,
                    page_number=page.page_number,
                    capability_id="layout-parsing",
                    evidence_payload={
                        "page_number": page.page_number,
                        "token_count": len(page.tokens),
                        "line_count": len(page.lines),
                        "table_count": len(page.tables),
                        "has_vector_text": page.has_vector_text,
                        "extraction_status": page.extraction_status,
                        "text_sample": page.raw_text[:200],
                    },
                )
                observations.append(page_obs)

                # 3. Table observations
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

            status = PipelineStatus.SUCCEEDED

        except Exception as e:
            logger.exception("OCR extraction failed")
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
    ) -> ExtractedDocumentText:
        """Internal worker extracting structured text, lines, blocks, and tables."""
        if not file_path.exists():
            raise FileNotFoundError(f"File not found for extraction: {file_path}")

        engine_meta = OcrEngineMetadata(
            engine_name="Google PDFium Text Engine",
            engine_version=self.version,
            model_id="pypdfium2-v5.15.0",
            language="en",
            dpi=self.default_dpi,
            execution_params={"max_pages": self.max_pages},
        )

        pages: list[ExtractedPage] = []

        if media_type.lower() == "application/pdf":
            doc = pdfium.PdfDocument(file_path)
            total_pages = len(doc)
            if total_pages > self.max_pages:
                doc.close()
                raise ValueError(
                    f"PDF page count ({total_pages}) exceeds maximum permitted limit ({self.max_pages})."
                )

            for p_idx in range(total_pages):
                page = doc[p_idx]
                extracted_page = self._extract_pdf_page(page, page_number=p_idx + 1)
                pages.append(extracted_page)
                page.close()

            doc.close()
        else:
            # Direct raster image (PNG, JPEG, etc.)
            extracted_page = self._extract_raster_image(file_path, page_number=1)
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

    def _extract_pdf_page(self, page: pdfium.PdfPage, page_number: int) -> ExtractedPage:
        """Extract structured text, lines, and layout from a single PDFium page."""
        width_pts = float(page.get_width())
        height_pts = float(page.get_height())
        rotation = int(page.get_rotation())

        geom = PageGeometry(
            width=width_pts,
            height=height_pts,
            rotation=rotation,
            dpi=72.0,
        )

        textpage = page.get_textpage()
        char_count = textpage.count_chars()

        if char_count == 0:
            textpage.close()
            return ExtractedPage(
                page_number=page_number,
                geometry=geom,
                raw_text="",
                normalized_text="",
                has_vector_text=False,
                extraction_status="SCANNED_PAGE_DETECTED",
            )

        # Unrotated native dimensions in MediaBox
        # If rotation is 90 or 270, unrotated width and height are swapped
        if rotation in (90, 270):
            unrot_w = height_pts
            unrot_h = width_pts
        else:
            unrot_w = width_pts
            unrot_h = height_pts

        unrot_geom = PageGeometry(width=unrot_w, height=unrot_h, rotation=0, dpi=72.0)

        # 1. Token extraction
        tokens: list[TextToken] = []
        current_token_chars: list[str] = []
        current_char_boxes: list[tuple[float, float, float, float]] = []

        for c_idx in range(char_count):
            ch = textpage.get_text_range(index=c_idx, count=1)
            if ch.isspace():
                if current_token_chars:
                    token = self._build_token(
                        chars=current_token_chars,
                        boxes=current_char_boxes,
                        unrot_geom=unrot_geom,
                        rotation=rotation,
                        reading_order_idx=len(tokens),
                    )
                    tokens.append(token)
                    current_token_chars = []
                    current_char_boxes = []
            else:
                current_token_chars.append(ch)
                box = textpage.get_charbox(c_idx)
                current_char_boxes.append(box)

        if current_token_chars:
            token = self._build_token(
                chars=current_token_chars,
                boxes=current_char_boxes,
                unrot_geom=unrot_geom,
                rotation=rotation,
                reading_order_idx=len(tokens),
            )
            tokens.append(token)

        textpage.close()

        # 2. Cluster tokens into lines
        lines = self._cluster_tokens_into_lines(tokens)

        # 3. Detect blocks and reading order
        blocks, layout_regions = self._segment_blocks_and_layout(lines)

        # 4. Detect tables
        tables = self._detect_tables_from_lines(lines)

        page_raw_text = "\n".join(line.raw_text for line in lines)
        page_norm_text = "\n".join(line.normalized_text or line.raw_text for line in lines)

        return ExtractedPage(
            page_number=page_number,
            geometry=geom,
            raw_text=page_raw_text,
            normalized_text=page_norm_text,
            tokens=tokens,
            lines=lines,
            blocks=blocks,
            tables=tables,
            layout_regions=layout_regions,
            has_vector_text=True,
            extraction_status="SUCCEEDED",
        )

    def _build_token(
        self,
        chars: list[str],
        boxes: list[tuple[float, float, float, float]],
        unrot_geom: PageGeometry,
        rotation: int,
        reading_order_idx: int,
    ) -> TextToken:
        raw_text = "".join(chars)

        if not boxes:
            return create_traceable_token(
                raw_text=raw_text,
                bounding_box=None,
                confidence=None,
                reading_order_index=reading_order_idx,
                is_coordinate_uncertain=True,
                coordinate_uncertainty_reason="No character bounding box data returned by engine",
                metadata={"confidence_calibration_method": "not_applicable_vector_extraction"},
            )

        min_x = min(b[0] for b in boxes)
        min_y = min(b[1] for b in boxes)
        max_x = max(b[2] for b in boxes)
        max_y = max(b[3] for b in boxes)

        # Unrotated top-left normalized
        unrot_box = BoundingBox.from_pdf_points(
            x0=min_x,
            y0=min_y,
            x1=max_x,
            y1=max_y,
            page_width=unrot_geom.width,
            page_height=unrot_geom.height,
        )

        canonical_box = unrot_box.apply_rotation(unrot_geom, rotation)

        return create_traceable_token(
            raw_text=raw_text,
            bounding_box=canonical_box,
            confidence=None,  # PDFium programmatic text has no calibrated confidence; nullable
            reading_order_index=reading_order_idx,
            metadata={"confidence_calibration_method": "not_applicable_vector_extraction"},
        )

    def _cluster_tokens_into_lines(self, tokens: list[TextToken]) -> list[TextLine]:
        """Group tokens into lines based on vertical overlap and horizontal reading order."""
        if not tokens:
            return []

        # Sort tokens primarily by y, then by x
        valid_tokens = [t for t in tokens if t.bounding_box is not None]
        uncertain_tokens = [t for t in tokens if t.bounding_box is None]

        # Group tokens with similar y-center
        lines: list[TextLine] = []
        y_tolerance = 0.012  # ~1.2% of page height

        sorted_tokens = sorted(valid_tokens, key=lambda t: (t.bounding_box.y, t.bounding_box.x))  # type: ignore[union-attr]

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
                # Finish line
                line = self._create_line_from_tokens(
                    current_line_tokens, reading_order_idx=len(lines)
                )
                lines.append(line)
                current_line_tokens = [token]
                current_y = y_center

        if current_line_tokens:
            line = self._create_line_from_tokens(current_line_tokens, reading_order_idx=len(lines))
            lines.append(line)

        # Append uncertain tokens at end if any
        if uncertain_tokens:
            unc_line = TextLine(
                raw_text=" ".join(t.raw_text for t in uncertain_tokens),
                tokens=uncertain_tokens,
                reading_order_index=len(lines),
                is_coordinate_uncertain=True,
            )
            lines.append(unc_line)

        return lines

    def _create_line_from_tokens(self, tokens: list[TextToken], reading_order_idx: int) -> TextLine:
        # Sort tokens on line strictly left to right
        sorted_tokens = sorted(tokens, key=lambda t: t.bounding_box.x if t.bounding_box else 0.0)
        raw_text = " ".join(t.raw_text for t in sorted_tokens)
        norm_text = " ".join(t.normalized_text or t.raw_text for t in sorted_tokens)

        # Enclosing bounding box
        boxes = [t.bounding_box for t in sorted_tokens if t.bounding_box]
        line_box = None
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
            confidence=None,
            tokens=sorted_tokens,
            reading_order_index=reading_order_idx,
            metadata={"confidence_calibration_method": "not_applicable_vector_extraction"},
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

            # Classify line type
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

        # Find lines that contain 3 or more separated tokens
        multi_col_lines = []
        for line in lines:
            if len(line.tokens) >= 3 and line.bounding_box:
                multi_col_lines.append(line)

        if len(multi_col_lines) >= 3:
            # We have a candidate table
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

            table = ExtractedTable(
                num_rows=num_rows,
                num_cols=max_cols,
                cells=cells,
                bounding_box=tbl_box,
                confidence=None,
                reading_order_index=0,
            )
            tables.append(table)

        return tables

    def _extract_raster_image(self, image_path: Path, page_number: int) -> ExtractedPage:
        """Handle scanned/raster image by inspecting dimensions and recording scanned status."""
        with Image.open(image_path) as img:
            w, h = img.size

        geom = PageGeometry(width=float(w), height=float(h), rotation=0, dpi=self.default_dpi)

        return ExtractedPage(
            page_number=page_number,
            geometry=geom,
            raw_text="",
            normalized_text="",
            has_vector_text=False,
            extraction_status="SCANNED_IMAGE_DETECTED",
        )
