import { describe, expect, it } from "vitest";
import { type EvidenceCard, type LiteratureGraphNode } from "./model";
import { graphDoi, searchGraph, searchableGraphNodes } from "./graphSearch";

const paper: LiteratureGraphNode = { nodeId: "paper:alpha", kind: "candidate_paper", label: "Piezoelectric response of BiFeO₃", source: "Sciverse", publicationYear: 2024, doi: "10.1234/alpha", trustStatus: "retrieval_candidate" };
const citation: LiteratureGraphNode = { nodeId: "doi:10.1234/beta", kind: "citation_work", label: "10.1234/beta", trustStatus: "bibliographic" };
const nodes = [paper, citation];

describe("local map lookup", () => {
  it("accepts resolver URLs, bare document IDs and tokens across bibliographic fields", () => {
    for (const query of ["HTTPS://DOI.ORG/10.1234/ALPHA", "alpha", "Sciverse 2024 bifeo3"]) expect(searchGraph(nodes, query)).toEqual([paper]);
    expect(searchGraph(nodes, "doi: 10.1234/BETA")).toEqual([citation]);
    expect(searchGraph(nodes, "doi:")).toEqual([]);
    expect(searchGraph(nodes, "2025 response")).toEqual([]);
  });
  it("retains duplicate DOI records and puts exact work IDs before partial identifiers", () => {
    const longer = { ...paper, nodeId: "paper:alpha-2", doi: "10.1234/alpha-2" };
    const duplicate = { ...paper, nodeId: "paper:beta-edition" };
    expect(searchGraph([longer, paper, duplicate], "10.1234/alpha")).toEqual([paper, duplicate, longer]);
  });
  it("can use an older bundle's unambiguous recorded DOI without joining unrelated papers", () => {
    const legacy = { ...paper, doi: undefined };
    const card = (id: string, doi: string) => ({ provenance: { documentId: id, doi } }) as EvidenceCard;
    expect(searchableGraphNodes([legacy], [card("alpha", "doi:10.1234/One"), card("other", "10.1234/two")])[0].doi).toBe("10.1234/one");
    expect(searchableGraphNodes([legacy], [card("alpha", "10.1234/one"), card("alpha", "10.1234/two")])[0].doi).toBeUndefined();
    expect(graphDoi({ ...citation, kind: "mission" })).toBeUndefined();
  });
});
