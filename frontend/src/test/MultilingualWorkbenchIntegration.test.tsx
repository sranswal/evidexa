import { render, screen, fireEvent } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { OcrInspector } from '../components/viewer/OcrInspector';
import { StructuredExtractionInspector } from '../components/viewer/StructuredExtractionInspector';
import type {
  ExtractedDocumentText,
  DocumentExtractionResult,
} from '../types/api';

describe('Multilingual Workbench Integration (Phase 4D.3.6)', () => {
  // Mock multilingual document data
  const mockMultilingualOcr: ExtractedDocumentText = {
    schema_version: '2.0.0',
    document_id: 'doc-multi-001',
    processing_run_id: 'run-multi-001',
    total_pages: 2,
    total_tokens: 6,
    full_raw_text: 'भारतीय स्टेट बैंक खाता विवरण\nInvoice संख्या १२५०००\nGSTIN: 27AABCU9603R1ZM',
    full_normalized_text: 'भारतीय स्टेट बैंक खाता विवरण\nInvoice संख्या 125000\nGSTIN: 27AABCU9603R1ZM',
    script_summary: { DEVANAGARI: 0.6, LATIN: 0.4 },
    pages: [
      {
        page_number: 1,
        raw_text: 'भारतीय स्टेट बैंक खाता विवरण',
        normalized_text: 'भारतीय स्टेट बैंक खाता विवरण',
        extraction_status: 'SUCCEEDED',
        engine_name: 'ppocrv5-devanagari-engine',
        routing_decision: 'HYBRID_FUSION',
        routing_reason: 'Composite page with vector text and high raster ratio (55%)',
        has_vector_text: false,
        raster_area_ratio: 0.55,
        vector_char_count: 28,
        script_distribution: { DEVANAGARI: 0.8, LATIN: 0.2 },
        lines: [
          {
            id: 'line-hi-1',
            raw_text: 'भारतीय स्टेट बैंक खाता विवरण',
            normalized_text: 'भारतीय स्टेट बैंक खाता विवरण',
            dominant_script: 'DEVANAGARI',
            confidence: 0.96,
            tokens: [
              {
                id: 'tok-hi-1',
                raw_text: 'भारतीय',
                normalized_text: 'भारतीय',
                detected_script: 'DEVANAGARI',
                confidence: 0.97,
                reading_order_index: 1,
                bounding_box: { x: 0.1, y: 0.1, width: 0.15, height: 0.04 },
              },
              {
                id: 'tok-hi-2',
                raw_text: 'स्टेट',
                normalized_text: 'स्टेट',
                detected_script: 'DEVANAGARI',
                confidence: 0.96,
                reading_order_index: 2,
                bounding_box: { x: 0.26, y: 0.1, width: 0.12, height: 0.04 },
              },
              {
                id: 'tok-hi-3',
                raw_text: '१२५०००',
                normalized_text: '125000',
                detected_script: 'NUMERIC',
                is_numeral_converted: true,
                original_numeral_system: 'DEVANAGARI',
                original_raw_value: '१२५०००',
                confidence: 0.95,
                reading_order_index: 3,
                bounding_box: { x: 0.39, y: 0.1, width: 0.15, height: 0.04 },
              },
            ],
          },
        ],
        tokens: [
          {
            id: 'tok-hi-1',
            raw_text: 'भारतीय',
            normalized_text: 'भारतीय',
            detected_script: 'DEVANAGARI',
            confidence: 0.97,
            reading_order_index: 1,
            bounding_box: { x: 0.1, y: 0.1, width: 0.15, height: 0.04 },
          },
          {
            id: 'tok-hi-2',
            raw_text: 'स्टेट',
            normalized_text: 'स्टेट',
            detected_script: 'DEVANAGARI',
            confidence: 0.96,
            reading_order_index: 2,
            bounding_box: { x: 0.26, y: 0.1, width: 0.12, height: 0.04 },
          },
          {
            id: 'tok-hi-3',
            raw_text: '१२५०००',
            normalized_text: '125000',
            detected_script: 'NUMERIC',
            is_numeral_converted: true,
            original_numeral_system: 'DEVANAGARI',
            original_raw_value: '१२५०००',
            confidence: 0.95,
            reading_order_index: 3,
            bounding_box: { x: 0.39, y: 0.1, width: 0.15, height: 0.04 },
          },
        ],
        alternative_extractions: {
          pdfium: {
            engine_name: 'pypdfium2',
            raw_text: 'State Bank of India Account Statement',
            normalized_text: 'State Bank of India Account Statement',
            token_count: 6,
            line_count: 1,
            confidence: null,
            tokens: [
              {
                id: 'vec-tok-1',
                raw_text: 'State',
                normalized_text: 'State',
                detected_script: 'LATIN',
                confidence: null,
                reading_order_index: 1,
                bounding_box: { x: 0.1, y: 0.1, width: 0.12, height: 0.04 },
              },
              {
                id: 'vec-tok-2',
                raw_text: 'Bank',
                normalized_text: 'Bank',
                detected_script: 'LATIN',
                confidence: null,
                reading_order_index: 2,
                bounding_box: { x: 0.23, y: 0.1, width: 0.1, height: 0.04 },
              },
            ],
            metadata: {
              potential_duplicate_tokens: [
                {
                  text: 'State Bank',
                  ocr_token_id: 'tok-hi-1',
                  pdfium_token_id: 'vec-tok-1',
                  spatial_iou: 0.85,
                },
              ],
            },
          },
        },
        disagreements: [
          {
            primary_engine: 'ppocrv5-devanagari-engine',
            alternative_key: 'pdfium',
            alternative_engine: 'pypdfium2',
            primary_char_count: 28,
            alternative_char_count: 37,
            char_count_delta: 9,
            primary_token_count: 3,
            alternative_token_count: 6,
            token_count_delta: 3,
            has_disagreement: true,
            disagreement_reasons: ['Optical engine extracted Devanagari while vector layer contains Latin text.'],
          },
        ],
      },
      {
        page_number: 2,
        raw_text: 'Corrupted\ufffdVoucher Invoice संख्या 99',
        normalized_text: 'Corrupted\ufffdVoucher Invoice संख्या 99',
        extraction_status: 'SUCCEEDED',
        engine_name: 'rapidocr-optical-engine',
        routing_decision: 'OCR_ONLY',
        has_vector_text: false,
        tokens: [
          {
            id: 'tok-mixed-1',
            raw_text: 'Invoice संख्या',
            normalized_text: 'Invoice संख्या',
            detected_script: 'MIXED',
            confidence: 0.94,
            reading_order_index: 1,
            bounding_box: { x: 0.1, y: 0.2, width: 0.25, height: 0.04 },
          },
          {
            id: 'tok-uncert-1',
            raw_text: 'Corrupted\ufffdVoucher',
            normalized_text: 'Corrupted\ufffdVoucher',
            detected_script: 'UNKNOWN',
            is_uncertain: true,
            uncertainty_reason: 'Ambiguous Unicode replacement character (U+FFFD) detected in raw text.',
            confidence: 0.5,
            reading_order_index: 2,
            bounding_box: { x: 0.1, y: 0.3, width: 0.3, height: 0.04 },
          },
        ],
      },
    ],
  };

  // Mock extraction result
  const mockExtractionData: DocumentExtractionResult = {
    document_id: 'doc-multi-001',
    processing_run_id: 'run-multi-001',
    document_class: 'INVOICE',
    schema_id: 'invoice_bilingual_v1',
    schema_version: '1.0.0',
    execution_duration_ms: 120,
    created_at: '2026-11-10T12:00:00Z',
    validation_summary: { valid: true },
    fields: {
      total_amount: {
        id: 'fld-1',
        field_key: 'total_amount',
        label: 'Total Amount',
        normalized_value: '125000.00',
        raw_text: '₹१२५०००.००',
        data_type: 'DECIMAL',
        extraction_method: 'deterministic_pattern_v1',
        score: 0.92,
        confidence: null,
        confidence_explanation: 'Deterministic pattern extraction has no calibrated probabilistic confidence.',
        source_document_id: 'doc-multi-001',
        source_page_number: 1,
        source_bounding_boxes: [{ x: 0.39, y: 0.1, width: 0.15, height: 0.04 }],
        source_token_ids: ['tok-hi-3'],
        validation_status: 'VALID',
        warnings: [],
      },
      account_number_masked: {
        id: 'fld-2',
        field_key: 'account_number_masked',
        label: 'Bank Account Number',
        normalized_value: '123456789012',
        raw_text: '123456789012',
        data_type: 'MASKED_STRING',
        extraction_method: 'deterministic_pattern_v1',
        score: 0.95,
        confidence: null,
        source_document_id: 'doc-multi-001',
        source_page_number: 1,
        source_bounding_boxes: [{ x: 0.1, y: 0.5, width: 0.2, height: 0.04 }],
        validation_status: 'VALID',
        warnings: [],
      },
    },
  };

  // 1. Hindi rendering
  it('Scenario 1: renders Hindi Devanagari text with correct Unicode characters and script tags', () => {
    render(<OcrInspector ocrData={mockMultilingualOcr} currentPage={1} onSelectToken={vi.fn()} />);

    expect(screen.getByText('भारतीय स्टेट बैंक खाता विवरण')).toBeInTheDocument();
    // Switch to tokens view
    fireEvent.click(screen.getByTitle('Token-Level Inspector'));
    expect(screen.getByText('भारतीय')).toBeInTheDocument();
    expect(screen.getByText('स्टेट')).toBeInTheDocument();
    expect(screen.getAllByText('DEVANAGARI').length).toBeGreaterThan(0);
  });

  // 2. English regression
  it('Scenario 2: preserves standard English text extraction and controls without regression', () => {
    const handleSelectToken = vi.fn();
    render(<OcrInspector ocrData={mockMultilingualOcr} currentPage={1} onSelectToken={handleSelectToken} />);

    expect(screen.getByTitle('Reading-Order Line View')).toBeInTheDocument();
    expect(screen.getByTitle('Token-Level Inspector')).toBeInTheDocument();
    expect(screen.getByTitle('Continuous Raw Text')).toBeInTheDocument();
    expect(screen.getByText(/Total Tokens:/i)).toBeInTheDocument();
  });

  // 3. Mixed-script rendering
  it('Scenario 3: renders mixed Hindi-English script tokens with MIXED badge', () => {
    render(<OcrInspector ocrData={mockMultilingualOcr} currentPage={2} onSelectToken={vi.fn()} />);

    // Switch to tokens view
    fireEvent.click(screen.getByTitle('Token-Level Inspector'));
    expect(screen.getByText('Invoice संख्या')).toBeInTheDocument();
    expect(screen.getByText('MIXED')).toBeInTheDocument();
  });

  // 4. Original versus normalized text
  it('Scenario 4: toggles between normalized text (125000) and original observed raw text (१२५०००)', () => {
    render(<OcrInspector ocrData={mockMultilingualOcr} currentPage={1} onSelectToken={vi.fn()} />);

    // In tokens view
    fireEvent.click(screen.getByTitle('Token-Level Inspector'));

    // Default normalized view shows converted numeral 125000
    expect(screen.getByText('125000')).toBeInTheDocument();

    // Toggle to raw view
    const toggleButton = screen.getByTitle(/toggle between unicode nfc/i);
    fireEvent.click(toggleButton);

    // After toggle, original Devanagari raw numeral is displayed
    expect(screen.getByText('१२५०००')).toBeInTheDocument();
  });

  // 5. Extraction-layer comparison
  it('Scenario 5: compares Primary Optical OCR layer and Alternative Vector PDFium layer', () => {
    render(<OcrInspector ocrData={mockMultilingualOcr} currentPage={1} onSelectToken={vi.fn()} />);

    // Shows layer switcher for hybrid document
    expect(screen.getByText(/Extraction Layer:/i)).toBeInTheDocument();
    const primaryBtn = screen.getByText(/Primary/i);
    const vectorBtn = screen.getByText(/Alternative Vector/i);
    expect(primaryBtn).toBeInTheDocument();
    expect(vectorBtn).toBeInTheDocument();

    // Click to switch to Alternative Vector layer
    fireEvent.click(vectorBtn);
    expect(screen.getByText('State Bank of India Account Statement')).toBeInTheDocument();
  });

  // 6. Routing indicators
  it('Scenario 6: renders page routing badges (HYBRID_FUSION and OCR_ONLY)', () => {
    const { rerender } = render(
      <OcrInspector ocrData={mockMultilingualOcr} currentPage={1} onSelectToken={vi.fn()} />
    );
    expect(screen.getByText('HYBRID_FUSION')).toBeInTheDocument();

    rerender(<OcrInspector ocrData={mockMultilingualOcr} currentPage={2} onSelectToken={vi.fn()} />);
    expect(screen.getByText('OCR_ONLY')).toBeInTheDocument();
  });

  // 7. Disagreement warnings
  it('Scenario 7: renders extraction layer disagreement alert with delta counts and reasons', () => {
    render(<OcrInspector ocrData={mockMultilingualOcr} currentPage={1} onSelectToken={vi.fn()} />);

    expect(screen.getByText(/Extraction Layer Disagreement Detected/i)).toBeInTheDocument();
    expect(screen.getByText(/Δ chars: 9, Δ tokens: 3/i)).toBeInTheDocument();
    expect(
      screen.getByText(/Optical engine extracted Devanagari while vector layer contains Latin text/i)
    ).toBeInTheDocument();
  });

  // 8. Field provenance navigation
  it('Scenario 8: structured field inspector displays normalized vs original values and provides navigation', () => {
    const handleNavigate = vi.fn();
    const handleHighlight = vi.fn();

    render(
      <StructuredExtractionInspector
        extractionData={mockExtractionData}
        currentPage={1}
        onNavigateToPage={handleNavigate}
        onHighlightBox={handleHighlight}
      />
    );

    // Displays Total Amount
    expect(screen.getByText('Total Amount')).toBeInTheDocument();
    // Normalized value 125000.00
    expect(screen.getByText('125000.00')).toBeInTheDocument();
    // Original observed value ₹१२५०००.००
    expect(screen.getByText('₹१२५०००.००')).toBeInTheDocument();

    // Click Locate button
    const locateBtns = screen.getAllByText('Locate');
    fireEvent.click(locateBtns[0]);

    expect(handleHighlight).toHaveBeenCalledWith(
      expect.objectContaining({ x: 0.39, y: 0.1, width: 0.15, height: 0.04 })
    );
  });

  // 9. PII masking
  it('Scenario 9: masks sensitive identifiers (account_number_masked) by default and allows toggle', () => {
    render(
      <StructuredExtractionInspector
        extractionData={mockExtractionData}
        currentPage={1}
        onNavigateToPage={vi.fn()}
        onHighlightBox={vi.fn()}
      />
    );

    expect(screen.getByText('Bank Account Number')).toBeInTheDocument();
    // Masked representation contains trailing digits
    expect(screen.getByText(/9012/)).toBeInTheDocument();

    // Toggle mask button
    const revealBtn = screen.getByTitle('Reveal identifier');
    fireEvent.click(revealBtn);
    expect(screen.getByTitle('Mask identifier')).toBeInTheDocument();
    expect(screen.getByText('123456789012')).toBeInTheDocument();
  });

  // 10. Unsupported-script handling
  it('Scenario 10: flags uncertain or corrupted tokens (U+FFFD) with uncertainty warning badge', () => {
    render(<OcrInspector ocrData={mockMultilingualOcr} currentPage={2} onSelectToken={vi.fn()} />);

    // Switch to tokens view
    fireEvent.click(screen.getByTitle('Token-Level Inspector'));

    expect(screen.getByText('UNKNOWN')).toBeInTheDocument();
    expect(screen.getByText('Uncertain')).toBeInTheDocument();
    expect(screen.getByText(/Corrupted/i)).toBeInTheDocument();
  });
});

