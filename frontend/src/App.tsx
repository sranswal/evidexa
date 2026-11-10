import React from "react";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { AuthProvider } from "./context/AuthContext";
import { ProtectedRoute } from "./components/auth/ProtectedRoute";
import { AppShell } from "./components/layout/AppShell";
import { LandingPage } from "./pages/LandingPage";
import { LoginPage } from "./pages/LoginPage";
import { RegisterPage } from "./pages/RegisterPage";
import { CasesPage } from "./pages/CasesPage";
import { CaseOverviewPage } from "./pages/CaseOverviewPage";
import { DocumentsPage } from "./pages/DocumentsPage";
import { DocumentExaminePage } from "./pages/DocumentExaminePage";
import { EvidenceGraphPage } from "./pages/EvidenceGraphPage";
import { FindingsWorkbenchPage } from "./pages/FindingsWorkbenchPage";
import { AssistantPage } from "./pages/AssistantPage";
import { CrossCasePage } from "./pages/CrossCasePage";
import { PlaceholderPage } from "./pages/PlaceholderPage";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      refetchOnWindowFocus: false,
      staleTime: 30000,
    },
  },
});

export const App: React.FC = () => {
  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <BrowserRouter>
          <Routes>
            {/* Public Unauthenticated Routes */}
            <Route path="/" element={<LandingPage />} />
            <Route path="/landing" element={<LandingPage />} />
            <Route path="/login" element={<LoginPage />} />
            <Route path="/register" element={<RegisterPage />} />

            {/* Protected Investigation Workspace */}
            <Route
              element={
                <ProtectedRoute>
                  <AppShell />
                </ProtectedRoute>
              }
            >
              <Route path="/app" element={<Navigate to="/cases" replace />} />
              <Route path="/dashboard" element={<Navigate to="/cases" replace />} />
              <Route path="/cases" element={<CasesPage />} />
              <Route path="/cases/:caseId" element={<Navigate to="overview" replace />} />
              <Route path="/cases/:caseId/overview" element={<CaseOverviewPage />} />
              <Route path="/cases/:caseId/documents" element={<DocumentsPage />} />
              <Route path="/cases/:caseId/documents/:documentId" element={<DocumentExaminePage />} />
              <Route path="/cases/:caseId/documents/:documentId/examine" element={<DocumentExaminePage />} />
              <Route path="/cases/:caseId/graph" element={<EvidenceGraphPage />} />
              <Route path="/cases/:caseId/findings" element={<FindingsWorkbenchPage />} />
              <Route path="/cases/:caseId/assistant" element={<AssistantPage />} />
              <Route path="/cross-case" element={<CrossCasePage />} />
              <Route
                path="/cases/:caseId/dossiers"
                element={<PlaceholderPage moduleKey="dossiers" />}
              />
              <Route path="*" element={<Navigate to="/cases" replace />} />
            </Route>
          </Routes>
        </BrowserRouter>
      </AuthProvider>
    </QueryClientProvider>
  );
};

export default App;
