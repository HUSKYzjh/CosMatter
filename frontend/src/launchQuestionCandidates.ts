import { researchObjectFromQuestion } from "./launchQuestionObject";

export interface DeterministicLaunchCandidate {
  id: "survey" | "contrast" | "mechanism";
  question: string;
  material: string;
  property: string;
  scope: string;
  kind: "survey" | "contrast" | "mechanism";
}

/**
 * Local, non-model fallback candidates.  They preserve the user's named
 * object and question focus instead of pretending a generic literature
 * workflow is a substantive research direction.
 */
export function questionBoundFallbackCandidates(question: string, language: "zh" | "en"): DeterministicLaunchCandidate[] {
  const normalized = question.trim().replace(/\s+/g, " ");
  const material = researchObjectFromQuestion(normalized) ?? (language === "zh" ? "输入中的研究对象，待人工确认" : "Research object in the prompt; confirm manually");
  const focus = questionFocus(normalized, language);
  if (language === "en") return [
    { id: "survey", kind: "survey", question: normalized, material, property: focus, scope: `Resolve the question as written: “${normalized}”. Preserve each reported definition, sample condition, method, and evidence boundary.`, },
    { id: "contrast", kind: "contrast", question: `For ${material}, when reports discuss “${focus}”, which definitions, sample states, and measurement conditions make the reported values comparable or non-comparable?`, material, property: focus, scope: `Compare only literature that addresses “${focus}” for the object in “${normalized}”; retain incompatible conditions as explicit boundaries.`, },
    { id: "mechanism", kind: "mechanism", question: `For “${focus}” in ${material}, which primary-source definitions, transition assignments, and measurements must be checked before distinguishing competing interpretations?`, material, property: focus, scope: `Locate evidence needed to answer “${normalized}”; do not infer a mechanism from the question alone.`, },
  ];
  return [
    { id: "survey", kind: "survey", question: normalized, material, property: focus, scope: `按原问题“${normalized}”梳理文献；逐条保留报告中的定义、样品条件、测量方法与证据边界。`, },
    { id: "contrast", kind: "contrast", question: `针对 ${material} 的“${focus}”，不同论文的定义、样品状态和测量条件分别是什么？哪些报告可比较，哪些不能比较？`, material, property: focus, scope: `只比较与“${focus}”直接相关的文献；把“${normalized}”中未说明的条件保留为待核对边界。`, },
    { id: "mechanism", kind: "mechanism", question: `回答 ${material} 的“${focus}”前，需要优先核对哪些相变指派、原始测量与条件字段，才能排除术语混用或竞争解释？`, material, property: focus, scope: `围绕“${normalized}”定位原始证据；不从问题文本推断具体机制或数值。`, },
  ];
}

function questionFocus(question: string, language: "zh" | "en"): string {
  if (/相(?:转变|变).*温度|相转变温度|相变温度/i.test(question)) return language === "zh" ? "相转变温度" : "phase-transition temperature";
  if (/居里温度|Curie temperature/i.test(question)) return language === "zh" ? "居里温度" : "Curie temperature";
  if (/磁(?:转变|相变).*温度|磁转变温度/i.test(question)) return language === "zh" ? "磁转变温度" : "magnetic transition temperature";
  if (/电(?:转变|相变).*温度|电转变温度/i.test(question)) return language === "zh" ? "电转变温度" : "electric transition temperature";
  const stripped = question.replace(/BiFeO(?:3|₃)/ig, "").replace(/[？?。.!！]/g, "").trim();
  return stripped || (language === "zh" ? "问题中指定的研究性质" : "the property specified in the question");
}
