import { documentIdForReviewablePaper } from "./evidenceLinking";
import type { LiteratureGraphNode } from "./model";
import type { PaperWorkflowState } from "./paperWorkflowState";

export type ReadingRouteAction = "recover-pdf" | "register-source-map" | "review-evidence" | "audit-provenance" | "verify-evidence" | "select-pdf" | "screen-paper" | "load-screening" | "wait-for-parse";
export type TaskTitleAnchorMatch = "material-and-context" | "context" | "material" | "none";

export interface ReadingRouteTaskAnchors {
  material?: string | null;
  property?: string | null;
  scope?: string | null;
  question?: string | null;
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
  "material-and-context": 0,
  material: 1,
  context: 2,
  none: 3,
};

const GENERIC_ANCHOR_TERMS = new Set([
  "analysis", "different", "effect", "effects", "material", "materials", "measurement", "properties", "property", "research", "sample", "samples", "study", "temperature",
  "不同", "分析", "影响", "性能", "材料", "样品", "测量", "温度", "研究",
]);

function normalizeAnchorText(value: string): string {
  return value
    .normalize("NFKD")
    .replace(/\p{M}/gu, "")
    .normalize("NFKC")
    .toLocaleLowerCase()
    .replace(/\[!?\/?sub\]/g, "")
    .replace(/<[^>]+>/g, " ")
    .replace(/&(?:amp|lt|gt|quot|apos|nbsp|#\d+|#x[\da-f]+);/g, " ")
    .replace(/[^a-z0-9\u3400-\u9fff]+/g, " ")
    .trim();
}

const CONTEXT_ALIASES: ReadonlyArray<{ pattern: RegExp; aliases: readonly string[] }> = [
  { pattern: /相转变|相变|phase transition|phase stability|structural phase/, aliases: ["phase transition", "phase transitions", "phase diagram", "phase stability", "structural transition", "structural transitions"] },
  { pattern: /居里|curie/, aliases: ["curie", "ferroelectric transition", "ferroelectric transitions"] },
  { pattern: /奈尔|neel/, aliases: ["neel", "antiferromagnetic transition", "antiferromagnetic transitions", "magnetic transition", "magnetic behavior", "magnetic ordering"] },
  { pattern: /应变|strain/, aliases: ["strain", "strained", "misfit", "film thickness"] },
  { pattern: /氧空位|oxygen vacanc/, aliases: ["oxygen vacancy", "oxygen vacancies", "oxygen deficient", "vacancy ordering"] },
  { pattern: /缺陷|defect/, aliases: ["defect", "defects", "disorder"] },
  { pattern: /循环稳定性|cycling stability|cycle life/, aliases: ["cycling stability", "cycle life", "capacity retention"] },
  { pattern: /带隙|band gap/, aliases: ["band gap", "electronic structure", "optical properties"] },
];

function contextAnchorTerms(anchors: ReadingRouteTaskAnchors): string[] {
  const context = normalizeAnchorText(`${anchors.question ?? ""} ${anchors.property ?? ""} ${anchors.scope ?? ""}`);
  const explicit = [...anchorTerms(anchors.property), ...anchorTerms(anchors.scope)];
  const aliases = CONTEXT_ALIASES.flatMap((entry) => entry.pattern.test(context) ? entry.aliases : []);
  return [...new Set([...explicit, ...aliases].map(normalizeAnchorText).filter(Boolean))];
}

function anchorTerms(value: string | null | undefined): string[] {
  if (!value) return [];
  return [...new Set(normalizeAnchorText(value).split(/\s+/).filter((term) => term.length >= 2 && !GENERIC_ANCHOR_TERMS.has(term)))];
}

function titleMatches(title: string, terms: readonly string[]): boolean {
  const normalizedTitle = normalizeAnchorText(title);
  const compactTitle = normalizedTitle.replace(/\s+/g, "");
  const titleTokens = new Set(normalizedTitle.split(/\s+/).filter(Boolean));
  return terms.some((rawTerm) => {
    const term = normalizeAnchorText(rawTerm);
    if (!term) return false;
    const compactTerm = term.replace(/\s+/g, "");
    if (/[\u3400-\u9fff]/.test(term)) return normalizedTitle.includes(term) || compactTitle.includes(compactTerm);
    if (term.includes(" ")) return normalizedTitle.includes(term) || compactTitle.includes(compactTerm);
    if (/\d/.test(term)) return titleTokens.has(term) || compactTitle.includes(compactTerm);
    return titleTokens.has(term);
  });
}

function formulaAnchorTerms(value: string | null | undefined): string[] {
  if (!value) return [];
  const formulas = value.normalize("NFKC").match(/\b(?:[A-Z][a-z]?\d*){2,}\b/g) ?? [];
  return [...new Set(formulas.map(normalizeAnchorText).filter(Boolean))];
}

function materialTitleMatches(title: string, material: string | null | undefined): boolean {
  const formulas = formulaAnchorTerms(material);
  if (formulas.length && titleMatches(title, formulas)) return true;
  const materialCompact = normalizeAnchorText(material ?? "").replace(/\s+/g, "");
  if (materialCompact.includes("bifeo3")) {
    const titleCompact = normalizeAnchorText(title).replace(/\s+/g, "");
    return titleCompact.includes("bismuthferrite") || /bi[a-z0-9]{0,14}fe[a-z0-9]{0,14}o3/.test(titleCompact);
  }
  return formulas.length ? false : titleMatches(title, anchorTerms(material));
}

function taskTitleAnchorMatch(title: string, anchors: ReadingRouteTaskAnchors): TaskTitleAnchorMatch {
  const materialMatches = materialTitleMatches(title, anchors.material);
  const contextMatches = titleMatches(title, contextAnchorTerms(anchors));
  if (materialMatches && contextMatches) return "material-and-context";
  if (contextMatches) return "context";
  if (materialMatches) return "material";
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
  return nodes.flatMap((node, sourceOrder) => {
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
      sourceOrder,
    }];
  }).sort((left, right) => PRIORITY[left.action] - PRIORITY[right.action]
      || TITLE_ANCHOR_PRIORITY[left.titleAnchorMatch] - TITLE_ANCHOR_PRIORITY[right.titleAnchorMatch]
      || left.sourceOrder - right.sourceOrder)
    .slice(0, Math.max(0, limit))
    .map((entry, index) => ({
      ordinal: index + 1,
      nodeId: entry.nodeId,
      documentId: entry.documentId,
      title: entry.title,
      workflowState: entry.workflowState,
      action: entry.action,
      titleAnchorMatch: entry.titleAnchorMatch,
    }));
}
