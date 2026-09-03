'use client';

import React, { useRef, useEffect, useState, useMemo } from 'react';
import dynamic from 'next/dynamic';
import { GraphNodeData, GraphEdgeData } from '@/types/graph';
import {
  ZoomIn,
  ZoomOut,
  Maximize2,
  Info,
  ShieldAlert,
  Layers,
} from 'lucide-react';

// Dynamic import with SSR disabled to prevent hydration/canvas errors
const ForceGraph2D = dynamic(() => import('react-force-graph-2d'), {
  ssr: false,
  loading: () => (
    <div className="w-full h-full flex items-center justify-center bg-[#030712] text-slate-400 text-xs font-mono">
      <div className="flex items-center gap-2">
        <div className="w-3 h-3 rounded-full bg-indigo-500 animate-ping" />
        <span>Initializing Force Physics Engine...</span>
      </div>
    </div>
  ),
});

export interface ForceGraphCanvasProps {
  nodes: GraphNodeData[];
  edges: GraphEdgeData[];
  onSelectNode: (node: GraphNodeData) => void;
  onSelectEdge: (edge: GraphEdgeData) => void;
  selectedNodeId?: string;
  selectedEdgeId?: string;
}

export const ForceGraphCanvas: React.FC<ForceGraphCanvasProps> = ({
  nodes,
  edges,
  onSelectNode,
  onSelectEdge,
  selectedNodeId,
  selectedEdgeId,
}) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const fgRef = useRef<any>(null);
  const [dimensions, setDimensions] = useState({ width: 800, height: 580 });

  // Update canvas dimensions on container resize
  useEffect(() => {
    if (!containerRef.current) return;

    const updateSize = () => {
      if (containerRef.current) {
        const { clientWidth, clientHeight } = containerRef.current;
        setDimensions({
          width: clientWidth || 800,
          height: clientHeight || 580,
        });
      }
    };

    updateSize();
    const resizeObserver = new ResizeObserver(updateSize);
    resizeObserver.observe(containerRef.current);

    return () => resizeObserver.disconnect();
  }, []);

  // Data Transformation for react-force-graph-2d
  const graphData = useMemo(() => {
    const nodeLookup = new Map<string, boolean>();

    const forceNodes = nodes.map((n) => {
      const typeStr = (n.type || '').toUpperCase();
      const rawBetweenness =
        (n.metadata?.betweenness as number | undefined) ??
        (n.riskScore ? n.riskScore / 100 : 0.45);

      nodeLookup.set(n.id, true);

      return {
        id: n.id,
        name: n.label,
        type: n.type,
        role: n.role || (typeStr.includes('SUSPECT') ? 'Operative' : n.type),
        betweenness: rawBetweenness,
        riskScore: n.riskScore ?? 75,
        opacity: n.opacity ?? 1,
        metadata: n.metadata,
        originalNode: n,
        // Optional coordinate hints
        x: n.x,
        y: n.y,
      };
    });

    const forceLinks = edges
      .filter((e) => nodeLookup.has(e.source) && nodeLookup.has(e.target))
      .map((e) => ({
        id: e.id,
        source: e.source,
        target: e.target,
        type: e.type,
        amount: e.amount,
        duration: e.duration,
        timestamp: e.timestamp,
        originalEdge: e,
      }));

    return { nodes: forceNodes, links: forceLinks };
  }, [nodes, edges]);

  // Configure D3 Force Physics
  useEffect(() => {
    if (fgRef.current) {
      // Strong repulsion to prevent clumping
      fgRef.current.d3Force('charge')?.strength(-350);

      // Spacious link distance (100 to 140)
      const linkForce = fgRef.current.d3Force('link');
      if (linkForce && typeof linkForce.distance === 'function') {
        linkForce.distance(120);
      }
    }
  }, [graphData]);

  // Color selection for node halos by category and betweenness
  const getNodeHaloColor = (node: any) => {
    const typeStr = (node.type || '').toUpperCase();
    const isKingpinOrBroker =
      node.betweenness > 0.5 ||
      (node.role &&
        (node.role.toLowerCase().includes('kingpin') ||
          node.role.toLowerCase().includes('broker')));

    if (isKingpinOrBroker) return '#ef4444'; // Red for Kingpin/Broker
    if (typeStr.includes('SUSPECT')) return '#3b82f6'; // Blue for Suspect Operatives
    if (typeStr.includes('PHONE')) return '#f59e0b'; // Amber for Phones
    if (typeStr.includes('ACCOUNT') || typeStr.includes('BANK')) return '#10b981'; // Green for Mule Accounts
    if (typeStr.includes('FIR') || typeStr.includes('CRIME') || typeStr.includes('CASE')) return '#8b5cf6'; // Violet for Crime Cases
    return '#6366f1'; // Default Indigo
  };

  // Color selection for relationship links
  const getLinkColor = (link: any) => {
    const isSelected = selectedEdgeId === link.id;
    if (isSelected) return '#38bdf8'; // Bright Cyan for selected link

    const t = (link.type || '').toUpperCase();
    if (t === 'CALLED') return '#f59e0b'; // Amber for CALLED
    if (t === 'TRANSFERRED') return '#10b981'; // Emerald for TRANSFERRED
    if (t === 'CO_ACCUSED_IN') return '#f43f5e'; // Rose for CO_ACCUSED_IN
    return '#6366f1'; // Indigo for OPERATES / USES
  };

  // Custom Node Painting on HTML5 2D Canvas
  const handleNodeCanvasObject = (node: any, ctx: CanvasRenderingContext2D, globalScale: number) => {
    const x = node.x ?? 0;
    const y = node.y ?? 0;
    const opacity = node.opacity ?? 1;
    const isSelected = selectedNodeId === node.id;
    const haloColor = getNodeHaloColor(node);
    const radius = isSelected ? 8.5 : 6.5;

    ctx.save();
    ctx.globalAlpha = opacity;

    // 1. Glowing Halo for high-risk targets or selected node
    if (node.betweenness > 0.5 || (node.riskScore ?? 0) >= 80 || isSelected) {
      ctx.beginPath();
      ctx.arc(x, y, radius + (isSelected ? 5 : 3.5), 0, 2 * Math.PI, false);
      ctx.fillStyle = `${haloColor}25`;
      ctx.fill();

      ctx.beginPath();
      ctx.arc(x, y, radius + (isSelected ? 3 : 2), 0, 2 * Math.PI, false);
      ctx.strokeStyle = haloColor;
      ctx.lineWidth = isSelected ? 1.8 / globalScale : 1.2 / globalScale;
      ctx.stroke();
    }

    // 2. Core Solid Node Circle
    ctx.beginPath();
    ctx.arc(x, y, radius, 0, 2 * Math.PI, false);
    ctx.fillStyle = '#0f172a';
    ctx.fill();
    ctx.strokeStyle = isSelected ? '#38bdf8' : haloColor;
    ctx.lineWidth = 1.5 / globalScale;
    ctx.stroke();

    // 3. Small Betweenness / Risk Score Badge Pill directly on top of high-priority nodes
    if (node.betweenness > 0.5 || (node.riskScore ?? 0) >= 80) {
      const badgeText = (node.betweenness ?? 0.85).toFixed(2);
      const badgeFontSize = Math.max(7 / globalScale, 2.8);
      ctx.font = `bold ${badgeFontSize}px monospace`;
      const textWidth = ctx.measureText(badgeText).width;
      const pillWidth = textWidth + 4 / globalScale;
      const pillHeight = badgeFontSize + 2 / globalScale;
      const pillY = y - radius - 5 / globalScale;

      ctx.fillStyle = '#1e293b';
      ctx.beginPath();
      ctx.roundRect(x - pillWidth / 2, pillY - pillHeight / 2, pillWidth, pillHeight, 2 / globalScale);
      ctx.fill();
      ctx.strokeStyle = haloColor;
      ctx.lineWidth = 0.6 / globalScale;
      ctx.stroke();

      ctx.fillStyle = haloColor;
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      ctx.fillText(badgeText, x, pillY);
    }

    // 4. Crisp Typography Under Each Node (White label, muted type subtext)
    const labelFontSize = Math.max(9 / globalScale, 3.2);
    ctx.font = `600 ${labelFontSize}px sans-serif`;
    ctx.textAlign = 'center';
    ctx.textBaseline = 'top';
    ctx.fillStyle = '#f8fafc';
    ctx.fillText(node.name || node.id, x, y + radius + 3 / globalScale);

    const subFontSize = Math.max(7.5 / globalScale, 2.6);
    ctx.font = `normal ${subFontSize}px sans-serif`;
    ctx.fillStyle = '#94a3b8';
    ctx.fillText(node.role || node.type || '', x, y + radius + labelFontSize + 4 / globalScale);

    ctx.restore();
  };

  const handleZoomIn = () => {
    if (fgRef.current) {
      fgRef.current.zoom(fgRef.current.zoom() * 1.3, 300);
    }
  };

  const handleZoomOut = () => {
    if (fgRef.current) {
      fgRef.current.zoom(fgRef.current.zoom() / 1.3, 300);
    }
  };

  const handleRecenter = () => {
    if (fgRef.current) {
      fgRef.current.zoomToFit(400, 50);
    }
  };

  return (
    <div
      ref={containerRef}
      className="relative w-full h-[620px] bg-[#030712] rounded-xl border border-slate-800 overflow-hidden shadow-2xl flex flex-col"
    >
      {/* Background Dot Matrix Pattern */}
      <div
        className="absolute inset-0 pointer-events-none opacity-20"
        style={{
          backgroundImage: 'radial-gradient(#475569 1px, transparent 1px)',
          backgroundSize: '24px 24px',
        }}
      />

      {/* Canvas Top Action Bar */}
      <div className="absolute top-4 left-4 z-10 flex items-center gap-2">
        <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-slate-900/90 border border-slate-800 backdrop-blur-md text-xs font-mono text-slate-300 shadow-md">
          <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
          <span>D3 FORCE NEURAL ENGINE</span>
        </div>

        <div className="hidden sm:flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-900/90 border border-slate-800 backdrop-blur-md text-xs text-slate-400">
          <Info className="w-3.5 h-3.5 text-indigo-400" />
          <span>Drag nodes to explore physics; click edges to inspect evidence</span>
        </div>
      </div>

      {/* Control Buttons */}
      <div className="absolute top-4 right-4 z-10 flex items-center gap-1.5 bg-slate-900/90 border border-slate-800 p-1 rounded-lg backdrop-blur-md">
        <button
          onClick={handleZoomIn}
          className="p-1.5 text-slate-400 hover:text-slate-100 hover:bg-slate-800 rounded transition-colors"
          title="Zoom In"
        >
          <ZoomIn className="w-4 h-4" />
        </button>
        <button
          onClick={handleZoomOut}
          className="p-1.5 text-slate-400 hover:text-slate-100 hover:bg-slate-800 rounded transition-colors"
          title="Zoom Out"
        >
          <ZoomOut className="w-4 h-4" />
        </button>
        <button
          onClick={handleRecenter}
          className="p-1.5 text-slate-400 hover:text-slate-100 hover:bg-slate-800 rounded transition-colors"
          title="Recenter Canvas"
        >
          <Maximize2 className="w-4 h-4" />
        </button>
      </div>

      {/* React Force Graph 2D Component */}
      <div className="flex-1 w-full h-full relative cursor-grab active:cursor-grabbing">
        <ForceGraph2D
          ref={fgRef}
          width={dimensions.width}
          height={dimensions.height}
          graphData={graphData}
          backgroundColor="#030712"
          nodeCanvasObject={handleNodeCanvasObject}
          nodePointerAreaPaint={(node: any, color, ctx) => {
            ctx.fillStyle = color;
            ctx.beginPath();
            ctx.arc(node.x || 0, node.y || 0, 10, 0, 2 * Math.PI, false);
            ctx.fill();
          }}
          onNodeClick={(node: any) => {
            if (node.originalNode) {
              onSelectNode(node.originalNode);
            }
          }}
          onLinkClick={(link: any) => {
            if (link.originalEdge) {
              onSelectEdge(link.originalEdge);
            }
          }}
          nodeLabel={(node: any) => `
            <div style="background:#0f172a; border:1px solid #334155; padding:6px 10px; border-radius:6px; font-family:sans-serif; font-size:11px; color:#f8fafc; box-shadow:0 8px 16px rgba(0,0,0,0.5)">
              <div style="font-weight:bold; color:#38bdf8">${node.name}</div>
              <div style="color:#94a3b8; font-size:10px">${node.role || node.type}</div>
              <div style="color:#f43f5e; font-size:10px; margin-top:2px">Betweenness: ${(node.betweenness || 0).toFixed(2)}</div>
            </div>
          `}
          linkLabel={(link: any) => `
            <div style="background:#0f172a; border:1px solid #334155; padding:6px 10px; border-radius:6px; font-family:sans-serif; font-size:11px; color:#f8fafc; box-shadow:0 8px 16px rgba(0,0,0,0.5)">
              <div style="font-weight:bold; color:#818cf8; text-transform:uppercase">${link.type}</div>
              ${link.amount ? `<div style="color:#10b981; font-weight:bold">₹${Number(link.amount).toLocaleString('en-IN')}</div>` : ''}
              ${link.duration ? `<div style="color:#38bdf8">Duration: ${link.duration}s</div>` : ''}
              <div style="color:#64748b; font-size:9px; margin-top:2px">Click to inspect XAI Evidence Trail</div>
            </div>
          `}
          linkColor={getLinkColor}
          linkWidth={(link: any) => (selectedEdgeId === link.id ? 3 : 1.6)}
          linkDirectionalParticles={2}
          linkDirectionalParticleSpeed={0.005}
          linkDirectionalParticleWidth={2.5}
          linkDirectionalParticleColor={getLinkColor}
          linkDirectionalArrowLength={4}
          linkDirectionalArrowRelPos={1}
          linkDirectionalArrowColor={getLinkColor}
          d3VelocityDecay={0.3}
          cooldownTicks={120}
          enableNodeDrag={true}
          enableZoomInteraction={true}
        />
      </div>

      {/* Forensic Category & Relationship Legend Bar */}
      <div className="px-5 py-2.5 bg-slate-900/90 border-t border-slate-800 flex flex-wrap items-center justify-between gap-3 text-xs">
        <div className="flex flex-wrap items-center gap-3.5 text-slate-300">
          <span className="font-semibold text-slate-400">Classifications:</span>
          <div className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-full bg-red-500 shadow-sm shadow-red-500/50" />
            <span className="text-[11px]">Kingpin / Broker</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-full bg-blue-500 shadow-sm shadow-blue-500/50" />
            <span className="text-[11px]">Operative</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-full bg-amber-500 shadow-sm shadow-amber-500/50" />
            <span className="text-[11px]">Phone / SIM</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-full bg-emerald-500 shadow-sm shadow-emerald-500/50" />
            <span className="text-[11px]">Mule Account</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-full bg-purple-500 shadow-sm shadow-purple-500/50" />
            <span className="text-[11px]">Crime FIR</span>
          </div>
        </div>

        <div className="text-slate-400 font-mono text-[11px]">
          Physics Graph: {graphData.nodes.length} Nodes • {graphData.links.length} Traversal Links
        </div>
      </div>
    </div>
  );
};

export default ForceGraphCanvas;
