import React from "react";
import { Outlet } from "react-router-dom";
import { Sidebar } from "./Sidebar";
import { Header } from "./Header";
import { CaseProvider } from "../../context/CaseContext";

export const AppShell: React.FC = () => {
  return (
    <CaseProvider>
      <div className="flex min-h-screen bg-evidexa-midnight text-slate-100">
        <Sidebar />
        <div className="flex-1 flex flex-col min-w-0">
          <Header />
          <main className="flex-1 p-6 md:p-8 max-w-7xl w-full mx-auto">
            <Outlet />
          </main>
        </div>
      </div>
    </CaseProvider>
  );
};

