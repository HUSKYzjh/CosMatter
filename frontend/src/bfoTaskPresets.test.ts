import { describe, expect, it } from "vitest";

import { bfoTaskPresets } from "./bfoTaskPresets";
import { isLaunchMissionReady } from "./launchMissionValidation";

describe("BFO task presets", () => {
  it("offers three editable, complete local task briefs", () => {
    const presets = bfoTaskPresets("zh");
    expect(presets).toHaveLength(3);
    expect(new Set(presets.map((preset) => preset.id)).size).toBe(3);
    expect(presets.every(isLaunchMissionReady)).toBe(true);
  });

  it("keeps the task identity while localising each displayed field", () => {
    const zh = bfoTaskPresets("zh");
    const en = bfoTaskPresets("en");
    expect(en.map((preset) => preset.id)).toEqual(zh.map((preset) => preset.id));
    expect(en[0].question).not.toBe(zh[0].question);
  });
});
