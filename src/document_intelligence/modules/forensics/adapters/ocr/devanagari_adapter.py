"""Provider-neutral Multilingual OCR Adapter using RapidOCR PP-OCRv5 Devanagari Mobile.

Provides high-precision bilingual Hindi (Devanagari) and English (Latin) text
recognition, token-level bounding boxes, deterministic script attribution, and
traceable numeral normalization with strict cryptographic model integrity verification.
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
    PageRoutingDecision,
    PipelineStatus,
)
from document_intelligence.domain.models.bounding_box import BoundingBox
from document_intelligence.domain.models.ocr import (
    CURRENT_ARTIFACT_SCHEMA_VERSION,
    ExtractedDocumentText,
    ExtractedPage,
    OcrEngineMetadata,
    TextToken,
    create_traceable_token,
)
from document_intelligence.infrastructure.storage.interface import DocumentStorageProtocol
from document_intelligence.modules.forensics.adapters.ocr.artifact_manager import (
    PP_OCRV5_DEVANAGARI,
    ApprovedModelArtifact,
    OcrModelArtifactManager,
    VerifiedModelArtifact,
)
from document_intelligence.modules.forensics.adapters.ocr.rapidocr_adapter import RapidOcrAdapter
from document_intelligence.modules.forensics.adapters.visual.page_renderer import (
    MAX_PAGES_DEFAULT,
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

# Resource and security limits
MAX_PIXEL_DIMENSION = 8192
MAX_TOTAL_PIXELS = 36_000_000  # 36 MP
MAX_IMAGE_FILE_SIZE_BYTES = 50 * 1024 * 1024  # 50 MB


class DevanagariRapidOcrAdapter(RapidOcrAdapter, ForensicAnalyzer):
    """Forensic OCR adapter utilizing PP-OCRv5 Devanagari Mobile via RapidOCR ONNX Runtime."""

    def __init__(
        self,
        storage: DocumentStorageProtocol | None = None,
        artifact_manager: OcrModelArtifactManager | None = None,
        model_artifact: ApprovedModelArtifact = PP_OCRV5_DEVANAGARI,
        max_pages: int = MAX_PAGES_DEFAULT,
        default_dpi: float = 150.0,
        box_thresh: float = 0.3,
        unclip_ratio: float = 1.6,
        use_cls: bool = False,
        rec_img_shape: list[int] | None = None,
        intra_op_num_threads: int | None = 2,
        inter_op_num_threads: int | None = 1,
    ) -> None:
        super().__init__(
            storage=storage,
            max_pages=max_pages,
            default_dpi=default_dpi,
            intra_op_num_threads=intra_op_num_threads,
            inter_op_num_threads=inter_op_num_threads,
        )
        self.artifact_manager = artifact_manager or OcrModelArtifactManager()
        self.model_artifact = model_artifact
        self.box_thresh = box_thresh
        self.unclip_ratio = unclip_ratio
        self.use_cls = use_cls
        self.rec_img_shape = rec_img_shape or [3, 48, 320]
        self._verified_artifact: VerifiedModelArtifact | None = None
        self._init_lock = threading.Lock()
        self._inference_lock = threading.Lock()
        self._engine: Any = None

    @property
    def analyzer_id(self) -> str:
        return "ppocrv5-devanagari-engine"

    @property
    def display_name(self) -> str:
        return "RapidOCR PP-OCRv5 Devanagari & Hindi Optical Recognition Engine"

    @property
    def name(self) -> str:
        return "PP-OCRv5 Devanagari Scanned Document Recognition Pipeline"

    @property
    def version(self) -> str:
        return "2.0.0"

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
            "traceable-normalization",
            "numeral-conversion",
        ]

    def _get_engine(
        self,
        intra_op_num_threads: int | None = None,
        inter_op_num_threads: int | None = None,
    ) -> Any:
        """Lazy, thread-safe initialization of RapidOCR with verified PP-OCRv5 Devanagari weights."""
        if self._engine is not None:
            return self._engine

        with self._init_lock:
            # Double-check locking
            if self._engine is not None:
                return self._engine

            try:
                from rapidocr_onnxruntime import RapidOCR  # type: ignore[import-untyped]
            except ImportError as exc:
                raise RuntimeError(
                    "rapidocr-onnxruntime is not installed. Install it via 'pip install rapidocr-onnxruntime'."
                ) from exc

            # 1. Cryptographically verify model and dictionary artifacts
            try:
                verified = self.artifact_manager.verify_artifact(self.model_artifact)
                self._verified_artifact = verified
            except Exception as exc:
                self._engine = None
                self._verified_artifact = None
                # Log safe diagnostic without exposing absolute paths
                logger.error(f"OCR model artifact verification failed: {type(exc).__name__}: {exc}")
                raise

            # 2. Configure ONNX Runtime and RapidOCR parameters
            intra_threads = (
                intra_op_num_threads
                if intra_op_num_threads is not None
                else self.intra_op_num_threads
            )
            inter_threads = (
                inter_op_num_threads
                if inter_op_num_threads is not None
                else self.inter_op_num_threads
            )

            kwargs: dict[str, Any] = {
                "rec_model_path": str(verified.model_path),
                "rec_keys_path": str(verified.dictionary_path),
                "rec_img_shape": self.rec_img_shape,
                "use_cls": self.use_cls,
                "box_thresh": self.box_thresh,
                "unclip_ratio": self.unclip_ratio,
            }
            if intra_threads is not None:
                kwargs["intra_op_num_threads"] = intra_threads
            if inter_threads is not None:
                kwargs["inter_op_num_threads"] = inter_threads

            try:
                self._engine = RapidOCR(**kwargs)
            except Exception as exc:
                self._engine = None
                self._verified_artifact = None
                logger.error(f"RapidOCR PP-OCRv5 engine initialization failed: {exc}")
                raise RuntimeError(f"RapidOCR engine initialization failed: {exc}") from exc

            return self._engine

    def recognize_rendered_page(
        self,
        engine: Any,
        rendered_page: RenderedPage,
    ) -> ExtractedPage:
        """Execute PP-OCRv5 Devanagari OCR on a single rendered page with thread-safe inference."""
        img = rendered_page.image
        width_px = rendered_page.pixel_width
        height_px = rendered_page.pixel_height
        geom = rendered_page.geometry

        # Pre-allocation dimension guards
        if width_px > MAX_PIXEL_DIMENSION or height_px > MAX_PIXEL_DIMENSION:
            raise ValueError(
                f"Page image dimension ({width_px}x{height_px}) exceeds maximum allowed ({MAX_PIXEL_DIMENSION} px)."
            )
        if (width_px * height_px) > MAX_TOTAL_PIXELS:
            raise ValueError(
                f"Page total pixels ({width_px * height_px}) exceeds maximum allowed ({MAX_TOTAL_PIXELS} px)."
            )

        # Convert to numpy array for inference
        img_arr = np.array(img)

        # Execute thread-safe inference
        with self._inference_lock:
            result, _ = engine(img_arr)

        if not result:
            return ExtractedPage(
                page_number=rendered_page.page_number,
                geometry=geom,
                raw_text="",
                normalized_text="",
                has_vector_text=False,
                extraction_status="NO_TEXT_DETECTED",
                engine_name="rapidocr-ppocrv5-devanagari",
                routing_decision=PageRoutingDecision.OPTICAL_OCR,
                routing_reason="Optical OCR yielded zero text on rendered canvas",
            )

        tokens: list[TextToken] = []
        script_counts: dict[str, int] = {}
        total_chars_by_script: dict[str, int] = {}

        for idx, item in enumerate(result):
            box_pts = item[0]
            raw_text = str(item[1])
            conf = float(item[2])

            # Convert 4-point polygon to normalized axis-aligned bounding box
            xs = [pt[0] for pt in box_pts]
            ys = [pt[1] for pt in box_pts]
            min_x = min(xs)
            max_x = max(xs)
            min_y = min(ys)
            max_y = max(ys)

            norm_x = max(0.0, min(1.0, min_x / float(width_px)))
            norm_y = max(0.0, min(1.0, min_y / float(height_px)))
            norm_w = max(0.0, min(1.0 - norm_x, (max_x - min_x) / float(width_px)))
            norm_h = max(0.0, min(1.0 - norm_y, (max_y - min_y) / float(height_px)))

            token_box = BoundingBox(
                x=round(norm_x, 4),
                y=round(norm_y, 4),
                width=round(norm_w, 4),
                height=round(norm_h, 4),
                coordinate_system=CoordinateSystem.NORMALIZED_0_1,
            )

            # Construct traceable token with deterministic script attribution and NFC normalization
            tok = create_traceable_token(
                raw_text=raw_text,
                bounding_box=token_box,
                confidence=round(conf, 4),
                reading_order_index=idx,
                metadata={
                    "polygon": box_pts,
                    "model": "PP-OCRv5-Devanagari-Mobile",
                    "confidence_calibration_method": "uncalibrated_model_score",
                },
            )
            tokens.append(tok)

            # Track script statistics
            s_name = str(tok.detected_script) if tok.detected_script else "UNKNOWN"
            script_counts[s_name] = script_counts.get(s_name, 0) + 1
            char_len = len(raw_text.strip())
            total_chars_by_script[s_name] = total_chars_by_script.get(s_name, 0) + char_len

        # Cluster tokens into lines and assign line dominant scripts
        lines = self._cluster_tokens_into_lines(tokens)
        for ln in lines:
            line_scripts: dict[str, int] = {}
            for t in ln.tokens:
                s = str(t.detected_script) if t.detected_script else "UNKNOWN"
                line_scripts[s] = line_scripts.get(s, 0) + 1
            ln.script_token_counts = line_scripts
            if line_scripts:
                ln.dominant_script = max(line_scripts.items(), key=lambda kv: kv[1])[0]

        # Structure blocks and layout regions
        blocks, layout_regions = self._segment_blocks_and_layout(lines)
        tables = self._detect_tables_from_lines(lines)

        page_raw_text = "\n".join(ln.raw_text for ln in lines)
        page_norm_text = "\n".join(ln.normalized_text or ln.raw_text for ln in lines)

        # Compute page script distribution
        total_meaningful_chars = sum(total_chars_by_script.values())
        script_distribution: dict[str, float] = {}
        if total_meaningful_chars > 0:
            for s_k, c_v in total_chars_by_script.items():
                script_distribution[s_k] = round(c_v / total_meaningful_chars, 4)

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
            engine_name="rapidocr-ppocrv5-devanagari",
            routing_decision=PageRoutingDecision.OPTICAL_OCR,
            routing_reason="PP-OCRv5 Devanagari optical OCR executed on rendered canvas",
            script_distribution=script_distribution,
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
        """Execute PP-OCRv5 Devanagari extraction across document pages."""
        if not file_path.exists():
            raise FileNotFoundError(f"File not found for extraction: {file_path}")

        # Check maximum file size limit
        file_size = file_path.stat().st_size
        if file_size > MAX_IMAGE_FILE_SIZE_BYTES:
            raise ValueError(
                f"Document file size ({file_size} bytes) exceeds maximum permitted limit ({MAX_IMAGE_FILE_SIZE_BYTES} bytes)."
            )

        opts = options or {}
        dpi = float(opts.get("dpi", self.default_dpi))
        max_pages = int(opts.get("max_pages", self.max_pages))
        intra_threads = opts.get("intra_op_num_threads", self.intra_op_num_threads)
        inter_threads = opts.get("inter_op_num_threads", self.inter_op_num_threads)

        engine = self._get_engine(
            intra_op_num_threads=intra_threads,
            inter_op_num_threads=inter_threads,
        )

        verified = self._verified_artifact or self.artifact_manager.verify_artifact(
            self.model_artifact
        )

        try:
            import onnxruntime  # type: ignore[import-untyped]

            runtime_ver = onnxruntime.__version__
        except Exception:
            runtime_ver = "unknown"

        engine_meta = OcrEngineMetadata(
            engine_name="RapidOCR PP-OCRv5 Devanagari",
            engine_version="2.0.0",
            model_id=verified.model_filename,
            character_dict_name=verified.dictionary_filename,
            model_artifacts={
                "rec_model": verified.model_sha256,
                "rec_dict": verified.dictionary_sha256,
            },
            runtime_name="ONNXRuntime-CPU",
            runtime_version=runtime_ver,
            language=str(opts.get("language", "hi+en")),
            dpi=dpi,
            execution_params={
                "box_thresh": self.box_thresh,
                "unclip_ratio": self.unclip_ratio,
                "use_cls": self.use_cls,
                "rec_img_shape": self.rec_img_shape,
                "intra_op_num_threads": intra_threads,
                "inter_op_num_threads": inter_threads,
            },
        )

        pages: list[ExtractedPage] = []
        doc_script_chars: dict[str, int] = {}

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
                logger.error(
                    f"PP-OCRv5 extraction failed on page {rendered_page.page_number}: {exc}"
                )
                extracted_page = ExtractedPage(
                    page_number=rendered_page.page_number,
                    geometry=rendered_page.geometry,
                    raw_text="",
                    normalized_text="",
                    has_vector_text=False,
                    extraction_status="FAILED",
                    error_message=str(exc),
                    engine_name="rapidocr-ppocrv5-devanagari",
                    routing_decision=PageRoutingDecision.OPTICAL_OCR,
                    routing_reason=f"Optical OCR execution failed: {exc}",
                )
            pages.append(extracted_page)

            # Accumulate document-level script counts
            for s_name, ratio in extracted_page.script_distribution.items():
                p_chars = int(round(ratio * len(extracted_page.raw_text.strip())))
                doc_script_chars[s_name] = doc_script_chars.get(s_name, 0) + p_chars

        total_tokens = sum(len(p.tokens) for p in pages)
        full_raw_text = "\n\n".join(p.raw_text for p in pages if p.raw_text)
        full_norm_text = "\n\n".join(p.normalized_text for p in pages if p.normalized_text)

        total_doc_chars = sum(doc_script_chars.values())
        script_summary: dict[str, float] = {}
        if total_doc_chars > 0:
            for s_k, c_v in doc_script_chars.items():
                script_summary[s_k] = round(c_v / total_doc_chars, 4)

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

    def analyze(self, input_data: AnalyzerInput) -> AnalyzerOutput:
        """Execute PP-OCRv5 Devanagari analysis on a document."""
        t0 = time.perf_counter()
        capabilities_executed: list[AnalyzerCapabilityResult] = []
        observations: list[AnalyzerObservation] = []
        errors: list[str] = []
        artifact_key: str | None = None
        artifact_sha256: str | None = None

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

            # Persist artifact
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
                except Exception as exc:
                    logger.warning(f"Failed storing OCR JSON artifact: {exc}")

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

            capabilities_executed.append(
                AnalyzerCapabilityResult(
                    capability_id="multilingual-devanagari-ocr",
                    status=cap_status,
                    summary=(
                        f"Extracted {extracted_doc.total_tokens} tokens across {extracted_doc.total_pages} page(s) "
                        f"using PP-OCRv5 Devanagari Mobile (Hindi CER recovery enabled, use_cls=False)."
                    ),
                    details={
                        "total_pages": extracted_doc.total_pages,
                        "failed_pages": len(failed_pages),
                        "total_tokens": extracted_doc.total_tokens,
                        "script_summary": extracted_doc.script_summary,
                    },
                )
            )

            # Summary observation
            doc_obs = AnalyzerObservation(
                observation_type="ocr_text",
                title=f"PP-OCRv5 Devanagari OCR: {extracted_doc.total_tokens} Tokens Across {extracted_doc.total_pages} Page(s)",
                description=(
                    f"Multilingual document extraction complete using {self.display_name} v{self.version}. "
                    f"Primary scripts: {extracted_doc.script_summary}."
                ),
                severity="warning" if failed_pages else "info",
                categorical_confidence="high" if extracted_doc.total_tokens > 0 else "unknown",
                confidence=None,
                capability_id="multilingual-devanagari-ocr",
                evidence_payload={
                    "total_pages": extracted_doc.total_pages,
                    "failed_pages": len(failed_pages),
                    "total_tokens": extracted_doc.total_tokens,
                    "script_summary": extracted_doc.script_summary,
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
                    title=f"Page {page.page_number} Devanagari OCR ({len(page.tokens)} tokens)",
                    description=(
                        f"Page {page.page_number} multilingual recognition yielded {len(page.lines)} lines, "
                        f"{len(page.tokens)} tokens, and {len(page.tables)} table(s)."
                    ),
                    severity="info",
                    categorical_confidence="high" if page.tokens else "low",
                    confidence=None,
                    page_number=page.page_number,
                    capability_id="multilingual-devanagari",
                    evidence_payload={
                        "page_number": page.page_number,
                        "token_count": len(page.tokens),
                        "line_count": len(page.lines),
                        "table_count": len(page.tables),
                        "has_vector_text": page.has_vector_text,
                        "extraction_status": page.extraction_status,
                        "engine_name": page.engine_name,
                        "routing_decision": str(page.routing_decision),
                        "routing_reason": page.routing_reason,
                        "script_distribution": page.script_distribution,
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

        except Exception as exc:
            logger.exception("PP-OCRv5 Devanagari OCR pipeline execution failed")
            errors.append(str(exc))
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
            limitations=[
                "Recognizes Devanagari, Latin, digits, and currency symbols simultaneously.",
                "Angle classifier is disabled (use_cls=False) to prevent headline-inversion on Devanagari text.",
                "Confidence values are raw, uncalibrated model scores.",
                "Non-destructive preservation stores alternative layers under alternative_extractions.",
            ],
            errors=errors,
        )
