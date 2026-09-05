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
  return value.replace(/[₀-₉]/g, (digit) => SUBSCRIPT_DIGITS[digit]);
}

function isChemicalFormula(value: string): boolean {
  const normalized = asciiFormula(value);
  const parts = [...normalized.matchAll(/([A-Z][a-z]?)(?:\d+(?:\.\d+)?)?/g)];
  return parts.length >= 2
    && parts.map((part) => part[0]).join("") === normalized
    && parts.every((part) => ELEMENTS.has(part[1]));
}

/**
 * Recognise an explicitly written material label without inferring a phase or
 * composition. Formula recognition is bounded to valid element symbols; a
 * short Chinese noun phrase is retained only when the question itself places
 * it directly before a known property expression. The result remains editable.
 */
export function researchObjectFromQuestion(question: string): string | null {
  if (/BiFeO(?:3|₃)/i.test(question)) return "BiFeO₃";

  const formula = question.match(/\b[A-Z][A-Za-z0-9₀-₉]{1,24}\b/g)?.find(isChemicalFormula);
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
