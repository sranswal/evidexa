"""Unit tests for rule-based document classification engine."""

from __future__ import annotations

from document_intelligence.domain.enums import CoordinateSystem, DocumentClass
from document_intelligence.domain.models.bounding_box import BoundingBox, PageGeometry
from document_intelligence.domain.models.ocr import (
    ExtractedDocumentText,
    ExtractedPage,
    OcrEngineMetadata,
    TextBlock,
    TextLine,
    TextToken,
)
from document_intelligence.modules.understanding.classification.classifier import (
    RuleBasedDocumentClassifier,
)


def _make_mock_ocr_doc(
    text_content: str,
    doc_id: str = "doc-test-1",
    page_num: int = 1,
) -> ExtractedDocumentText:
    """Helper to generate an ExtractedDocumentText fixture with tokens and lines."""
    lines: list[TextLine] = []
    all_tokens: list[TextToken] = []

    raw_lines = text_content.strip().split("\n")
    for l_idx, line_str in enumerate(raw_lines):
        line_clean = line_str.strip()
        if not line_clean:
            continue
        words = line_clean.split()
        tokens: list[TextToken] = []
        for w_idx, word in enumerate(words):
            col = w_idx % 10
            tok = TextToken(
                id=f"p{page_num}_l{l_idx}_t{w_idx}",
                raw_text=word,
                reading_order_index=len(all_tokens),
                page_number=page_num,
                bounding_box=BoundingBox(
                    x=round(0.05 + col * 0.08, 3),
                    y=round(0.05 + min(0.85, l_idx * 0.03), 3),
                    width=0.07,
                    height=0.02,
                    coordinate_system=CoordinateSystem.NORMALIZED_0_1,
                ),
            )
            tokens.append(tok)
            all_tokens.append(tok)

        lines.append(
            TextLine(
                id=f"p{page_num}_l{l_idx}",
                raw_text=line_clean,
                reading_order_index=l_idx,
                page_number=page_num,
                tokens=tokens,
                bounding_box=BoundingBox(
                    x=0.05,
                    y=round(0.05 + min(0.85, l_idx * 0.03), 3),
                    width=0.85,
                    height=0.02,
                    coordinate_system=CoordinateSystem.NORMALIZED_0_1,
                ),
            )
        )

    page = ExtractedPage(
        page_number=page_num,
        geometry=PageGeometry(width=612.0, height=792.0),
        raw_text=text_content,
        normalized_text=text_content,
        lines=lines,
        blocks=[
            TextBlock(
                id=f"p{page_num}_b0",
                raw_text=text_content,
                reading_order_index=0,
                lines=lines,
            )
        ],
        tokens=all_tokens,
    )

    return ExtractedDocumentText(
        document_id=doc_id,
        processing_run_id="run-mock-1",
        engine_metadata=OcrEngineMetadata(
            engine_name="mock-ocr",
            engine_version="1.0.0",
        ),
        pages=[page],
        total_pages=1,
        total_tokens=len(all_tokens),
        full_raw_text=text_content,
        full_normalized_text=text_content,
    )


class TestRuleBasedDocumentClassifier:
    """Validation suite for deterministic document classification."""

    def setup_method(self) -> None:
        self.classifier = RuleBasedDocumentClassifier()

    def test_classify_invoice_document(self) -> None:
        text = """
        ACME CORPORATION
        COMMERCIAL INVOICE
        Invoice Number: INV-2024-8841
        Invoice Date: 2024-03-15
        Due Date: 2024-04-15
        Bill To: Global Tech Enterprises
        Purchase Order: PO-99124
        Terms: Net 30
        Description: Enterprise Cloud Consulting Services
        Subtotal: $4,500.00
        Tax (8%): $360.00
        Total Due: $4,860.00
        Please remit payment to ACME Corp Wire.
        """
        doc = _make_mock_ocr_doc(text)
        result = self.classifier.classify_document(doc)

        assert result.predicted_class == DocumentClass.INVOICE
        assert result.effective_class == DocumentClass.INVOICE
        assert result.ranking_score > 0.5
        assert result.score_type == "rule_ranking_score"
        assert len(result.candidates) > 0
        assert result.candidates[0].document_class == DocumentClass.INVOICE
        assert any("invoice" in sig.lower() for sig in result.candidates[0].matched_signals)
        assert len(result.page_classifications) == 1
        assert result.page_classifications[0].predicted_class == DocumentClass.INVOICE

    def test_classify_receipt_document(self) -> None:
        text = """
        TARGET STORES #1402
        SALES RECEIPT
        Register: 04  Cashier: Sarah M.
        Date: 10/12/2024 14:22:10
        Receipt #: REC-774109
        Organic Milk           $4.99
        Whole Wheat Bread      $3.49
        Apples 2lb             $5.20
        SUBTOTAL:             $13.68
        TAX 7%:                $0.96
        TOTAL:                $14.64
        VISA CARD TENDERED:   $14.64
        CHANGE DUE:            $0.00
        THANK YOU FOR SHOPPING!
        """
        doc = _make_mock_ocr_doc(text)
        result = self.classifier.classify_document(doc)

        assert result.predicted_class == DocumentClass.RECEIPT
        assert result.effective_class == DocumentClass.RECEIPT
        assert result.ranking_score > 0.5
        assert result.candidates[0].document_class == DocumentClass.RECEIPT
        assert any(
            "receipt_header" in sig or "cashier" in sig or "tender" in sig
            for sig in result.candidates[0].matched_signals
        )

    def test_classify_bank_statement_document(self) -> None:
        text = """
        JPMORGAN CHASE BANK, N.A.
        MONTHLY ACCOUNT STATEMENT
        Statement Period: October 1, 2024 through October 31, 2024
        Account Number: *******4921
        Primary Checking Account
        Beginning Balance: $12,450.80
        Deposits and Additions: $6,200.00
        Electronic Withdrawals: $3,140.50
        Ending Balance: $15,510.30
        Available Balance: $15,510.30
        FDIC Insured.
        """
        doc = _make_mock_ocr_doc(text)
        result = self.classifier.classify_document(doc)

        assert result.predicted_class == DocumentClass.BANK_STATEMENT
        assert result.effective_class == DocumentClass.BANK_STATEMENT
        assert result.ranking_score > 0.5
        assert result.candidates[0].document_class == DocumentClass.BANK_STATEMENT

    def test_classify_identity_document(self) -> None:
        text = """
        UNITED STATES OF AMERICA
        PASSPORT / PASSEPORT
        Type: P  Code: USA  Passport No: 981240182
        Surname: DOE
        Given Names: JOHN ALEXANDER
        Nationality: UNITED STATES OF AMERICA
        Date of Birth: 14 JAN 1985
        Sex: M  Place of Birth: CALIFORNIA, U.S.A.
        Date of Issue: 22 AUG 2020
        Date of Expiration: 21 AUG 2030
        Authority: United States Department of State
        """
        doc = _make_mock_ocr_doc(text)
        result = self.classifier.classify_document(doc)

        assert result.predicted_class == DocumentClass.IDENTITY_DOCUMENT
        assert result.effective_class == DocumentClass.IDENTITY_DOCUMENT
        assert result.ranking_score > 0.4
        assert result.candidates[0].document_class == DocumentClass.IDENTITY_DOCUMENT

    def test_classify_tax_document(self) -> None:
        text = """
        Department of the Treasury - Internal Revenue Service
        Form 1040 U.S. Individual Income Tax Return 2024
        OMB No. 1545-0074
        Filing Status: Single
        W-2 Wage and Tax Statement attached
        Line 1: Wages, salaries, tips: $85,000.00
        Line 9: Total Income: $85,000.00
        Line 11: Adjusted Gross Income: $85,000.00
        Line 24: Total Tax: $12,400.00
        Federal Income Tax Withheld: $14,000.00
        Refund Amount: $1,600.00
        """
        doc = _make_mock_ocr_doc(text)
        result = self.classifier.classify_document(doc)

        assert result.predicted_class == DocumentClass.TAX_DOCUMENT
        assert result.effective_class == DocumentClass.TAX_DOCUMENT
        assert result.ranking_score > 0.4
        assert result.candidates[0].document_class == DocumentClass.TAX_DOCUMENT

    def test_classify_contract_document(self) -> None:
        text = """
        MASTER SERVICES AGREEMENT
        This Agreement is entered into as of January 15, 2024 by and between
        Party of the First Part (Alpha Corp) and Party of the Second Part (Beta LLC).
        WHEREAS, Provider desires to perform services and Client desires to retain Provider.
        NOW, THEREFORE, the parties agree as follows:
        1. Scope of Work
        2. Indemnification and Limitation of Liability
        3. Governing Law and Dispute Resolution
        IN WITNESS WHEREOF, the duly authorized representatives have executed this Agreement.
        """
        doc = _make_mock_ocr_doc(text)
        result = self.classifier.classify_document(doc)

        assert result.predicted_class == DocumentClass.CONTRACT
        assert result.effective_class == DocumentClass.CONTRACT
        assert result.ranking_score > 0.4
        assert result.candidates[0].document_class == DocumentClass.CONTRACT

    def test_classify_sparse_or_ambiguous_text_yields_unknown(self) -> None:
        text = """
        Hello world!
        This is a random snippet of miscellaneous notes.
        Meeting at 3 PM with team to discuss general updates.
        Nothing formal here.
        """
        doc = _make_mock_ocr_doc(text)
        result = self.classifier.classify_document(doc)

        assert result.predicted_class == DocumentClass.UNKNOWN
        assert result.effective_class == DocumentClass.UNKNOWN
        # All ranking scores should be under the threshold
        assert all(c.ranking_score < self.classifier.score_threshold for c in result.candidates)

    def test_deterministic_scoring(self) -> None:
        text = "COMMERCIAL INVOICE\nInvoice # 12345\nTotal: $500\nDue: 2024-05-01"
        doc = _make_mock_ocr_doc(text)
        res1 = self.classifier.classify_document(doc)
        res2 = self.classifier.classify_document(doc)

        assert res1.predicted_class == res2.predicted_class
        assert res1.ranking_score == res2.ranking_score
        assert [c.document_class for c in res1.candidates] == [
            c.document_class for c in res2.candidates
        ]
        assert [c.ranking_score for c in res1.candidates] == [
            c.ranking_score for c in res2.candidates
        ]

    def test_candidates_sorted_descending(self) -> None:
        text = "INVOICE # 9912\nReceipt of payment\nAccount statement reference"
        doc = _make_mock_ocr_doc(text)
        result = self.classifier.classify_document(doc)

        scores = [c.ranking_score for c in result.candidates]
        assert scores == sorted(scores, reverse=True)

    def test_multi_page_document_aggregation(self) -> None:
        doc1 = _make_mock_ocr_doc(
            "COMMERCIAL INVOICE\nInvoice No: INV-100\nTotal Due: $200.00", page_num=1
        )
        doc2 = _make_mock_ocr_doc(
            "COMMERCIAL INVOICE\nPage 2 of 2\nPayment Instructions\nTotal Due: $200.00", page_num=2
        )

        multi_page_doc = ExtractedDocumentText(
            document_id="multi-page-doc",
            processing_run_id="run-multi-1",
            engine_metadata=OcrEngineMetadata(engine_name="mock-ocr", engine_version="1.0.0"),
            pages=[doc1.pages[0], doc2.pages[0]],
            full_raw_text=doc1.full_raw_text + "\n" + doc2.full_raw_text,
            full_normalized_text=doc1.full_normalized_text + "\n" + doc2.full_normalized_text,
            total_pages=2,
            total_tokens=doc1.total_tokens + doc2.total_tokens,
        )

        result = self.classifier.classify_document(multi_page_doc)
        assert len(result.page_classifications) == 2
        assert result.page_classifications[0].page_number == 1
        assert result.page_classifications[1].page_number == 2
        assert result.predicted_class == DocumentClass.INVOICE
