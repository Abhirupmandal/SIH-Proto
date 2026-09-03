'use client';

import React, { useState } from 'react';
import { GraphEdgeData } from '@/types/graph';
import { EvidenceModal } from '@/components/modals/EvidenceModal';
import { GraphCanvas } from '@/components/GraphCanvas';
import {
  ShieldAlert,
  Search,
  Fingerprint,
  PhoneForwarded,
  IndianRupee,
  FileCheck2,
  Cpu,
  Layers,
  Sparkles,
} from 'lucide-react';

export default function Home() {
  const [selectedEdge, setSelectedEdge] = useState<GraphEdgeData | null>(null);
  const [searchQuery, setSearchQuery] = useState('');

  return (
    <main className="min-h-screen bg-slate-950 text-slate-100 flex flex-col">
      {/* Top Forensic Navigation Bar */}
      <header className="border-b border-slate-800/80 bg-slate-900/80 backdrop-blur-md sticky top-0 z-30 px-6 py-4">
        <div className="max-w-7xl mx-auto flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="p-2.5 rounded-xl bg-indigo-600/20 border border-indigo-500/40 text-indigo-400 shadow-inner">
              <ShieldAlert className="w-6 h-6" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="text-[11px] font-mono font-bold px-2 py-0.5 rounded bg-indigo-500/20 text-indigo-300 border border-indigo-500/30 uppercase tracking-wide">
                  PS ID: SIH26189
                </span>
                <span className="flex items-center gap-1.5 text-xs text-emerald-400 font-medium">
                  <span className="w-2 h-2 rounded-full bg-emerald-400 animate-ping" />
                  Forensic Core Active
                </span>
              </div>
              <h1 className="text-xl font-bold tracking-tight text-white mt-0.5">
                AI-Powered Criminal Network Analysis System
              </h1>
            </div>
          </div>

          <div className="flex items-center gap-3">
            <div className="relative">
              <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
              <input
                type="text"
                placeholder="Search suspect, FIR, phone, bank A/C..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-64 pl-9 pr-4 py-1.5 text-xs bg-slate-950/80 border border-slate-800 rounded-lg text-slate-200 placeholder-slate-500 focus:outline-none focus:border-indigo-500 transition-colors"
              />
            </div>
            <div className="hidden lg:flex items-center gap-2 text-xs font-mono px-3 py-1.5 rounded-lg bg-slate-800/60 border border-slate-700/60 text-slate-300">
              <Fingerprint className="w-3.5 h-3.5 text-indigo-400" />
              <span>CASE: #KSP-CYBER-2024-88</span>
            </div>
          </div>
        </div>
      </header>

      {/* Main Content Area */}
      <div className="max-w-7xl w-full mx-auto p-6 space-y-6 flex-1 flex flex-col">
        {/* Intelligence Statistics Banner */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div className="p-4 rounded-xl bg-slate-900/60 border border-slate-800/80 backdrop-blur-sm">
            <div className="flex items-center justify-between">
              <span className="text-xs text-slate-400 font-medium">Suspect Entities</span>
              <Layers className="w-4 h-4 text-indigo-400" />
            </div>
            <div className="text-2xl font-bold text-white font-mono mt-2">6 Nodes</div>
            <div className="text-[11px] text-indigo-400 mt-1">Kingpins, mules, burners</div>
          </div>

          <div className="p-4 rounded-xl bg-slate-900/60 border border-slate-800/80 backdrop-blur-sm">
            <div className="flex items-center justify-between">
              <span className="text-xs text-slate-400 font-medium">Verified Links</span>
              <PhoneForwarded className="w-4 h-4 text-sky-400" />
            </div>
            <div className="text-2xl font-bold text-white font-mono mt-2">6 Edges</div>
            <div className="text-[11px] text-sky-400 mt-1">CDR & ledger corroborations</div>
          </div>

          <div className="p-4 rounded-xl bg-slate-900/60 border border-slate-800/80 backdrop-blur-sm">
            <div className="flex items-center justify-between">
              <span className="text-xs text-slate-400 font-medium">Traced Illicit Flow</span>
              <IndianRupee className="w-4 h-4 text-emerald-400" />
            </div>
            <div className="text-2xl font-bold text-emerald-400 font-mono mt-2">₹46,00,000</div>
            <div className="text-[11px] text-emerald-400/90 mt-1">High-velocity laundering</div>
          </div>

          <div className="p-4 rounded-xl bg-slate-900/60 border border-slate-800/80 backdrop-blur-sm">
            <div className="flex items-center justify-between">
              <span className="text-xs text-slate-400 font-medium">XAI Grounding</span>
              <Cpu className="w-4 h-4 text-amber-400" />
            </div>
            <div className="text-2xl font-bold text-amber-400 font-mono mt-2">96.8%</div>
            <div className="text-[11px] text-amber-400/90 mt-1">Court-admissible trail</div>
          </div>
        </div>

        {/* Network Graph Canvas Section */}
        <section className="space-y-3 flex-1 flex flex-col">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Sparkles className="w-4 h-4 text-indigo-400" />
              <h2 className="text-sm font-semibold tracking-wide uppercase text-slate-200">
                Interactive Criminal Entity & Association Network
              </h2>
            </div>
            <div className="text-xs text-slate-400 flex items-center gap-2">
              <FileCheck2 className="w-4 h-4 text-emerald-400" />
              <span>Click any connection edge to inspect Explainable AI (XAI) evidence trail</span>
            </div>
          </div>

          {/* GraphCanvas Component */}
          <GraphCanvas
            onSelectEdge={setSelectedEdge}
            selectedEdge={selectedEdge}
          />
        </section>
      </div>

      {/* Conditionally rendered Explainable AI (XAI) Evidence Modal */}
      <EvidenceModal
        selectedEdge={selectedEdge}
        onClose={() => setSelectedEdge(null)}
      />
    </main>
  );
}
