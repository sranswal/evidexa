import { render, screen, fireEvent } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { PdfDocumentViewer } from '../components/viewer/PdfDocumentViewer';

describe('PdfDocumentViewer', () => {
  const defaultProps = {
    documentUrl: '/api/v1/cases/case-1/documents/doc-1/download',
    fileExtension: '.png', // Use image to avoid mocking PDF.js worker in jsdom
    currentPage: 1,
    onPageChange: vi.fn(),
    onTotalPagesDetected: vi.fn(),
    scale: 1.0,
    onScaleChange: vi.fn(),
    rotation: 0 as const,
    onRotationChange: vi.fn(),
    activeOverlays: new Set<'ocr' | 'findings' | 'heatmap'>(['ocr', 'findings']),
    onToggleOverlay: vi.fn(),
    tokens: [
      {
        id: 'tok-1',
        raw_text: 'Test Token',
        confidence: 0.95,
        reading_order_index: 1,
        bounding_box: { x: 0.1, y: 0.1, width: 0.2, height: 0.05 },
      },
    ],
    evidenceList: [
      {
        id: 'ev-1',
        case_id: 'case-1',
        document_id: 'doc-1',
        evidence_type: 'VISUAL_REGION',
        source_component: 'ela-analyzer',
        page_number: 1,
        bounding_box: { x: 0.3, y: 0.3, width: 0.3, height: 0.2 },
        confidence: null,
        title: 'Compression Anomaly',
        description: 'Test anomaly',
        created_at: new Date().toISOString(),
      },
    ],
  };

  it('renders control bar buttons and indicators', () => {
    render(<PdfDocumentViewer {...defaultProps} />);

    expect(screen.getByTitle('Zoom In (+25%)')).toBeInTheDocument();
    expect(screen.getByTitle('Zoom Out (-25%)')).toBeInTheDocument();
    expect(screen.getByText('100%')).toBeInTheDocument();
    expect(screen.getByText('OCR (1)')).toBeInTheDocument();
    expect(screen.getByText('Findings (1)')).toBeInTheDocument();
  });

  it('triggers zoom in and zoom out callbacks', () => {
    const handleScaleChange = vi.fn();
    render(<PdfDocumentViewer {...defaultProps} onScaleChange={handleScaleChange} />);

    fireEvent.click(screen.getByTitle('Zoom In (+25%)'));
    expect(handleScaleChange).toHaveBeenCalledWith(1.25);

    fireEvent.click(screen.getByTitle('Zoom Out (-25%)'));
    expect(handleScaleChange).toHaveBeenCalledWith(0.75);
  });

  it('triggers 90 degree clockwise rotation callback', () => {
    const handleRotationChange = vi.fn();
    render(<PdfDocumentViewer {...defaultProps} onRotationChange={handleRotationChange} />);

    const rotateBtn = screen.getByTitle(/rotate clockwise 90°/i);
    fireEvent.click(rotateBtn);
    expect(handleRotationChange).toHaveBeenCalledWith(90);
  });

  it('toggles overlay layer buttons', () => {
    const handleToggleOverlay = vi.fn();
    render(<PdfDocumentViewer {...defaultProps} onToggleOverlay={handleToggleOverlay} />);

    fireEvent.click(screen.getByText('OCR (1)'));
    expect(handleToggleOverlay).toHaveBeenCalledWith('ocr');

    fireEvent.click(screen.getByText('Findings (1)'));
    expect(handleToggleOverlay).toHaveBeenCalledWith('findings');
  });

  it('renders image element for non-PDF documents', () => {
    render(<PdfDocumentViewer {...defaultProps} />);
    const img = screen.getByAltText('Evidence Document Page');
    expect(img).toBeInTheDocument();
    expect(img).toHaveAttribute('src', defaultProps.documentUrl);
  });
});

