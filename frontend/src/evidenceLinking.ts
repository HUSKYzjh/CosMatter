import type { EvidenceCard, ImportedBundle, LiteratureGraphNode } from "./model";
const REVIEWABLE_PAPER_KINDS = new Set(["candidate_paper", "evidence_paper", "structured_paper"]);

/**
 * Return a document identifier only for a declared reviewable-paper node that
 * follows the explicit graph projection convention. Citation-navigation nodes
 * may help locate a paper, but cannot silently become a private PDF task,
 * source map, or EvidenceCard provenance record.
 */
export function documentIdForReviewablePaper(node: LiteratureGraphNode | null): string | null {
  if (!node || !REVIEWABLE_PAPER_KINDS.has(node.kind) || !node.nodeId.startsWith("paper:")) return null;
  const documentId = node.nodeId.slice("paper:".length).trim();
  return documentId ? documentId : null;
}

export function reviewablePaperForDocumentId(nodes: LiteratureGraphNode[], documentId: string): LiteratureGraphNode | null {
  const normalized = documentId.trim();
  if (!normalized) return null;
  return nodes.find((node) => documentIdForReviewablePaper(node) === normalized) ?? null;
}
/**
 * The graph is the authoritative UI projection of paper-to-EvidenceCard
 * provenance.  A matching string alone is intentionally insufficient: a
 * card becomes selectable for a paper only when the projection contains the
 * reviewed `source_provenance` edge.
 */
/**
 * A provenance edge is an auditable reader handoff only after the graph
 * projection labels it as accepted evidence.  A similarly shaped candidate,
 * parser, or import edge must never unlock EvidenceCard review.
 */
export function isAcceptedProvenanceEdge(edge: { edgeType: string; trustStatus: string }): boolean {
  return edge.edgeType === "source_provenance"
    && ["accepted", "accepted_evidence", "human_reviewed_accepted_evidence_card"].includes(edge.trustStatus.trim());
}

export function evidenceForPaper(bundle: ImportedBundle, paper: LiteratureGraphNode | null): EvidenceCard[] {
  const documentId = documentIdForReviewablePaper(paper);
  if (!paper || !documentId) return [];
  return bundle.evidenceCards.filter((evidence) => {
    const paperId = `paper:${documentId}`;
    const evidenceId = `evidence:${evidence.evidenceId}`;
    return evidence.reviewStatus === "accepted"
      && evidence.provenance.documentId === documentId
      && paper.nodeId === paperId
      && bundle.literatureGraph.edges.some((edge) => (
        edge.sourceId === paperId
        && edge.targetId === evidenceId
        && isAcceptedProvenanceEdge(edge)
      ));
  });
}

export function evidenceMatchesPaper(bundle: ImportedBundle, paper: LiteratureGraphNode | null, evidence: EvidenceCard | null): boolean {
  return Boolean(evidence && evidenceForPaper(bundle, paper).some((item) => item.evidenceId === evidence.evidenceId));
}

export function reviewablePaperCount(bundle: ImportedBundle): number {
  return bundle.literatureGraph.nodes.filter((node) => Boolean(documentIdForReviewablePaper(node))).length;
}
/**
 * Count only accepted cards that the visible graph can trace back to their
 * paper through a reviewed source_provenance edge. Imported card counts alone
 * must not unlock a cross-paper comparison.
 */
export function auditableAcceptedEvidence(bundle: ImportedBundle): EvidenceCard[] {
  const paperIds = new Set(bundle.literatureGraph.nodes.filter((node) => Boolean(documentIdForReviewablePaper(node))).map((node) => node.nodeId));
  const provenanceEdges = new Set(bundle.literatureGraph.edges.filter(isAcceptedProvenanceEdge).map((edge) => `${edge.sourceId}\u241f${edge.targetId}`));
  const reviewedSourceMapDocuments = new Set(bundle.sourceMapSummary.documentIds);
  const sourceMapInventoryIsUsable = bundle.sourceMapSummary.segmentCount > 0
    && bundle.sourceMapSummary.documentCount === reviewedSourceMapDocuments.size;
  return bundle.evidenceCards.filter((card) => card.reviewStatus === "accepted" && Boolean(card.provenance.documentId.trim()) && Boolean(card.provenance.locator.trim()) && sourceMapInventoryIsUsable && reviewedSourceMapDocuments.has(card.provenance.documentId) && paperIds.has(`paper:${card.provenance.documentId}`) && provenanceEdges.has(`paper:${card.provenance.documentId}\u241fevidence:${card.evidenceId}`));
}
