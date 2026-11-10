import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { describe, expect, it, vi, beforeEach } from 'vitest';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { DocumentExaminePage } from '../pages/DocumentExaminePage';
import { documentsApi } from '../api/documents';
import { casesApi } from '../api/cases';

vi.mock('../api/documents', () => ({
  documentsApi: {
    getDocument: vi.fn(),
    getOcrText: vi.fn(),
    getExtraction: vi.fn(),
    listDocumentFindings: vi.fn(),
    listDocumentEvidence: vi.fn(),
    listDocumentRuns: vi.fn(),
    getDocumentDownloadUrl: vi.fn().mockReturnValue('/api/v1/cases/c-1/documents/d-1/download'),
    getArtifactUrl: vi.fn().mockReturnValue('/api/v1/cases/c-1/documents/d-1/artifacts/r-1/ela.png'),
  },
}));

vi.mock('../api/cases', () => ({
  casesApi: {
    getCase: vi.fn(),
  },
}));

const mockDoc = {
  id: 'd-1',
  case_id: 'c-1',
  original_filename: 'bank_statement.pdf',
  media_type: 'application/pdf',
  file_extension: '.png', // Use image in test to bypass jsdom worker
  file_size_bytes: 10240,
  sha256: 'a1b2c3d4e5f67890123456789012345678901234567890123456789012345678',
  storage_key: 'c-1/d-1.png',
  page_count: 2,
  document_type: 'BANK_STATEMENT',
  ingestion_status: 'STORED',
  created_at: new Date().toISOString(),
  created_by: 'lead_examiner',
  metadata: {},
};

const mockCase = {
  id: 'c-1',
  case_reference: 'CASE-2026-0042',
  title: 'Corporate Financial Audit',
  status: 'ACTIVE',
  created_at: new Date().toISOString(),
  updated_at: new Date().toISOString(),
  created_by: 'examiner',
  metadata: {},
};

describe('DocumentExaminePage Integration', () => {
  let queryClient: QueryClient;

  beforeEach(() => {
    vi.clearAllMocks();
    queryClient = new QueryClient({
      defaultOptions: {
        queries: { retry: false },
      },
    });

    vi.mocked(documentsApi.getDocument).mockResolvedValue(mockDoc as any);
    vi.mocked(casesApi.getCase).mockResolvedValue(mockCase as any);
    vi.mocked(documentsApi.getOcrText).mockResolvedValue({
      document_id: 'd-1',
      processing_run_id: 'r-1',
      total_pages: 1,
      total_tokens: 1,
      full_raw_text: 'Account Statement Sample',
      pages: [
        {
          page_number: 1,
          raw_text: 'Account Statement Sample',
          extraction_status: 'SUCCEEDED',
          has_vector_text: true,
          engine_name: 'pdfium-ocr-engine',
          tokens: [
            {
              id: 'tok-1',
              raw_text: 'Account',
              confidence: 0.99,
              bounding_box: { x: 0.1, y: 0.1, width: 0.2, height: 0.05 },
            },
          ],
        },
      ],
    });
    vi.mocked(documentsApi.getExtraction).mockResolvedValue({
      document_id: 'd-1',
      processing_run_id: 'r-1',
      document_class: 'BANK_STATEMENT',
      schema_id: 'bank_stmt_v1',
      schema_version: '1.0.0',
      fields: {},
      validation_summary: {},
      execution_duration_ms: 50,
      created_at: new Date().toISOString(),
    });
    vi.mocked(documentsApi.listDocumentFindings).mockResolvedValue({
      items: [],
      total: 0,
      skip: 0,
      limit: 50,
    });
    vi.mocked(documentsApi.listDocumentEvidence).mockResolvedValue({
      items: [],
      total: 0,
      skip: 0,
      limit: 50,
    });
    vi.mocked(documentsApi.listDocumentRuns).mockResolvedValue({
      items: [],
      total: 0,
      skip: 0,
      limit: 50,
    });
  });

  const renderComponent = () =>
    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={['/cases/c-1/documents/d-1/examine']}>
          <Routes>
            <Route
              path="/cases/:caseId/documents/:documentId/examine"
              element={<DocumentExaminePage />}
            />
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>
    );

  it('mounts and renders breadcrumbs, document title, and SHA-256 prefix', async () => {
    renderComponent();

    await waitFor(() => {
      expect(screen.getByText('bank_statement.pdf')).toBeInTheDocument();
      expect(screen.getByText('CASE-2026-0042')).toBeInTheDocument();
      expect(screen.getByText(/SHA-256: a1b2c3d4e5f6/)).toBeInTheDocument();
    });
  });

  it('switches inspector tabs between OCR, Extraction, Findings, and Runs', async () => {
    renderComponent();

    await waitFor(() => {
      expect(screen.getByText('bank_statement.pdf')).toBeInTheDocument();
    });

    // Default tab is OCR
    expect(screen.getByText('pdfium-ocr-engine')).toBeInTheDocument();

    // Switch to Extraction tab
    fireEvent.click(screen.getByTestId('tab-extraction'));
    expect(screen.getByText('No Structured Fields Extracted')).toBeInTheDocument();

    // Switch to Findings tab
    fireEvent.click(screen.getByTestId('tab-findings'));
    expect(screen.getByText('No Findings Detected')).toBeInTheDocument();

    // Switch to Runs tab
    fireEvent.click(screen.getByTestId('tab-info'));
    expect(screen.getByText('Document Metadata')).toBeInTheDocument();
  });
});
