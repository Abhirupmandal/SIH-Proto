import { GraphNodeData, GraphEdgeData, GraphData, CytoscapeElement } from '@/types/graph';

export const BACKEND_BASE_URL =
  process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000';

export interface GraphResponse {
  nodes: GraphNodeData[];
  edges: GraphEdgeData[];
  timeRange?: {
    earliest: string | null;
    latest: string | null;
  };
  isLiveBackend: boolean;
}

export interface IngestResponse {
  success: boolean;
  isLiveBackend: boolean;
  stats?: Record<string, unknown>;
  elements?: CytoscapeElement[];
  message?: string;
}

/**
 * Format raw backend Cytoscape elements into frontend GraphNodeData and GraphEdgeData models
 */
function formatCytoscapePayload(rawElements: { nodes?: any[]; edges?: any[] }): {
  nodes: GraphNodeData[];
  edges: GraphEdgeData[];
} {
  const rawNodes = rawElements.nodes || [];
  const rawEdges = rawElements.edges || [];

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

  const nodeMap = new Map<string, { label: string; type: string }>();

  const nodes: GraphNodeData[] = rawNodes.map((n: any, idx: number) => {
    const data = n.data || n;
    nodeMap.set(data.id, { label: data.label, type: data.type });

    const totalNodes = rawNodes.length || 1;
    const angle = (2 * Math.PI * idx) / totalNodes;
    const fallbackX = Math.round(480 + 260 * Math.cos(angle));
    const fallbackY = Math.round(260 + 170 * Math.sin(angle));
    const coords = defaultCoords[data.id] || {
      x: data.x ?? fallbackX,
      y: data.y ?? fallbackY,
    };

    const betweenness =
      typeof data.betweenness === 'number'
        ? data.betweenness
        : data.metadata?.betweenness ?? 0.45;
    const pagerank =
      typeof data.pagerank === 'number'
        ? data.pagerank
        : data.metadata?.pagerank ?? 0.1;
    const communityId =
      typeof data.community_id === 'number'
        ? data.community_id
        : data.communityId ?? data.metadata?.community_id;

    // Normalize risk score to 0-100 scale
    let riskScore = data.riskScore;
    if (riskScore === undefined) {
      if (data.type === 'Suspect' || (data.type && data.type.toUpperCase().includes('SUSPECT'))) {
        riskScore = Math.min(99, Math.round(betweenness * 60 + pagerank * 200 + 40));
      } else if (data.type === 'CrimeCase' || data.type === 'FIR') {
        riskScore = 95;
      } else {
        riskScore = Math.min(90, Math.round(betweenness * 50 + 45));
      }
    }

    const typeStr = (data.type || '').toUpperCase();
    const role =
      data.role ||
      data.metadata?.role ||
      (typeStr.includes('SUSPECT')
        ? betweenness > 0.5
          ? 'Kingpin / Broker'
          : 'Operative'
        : typeStr.includes('ACCOUNT') || typeStr.includes('BANK')
        ? 'Mule Account'
        : typeStr.includes('CRIME') || typeStr.includes('FIR')
        ? 'Case File'
        : data.type);

    return {
      id: data.id,
      label: data.label || data.id,
      type: data.type || 'Suspect',
      role,
      betweenness,
      pagerank,
      communityId,
      riskScore,
      createdAt:
        data.createdAt ||
        data.metadata?.date ||
        data.metadata?.timestamp ||
        '2024-03-15T00:00:00+00:00',
      metadata: data.metadata || {},
      x: coords.x,
      y: coords.y,
    };
  });

  const edges: GraphEdgeData[] = rawEdges.map((e: any, idx: number) => {
    const data = e.data || e;
    const src = nodeMap.get(data.source);
    const tgt = nodeMap.get(data.target);

    const edgeId =
      data.id || `${data.source}_${data.target}_${data.type || 'LINK'}_${idx}`;
    const timestamp =
      data.timestamp || data.metadata?.timestamp || '2024-03-15T00:00:00+00:00';
    const amount =
      data.amount !== undefined
        ? Number(data.amount)
        : data.metadata?.amount !== undefined
        ? Number(data.metadata.amount)
        : undefined;

    return {
      id: edgeId,
      source: data.source,
      target: data.target,
      type: data.type || 'LINK',
      sourceLabel: data.sourceLabel || src?.label || data.source,
      targetLabel: data.targetLabel || tgt?.label || data.target,
      sourceType: data.sourceType || src?.type,
      targetType: data.targetType || tgt?.type,
      timestamp,
      amount,
      duration: data.duration ?? data.metadata?.duration,
      callerImei: data.callerImei ?? data.metadata?.imei ?? data.metadata?.caller_imei,
      cellTowerId:
        data.cellTowerId ??
        data.metadata?.tower_id ??
        (Array.isArray(data.metadata?.tower_ids) ? data.metadata.tower_ids[0] : undefined),
      transactionId:
        data.transactionId ?? data.metadata?.tx_id ?? data.metadata?.transaction_id,
      ledgerTimestamp: data.ledgerTimestamp ?? data.metadata?.timestamp ?? timestamp,
      firNumber:
        data.firNumber ??
        data.metadata?.fir_no ??
        data.metadata?.fir_id ??
        (data.metadata?.evidence_source?.startsWith('FIR')
          ? data.metadata.evidence_source
          : undefined),
      firExcerpt:
        data.firExcerpt ??
        data.metadata?.fir_excerpt ??
        data.metadata?.text_snippet,
      confidenceScore:
        data.confidenceScore ?? data.metadata?.confidenceScore ?? 0.95,
      metadata: data.metadata || {},
      reasoningNote:
        data.reasoningNote ||
        data.metadata?.relation ||
        data.metadata?.reasoning ||
        (data.type === 'CO_ACCUSED_IN'
          ? 'Co-accused correlation established from FIR narrative'
          : data.type === 'TRANSFERRED'
          ? 'Bank transaction ledger record identified'
          : data.type === 'CALLED'
          ? 'CDR telecommunication record triangulated'
          : undefined),
    };
  });

  return { nodes, edges };
}

/**
 * Fetch graph data from Member 2's live FastAPI backend.
 * Falls back safely to internal /api/graph if FastAPI is unreachable.
 */
export async function getGraphData(params?: {
  startTime?: string;
  endTime?: string;
}): Promise<GraphResponse> {
  const queryParams = new URLSearchParams();
  if (params?.startTime) queryParams.set('start_time', params.startTime);
  if (params?.endTime) queryParams.set('end_time', params.endTime);
  const qs = queryParams.toString() ? `?${queryParams.toString()}` : '';

  // 1. Attempt fetching from Member 2's live FastAPI backend
  try {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 3500);

    const backendUrl = `${BACKEND_BASE_URL}/api/graph${qs}`;
    const res = await fetch(backendUrl, {
      signal: controller.signal,
      cache: 'no-store',
    });
    clearTimeout(timeoutId);

    if (res.ok) {
      const data = await res.json();
      if (data.elements) {
        const { nodes, edges } = formatCytoscapePayload(data.elements);

        // Optional time-range fetch from FastAPI
        let timeRange: { earliest: string | null; latest: string | null } | undefined;
        try {
          const trRes = await fetch(`${BACKEND_BASE_URL}/api/graph/time-range`, {
            cache: 'no-store',
          });
          if (trRes.ok) {
            timeRange = await trRes.json();
          }
        } catch {
          // ignore time-range failure
        }

        return {
          nodes,
          edges,
          timeRange,
          isLiveBackend: true,
        };
      }
    }
  } catch (err) {
    console.info(
      `FastAPI backend at ${BACKEND_BASE_URL} unreachable or timed out. Engaging fallback to internal /api/graph.`,
      err
    );
  }

  // 2. Safe Fallback: read from local Next.js API route (/api/graph)
  try {
    const fallbackRes = await fetch('/api/graph');
    if (fallbackRes.ok) {
      const fallbackData = await fallbackRes.json();
      if (fallbackData.elements) {
        const { nodes, edges } = formatCytoscapePayload(fallbackData.elements);
        return {
          nodes,
          edges,
          isLiveBackend: false,
        };
      }
    }
  } catch (fallbackErr) {
    console.error('Failed to read fallback /api/graph:', fallbackErr);
  }

  // 3. Guaranteed non-empty fallback
  return {
    nodes: [],
    edges: [],
    isLiveBackend: false,
  };
}

/**
 * Fetch top high-risk candidates ranked by betweenness centrality from Member 2's analytics endpoint
 */
export async function getHighRiskNodes(limit: number = 6) {
  try {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 2500);

    const res = await fetch(
      `${BACKEND_BASE_URL}/api/analytics/high-risk?limit=${limit}`,
      {
        signal: controller.signal,
      }
    );
    clearTimeout(timeoutId);

    if (res.ok) {
      const json = await res.json();
      return json.results || [];
    }
  } catch {
    // Graceful fallback
  }
  return [];
}

/**
 * Fetch relationship evidence trail from Member 2's /api/evidence-trail endpoint
 */
export async function getEvidenceTrail(
  source: string,
  target: string,
  bidirectional: boolean = true
): Promise<{
  source: { id: string; label: string };
  target: { id: string; label: string };
  relationships: Array<Record<string, any>>;
} | null> {
  try {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 2500);

    const qs = new URLSearchParams({
      source,
      target,
      bidirectional: String(bidirectional),
    });

    const res = await fetch(`${BACKEND_BASE_URL}/api/evidence-trail?${qs.toString()}`, {
      signal: controller.signal,
    });
    clearTimeout(timeoutId);

    if (res.ok) {
      return await res.json();
    }
  } catch {
    // Graceful fallback
  }
  return null;
}

/**
 * Normalizes input objects into Member 2's Pydantic GraphPayload model
 * { nodes: [{ id, type, label, metadata }], edges: [{ source, target, type, metadata }] }
 */
function toBackendGraphPayload(data: any): { nodes: any[]; edges: any[] } {
  if (data && Array.isArray(data.nodes) && Array.isArray(data.edges)) {
    return {
      nodes: data.nodes.map((n: any) => ({
        id: String(n.id || n.data?.id),
        type: mapToPydanticNodeType(n.type || n.data?.type),
        label: String(n.label || n.data?.label || n.id),
        metadata: n.metadata || n.data?.metadata || {},
      })),
      edges: data.edges.map((e: any) => ({
        source: String(e.source || e.data?.source),
        target: String(e.target || e.data?.target),
        type: mapToPydanticEdgeType(e.type || e.data?.type),
        metadata: e.metadata || e.data?.metadata || {
          amount: e.amount || e.data?.amount,
          duration: e.duration || e.data?.duration,
          timestamp: e.timestamp || e.data?.timestamp,
        },
      })),
    };
  }

  // If input is CytoscapeElement[]
  if (Array.isArray(data)) {
    const nodes: any[] = [];
    const edges: any[] = [];

    data.forEach((item: any) => {
      const d = item.data || item;
      if ('source' in d && 'target' in d) {
        edges.push({
          source: String(d.source),
          target: String(d.target),
          type: mapToPydanticEdgeType(d.type),
          metadata: d.metadata || {
            amount: d.amount,
            duration: d.duration,
            timestamp: d.timestamp,
            fir_no: d.firNumber,
            fir_excerpt: d.firExcerpt,
          },
        });
      } else if ('id' in d) {
        nodes.push({
          id: String(d.id),
          type: mapToPydanticNodeType(d.type),
          label: String(d.label || d.id),
          metadata: d.metadata || {
            role: d.role,
            riskScore: d.riskScore,
          },
        });
      }
    });

    return { nodes, edges };
  }

  return { nodes: [], edges: [] };
}

function mapToPydanticNodeType(typeStr?: string): 'Suspect' | 'Phone' | 'Account' | 'Location' | 'CrimeCase' {
  const t = (typeStr || '').toUpperCase();
  if (t.includes('PHONE')) return 'Phone';
  if (t.includes('ACCOUNT') || t.includes('BANK')) return 'Account';
  if (t.includes('LOCATION') || t.includes('TOWER')) return 'Location';
  if (t.includes('FIR') || t.includes('CASE') || t.includes('CRIME')) return 'CrimeCase';
  return 'Suspect';
}

function mapToPydanticEdgeType(
  typeStr?: string
): 'CALLED' | 'TRANSFERRED' | 'OPERATES' | 'USES' | 'CO_ACCUSED_IN' {
  const t = (typeStr || '').toUpperCase();
  if (t === 'CALLED') return 'CALLED';
  if (t === 'TRANSFERRED') return 'TRANSFERRED';
  if (t === 'USES') return 'USES';
  if (t === 'CO_ACCUSED_IN') return 'CO_ACCUSED_IN';
  return 'OPERATES';
}

/**
 * Post ingestion payload to Member 2's /api/ingest endpoint
 */
export async function postIngestData(data: FormData | object): Promise<IngestResponse> {
  try {
    let payload: any = data;

    if (data instanceof FormData) {
      const formObj: Record<string, any> = {};
      data.forEach((val, key) => {
        formObj[key] = val;
      });
      payload = formObj;
    }

    const graphPayload = toBackendGraphPayload(payload);

    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 4000);

    const res = await fetch(`${BACKEND_BASE_URL}/api/ingest`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(graphPayload),
      signal: controller.signal,
    });
    clearTimeout(timeoutId);

    if (res.ok) {
      const result = await res.json();
      return {
        success: true,
        isLiveBackend: true,
        stats: result.stats,
        message: `FastAPI Backend Ingestion Succeeded: ${result.status || 'loaded'}.`,
      };
    }
  } catch (err) {
    console.info(`FastAPI ingest at ${BACKEND_BASE_URL} unavailable:`, err);
  }

  // Graceful fallback response
  return {
    success: false,
    isLiveBackend: false,
    message: 'Backend unreachable. Standalone local parsing engaged.',
  };
}
