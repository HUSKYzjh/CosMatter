const scriptCharacters = "0123456789+-=()";
const subscripts = "₀₁₂₃₄₅₆₇₈₉₊₋₌₍₎";
const superscripts = "⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻⁼⁽⁾";

/** Render an explicit numerical TeX script in a plain-text bibliographic title. */
export function displayPaperTitle(title: string): string {
  if (!title.includes("$")) return title;
  // Consume literal dollars and display-math blocks intact. Only an entire
  // inline fragment consisting of one subscript or superscript is eligible.
  return title.replace(/\\\$|\$\$[\s\S]*?\$\$|\$([_^])(?:\{([0-9+\-=()−]+)\}|([0-9+\-=()−]))\$/gu,
    (fragment, script?: string, group?: string, single?: string) => {
      if (!script) return fragment;
      const digits = (group ?? single!).replaceAll("−", "-");
      const glyphs = script === "_" ? subscripts : superscripts;
      return Array.from(digits, char => glyphs[scriptCharacters.indexOf(char)]).join("");
    });
}
