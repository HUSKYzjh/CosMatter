import { isPaperNode } from "./literatureTopology";
import type { LiteratureGraphEdge, LiteratureGraphNode } from "./model";

/** Repeated discovery from one question can be disclosed on selection. */
export function retrievalHubs(nodes: LiteratureGraphNode[], edges: LiteratureGraphEdge[]): Set<string> {
  const missions = new Set(nodes.filter(node => node.kind === "mission").map(node => node.nodeId));
  const papers = new Set(nodes.filter(isPaperNode).map(node => node.nodeId));
  const candidates = new Map<string, Set<string>>();
  for (const edge of edges) {
    if (edge.edgeType !== "retrieval_candidate" || !missions.has(edge.sourceId) || !papers.has(edge.targetId)) continue;
    const targets = candidates.get(edge.sourceId) ?? new Set<string>();
    targets.add(edge.targetId);
    candidates.set(edge.sourceId, targets);
  }
  return new Set([...candidates].filter(([, targets]) => targets.size >= 8).map(([id]) => id));
}
