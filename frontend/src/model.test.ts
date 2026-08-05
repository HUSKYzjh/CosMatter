import { describe, expect, it } from "vitest";

import { readBundle } from "./model";

describe("readBundle", () => {
  it("accepts a complete CosMatter mission projection", () => {
    const bundle = readBundle({
      mission: {
        mission_id: "mission_a",
        question: "What is the phase boundary?",
        material: "BiFeO3",
        property_name: "phase stability",
        scope: "thin film"
      }
    });

    expect(bundle.source).toBe("local-file");
    expect(bundle.mission.material).toBe("BiFeO3");
  });

  it("rejects incomplete bundles", () => {
    expect(() => readBundle({ mission: { mission_id: "mission_a" } })).toThrow("字段不完整");
  });
});
