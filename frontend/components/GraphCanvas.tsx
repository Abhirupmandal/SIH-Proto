'use client';

import React, { useState } from 'react';
import { GraphEdgeData, GraphNodeData } from '@/types/graph';
import {
  ShieldAlert,
  Phone,
  Landmark,
  FileSpreadsheet,
  HelpCircle,
  ZoomIn,
  ZoomOut,
  Maximize2,
  Info,
} from 'lucide-react';

export interface GraphCanvasProps {
  nodes?: GraphNodeData[];
  edges?: GraphEdgeData[];
  onSelectEdge?: (edge: GraphEdgeData | null) => void;
  selectedEdge?: GraphEdgeData | null;
}

// Forensic sample dataset for PS ID: SIH26189 spanning Aug 10, 2026 to Aug 15, 2026
export const SAMPLE_NODES: GraphNodeData[] = [
  {
    id: 'node-1',
    label: 'Vikram Rao (Prime Suspect)',
    type: 'SUSPECT',
    riskScore: 94,
    role: 'Syndicate Kingpin',
    createdAt: '2026-08-10T08:00:00.000Z',
    x: 220,
    y: 180,
  },
  {
    id: 'node-2',
    label: 'Farhan Ahmed',
    type: 'SUSPECT',
    riskScore: 88,
    role: 'Hawala Courier',
    createdAt: '2026-08-12T12:00:00.000Z',
    x: 480,
    y: 130,
  },
  {
    id: 'node-3',
    label: 'A/C #8849201948 (Mule Account)',
    type: 'BANK_ACCOUNT',
    riskScore: 76,
    role: 'Laundering Node',
    createdAt: '2026-08-14T18:00:00.000Z',
    x: 720,
    y: 220,
  },
  {
    id: 'node-4',
    label: '+91-98765-43210 (Burner SIM)',
    type: 'PHONE',
    riskScore: 82,
    role: 'Disposable Comms',
    createdAt: '2026-08-11T12:00:00.000Z',
    x: 230,
    y: 380,
  },
  {
    id: 'node-5',
    label: 'FIR #382/2024 (Bengaluru Cyber PS)',
    type: 'FIR',
    riskScore: 90,
    role: 'Organized Cyber Extortion',
    createdAt: '2026-08-12T17:00:00.000Z',
    x: 520,
    y: 390,
  },
  {
    id: 'node-6',
    label: 'Aura Logistics Pvt Ltd',
    type: 'ORGANIZATION',
    riskScore: 71,
    role: 'Shell Corporation',
    createdAt: '2026-08-10T09:30:00.000Z',
    x: 730,
    y: 390,
  },
];

export const SAMPLE_EDGES: GraphEdgeData[] = [
  {
    id: 'edge-6',
    source: 'node-1',
    target: 'node-6',
    sourceLabel: 'Vikram Rao',
    targetLabel: 'Aura Logistics Pvt Ltd',
    sourceType: 'SUSPECT',
    targetType: 'ORGANIZATION',
    type: 'OPERATES',
    timestamp: '2026-08-10T10:00:00.000Z',
    confidenceScore: 0.89,
    metadata: {
      corporateRole: 'Beneficial Ultimate Owner (Undisclosed 85% stake)',
      registrationNo: 'CIN-U72900KA2021PTC148291',
      incorporationDate: '2021-11-12',
      registeredAddress: 'Level 4, Orion Complex, Rajajinagar, Bengaluru',
    },
    reasoningNote:
      'MCA company master records and proxy shareholder agreements reveal direct control.',
  },
  {
    id: 'edge-1',
    source: 'node-1',
    target: 'node-4',
    sourceLabel: 'Vikram Rao',
    targetLabel: '+91-98765-43210',
    sourceType: 'SUSPECT',
    targetType: 'PHONE',
    type: 'CALLED',
    timestamp: '2026-08-11T14:30:00.000Z',
    duration: 342,
    callerImei: '864201049281745',
    cellTowerId: 'TWR-KA-BLR-0412 (Indiranagar)',
    confidenceScore: 0.98,
    reasoningNote:
      'CDR triangulation confirms consecutive midnight calls matching suspect active geo-location.',
  },
  {
    id: 'edge-2',
    source: 'node-1',
    target: 'node-2',
    sourceLabel: 'Vikram Rao',
    targetLabel: 'Farhan Ahmed',
    sourceType: 'SUSPECT',
    targetType: 'SUSPECT',
    type: 'CO_ACCUSED_IN',
    timestamp: '2026-08-12T18:00:00.000Z',
    firNumber: 'FIR #382/2024',
    policeStation: 'Cyber Crime Police Station, Bengaluru Central',
    firExcerpt:
      'Accused No. 1 (Vikram Rao) conspired with Accused No. 2 (Farhan Ahmed) to route proceeds of ransomware extortion through multiple mule accounts, confirmed by confessions and seizure of encrypted ledger USB.',
    confidenceScore: 0.95,
    reasoningNote:
      'Direct co-accused relationship established under IPC Sections 420, 120B and IT Act Section 66D.',
  },
  {
    id: 'edge-4',
    source: 'node-2',
    target: 'node-5',
    sourceLabel: 'Farhan Ahmed',
    targetLabel: 'FIR #382/2024',
    sourceType: 'SUSPECT',
    targetType: 'FIR',
    type: 'CO_ACCUSED_IN',
    timestamp: '2026-08-13T16:20:00.000Z',
    firNumber: 'FIR #382/2024',
    policeStation: 'Cyber Crime Police Station, Bengaluru Central',
    firExcerpt:
      'Farhan Ahmed acted as primary cash collector and digital mule account aggregator under instructions from syndicate coordinators.',
    confidenceScore: 0.92,
  },
  {
    id: 'edge-3',
    source: 'node-2',
    target: 'node-3',
    sourceLabel: 'Farhan Ahmed',
    targetLabel: 'A/C #8849201948',
    sourceType: 'SUSPECT',
    targetType: 'BANK_ACCOUNT',
    type: 'TRANSFERRED',
    timestamp: '2026-08-14T23:14:00.000Z',
    transactionId: 'UTR-INDB94829104081',
    amount: 2850000,
    ledgerTimestamp: '2026-08-14T23:14:00.000Z',
    confidenceScore: 0.99,
    metadata: {
      remittanceChannel: 'RTGS Immediate Settle',
      originatingBank: 'IndusInd Bank, MG Road Branch',
      destinationBank: 'Axis Bank, Whitefield Branch',
      amlRiskFlag: 'CRITICAL_HIGH_VELOCITY',
    },
    reasoningNote:
      'Layering transaction executed within 2 hours of victim extortion deposit, exceeding standard KYC limits.',
  },
  {
    id: 'edge-5',
    source: 'node-3',
    target: 'node-6',
    sourceLabel: 'A/C #8849201948',
    targetLabel: 'Aura Logistics Pvt Ltd',
    sourceType: 'BANK_ACCOUNT',
    targetType: 'ORGANIZATION',
    type: 'TRANSFERRED',
    timestamp: '2026-08-15T11:30:00.000Z',
    transactionId: 'UTR-AXIS109823485',
    amount: 1750000,
    ledgerTimestamp: '2026-08-15T11:30:00.000Z',
    confidenceScore: 0.96,
    metadata: {
      paymentPurpose: 'Fictitious Freight Logistics Invoicing',
      taxInvoiceRef: 'INV-2024-08-992',
    },
    reasoningNote:
      'Integration stage: Fictitious invoicing used to justify illicit funds entering formal economy.',
  },
];

export interface GraphCanvasProps {
  nodes?: GraphNodeData[];
  edges?: GraphEdgeData[];
  onSelectEdge?: (edge: GraphEdgeData | null) => void;
  selectedEdge?: GraphEdgeData | null;
  onSelectNode?: (node: GraphNodeData | null) => void;
  selectedNode?: GraphNodeData | null;
}

export const GraphCanvas: React.FC<GraphCanvasProps> = ({
  nodes = SAMPLE_NODES,
  edges = SAMPLE_EDGES,
  onSelectEdge,
  selectedEdge,
  onSelectNode,
  selectedNode,
}) => {
  const [hoveredEdge, setHoveredEdge] = useState<string | null>(null);

  // Map nodes by ID for fast lookup
  const nodeMap = new Map<string, GraphNodeData>();
  nodes.forEach((n) => nodeMap.set(n.id, n));

  const getNodeIcon = (type: string) => {
    const t = (type || '').toUpperCase();
    if (t.includes('SUSPECT')) {
      return <ShieldAlert className="w-4 h-4 text-rose-400" />;
    }
    if (t.includes('ACCOUNT') || t.includes('BANK')) {
      return <Landmark className="w-4 h-4 text-emerald-400" />;
    }
    if (t.includes('PHONE')) {
      return <Phone className="w-4 h-4 text-sky-400" />;
    }
    if (t.includes('FIR') || t.includes('CRIME') || t.includes('CASE')) {
      return <FileSpreadsheet className="w-4 h-4 text-amber-400" />;
    }
    return <HelpCircle className="w-4 h-4 text-indigo-400" />;
  };

  const getEdgeStroke = (edge: GraphEdgeData, isHovered: boolean, isSelected: boolean) => {
    if (isSelected) return '#38bdf8'; // Bright sky
    if (isHovered) return '#f43f5e'; // High-contrast rose
    switch (edge.type) {
      case 'TRANSFERRED':
        return '#10b981'; // Emerald
      case 'CALLED':
        return '#0284c7'; // Sky
      case 'CO_ACCUSED_IN':
        return '#f43f5e'; // Rose
      case 'OPERATES':
        return '#a855f7'; // Purple
      default:
        return '#6366f1'; // Indigo
    }
  };

  return (
    <div className="relative w-full h-[620px] bg-slate-950 rounded-xl border border-slate-800 overflow-hidden shadow-2xl flex flex-col">
      {/* Canvas Top Action Bar */}
      <div className="absolute top-4 left-4 z-10 flex items-center gap-2">
        <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-slate-900/90 border border-slate-800 backdrop-blur-md text-xs font-mono text-slate-300 shadow-md">
          <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
          <span>FORENSIC NEURAL GRAPH v2.4</span>
        </div>

        <div className="hidden sm:flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-900/90 border border-slate-800 backdrop-blur-md text-xs text-slate-400">
          <Info className="w-3.5 h-3.5 text-indigo-400" />
          <span>Click any connection edge to open XAI Evidence Trail</span>
        </div>
      </div>

      {/* Control Buttons */}
      <div className="absolute top-4 right-4 z-10 flex items-center gap-1.5 bg-slate-900/90 border border-slate-800 p-1 rounded-lg backdrop-blur-md">
        <button
          className="p-1.5 text-slate-400 hover:text-slate-100 hover:bg-slate-800 rounded transition-colors"
          title="Zoom In"
        >
          <ZoomIn className="w-4 h-4" />
        </button>
        <button
          className="p-1.5 text-slate-400 hover:text-slate-100 hover:bg-slate-800 rounded transition-colors"
          title="Zoom Out"
        >
          <ZoomOut className="w-4 h-4" />
        </button>
        <button
          className="p-1.5 text-slate-400 hover:text-slate-100 hover:bg-slate-800 rounded transition-colors"
          title="Recenter Canvas"
        >
          <Maximize2 className="w-4 h-4" />
        </button>
      </div>

      {/* SVG Canvas with Network Graph */}
      <div className="flex-1 w-full h-full relative cursor-crosshair">
        {/* Subtle Background Coordinate Grid */}
        <div
          className="absolute inset-0 opacity-[0.15] pointer-events-none"
          style={{
            backgroundImage:
              'radial-gradient(#64748b 1px, transparent 1px), linear-gradient(to right, #1e293b 1px, transparent 1px), linear-gradient(to bottom, #1e293b 1px, transparent 1px)',
            backgroundSize: '24px 24px, 48px 48px, 48px 48px',
          }}
        />

        <svg className="w-full h-full select-none" viewBox="0 0 960 520">
          <defs>
            <marker
              id="arrow-default"
              viewBox="0 0 10 10"
              refX="28"
              refY="5"
              markerWidth="6"
              markerHeight="6"
              orient="auto-start-reverse"
            >
              <path d="M 0 1 L 10 5 L 0 9 z" fill="#64748b" />
            </marker>
            <marker
              id="arrow-highlight"
              viewBox="0 0 10 10"
              refX="28"
              refY="5"
              markerWidth="7"
              markerHeight="7"
              orient="auto-start-reverse"
            >
              <path d="M 0 1 L 10 5 L 0 9 z" fill="#38bdf8" />
            </marker>
          </defs>

          {/* Edges */}
          {edges.map((edge) => {
            const src = nodeMap.get(edge.source);
            const tgt = nodeMap.get(edge.target);
            if (!src || !tgt || src.x === undefined || src.y === undefined || tgt.x === undefined || tgt.y === undefined) {
              return null;
            }

            const isSelected = selectedEdge?.id === edge.id;
            const isHovered = hoveredEdge === edge.id;
            const strokeColor = getEdgeStroke(edge, isHovered, isSelected);

            // Midpoint coordinates for relationship badge
            const midX = (src.x + tgt.x) / 2;
            const midY = (src.y + tgt.y) / 2;

            return (
              <g
                key={edge.id}
                className="cursor-pointer group"
                onClick={() => onSelectEdge?.(edge)}
                onMouseEnter={() => setHoveredEdge(edge.id)}
                onMouseLeave={() => setHoveredEdge(null)}
              >
                {/* Thick invisible click/hover target for accessibility */}
                <line
                  x1={src.x}
                  y1={src.y}
                  x2={tgt.x}
                  y2={tgt.y}
                  stroke="transparent"
                  strokeWidth="24"
                />

                {/* Visible Animated Connection Line */}
                <line
                  x1={src.x}
                  y1={src.y}
                  x2={tgt.x}
                  y2={tgt.y}
                  stroke={strokeColor}
                  strokeWidth={isSelected ? 3.5 : isHovered ? 3 : 2}
                  strokeDasharray={edge.type === 'CO_ACCUSED_IN' ? '6 4' : undefined}
                  markerEnd={isSelected ? 'url(#arrow-highlight)' : 'url(#arrow-default)'}
                  className="transition-all duration-200"
                />

                {/* Relationship Tag Pill on Edge Midpoint */}
                <g transform={`translate(${midX}, ${midY})`}>
                  <rect
                    x="-48"
                    y="-11"
                    width="96"
                    height="22"
                    rx="11"
                    fill="#0f172a"
                    stroke={strokeColor}
                    strokeWidth={isSelected ? 2 : 1}
                    className="transition-colors duration-200"
                  />
                  <text
                    x="0"
                    y="3.5"
                    textAnchor="middle"
                    fill={isSelected ? '#38bdf8' : '#e2e8f0'}
                    fontSize="9.5"
                    fontFamily="monospace"
                    fontWeight="bold"
                    className="select-none pointer-events-none"
                  >
                    {edge.type}
                  </text>
                </g>
              </g>
            );
          })}

          {/* Nodes */}
          {nodes.map((node) => {
            const posX = node.x ?? 480;
            const posY = node.y ?? 260;
            const isHighRisk = (node.riskScore ?? 0) >= 80;
            const nodeOpacity = node.opacity ?? 1;
            const isSelectedNode = selectedNode?.id === node.id;

            return (
              <g
                key={node.id}
                transform={`translate(${posX}, ${posY})`}
                className="cursor-pointer group transition-opacity duration-300"
                style={{ opacity: nodeOpacity }}
                onClick={(e) => {
                  e.stopPropagation();
                  onSelectNode?.(node);
                }}
              >
                {/* Highlight ring for selected node */}
                {isSelectedNode && (
                  <circle
                    r="26"
                    fill="none"
                    stroke="#38bdf8"
                    strokeWidth="2.5"
                    strokeDasharray="4 2"
                    className="animate-spin"
                  />
                )}

                {/* Glow ring for high risk entities (only active when not dimmed) */}
                {isHighRisk && nodeOpacity >= 0.9 && (
                  <circle
                    r="24"
                    fill="none"
                    stroke="#f43f5e"
                    strokeWidth="1.5"
                    opacity="0.4"
                    className="animate-ping"
                  />
                )}

                {/* Node Outer Circle */}
                <circle
                  r="18"
                  fill="#0f172a"
                  stroke={isSelectedNode ? '#38bdf8' : isHighRisk ? '#f43f5e' : '#3b82f6'}
                  strokeWidth={isSelectedNode ? 3 : 2}
                  className="transition-transform duration-200 group-hover:scale-110"
                />

                {/* Risk Score Pill */}
                {node.riskScore && (
                  <g transform="translate(12, -12)">
                    <circle r="8" fill="#1e293b" stroke="#f43f5e" strokeWidth="1" />
                    <text
                      textAnchor="middle"
                      y="3"
                      fontSize="8"
                      fill="#f43f5e"
                      fontWeight="bold"
                      fontFamily="monospace"
                    >
                      {node.riskScore}
                    </text>
                  </g>
                )}

                {/* Node Label Below */}
                <text
                  x="0"
                  y="32"
                  textAnchor="middle"
                  fill="#f8fafc"
                  fontSize="11"
                  fontWeight="600"
                  className="select-none pointer-events-none drop-shadow"
                >
                  {node.label}
                </text>
                <text
                  x="0"
                  y="45"
                  textAnchor="middle"
                  fill="#94a3b8"
                  fontSize="9"
                  fontFamily="sans-serif"
                  className="select-none pointer-events-none"
                >
                  {node.role}
                </text>
              </g>
            );
          })}
        </svg>
      </div>

      {/* Quick Interactive Legend Bar at Bottom */}
      <div className="px-6 py-3 bg-slate-900/90 border-t border-slate-800 flex flex-wrap items-center justify-between gap-4 text-xs">
        <div className="flex items-center gap-4 text-slate-300">
          <span className="font-semibold text-slate-400">Relationship Legend:</span>
          <div className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-full bg-sky-400" />
            <span>CALLED</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-full bg-emerald-400" />
            <span>TRANSFERRED</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-full bg-rose-400" />
            <span>CO_ACCUSED_IN</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-full bg-purple-400" />
            <span>OPERATES</span>
          </div>
        </div>

        <div className="text-slate-400 font-mono text-[11px]">
          Temporal Subgraph: {nodes.filter((n) => (n.opacity ?? 1) > 0.5).length} Active Nodes • {edges.length} Intercepted Links
        </div>
      </div>
    </div>
  );
};

export default GraphCanvas;
