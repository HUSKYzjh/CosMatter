import { describe, expect, it } from "vitest";

import { gapEvidenceReferences, hasAuditableGapEvidenceBasis } from "./gapEvidenceReferences";
import { demoBundle, type EvidenceCard, type ResearchGapCandidate } from "./model";

const card = (id: string): EvidenceCard => ({ evidenceId: id, claim: "claim", stance: "support", conditions: {}, quote: "short quote", reviewStatus: "accepted", provenance: { documentId: `doc-${id}`, locator: "markdown_line:1-1", source: "reviewed", accessPolicy: "authorized" }, isSynthetic: false });
const candidate: ResearchGapCandidate = { gapId: "gap-1", problemDescription: "conflict", evidenceIds: ["ev-1", "ev-missing", "ev-2"], conflictOrMissingEvidence: ["unknown boundary"], noveltyStatus: "unreviewed", actionability: "human review", falsifiableHypothesis: "test", suggestedValidation: ["compare"], evidenceCompleteness: 0.5, reviewStatus: "candidate_requires_human_review" };

describe("gapEvidenceReferences", () => {
  it("preserves the candidate evidence order and reports unresolved IDs", () => {
    const result = gapEvidenceReferences(candidate, [card("ev-2"), card("ev-1")]);
    expect(result.linked.map((item) => item.evidenceId)).toEqual(["ev-1", "ev-2"]);
    expect(result.missingIds).toEqual(["ev-missing"]);
  });

  it("requires every candidate basis ID to resolve to current auditable evidence", () => {
    const cards = [card("ev-1"), card("ev-2")];
    const bundle = {
      ...demoBundle,
      evidenceCards: cards,
      sourceMapSummary: { documentCount: 2, segmentCount: 2, documentIds: ["doc-ev-1", "doc-ev-2"] },
      literatureGraph: { ...demoBundle.literatureGraph, nodes: cards.map((item) => ({ nodeId: `paper:${item.provenance.documentId}`, kind: "evidence_paper", label: item.provenance.documentId, trustStatus: "reviewed" })), edges: cards.map((item) => ({ sourceId: `paper:${item.provenance.documentId}`, targetId: `evidence:${item.evidenceId}`, edgeType: "source_provenance", relationSource: "reviewed", trustStatus: "accepted" })) },
    };
    expect(hasAuditableGapEvidenceBasis({ ...candidate, evidenceIds: ["ev-1", "ev-2"] }, bundle)).toBe(true);
    expect(hasAuditableGapEvidenceBasis(candidate, bundle)).toBe(false);
  });
});
