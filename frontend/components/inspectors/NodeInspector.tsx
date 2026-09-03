'use client';

import React from 'react';
import { GraphNodeData, GraphEdgeData } from '@/types/graph';
import {
  X,
  ShieldAlert,
  Car,
  Phone,
  Landmark,
  FileSpreadsheet,
  Building2,
  Radio,
  Share2,
  ArrowUpRight,
  User,
  Fingerprint,
} from 'lucide-react';

interface NodeInspectorProps {
  selectedNode: GraphNodeData | null;
  onClose: () => void;
  connectedEdges: GraphEdgeData[];
  onSelectEdge?: (edge: GraphEdgeData) => void;
}

export const NodeInspector: React.FC<NodeInspectorProps> = ({
  selectedNode,
  onClose,
  connectedEdges,
  onSelectEdge,
}) => {
  if (!selectedNode) return null;

  const metadata = selectedNode.metadata || {};
  const aliases = (metadata.aliases as string[]) || [];
  const vehicles = (metadata.vehicles as string[]) || [];
  const towerIds = (metadata.tower_ids as string[]) || [];
  const soRelations = (metadata.so_relations as Array<{ child: string; father: string }>) || [];
  const psName = (metadata.ps_name as string) || undefined;
  const imei = (metadata.imei as string) || undefined;
  const evidenceSource = (metadata.evidence_source as string) || undefined;
  const textSnippet = (metadata.text_snippet as string) || undefined;

  const getNodeBadgeColor = (type: string) => {
    const t = (type || '').toUpperCase();
    if (t.includes('SUSPECT')) return 'bg-rose-500/20 text-rose-300 border-rose-500/40';
    if (t.includes('ACCOUNT') || t.includes('BANK')) return 'bg-emerald-500/20 text-emerald-300 border-emerald-500/40';
    if (t.includes('PHONE')) return 'bg-sky-500/20 text-sky-300 border-sky-500/40';
    if (t.includes('FIR') || t.includes('CASE')) return 'bg-amber-500/20 text-amber-300 border-amber-500/40';
    return 'bg-indigo-500/20 text-indigo-300 border-indigo-500/40';
  };

  return (
    <div className="bg-slate-900/95 border border-slate-800 rounded-xl p-4 shadow-2xl backdrop-blur-md flex flex-col space-y-4 animate-in fade-in slide-in-from-bottom-2 duration-200">
      {/* Header */}
      <div className="flex items-start justify-between gap-2 border-b border-slate-800 pb-3">
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <span
              className={`text-[10px] font-mono font-bold px-2 py-0.5 rounded border uppercase tracking-wide ${getNodeBadgeColor(
                selectedNode.type
              )}`}
            >
              {selectedNode.type}
            </span>
            {selectedNode.riskScore && (
              <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-rose-500/15 text-rose-400 border border-rose-500/30">
                Risk {selectedNode.riskScore}
              </span>
            )}
          </div>
          <h3 className="text-sm font-bold text-slate-100">{selectedNode.label}</h3>
          <p className="text-xs text-slate-400">{selectedNode.role || 'Grounded Entity'}</p>
        </div>

        <button
          onClick={onClose}
          aria-label="Close entity inspector"
          className="p-1 rounded-lg text-slate-400 hover:text-slate-100 hover:bg-slate-800 transition-colors"
        >
          <X className="w-4 h-4" />
        </button>
      </div>

      {/* Structured Forensic Metadata */}
      <div className="space-y-2 text-xs">
        {aliases.length > 0 && (
          <div className="flex items-center justify-between p-2 rounded bg-slate-950/70 border border-slate-800/80">
            <span className="text-slate-400 flex items-center gap-1.5">
              <User className="w-3.5 h-3.5 text-indigo-400" />
              Alias / Street Name:
            </span>
            <span className="text-slate-200 font-medium font-mono">
              {aliases.join(', ')}
            </span>
          </div>
        )}

        {soRelations.length > 0 && (
          <div className="p-2 rounded bg-slate-950/70 border border-slate-800/80 space-y-1">
            <span className="text-slate-400 flex items-center gap-1.5">
              <Fingerprint className="w-3.5 h-3.5 text-indigo-400" />
              Familial Parentage Record:
            </span>
            <div className="text-slate-200 font-mono text-[11px] pl-5">
              s/o {soRelations[0].father}
            </div>
          </div>
        )}

        {vehicles.length > 0 && (
          <div className="flex items-center justify-between p-2 rounded bg-slate-950/70 border border-slate-800/80">
            <span className="text-slate-400 flex items-center gap-1.5">
              <Car className="w-3.5 h-3.5 text-amber-400" />
              Associated Vehicles:
            </span>
            <span className="text-amber-300 font-medium font-mono">
              {vehicles.join(', ')}
            </span>
          </div>
        )}

        {imei && (
          <div className="flex items-center justify-between p-2 rounded bg-slate-950/70 border border-slate-800/80">
            <span className="text-slate-400 flex items-center gap-1.5">
              <Phone className="w-3.5 h-3.5 text-sky-400" />
              Hardware IMEI:
            </span>
            <span className="text-sky-300 font-mono">{imei}</span>
          </div>
        )}

        {towerIds.length > 0 && (
          <div className="flex items-center justify-between p-2 rounded bg-slate-950/70 border border-slate-800/80">
            <span className="text-slate-400 flex items-center gap-1.5">
              <Radio className="w-3.5 h-3.5 text-sky-400" />
              Triangulated Towers:
            </span>
            <span className="text-slate-200 font-mono">{towerIds.join(', ')}</span>
          </div>
        )}

        {psName && (
          <div className="flex items-center justify-between p-2 rounded bg-slate-950/70 border border-slate-800/80">
            <span className="text-slate-400 flex items-center gap-1.5">
              <Building2 className="w-3.5 h-3.5 text-indigo-400" />
              Police Station Jurisdiction:
            </span>
            <span className="text-slate-200 font-medium">{psName} PS</span>
          </div>
        )}

        {evidenceSource && (
          <div className="flex items-center justify-between p-2 rounded bg-slate-950/70 border border-slate-800/80">
            <span className="text-slate-400 flex items-center gap-1.5">
              <FileSpreadsheet className="w-3.5 h-3.5 text-emerald-400" />
              Primary Source:
            </span>
            <span className="text-emerald-400 font-mono font-medium">{evidenceSource}</span>
          </div>
        )}

        {textSnippet && (
          <div className="p-2.5 rounded bg-slate-950/90 border border-slate-800 text-[11px] text-slate-300 italic leading-relaxed border-l-2 border-l-amber-500">
            "{textSnippet}"
          </div>
        )}
      </div>

      {/* Connected Relationships */}
      <div className="border-t border-slate-800 pt-3">
        <div className="flex items-center justify-between mb-2">
          <span className="text-[11px] font-bold text-slate-400 uppercase tracking-wider flex items-center gap-1.5">
            <Share2 className="w-3.5 h-3.5 text-indigo-400" />
            Active Linked Associations ({connectedEdges.length})
          </span>
        </div>

        <div className="space-y-1.5 max-h-40 overflow-y-auto pr-1">
          {connectedEdges.map((edge) => (
            <div
              key={edge.id}
              onClick={() => onSelectEdge?.(edge)}
              className="p-2 rounded bg-slate-950/60 border border-slate-800/80 hover:border-indigo-500/50 hover:bg-slate-900 transition-colors cursor-pointer flex items-center justify-between text-xs"
            >
              <div className="min-w-0 pr-2">
                <span className="font-mono text-[10px] text-indigo-400 font-bold uppercase block">
                  {edge.type}
                </span>
                <span className="text-slate-300 truncate block text-[11px]">
                  {edge.source === selectedNode.id ? `➔ ${edge.targetLabel}` : `⬅ from ${edge.sourceLabel}`}
                </span>
              </div>
              <ArrowUpRight className="w-3.5 h-3.5 text-slate-500 shrink-0" />
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};

export default NodeInspector;
