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
  const routes = routeText(normalized, material, focus, focusKind, language);
  return [
    { id: "survey", kind: "survey", question: routes.survey.question, material, property: focus, scope: routes.survey.scope },
    { id: "contrast", kind: "contrast", question: routes.contrast.question, material, property: focus, scope: routes.contrast.scope },
    { id: "mechanism", kind: "mechanism", question: routes.mechanism.question, material, property: focus, scope: routes.mechanism.scope },
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

type RouteSet = Record<"survey" | "contrast" | "mechanism", { question: string; scope: string }>;

/**
 * Turn a broad prompt into three domain-shaped retrieval questions.  The
 * fallback must not invent an answer, but it should still expose the concrete
 * variables a researcher would search for instead of paraphrasing a generic
 * review workflow.
 */
function routeText(originalQuestion: string, material: string, focus: string, kind: FocusKind, language: "zh" | "en"): RouteSet {
  if (language === "en") {
    const questions = ({
      transition: {
        survey: `Which transition ranges, phase assignments, and primary structural, thermal, magnetic, or electrical signals are reported for ${material} “${focus}”?`,
        contrast: `How does reported ${material} “${focus}” change across bulk, ceramic, and thin-film sample states, heating or cooling paths, and measurement atmospheres?`,
        mechanism: `For ${material} “${focus}”, which located signals distinguish a structural or ferroic transition from decomposition or a measurement artefact?`,
      },
      electrochemical: {
        survey: `Which cycle counts, retention definitions, current rates, and voltage windows underlie reported ${material} “${focus}”?`,
        contrast: `At matched composition, loading, current rate, voltage window, and cycle count, which ${material} “${focus}” reports remain comparable?`,
        mechanism: `Which post-test structural, chemical, and electrochemical observations distinguish competing explanations for ${material} “${focus}”?`,
      },
      transport: {
        survey: `Which values, temperature or frequency ranges, geometries, and uncertainty statements are reported for ${material} “${focus}”?`,
        contrast: `When geometry, contacts, sample state, calibration, and temperature or frequency range are aligned, which ${material} “${focus}” reports agree or diverge?`,
        mechanism: `Which raw transport and control measurements distinguish intrinsic ${material} “${focus}” from contact, electrode, or leakage contributions?`,
      },
      electronic: {
        survey: `Which experimental and computational values, methods, sample states, and uncertainties are reported for ${material} “${focus}”?`,
        contrast: `How do method, sample state, boundary conditions, and analysis convention affect reported ${material} “${focus}”?`,
        mechanism: `Which primary spectra or response curves discriminate between competing interpretations of ${material} “${focus}”?`,
      },
      synthesis: {
        survey: `Which precursor, stoichiometry, atmosphere, temperature, time, and phase-purity records define successful ${material} “${focus}”?`,
        contrast: `At matched composition and characterization criteria, which process variables change the reported ${material} “${focus}”?`,
        mechanism: `Which controlled process comparisons distinguish the proposed formation pathways for ${material} “${focus}”?`,
      },
      mechanism: {
        survey: `Which competing mechanisms and source-located observations are reported for ${material} “${focus}”?`,
        contrast: `Under which sample states, environments, and measurement protocols do reports of ${material} “${focus}” support different mechanisms?`,
        mechanism: `Which controls and raw observations can falsify each proposed mechanism for ${material} “${focus}”?`,
      },
      property: {
        survey: `Which values, operational definitions, sample conditions, primary measurements, and uncertainties are reported for ${material} “${focus}”?`,
        contrast: `After aligning sample state, environment, method, and uncertainty, which ${material} “${focus}” reports are comparable or contradictory?`,
        mechanism: `Which controls and primary observations distinguish intrinsic ${material} “${focus}” from plausible confounders?`,
      },
    } satisfies Record<FocusKind, Record<"survey" | "contrast" | "mechanism", string>>)[kind];
    const boundary = `Bounded by the original intent “${originalQuestion}”; retain source locations and incompatible conditions, and do not infer a value or mechanism from the prompt.`;
    return {
      survey: { question: questions.survey, scope: boundary },
      contrast: { question: questions.contrast, scope: boundary },
      mechanism: { question: questions.mechanism, scope: boundary },
    };
  }
  const questions = ({
    transition: {
      survey: `${material} 的“${focus}”研究分别报告了哪些转变温区、相结构指派，以及结构、热学、磁学或电学原始信号？`,
      contrast: `${material} 的“${focus}”在体相、陶瓷与薄膜样品、升降温路径和测试气氛之间是否可直接比较？`,
      mechanism: `${material} 的“${focus}”中，哪些可定位信号能区分结构或铁性转变、材料分解与测量伪影？`,
    },
    electrochemical: {
      survey: `${material} 的“${focus}”分别基于多少循环、何种保持率定义、倍率与电压窗口？`,
      contrast: `在组成、载量、倍率、电压窗口与循环数对齐后，哪些 ${material}“${focus}”报告仍可比较？`,
      mechanism: `哪些循环后结构、化学与电化学观测能区分 ${material}“${focus}”的竞争解释？`,
    },
    transport: {
      survey: `${material} 的“${focus}”报告分别采用哪些数值、温度或频率范围、测量几何与不确定度？`,
      contrast: `对齐几何、接触方式、样品状态、校准及温度或频率范围后，${material} 的“${focus}”报告哪些一致、哪些分歧？`,
      mechanism: `哪些原始输运与对照测量能区分 ${material} 本征“${focus}”和接触、电极或漏电贡献？`,
    },
    electronic: {
      survey: `${material} 的“${focus}”有哪些实验与计算数值，其方法、样品状态和不确定度分别是什么？`,
      contrast: `实验或计算方法、样品状态、边界条件与分析约定如何影响 ${material} 的“${focus}”报告？`,
      mechanism: `哪些原始谱线或响应曲线能区分 ${material}“${focus}”的竞争解释？`,
    },
    synthesis: {
      survey: `${material} 的“${focus}”由哪些前驱体、化学计量、气氛、温度、时间与物相纯度记录界定？`,
      contrast: `在组成与表征判据对齐后，哪些工艺变量改变了 ${material} 的“${focus}”报告？`,
      mechanism: `哪些受控工艺对比能区分 ${material}“${focus}”的候选形成路径？`,
    },
    mechanism: {
      survey: `${material} 的“${focus}”有哪些竞争机制及可定位原始观测？`,
      contrast: `在哪些样品状态、环境与测试协议下，${material} 的“${focus}”报告支持不同机制？`,
      mechanism: `哪些对照与原始观测可以分别证伪 ${material}“${focus}”的候选机制？`,
    },
    property: {
      survey: `${material} 的“${focus}”有哪些报告值、操作性定义、样品条件、原始测量与不确定度？`,
      contrast: `对齐样品状态、环境、方法与不确定度后，哪些 ${material}“${focus}”报告可比较或相互矛盾？`,
      mechanism: `哪些对照与原始观测能区分 ${material} 本征“${focus}”和潜在混杂因素？`,
    },
  } satisfies Record<FocusKind, Record<"survey" | "contrast" | "mechanism", string>>)[kind];
  const boundary = `以原问题“${originalQuestion}”为边界；保留来源定位与不兼容条件，不从问题文本推断数值或机制。`;
  return {
    survey: { question: questions.survey, scope: boundary },
    contrast: { question: questions.contrast, scope: boundary },
    mechanism: { question: questions.mechanism, scope: boundary },
  };
}
