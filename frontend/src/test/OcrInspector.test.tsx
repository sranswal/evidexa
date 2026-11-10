import { render, screen, fireEvent } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { OcrInspector } from '../components/viewer/OcrInspector';
import type { ExtractedDocumentText } from '../types/api';

const mockOcrData: ExtractedDocumentText = {
  document_id: 'doc-123',
  processing_run_id: 'run-456',
  total_pages: 2,
  total_tokens: 3,
  full_raw_text: 'ACME Corp Invoice\nTotal: $1,250.00\nPayment Due: 2026-12-01',
  pages: [
    {
      page_number: 1,
      raw_text: 'ACME Corp Invoice\nTotal: $1,250.00',
      extraction_status: 'SUCCEEDED',
      engine_name: 'hybrid-ocr-pipeline',
      has_vector_text: true,
      lines: [
        {
          id: 'line-1',
          raw_text: 'ACME Corp Invoice',
          confidence: 0.99,
          tokens: [
            {
              id: 'tok-1',
              raw_text: 'ACME',
              confidence: 0.99,
              reading_order_index: 1,
              bounding_box: { x: 0.1, y: 0.1, width: 0.2, height: 0.05 },
            },
            {
              id: 'tok-2',
              raw_text: 'Corp',
              confidence: 0.98,
              reading_order_index: 2,
              bounding_box: { x: 0.35, y: 0.1, width: 0.15, height: 0.05 },
            },
          ],
        },
        {
          id: 'line-2',
          raw_text: 'Total: $1,250.00',
          confidence: 0.95,
          tokens: [
            {
              id: 'tok-3',
              raw_text: '$1,250.00',
              confidence: 0.95,
              reading_order_index: 3,
              bounding_box: { x: 0.1, y: 0.2, width: 0.3, height: 0.05 },
            },
          ],
        },
      ],
      tokens: [
        {
          id: 'tok-1',
          raw_text: 'ACME',
          confidence: 0.99,
          reading_order_index: 1,
          bounding_box: { x: 0.1, y: 0.1, width: 0.2, height: 0.05 },
        },
        {
          id: 'tok-2',
          raw_text: 'Corp',
          confidence: 0.98,
          reading_order_index: 2,
          bounding_box: { x: 0.35, y: 0.1, width: 0.15, height: 0.05 },
        },
        {
          id: 'tok-3',
          raw_text: '$1,250.00',
          confidence: 0.95,
          reading_order_index: 3,
          bounding_box: { x: 0.1, y: 0.2, width: 0.3, height: 0.05 },
        },
      ],
    },
    {
      page_number: 2,
      raw_text: 'Payment Due: 2026-12-01',
      extraction_status: 'SUCCEEDED',
      engine_name: 'rapidocr-optical-engine',
      has_vector_text: false,
      lines: [
        {
          id: 'line-3',
          raw_text: 'Payment Due: 2026-12-01',
          confidence: 0.91,
          tokens: [
            {
              id: 'tok-4',
              raw_text: '2026-12-01',
              confidence: 0.91,
              reading_order_index: 4,
              bounding_box: { x: 0.2, y: 0.4, width: 0.25, height: 0.05 },
            },
          ],
        },
      ],
      tokens: [
        {
          id: 'tok-4',
          raw_text: '2026-12-01',
          confidence: 0.91,
          reading_order_index: 4,
          bounding_box: { x: 0.2, y: 0.4, width: 0.25, height: 0.05 },
        },
      ],
    },
  ],
};

describe('OcrInspector', () => {
  it('renders OCR engine metadata and vector text indicator', () => {
    const handleSelectToken = vi.fn();
    render(
      <OcrInspector
        ocrData={mockOcrData}
        currentPage={1}
        onSelectToken={handleSelectToken}
      />
    );

    expect(screen.getByText('hybrid-ocr-pipeline')).toBeInTheDocument();
    expect(screen.getByText('Vector Digital Text')).toBeInTheDocument();
    expect(screen.getByText('ACME Corp Invoice')).toBeInTheDocument();
  });

  it('filters text with search query', () => {
    const handleSelectToken = vi.fn();
    render(
      <OcrInspector
        ocrData={mockOcrData}
        currentPage={1}
        onSelectToken={handleSelectToken}
      />
    );

    const searchInput = screen.getByPlaceholderText(/search in page 1/i);
    fireEvent.change(searchInput, { target: { value: '1,250' } });

    expect(screen.getByText('Total: $1,250.00')).toBeInTheDocument();
    expect(screen.queryByText('ACME Corp Invoice')).not.toBeInTheDocument();
  });

  it('selects token on click and triggers callback', () => {
    const handleSelectToken = vi.fn();
    render(
      <OcrInspector
        ocrData={mockOcrData}
        currentPage={1}
        onSelectToken={handleSelectToken}
      />
    );

    // Switch to tokens view
    fireEvent.click(screen.getByTitle('Token-Level Inspector'));
    expect(screen.getByText('ACME')).toBeInTheDocument();

    fireEvent.click(screen.getByText('ACME'));
    expect(handleSelectToken).toHaveBeenCalledWith(
      expect.objectContaining({ raw_text: 'ACME' })
    );
  });

  it('renders heuristic confidence disclaimer', () => {
    render(
      <OcrInspector
        ocrData={mockOcrData}
        currentPage={1}
        onSelectToken={vi.fn()}
      />
    );

    expect(
      screen.getByText(/confidence scores reflect ocr pattern recognition heuristics/i)
    ).toBeInTheDocument();
  });
});

