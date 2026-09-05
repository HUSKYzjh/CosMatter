import { describe, expect, it } from "vitest";

import { readingRoute } from "./readingRoute";
import type { LiteratureGraphNode } from "./model";

const node = (id: string, title: string, trustStatus = "candidate_metadata_not_scientific_evidence"): LiteratureGraphNode => ({ nodeId: `paper:${id}`, kind: "candidate_paper", label: title, trustStatus });

describe("readingRoute", () => {
  it("orders recorded recovery and evidence work before screening, with stable local reasons", () => {
    const route = readingRoute([node("screen", "Screen"), node("source", "Source"), node("failed", "Failed")], {
      "paper:screen": "screening", "paper:source": "source_map", "paper:failed": "failed",
    });
    expect(route.map((entry) => [entry.documentId, entry.action, entry.ordinal])).toEqual([
      ["failed", "recover-pdf", 1], ["source", "register-source-map", 2], ["screen", "screen-paper", 3],
    ]);
  });

  it("excludes synthetic, metadata-only, and human-excluded records from the route", () => {
    const route = readingRoute([
      node("reviewable", "Reviewable"),
      node("synthetic", "Synthetic", "synthetic_demo_candidate_not_scientific_evidence"),
      { nodeId: "doi:10.1/example", kind: "citation_work", label: "DOI", trustStatus: "bibliography" },
      node("excluded", "Excluded"),
    ], { "paper:excluded": "excluded" });
    expect(route).toHaveLength(1);
    expect(route[0]).toMatchObject({ documentId: "reviewable", action: "load-screening" });
  });

  it("uses task material title anchors before alphabetical order for equal workflow actions", () => {
    const route = readingRoute([
      node("sodium", "23 Na NMR study of sodium order"),
      node("bfo", "Magnetic transition in BiFeO3 nanoparticles"),
      node("bfo-spaced", "Phase diagram of BiFeO <sub>3</sub> thin films"),
    ], {}, 6, { material: "BiFeO₃ 外延薄膜" });

    expect(route.map((entry) => [entry.documentId, entry.titleAnchorMatch])).toEqual([
      ["bfo", "material"],
      ["bfo-spaced", "material"],
      ["sodium", "none"],
    ]);
  });

  it("uses bilingual task-context aliases and ranks double matches above broad material matches", () => {
    const route = readingRoute([
      node("material", "Atomic-scale growth of BiFeO3 nanoparticles"),
      node("context", "Phase transitions in oxide perovskites"),
      node("both", "Thermodynamic phase diagram for multiferroic BiFeO3"),
      node("doped", "High-temperature magnetic behavior of Bi1-xCaxFeO3 ceramics"),
      node("neel", "Néel transition in BiFeO3 ceramics"),
      node("none", "Sodium ordering in layered oxides"),
    ], {}, 6, {
      material: "BiFeO₃",
      question: "BiFeO₃ 的相转变温度、铁电居里温度与奈尔温度分别是多少？",
    });

    expect(route.map((entry) => [entry.documentId, entry.titleAnchorMatch])).toEqual([
      ["both", "material-and-context"],
      ["doped", "material-and-context"],
      ["neel", "material-and-context"],
      ["material", "material"],
      ["context", "context"],
      ["none", "none"],
    ]);

    const legacyStrainRoute = readingRoute([
      node("material", "Growth of BiFeO3 nanoparticles"),
      node("wrong-material", "Strain-induced phase transitions in epitaxial BiCoO3 thin films"),
      node("both", "Thickness-dependent strain and phase stability in epitaxial BiFeO3 films"),
      node("optical", "Optical band gap in epitaxial BiFeO3 thin films"),
    ], {}, 6, {
      material: "BiFeO3 epitaxial thin films",
      question: "How do substrate-induced strain and film thickness relate to reported phase stability?",
    });
    expect(legacyStrainRoute.map((entry) => [entry.documentId, entry.titleAnchorMatch])).toEqual([
      ["both", "material-and-context"],
      ["material", "material"],
      ["optical", "material"],
      ["wrong-material", "context"],
    ]);

    const legacyScopeRoute = readingRoute([
      node("optical", "Revisiting the optical band gap in epitaxial BiFeO3 thin films"),
    ], {}, 6, {
      material: "BiFeO3 epitaxial thin films",
      property: "phase stability",
      question: "For BiFeO3 epitaxial thin films, how do substrate-induced strain and film thickness relate to reported phase stability, and what counterevidence identifies confounding conditions?",
      scope: "Bounded end-to-end provider test: DeepSeek-v4-flash planning plus Sciverse retrieval and one human-screened bounded full-text context; no scientific conclusion or automatic evidence acceptance.",
    });
    expect(legacyScopeRoute[0].titleAnchorMatch).toBe("material");

    const defectRoute = readingRoute([
      node("bfo-vacancy", "Thermodynamic stabilization of oxygen vacancies in BiFeO3"),
      node("bafe", "Stability of oxygen-defective BaFeO3"),
      node("photoanode", "Combined experimental and theoretical investigations of n-type BiFeO3 as a photoanode"),
    ], {}, 6, {
      material: "BiFeO3",
      property: "defect-mediated phase stability",
      question: "How do oxygen vacancies and substitution alter phase stability in BiFeO3?",
      scope: "Compare synthesis and computational studies, with contradictory evidence retained.",
    });
    expect(defectRoute.map((entry) => [entry.documentId, entry.titleAnchorMatch])).toEqual([
      ["bfo-vacancy", "material-and-context"],
      ["photoanode", "material"],
      ["bafe", "context"],
    ]);
  });

  it("keeps unanchored candidates for review and never lets title anchors override workflow recovery", () => {
    const route = readingRoute([
      node("relevant", "Phase transitions in BiFeO3"),
      node("failed", "Unrelated sodium compound"),
      node("unanchored", "A possible counterexample"),
    ], { "paper:relevant": "screening", "paper:failed": "failed", "paper:unanchored": "screening" }, 6, { material: "BiFeO3" });

    expect(route.map((entry) => [entry.documentId, entry.action, entry.titleAnchorMatch])).toEqual([
      ["failed", "recover-pdf", "none"],
      ["relevant", "screen-paper", "material"],
      ["unanchored", "screen-paper", "none"],
    ]);
  });
});
