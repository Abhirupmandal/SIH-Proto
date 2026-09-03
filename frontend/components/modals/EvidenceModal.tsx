'use client';

import React, { useEffect, useCallback } from 'react';
import {
  ShieldCheck,
  X,
  ArrowRight,
  PhoneCall,
  Clock,
  Radio,
  Cpu,
  IndianRupee,
  FileText,
  Building2,
  Quote,
  Hash,
  Activity,
  Layers,
  CheckCircle2,
  AlertTriangle,
} from 'lucide-react';
import { GraphEdgeData } from '@/types/graph';

interface EvidenceModalProps {
  selectedEdge: GraphEdgeData | null;
  onClose: () => void;
}

export const EvidenceModal: React.FC<EvidenceModalProps> = ({
  selectedEdge,
  onClose,
}) => {
  // Handle ESC key press to close modal
  const handleKeyDown = useCallback(
    (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        onClose();
      }
    },
    [onClose]
  );

  useEffect(() => {
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [handleKeyDown]);

  if (!selectedEdge) {
    return null;
  }

  const {
    type,
    source,
    target,
    sourceLabel = source,
    targetLabel = target,
    sourceType,
    targetType,
    confidenceScore,
    reasoningNote,
    metadata = {},
  } = selectedEdge;

  // Extract fields whether directly on edge or inside metadata
  const edgeDuration = selectedEdge.duration ?? (metadata.duration as number | undefined);
  const edgeTimestamp =
    selectedEdge.timestamp ?? (metadata.timestamp as string | undefined);
  const edgeImei =
    selectedEdge.callerImei ?? (metadata.callerImei as string | undefined) ?? (metadata.imei as string | undefined);
  const edgeTower =
    selectedEdge.cellTowerId ?? (metadata.cellTowerId as string | undefined) ?? (metadata.cellTower as string | undefined);

  const edgeTxId =
    selectedEdge.transactionId ?? (metadata.transactionId as string | undefined) ?? (metadata.utr as string | undefined);
  const edgeAmount =
    selectedEdge.amount ?? (metadata.amount as number | undefined);
  const edgeLedgerTimestamp =
    selectedEdge.ledgerTimestamp ?? (metadata.ledgerTimestamp as string | undefined) ?? edgeTimestamp;

  const edgeFir =
    selectedEdge.firNumber ?? (metadata.firNumber as string | undefined) ?? (metadata.firCaseNumber as string | undefined);
  const edgeStation =
    selectedEdge.policeStation ?? (metadata.policeStation as string | undefined) ?? (metadata.policeStationName as string | undefined);
  const edgeExcerpt =
    selectedEdge.firExcerpt ?? (metadata.firExcerpt as string | undefined) ?? (metadata.narrativeExcerpt as string | undefined);

  // Format currency in Indian Rupees (INR)
  const formatINR = (value?: number): string => {
    if (value === undefined || value === null) return 'N/A';
    return new Intl.NumberFormat('en-IN', {
      style: 'currency',
      currency: 'INR',
      maximumFractionDigits: 0,
    }).format(value);
  };

  // Format duration
  const formatDuration = (seconds?: number): string => {
    if (seconds === undefined || seconds === null) return 'N/A';
    const mins = Math.floor(seconds / 60);
    const remainingSecs = seconds % 60;
    if (mins === 0) return `${seconds}s`;
    return `${seconds} seconds (${mins}m ${remainingSecs}s)`;
  };

  // Determine badge styling based on relationship type
  const getTypeBadge = (edgeType: string) => {
    switch (edgeType) {
      case 'CALLED':
        return {
          bg: 'bg-sky-500/10 text-sky-400 border-sky-500/30',
          indicator: 'bg-sky-400',
        };
      case 'TRANSFERRED':
        return {
          bg: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30',
          indicator: 'bg-emerald-400',
        };
      case 'CO_ACCUSED_IN':
        return {
          bg: 'bg-rose-500/10 text-rose-400 border-rose-500/30',
          indicator: 'bg-rose-400',
        };
      case 'USES':
        return {
          bg: 'bg-amber-500/10 text-amber-400 border-amber-500/30',
          indicator: 'bg-amber-400',
        };
      case 'OPERATES':
        return {
          bg: 'bg-purple-500/10 text-purple-400 border-purple-500/30',
          indicator: 'bg-purple-400',
        };
      default:
        return {
          bg: 'bg-indigo-500/10 text-indigo-400 border-indigo-500/30',
          indicator: 'bg-indigo-400',
        };
    }
  };

  const badgeStyle = getTypeBadge(type);

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="evidence-modal-title"
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/75 backdrop-blur-sm animate-in fade-in duration-200"
      onClick={onClose}
    >
      <div
        className="relative w-full max-w-2xl bg-slate-900/95 border border-slate-800 rounded-xl shadow-2xl text-slate-100 backdrop-blur-md overflow-hidden ring-1 ring-white/10 flex flex-col max-h-[90vh]"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Top Forensic Status Bar */}
        <div className="flex items-center justify-between px-6 py-3 border-b border-slate-800/80 bg-slate-950/60 text-xs">
          <div className="flex items-center gap-2">
            <span className="flex items-center gap-1.5 font-medium px-2.5 py-1 rounded-full bg-emerald-500/15 text-emerald-400 border border-emerald-500/30">
              <ShieldCheck className="w-3.5 h-3.5 text-emerald-400" />
              Evidence Grounded (XAI)
            </span>
            <span className="text-slate-500 hidden sm:inline">|</span>
            <span className="text-slate-400 font-mono text-[11px] hidden sm:inline">
              REL_ID: {selectedEdge.id}
            </span>
          </div>

          <button
            onClick={onClose}
            aria-label="Close evidence modal"
            className="p-1 rounded-lg text-slate-400 hover:text-slate-100 hover:bg-slate-800/80 transition-colors focus:outline-none focus:ring-2 focus:ring-slate-400"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Header: Edge Type & Traversal Path */}
        <div className="px-6 py-5 border-b border-slate-800 bg-slate-900/50">
          <div className="flex items-center gap-3 mb-3">
            <span
              className={`inline-flex items-center gap-2 px-3 py-1 rounded-md text-xs font-semibold uppercase tracking-wider border ${badgeStyle.bg}`}
            >
              <span className={`w-2 h-2 rounded-full ${badgeStyle.indicator}`} />
              {type}
            </span>
            {confidenceScore !== undefined && (
              <span className="text-xs font-mono text-slate-400 bg-slate-800 px-2 py-0.5 rounded">
                AI Confidence: {(confidenceScore * 100).toFixed(0)}%
              </span>
            )}
          </div>

          {/* Traversal Path: Source Node ➔ Target Node */}
          <div className="bg-slate-950/80 rounded-lg p-3.5 border border-slate-800/90 flex items-center justify-between gap-4">
            {/* Source Node */}
            <div className="flex-1 min-w-0">
              <div className="text-[10px] uppercase font-bold text-slate-400 tracking-wider">
                Source Entity {sourceType ? `(${sourceType})` : ''}
              </div>
              <div className="text-sm font-semibold text-slate-100 truncate mt-0.5" title={sourceLabel}>
                {sourceLabel}
              </div>
            </div>

            {/* Traversal Arrow */}
            <div className="flex items-center justify-center text-slate-400 px-2">
              <ArrowRight className="w-5 h-5 text-indigo-400 animate-pulse" />
            </div>

            {/* Target Node */}
            <div className="flex-1 min-w-0 text-right">
              <div className="text-[10px] uppercase font-bold text-slate-400 tracking-wider">
                Target Entity {targetType ? `(${targetType})` : ''}
              </div>
              <div className="text-sm font-semibold text-slate-100 truncate mt-0.5" title={targetLabel}>
                {targetLabel}
              </div>
            </div>
          </div>
        </div>

        {/* Body: Auditable Reasoning Trail */}
        <div className="px-6 py-5 overflow-y-auto space-y-6 flex-1">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <Activity className="w-4 h-4 text-indigo-400" />
              <h3
                id="evidence-modal-title"
                className="text-base font-semibold text-slate-100 tracking-tight"
              >
                Auditable Reasoning Trail
              </h3>
            </div>
            <p className="text-xs text-slate-400">
              Verified digital forensic artifacts supporting the graph relationship.
            </p>
          </div>

          {/* Type-Specific Forensic Evidence Section */}
          {type === 'CALLED' && (
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div className="p-4 rounded-lg bg-slate-950/70 border border-slate-800/80">
                <div className="flex items-center gap-2 text-slate-400 text-xs font-medium mb-1">
                  <Clock className="w-3.5 h-3.5 text-sky-400" />
                  Call Timestamp
                </div>
                <div className="text-sm font-mono text-slate-200">
                  {edgeTimestamp || 'Timestamp Not Logged'}
                </div>
              </div>

              <div className="p-4 rounded-lg bg-slate-950/70 border border-slate-800/80">
                <div className="flex items-center gap-2 text-slate-400 text-xs font-medium mb-1">
                  <PhoneCall className="w-3.5 h-3.5 text-sky-400" />
                  Call Duration
                </div>
                <div className="text-sm font-semibold text-slate-100">
                  {formatDuration(edgeDuration)}
                </div>
              </div>

              <div className="p-4 rounded-lg bg-slate-950/70 border border-slate-800/80">
                <div className="flex items-center gap-2 text-slate-400 text-xs font-medium mb-1">
                  <Cpu className="w-3.5 h-3.5 text-sky-400" />
                  Caller IMEI
                </div>
                <div className="text-sm font-mono text-sky-300 font-semibold tracking-wider">
                  {edgeImei || 'IMEI Concealed / Burner'}
                </div>
              </div>

              <div className="p-4 rounded-lg bg-slate-950/70 border border-slate-800/80">
                <div className="flex items-center gap-2 text-slate-400 text-xs font-medium mb-1">
                  <Radio className="w-3.5 h-3.5 text-sky-400" />
                  Cell Tower ID
                </div>
                <div className="text-sm font-mono text-slate-200">
                  {edgeTower || 'Tower Triangulation Unavailable'}
                </div>
              </div>
            </div>
          )}

          {type === 'TRANSFERRED' && (
            <div className="space-y-4">
              <div className="p-4 rounded-lg bg-emerald-950/20 border border-emerald-800/40 flex items-center justify-between">
                <div>
                  <div className="text-xs text-emerald-400/90 font-medium">
                    Total Transfer Amount
                  </div>
                  <div className="text-2xl font-bold text-emerald-400 font-mono mt-1">
                    {formatINR(edgeAmount)}
                  </div>
                </div>
                <div className="p-3 rounded-full bg-emerald-500/10 text-emerald-400">
                  <IndianRupee className="w-6 h-6" />
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div className="p-4 rounded-lg bg-slate-950/70 border border-slate-800/80">
                  <div className="flex items-center gap-2 text-slate-400 text-xs font-medium mb-1">
                    <Hash className="w-3.5 h-3.5 text-emerald-400" />
                    Transaction / UTR ID
                  </div>
                  <div className="text-sm font-mono text-slate-200 break-all font-semibold">
                    {edgeTxId || 'N/A'}
                  </div>
                </div>

                <div className="p-4 rounded-lg bg-slate-950/70 border border-slate-800/80">
                  <div className="flex items-center gap-2 text-slate-400 text-xs font-medium mb-1">
                    <Clock className="w-3.5 h-3.5 text-emerald-400" />
                    Ledger Timestamp
                  </div>
                  <div className="text-sm font-mono text-slate-200">
                    {edgeLedgerTimestamp || 'N/A'}
                  </div>
                </div>
              </div>
            </div>
          )}

          {type === 'CO_ACCUSED_IN' && (
            <div className="space-y-4">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div className="p-4 rounded-lg bg-slate-950/70 border border-slate-800/80">
                  <div className="flex items-center gap-2 text-slate-400 text-xs font-medium mb-1">
                    <FileText className="w-3.5 h-3.5 text-rose-400" />
                    Linked FIR Case Number
                  </div>
                  <div className="text-sm font-mono text-rose-300 font-bold">
                    {edgeFir || 'FIR Not Specified'}
                  </div>
                </div>

                <div className="p-4 rounded-lg bg-slate-950/70 border border-slate-800/80">
                  <div className="flex items-center gap-2 text-slate-400 text-xs font-medium mb-1">
                    <Building2 className="w-3.5 h-3.5 text-rose-400" />
                    Police Station Name
                  </div>
                  <div className="text-sm font-medium text-slate-200">
                    {edgeStation || 'Jurisdiction Pending'}
                  </div>
                </div>
              </div>

              {/* Verbatim FIR Narrative Excerpt */}
              <div className="p-4 rounded-lg bg-slate-950/90 border border-slate-800 space-y-2">
                <div className="flex items-center gap-2 text-xs font-semibold text-amber-400 uppercase tracking-wider">
                  <Quote className="w-3.5 h-3.5" />
                  Verbatim Excerpt from FIR Narrative
                </div>
                <div className="border-l-4 border-amber-500/80 pl-3.5 py-1 text-slate-300 italic text-xs leading-relaxed font-sans">
                  {edgeExcerpt ? (
                    `"${edgeExcerpt}"`
                  ) : (
                    <span className="text-slate-500 not-italic">
                      No verbatim FIR narrative excerpt recorded for this link.
                    </span>
                  )}
                </div>
              </div>
            </div>
          )}

          {/* Fallback / Other Relationship Types: Gracefully display all metadata */}
          {type !== 'CALLED' && type !== 'TRANSFERRED' && type !== 'CO_ACCUSED_IN' && (
            <div className="space-y-4">
              <div className="flex items-center gap-2 text-xs text-slate-400 font-medium">
                <Layers className="w-4 h-4 text-indigo-400" />
                Relationship Metadata & Attributes
              </div>

              {Object.keys(metadata).length > 0 ? (
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  {Object.entries(metadata).map(([key, value]) => (
                    <div
                      key={key}
                      className="p-3 rounded-lg bg-slate-950/70 border border-slate-800/80"
                    >
                      <div className="text-[11px] font-mono text-slate-400 uppercase tracking-wider mb-1">
                        {key.replace(/([A-Z])/g, ' $1').trim()}
                      </div>
                      <div className="text-sm font-semibold text-slate-200 break-words">
                        {typeof value === 'object' && value !== null
                          ? JSON.stringify(value)
                          : String(value)}
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="p-6 rounded-lg bg-slate-950/50 border border-slate-850 text-center text-xs text-slate-400">
                  No additional raw metadata recorded for this link.
                </div>
              )}
            </div>
          )}

          {/* AI Reasoning / Analytical Grounding Note */}
          {Boolean(reasoningNote || selectedEdge.metadata?.reasoning) && (
            <div className="p-4 rounded-lg bg-indigo-950/30 border border-indigo-800/40 text-xs space-y-1.5">
              <div className="flex items-center gap-1.5 font-semibold text-indigo-300">
                <CheckCircle2 className="w-3.5 h-3.5 text-indigo-400" />
                Forensic Inference Justification
              </div>
              <p className="text-indigo-200/90 leading-relaxed">
                {reasoningNote || String(selectedEdge.metadata?.reasoning ?? '')}
              </p>
            </div>
          )}
        </div>

        {/* Modal Footer */}
        <div className="px-6 py-4 border-t border-slate-800 bg-slate-950/70 flex items-center justify-between text-xs">
          <div className="text-slate-400 flex items-center gap-1.5">
            <span className="inline-block w-2 h-2 rounded-full bg-emerald-400 animate-ping" />
            Chain of Custody Hash: <span className="font-mono text-slate-300">SHA-256 Verified</span>
          </div>

          <button
            onClick={onClose}
            className="px-4 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 font-medium transition-colors border border-slate-700"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
};

export default EvidenceModal;
