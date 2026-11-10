import React from 'react';
import { ChevronLeft, ChevronRight, FileText, ShieldAlert } from 'lucide-react';
import type { ExtractedPageText, ForensicFinding } from '../../types/api';

interface PageThumbnailStripProps {
  totalPages: number;
  currentPage: number;
  onPageSelect: (page: number) => void;
  ocrPages?: ExtractedPageText[];
  findings?: ForensicFinding[];
  collapsed: boolean;
  onToggleCollapse: () => void;
}

export const PageThumbnailStrip: React.FC<PageThumbnailStripProps> = ({
  totalPages,
  currentPage,
  onPageSelect,
  ocrPages = [],
  findings = [],
  collapsed,
  onToggleCollapse,
}) => {
  // Count tokens and findings per page
  const pageStats = React.useMemo(() => {
    const stats = new Map<number, { tokensCount: number; findingsCount: number }>();

    for (let p = 1; p <= totalPages; p++) {
      stats.set(p, { tokensCount: 0, findingsCount: 0 });
    }

    for (const page of ocrPages) {
      const cur = stats.get(page.page_number) || { tokensCount: 0, findingsCount: 0 };
      cur.tokensCount = page.tokens?.length || 0;
      stats.set(page.page_number, cur);
    }

    for (const f of findings) {
      if (f.page_number) {
        const cur = stats.get(f.page_number) || { tokensCount: 0, findingsCount: 0 };
        cur.findingsCount++;
        stats.set(f.page_number, cur);
      }
    }

    return stats;
  }, [totalPages, ocrPages, findings]);

  if (collapsed) {
    return (
      <div className="w-10 bg-brand-charcoal border-r border-brand-slate flex flex-col items-center py-3">
        <button
          type="button"
          onClick={onToggleCollapse}
          className="p-1.5 text-brand-slate-light hover:text-white rounded hover:bg-brand-slate/40 transition-colors"
          title="Expand Page Thumbnails"
        >
          <ChevronRight className="w-4 h-4" />
        </button>
        <div className="mt-4 writing-vertical-rl text-[11px] font-mono text-brand-slate-light tracking-wider">
          PAGE {currentPage} / {totalPages}
        </div>
      </div>
    );
  }

  return (
    <div className="w-48 bg-brand-charcoal border-r border-brand-slate flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center justify-between p-3 border-b border-brand-slate">
        <span className="text-xs font-semibold text-white uppercase tracking-wider">
          Pages ({totalPages})
        </span>
        <button
          type="button"
          onClick={onToggleCollapse}
          className="p-1 text-brand-slate-light hover:text-white rounded hover:bg-brand-slate/40 transition-colors"
          title="Collapse Thumbnails"
        >
          <ChevronLeft className="w-4 h-4" />
        </button>
      </div>

      {/* Pages List */}
      <div className="flex-1 overflow-y-auto p-2.5 space-y-2">
        {Array.from({ length: totalPages }, (_, i) => i + 1).map((pageNum) => {
          const isCurrent = pageNum === currentPage;
          const stat = pageStats.get(pageNum);

          return (
            <button
              key={pageNum}
              type="button"
              onClick={() => onPageSelect(pageNum)}
              className={`w-full p-2.5 rounded-lg border text-left transition-all flex flex-col gap-1.5 ${
                isCurrent
                  ? 'bg-brand-midnight border-brand-cyan shadow-[0_0_10px_rgba(0,229,255,0.25)]'
                  : 'bg-brand-midnight/50 border-brand-slate/50 hover:border-brand-slate hover:bg-brand-midnight'
              }`}
            >
              <div className="flex items-center justify-between">
                <span
                  className={`text-xs font-mono font-medium ${
                    isCurrent ? 'text-brand-cyan' : 'text-slate-300'
                  }`}
                >
                  Page {pageNum}
                </span>

                {isCurrent && (
                  <span className="w-1.5 h-1.5 rounded-full bg-brand-cyan animate-pulse" />
                )}
              </div>

              {/* Page Indicator Badges */}
              <div className="flex items-center gap-2 text-[10px] text-brand-slate-light">
                {stat?.tokensCount ? (
                  <span className="inline-flex items-center gap-0.5 text-brand-slate-light" title={`${stat.tokensCount} OCR tokens`}>
                    <FileText className="w-2.5 h-2.5 text-brand-cyan" />
                    <span>{stat.tokensCount}</span>
                  </span>
                ) : null}

                {stat?.findingsCount ? (
                  <span className="inline-flex items-center gap-0.5 text-amber-300" title={`${stat.findingsCount} findings`}>
                    <ShieldAlert className="w-2.5 h-2.5 text-amber-400" />
                    <span>{stat.findingsCount}</span>
                  </span>
                ) : null}
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
};

