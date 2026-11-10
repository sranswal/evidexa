import React from "react";
import { Link } from "react-router-dom";
import { Download, Eye, FileText, Copy, Check } from "lucide-react";
import { StatusBadge } from "../ui/Badge";
import { Button } from "../ui/Button";
import type { DocumentItem } from "../../types/api";

export interface DocumentTableProps {
  caseId: string;
  documents: DocumentItem[];
  onSelectDocument: (doc: DocumentItem) => void;
}

export const DocumentTable: React.FC<DocumentTableProps> = ({
  caseId,
  documents,
  onSelectDocument,
}) => {
  const [copiedId, setCopiedId] = React.useState<string | null>(null);

  const handleCopyDigest = (e: React.MouseEvent, sha256: string, id: string) => {
    e.stopPropagation();
    navigator.clipboard.writeText(sha256);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 2000);
  };

  return (
    <div className="overflow-x-auto rounded-lg border border-evidexa-slate bg-evidexa-charcoal shadow-card">
      <table className="w-full text-left text-xs">
        <thead>
          <tr className="border-b border-evidexa-slate bg-evidexa-midnight/80 text-slate-400 font-mono">
            <th className="py-3 px-4 font-semibold uppercase tracking-wider">Document / Identity</th>
            <th className="py-3 px-4 font-semibold uppercase tracking-wider">SHA-256 Digest</th>
            <th className="py-3 px-4 font-semibold uppercase tracking-wider">Format & Size</th>
            <th className="py-3 px-4 font-semibold uppercase tracking-wider">Ingestion Status</th>
            <th className="py-3 px-4 font-semibold uppercase tracking-wider">Ingested Date</th>
            <th className="py-3 px-4 font-semibold uppercase tracking-wider text-right">Actions</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-evidexa-slate/50">
          {documents.map((doc) => {
            const isCopied = copiedId === doc.id;
            const isDuplicate = Boolean(doc.metadata?.duplicate_of_document_id);

            return (
              <tr
                key={doc.id}
                onClick={() => onSelectDocument(doc)}
                className="hover:bg-slate-800/40 cursor-pointer transition-colors group"
              >
                {/* Filename & Document ID */}
                <td className="py-3.5 px-4 max-w-[220px]">
                  <div className="flex items-center gap-2.5 truncate">
                    <FileText className="w-4 h-4 text-evidexa-cyan shrink-0" />
                    <div className="truncate">
                      <p
                        className="font-semibold text-slate-100 group-hover:text-evidexa-aqua transition-colors truncate"
                        title={doc.original_filename}
                      >
                        {doc.original_filename}
                      </p>
                      <span className="font-mono text-[10px] text-slate-400 truncate block">
                        {doc.id}
                      </span>
                    </div>
                  </div>
                  {isDuplicate && (
                    <span className="inline-block mt-1 text-[9px] font-mono px-1.5 py-0.2 rounded bg-amber-950/80 text-amber-300 border border-amber-600/50">
                      Duplicate of prior submission
                    </span>
                  )}
                </td>

                {/* SHA-256 Digest */}
                <td className="py-3.5 px-4">
                  <div className="flex items-center gap-1.5 font-mono text-[11px] text-slate-300">
                    <span title={doc.sha256}>
                      {doc.sha256.slice(0, 8)}…{doc.sha256.slice(-8)}
                    </span>
                    <button
                      onClick={(e) => handleCopyDigest(e, doc.sha256, doc.id)}
                      className="text-slate-400 hover:text-white p-1 rounded hover:bg-slate-700/60 transition-colors"
                      title="Copy full 64-char SHA-256 digest"
                    >
                      {isCopied ? (
                        <Check className="w-3.5 h-3.5 text-emerald-400" />
                      ) : (
                        <Copy className="w-3.5 h-3.5" />
                      )}
                    </button>
                  </div>
                </td>

                {/* Format & Size */}
                <td className="py-3.5 px-4 font-mono text-slate-300">
                  <span className="block">{doc.file_extension.toUpperCase().replace(".", "") || "FILE"}</span>
                  <span className="text-[11px] text-slate-400">
                    {(doc.file_size_bytes / 1024).toFixed(1)} KB
                  </span>
                </td>

                {/* Ingestion Status */}
                <td className="py-3.5 px-4">
                  <StatusBadge status={doc.ingestion_status} type="ingestion" />
                </td>

                {/* Ingested Date */}
                <td className="py-3.5 px-4 font-mono text-slate-400 text-[11px]">
                  {new Date(doc.created_at).toLocaleDateString()}{" "}
                  <span className="text-slate-500">{new Date(doc.created_at).toLocaleTimeString()}</span>
                </td>

                {/* Actions */}
                <td className="py-3.5 px-4 text-right">
                  <div
                    className="inline-flex items-center gap-1.5"
                    onClick={(e) => e.stopPropagation()}
                  >
                    <Link
                      to={`/cases/${caseId}/documents/${doc.id}/examine`}
                      className="inline-flex items-center px-2 py-1 text-xs font-medium rounded-md bg-brand-cyan/15 border border-brand-cyan/40 text-brand-cyan hover:bg-brand-cyan hover:text-brand-midnight transition-colors"
                      title="Open Document Forensic Viewer"
                    >
                      <FileText className="w-3.5 h-3.5 mr-1" />
                      Examine
                    </Link>
                    <Button
                      variant="secondary"
                      size="sm"
                      onClick={() => onSelectDocument(doc)}
                      className="px-2 py-1 text-xs"
                    >
                      <Eye className="w-3.5 h-3.5 mr-1" />
                      Inspect
                    </Button>
                    <a
                      href={`/api/v1/cases/${caseId}/documents/${doc.id}/download`}
                      download={doc.original_filename}
                      className="p-1.5 rounded-md hover:bg-slate-700 text-slate-400 hover:text-white transition-colors"
                      title="Download original file"
                    >
                      <Download className="w-3.5 h-3.5" />
                    </a>
                  </div>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
};
