import { describe, expect, it } from "vitest";
import { displayPaperTitle } from "./paperTitle";

describe("bibliographic title typography", () => {
  it("renders only explicit single-token and braced numerical subscripts and charges", () => {
    expect(displayPaperTitle("la$_2$o$_3$-modified TiO$_{12}$ and Fe$^{3+}$")).toBe("la₂o₃-modified TiO₁₂ and Fe³⁺");
    expect(displayPaperTitle("SO$_4$$^{2−}$ at 10$^2$ K")).toBe("SO₄²⁻ at 10² K");
  });

  it("preserves plain formulas, literal dollars, unsupported notation and display math", () => {
    for (const title of ["BiFeO3 vs BiFeO₃", "Ref #1 costs $5", "La_2O_3", "Pb$_{1-x}$Sr$_x$",
      "E = $x^{2}+y_{2}$", "$^{3+}_{2}$", "$$^{2}$$", "price \\$_2$"]) {
      expect(displayPaperTitle(title)).toBe(title);
    }
    expect(displayPaperTitle("Pb$_{1-x}$TiO$_3$")).toBe("Pb$_{1-x}$TiO₃");
  });
});
