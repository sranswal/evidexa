import React from "react";
import { Link } from "react-router-dom";
import { ExternalLink, FileText, ShieldAlert, Network, Layers } from "lucide-react";
import type { EvidenceCitation } from "../../types/api";

interface CitationCardProps {
  citation: EvidenceCitation;
}

export const CitationCard: React.FC<CitationCardProps> = ({ citation }) => {
  const getSubsystemIcon = (subsystem: string) => {
    switch (subsystem.toLowerCase()) {
      case "forensics":
        return <ShieldAlert className="w-3.5 h-3.5 text-rose-400" />;
      case "consistency":
        return <Layers className="w-3.5 h-3.5 text-amber-400" />;
      case "relationships":
      case "entity_resolution":
        return <Network className="w-3.5 h-3.5 text-evidexa-cyan" />;
      default:
        return <FileText className="w-3.5 h-3.5 text-slate-300" />;
    }
  };

  const getSubsystemBadgeColor = (subsystem: string) => {
    switch (subsystem.toLowerCase()) {
      case "forensics":
        return "bg-rose-950/60 text-rose-300 border-rose-800";
      case "consistency":
        return "bg-amber-950/60 text-amber-300 border-amber-800";
      case "relationships":
      case "entity_resolution":
        return "bg-cyan-950/60 text-cyan-300 border-cyan-800";
      default:
        return "bg-slate-800 text-slate-300 border-slate-700";
    }
  };

  const cardContent = (
    <div className="p-3 bg-evidexa-midnight/90 border border-evidexa-slate rounded-lg hover:border-evidexa-cyan/60 transition-all group">
      <div className="flex items-center justify-between gap-2 mb-1.5">
        <div className="flex items-center gap-1.5 min-w-0">
          <span className="px-1.5 py-0.5 text-[10px] font-mono font-bold rounded bg-evidexa-slate text-evidexa-cyan shrink-0">
            {citation.citation_id}
          </span>
          <span
            className={`px-1.5 py-0.5 text-[10px] font-mono uppercase tracking-wider rounded border flex items-center gap-1 shrink-0 ${getSubsystemBadgeColor(
              citation.source_subsystem
            )}`}
          >
            {getSubsystemIcon(citation.source_subsystem)}
            {citation.source_subsystem}
          </span>
          {citation.page_number && (
            <span className="text-[10px] font-mono text-slate-400 bg-slate-900/60 px-1.5 py-0.5 rounded border border-slate-800 shrink-0">
              p. {citation.page_number}
            </span>
          )}
        </div>
        {citation.target_route && (
          <ExternalLink className="w-3.5 h-3.5 text-slate-400 group-hover:text-evidexa-cyan transition-colors shrink-0" />
        )}
      </div>

      {citation.document_title && (
        <p className="text-xs font-semibold text-slate-200 truncate mb-1" title={citation.document_title}>
          {citation.document_title}
        </p>
      )}

      {citation.relevant_text && (
        <p className="text-xs text-slate-400 line-clamp-2 italic font-mono bg-slate-950/50 p-1.5 rounded border border-slate-900">
          "{citation.relevant_text}"
        </p>
      )}

      <div className="mt-2 flex flex-wrap gap-1 text-[10px] font-mono text-slate-400">
        {citation.document_id && (
          <span className="text-slate-400" title={`Document ID: ${citation.document_id}`}>
            Doc: {citation.document_id.slice(0, 8)}…
          </span>
        )}
        {citation.finding_id && (
          <span className="text-amber-400/90" title={`Finding ID: ${citation.finding_id}`}>
            Finding: {citation.finding_id.slice(0, 8)}…
          </span>
        )}
        {citation.relationship_id && (
          <span className="text-cyan-400/90" title={`Relationship ID: ${citation.relationship_id}`}>
            Rel: {citation.relationship_id.slice(0, 8)}…
          </span>
        )}
      </div>
    </div>
  );

  if (citation.target_route) {
    return (
      <Link to={citation.target_route} className="block focus:outline-none focus:ring-1 focus:ring-evidexa-cyan rounded-lg">
        {cardContent}
      </Link>
    );
  }

  return cardContent;
};

