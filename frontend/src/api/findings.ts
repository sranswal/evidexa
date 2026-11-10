import { api } from "./client";
import type {
  AggregatedFinding,
  AggregatedFindingReview,
  ReviewCreateRequest,
} from "../types/api";

export const findingsApi = {
  getAggregatedFindings: (caseId: string): Promise<AggregatedFinding[]> => {
    return api.get<AggregatedFinding[]>(`/cases/${caseId}/findings/aggregated`);
  },

  recordFindingReview: (
    caseId: string,
    findingId: string,
    payload: ReviewCreateRequest
  ): Promise<AggregatedFindingReview> => {
    return api.post<AggregatedFindingReview>(
      `/cases/${caseId}/findings/aggregated/${findingId}/reviews`,
      payload
    );
  },

  listFindingReviews: (
    caseId: string,
    findingId: string
  ): Promise<AggregatedFindingReview[]> => {
    return api.get<AggregatedFindingReview[]>(
      `/cases/${caseId}/findings/aggregated/${findingId}/reviews`
    );
  },
};

