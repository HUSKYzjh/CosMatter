import { describe, expect, it } from "vitest";

import { gapEvidenceReferences } from "./gapEvidenceReferences";
import type { EvidenceCard, ResearchGapCandidate } from "./model";

const card = (id: string): EvidenceCard => ({ evidenceId: id, claim: "claim", stance: "support", conditions: {}, quote: "short quote", reviewStatus: "accepted", provenance: { documentId: `doc-${id}`, locator: "markdown_line:1-1", source: "reviewed", accessPolicy: "authorized" }, isSynthetic: false });
const candidate: ResearchGapCandidate = { gapId: "gap-1", problemDescription: "conflict", evidenceIds: ["ev-1", "ev-missing", "ev-2"], conflictOrMissingEvidence: ["unknown boundary"], noveltyStatus: "unreviewed", actionability: "human review", falsifiableHypothesis: "test", suggestedValidation: ["compare"], evidenceCompleteness: 0.5, reviewStatus: "candidate_requires_human_review" };

describe("gapEvidenceReferences", () => {
  it("preserves the candidate evidence order and reports unresolved IDs", () => {
    const result = gapEvidenceReferences(candidate, [card("ev-2"), card("ev-1")]);
    expect(result.linked.map((item) => item.evidenceId)).toEqual(["ev-1", "ev-2"]);
    expect(result.missingIds).toEqual(["ev-missing"]);
  });
});