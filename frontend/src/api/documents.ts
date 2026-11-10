import { api, request, BASE_URL } from "./client";
import type {
  DocumentItem,
  DocumentListResponse,
  AnalyzerInfo,
  ProcessingRun,
  ProcessingRunListResponse,
  ForensicFinding,
  FindingListResponse,
  EvidenceNode,
  EvidenceListResponse,
  DocumentClassificationResult,
  DocumentExtractionResult,
  ExtractedDocumentText,
  DocumentLayersResponse,
  TextToken,
} from "../types/api";

export const documentsApi = {
  listDocuments: (caseId: string, skip = 0, limit = 50): Promise<DocumentListResponse> => {
    return api.get<DocumentListResponse>(`/cases/${caseId}/documents`, { skip, limit });
  },

  getDocument: (caseId: string, documentId: string): Promise<DocumentItem> => {
    return api.get<DocumentItem>(`/cases/${caseId}/documents/${documentId}`);
  },

  uploadDocument: (caseId: string, file: File, createdBy?: string): Promise<DocumentItem> => {
    const formData = new FormData();
    formData.append("file", file);
    if (createdBy) {
      formData.append("created_by", createdBy);
    }
    return request<DocumentItem>(`/cases/${caseId}/documents`, {
      method: "POST",
      body: formData,
    });
  },

  listAnalyzers: (caseId: string): Promise<AnalyzerInfo[]> => {
    return api.get<AnalyzerInfo[]>(`/cases/${caseId}/analyzers`);
  },

  analyzeDocument: (
    caseId: string,
    documentId: string,
    analyzerId = "pdf-structural-analyzer",
    options: Record<string, unknown> = {}
  ): Promise<{ processing_run: ProcessingRun; findings: ForensicFinding[] }> => {
    return api.post<{ processing_run: ProcessingRun; findings: ForensicFinding[] }>(
      `/cases/${caseId}/documents/${documentId}/analyze`,
      { analyzer_id: analyzerId, options }
    );
  },

  startOcr: (
    caseId: string,
    documentId: string,
    analyzerId = "hybrid-ocr-pipeline",
    options: Record<string, unknown> = {}
  ): Promise<{ processing_run: ProcessingRun; summary: Record<string, unknown> }> => {
    return api.post<{ processing_run: ProcessingRun; summary: Record<string, unknown> }>(
      `/cases/${caseId}/documents/${documentId}/ocr`,
      { analyzer_id: analyzerId, options }
    );
  },

  getOcrText: (caseId: string, documentId: string, layer?: string): Promise<ExtractedDocumentText> => {
    return api.get<ExtractedDocumentText>(
      `/cases/${caseId}/documents/${documentId}/ocr/text`,
      { layer }
    );
  },

  getLayers: (caseId: string, documentId: string, pageNumber?: number): Promise<DocumentLayersResponse> => {
    return api.get<DocumentLayersResponse>(
      `/cases/${caseId}/documents/${documentId}/ocr/layers`,
      { page_number: pageNumber }
    );
  },

  classifyDocument: (
    caseId: string,
    documentId: string,
    options: Record<string, unknown> = {}
  ): Promise<DocumentClassificationResult> => {
    return api.post<DocumentClassificationResult>(
      `/cases/${caseId}/documents/${documentId}/classification`,
      { options }
    );
  },

  getClassification: (caseId: string, documentId: string): Promise<DocumentClassificationResult> => {
    return api.get<DocumentClassificationResult>(
      `/cases/${caseId}/documents/${documentId}/classification`
    );
  },

  extractFields: (
    caseId: string,
    documentId: string,
    schemaId?: string,
    options: Record<string, unknown> = {}
  ): Promise<DocumentExtractionResult> => {
    return api.post<DocumentExtractionResult>(
      `/cases/${caseId}/documents/${documentId}/extraction`,
      { schema_id: schemaId, options }
    );
  },

  getExtraction: (caseId: string, documentId: string): Promise<DocumentExtractionResult> => {
    return api.get<DocumentExtractionResult>(
      `/cases/${caseId}/documents/${documentId}/extraction`
    );
  },

  listDocumentRuns: (
    caseId: string,
    documentId: string,
    skip = 0,
    limit = 50
  ): Promise<ProcessingRunListResponse> => {
    return api.get<ProcessingRunListResponse>(`/cases/${caseId}/processing-runs`, {
      document_id: documentId,
      skip,
      limit,
    });
  },

  listDocumentFindings: (
    caseId: string,
    documentId: string,
    skip = 0,
    limit = 50
  ): Promise<FindingListResponse> => {
    return api.get<FindingListResponse>(`/cases/${caseId}/findings`, {
      document_id: documentId,
      skip,
      limit,
    });
  },

  listDocumentEvidence: (
    caseId: string,
    documentId: string,
    skip = 0,
    limit = 50
  ): Promise<EvidenceListResponse> => {
    return api.get<EvidenceListResponse>(`/cases/${caseId}/evidence`, {
      document_id: documentId,
      skip,
      limit,
    });
  },

  getEvidence: (caseId: string, evidenceId: string): Promise<EvidenceNode> => {
    return api.get<EvidenceNode>(`/cases/${caseId}/evidence/${evidenceId}`);
  },

  getTokens: (
    caseId: string,
    documentId: string,
    pageNumber?: number,
    query?: string,
    offset = 0,
    limit = 100
  ): Promise<{ total_count: number; offset: number; limit: number; tokens: TextToken[] }> => {
    return api.get<{ total_count: number; offset: number; limit: number; tokens: TextToken[] }>(
      `/cases/${caseId}/documents/${documentId}/ocr/tokens`,
      { page_number: pageNumber, query, offset, limit }
    );
  },

  getDocumentDownloadUrl: (caseId: string, documentId: string): string => {
    return `${BASE_URL}/cases/${caseId}/documents/${documentId}/download`;
  },

  getArtifactUrl: (caseId: string, documentId: string, runId: string, filename: string): string => {
    return `${BASE_URL}/cases/${caseId}/documents/${documentId}/artifacts/${runId}/${filename}`;
  },
};

