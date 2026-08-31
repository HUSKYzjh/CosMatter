import { describe, expect, it } from "vitest";

import { materialFactScalar } from "./materialFactValue";

describe("materialFactScalar", () => {
  it("serializes standalone finite numeric values for loopback normalization", () => {
    expect(materialFactScalar(" 300 ")).toBe(300);
    expect(materialFactScalar("-2.5e-3")).toBe(-0.0025);
  });

  it("preserves reported prose and represents a blank field as null", () => {
    expect(materialFactScalar("shifts with strain")).toBe("shifts with strain");
    expect(materialFactScalar(" ")).toBeNull();
  });
});
