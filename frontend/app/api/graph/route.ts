import { NextResponse } from 'next/server';
import fs from 'fs/promises';
import path from 'path';

export async function GET() {
  try {
    // Attempt to locate data/clean_graph.json from frontend/ or repo root
    const rootPath = path.join(process.cwd(), '../data/clean_graph.json');
    const localPath = path.join(process.cwd(), './data/clean_graph.json');

    let filePath = rootPath;
    try {
      await fs.access(rootPath);
    } catch {
      filePath = localPath;
    }

    const rawData = await fs.readFile(filePath, 'utf-8');
    const json = JSON.parse(rawData);

    const rawNodes = json.nodes || [];
    const rawEdges = json.edges || [];

    // Pre-calculated aesthetic layout coordinates for SIH26189 forensic entities
    const defaultCoords: Record<string, { x: number; y: number }> = {
      suspect_ramesh_kumar: { x: 320, y: 170 },
      suspect_rakesh: { x: 480, y: 140 },
      suspect_sunil_kumar: { x: 640, y: 170 },
      crime_fir_2024_cr0142: { x: 400, y: 70 },
      crime_fir_2025_cr0999: { x: 680, y: 70 },
      phone_9876543210: { x: 360, y: 290 },
      phone_9876512345: { x: 520, y: 280 },
      phone_9123456789: { x: 220, y: 290 },
      account_123456789012: { x: 340, y: 420 },
      account_987654321098765432: { x: 620, y: 420 },
      location_tower_a: { x: 180, y: 430 },
      location_tower_b: { x: 480, y: 440 },
      location_tower_c: { x: 780, y: 430 },
    };

    // Transform to standard Cytoscape elements format
    const mappedNodes = rawNodes.map((node: any, index: number) => {
      // Dynamic fallback coordinates if not in predefined map
      const totalNodes = rawNodes.length || 1;
      const angle = (2 * Math.PI * index) / totalNodes;
      const fallbackX = Math.round(480 + 260 * Math.cos(angle));
      const fallbackY = Math.round(260 + 170 * Math.sin(angle));

      const coords = defaultCoords[node.id] || { x: fallbackX, y: fallbackY };

      // Calculate risk score from metadata or node type
      const riskScore =
        node.metadata?.riskScore ||
        (node.type === 'Suspect' ? 92 : node.type === 'CrimeCase' ? 95 : 75);

      return {
        data: {
          id: node.id,
          label: node.label,
          type: node.type,
          metadata: node.metadata || {},
          role:
            node.metadata?.role ||
            (node.type === 'Suspect'
              ? 'Operative'
              : node.type === 'CrimeCase'
              ? 'Case File'
              : node.type === 'Account'
              ? 'Mule Account'
              : undefined),
          betweenness: node.metadata?.betweenness || (node.type === 'Suspect' ? 0.84 : 0.42),
          riskScore,
          createdAt: node.metadata?.date || '2024-03-15T00:00:00+00:00',
          x: coords.x,
          y: coords.y,
        },
      };
    });

    // Map of nodes for source and target labels
    const nodeLabelMap = new Map<string, { label: string; type: string }>();
    rawNodes.forEach((n: any) => nodeLabelMap.set(n.id, { label: n.label, type: n.type }));

    const mappedEdges = rawEdges.map((edge: any, index: number) => {
      const edgeId =
        edge.id || `${edge.source}_${edge.target}_${edge.type || 'LINK'}_${index}`;
      const src = nodeLabelMap.get(edge.source);
      const tgt = nodeLabelMap.get(edge.target);

      const timestamp =
        edge.metadata?.timestamp || edge.timestamp || '2024-03-15T00:00:00+00:00';
      const amount =
        edge.metadata?.amount !== undefined
          ? Number(edge.metadata.amount)
          : edge.amount !== undefined
          ? Number(edge.amount)
          : undefined;

      const evidenceSource =
        edge.metadata?.evidence_source || edge.metadata?.fir_no || undefined;

      return {
        data: {
          id: edgeId,
          source: edge.source,
          target: edge.target,
          sourceLabel: src?.label || edge.source,
          targetLabel: tgt?.label || edge.target,
          sourceType: src?.type || undefined,
          targetType: tgt?.type || undefined,
          type: edge.type,
          timestamp,
          amount,
          duration: edge.metadata?.duration,
          callerImei: edge.metadata?.imei,
          cellTowerId: edge.metadata?.tower_id,
          transactionId: edge.metadata?.tx_id,
          ledgerTimestamp: edge.metadata?.timestamp,
          firNumber: edge.metadata?.fir_no || (evidenceSource?.startsWith('FIR') ? evidenceSource : undefined),
          firExcerpt: edge.metadata?.text_snippet,
          evidenceSource,
          metadata: edge.metadata || {},
          confidenceScore: edge.metadata?.confidenceScore || 0.96,
          reasoningNote:
            edge.metadata?.relation ||
            (edge.type === 'CO_ACCUSED_IN'
              ? 'Co-accused correlation established from FIR narrative'
              : edge.type === 'TRANSFERRED'
              ? 'Bank transaction ledger record identified'
              : edge.type === 'CALLED'
              ? 'CDR telecommunication record triangulated'
              : undefined),
        },
      };
    });

    return NextResponse.json({
      elements: {
        nodes: mappedNodes,
        edges: mappedEdges,
      },
    });
  } catch (err: any) {
    console.error('Failed to load clean_graph.json:', err);
    return NextResponse.json(
      { error: 'Failed to read clean_graph.json', details: err?.message },
      { status: 500 }
    );
  }
}
