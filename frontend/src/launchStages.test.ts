import { describe, expect, it } from "vitest";
import { LAUNCH_STAGES, launchModeStatus, stageForLaunchMode } from "./launchStages";

describe("launch-stage route", () => {
  it("defines the five evidence-loop stages in order", () => {
    expect(LAUNCH_STAGES.map((stage) => stage.id)).toEqual(["discover", "workflow", "graph", "reader", "horizon"]);
    expect(LAUNCH_STAGES.every((stage) => stage.zh && stage.en && stage.inputZh && stage.outputZh && stage.gateZh)).toBe(true);
  });

  it("maps each entry mode to its read-only preview starting point", () => {
    expect(stageForLaunchMode("question")).toBe("discover");
    expect(stageForLaunchMode("pdf")).toBe("reader");
    expect(stageForLaunchMode("resume")).toBe("workflow");
  });

  it("keeps mode status bilingual and descriptive", () => {
    expect(launchModeStatus("question", "zh")).toContain("受控编排");
    expect(launchModeStatus("pdf", "en")).toContain("PDF entry");
    expect(launchModeStatus("resume", "zh")).toContain("运行包");
  });
});