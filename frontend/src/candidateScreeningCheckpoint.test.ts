import { describe, expect, it } from "vitest";
import { encodeCheckpoint, readCheckpoint } from "./candidateScreeningCheckpoint";
import type { CandidateScreening, CandidateScreeningDecision } from "./localApi";

const screening: CandidateScreening = {
  run_id: "test_run", checklist_revision: "a".repeat(64), candidate_count: 2, trust_status: "template",
  candidates: ["a", "b"].map(document_id => ({ document_id, title: "Private paper title", source: "fixture", publication_year: null })),
  decisions: [],
};
const selected = { document_id: "a", decision: "exclude", reason_codes: ["duplicate_or_version"] };
const allowed = (item: unknown): item is CandidateScreeningDecision => typeof item === "object" && item !== null
  && "document_id" in item && "decision" in item && item.decision === "exclude";
const encoded = encodeCheckpoint(screening, "mission_one", "b", [selected]);

describe("screening checkpoint identity", () => {
  it("retains only identifiers and decisions and can follow reordered candidates", () => {
    expect(encoded).not.toContain("Private paper title");
    expect(readCheckpoint(encoded, { ...screening, candidates: [...screening.candidates].reverse() }, "mission_one", allowed))
      .toMatchObject({ current: "b", changes: [selected] });
  });
  it("rejects foreign or malformed snapshots before applying any part", () => {
    const restore = (changes: object) => readCheckpoint(JSON.stringify({ ...JSON.parse(encoded), ...changes }), screening, "mission_one", allowed);
    for (const invalid of [{ run_id: "other" }, { mission_id: "mission_two" }, { revision: "b".repeat(64) },
      { candidates: ["a", "c"] }, { candidates: ["b", "b"] }, { current: "c" }, { changes: [selected, selected] },
      { changes: [{ ...selected, document_id: "c" }] }, { changes: [{ ...selected, decision: "invented" }] }]) {
      expect(restore(invalid)).toBeNull();
    }
    expect(readCheckpoint("invalid json", screening, "mission_one", allowed)).toBeNull();
    expect(readCheckpoint(encoded, { ...screening, candidate_count: 1 }, "mission_one", allowed)).toBeNull();
    expect(() => encodeCheckpoint(screening, "mission_one", "absent", [])).toThrow();
  });
});
