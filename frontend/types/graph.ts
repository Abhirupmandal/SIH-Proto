export type NodeType =
  | 'SUSPECT'
  | 'BANK_ACCOUNT'
  | 'PHONE'
  | 'FIR'
  | 'LOCATION'
  | 'VEHICLE'
  | string;

export type EdgeType =
  | 'CALLED'
  | 'TRANSFERRED'
  | 'CO_ACCUSED_IN'
  | 'USES'
  | 'OPERATES'
  | string;

export interface GraphNodeData {
  id: string;
  label: string;
  type: NodeType;
  riskScore?: number;
  role?: string;
  metadata?: Record<string, unknown>;
  x?: number;
  y?: number;
}

export interface GraphEdgeData {
  id: string;
  source: string;
  target: string;
  type: EdgeType;
  sourceLabel?: string;
  targetLabel?: string;
  sourceType?: NodeType;
  targetType?: NodeType;
  // Specific properties for CALLED
  timestamp?: string;
  duration?: number; // duration in seconds
  callerImei?: string;
  cellTowerId?: string;
  // Specific properties for TRANSFERRED
  transactionId?: string;
  amount?: number;
  ledgerTimestamp?: string;
  // Specific properties for CO_ACCUSED_IN
  firNumber?: string;
  policeStation?: string;
  firExcerpt?: string;
  // Generic metadata and XAI properties
  confidenceScore?: number;
  metadata?: Record<string, unknown>;
  reasoningNote?: string;
}

export interface GraphData {
  nodes: GraphNodeData[];
  edges: GraphEdgeData[];
}
