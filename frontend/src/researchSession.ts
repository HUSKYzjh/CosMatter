import type { EvidenceCard, ImportedBundle, LiteratureGraphNode } from "./model";
import { documentIdForReviewablePaper, evidenceMatchesPaper } from "./evidenceLinking";
import { evidenceProvenanceAuditComplete } from "./evidenceProvenanceAudit";

export interface ResearchSession {
  selectedNode: LiteratureGraphNode | null;
  documentId: string | null;
  evidenceId: string | null;
  conditionCluster: string | null;
  gateMessage: string | null;
}

export const emptyResearchSession = (): ResearchSession => ({ selectedNode: null, documentId: null, evidenceId: null, conditionCluster: null, gateMessage: null });

export function selectPaper(session: ResearchSession, selectedNode: LiteratureGraphNode): ResearchSession {
  // A graph selection becomes a verification session only when it is an
  // explicit reviewable-paper projection. Graph IDs never become source-map
  // document IDs by themselves.
  if (!documentIdForReviewablePaper(selectedNode)) return emptyResearchSession();
  return { ...session, selectedNode, documentId: null, evidenceId: null, conditionCluster: null, gateMessage: null };
}

export function selectEvidence(session: ResearchSession, evidence: EvidenceCard): ResearchSession {
  return { ...session, evidenceId: evidence.evidenceId, documentId: evidence.provenance.documentId, gateMessage: null };
}

export function selectedEvidence(bundle: ImportedBundle, session: ResearchSession): EvidenceCard | null {
  return bundle.evidenceCards.find((item) => item.evidenceId === session.evidenceId) ?? null;
}

export function evidenceGate(bundle: ImportedBundle, session: ResearchSession): { ready: boolean; reason: "paper" | "evidence" | "source-link" | "locator" | "source-map" | "provenance-audit" | null } {
  if (!session.selectedNode) return { ready: false, reason: "paper" };
  const evidence = selectedEvidence(bundle, session);
  if (!evidence) return { ready: false, reason: "evidence" };
  if (!evidenceMatchesPaper(bundle, session.selectedNode, evidence)) return { ready: false, reason: "source-link" };
  if (!evidence.provenance.documentId.trim() || !evidence.provenance.locator.trim()) return { ready: false, reason: "locator" };
  if (bundle.sourceMapSummary.segmentCount < 1 || !bundle.sourceMapSummary.documentIds.includes(evidence.provenance.documentId)) return { ready: false, reason: "source-map" };
  // UI receives no Source Map excerpts. Require the backend's quote-free exact-match audit before a current-session card appears verified.
  const acceptedEvidenceCount = bundle.evidenceCards.filter((item) => item.reviewStatus === "accepted").length;
  if (!evidenceProvenanceAuditComplete(bundle.auditSummary.evidenceProvenance, acceptedEvidenceCount)) return { ready: false, reason: "provenance-audit" };
  return { ready: true, reason: null };
}
/**
 * Keep only a session selection that still exists in a freshly imported UI
 * projection.  This preserves a researcher’s place after a local audit write
 * without carrying a stale paper ID or EvidenceCard across an artifact change.
 */
export function reconcileResearchSession(bundle: ImportedBundle, session: ResearchSession): ResearchSession {
  if (!session.selectedNode) return emptyResearchSession();
  const paper = bundle.literatureGraph.nodes.find((node) => node.nodeId === session.selectedNode!.nodeId) ?? null;
  if (!paper) return emptyResearchSession();
  let next = selectPaper(emptyResearchSession(), paper);
  const evidence = selectedEvidence(bundle, session);
  if (evidence && evidenceMatchesPaper(bundle, paper, evidence)) next = selectEvidence(next, evidence);
  return next;
}
