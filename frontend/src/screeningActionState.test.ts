import { describe, expect, it } from "vitest";

import { shouldPromptForScreening } from "./screeningActionState";
import type { CandidateScreening } from "./localApi";

const base: CandidateScreening = { run_id: "run-1", candidate_count: 1, candidates: [{ document_id: "paper-1", title: "Paper", source: "fixture", publication_year: 2024 }], decisions: [], trust_status: "candidate_metadata_not_scientific_evidence" as const };
describe("shouldPromptForScreening", () => {
  it("prompts to load the checklist when reviewable papers exist but it is not loaded", () => { expect(shouldPromptForScreening(true, true, null)).toBe(true); });
  it("does not expose a screening action without a reviewable map or enabled API", () => { expect(shouldPromptForScreening(false, true, null)).toBe(false); expect(shouldPromptForScreening(true, false, null)).toBe(false); });
  it("remains visible only while at least one candidate lacks a recorded decision", () => { expect(shouldPromptForScreening(true, true, base)).toBe(true); const complete: CandidateScreening = { ...base, decisions: [{ document_id: "paper-1", decision: "exclude", reason_codes: ["out_of_scope_material"] }], trust_status: "human_reviewed_candidate_screening_not_scientific_evidence" }; expect(shouldPromptForScreening(true, true, complete)).toBe(false); });
});
