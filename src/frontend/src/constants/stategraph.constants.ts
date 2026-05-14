/**
 * StateGraph Constants - T-1807
 * 
 * Defines the 8 nodes of the LangGraph validation workflow
 * and mapping logic for events → progress steps.
 */

import type { ProgressStep } from '../types/upload';

/**
 * StateGraph node names (must match backend src/agent/graph/nodes.py)
 */
export const STATEGRAPH_NODES = [
  'ExtractGeometry',
  'ValidateNomenclature',
  'ValidateGeometry',
  'ClassifyTipologia',
  'EnrichMetadata',
  'GenerateReport',
  'MarkValidated',
  'MarkRejected',
] as const;

export type StateGraphNode = typeof STATEGRAPH_NODES[number];

/**
 * Display labels for each node (Spanish for UI)
 */
export const NODE_LABELS: Record<StateGraphNode, string> = {
  ExtractGeometry: 'Extracción Geometría',
  ValidateNomenclature: 'Validación Nomenclatura',
  ValidateGeometry: 'Validación Geometría',
  ClassifyTipologia: 'Clasificación Tipología',
  EnrichMetadata: 'Enriquecimiento Metadatos',
  GenerateReport: 'Generación Reporte',
  MarkValidated: 'Marca Validado',
  MarkRejected: 'Marca Rechazado',
};

/**
 * Event types from backend events table (src/backend/schemas.py EventType enum)
 */
export enum EventType {
  GRAPH_STARTED = 'GRAPH_STARTED',
  NODE_ENTERED = 'NODE_ENTERED',
  NODE_COMPLETED = 'NODE_COMPLETED',
  NODE_FAILED = 'NODE_FAILED',
  TRANSITION_CONDITIONAL = 'TRANSITION_CONDITIONAL',
  FALLBACK_ACTIVATED = 'FALLBACK_ACTIVATED',
  GRAPH_COMPLETED = 'GRAPH_COMPLETED',
  GRAPH_FAILED = 'GRAPH_FAILED',
}

/**
 * Map event type to step status
 */
export function mapEventTypeToStepStatus(eventType: EventType): 'active' | 'completed' | 'error' | 'warning' {
  switch (eventType) {
    case EventType.NODE_ENTERED:
      return 'active';
    case EventType.NODE_COMPLETED:
      return 'completed';
    case EventType.NODE_FAILED:
      return 'error';
    case EventType.FALLBACK_ACTIVATED:
      return 'warning';
    default:
      return 'active';
  }
}

/**
 * Map node name to step index (0-7)
 */
export function getStepIndexByNodeName(nodeName: string): number {
  const index = STATEGRAPH_NODES.indexOf(nodeName as StateGraphNode);
  return index >= 0 ? index : -1;
}

/**
 * Initial progress steps (all idle)
 */
export function createInitialSteps(): ProgressStep[] {
  return STATEGRAPH_NODES.map((nodeName, index) => ({
    index,
    nodeName,
    label: NODE_LABELS[nodeName],
    status: 'idle',
    startedAt: null,
    completedAt: null,
  }));
}

/**
 * Ant Design Steps component status mapping
 */
export function mapStepStatusToAntStatus(
  stepStatus: ProgressStep['status']
): 'wait' | 'process' | 'finish' | 'error' {
  switch (stepStatus) {
    case 'idle':
      return 'wait';
    case 'active':
      return 'process';
    case 'completed':
    case 'warning':
      return 'finish';
    case 'error':
      return 'error';
  }
}
