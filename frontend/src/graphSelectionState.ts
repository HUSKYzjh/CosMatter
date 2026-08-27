import type { LiteratureGraphEdge, LiteratureGraphNode } from "./model";

export function graphSelectionVisibility(selectedNodeId: string | null, allNodes: LiteratureGraphNode[], visibleNodes: LiteratureGraphNode[]): { exists: boolean; visible: boolean } {
  if (!selectedNodeId) return { exists: false, visible: false };
  return {
    exists: allNodes.some((node) => node.nodeId === selectedNodeId),
    visible: visibleNodes.some((node) => node.nodeId === selectedNodeId),
  };
}

export function graphEdgeStillExists(selected: LiteratureGraphEdge | null, edges: LiteratureGraphEdge[]): boolean {
  if (!selected) return true;
  return edges.some((edge) => edge.sourceId === selected.sourceId && edge.targetId === selected.targetId && edge.edgeType === selected.edgeType && edge.relationSource === selected.relationSource);
}