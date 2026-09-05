import { documentIdForReviewablePaper } from "./evidenceLinking";
import type { LiteratureGraphNode } from "./model";
import type { PaperWorkflowState } from "./paperWorkflowState";

export type ReadingRouteAction = "recover-pdf" | "register-source-map" | "review-evidence" | "audit-provenance" | "verify-evidence" | "select-pdf" | "screen-paper" | "load-screening" | "wait-for-parse";
export type TaskTitleAnchorMatch = "material" | "context" | "none";

export interface ReadingRouteTaskAnchors {
  material?: string | null;
  property?: string | null;
  scope?: string | null;
}

export interface ReadingRouteEntry {
  ordinal: number;
  nodeId: string;
  documentId: string;
  title: string;
  workflowState: PaperWorkflowState;
  action: ReadingRouteAction;
  titleAnchorMatch: TaskTitleAnchorMatch;
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

const TITLE_ANCHOR_PRIORITY: Record<TaskTitleAnchorMatch, number> = {
  material: 0,
  context: 1,
  none: 2,
};

const GENERIC_ANCHOR_TERMS = new Set([
  "analysis", "different", "effect", "effects", "material", "materials", "measurement", "properties", "property", "research", "sample", "samples", "study", "temperature",
  "不同", "分析", "影响", "性能", "材料", "样品", "测量", "温度", "研究",
]);

function normalizeAnchorText(value: string): string {
  return value
    .normalize("NFKC")
    .toLocaleLowerCase()
    .replace(/<[^>]+>/g, " ")
    .replace(/&(?:amp|lt|gt|quot|apos|nbsp|#\d+|#x[\da-f]+);/g, " ")
    .replace(/[^a-z0-9\u3400-\u9fff]+/g, " ")
    .trim();
}

function anchorTerms(value: string | null | undefined): string[] {
  if (!value) return [];
  return [...new Set(normalizeAnchorText(value).split(/\s+/).filter((term) => term.length >= 2 && !GENERIC_ANCHOR_TERMS.has(term)))];
}

function titleMatches(title: string, terms: readonly string[]): boolean {
  const normalizedTitle = normalizeAnchorText(title);
  const compactTitle = normalizedTitle.replace(/\s+/g, "");
  return terms.some((term) => normalizedTitle.includes(term) || compactTitle.includes(term.replace(/\s+/g, "")));
}

function taskTitleAnchorMatch(title: string, anchors: ReadingRouteTaskAnchors): TaskTitleAnchorMatch {
  if (titleMatches(title, anchorTerms(anchors.material))) return "material";
  if (titleMatches(title, [...anchorTerms(anchors.property), ...anchorTerms(anchors.scope)])) return "context";
  return "none";
}

/**
 * A deterministic local reading queue. It is a navigation aid only: entries
 * are derived from the visible reviewable-paper projection and recorded
 * workflow state. Task-title anchors only break ties between equal workflow
 * actions; they are not a model/provider score or a scientific relevance claim.
 */
export function readingRoute(
  nodes: readonly LiteratureGraphNode[],
  paperStates: Readonly<Record<string, PaperWorkflowState>>,
  limit = 6,
  taskAnchors: ReadingRouteTaskAnchors = {},
): ReadingRouteEntry[] {
  return nodes.flatMap((node) => {
    const documentId = documentIdForReviewablePaper(node);
    const workflowState = paperStates[node.nodeId] ?? "untracked";
    if (!documentId || workflowState === "excluded") return [];
    return [{
      nodeId: node.nodeId,
      documentId,
      title: node.label,
      workflowState,
      action: ROUTE_ACTION[workflowState],
      titleAnchorMatch: taskTitleAnchorMatch(node.label, taskAnchors),
    }];
  }).sort((left, right) => PRIORITY[left.action] - PRIORITY[right.action]
      || TITLE_ANCHOR_PRIORITY[left.titleAnchorMatch] - TITLE_ANCHOR_PRIORITY[right.titleAnchorMatch]
      || left.title.localeCompare(right.title)
      || left.nodeId.localeCompare(right.nodeId))
    .slice(0, Math.max(0, limit))
    .map((entry, index) => ({ ...entry, ordinal: index + 1 }));
}
