import React, { createContext, useContext, useState, useEffect } from "react";
import { useParams } from "react-router-dom";
import { casesApi } from "../api/cases";
import type { Case } from "../types/api";

interface CaseContextType {
  activeCaseId: string | null;
  activeCase: Case | null;
  isLoadingCase: boolean;
  caseError: Error | null;
  setActiveCaseId: (id: string | null) => void;
  refreshCase: () => Promise<void>;
}

const CaseContext = createContext<CaseContextType | undefined>(undefined);

export const CaseProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { caseId } = useParams<{ caseId?: string }>();
  const [activeCaseId, setActiveCaseId] = useState<string | null>(caseId || null);
  const [activeCase, setActiveCase] = useState<Case | null>(null);
  const [isLoadingCase, setIsLoadingCase] = useState<boolean>(false);
  const [caseError, setCaseError] = useState<Error | null>(null);

  useEffect(() => {
    if (caseId) {
      setActiveCaseId(caseId);
    }
  }, [caseId]);

  const loadCase = async (id: string) => {
    setIsLoadingCase(true);
    setCaseError(null);
    try {
      const data = await casesApi.getCase(id);
      setActiveCase(data);
    } catch (err) {
      setCaseError(err instanceof Error ? err : new Error("Failed to load case context"));
      setActiveCase(null);
    } finally {
      setIsLoadingCase(false);
    }
  };

  useEffect(() => {
    if (activeCaseId) {
      loadCase(activeCaseId);
    } else {
      setActiveCase(null);
    }
  }, [activeCaseId]);

  return (
    <CaseContext.Provider
      value={{
        activeCaseId,
        activeCase,
        isLoadingCase,
        caseError,
        setActiveCaseId,
        refreshCase: async () => {
          if (activeCaseId) await loadCase(activeCaseId);
        },
      }}
    >
      {children}
    </CaseContext.Provider>
  );
};

export const useCaseContext = (): CaseContextType => {
  const context = useContext(CaseContext);
  if (!context) {
    throw new Error("useCaseContext must be used within a CaseProvider");
  }
  return context;
};

