import { documentIdForReviewablePaper } from "./evidenceLinking";
import type { LiteratureGraphNode } from "./model";

/** Locate the session's current reviewable paper without inferring a source link. */
export function graphNodeForSessionDocument(
  nodes: readonly LiteratureGraphNode[],
  documentId: string | null | undefined,
): LiteratureGraphNode | null {
  const normalized = documentId?.trim();
  if (!normalized) return null;
  return nodes.find((node) => documentIdForReviewablePaper(node) === normalized) ?? null;
}
