const SUBSCRIPT_DIGITS: Record<string, string> = {
  "₀": "0", "₁": "1", "₂": "2", "₃": "3", "₄": "4",
  "₅": "5", "₆": "6", "₇": "7", "₈": "8", "₉": "9",
};

const ELEMENTS = new Set([
  "H", "He", "Li", "Be", "B", "C", "N", "O", "F", "Ne", "Na", "Mg", "Al", "Si", "P", "S", "Cl", "Ar",
  "K", "Ca", "Sc", "Ti", "V", "Cr", "Mn", "Fe", "Co", "Ni", "Cu", "Zn", "Ga", "Ge", "As", "Se", "Br", "Kr",
  "Rb", "Sr", "Y", "Zr", "Nb", "Mo", "Tc", "Ru", "Rh", "Pd", "Ag", "Cd", "In", "Sn", "Sb", "Te", "I", "Xe",
  "Cs", "Ba", "La", "Ce", "Pr", "Nd", "Pm", "Sm", "Eu", "Gd", "Tb", "Dy", "Ho", "Er", "Tm", "Yb", "Lu",
  "Hf", "Ta", "W", "Re", "Os", "Ir", "Pt", "Au", "Hg", "Tl", "Pb", "Bi", "Po", "At", "Rn",
  "Fr", "Ra", "Ac", "Th", "Pa", "U", "Np", "Pu", "Am", "Cm", "Bk", "Cf", "Es", "Fm", "Md", "No", "Lr",
]);

function asciiFormula(value: string): string {
  return value
    .replace(/[₀-₉]/g, (digit) => SUBSCRIPT_DIGITS[digit])
    .replace(/_\{(\d+(?:\.\d+)?)\}|_(\d+(?:\.\d+)?)/g, (_, braced, plain) => braced ?? plain);
}

function isChemicalFormula(value: string): boolean {
  const normalized = asciiFormula(value);
  const parts = [...normalized.matchAll(/([A-Z][a-z]?)(?:\d+(?:\.\d+)?)?/g)];
  return parts.length >= 2
    && parts.map((part) => part[0]).join("") === normalized
    && parts.every((part) => ELEMENTS.has(part[1]));
}

const mixedOccupancy = /\((?:[A-Z][a-w]?(?:_?\{?[0-9₀-₉xyzₓ.−₋+\-]+\}?)?\s*){2,}\)(?:[A-Z][a-z]?(?:_?\{?[0-9₀-₉]+\}?)?)+/;
const writtenToken = /[A-Za-z](?:[A-Za-z0-9₀-₉]|\.(?=\d)|_\{\d+(?:\.\d+)?\}|_(?=\d))*/;
// ASCII word boundaries split a formula before a Unicode subscript. Consume
// a whole token first, then validate its element symbols and stoichiometry.
const materialToken = new RegExp(
  "(?<![A-Za-z0-9₀-₉_])(?:(" + mixedOccupancy.source + ")|" + writtenToken.source + ")(?![A-Za-z0-9₀-₉_])", "gu",
);
const isBfo = (value: string) => /^BiFeO3$/i.test(asciiFormula(value));

function writtenMaterials(question: string) {
  return [...question.matchAll(materialToken)].filter(match => match[1] || isBfo(match[0]) || isChemicalFormula(match[0]));
}

function explicitMaterial(question: string): string | null {
  const matches = writtenMaterials(question);
  const comparison = /\bcompar(?:e|ing|ison)\b|比较|对比/i.test(question);
  // Preserve the original order and conjunction of materials named together.
  // Other mentions, such as a growth substrate, keep their role in the scope.
  let first = 0;
  for (let i = 1; i <= matches.length; i++) {
    if (i < matches.length) {
      const previous = matches[i - 1];
      const between = question.slice(previous.index + previous[0].length, matches[i].index).trim();
      if (/^(?:和|与|及|或|以及|[,，、/]|,?\s*(?:and|or)|versus|vs\.?|compared (?:with|to))$/i.test(between)
        || (comparison && /^(?:with|to)(?: that of)?$/i.test(between))) continue;
    }
    if (i - first > 1) {
      const last = matches[i - 1];
      return question.slice(matches[first].index, last.index + last[0].length)
        .replace(/\s+(?:compared (?:with|to)|with|to)(?: that of)?\s+/gi, " vs. ");
    }
    first = i;
  }
  const firstLabel = matches[0]?.[0];
  if (!firstLabel) return null;
  return isBfo(firstLabel) ? "BiFeO₃" : firstLabel;
}

export function questionWithoutMaterialFormulas(question: string): string {
  let remaining = question;
  for (const match of writtenMaterials(question).reverse()) {
    remaining = remaining.slice(0, match.index) + remaining.slice(match.index + match[0].length);
  }
  return remaining;
}

/**
 * Recognise an explicitly written material label without inferring a phase or
 * composition. Formula recognition is bounded to valid element symbols; a
 * short Chinese noun phrase is retained only when the question itself places
 * it directly before a known property expression. The result remains editable.
 */
export function researchObjectFromQuestion(question: string): string | null {
  const formula = explicitMaterial(question);
  if (formula) return formula;

  const propertyMarker = /(?:相(?:转变|变)温度|居里温度|奈尔温度|磁转变温度|带隙|循环稳定性|容量保持率|电导率|热导率|矫顽场|剩余极化|介电常数|漏电流|催化活性|吸附能|形成能|晶格常数)/;
  const marker = propertyMarker.exec(question);
  if (!marker?.index) return null;
  let prefix = question.slice(0, marker.index).replace(/[“”"']/g, "").trim();
  prefix = prefix
    .replace(/^(?:请问|请比较|请评估|请研究|如何比较|如何评估|如何研究|怎样比较|怎样评估|为什么|为何)/, "")
    .replace(/(?:在|于)[^，。？?]{1,24}(?:下|时)的?$/, "")
    .replace(/的$/, "")
    .trim();
  return prefix.length >= 2 && prefix.length <= 32 ? prefix : null;
}
