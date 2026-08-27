import { describe, expect, it } from "vitest";

import { gapCandidatesForEvidence } from "./gapLinking";
import type { EvidenceCard, ResearchGapCandidate } from "./model";

const evidence: EvidenceCard = { evidenceId: "ev-1", claim: "claim", stance: "supports", conditions: {}, quote: "quote", reviewStatus: "accepted", provenance: { documentId: "doc-1", locator: "p.1", source: "local", accessPolicy: "authorized" }, isSynthetic: false };
const candidate = (gapId: string, evidenceIds: string[]): ResearchGapCandidate => ({ gapId, problemDescription: "candidate", evidenceIds, conflictOrMissingEvidence: ["missing condition"], noveltyStatus: "unverified", actionability: "review", falsifiableHypothesis: "test", suggestedValidation: ["compare"], evidenceCompleteness: 0.5, reviewStatus: "candidate_requires_human_review" });

describe("gapCandidatesForEvidence", () => {
  it("keeps the current reading session scoped to its selected evidence", () => {
    expect(gapCandidatesForEvidence([candidate("gap-linked", ["ev-1"]), candidate("gap-other", ["ev-2"])], evidence).map((item) => item.gapId)).toEqual(["gap-linked"]);
    expect(gapCandidatesForEvidence([candidate("gap-other", ["ev-2"])], evidence)).toEqual([]);
  });
});
