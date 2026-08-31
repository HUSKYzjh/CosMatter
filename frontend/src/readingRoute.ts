import { documentIdForReviewablePaper } from "./evidenceLinking";
import type { LiteratureGraphNode } from "./model";
import type { PaperWorkflowState } from "./paperWorkflowState";

export type ReadingRouteAction = "recover-pdf" | "register-source-map" | "review-evidence" | "audit-provenance" | "verify-evidence" | "select-pdf" | "screen-paper" | "load-screening" | "wait-for-parse";

export interface ReadingRouteEntry {
  ordinal: number;
  nodeId: string;
  documentId: string;
  title: string;
  workflowState: PaperWorkflowState;
  action: ReadingRouteAction;
}

const ROUTE_ACTION: Record<PaperWorkflowState, ReadingRouteAction> = {
  failed: "recover-pdf",
  source_map: "register-source-map",
  evidence_review: "review-evidence",
  provenance_audit: "audit-provenance",
  accepted_evidence: "verify-evidence",
  included: "select-pdf",
  screening: "screen-paper",
  untracked: "load-screening",
  parsing: "wait-for-parse",
  excluded: "screen-paper",
};

const PRIORITY: Record<ReadingRouteAction, number> = {
  "recover-pdf": 0,
  "register-source-map": 1,
  "review-evidence": 2,
  "audit-provenance": 3,
  "verify-evidence": 4,
  "select-pdf": 5,
  "screen-paper": 6,
  "load-screening": 7,
  "wait-for-parse": 8,
};

/**
 * A deterministic local reading queue. It is a navigation aid only: entries
 * are derived from the visible reviewable-paper projection and recorded
 * workflow state, never from a model ranking or a scientific claim.
 */
export function readingRoute(
  nodes: readonly LiteratureGraphNode[],
  paperStates: Readonly<Record<string, PaperWorkflowState>>,
  limit = 6,
): ReadingRouteEntry[] {
  return nodes.flatMap((node) => {
    const documentId = documentIdForReviewablePaper(node);
    const workflowState = paperStates[node.nodeId] ?? "untracked";
    if (!documentId || workflowState === "excluded") return [];
    return [{ nodeId: node.nodeId, documentId, title: node.label, workflowState, action: ROUTE_ACTION[workflowState] }];
  }).sort((left, right) => PRIORITY[left.action] - PRIORITY[right.action] || left.title.localeCompare(right.title) || left.nodeId.localeCompare(right.nodeId))
    .slice(0, Math.max(0, limit))
    .map((entry, index) => ({ ...entry, ordinal: index + 1 }));
}
