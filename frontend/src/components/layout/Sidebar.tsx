import React from "react";
import { NavLink, Link } from "react-router-dom";
import {
  FolderKanban,
  LayoutDashboard,
  FileText,
  Network,
  ShieldAlert,
  FileCheck2,
  ShieldCheck,
  ExternalLink,
  Bot,
} from "lucide-react";
import clsx from "clsx";
import { Logo } from "../brand/Logo";
import { StatusBadge } from "../ui/Badge";
import { useCaseContext } from "../../context/CaseContext";

export const Sidebar: React.FC = () => {
  const { activeCaseId, activeCase } = useCaseContext();

  const navLinkClass = ({ isActive }: { isActive: boolean }) =>
    clsx(
      "flex items-center gap-3 px-3 py-2 rounded-md text-sm font-medium transition-all select-none group",
      isActive
        ? "bg-evidexa-slate/60 text-evidexa-cyan border-l-2 border-evidexa-cyan pl-2.5 font-semibold"
        : "text-slate-300 hover:bg-slate-800/60 hover:text-white"
    );

  return (
    <aside className="w-64 bg-evidexa-charcoal border-r border-evidexa-slate flex flex-col shrink-0 h-screen sticky top-0 overflow-y-auto">
      {/* Brand Header */}
      <div className="p-5 border-b border-evidexa-slate/80">
        <Link to="/cases" className="block focus:outline-none focus:ring-2 focus:ring-evidexa-cyan rounded">
          <Logo />
        </Link>
      </div>

      {/* Main Navigation */}
      <div className="flex-1 p-4 space-y-6">
        <div>
          <span className="text-[11px] font-mono uppercase tracking-wider text-slate-400 font-semibold px-3">
            Investigation Workspaces
          </span>
          <nav className="mt-2 space-y-1">
            <NavLink to="/cases" end className={navLinkClass}>
              <FolderKanban className="w-4 h-4 text-slate-400 group-hover:text-evidexa-cyan transition-colors" />
              <span>All Cases</span>
            </NavLink>
            <NavLink to="/cross-case" className={navLinkClass}>
              <Network className="w-4 h-4 text-slate-400 group-hover:text-evidexa-cyan transition-colors" />
              <span>Cross-Case Intel</span>
            </NavLink>
          </nav>
        </div>

        {/* Active Case Context Menu */}
        {activeCaseId ? (
          <div>
            <div className="flex items-center justify-between px-3 mb-2">
              <span className="text-[11px] font-mono uppercase tracking-wider text-slate-400 font-semibold">
                Active Case
              </span>
              <Link
                to="/cases"
                className="text-[11px] text-evidexa-aqua hover:underline flex items-center gap-0.5"
                title="Switch to another case"
              >
                Switch <ExternalLink className="w-2.5 h-2.5" />
              </Link>
            </div>

            {/* Case context pill */}
            <div className="px-3 py-2.5 mb-3 bg-evidexa-midnight/80 border border-evidexa-slate rounded-lg">
              <div className="flex items-center justify-between mb-1">
                <span className="text-xs font-mono font-bold text-evidexa-cyan tracking-wider">
                  {activeCase ? activeCase.case_reference : activeCaseId.slice(0, 12)}
                </span>
                {activeCase && <StatusBadge status={activeCase.status} type="case" />}
              </div>
              <p className="text-xs text-slate-300 truncate" title={activeCase?.title || ""}>
                {activeCase?.title || "Loading case..."}
              </p>
            </div>

            <nav className="space-y-1">
              <NavLink to={`/cases/${activeCaseId}/overview`} className={navLinkClass}>
                <LayoutDashboard className="w-4 h-4 text-slate-400 group-hover:text-evidexa-cyan transition-colors" />
                <span>Case Overview</span>
              </NavLink>

              <NavLink to={`/cases/${activeCaseId}/documents`} className={navLinkClass}>
                <FileText className="w-4 h-4 text-slate-400 group-hover:text-evidexa-cyan transition-colors" />
                <span>Documents</span>
              </NavLink>

              <NavLink to={`/cases/${activeCaseId}/graph`} className={navLinkClass}>
                <Network className="w-4 h-4 text-slate-400 group-hover:text-evidexa-cyan transition-colors" />
                <span>Evidence Graph</span>
              </NavLink>

              <NavLink to={`/cases/${activeCaseId}/findings`} className={navLinkClass}>
                <ShieldAlert className="w-4 h-4 text-slate-400 group-hover:text-evidexa-cyan transition-colors" />
                <span>Findings</span>
              </NavLink>

              <NavLink to={`/cases/${activeCaseId}/assistant`} className={navLinkClass}>
                <Bot className="w-4 h-4 text-slate-400 group-hover:text-evidexa-cyan transition-colors" />
                <span>AI Assistant</span>
              </NavLink>

              <NavLink to={`/cases/${activeCaseId}/dossiers`} className={navLinkClass}>
                <FileCheck2 className="w-4 h-4 text-slate-400 group-hover:text-evidexa-cyan transition-colors" />
                <span>Dossiers</span>
              </NavLink>
            </nav>
          </div>
        ) : (
          <div className="p-3 bg-evidexa-midnight/40 border border-dashed border-evidexa-slate/60 rounded-lg text-center">
            <p className="text-xs text-slate-400">Select an investigation case to access case-specific evidence workflows.</p>
          </div>
        )}
      </div>

      {/* Footer System Status */}
      <div className="p-4 border-t border-evidexa-slate/80 bg-evidexa-midnight/50">
        <div className="flex items-center gap-2 text-xs text-emerald-400">
          <ShieldCheck className="w-4 h-4 text-emerald-400 shrink-0" />
          <span className="font-mono text-[11px] font-medium tracking-tight">EVIDEXA Core v0.1.0</span>
        </div>
        <p className="text-[10px] text-slate-400 font-mono mt-1">Deterministic & Cryptographic</p>
      </div>
    </aside>
  );
};
