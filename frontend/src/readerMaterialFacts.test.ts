import { describe, expect, it } from "vitest";

import { demoBundle, type LiteratureGraphNode } from "./model";
import { materialFactsForSelectedPaper } from "./readerMaterialFacts";
import { emptyResearchSession, selectPaper } from "./researchSession";

const paper: LiteratureGraphNode = { nodeId: "paper:doc-1", kind: "candidate_paper", label: "Paper one", trustStatus: "candidate" };

describe("reader material facts", () => {
  it("shows a reviewed fact ledger only for the currently selected paper", () => {
    const bundle = { ...demoBundle, materialFacts: { documentId: "doc-1", trustStatus: "human_reviewed", facts: [{ factId: "f1", segmentId: "s1", category: "property", name: "polarization", value: 50, unit: "uC/cm2", normalizedValue: 50, normalizedUnit: "uC/cm2", qualifiers: {}, locator: "p. 2" }] } };
    expect(materialFactsForSelectedPaper(bundle, selectPaper(emptyResearchSession(), paper))?.facts).toHaveLength(1);
  });

  it("does not present another paper's facts in the current reading context", () => {
    const bundle = { ...demoBundle, materialFacts: { documentId: "doc-2", trustStatus: "human_reviewed", facts: [] } };
    expect(materialFactsForSelectedPaper(bundle, selectPaper(emptyResearchSession(), paper))).toBeNull();
  });
});