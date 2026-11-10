import { memo } from 'react';
import {
  BaseEdge,
  EdgeLabelRenderer,
  getBezierPath,
  EdgeProps,
} from '@xyflow/react';
import type { GraphRelationshipStatus } from '../../types/api';
import type { EvidenceEdgeData } from './layout';

interface EdgeStatusStyle {
  stroke: string;
  strokeDasharray?: string;
  labelBg: string;
  labelText: string;
  labelBorder: string;
}

const STATUS_STYLES: Record<GraphRelationshipStatus, EdgeStatusStyle> = {
  CONFIRMED: {
    stroke: '#00E5FF', // Electric cyan
    labelBg: 'bg-brand-midnight/90',
    labelText: 'text-brand-cyan',
    labelBorder: 'border-brand-cyan/40',
  },
  CANDIDATE: {
    stroke: '#F59E0B', // Amber
    strokeDasharray: '6 4',
    labelBg: 'bg-amber-950/90',
    labelText: 'text-amber-300',
    labelBorder: 'border-amber-500/50',
  },
  CONTRADICTED: {
    stroke: '#EF4444', // Crimson
    strokeDasharray: '6 4',
    labelBg: 'bg-red-950/90',
    labelText: 'text-red-300',
    labelBorder: 'border-red-500/50',
  },
  UNRESOLVED: {
    stroke: '#94A3B8', // Slate
    strokeDasharray: '3 3',
    labelBg: 'bg-brand-midnight/90',
    labelText: 'text-slate-400',
    labelBorder: 'border-brand-slate',
  },
  REJECTED: {
    stroke: '#64748B', // Muted slate
    strokeDasharray: '2 4',
    labelBg: 'bg-brand-midnight/90',
    labelText: 'text-slate-500 line-through',
    labelBorder: 'border-brand-slate/40',
  },
};

export const EvidenceGraphEdge = memo(
  ({
    id,
    sourceX,
    sourceY,
    targetX,
    targetY,
    sourcePosition,
    targetPosition,
    data,
    selected,
  }: EdgeProps) => {
    const edgeData = (data || {}) as unknown as EvidenceEdgeData;
    const raw = (edgeData?.rawEdge || edgeData || {}) as any;
    const status: GraphRelationshipStatus = (raw?.status as GraphRelationshipStatus) || 'CONFIRMED';
    const statusStyle = STATUS_STYLES[status] || STATUS_STYLES.CONFIRMED;

    const isHighlighted = Boolean(edgeData?.isPathHighlighted || raw?.isHighlighted);

    const [edgePath, labelX, labelY] = getBezierPath({
      sourceX,
      sourceY,
      sourcePosition,
      targetX,
      targetY,
      targetPosition,
    });

    const strokeColor = isHighlighted ? '#F59E0B' : selected ? '#00E5FF' : statusStyle.stroke;
    const strokeWidth = isHighlighted ? 3.5 : selected ? 3 : 1.75;

    const predicate = raw?.predicate || 'CONNECTED_TO';

    return (
      <>
        {/* Glow halo when selected or path-highlighted */}
        {(selected || isHighlighted) && (
          <path
            d={edgePath}
            fill="none"
            stroke={isHighlighted ? '#F59E0B' : '#00E5FF'}
            strokeWidth={8}
            strokeOpacity={0.3}
            className="pointer-events-none"
          />
        )}

        {/* Base directed edge path */}
        <BaseEdge
          id={id}
          path={edgePath}
          style={{
            stroke: strokeColor,
            strokeWidth,
            strokeDasharray: statusStyle.strokeDasharray,
          }}
        />

        {/* Edge Predicate Label */}
        <EdgeLabelRenderer>
          <div
            style={{
              position: 'absolute',
              transform: `translate(-50%, -50%) translate(${labelX}px,${labelY}px)`,
              pointerEvents: 'all',
            }}
            className="nodrag nopan"
          >
            <div
              className={`px-1.5 py-0.5 rounded text-[9px] font-mono border backdrop-blur-sm shadow-md transition-all flex items-center gap-1 select-none ${
                selected
                  ? 'bg-brand-charcoal border-brand-cyan text-brand-cyan ring-1 ring-brand-cyan shadow-cyan-500/20'
                  : `${statusStyle.labelBg} ${statusStyle.labelBorder} ${statusStyle.labelText}`
              }`}
              title={`Predicate: ${predicate} | Status: ${status}${
                raw?.score !== null && raw?.score !== undefined ? ` | Score: ${raw.score}` : ''
              }`}
            >
              <span>{predicate.replace(/_/g, ' ')}</span>
              {status !== 'CONFIRMED' && (
                <span className="text-[8px] uppercase opacity-75 font-bold">({status})</span>
              )}
            </div>
          </div>
        </EdgeLabelRenderer>
      </>
    );
  }
);

EvidenceGraphEdge.displayName = 'EvidenceGraphEdge';
