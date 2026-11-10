import { render, screen, fireEvent } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { FindingsInspector } from '../components/viewer/FindingsInspector';
import type { ForensicFinding, EvidenceNode } from '../types/api';

const mockFindings: ForensicFinding[] = [
  {
    id: 'find-1',
    document_id: 'doc-123',
    processing_run_id: 'run-1',
    category: 'VISUAL_ANOMALY',
    finding_type: 'visual_ela',
    severity: 'HIGH',
    title: 'Candidate visual region with local compression inconsistency',
    description: 'Compression difference indicator detected in candidate region on page 1.',
    rule_id: 'visual.ela.compression_delta',
    page_number: 1,
    confidence: null,
    evidence_ids: ['ev-1'],
    limitations: ['Scanned document background noise may trigger elevated error levels.'],
    created_at: new Date().toISOString(),
  },
  {
    id: 'find-2',
    document_id: 'doc-123',
    processing_run_id: 'run-1',
    category: 'PDF_STRUCTURE',
    finding_type: 'pdf_xref_anomaly',
    severity: 'MEDIUM',
    title: 'Multiple incremental update sections detected',
    description: 'PDF contains 3 incremental update sections indicating post-creation revision.',
    rule_id: 'pdf.structural.incremental_update',
    page_number: 2,
    confidence: null,
    evidence_ids: [],
    created_at: new Date().toISOString(),
  },
];

const mockEvidenceList: EvidenceNode[] = [
  {
    id: 'ev-1',
    case_id: 'case-1',
    document_id: 'doc-123',
    evidence_type: 'VISUAL_REGION',
    source_component: 'ela-analyzer',
    page_number: 1,
    bounding_box: { x: 0.2, y: 0.3, width: 0.4, height: 0.2 },
    confidence: null,
    title: 'Observation: Candidate visual region',
    description: 'Compression delta observed',
    created_at: new Date().toISOString(),
  },
];

describe('FindingsInspector', () => {
  it('renders findings and severity distribution badges', () => {
    render(
      <FindingsInspector
        findings={mockFindings}
        evidenceList={mockEvidenceList}
        currentPage={1}
        onNavigateToPage={vi.fn()}
        onSelectEvidence={vi.fn()}
        onHighlightBox={vi.fn()}
      />
    );

    expect(screen.getByText(/candidate visual region with local compression/i)).toBeInTheDocument();
    expect(screen.getByText(/multiple incremental update sections detected/i)).toBeInTheDocument();
    expect(screen.getByText('HIGH (1)')).toBeInTheDocument();
    expect(screen.getByText('MEDIUM (1)')).toBeInTheDocument();
  });

  it('filters by page when page-only filter is clicked', () => {
    render(
      <FindingsInspector
        findings={mockFindings}
        evidenceList={mockEvidenceList}
        currentPage={1}
        onNavigateToPage={vi.fn()}
        onSelectEvidence={vi.fn()}
        onHighlightBox={vi.fn()}
      />
    );

    fireEvent.click(screen.getByText('All Pages'));
    // Now page 1 only
    expect(screen.getByText('Page 1 Only')).toBeInTheDocument();
    expect(screen.getByText(/candidate visual region/i)).toBeInTheDocument();
    expect(screen.queryByText(/multiple incremental update sections/i)).not.toBeInTheDocument();
  });

  it('navigates and highlights bounding box when locate evidence is clicked', () => {
    const handleSelectEvidence = vi.fn();
    const handleHighlightBox = vi.fn();

    render(
      <FindingsInspector
        findings={mockFindings}
        evidenceList={mockEvidenceList}
        currentPage={1}
        onNavigateToPage={vi.fn()}
        onSelectEvidence={handleSelectEvidence}
        onHighlightBox={handleHighlightBox}
      />
    );

    const locateButtons = screen.getAllByText('Locate on Page');
    fireEvent.click(locateButtons[0]);

    expect(handleSelectEvidence).toHaveBeenCalledWith(
      expect.objectContaining({ id: 'ev-1' })
    );
    expect(handleHighlightBox).toHaveBeenCalledWith(
      expect.objectContaining({ x: 0.2, y: 0.3 })
    );
  });

  it('displays the non-verdict forensic caveat banner', () => {
    render(
      <FindingsInspector
        findings={mockFindings}
        evidenceList={mockEvidenceList}
        currentPage={1}
        onNavigateToPage={vi.fn()}
        onSelectEvidence={vi.fn()}
        onHighlightBox={vi.fn()}
      />
    );

    expect(
      screen.getByText(/they do not constitute automated fraud determinations/i)
    ).toBeInTheDocument();
  });
});

