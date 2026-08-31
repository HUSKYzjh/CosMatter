import { describe, expect, it } from "vitest";

import { demoBundle } from "./model";
import { emptyBundleForMission } from "./missionBundleFactory";
import { hasNavigableLiteratureGraph, missionJourney } from "./missionJourney";

const reviewableBundle = {
  ...demoBundle,
  literatureGraph: {
    ...demoBundle.literatureGraph,
    nodes: [{ nodeId: "paper:reviewable-fixture", kind: "candidate_paper", label: "Reviewable fixture", trustStatus: "human_screening_required" }],
    edges: [],
  },
};

describe("missionJourney task-boundary lock", () => {
  it("does not call a fresh question-intake shell a completed orchestration", () => {
    const shell = emptyBundleForMission(demoBundle.mission);
    const stages = missionJourney(shell, shell.mission.question, "discover");
    expect(stages.find((item) => item.id === "orchestrate")?.state).toBe("ready");
    expect(stages.find((item) => item.id === "map")?.state).toBe("blocked");
  });
  it("keeps the bridge reachable but locks downstream artifact stages", () => {
    const stages = missionJourney(demoBundle, demoBundle.mission.question, "discover", true);
    expect(stages.find((item) => item.id === "orchestrate")?.state).toBe("complete");
    expect(stages.find((item) => item.id === "map")?.state).toBe("blocked");
    expect(stages.find((item) => item.id === "verify")?.state).toBe("blocked");
    expect(stages.find((item) => item.id === "extend")?.state).toBe("blocked");
  });

  it("keeps the route at task definition when any mission-boundary field is missing", () => {
    const incomplete = { ...demoBundle, mission: { ...demoBundle.mission, scope: "" } };
    const stages = missionJourney(incomplete, incomplete.mission.question, "discover");
    expect(stages.find((item) => item.id === "orchestrate")?.state).toBe("blocked");
  });
  it("keeps orchestration blocked until the visible task draft is confirmed", () => {
    const stages = missionJourney(demoBundle, "A revised but unconfirmed research question", "discover", false, false, { paperSelected: false, evidenceReady: false }, false);
    expect(stages.find((item) => item.id === "define")?.state).toBe("current");
    expect(stages.find((item) => item.id === "orchestrate")?.state).toBe("blocked");
    expect(stages.find((item) => item.id === "orchestrate")?.reasonZh).toContain("确认完整任务简报");
  });

  it("does not treat mission-only graph nodes as a reviewable literature map", () => {
    const missionOnly = { ...demoBundle, literatureGraph: { ...demoBundle.literatureGraph, nodes: [{ nodeId: "mission:only", kind: "mission", label: "Mission", trustStatus: "navigation" }], edges: [] } };
    const stages = missionJourney(missionOnly, missionOnly.mission.question, "workflow");
    expect(stages.find((item) => item.id === "verify")?.state).toBe("blocked");
  });

  it("keeps the map blocked when orchestration has no literature or bibliography projection", () => {
    const withoutMap = { ...demoBundle, literatureGraph: { ...demoBundle.literatureGraph, nodes: [{ nodeId: "mission:only", kind: "mission", label: "Mission", trustStatus: "navigation" }], edges: [] } };
    const stages = missionJourney(withoutMap, withoutMap.mission.question, "workflow");
    expect(stages.find((item) => item.id === "map")?.state).toBe("blocked");
    expect(stages.find((item) => item.id === "map")?.reasonZh).toContain("候选论文或 DOI 书目子图");
  });

  it("does not call a mission marker or isolated DOI node a navigable graph", () => {
    const missionOnly = { ...demoBundle, literatureGraph: { ...demoBundle.literatureGraph, nodes: [{ nodeId: "mission:only", kind: "mission", label: "Mission", trustStatus: "navigation" }], edges: [] } };
    const isolatedDoi = { ...demoBundle, literatureGraph: { ...demoBundle.literatureGraph, nodes: [{ nodeId: "doi:root", kind: "citation_work", label: "Root", trustStatus: "bibliography" }], edges: [] } };
    expect(hasNavigableLiteratureGraph(missionOnly)).toBe(false);
    expect(hasNavigableLiteratureGraph(isolatedDoi)).toBe(false);
  });

  it("allows DOI bibliography navigation without treating it as a reviewable evidence map", () => {
    const bibliography = {
      ...demoBundle,
      literatureGraph: {
        ...demoBundle.literatureGraph,
        trustStatus: "bibliography",
        nodes: [{ nodeId: "doi:root", kind: "citation_work", label: "Root", trustStatus: "bibliography" }, { nodeId: "doi:ref", kind: "citation_work", label: "Reference", trustStatus: "bibliography" }],
        edges: [{ sourceId: "doi:root", targetId: "doi:ref", edgeType: "citation_reference", relationSource: "OpenAlex", trustStatus: "bibliography" }],
      } as typeof demoBundle.literatureGraph,
    };
    const stages = missionJourney(bibliography, bibliography.mission.question, "workflow");
    expect(stages.find((item) => item.id === "map")?.state).toBe("ready");
    expect(stages.find((item) => item.id === "verify")?.state).toBe("blocked");
  });

  it("does not let a completed private PDF bypass paper selection", () => {
    // A candidate-linked private PDF may prepare source intake, but a real review session still starts from a selected paper.
    const stages = missionJourney(reviewableBundle, reviewableBundle.mission.question, "workflow", false, true);
    expect(stages.find((item) => item.id === "verify")?.state).toBe("blocked");
    expect(stages.find((item) => item.id === "verify")?.reasonZh).toContain("选择一篇待核对论文");
    expect(stages.find((item) => item.id === "extend")?.state).toBe("blocked");
  });

  it("keeps verification blocked when a researcher only selects metadata", () => {
    const stages = missionJourney(reviewableBundle, reviewableBundle.mission.question, "graph", false, false, { paperSelected: true, evidenceReady: false });
    expect(stages.find((item) => item.id === "map")?.state).toBe("current");
    expect(stages.find((item) => item.id === "verify")?.state).toBe("blocked");
    expect(stages.find((item) => item.id === "verify")?.reasonZh).toContain("人工纳入全文核对");
  });
  it("marks the literature-map stage complete after selecting a paper, without implying source review", () => {
    const stages = missionJourney(reviewableBundle, reviewableBundle.mission.question, "workflow", false, false, { paperSelected: true, evidenceReady: false });
    expect(stages.find((item) => item.id === "map")?.state).toBe("complete");
    expect(stages.find((item) => item.id === "verify")?.state).toBe("blocked");
  });

  it("unlocks verification after the current paper is human-included for full-text review", () => {
    const stages = missionJourney(reviewableBundle, reviewableBundle.mission.question, "graph", false, false, { paperSelected: true, evidenceReady: false, screeningAllowsSourceReview: true });
    expect(stages.find((item) => item.id === "verify")?.state).toBe("ready");
    expect(stages.find((item) => item.id === "extend")?.state).toBe("blocked");
  });

  it("unlocks verification when a completed private source map matches the selected paper", () => {
    const stages = missionJourney(reviewableBundle, reviewableBundle.mission.question, "graph", false, true, { paperSelected: true, evidenceReady: false });
    expect(stages.find((item) => item.id === "verify")?.state).toBe("ready");
  });
  it("unlocks the reader for a selected paper with an imported provenance-linked accepted card", () => {
    const stages = missionJourney(reviewableBundle, reviewableBundle.mission.question, "graph", false, false, { paperSelected: true, evidenceReady: false, paperHasAcceptedEvidence: true });
    expect(stages.find((item) => item.id === "verify")?.state).toBe("ready");
    expect(stages.find((item) => item.id === "extend")?.state).toBe("blocked");
  });
});





