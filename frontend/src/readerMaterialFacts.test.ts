import { describe, expect, it } from "vitest";

import { readBundle, type LiteratureGraphNode } from "./model";
import { materialFactsForSelectedPaper } from "./readerMaterialFacts";
import { emptyResearchSession, selectPaper } from "./researchSession";

const mission = { mission_id: "m1", question: "Compare samples", material: "BiFeO3", property_name: "permittivity", scope: "ceramics" };
const sessionFor = (documentId: string) => {
  const paper: LiteratureGraphNode = { nodeId: `paper:${documentId}`, kind: "candidate_paper", label: documentId, trustStatus: "candidate" };
  return selectPaper(emptyResearchSession(), paper);
};
const ledger = (documentId: string, value: number) => ({
  document_id: documentId, trust_status: "human_reviewed_structured_material_facts_not_scientific_conclusion",
  facts: [{ fact_id: "f1", segment_id: "s1", category: "property", name: "permittivity", value, unit: "-",
    normalized_value: null, normalized_unit: null, qualifiers: { sample: documentId }, locator: "Fig. 6" }],
});

describe("reader material facts", () => {
  it("selects each paper's facts even when the fact and source segment identifiers repeat", () => {
    const bundle = readBundle({ mission, material_fact_ledgers: [ledger("doc-a", 20), ledger("doc-b", 42)], material_facts: ledger("stale", 71) });
    expect(materialFactsForSelectedPaper(bundle, sessionFor("doc-a"))?.facts[0]).toMatchObject({ value: 20, qualifiers: { sample: "doc-a" } });
    expect(materialFactsForSelectedPaper(bundle, sessionFor("doc-b"))?.facts[0]).toMatchObject({ value: 42, qualifiers: { sample: "doc-b" } });
    expect(materialFactsForSelectedPaper(bundle, sessionFor("stale"))).toBeNull();
    expect(bundle.materialFacts).toBe(bundle.materialFactLedgers[0]);
    expect(bundle.evidenceCards).toEqual([]);
  });

  it("reads the older single-paper export only for that paper", () => {
    const bundle = readBundle({ mission, material_facts: ledger("doc-a", 20) });
    expect(materialFactsForSelectedPaper(bundle, sessionFor("doc-a"))?.facts[0].value).toBe(20);
    expect(materialFactsForSelectedPaper(bundle, sessionFor("doc-b"))).toBeNull();
  });

  it("does not resurrect the legacy copy when the modern ledgers are empty, untrusted or malformed", () => {
    const stale = ledger("doc-a", 20);
    for (const material_fact_ledgers of [[], null, {}, [{ ...stale, trust_status: "unreviewed" }], [stale, stale]]) {
      const bundle = readBundle({ mission, material_fact_ledgers, material_facts: stale });
      expect(bundle.materialFactLedgers).toEqual([]);
      expect(bundle.materialFacts).toBeNull();
    }
  });

  it("withholds both forms and the review counts in a delegated trial", () => {
    const facts = ledger("doc-a", 20);
    const bundle = readBundle({ mission, delegated_test_boundary: true, material_facts: facts, material_fact_ledgers: [facts],
      reviewed_material_fact_summary: { document_count: 1, fact_count: 1 } });
    expect(bundle.materialFactLedgers).toEqual([]);
    expect(bundle.materialFacts).toBeNull();
    expect(bundle.materialFactSummary).toEqual({ documentCount: 0, factCount: 0 });
  });
});
