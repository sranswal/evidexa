import React from "react";
import { Link, useLocation } from "react-router-dom";
import { ChevronRight, LogOut, Server, Shield, User as UserIcon } from "lucide-react";
import { useCaseContext } from "../../context/CaseContext";
import { useAuth } from "../../context/AuthContext";
import { StatusBadge } from "../ui/Badge";

export const Header: React.FC = () => {
  const location = useLocation();
  const { activeCase } = useCaseContext();
  const { user, logout } = useAuth();

  const getBreadcrumbs = () => {
    const parts = location.pathname.split("/").filter(Boolean);
    const crumbs: { label: string; to: string }[] = [{ label: "Cases", to: "/cases" }];

    if (parts[0] === "cases" && parts[1]) {
      const caseId = parts[1];
      crumbs.push({
        label: activeCase?.case_reference || caseId.slice(0, 8),
        to: `/cases/${caseId}/overview`,
      });

      if (parts[2]) {
        const screenName = parts[2].charAt(0).toUpperCase() + parts[2].slice(1);
        crumbs.push({
          label: screenName,
          to: location.pathname,
        });
      }
    }

    return crumbs;
  };

  const breadcrumbs = getBreadcrumbs();

  return (
    <header className="h-14 bg-evidexa-midnight/90 backdrop-blur border-b border-evidexa-slate px-6 flex items-center justify-between sticky top-0 z-20">
      {/* Breadcrumbs */}
      <nav className="flex items-center gap-2 text-sm" aria-label="Breadcrumb">
        {breadcrumbs.map((crumb, idx) => {
          const isLast = idx === breadcrumbs.length - 1;
          return (
            <React.Fragment key={crumb.to}>
              {idx > 0 && <ChevronRight className="w-3.5 h-3.5 text-slate-500" />}
              {isLast ? (
                <span className="font-semibold text-white tracking-wide">{crumb.label}</span>
              ) : (
                <Link to={crumb.to} className="text-slate-400 hover:text-evidexa-aqua transition-colors">
                  {crumb.label}
                </Link>
              )}
            </React.Fragment>
          );
        })}
      </nav>

      {/* Right System Indicators */}
      <div className="flex items-center gap-4 text-xs font-mono">
        {activeCase && (
          <div className="hidden sm:flex items-center gap-2">
            <span className="text-slate-400">Case State:</span>
            <StatusBadge status={activeCase.status} type="case" />
          </div>
        )}

        <div className="flex items-center gap-2 px-2.5 py-1 rounded bg-slate-900 border border-slate-700 text-slate-300">
          <Server className="w-3.5 h-3.5 text-emerald-400" />
          <span className="text-emerald-400 font-semibold">API ONLINE</span>
        </div>

        <div className="hidden md:flex items-center gap-1.5 px-2.5 py-1 rounded bg-evidexa-charcoal border border-evidexa-slate text-slate-400">
          <Shield className="w-3.5 h-3.5 text-evidexa-cyan" />
          <span>ZERO-RETENTION / AUDITED</span>
        </div>

        {user && (
          <div className="flex items-center gap-3 border-l border-zinc-800 pl-4 font-sans">
            <div className="flex items-center gap-2">
              <div className="flex h-7 w-7 items-center justify-center rounded-full bg-orange-950/60 border border-orange-500/40 text-orange-400 text-xs font-bold">
                <UserIcon className="w-3.5 h-3.5" />
              </div>
              <div className="hidden lg:flex flex-col text-left">
                <span className="text-xs font-semibold text-zinc-100 leading-tight">{user.full_name}</span>
                <span className="text-[10px] text-orange-400 font-mono leading-none">{user.system_role}</span>
              </div>
            </div>
            <button
              onClick={() => void logout()}
              title="Sign Out"
              className="flex items-center gap-1.5 rounded bg-zinc-900/80 px-2 py-1 text-xs text-zinc-300 hover:bg-red-950/60 hover:text-red-300 hover:border-red-500/40 border border-zinc-800 transition"
            >
              <LogOut className="w-3 h-3" />
              <span className="hidden sm:inline">Sign Out</span>
            </button>
          </div>
        )}
      </div>
    </header>
  );
};

