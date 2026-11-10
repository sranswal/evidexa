import React, { memo } from 'react';
import { Handle, Position, NodeProps } from '@xyflow/react';
import {
  FolderOpen,
  FileText,
  FileSearch,
  ShieldAlert,
  AlertTriangle,
  Building2,
  User,
  Landmark,
  Receipt,
  HelpCircle,
  Clock,
  Layers,
} from 'lucide-react';
import type { GraphNodeType } from '../../types/api';
import type { EvidenceNodeData } from './layout';
import { maskSensitiveValue, isSensitiveField } from '../../utils/masking';

interface NodeStyleConfig {
  icon: React.ComponentType<{ className?: string }>;
  borderClass: string;
  badgeBg: string;
  badgeText: string;
  headerColor: string;
}

const NODE_STYLES: Record<string, NodeStyleConfig> = {
  CASE: {
    icon: FolderOpen,
    borderClass: 'border-purple-500/70',
    badgeBg: 'bg-purple-500/15',
    badgeText: 'text-purple-300 border-purple-500/30',
    headerColor: 'text-purple-400',
  },
  DOCUMENT: {
    icon: FileText,
    borderClass: 'border-cyan-500/70',
    badgeBg: 'bg-cyan-500/15',
    badgeText: 'text-cyan-300 border-cyan-500/30',
    headerColor: 'text-cyan-400',
  },
  EVIDENCE: {
    icon: FileSearch,
    borderClass: 'border-blue-500/70',
    badgeBg: 'bg-blue-500/15',
    badgeText: 'text-blue-300 border-blue-500/30',
    headerColor: 'text-blue-400',
  },
  FORENSIC_FINDING: {
    icon: ShieldAlert,
    borderClass: 'border-rose-500/70',
    badgeBg: 'bg-rose-500/15',
    badgeText: 'text-rose-300 border-rose-500/30',
    headerColor: 'text-rose-400',
  },
  CONSISTENCY_FINDING: {
    icon: AlertTriangle,
    borderClass: 'border-amber-500/70',
    badgeBg: 'bg-amber-500/15',
    badgeText: 'text-amber-300 border-amber-500/30',
    headerColor: 'text-amber-400',
  },
  ORGANIZATION: {
    icon: Building2,
    borderClass: 'border-teal-500/70',
    badgeBg: 'bg-teal-500/15',
    badgeText: 'text-teal-300 border-teal-500/30',
    headerColor: 'text-teal-400',
  },
  SUPPLIER: {
    icon: Building2,
    borderClass: 'border-teal-500/70',
    badgeBg: 'bg-teal-500/15',
    badgeText: 'text-teal-300 border-teal-500/30',
    headerColor: 'text-teal-400',
  },
  BUYER: {
    icon: Building2,
    borderClass: 'border-teal-500/70',
    badgeBg: 'bg-teal-500/15',
    badgeText: 'text-teal-300 border-teal-500/30',
    headerColor: 'text-teal-400',
  },
  MERCHANT: {
    icon: Building2,
    borderClass: 'border-teal-500/70',
    badgeBg: 'bg-teal-500/15',
    badgeText: 'text-teal-300 border-teal-500/30',
    headerColor: 'text-teal-400',
  },
  PERSON: {
    icon: User,
    borderClass: 'border-violet-500/70',
    badgeBg: 'bg-violet-500/15',
    badgeText: 'text-violet-300 border-violet-500/30',
    headerColor: 'text-violet-400',
  },
  BANK: {
    icon: Landmark,
    borderClass: 'border-emerald-500/70',
    badgeBg: 'bg-emerald-500/15',
    badgeText: 'text-emerald-300 border-emerald-500/30',
    headerColor: 'text-emerald-400',
  },
  ACCOUNT: {
    icon: Landmark,
    borderClass: 'border-emerald-500/70',
    badgeBg: 'bg-emerald-500/15',
    badgeText: 'text-emerald-300 border-emerald-500/30',
    headerColor: 'text-emerald-400',
  },
  INVOICE: {
    icon: Receipt,
    borderClass: 'border-orange-500/70',
    badgeBg: 'bg-orange-500/15',
    badgeText: 'text-orange-300 border-orange-500/30',
    headerColor: 'text-orange-400',
  },
  RECEIPT: {
    icon: Receipt,
    borderClass: 'border-orange-500/70',
    badgeBg: 'bg-orange-500/15',
    badgeText: 'text-orange-300 border-orange-500/30',
    headerColor: 'text-orange-400',
  },
  PURCHASE_ORDER: {
    icon: Receipt,
    borderClass: 'border-orange-500/70',
    badgeBg: 'bg-orange-500/15',
    badgeText: 'text-orange-300 border-orange-500/30',
    headerColor: 'text-orange-400',
  },
  BANK_TRANSACTION: {
    icon: Clock,
    borderClass: 'border-yellow-500/70',
    badgeBg: 'bg-yellow-500/15',
    badgeText: 'text-yellow-300 border-yellow-500/30',
    headerColor: 'text-yellow-400',
  },
};

function getNodeStyle(type: GraphNodeType | string): NodeStyleConfig {
  return (
    NODE_STYLES[type.toUpperCase()] || {
      icon: HelpCircle,
      borderClass: 'border-brand-slate',
      badgeBg: 'bg-brand-slate/20',
      badgeText: 'text-brand-slate-light border-brand-slate',
      headerColor: 'text-brand-slate-light',
    }
  );
}

export const EvidenceGraphNode = memo(({ data, selected }: NodeProps) => {
  const nodeData = (data || {}) as unknown as EvidenceNodeData;
  const raw = (nodeData.rawNode || nodeData || {}) as any;
  const nodeType: GraphNodeType = (raw.node_type || raw.nodeType || 'DOCUMENT') as GraphNodeType;
  const style = getNodeStyle(nodeType);
  const Icon = style.icon;

  const isHighlighted = Boolean(nodeData.isPathHighlighted || raw.isHighlighted);

  // Extract secondary summary indicator if available
  const secondaryDetail =
    raw.display_attributes?.document_type ||
    raw.display_attributes?.evidence_type ||
    raw.display_attributes?.severity ||
    raw.display_attributes?.rule_id ||
    raw.source_entity_type ||
    raw.category;

  const rawLabel = raw.label || '';
  const shouldMask =
    nodeType === 'ACCOUNT' ||
    isSensitiveField(nodeType) ||
    raw.properties?.is_sensitive === true;
  const displayLabel = shouldMask ? maskSensitiveValue(rawLabel) : rawLabel;

  const sourceId = String(raw.source_entity_id || raw.id || raw.nodeId || '');

  return (
    <div
      className={`relative w-[230px] rounded-lg p-2.5 transition-all select-none backdrop-blur-md ${isHighlighted
          ? 'bg-amber-950/80 border-2 border-amber-400 ring-4 ring-amber-400/20 shadow-[0_0_16px_rgba(251,191,36,0.5)] z-40'
          : selected
            ? 'bg-brand-charcoal border-2 border-brand-cyan ring-4 ring-brand-cyan/25 shadow-[0_0_18px_rgba(0,229,255,0.6)] z-30'
            : `bg-brand-charcoal/95 border ${style.borderClass} hover:border-brand-cyan/80 hover:shadow-lg z-10`
        }`}
    >
      {/* React Flow Connection Handles */}
      <Handle
        type="target"
        position={Position.Left}
        className="!w-2 !h-2 !bg-brand-cyan !border !border-brand-midnight !rounded-full"
      />
      <Handle
        type="source"
        position={Position.Right}
        className="!w-2 !h-2 !bg-brand-cyan !border !border-brand-midnight !rounded-full"
      />

      {/* Top Header: Category Icon & Type Badge */}
      <div className="flex items-center justify-between gap-1 mb-1.5">
        <div className="flex items-center gap-1.5 min-w-0">
          <Icon className={`w-3.5 h-3.5 shrink-0 ${style.headerColor}`} />
          <span className={`text-[10px] font-mono font-semibold uppercase tracking-wider truncate ${style.headerColor}`}>
            {nodeType.replace('_', ' ')}
          </span>
        </div>

        {secondaryDetail && (
          <span className={`px-1.5 py-0.5 rounded text-[9px] font-mono border truncate max-w-[95px] ${style.badgeBg} ${style.badgeText}`}>
            {String(secondaryDetail).replace('_', ' ')}
          </span>
        )}
      </div>

      {/* Main Node Label */}
      <div
        className="text-xs font-medium text-white line-clamp-2 leading-snug mb-1 font-sans"
        title={rawLabel}
      >
        {displayLabel}
      </div>

      {/* Footer Info: Page / Source / ID */}
      <div className="flex items-center justify-between text-[10px] text-brand-slate-light font-mono pt-1 border-t border-brand-slate/40">
        <span className="truncate max-w-[120px]" title={sourceId}>
          {sourceId ? `#${sourceId.slice(-6)}` : '-'}
        </span>

        {raw.provenance?.page_number ? (
          <span className="flex items-center gap-0.5 text-brand-cyan">
            <Layers className="w-2.5 h-2.5" />
            <span>p. {String(raw.provenance.page_number)}</span>
          </span>
        ) : (
          <span className="text-slate-500">{raw.source_entity_type || ''}</span>
        )}
      </div>
    </div>
  );
});

EvidenceGraphNode.displayName = 'EvidenceGraphNode';
