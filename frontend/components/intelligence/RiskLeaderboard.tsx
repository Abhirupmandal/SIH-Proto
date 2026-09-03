'use client';

import React from 'react';
import { GraphNodeData } from '@/types/graph';
import { ShieldAlert, ChevronRight, UserX, AlertTriangle } from 'lucide-react';

interface RiskLeaderboardProps {
  nodes: GraphNodeData[];
  onSelectNode: (node: GraphNodeData) => void;
  selectedNodeId?: string;
}

export const RiskLeaderboard: React.FC<RiskLeaderboardProps> = ({
  nodes,
  onSelectNode,
  selectedNodeId,
}) => {
  // Filter suspects or high risk entities
  const rankedTargets = [...nodes]
    .filter((n) => {
      const type = (n.type || '').toUpperCase();
      return type.includes('SUSPECT') || (n.riskScore ?? 0) >= 80;
    })
    .sort((a, b) => (b.riskScore ?? 0) - (a.riskScore ?? 0));

  if (rankedTargets.length === 0) return null;

  return (
    <div className="bg-slate-900/90 border border-slate-800 rounded-xl p-4 shadow-xl backdrop-blur-md">
      <div className="flex items-center justify-between pb-3 border-b border-slate-800 mb-3">
        <div className="flex items-center gap-2">
          <div className="p-1.5 rounded-lg bg-rose-500/10 border border-rose-500/30 text-rose-400">
            <ShieldAlert className="w-4 h-4" />
          </div>
          <div>
            <h3 className="text-xs font-bold text-slate-100 uppercase tracking-wider">
              Priority Risk Leaderboard
            </h3>
            <p className="text-[10px] text-slate-400">Betweenness Centrality & Threat Ranking</p>
          </div>
        </div>

        <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-rose-500/20 text-rose-300 border border-rose-500/30">
          {rankedTargets.length} Key Targets
        </span>
      </div>

      <div className="space-y-2 max-h-60 overflow-y-auto pr-1">
        {rankedTargets.map((node, index) => {
          const isSelected = selectedNodeId === node.id;
          const aliases = (node.metadata?.aliases as string[]) || [];

          return (
            <div
              key={node.id}
              onClick={() => onSelectNode(node)}
              className={`p-2.5 rounded-lg border transition-all cursor-pointer flex items-center justify-between gap-3 ${
                isSelected
                  ? 'bg-rose-950/40 border-rose-500 shadow-md text-slate-100'
                  : 'bg-slate-950/70 border-slate-800/80 hover:border-slate-700 text-slate-300 hover:text-slate-100'
              }`}
            >
              <div className="flex items-center gap-2.5 min-w-0">
                <span
                  className={`w-5 h-5 rounded-full flex items-center justify-center text-[10px] font-bold font-mono ${
                    index === 0
                      ? 'bg-rose-500 text-white'
                      : index === 1
                      ? 'bg-amber-500 text-white'
                      : 'bg-slate-800 text-slate-400'
                  }`}
                >
                  {index + 1}
                </span>

                <div className="min-w-0">
                  <div className="text-xs font-semibold truncate flex items-center gap-1.5">
                    <span>{node.label}</span>
                    {aliases.length > 0 && (
                      <span className="text-[10px] text-slate-400 font-normal">
                        ({aliases[0]})
                      </span>
                    )}
                  </div>
                  <div className="flex items-center gap-2 text-[10px] text-slate-400 truncate">
                    <span>{node.role || 'Syndicate Member'}</span>
                    {node.communityId !== undefined && (
                      <span className="px-1.5 py-0.2 rounded bg-indigo-950/60 text-indigo-400 border border-indigo-800/60 font-mono text-[9px]">
                        Comm #{node.communityId}
                      </span>
                    )}
                  </div>
                </div>
              </div>

              <div className="flex items-center gap-2 shrink-0">
                <div className="text-right">
                  <div className="text-xs font-bold font-mono text-rose-400">
                    {node.riskScore ? `${node.riskScore}` : '90'}
                  </div>
                  <div className="text-[9px] text-slate-500 uppercase font-mono">
                    {node.betweenness !== undefined ? `BC ${(node.betweenness).toFixed(2)}` : 'THREAT'}
                  </div>
                </div>
                <ChevronRight className="w-3.5 h-3.5 text-slate-500" />
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};

export default RiskLeaderboard;
