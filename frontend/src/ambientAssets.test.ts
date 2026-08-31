import { describe, expect, it } from "vitest";
import { AMBIENT_ASSETS } from "./FleetDecoration";

describe("ambient background asset pools", () => {
  it("provides five transparent assets for every research-stage pool", () => {
    for (const [stage, assets] of Object.entries(AMBIENT_ASSETS)) {
      expect(assets, stage).toHaveLength(5);
      expect(assets.every((asset) => asset.startsWith("/ambient-backgrounds/") && asset.endsWith(".png"))).toBe(true);
    }
  });

  it("keeps a distinct, stage-specific dynamic background pool", () => {
    expect(Object.keys(AMBIENT_ASSETS).sort()).toEqual(["discover", "graph", "horizon", "reader", "workflow"]);
    expect(new Set(AMBIENT_ASSETS.workflow)).toHaveLength(5);
    expect(AMBIENT_ASSETS.workflow.every((asset) => asset.includes("/fleet/"))).toBe(true);
    expect(AMBIENT_ASSETS.graph.every((asset) => asset.includes("/starfield/"))).toBe(true);
    expect(AMBIENT_ASSETS.discover.every((asset) => asset.includes("/fleet/"))).toBe(true);
    expect(AMBIENT_ASSETS.reader.every((asset) => asset.includes("/fleet/"))).toBe(true);
  });
});
