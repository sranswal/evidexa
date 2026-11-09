"""Rule-based document classifier implementing provider-neutral classification protocol."""

from __future__ import annotations

import logging
import time
from typing import Protocol

from document_intelligence.domain.enums import DocumentClass
from document_intelligence.domain.models.classification import (
    ClassificationCandidate,
    DocumentClassificationResult,
    PageClassification,
)
from document_intelligence.domain.models.ocr import ExtractedDocumentText, ExtractedPage
from document_intelligence.modules.understanding.classification.rules import (
    COMPILED_PATTERNS,
)

logger = logging.getLogger(__name__)

SCORE_THRESHOLD: float = 0.25
MAX_SCORE_NORMALIZER: float = 10.0


class DocumentClassifierProtocol(Protocol):
    """Protocol defining document classification contract."""

    def classify_document(
        self,
        extracted_doc: ExtractedDocumentText,
        options: dict[str, str] | None = None,
    ) -> DocumentClassificationResult:
        """Classify a multi-page document into candidate classes with page-level breakdown."""
        ...


class RuleBasedDocumentClassifier:
    """Deterministic rule-based document classifier using lexical, pattern, and layout cues."""

    def __init__(self, score_threshold: float = SCORE_THRESHOLD) -> None:
        self.score_threshold = score_threshold
        self.classifier_version = "1.0.0"
        self.classification_method = "rule_pattern_classifier_v1"

    def classify_document(
        self,
        extracted_doc: ExtractedDocumentText,
        options: dict[str, str] | None = None,
    ) -> DocumentClassificationResult:
        """Classify document and all constituent pages based on extracted text and layout."""
        t0 = time.perf_counter()

        page_classifications: list[PageClassification] = []
        doc_class_scores: dict[DocumentClass, float] = dict.fromkeys(COMPILED_PATTERNS, 0.0)
        doc_class_signals: dict[DocumentClass, set[str]] = {cls: set() for cls in COMPILED_PATTERNS}

        total_pages = max(1, len(extracted_doc.pages))

        for page in extracted_doc.pages:
            page_class = self.classify_page(page)
            page_classifications.append(page_class)

            # Accumulate into document-level scores
            for cand in page_class.candidates:
                doc_class_scores[cand.document_class] += cand.ranking_score
                for sig in cand.matched_signals:
                    doc_class_signals[cand.document_class].add(sig)

        # Average candidate scores across pages
        avg_candidates: list[ClassificationCandidate] = []
        for doc_cls, total_score in doc_class_scores.items():
            avg_score = round(min(1.0, total_score / float(total_pages)), 4)
            signals = sorted(doc_class_signals[doc_cls])
            avg_candidates.append(
                ClassificationCandidate(
                    document_class=doc_cls,
                    ranking_score=avg_score,
                    matched_signals=signals,
                )
            )

        avg_candidates.sort(key=lambda c: c.ranking_score, reverse=True)

        # Determine document-level prediction
        if not avg_candidates or avg_candidates[0].ranking_score < self.score_threshold:
            predicted_class = DocumentClass.UNKNOWN
            top_score = avg_candidates[0].ranking_score if avg_candidates else 0.0
        else:
            predicted_class = avg_candidates[0].document_class
            top_score = avg_candidates[0].ranking_score

        elapsed_ms = (time.perf_counter() - t0) * 1000.0

        return DocumentClassificationResult(
            document_id=extracted_doc.document_id,
            processing_run_id=extracted_doc.processing_run_id,
            predicted_class=predicted_class,
            effective_class=predicted_class,
            ranking_score=top_score,
            score_type="rule_ranking_score",
            classification_method=self.classification_method,
            classifier_version=self.classifier_version,
            candidates=avg_candidates,
            page_classifications=page_classifications,
            execution_duration_ms=round(elapsed_ms, 2),
        )

    def classify_page(self, page: ExtractedPage) -> PageClassification:
        """Score an individual page against all document classes."""
        text = f"{page.raw_text} {page.normalized_text}".strip()
        words = text.split()

        # If text is virtually empty, return UNKNOWN
        if len(words) < 3:
            return PageClassification(
                page_number=page.page_number,
                predicted_class=DocumentClass.UNKNOWN,
                ranking_score=0.0,
                candidates=[],
                matched_signals=["insufficient_page_text"],
            )

        candidates: list[ClassificationCandidate] = []

        for doc_cls, compiled_list in COMPILED_PATTERNS.items():
            raw_score = 0.0
            matched_sigs: list[str] = []

            for regex, weight, pat_str in compiled_list:
                matches = regex.findall(text)
                if matches:
                    # Bounded count multiplier to prevent keyword stuffing
                    count_mult = min(len(matches), 3)
                    raw_score += weight * count_mult
                    matched_sigs.append(f"{pat_str} (x{count_mult})")

            # Layout bonuses
            if doc_cls == DocumentClass.INVOICE and page.tables:
                raw_score += 1.5
                matched_sigs.append("layout:tabular_itemization")

            if doc_cls == DocumentClass.BANK_STATEMENT and page.tables:
                raw_score += 1.5
                matched_sigs.append("layout:account_transaction_table")

            # Check for receipt distinguishing features:
            # Receipts typically have no "Bill To" or multi-party address
            if doc_cls == DocumentClass.RECEIPT:
                if any("receipt" in s.lower() for s in matched_sigs):
                    if not any("bill to" in text.lower() or "sold to" in text.lower() for _ in [1]):
                        raw_score += 1.0
                        matched_sigs.append("layout:single_party_slip")

            ranking_score = round(min(1.0, raw_score / MAX_SCORE_NORMALIZER), 4)

            candidates.append(
                ClassificationCandidate(
                    document_class=doc_cls,
                    ranking_score=ranking_score,
                    matched_signals=matched_sigs,
                )
            )

        candidates.sort(key=lambda c: c.ranking_score, reverse=True)

        if not candidates or candidates[0].ranking_score < self.score_threshold:
            pred_class = DocumentClass.UNKNOWN
            pred_score = candidates[0].ranking_score if candidates else 0.0
            signals = ["no_candidate_crossed_threshold"]
        else:
            pred_class = candidates[0].document_class
            pred_score = candidates[0].ranking_score
            signals = candidates[0].matched_signals

        return PageClassification(
            page_number=page.page_number,
            predicted_class=pred_class,
            ranking_score=pred_score,
            candidates=candidates,
            matched_signals=signals,
        )
