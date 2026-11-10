import { request } from "./client";
import type { GraphSnapshot } from "../types/api";

export interface CrossCaseScope {
  id: string;
  organization_id: string;
  name: string;
  description?: string | null;
  case_ids: string[];
  created_by: string;
  created_at: string;
  updated_at: string;
  is_active: boolean;
  metadata?: Record<string, unknown>;
}

export interface CrossCaseMatchEvidence {
  target_case_id: string;
  candidate_case_id: string;
  target_mention_id: string;
  candidate_mention_id: string;
  target_document_id: string;
  candidate_document_id: string;
  target_page_number?: number;
  candidate_page_number?: number;
  target_field_key: string;
  candidate_field_key: string;
  matching_signals: string[];
  contradicting_signals: string[];
  confidence_score: number;
  matching_method: string;
  match_classification: string;
}

export interface CrossCaseMatchReview {
  id: string;
  match_id: string;
  scope_id: string;
  decision: "PENDING_REVIEW" | "ACCEPTED" | "REJECTED" | "NEEDS_FURTHER_INVESTIGATION";
  reviewer_id: string;
  reviewer_username: string;
  rationale: string;
  previous_status?: string | null;
  new_status: string;
  reviewed_at: string;
}

export interface CrossCaseCandidateMatch {
  id: string;
  scope_id: string;
  organization_id: string;
  entity_type: string;
  target_case_id: string;
  candidate_case_id: string;
  target_value_display: string;
  candidate_value_display: string;
  raw_target_value_masked: string;
  raw_candidate_value_masked: string;
  matching_method: string;
  match_classification: string;
  match_score: number;
  decision_status: "PENDING_REVIEW" | "ACCEPTED" | "REJECTED" | "NEEDS_FURTHER_INVESTIGATION";
  evidence: CrossCaseMatchEvidence;
  review_history: CrossCaseMatchReview[];
  created_at: string;
}

export interface CrossCaseCorrelationResult {
  scope_id: string;
  cases_analyzed: string[];
  total_mentions_compared: number;
  candidate_matches: CrossCaseCandidateMatch[];
  execution_duration_ms: number;
  correlated_at: string;
}

export interface CreateScopePayload {
  name: string;
  case_ids: string[];
  description?: string;
  metadata?: Record<string, unknown>;
}

export interface PaginatedCandidatesResponse {
  items: CrossCaseCandidateMatch[];
  total: number;
  limit: number;
  offset: number;
}

export const crossCaseApi = {
  createScope: (data: CreateScopePayload): Promise<CrossCaseScope> =>
    request<CrossCaseScope>("/cross-case/scopes", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  listScopes: (): Promise<CrossCaseScope[]> =>
    request<CrossCaseScope[]>("/cross-case/scopes"),

  getScope: (scopeId: string): Promise<CrossCaseScope> =>
    request<CrossCaseScope>(`/cross-case/scopes/${scopeId}`),

  updateScopeCases: (scopeId: string, caseIds: string[]): Promise<CrossCaseScope> =>
    request<CrossCaseScope>(`/cross-case/scopes/${scopeId}/cases`, {
      method: "PUT",
      body: JSON.stringify({ case_ids: caseIds }),
    }),

  runCorrelation: (scopeId: string): Promise<CrossCaseCorrelationResult> =>
    request<CrossCaseCorrelationResult>(`/cross-case/scopes/${scopeId}/correlate`, {
      method: "POST",
    }),

  listCandidates: (
    scopeId: string,
    params?: { decision_status?: string; entity_type?: string; limit?: number; offset?: number }
  ): Promise<PaginatedCandidatesResponse> =>
    request<PaginatedCandidatesResponse>(`/cross-case/scopes/${scopeId}/candidates`, {
      params: params as Record<string, string | number>,
    }),

  getCandidate: (scopeId: string, matchId: string): Promise<CrossCaseCandidateMatch> =>
    request<CrossCaseCandidateMatch>(`/cross-case/scopes/${scopeId}/candidates/${matchId}`),

  reviewCandidate: (
    scopeId: string,
    matchId: string,
    data: { decision: "ACCEPTED" | "REJECTED" | "NEEDS_FURTHER_INVESTIGATION"; rationale: string }
  ): Promise<CrossCaseCandidateMatch> =>
    request<CrossCaseCandidateMatch>(`/cross-case/scopes/${scopeId}/candidates/${matchId}/review`, {
      method: "POST",
      body: JSON.stringify(data),
    }),

  getCrossCaseGraph: (
    scopeId: string,
    params?: { max_hops?: number; max_nodes?: number }
  ): Promise<GraphSnapshot> =>
    request<GraphSnapshot>(`/cross-case/scopes/${scopeId}/graph`, {
      params: params as Record<string, number>,
    }),
};
