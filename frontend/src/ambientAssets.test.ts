import { describe, expect, it } from "vitest";
import { AMBIENT_ASSETS } from "./FleetDecoration";

describe("ambient background asset pools", () => {
  it("provides five transparent assets for every research-stage pool", () => {
    for (const [stage, assets] of Object.entries(AMBIENT_ASSETS)) {
      expect(assets, stage).toHaveLength(5);
      expect(assets.every((asset) => asset.startsWith("/ambient-backgrounds/") && asset.endsWith(".png"))).toBe(true);
    }
  });
});