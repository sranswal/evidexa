import { render, screen, fireEvent } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { StructuredExtractionInspector } from '../components/viewer/StructuredExtractionInspector';
import type { DocumentExtractionResult } from '../types/api';

const mockExtraction: DocumentExtractionResult = {
  document_id: 'doc-123',
  processing_run_id: 'run-456',
  document_class: 'INVOICE',
  schema_id: 'invoice_v1',
  schema_version: '1.0.0',
  execution_duration_ms: 120,
  created_at: new Date().toISOString(),
  validation_summary: { valid_count: 2 },
  fields: {
    invoice_total: {
      id: 'f-1',
      field_key: 'invoice_total',
      label: 'Invoice Total Amount',
      raw_text: '$1,250.00',
      normalized_value: 1250.0,
      data_type: 'DECIMAL',
      extraction_method: 'regex_pattern',
      score: 0.98,
      confidence: null,
      source_document_id: 'doc-123',
      source_page_number: 1,
      source_bounding_boxes: [{ x: 0.5, y: 0.8, width: 0.2, height: 0.05 }],
      validation_status: 'VALID',
      warnings: [],
    },
    bank_account_number: {
      id: 'f-2',
      field_key: 'bank_account_number',
      label: 'Bank Account Number',
      raw_text: '987654321098',
      normalized_value: '987654321098',
      data_type: 'ACCOUNT_NUMBER',
      extraction_method: 'pattern_match',
      score: 0.9,
      confidence: null,
      source_document_id: 'doc-123',
      source_page_number: 1,
      source_bounding_boxes: [],
      validation_status: 'VALID',
      warnings: [],
    },
  },
};

describe('StructuredExtractionInspector', () => {
  it('renders extracted fields and document class schema', () => {
    render(
      <StructuredExtractionInspector
        extractionData={mockExtraction}
        currentPage={1}
        onNavigateToPage={vi.fn()}
        onHighlightBox={vi.fn()}
      />
    );

    expect(screen.getByText('INVOICE')).toBeInTheDocument();
    expect(screen.getByText('Invoice Total Amount')).toBeInTheDocument();
    expect(screen.getByText('Bank Account Number')).toBeInTheDocument();
  });

  it('masks sensitive bank account number by default and unmasks on toggle', () => {
    render(
      <StructuredExtractionInspector
        extractionData={mockExtraction}
        currentPage={1}
        onNavigateToPage={vi.fn()}
        onHighlightBox={vi.fn()}
      />
    );

    // Default masked
    expect(screen.getByText('•••••••• 1098')).toBeInTheDocument();

    // Toggle reveal
    const revealBtn = screen.getByTitle('Reveal identifier');
    fireEvent.click(revealBtn);

    expect(screen.getByText('987654321098')).toBeInTheDocument();
  });

  it('triggers box highlight when field with bounding box is clicked', () => {
    const handleHighlightBox = vi.fn();
    render(
      <StructuredExtractionInspector
        extractionData={mockExtraction}
        currentPage={1}
        onNavigateToPage={vi.fn()}
        onHighlightBox={handleHighlightBox}
      />
    );

    fireEvent.click(screen.getByText('Invoice Total Amount'));
    expect(handleHighlightBox).toHaveBeenCalledWith(
      expect.objectContaining({ x: 0.5, y: 0.8 })
    );
  });

  it('shows missing spatial bounds indicator when coordinates are absent', () => {
    render(
      <StructuredExtractionInspector
        extractionData={mockExtraction}
        currentPage={1}
        onNavigateToPage={vi.fn()}
        onHighlightBox={vi.fn()}
      />
    );

    expect(screen.getByText('No spatial bounds')).toBeInTheDocument();
  });
});

