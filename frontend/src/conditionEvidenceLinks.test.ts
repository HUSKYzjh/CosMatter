import { describe, expect, it } from "vitest";
import { conditionEvidenceLinks } from "./conditionEvidenceLinks";
import type { EvidenceCard } from "./model";

const cards = [{ evidenceId: "ev-2" }] as EvidenceCard[];

describe("conditionEvidenceLinks", () => {
  it("preserves recorded matrix IDs and flags missing artifacts without inference", () => {
    const links = conditionEvidenceLinks(["ev-2", "ev-missing"], cards);
    expect(links.map((link) => [link.evidenceId, link.evidence?.evidenceId ?? null])).toEqual([
      ["ev-2", "ev-2"],
      ["ev-missing", null],
    ]);
  });
});
