import { api } from "./client";
import type {
  Case,
  CaseListResponse,
  CaseStatus,
  DocumentListResponse,
  FindingListResponse,
  AggregatedFinding,
  PaginatedRelationshipsResponse,
  InvestigationDossier,
  ProcessingRun,
} from "../types/api";

export interface CreateCasePayload {
  title: string;
  description?: string;
  created_by?: string;
  metadata?: Record<string, unknown>;
}

export interface ListCasesParams {
  [key: string]: string | number | boolean | undefined | null;
  skip?: number;
  limit?: number;
  status?: CaseStatus;
}

export const casesApi = {
  listCases: (params?: ListCasesParams): Promise<CaseListResponse> => {
    return api.get<CaseListResponse>("/cases", params);
  },

  getCase: (caseId: string): Promise<Case> => {
    return api.get<Case>(`/cases/${caseId}`);
  },

  createCase: (payload: CreateCasePayload): Promise<Case> => {
    return api.post<Case>("/cases", payload);
  },

  archiveCase: (caseId: string): Promise<Case> => {
    return api.post<Case>(`/cases/${caseId}/archive`);
  },

  listCaseDocuments: (caseId: string, skip = 0, limit = 50): Promise<DocumentListResponse> => {
    return api.get<DocumentListResponse>(`/cases/${caseId}/documents`, { skip, limit });
  },

  listCaseFindings: (caseId: string, skip = 0, limit = 50): Promise<FindingListResponse> => {
    return api.get<FindingListResponse>(`/cases/${caseId}/findings`, { skip, limit });
  },

  listAggregatedFindings: (caseId: string): Promise<AggregatedFinding[]> => {
    return api.get<AggregatedFinding[]>(`/cases/${caseId}/findings/aggregated`);
  },

  listRelationships: (caseId: string, skip = 0, limit = 50): Promise<PaginatedRelationshipsResponse> => {
    return api.get<PaginatedRelationshipsResponse>(`/cases/${caseId}/relationships`, { skip, limit });
  },

  listConsistencyRuns: (caseId: string): Promise<ProcessingRun[]> => {
    return api.get<ProcessingRun[]>(`/cases/${caseId}/consistency/runs`);
  },

  listDossiers: (caseId: string): Promise<InvestigationDossier[]> => {
    return api.get<InvestigationDossier[]>(`/cases/${caseId}/dossiers`);
  },

  generateDossier: (caseId: string, scopeAndPurpose?: string): Promise<InvestigationDossier> => {
    return api.post<InvestigationDossier>(`/cases/${caseId}/dossiers/generate`, {
      created_by: "investigator",
      scope_and_purpose: scopeAndPurpose,
    });
  },
};
