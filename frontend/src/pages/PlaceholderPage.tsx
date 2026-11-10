import React from "react";
import { useParams, Link } from "react-router-dom";
import { ArrowLeft, Clock, Hammer, ShieldAlert, FileText, Network, FileCheck2 } from "lucide-react";
import { Card } from "../components/ui/Card";
import { Button } from "../components/ui/Button";

interface PlaceholderConfig {
  title: string;
  phase: string;
  description: string;
  icon: React.ReactNode;
  capabilities: string[];
}

const CONFIGS: Record<string, PlaceholderConfig> = {
  documents: {
    title: "Document Ingestion & Optical Forensics",
    phase: "Phase 3B",
    description: "Multi-file document registry, drag-and-drop secure upload, byte-level inspection, PDF visual heatmap, and interactive OCR token overlay.",
    icon: <FileText className="w-10 h-10 text-evidexa-cyan" />,
    capabilities: [
      "Cryptographic SHA-256 integrity verification",
      "Interactive bounding box inspection",
      "PDF structural and optical forensics heatmap",
      "Structured field extraction table",
    ],
  },
  graph: {
    title: "Interactive Evidence Graph Canvas",
    phase: "Phase 3C",
    description: "Force-directed relational investigation canvas rendering document nodes, extracted entities, forensic anomalies, and cross-document edges.",
    icon: <Network className="w-10 h-10 text-purple-400" />,
    capabilities: [
      "Deterministic graph projection over authoritative database records",
      "Node clustering by document class and entity type",
      "Exploratory shortest path & circular flow analysis",
      "Evidentiary status edge filtering (Confirmed, Candidate, Contradicted)",
    ],
  },
  findings: {
    title: "Forensic Findings & Investigator Review",
    phase: "Phase 3D",
    description: "Deep-dive findings workbench with human review actions, rationale audit trail, rule-based filtering, and contradiction adjudication.",
    icon: <ShieldAlert className="w-10 h-10 text-orange-400" />,
    capabilities: [
      "Unified view of forensic rule flags and cross-document contradictions",
      "Append-only investigator review workflow (Confirm / Dismiss / Request Evidence)",
      "Strict separation between automated anomaly and fraud verdict",
      "Chronological review ledger with examiner attribution",
    ],
  },
  dossiers: {
    title: "Evidence Dossier Workbench & Export",
    phase: "Phase 3E",
    description: "Full 12-section dossier viewer, revision history, cryptographic sealing, and one-click PDF / JSON vector export.",
    icon: <FileCheck2 className="w-10 h-10 text-emerald-400" />,
    capabilities: [
      "Real-time rendering of all 12 analytical investigation sections",
      "Cryptographic SHA-256 seal computation and freeze",
      "High-fidelity vector PDF download with visual disclaimers",
      "Machine-readable JSON schema export for court or compliance ingest",
    ],
  },
};

export interface PlaceholderPageProps {
  moduleKey: "documents" | "graph" | "findings" | "dossiers";
}

export const PlaceholderPage: React.FC<PlaceholderPageProps> = ({ moduleKey }) => {
  const { caseId } = useParams<{ caseId?: string }>();
  const config = CONFIGS[moduleKey] || {
    title: "Investigation Module",
    phase: "Upcoming Phase",
    description: "This forensic workspace module is currently under active development.",
    icon: <Hammer className="w-10 h-10 text-slate-400" />,
    capabilities: [],
  };

  return (
    <div className="max-w-3xl mx-auto py-8 space-y-6">
      <Link
        to={caseId ? `/cases/${caseId}/overview` : "/cases"}
        className="inline-flex items-center gap-2 text-xs font-mono text-evidexa-aqua hover:underline"
      >
        <ArrowLeft className="w-3.5 h-3.5" />
        Return to Case Overview
      </Link>

      <Card className="p-8 text-center border-dashed border-evidexa-slate space-y-6">
        <div className="flex justify-center">
          <div className="p-4 bg-evidexa-midnight/80 border border-evidexa-slate rounded-2xl shadow-glow">
            {config.icon}
          </div>
        </div>

        <div className="space-y-2">
          <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-mono font-semibold bg-evidexa-slate/80 text-evidexa-cyan border border-evidexa-cyan/30">
            <Clock className="w-3.5 h-3.5" />
            <span>Scheduled for {config.phase}</span>
          </div>
          <h2 className="text-2xl font-bold text-white tracking-tight">{config.title}</h2>
          <p className="text-sm text-slate-300 max-w-xl mx-auto leading-relaxed">
            {config.description}
          </p>
        </div>

        {config.capabilities.length > 0 && (
          <div className="pt-6 border-t border-evidexa-slate/60 text-left max-w-lg mx-auto">
            <h4 className="text-xs font-mono uppercase tracking-wider text-slate-400 font-semibold mb-3">
              Planned Forensic Capabilities
            </h4>
            <ul className="space-y-2 text-xs text-slate-300">
              {config.capabilities.map((cap, i) => (
                <li key={i} className="flex items-center gap-2">
                  <span className="w-1.5 h-1.5 rounded-full bg-evidexa-cyan shrink-0" />
                  <span>{cap}</span>
                </li>
              ))}
            </ul>
          </div>
        )}

        <div className="pt-4 flex justify-center">
          <Link to={caseId ? `/cases/${caseId}/overview` : "/cases"}>
            <Button variant="secondary">Back to Case Overview</Button>
          </Link>
        </div>
      </Card>
    </div>
  );
};

