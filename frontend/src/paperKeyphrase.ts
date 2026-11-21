import { displayPaperTitle } from "./paperTitle";

// Match specific measurements, mechanisms and techniques before broader subjects.
// English labels quote the match; Chinese glosses only translate an observed term.
const terms: ReadonlyArray<readonly [RegExp, string, string?]> = [
  [/\bthermal depolarization temperature\b/i, "热退极化温度"],
  [/\b(?:curie temperature|curie point)\b/i, "居里温度"],
  [/\bn[ée]el temperature\b/i, "奈尔温度"],
  [/\bpolarization rotation\b/i, "极化旋转"],
  [/\b(?:antiphase|anti-phase) domain boundar(?:y|ies)\b/i, "反相畴界"],
  [/\bstationary domain walls?\b/i, "静止畴壁"],
  [/\bdomain[- ]wall motion\b/i, "畴壁运动"],
  [/\bferroelastic domains?\b/i, "铁弹畴"],
  [/\bferroelectric domains?\b/i, "铁电畴"],
  [/\bdomain walls?\b/i, "畴壁"],
  [/\bshear piezoelectricity\b/i, "剪切压电效应"],
  [/\borbital ordering\b/i, "轨道有序"],
  [/\bcation and magnetic order\b/i, "阳离子与磁有序"],
  [/\b([ab])[- ]site cation order(?:ing)?\b/i, "位阳离子有序"],
  [/\b([ab])[- ]site disorder\b/i, "位无序"],
  [/\b([ab])\s*[- ]\s*site ordered\b/i, "位有序"],
  [/\bpartial cation order(?:ing)?\b/i, "部分阳离子有序"],
  [/\bcation order(?:ing)? and dielectric properties\b/i, "阳离子有序与介电性质"],
  [/\bcation order(?:ing)? in complex oxides\b/i, "复合氧化物阳离子有序", "complex oxide cation order"],
  [/\bdouble double cation order\b/i, "双重阳离子有序"],
  [/\bferroelectric phase transitions?\b/i, "铁电相变"],
  [/\bstructural phase transitions?\b/i, "结构相变"],
  [/\bnoncentrosymmetric structural transitions?\b/i, "非中心对称结构转变"],
  [/\bspatial inversion symmetry breaking\b/i, "空间反演对称性破缺"],
  [/\bsymmetry[- ]forbidden interfaces?\b/i, "对称性禁戒界面"],
  [/\boxygen octahedr(?:a|al) rotations?\b/i, "氧八面体转动"],
  [/\blongitudinal and transverse optical phonons?\b/i, "纵横光学声子", "LO/TO phonons"],
  [/\btransverse optical phonons?\b/i, "横向光学声子"],
  [/\blongitudinal optical phonons?\b/i, "纵向光学声子"],
  [/\bdipolar glass\b/i, "偶极玻璃"],
  [/\bfree[- ]energy landscapes?\b/i, "自由能景观"],
  [/\bantiferrodistortive instabilit(?:y|ies)\b/i, "反铁畸变不稳定性"],
  [/\bimpurity[- ]induced polar states?\b/i, "杂质诱导极性态"],
  [/\bdiffuse scattering\b/i, "漫散射"],
  [/\bdielectric anomal(?:y|ies)\b/i, "介电异常"],
  [/\bdielectric loss\b/i, "介电损耗"],
  [/\bepitaxial strain\b/i, "外延应变"],
  [/\bcoherently strained\b/i, "相干应变"],
  [/\banelastic and dielectric measurements?\b/i, "滞弹与介电测量"],
  [/\bkinetic monte carlo\b/i, "动力学蒙特卡洛"],
  [/\bbayesian optimi[sz]ation\b/i, "贝叶斯优化"],
  [/\b(?:stem\/eels|haadf[- ]stem)\b/i, ""],
  [/\bmolecular dynamics\b/i, "分子动力学"],
  [/\bhigh[- ]pressure synthesis\b/i, "高压合成"],
  [/\bphysical tensors?\b/i, "物性张量"],
  [/\belectromechanical responses?\b/i, "机电响应"],
  [/\bsofc composite cathodes?\b/i, "SOFC 复合阴极"],
  [/\bshort[- ]period [\p{L}\p{N}_/∕.-]+ superlattices?\b/iu, "短周期超晶格", "short-period superlattice"],
  [/\bmicrowave frequenc(?:y|ies)\b/i, "微波频率"],
  [/\bferrimagnetism\b/i, "亚铁磁性"],
  [/\bcrystal chemistry\b/i, "晶体化学"],
  [/\boxygen[- ]deficient perovskites?\b/i, "缺氧钙钛矿"],
  [/\bmolecular ferroelec(?:tric|trics)\b/i, "分子铁电体"],
  [/\brelaxor ferroelectrics?\b/i, "弛豫铁电体"],
  [/\bcation order(?:ing)?\b/i, "阳离子有序"],
  [/\bferroelectric susceptibility\b/i, "铁电极化率"],
  [/\bdensity functional theory\b/i, "密度泛函理论"],
  [/\bcomplex perovskite structures?\b/i, "复合钙钛矿结构"],
  [/\bmagnetic and structural properties\b/i, "磁性与结构性质"],
  [/\bcumulative subject index\b/i, "主题累积索引"],
  [/\bdielectric (?:properties|response)\b/i, "介电性质"],
  [/\bphase diagram\b/i, "相图"],
];

const chineseTerm = /热退极化温度|居里温度|奈[耳尔]温度|极化(?:旋转|翻转|反转)|(?:反相|铁电|铁弹)畴壁|畴壁(?:运动|迁移)|剪切压电(?:效应|响应)|[AB]\s*位(?:阳离子)?(?:有序|无序)|阳离子有序|轨道有序|空间反演对称性破缺|氧八面体(?:转动|旋转)|(?:纵向|横向)?光学声子|漫散射|介电(?:损耗|异常|常数|响应)|压电(?:系数|响应)|(?:结构|铁电|磁性)相变|外延应变|相干应变|贝叶斯优化|(?:经典|第一性原理)?分子动力学|(?:动力学)?蒙特卡洛|密度泛函理论|自由能景观|反铁畸变|电畴|畴壁|超晶格/u;

const metadataId = /^(?:(?:doi\s*:\s*|https?:\/\/(?:dx\.)?doi\.org\/)?10\.\d{4,9}\/\S+|(?:arxiv:\s*)?\d{4}\.\d{4,5}(?:v\d+)?|(?:paper|doc(?:ument)?|node|work|record)[:_-]\S+|[0-9a-f-]{24,}|https?:\/\/\S+)$/iu;
const unknownTitle = /^(?:n\/?a|untitled|(?:no|unknown|missing) title|无题|未命名|题名未记录|标题未知)$/iu;
const filler = /\b(?:a|an|the|of|in|into|on|at|by|for|to|from|as|via|with|without|under|using|between|through|during|and|or|their|our|its|towards?|based|role|effects?|influence|new|novel|study|studies|analysis|analyses|investigation|overview|review|research|title|results?|evidence|properties|characterization|determination|dependence|tracking|mapping|investigating|understanding|measuring|assessing|evaluating)\b/giu;

function fallback(title: string): string {
  // Work along clause and word boundaries so a caption cannot end in half a word.
  // A letter after a noun can be a sample identifier, as in "thin film A".
  const fragments = title.replace(filler, (word, index: number) => word === "A" && index > 0 && index === title.length - 1 ? word : "|")
    .split(/[|:：;；,，、?!？！()[\]{}]+|(?:基于|关于|探讨|研究表明|及其|以及|影响|研究|分析|综述|应用|对于|中的|的|与)/u);
  let best = "", bestScore = 0;
  for (const [index, fragment] of fragments.entries()) {
    const part = fragment.trim();
    const useHanWords = part.length > 14 && /\p{Script=Han}/u.test(part) && typeof Intl.Segmenter === "function";
    const words = useHanWords
      ? Array.from(new Intl.Segmenter("zh", { granularity: "word" }).segment(part)).filter(word => word.isWordLike).map(word => word.segment)
      : part.split(/\s+/u).filter(Boolean);
    for (let start = 0; start < words.length; start++) {
      // Keep short descriptors beside their nouns, including chemical formulas.
      let phrase = "";
      for (const word of words.slice(start, start + 3)) {
        if (!/\p{L}/u.test(word)) break;
        const next = (phrase && !useHanWords ? phrase + " " : phrase) + word;
        if (phrase && next.length > 27) break;
        phrase = next;
      }
      if (phrase.length < 2 || metadataId.test(phrase)) continue;
      const hanCount = (phrase.match(/\p{Script=Han}/gu) ?? []).length;
      const score = Math.min(phrase.length + hanCount * 2, 22) + (start === 0 ? 3 : 0)
        + Number(hanCount > 0 && index > 0) - Math.max(0, phrase.length - 26);
      if (score > bestScore) { best = phrase; bestScore = score; }
    }
  }
  return best;
}

/** A navigation caption extracted from the bibliographic title, including for offline graphs. */
export function paperKeyphrase(title: string, locale: "zh" | "en" = "zh"): string {
  const text = displayPaperTitle(title).replace(/^\s*(?:title|题名)\s*[:：]\s*/iu, "")
    .replace(/\[!\/?(?:i|sub|sup)\]/giu, "")
    .replace(/[‐‑–−]/gu, "-").trim();
  if (!text || metadataId.test(text) || unknownTitle.test(text)) return "";
  const chinese = text.match(chineseTerm);
  if (chinese) return chinese[0];
  for (const [pattern, translation, shortEnglish] of terms) {
    const match = text.match(pattern);
    if (!match) continue;
    if (!translation) return match[0].toUpperCase();
    if (locale === "en") return shortEnglish ?? match[0];
    return match[1] ? match[1].toUpperCase() + " " + translation : translation;
  }
  return fallback(text);
}
