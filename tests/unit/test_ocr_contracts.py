"""Unit tests for OCR domain contracts, models, and coordinate representations."""

import pytest

from document_intelligence.domain.enums import CoordinateSystem, LayoutRegionType
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
)


class TestOcrDomainContracts:
    """Validate Pydantic domain models, nullable confidences, stable IDs, and hierarchy."""

    def test_token_model_invariants_and_nullable_confidence(self) -> None:
        box = BoundingBox(
            x=0.1, y=0.2, width=0.3, height=0.05, coordinate_system=CoordinateSystem.NORMALIZED_0_1
        )

        # 1. Nullable confidence
        token_none_conf = TextToken(raw_text="Invoice#", bounding_box=box, confidence=None)
        assert token_none_conf.confidence is None
        assert token_none_conf.raw_text == "Invoice#"
        assert len(token_none_conf.id) == 36  # Valid UUID string

        # 2. Honest calibrated confidence
        token_calibrated = TextToken(raw_text="Invoice#", bounding_box=box, confidence=0.95)
        assert token_calibrated.confidence == 0.95

        # 3. Invalid confidence rejected
        with pytest.raises(ValueError):
            TextToken(raw_text="Invalid", confidence=1.5)

    def test_text_line_hierarchy_and_token_containment(self) -> None:
        t1 = TextToken(raw_text="Total", reading_order_index=0)
        t2 = TextToken(raw_text="Amount:", reading_order_index=1)
        t3 = TextToken(raw_text="$4,500.00", reading_order_index=2)

        line = TextLine(
            raw_text="Total Amount: $4,500.00",
            tokens=[t1, t2, t3],
            reading_order_index=5,
        )

        assert line.raw_text == "Total Amount: $4,500.00"
        assert len(line.tokens) == 3
        assert line.reading_order_index == 5
        assert line.tokens[0].raw_text == "Total"
        assert line.tokens[2].raw_text == "$4,500.00"

    def test_text_block_and_layout_region_contracts(self) -> None:
        t1 = TextToken(raw_text="CONFIDENTIAL")
        line = TextLine(raw_text="CONFIDENTIAL", tokens=[t1])
        block = TextBlock(
            block_type=LayoutRegionType.HEADER,
            raw_text="CONFIDENTIAL",
            lines=[line],
            reading_order_index=0,
        )
        assert block.block_type == LayoutRegionType.HEADER
        assert len(block.lines) == 1

        region = LayoutRegion(
            region_type=LayoutRegionType.HEADER,
            associated_block_ids=[block.id],
            reading_order_index=0,
        )
        assert region.region_type == LayoutRegionType.HEADER
        assert region.associated_block_ids == [block.id]

    def test_extracted_table_and_cell_grid_contracts(self) -> None:
        cell_header = ExtractedTableCell(
            row_index=0,
            col_index=0,
            raw_text="Item",
            is_header=True,
        )
        cell_data = ExtractedTableCell(
            row_index=1,
            col_index=0,
            raw_text="Server License",
            is_header=False,
        )

        table = ExtractedTable(
            num_rows=2,
            num_cols=1,
            cells=[cell_header, cell_data],
        )

        assert table.num_rows == 2
        assert table.num_cols == 1
        assert len(table.cells) == 2
        assert table.cells[0].is_header is True
        assert table.cells[1].is_header is False
        assert table.cells[1].raw_text == "Server License"

    def test_extracted_document_text_serialization_roundtrip(self) -> None:
        meta = OcrEngineMetadata(
            engine_name="Google PDFium Engine",
            engine_version="1.0.0",
            language="en",
            dpi=150.0,
        )
        geom = PageGeometry(width=612.0, height=792.0, rotation=0, dpi=72.0)
        tok = TextToken(raw_text="Sample")
        page = ExtractedPage(
            page_number=1,
            geometry=geom,
            raw_text="Sample",
            normalized_text="sample",
            tokens=[tok],
            has_vector_text=True,
        )
        doc = ExtractedDocumentText(
            document_id="doc-123",
            processing_run_id="run-456",
            engine_metadata=meta,
            pages=[page],
            total_pages=1,
            total_tokens=1,
            full_raw_text="Sample",
            full_normalized_text="sample",
        )

        json_str = doc.model_dump_json()
        restored = ExtractedDocumentText.model_validate_json(json_str)

        assert restored.document_id == "doc-123"
        assert restored.engine_metadata.engine_name == "Google PDFium Engine"
        assert len(restored.pages) == 1
        assert restored.pages[0].tokens[0].raw_text == "Sample"
        assert restored.total_tokens == 1

    def test_uncertain_coordinates_preserves_provenance(self) -> None:
        tok = TextToken(
            raw_text="UncertainGlyph",
            bounding_box=None,
            is_coordinate_uncertain=True,
            coordinate_uncertainty_reason="Font matrix mapping missing glyph metrics",
        )
        assert tok.bounding_box is None
        assert tok.is_coordinate_uncertain is True
        assert tok.coordinate_uncertainty_reason is not None
