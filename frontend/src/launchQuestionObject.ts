/**
 * A deliberately narrow local convenience: recognise the material label that
 * is already present in a question. It does not infer composition, phase, or
 * a scientific result; the editable mission brief still needs confirmation.
 */
export function researchObjectFromQuestion(question: string): string | null {
  return /BiFeO(?:3|₃)/i.test(question) ? "BiFeO₃" : null;
}
