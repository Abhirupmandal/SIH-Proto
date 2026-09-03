'use client';

import React, { useState, useEffect, useMemo } from 'react';
import dynamic from 'next/dynamic';
import { GraphEdgeData, GraphNodeData, CytoscapeElement } from '@/types/graph';
import { EvidenceModal } from '@/components/modals/EvidenceModal';
import { IngestionModal } from '@/components/modals/IngestionModal';
import { GraphCanvas, SAMPLE_NODES, SAMPLE_EDGES } from '@/components/GraphCanvas';
import { ForceGraphCanvas } from '@/components/canvas/ForceGraphCanvas';
import { TimelineSlider } from '@/components/controls/TimelineSlider';
import { RiskLeaderboard } from '@/components/intelligence/RiskLeaderboard';
import { NodeInspector } from '@/components/inspectors/NodeInspector';
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
  Loader2,
  Target,
  Orbit,
} from 'lucide-react';

// Dynamic import for React-PDF DossierDownloadButton with SSR disabled
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

export default function Home() {
  // Graph elements state loaded dynamically from /api/graph
  const [nodes, setNodes] = useState<GraphNodeData[]>([]);
  const [edges, setEdges] = useState<GraphEdgeData[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(true);

  const [selectedEdge, setSelectedEdge] = useState<GraphEdgeData | null>(null);
  const [selectedNode, setSelectedNode] = useState<GraphNodeData | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [currentTimestamp, setCurrentTimestamp] = useState<string>('');
  const [isPlaying, setIsPlaying] = useState<boolean>(false);
  const [isIngestOpen, setIsIngestOpen] = useState(false);
  const [canvasMode, setCanvasMode] = useState<'force' | 'static'>('force');

  // Fetch /api/graph on initial load
  useEffect(() => {
    let isMounted = true;

    async function fetchGraphData() {
      try {
        setIsLoading(true);
        const res = await fetch('/api/graph');
        if (!res.ok) throw new Error(`HTTP error ${res.status}`);
        const json = await res.json();

        if (isMounted && json.elements) {
          const fetchedNodes: GraphNodeData[] = (json.elements.nodes || []).map(
            (n: any) => n.data
          );
          const fetchedEdges: GraphEdgeData[] = (json.elements.edges || []).map(
            (e: any) => e.data
          );

          setNodes(fetchedNodes);
          setEdges(fetchedEdges);

          // Calculate initial max timestamp
          const allTimes = fetchedEdges
            .map((e) => new Date(e.timestamp || '').getTime())
            .filter((t) => !isNaN(t));

          if (allTimes.length > 0) {
            const maxT = Math.max(...allTimes);
            setCurrentTimestamp(new Date(maxT).toISOString());
          }
        }
      } catch (err) {
        console.error('Failed to fetch /api/graph, loading fallback sample dataset:', err);
        if (isMounted) {
          setNodes(SAMPLE_NODES);
          setEdges(SAMPLE_EDGES);
          setCurrentTimestamp('2026-08-15T23:59:59.000Z');
        }
      } finally {
        if (isMounted) {
          setIsLoading(false);
        }
      }
    }

    fetchGraphData();

    return () => {
      isMounted = false;
    };
  }, []);

  // Compute dynamic minDate and maxDate from all edge timestamps
  const { minDate, maxDate } = useMemo(() => {
    const timestamps: number[] = [];

    edges.forEach((edge) => {
      if (edge.timestamp) {
        const t = new Date(edge.timestamp).getTime();
        if (!isNaN(t)) timestamps.push(t);
      }
    });

    nodes.forEach((node) => {
      if (node.createdAt) {
        const t = new Date(node.createdAt).getTime();
        if (!isNaN(t)) timestamps.push(t);
      }
    });

    if (timestamps.length === 0) {
      return {
        minDate: '2024-03-15T00:00:00.000Z',
        maxDate: '2025-01-25T23:59:59.000Z',
      };
    }

    const min = Math.min(...timestamps);
    const max = Math.max(...timestamps);

    return {
      minDate: new Date(min).toISOString(),
      maxDate: new Date(max).toISOString(),
    };
  }, [edges, nodes]);

  // Set default currentTimestamp once min/max are ready
  useEffect(() => {
    if (!currentTimestamp && maxDate) {
      setCurrentTimestamp(maxDate);
    }
  }, [maxDate, currentTimestamp]);

  // Auto-increment playback timer every 800ms
  useEffect(() => {
    if (!isPlaying) return;

    const interval = setInterval(() => {
      setCurrentTimestamp((prev) => {
        const prevTime = new Date(prev || minDate).getTime();
        const maxTime = new Date(maxDate).getTime();
        const minTime = new Date(minDate).getTime();

        // Dynamically scale step increment to cover ~30 steps
        const stepMs = Math.max(
          3600000,
          Math.round((maxTime - minTime) / 30)
        );
        const nextTime = prevTime + stepMs;

        if (nextTime >= maxTime) {
          setIsPlaying(false);
          return maxDate;
        }
        return new Date(nextTime).toISOString();
      });
    }, 800);

    return () => clearInterval(interval);
  }, [isPlaying, minDate, maxDate]);

  const handleTogglePlay = () => {
    if (!isPlaying && new Date(currentTimestamp || maxDate).getTime() >= new Date(maxDate).getTime()) {
      setCurrentTimestamp(minDate);
    }
    setIsPlaying((prev) => !prev);
  };

  const currentDateVal = useMemo(() => {
    if (!currentTimestamp) return Infinity;
    const t = new Date(currentTimestamp).getTime();
    return isNaN(t) ? Infinity : t;
  }, [currentTimestamp]);

  // Search filter
  const searchedNodeIds = useMemo(() => {
    if (!searchQuery.trim()) return null;
    const q = searchQuery.toLowerCase().trim();
    const set = new Set<string>();
    nodes.forEach((n) => {
      const labelMatch = n.label.toLowerCase().includes(q);
      const idMatch = n.id.toLowerCase().includes(q);
      const roleMatch = (n.role || '').toLowerCase().includes(q);
      const aliasMatch = ((n.metadata?.aliases as string[]) || []).some((a) =>
        a.toLowerCase().includes(q)
      );
      if (labelMatch || idMatch || roleMatch || aliasMatch) {
        set.add(n.id);
      }
    });
    return set;
  }, [nodes, searchQuery]);

  // Filter edges: hide edges with timestamps > currentTimestamp
  const filteredEdges = useMemo(() => {
    return edges.filter((edge) => {
      if (!edge.timestamp) return true;
      const t = new Date(edge.timestamp).getTime();
      if (isNaN(t)) return true;
      return t <= currentDateVal;
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
      const isCreated =
        !node.createdAt || new Date(node.createdAt).getTime() <= currentDateVal;
      const hasActiveEdge = activeNodeIds.has(node.id);
      const matchesSearch = searchedNodeIds === null || searchedNodeIds.has(node.id);

      let opacity = hasActiveEdge ? 1 : isCreated ? 0.25 : 0.15;
      if (searchedNodeIds !== null && !matchesSearch) {
        opacity = 0.1;
      }

      return {
        ...node,
        opacity,
      };
    });
  }, [nodes, activeNodeIds, currentDateVal, searchedNodeIds]);

  // Auto-deselect edge if it gets scrubbed out of temporal window
  useEffect(() => {
    if (selectedEdge && selectedEdge.timestamp) {
      const t = new Date(selectedEdge.timestamp).getTime();
      if (!isNaN(t) && t > currentDateVal) {
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

    setNodes((prevNodes) => {
      const existingIds = new Set(prevNodes.map((n) => n.id));
      const uniqueNewNodes = newNodes.filter((n) => !existingIds.has(n.id));
      return [...prevNodes, ...uniqueNewNodes];
    });

    setEdges((prevEdges) => {
      const existingIds = new Set(prevEdges.map((e) => e.id));
      const uniqueNewEdges = newEdges.filter((e) => !existingIds.has(e.id));
      return [...prevEdges, ...uniqueNewEdges];
    });

    setIsIngestOpen(false);
  };

  // Connected edges for the currently inspected node
  const connectedEdgesForSelectedNode = useMemo(() => {
    if (!selectedNode) return [];
    return filteredEdges.filter(
      (e) => e.source === selectedNode.id || e.target === selectedNode.id
    );
  }, [selectedNode, filteredEdges]);

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
                  Live Core Connected
                </span>
              </div>
              <h1 className="text-xl font-bold tracking-tight text-white mt-0.5">
                AI-Powered Criminal Network Analysis System
              </h1>
            </div>
          </div>

          <div className="flex items-center gap-2.5 flex-wrap sm:flex-nowrap">
            <div className="relative">
              <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
              <input
                type="text"
                placeholder="Search suspect, FIR, phone, bank A/C..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-52 pl-9 pr-4 py-1.5 text-xs bg-slate-950/80 border border-slate-800 rounded-lg text-slate-200 placeholder-slate-500 focus:outline-none focus:border-indigo-500 transition-colors"
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
              caseId="FIR-2024-CR0142"
              jurisdiction="Andheri / Cyber Cell Central"
              nodes={filteredNodes}
              edges={filteredEdges}
            />

            <div className="hidden xl:flex items-center gap-2 text-xs font-mono px-3 py-1.5 rounded-lg bg-slate-800/60 border border-slate-700/60 text-slate-300">
              <Fingerprint className="w-3.5 h-3.5 text-indigo-400" />
              <span>CASE: #FIR-2024-CR0142</span>
            </div>
          </div>
        </div>
      </header>

      {/* Main Content Area */}
      <div className="max-w-7xl w-full mx-auto p-6 space-y-6 flex-1 flex flex-col">
        {/* Loading Spinner State */}
        {isLoading ? (
          <div className="flex-1 flex flex-col items-center justify-center min-h-[480px] p-12 bg-slate-900/40 border border-slate-800/60 rounded-2xl">
            <div className="relative flex items-center justify-center mb-4">
              <div className="w-14 h-14 rounded-full border-4 border-slate-800 border-t-indigo-500 animate-spin" />
              <ShieldAlert className="w-6 h-6 text-indigo-400 absolute animate-pulse" />
            </div>
            <div className="text-sm font-semibold text-slate-200">
              Loading Forensic Neural Graph & Entities...
            </div>
            <div className="text-xs text-slate-500 mt-1 font-mono">
              Parsing verified CCTNS clean_graph.json intelligence...
            </div>
          </div>
        ) : (
          <>
            {/* Intelligence Statistics Banner (Dynamic by clean_graph.json & Temporal Window) */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div className="p-4 rounded-xl bg-slate-900/60 border border-slate-800/80 backdrop-blur-sm">
                <div className="flex items-center justify-between">
                  <span className="text-xs text-slate-400 font-medium">Active Entities</span>
                  <Layers className="w-4 h-4 text-indigo-400" />
                </div>
                <div className="text-2xl font-bold text-white font-mono mt-2">
                  {filteredNodes.filter((n) => (n.opacity ?? 1) > 0.5).length} / {nodes.length}
                </div>
                <div className="text-[11px] text-indigo-400 mt-1">Grounded in scrub window</div>
              </div>

              <div className="p-4 rounded-xl bg-slate-900/60 border border-slate-800/80 backdrop-blur-sm">
                <div className="flex items-center justify-between">
                  <span className="text-xs text-slate-400 font-medium">Active Intercepts</span>
                  <PhoneForwarded className="w-4 h-4 text-sky-400" />
                </div>
                <div className="text-2xl font-bold text-white font-mono mt-2">
                  {filteredEdges.length} / {edges.length}
                </div>
                <div className="text-[11px] text-sky-400 mt-1">Grounded CDR & ledger links</div>
              </div>

              <div className="p-4 rounded-xl bg-slate-900/60 border border-slate-800/80 backdrop-blur-sm">
                <div className="flex items-center justify-between">
                  <span className="text-xs text-slate-400 font-medium">Cumulative Illicit Flow</span>
                  <IndianRupee className="w-4 h-4 text-emerald-400" />
                </div>
                <div className="text-2xl font-bold text-emerald-400 font-mono mt-2">
                  {formatINR(activeTracedSum)}
                </div>
                <div className="text-[11px] text-emerald-400/90 mt-1">Laundered up to scrub time</div>
              </div>

              <div className="p-4 rounded-xl bg-slate-900/60 border border-slate-800/80 backdrop-blur-sm">
                <div className="flex items-center justify-between">
                  <span className="text-xs text-slate-400 font-medium">Temporal Window</span>
                  <CalendarRange className="w-4 h-4 text-amber-400" />
                </div>
                <div className="text-2xl font-bold text-amber-400 font-mono mt-2">
                  {currentTimestamp
                    ? new Date(currentTimestamp).toLocaleDateString('en-US', {
                        day: 'numeric',
                        month: 'short',
                        year: 'numeric',
                      })
                    : 'All Active'}
                </div>
                <div className="text-[11px] text-amber-400/90 mt-1">
                  {isPlaying ? 'Auto-stepping timeline' : 'Interactive scrub active'}
                </div>
              </div>
            </div>

            {/* Main Network Graph & Intelligence Layout */}
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-5 flex-1 items-start">
              {/* Center Canvas & Temporal Playback: 8 or 9 columns */}
              <div className="lg:col-span-8 xl:col-span-9 flex flex-col space-y-3">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Sparkles className="w-4 h-4 text-indigo-400" />
                    <h2 className="text-sm font-semibold tracking-wide uppercase text-slate-200">
                      CCTNS Verified Criminal Syndicate Graph
                    </h2>
                  </div>
                  <div className="flex items-center gap-3">
                    {/* Canvas Mode Toggle */}
                    <div className="flex items-center gap-1 p-0.5 rounded-lg bg-slate-900 border border-slate-800 text-xs">
                      <button
                        type="button"
                        onClick={() => setCanvasMode('force')}
                        className={`flex items-center gap-1.5 px-3 py-1 rounded-md transition-all font-medium ${
                          canvasMode === 'force'
                            ? 'bg-indigo-600 text-white shadow-sm'
                            : 'text-slate-400 hover:text-slate-200'
                        }`}
                      >
                        <Orbit className="w-3.5 h-3.5" />
                        <span>Force 2D Physics</span>
                      </button>
                      <button
                        type="button"
                        onClick={() => setCanvasMode('static')}
                        className={`flex items-center gap-1.5 px-3 py-1 rounded-md transition-all font-medium ${
                          canvasMode === 'static'
                            ? 'bg-indigo-600 text-white shadow-sm'
                            : 'text-slate-400 hover:text-slate-200'
                        }`}
                      >
                        <Layers className="w-3.5 h-3.5" />
                        <span>Static Grid</span>
                      </button>
                    </div>

                    <div className="text-xs text-slate-400 hidden xl:flex items-center gap-2">
                      <FileCheck2 className="w-4 h-4 text-emerald-400" />
                      <span>Click edges for XAI evidence; drag nodes to simulate physics</span>
                    </div>
                  </div>
                </div>

                {/* Interactive Graph Canvas (Force 2D Physics or Static Layout) */}
                {canvasMode === 'force' ? (
                  <ForceGraphCanvas
                    nodes={filteredNodes}
                    edges={filteredEdges}
                    onSelectNode={setSelectedNode}
                    onSelectEdge={setSelectedEdge}
                    selectedNodeId={selectedNode?.id}
                    selectedEdgeId={selectedEdge?.id}
                  />
                ) : (
                  <GraphCanvas
                    nodes={filteredNodes}
                    edges={filteredEdges}
                    onSelectEdge={setSelectedEdge}
                    selectedEdge={selectedEdge}
                    onSelectNode={setSelectedNode}
                    selectedNode={selectedNode}
                  />
                )}

                {/* Docked Temporal Playback Slider */}
                <div className="w-full flex justify-center">
                  <TimelineSlider
                    minDate={minDate}
                    maxDate={maxDate}
                    currentDate={currentTimestamp || maxDate}
                    onChange={setCurrentTimestamp}
                    isPlaying={isPlaying}
                    onTogglePlay={handleTogglePlay}
                  />
                </div>
              </div>

              {/* Right Side Intelligence Panel: Risk Leaderboard & Node Inspector */}
              <div className="lg:col-span-4 xl:col-span-3 space-y-4">
                {/* Node Inspector (when an entity is clicked) */}
                {selectedNode && (
                  <NodeInspector
                    selectedNode={selectedNode}
                    onClose={() => setSelectedNode(null)}
                    connectedEdges={connectedEdgesForSelectedNode}
                    onSelectEdge={setSelectedEdge}
                  />
                )}

                {/* Priority Risk Leaderboard */}
                <RiskLeaderboard
                  nodes={filteredNodes}
                  selectedNodeId={selectedNode?.id}
                  onSelectNode={setSelectedNode}
                />
              </div>
            </div>
          </>
        )}
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
