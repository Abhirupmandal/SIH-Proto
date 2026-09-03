'use client';

import React, { useState, useEffect, useMemo } from 'react';
import dynamic from 'next/dynamic';
import { GraphEdgeData, GraphNodeData, CytoscapeElement } from '@/types/graph';
import { EvidenceModal } from '@/components/modals/EvidenceModal';
import { IngestionModal } from '@/components/modals/IngestionModal';
import { GraphCanvas, SAMPLE_NODES, SAMPLE_EDGES } from '@/components/GraphCanvas';
import { TimelineSlider } from '@/components/controls/TimelineSlider';
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
  CalendarRange,
  UploadCloud,
  FileDown,
} from 'lucide-react';

// Dynamic import for React-PDF DossierDownloadButton with SSR disabled to prevent hydration mismatch
const DossierDownloadButton = dynamic(
  () => import('@/components/export/DossierPdf').then((mod) => mod.DossierDownloadButton),
  {
    ssr: false,
    loading: () => (
      <button
        disabled
        className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-800 text-slate-400 border border-slate-700 text-xs font-semibold"
      >
        <FileDown className="w-3.5 h-3.5" />
        <span>Export Dossier (PDF)</span>
      </button>
    ),
  }
);

const MIN_DATE = '2026-08-10T00:00:00.000Z';
const MAX_DATE = '2026-08-15T23:59:59.000Z';

export default function Home() {
  // Graph elements state initialized with baseline forensic dataset
  const [nodes, setNodes] = useState<GraphNodeData[]>(SAMPLE_NODES);
  const [edges, setEdges] = useState<GraphEdgeData[]>(SAMPLE_EDGES);

  const [selectedEdge, setSelectedEdge] = useState<GraphEdgeData | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [currentTimestamp, setCurrentTimestamp] = useState<string>(MAX_DATE);
  const [isPlaying, setIsPlaying] = useState<boolean>(false);
  const [isIngestOpen, setIsIngestOpen] = useState(false);

  // Auto-increment playback timer every 800ms
  useEffect(() => {
    if (!isPlaying) return;

    const interval = setInterval(() => {
      setCurrentTimestamp((prev) => {
        const prevTime = new Date(prev).getTime();
        const maxTime = new Date(MAX_DATE).getTime();
        // Step forward by 8 hours per tick (800ms)
        const nextTime = prevTime + 8 * 60 * 60 * 1000;

        if (nextTime >= maxTime) {
          setIsPlaying(false);
          return MAX_DATE;
        }
        return new Date(nextTime).toISOString();
      });
    }, 800);

    return () => clearInterval(interval);
  }, [isPlaying]);

  const handleTogglePlay = () => {
    if (!isPlaying && new Date(currentTimestamp).getTime() >= new Date(MAX_DATE).getTime()) {
      setCurrentTimestamp(MIN_DATE);
    }
    setIsPlaying((prev) => !prev);
  };

  const currentDateVal = useMemo(() => new Date(currentTimestamp).getTime(), [currentTimestamp]);

  // Filter edges: hide edges with timestamps > currentTimestamp
  const filteredEdges = useMemo(() => {
    return edges.filter((edge) => {
      if (!edge.timestamp) return true;
      return new Date(edge.timestamp).getTime() <= currentDateVal;
    });
  }, [edges, currentDateVal]);

  // Active node IDs connected to active edges
  const activeNodeIds = useMemo(() => {
    const set = new Set<string>();
    filteredEdges.forEach((edge) => {
      set.add(edge.source);
      set.add(edge.target);
    });
    return set;
  }, [filteredEdges]);

  // Filter nodes: nodes with no active edges at that timestamp render with reduced opacity (0.25)
  const filteredNodes = useMemo(() => {
    return nodes.map((node) => {
      const isCreated = !node.createdAt || new Date(node.createdAt).getTime() <= currentDateVal;
      const hasActiveEdge = activeNodeIds.has(node.id);
      const opacity = hasActiveEdge ? 1 : isCreated ? 0.25 : 0.15;
      return {
        ...node,
        opacity,
      };
    });
  }, [nodes, activeNodeIds, currentDateVal]);

  // Auto-deselect edge if it gets scrubbed out of temporal window
  useEffect(() => {
    if (selectedEdge && selectedEdge.timestamp) {
      if (new Date(selectedEdge.timestamp).getTime() > currentDateVal) {
        setSelectedEdge(null);
      }
    }
  }, [selectedEdge, currentDateVal]);

  // Append new elements from Ingestion modal without duplicate node IDs
  const handleIngestSuccess = (newElements: CytoscapeElement[]) => {
    const newNodes: GraphNodeData[] = [];
    const newEdges: GraphEdgeData[] = [];

    newElements.forEach((el) => {
      const data = el.data;
      if ('source' in data && 'target' in data) {
        newEdges.push(data as GraphEdgeData);
      } else if ('id' in data) {
        newNodes.push(data as GraphNodeData);
      }
    });

    // Append new nodes ensuring no duplicate node IDs exist
    setNodes((prevNodes) => {
      const existingIds = new Set(prevNodes.map((n) => n.id));
      const uniqueNewNodes = newNodes.filter((n) => !existingIds.has(n.id));
      return [...prevNodes, ...uniqueNewNodes];
    });

    // Append new edges ensuring no duplicate edge IDs exist
    setEdges((prevEdges) => {
      const existingIds = new Set(prevEdges.map((e) => e.id));
      const uniqueNewEdges = newEdges.filter((e) => !existingIds.has(e.id));
      return [...prevEdges, ...uniqueNewEdges];
    });

    setIsIngestOpen(false);
  };

  // Dynamic metrics calculated based on temporal window
  const activeTracedSum = useMemo(() => {
    return filteredEdges.reduce((acc, edge) => acc + (edge.amount ?? 0), 0);
  }, [filteredEdges]);

  const formatINR = (val: number) => {
    return new Intl.NumberFormat('en-IN', {
      style: 'currency',
      currency: 'INR',
      maximumFractionDigits: 0,
    }).format(val);
  };

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
                  PS ID: SIH26189 • Team AKATSUKI
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
                className="w-56 pl-9 pr-4 py-1.5 text-xs bg-slate-950/80 border border-slate-800 rounded-lg text-slate-200 placeholder-slate-500 focus:outline-none focus:border-indigo-500 transition-colors"
              />
            </div>

            {/* Ingest Records Action Button */}
            <button
              type="button"
              onClick={() => setIsIngestOpen(true)}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white font-semibold text-xs transition-all shadow-md shadow-indigo-600/30 border border-indigo-400 focus:outline-none focus:ring-2 focus:ring-indigo-400"
              title="Ingest FIR Narrative, CDR Tower Dump, or Bank Ledger"
            >
              <UploadCloud className="w-3.5 h-3.5" />
              <span>Ingest Records</span>
            </button>

            {/* Export Dossier (PDF) Action Button */}
            <DossierDownloadButton
              caseId="#KSP-CYBER-2024-88"
              jurisdiction="Crime Branch Unit 4 / Cyber Cell Central"
              nodes={filteredNodes}
              edges={filteredEdges}
            />

            <div className="hidden lg:flex items-center gap-2 text-xs font-mono px-3 py-1.5 rounded-lg bg-slate-800/60 border border-slate-700/60 text-slate-300">
              <Fingerprint className="w-3.5 h-3.5 text-indigo-400" />
              <span>CASE: #KSP-CYBER-2024-88</span>
            </div>
          </div>
        </div>
      </header>

      {/* Main Content Area */}
      <div className="max-w-7xl w-full mx-auto p-6 space-y-6 flex-1 flex flex-col">
        {/* Intelligence Statistics Banner (Dynamic by Ingestion & Temporal Window) */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div className="p-4 rounded-xl bg-slate-900/60 border border-slate-800/80 backdrop-blur-sm">
            <div className="flex items-center justify-between">
              <span className="text-xs text-slate-400 font-medium">Active Suspects</span>
              <Layers className="w-4 h-4 text-indigo-400" />
            </div>
            <div className="text-2xl font-bold text-white font-mono mt-2">
              {filteredNodes.filter((n) => (n.opacity ?? 1) > 0.5).length} / {nodes.length}
            </div>
            <div className="text-[11px] text-indigo-400 mt-1">Grounded at scrub window</div>
          </div>

          <div className="p-4 rounded-xl bg-slate-900/60 border border-slate-800/80 backdrop-blur-sm">
            <div className="flex items-center justify-between">
              <span className="text-xs text-slate-400 font-medium">Active Intercepts</span>
              <PhoneForwarded className="w-4 h-4 text-sky-400" />
            </div>
            <div className="text-2xl font-bold text-white font-mono mt-2">
              {filteredEdges.length} / {edges.length}
            </div>
            <div className="text-[11px] text-sky-400 mt-1">Chronological links revealed</div>
          </div>

          <div className="p-4 rounded-xl bg-slate-900/60 border border-slate-800/80 backdrop-blur-sm">
            <div className="flex items-center justify-between">
              <span className="text-xs text-slate-400 font-medium">Cumulative Illicit Flow</span>
              <IndianRupee className="w-4 h-4 text-emerald-400" />
            </div>
            <div className="text-2xl font-bold text-emerald-400 font-mono mt-2">
              {formatINR(activeTracedSum)}
            </div>
            <div className="text-[11px] text-emerald-400/90 mt-1">Laundered up to current time</div>
          </div>

          <div className="p-4 rounded-xl bg-slate-900/60 border border-slate-800/80 backdrop-blur-sm">
            <div className="flex items-center justify-between">
              <span className="text-xs text-slate-400 font-medium">Temporal Window</span>
              <CalendarRange className="w-4 h-4 text-amber-400" />
            </div>
            <div className="text-2xl font-bold text-amber-400 font-mono mt-2">
              {new Date(currentTimestamp).toLocaleDateString('en-US', { day: 'numeric', month: 'short' })}
            </div>
            <div className="text-[11px] text-amber-400/90 mt-1">
              {isPlaying ? 'Auto-stepping playback' : 'Interactive scrub active'}
            </div>
          </div>
        </div>

        {/* Network Graph Canvas Section */}
        <section className="space-y-3 flex-1 flex flex-col">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Sparkles className="w-4 h-4 text-indigo-400" />
              <h2 className="text-sm font-semibold tracking-wide uppercase text-slate-200">
                Temporal Evolution of Criminal Syndicate Network
              </h2>
            </div>
            <div className="text-xs text-slate-400 flex items-center gap-2">
              <FileCheck2 className="w-4 h-4 text-emerald-400" />
              <span>Click connection edges to inspect Explainable AI (XAI) evidence trail</span>
            </div>
          </div>

          {/* Interactive Graph Canvas with Dynamic Elements */}
          <div className="flex-1 flex flex-col space-y-3">
            <GraphCanvas
              nodes={filteredNodes}
              edges={filteredEdges}
              onSelectEdge={setSelectedEdge}
              selectedEdge={selectedEdge}
            />

            {/* Docked Temporal Playback Slider anchored along the bottom center */}
            <div className="w-full flex justify-center">
              <TimelineSlider
                minDate={MIN_DATE}
                maxDate={MAX_DATE}
                currentDate={currentTimestamp}
                onChange={setCurrentTimestamp}
                isPlaying={isPlaying}
                onTogglePlay={handleTogglePlay}
              />
            </div>
          </div>
        </section>
      </div>

      {/* Dynamic Record Ingestion Modal */}
      <IngestionModal
        isOpen={isIngestOpen}
        onClose={() => setIsIngestOpen(false)}
        onIngestSuccess={handleIngestSuccess}
      />

      {/* Conditionally rendered Explainable AI (XAI) Evidence Modal */}
      <EvidenceModal
        selectedEdge={selectedEdge}
        onClose={() => setSelectedEdge(null)}
      />
    </main>
  );
}
