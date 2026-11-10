import { api } from "./client";
import type {
  InvestigationDossier,
  DossierGenerateRequest,
  DossierFinalizeRequest,
} from "../types/api";

export const dossiersApi = {
  listDossiers: (caseId: string): Promise<InvestigationDossier[]> => {
    return api.get<InvestigationDossier[]>(`/cases/${caseId}/dossiers`);
  },

  getDossier: (caseId: string, dossierId: string): Promise<InvestigationDossier> => {
    return api.get<InvestigationDossier>(`/cases/${caseId}/dossiers/${dossierId}`);
  },

  generateDossier: (
    caseId: string,
    payload: DossierGenerateRequest
  ): Promise<InvestigationDossier> => {
    return api.post<InvestigationDossier>(`/cases/${caseId}/dossiers/generate`, payload);
  },

  finalizeDossier: (
    caseId: string,
    dossierId: string,
    payload: DossierFinalizeRequest
  ): Promise<InvestigationDossier> => {
    return api.post<InvestigationDossier>(
      `/cases/${caseId}/dossiers/${dossierId}/finalize`,
      payload
    );
  },

  getExportUrl: (
    caseId: string,
    dossierId: string,
    format: "pdf" | "json" = "pdf",
    userId = "investigator"
  ): string => {
    return `/api/v1/cases/${caseId}/dossiers/${dossierId}/export?format=${format}&user_id=${encodeURIComponent(
      userId
    )}`;
  },
};

