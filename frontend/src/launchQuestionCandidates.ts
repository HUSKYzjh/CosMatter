import { researchObjectFromQuestion } from "./launchQuestionObject";

export interface DeterministicLaunchCandidate {
  id: "survey" | "contrast" | "mechanism";
  question: string;
  material: string;
  property: string;
  scope: string;
  kind: "survey" | "contrast" | "mechanism";
}

type FocusKind = "transition" | "electrochemical" | "transport" | "electronic" | "synthesis" | "mechanism" | "property";

/**
 * Local, non-model fallback candidates.  They preserve the user's named
 * object and question focus instead of pretending a generic literature
 * workflow is a substantive research direction.
 */
export function questionBoundFallbackCandidates(question: string, language: "zh" | "en"): DeterministicLaunchCandidate[] {
  const normalized = question.trim().replace(/\s+/g, " ");
  const material = researchObjectFromQuestion(normalized) ?? (language === "zh" ? "输入中的研究对象，待人工确认" : "Research object in the prompt; confirm manually");
  const focus = questionFocus(normalized, language);
  const focusKind = classifyFocus(normalized, focus);
  const audit = auditRoute(normalized, material, focus, focusKind, language);
  if (language === "en") return [
    { id: "survey", kind: "survey", question: normalized, material, property: focus, scope: `Resolve the question as written: “${normalized}”. Preserve each reported definition, sample condition, method, and evidence boundary.`, },
    { id: "contrast", kind: "contrast", question: `For ${material}, when reports discuss “${focus}”, which definitions, sample states, and measurement conditions make the reported values comparable or non-comparable?`, material, property: focus, scope: `Compare only literature that addresses “${focus}” for the object in “${normalized}”; retain incompatible conditions as explicit boundaries.`, },
    { id: "mechanism", kind: "mechanism", question: audit.question, material, property: focus, scope: audit.scope, },
  ];
  return [
    { id: "survey", kind: "survey", question: normalized, material, property: focus, scope: `按原问题“${normalized}”梳理文献；逐条保留报告中的定义、样品条件、测量方法与证据边界。`, },
    { id: "contrast", kind: "contrast", question: `针对 ${material} 的“${focus}”，不同论文的定义、样品状态和测量条件分别是什么？哪些报告可比较，哪些不能比较？`, material, property: focus, scope: `只比较与“${focus}”直接相关的文献；把“${normalized}”中未说明的条件保留为待核对边界。`, },
    { id: "mechanism", kind: "mechanism", question: audit.question, material, property: focus, scope: audit.scope, },
  ];
}

function questionFocus(question: string, language: "zh" | "en"): string {
  if (/相(?:转变|变).*温度|相转变温度|相变温度/i.test(question)) return language === "zh" ? "相转变温度" : "phase-transition temperature";
  if (/居里温度|Curie temperature/i.test(question)) return language === "zh" ? "居里温度" : "Curie temperature";
  if (/奈尔温度|N[eé]el temperature/i.test(question)) return language === "zh" ? "奈尔温度" : "Néel temperature";
  if (/磁(?:转变|相变).*温度|磁转变温度/i.test(question)) return language === "zh" ? "磁转变温度" : "magnetic transition temperature";
  if (/电(?:转变|相变).*温度|电转变温度/i.test(question)) return language === "zh" ? "电转变温度" : "electric transition temperature";
  const namedFocuses: Array<[RegExp, string, string]> = [
    [/循环稳定性|cycling stability|cycle life/i, "循环稳定性", "cycling stability"],
    [/容量保持率|capacity retention/i, "容量保持率", "capacity retention"],
    [/带隙|band[ -]?gap/i, "带隙", "band gap"],
    [/电导率|electrical conductivity/i, "电导率", "electrical conductivity"],
    [/热导率|thermal conductivity/i, "热导率", "thermal conductivity"],
    [/矫顽场|coercive field/i, "矫顽场", "coercive field"],
    [/剩余极化|remanent polarization/i, "剩余极化", "remanent polarization"],
    [/介电常数|dielectric (?:constant|permittivity)/i, "介电常数", "dielectric permittivity"],
    [/漏电流|leakage current/i, "漏电流", "leakage current"],
    [/催化活性|catalytic activity/i, "催化活性", "catalytic activity"],
    [/吸附能|adsorption energy/i, "吸附能", "adsorption energy"],
    [/形成能|formation energy/i, "形成能", "formation energy"],
    [/晶格常数|lattice constant/i, "晶格常数", "lattice constant"],
    [/制备|合成|生长|退火|沉积|synthesi[sz]|fabricat|growth|anneal|deposition/i, "制备条件与产物", "synthesis conditions and outcome"],
    [/机理|机制|mechanism/i, "作用机理", "mechanism"],
  ];
  for (const [pattern, zh, en] of namedFocuses) if (pattern.test(question)) return language === "zh" ? zh : en;
  const stripped = question
    .replace(/BiFeO(?:3|₃)/ig, "")
    .replace(/\b[A-Z][A-Za-z0-9₀-₉]{1,24}\b/g, "")
    .replace(/^(?:请问|请比较|请评估|如何|怎样|为什么|为何|what|which|how|why|is|are)\s*/i, "")
    .replace(/[？?。.!！]/g, "")
    .trim();
  return stripped || (language === "zh" ? "问题中指定的研究性质" : "the property specified in the question");
}

function classifyFocus(question: string, focus: string): FocusKind {
  const text = `${question} ${focus}`;
  if (/相(?:转变|变)|居里|奈尔|transition|Curie|N[eé]el/i.test(text)) return "transition";
  if (/循环|容量|倍率|电池|电极|cycle|capacity|battery|electrode/i.test(text)) return "electrochemical";
  if (/电导|热导|漏电|输运|conductiv|transport|leakage/i.test(text)) return "transport";
  if (/带隙|极化|介电|矫顽|band[ -]?gap|polarization|permittivity|coercive/i.test(text)) return "electronic";
  if (/制备|合成|生长|退火|沉积|synthesi[sz]|fabricat|growth|anneal|deposition/i.test(text)) return "synthesis";
  if (/机理|机制|mechanism/i.test(text)) return "mechanism";
  return "property";
}

function auditRoute(originalQuestion: string, material: string, focus: string, kind: FocusKind, language: "zh" | "en"): { question: string; scope: string } {
  if (language === "en") {
    const detail = ({
      transition: "transition assignments, heating/cooling history, sample state, and raw thermal, structural, magnetic, or electrical signals",
      electrochemical: "electrode composition, loading, current rate, voltage window, cycle count, retention definition, and post-test evidence",
      transport: "measurement geometry, temperature/frequency range, contacts, calibration, uncertainty, and raw transport data",
      electronic: "experimental or computational method, sample state, boundary conditions, uncertainty, and the primary spectrum or response curve",
      synthesis: "precursors, stoichiometry, atmosphere, process history, phase-purity checks, yield, and independent repetitions",
      mechanism: "competing explanations, discriminating controls, raw observations, and unresolved alternatives",
      property: "operational definition, sample condition, primary measurement, uncertainty, controls, and possible confounders",
    } satisfies Record<FocusKind, string>)[kind];
    return {
      question: `Before answering “${focus}” for ${material}, which ${detail} must be checked in the primary sources?`,
      scope: `Use the checks that fit “${focus}” to answer “${originalQuestion}”; do not infer a value or mechanism from the prompt alone.`,
    };
  }
  const detail = ({
    transition: "相变指派、升降温历史、样品状态，以及热学、结构、磁学或电学原始信号",
    electrochemical: "电极组成与载量、倍率、电压窗口、循环数、保持率定义及循环后表征",
    transport: "测量几何、温度或频率范围、接触方式、校准、不确定度及原始输运数据",
    electronic: "实验或计算方法、样品状态、边界条件、不确定度及原始谱线或响应曲线",
    synthesis: "前驱体、化学计量、气氛、工艺历史、物相纯度、产率及独立重复",
    mechanism: "竞争解释、区分性对照、原始观测和仍未排除的替代机制",
    property: "操作性定义、样品条件、原始测量、不确定度、对照实验及潜在混杂因素",
  } satisfies Record<FocusKind, string>)[kind];
  return {
    question: `回答 ${material} 的“${focus}”前，需要优先核对哪些${detail}？`,
    scope: `用与“${focus}”相匹配的核验项回答“${originalQuestion}”；不从问题文本推断数值或机制。`,
  };
}
