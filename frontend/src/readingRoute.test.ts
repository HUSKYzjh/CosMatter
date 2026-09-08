import { describe, expect, it } from "vitest";

import { readingRoute } from "./readingRoute";
import type { LiteratureGraphNode, ResearchGuide } from "./model";

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

  it("uses the validated backend three-track guide within equal workflow actions", () => {
    const guide: ResearchGuide = {
      trustStatus: "derived_from_approved_artifacts",
      items: [
        { order: 1, documentId: "algorithm", title: "Algorithm", researchTrack: "algorithm", routeEligibility: "primary_allowed", facetSignals: ["configuration_search_method"] },
        { order: 2, documentId: "analogue", title: "Analogue", researchTrack: "mechanism_analogue", routeEligibility: "counterevidence_only", facetSignals: ["approved_counterevidence_query"] },
        { order: 3, documentId: "exact", title: "Exact", researchTrack: "exact_material", routeEligibility: "primary_allowed", facetSignals: ["exact_material_title"] },
      ],
      routePolicy: {
        classificationStatus: "current_candidate_pool",
        queryTrackPlanningStatus: "approved_independent_tracks",
        approvedQueryTrackCounts: { exact_material: 1, mechanism_analogue: 1, algorithm: 1 },
        trackMinimums: { exact_material: 4, mechanism_analogue: 3, algorithm: 4 },
        availableTrackCounts: { exact_material: 1, mechanism_analogue: 1, algorithm: 1 },
        selectedTrackCounts: { exact_material: 1, mechanism_analogue: 1, algorithm: 1 },
        trackShortfallCounts: { exact_material: 3, mechanism_analogue: 2, algorithm: 3 },
        shortfallReasonCodes: ["exact_material_shortfall", "mechanism_analogue_shortfall", "algorithm_shortfall"],
        availableCounterevidenceCount: 1,
        selectedCounterevidenceCount: 1,
      },
    };
    const route = readingRoute([
      node("exact", "BiFeO3 exact material"),
      node("algorithm", "Unrelated configuration search"),
      node("analogue", "Analogue"),
    ], {}, 6, { material: "BiFeO3" }, guide);

    expect(route.map((entry) => [entry.documentId, entry.researchTrack, entry.routeEligibility, entry.routeSource])).toEqual([
      ["algorithm", "algorithm", "primary_allowed", "backend-guide"],
      ["analogue", "mechanism_analogue", "counterevidence_only", "backend-guide"],
      ["exact", "exact_material", "primary_allowed", "backend-guide"],
    ]);
  });
});
