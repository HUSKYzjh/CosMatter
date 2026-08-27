import type { LiteratureGraphEdge, LiteratureGraphNode } from "./model";
import { documentIdForReviewablePaper } from "./evidenceLinking";

export type LiteratureGraphMode = "evidence" | "bibliography" | "empty";

/**
 * Distinguish a reviewable paper/evidence map from a DOI citation map.
 * Citation metadata is navigable, but never grants the evidence-reading gate.
 */
export function literatureGraphMode(nodes: LiteratureGraphNode[], edges: LiteratureGraphEdge[]): LiteratureGraphMode {
  if (nodes.some((node) => Boolean(documentIdForReviewablePaper(node)))) return "evidence";
  const citationNodes = nodes.some((node) => node.kind === "citation_work");
  const citationEdges = edges.some((edge) => edge.edgeType === "citation_reference" || edge.edgeType === "citation_cited_by");
  return citationNodes && citationEdges ? "bibliography" : "empty";
}
