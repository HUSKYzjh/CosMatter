import { For, Show, createMemo, createSignal } from "solid-js";

import { demoBundle, readBundle, type ImportedBundle } from "./model";
import { ResearchWorkflow } from "./ResearchWorkflow";
import { GraphNetwork } from "./GraphNetwork";

type Theme = "light" | "dark" | "eye";
type View = "discover" | "workflow" | "graph";
type DiscoveryKind = "scope" | "condition" | "evidence" | "question";

interface DiscoveryObject {
  id: string;
  kind: DiscoveryKind;
  index: number;
  title: string;
  detail: string;
  footer: string;
}

const EXAMPLES = [
  "为什么不同薄膜研究对 BiFeO3 应变相变有相反结论？",
  "氧空位如何改变钙钛矿薄膜的铁电相稳定性？",
  "如何比较不同表征方法得到的材料相边界？",
  "哪些实验条件会造成材料文献结论不可直接比较？"
];

const KIND_LABEL: Record<DiscoveryKind, string> = {
  scope: "任务范围",
  condition: "条件簇",
  evidence: "已批准证据",
  question: "待核查问题"
};

function createObjects(bundle: ImportedBundle): DiscoveryObject[] {
  const { mission } = bundle;
  return [
    {
      id: "scope",
      kind: "scope",
      index: 1,
      title: mission.material,
      detail: `关注性质：${mission.property}。当前范围：${mission.scope}。`,
      footer: "MissionBrief · 本地任务边界"
    },
    {
      id: "condition",
      kind: "condition",
      index: 2,
      title: "条件差分",
      detail: "应变、厚度、衬底、氧空位与表征方法需被显式记录后才能比较。",
      footer: "ConditionMatrix · 待由审核工件补全"
    },
    {
      id: "evidence",
      kind: "evidence",
      index: 3,
      title: "证据门禁",
      detail: "仅显示具有来源定位、条件字段和 accepted 审核结论的短证据。",
      footer: "EvidenceCard · 不加载全文"
    },
    {
      id: "question",
      kind: "question",
      index: 4,
      title: "反例航线",
      detail: "下一步需由人工批准主检索与反例检索计划，不能由界面自动推断。",
      footer: "FlightPlan · 人工批准后可执行"
    }
  ];
}

export function App() {
  const [bundle, setBundle] = createSignal<ImportedBundle>(demoBundle);
  const [question, setQuestion] = createSignal(demoBundle.mission.question);
  const [theme, setTheme] = createSignal<Theme>("light");
  const [view, setView] = createSignal<View>("discover");
  const [status, setStatus] = createSignal("当前显示合成演示对象；未发起网络请求。");
  const [filter, setFilter] = createSignal<DiscoveryKind | "all">("all");

  const objects = createMemo(() => createObjects(bundle()));
  const visibleObjects = createMemo(() => objects().filter((item) => filter() === "all" || item.kind === filter()));

  function beginDiscovery() {
    const trimmed = question().trim();
    if (!trimmed) {
      setStatus("请先输入一个可审核的研究问题。");
      return;
    }
    setBundle((current) => ({ ...current, mission: { ...current.mission, question: trimmed } }));
    setStatus("已更新本地发现台；未调用模型、检索服务或第三方 API。");
  }

  function loadExample(example: string) {
    setQuestion(example);
    setStatus("已载入示例问题；需点击“更新发现台”才会改变当前本地预览。");
  }

  async function importBundle(file: File | undefined) {
    if (!file) return;
    try {
      const parsed = readBundle(JSON.parse(await file.text()));
      setBundle(parsed);
      setQuestion(parsed.mission.question);
      setStatus(`已导入 ${file.name}；仅解析浏览器本地选择的 JSON 文件。`);
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "无法解析该 JSON 工件。");
    }
  }

  return (
    <div class={`workbench theme-${theme()}`}>
      <aside class="research-rail" aria-label="研究控制栏">
        <a class="wordmark" href="/" aria-label="CosMatter 研究发现页">Cos<span>Matter</span></a>
        <p class="rail-kicker">MATERIALS / DISCOVERY</p>
        <nav class="view-switcher" aria-label="工作台视图">
          <button type="button" classList={{ active: view() === "discover" }} onClick={() => setView("discover")}>发现</button>
          <button type="button" classList={{ active: view() === "workflow" }} onClick={() => setView("workflow")}>工作流</button>
          <button type="button" classList={{ active: view() === "graph" }} onClick={() => setView("graph")}>图谱</button>
        </nav>
        <section class="rail-stats" aria-label="当前发现范围">
          <div><strong>01</strong><span>当前任务</span></div>
          <div><strong>04</strong><span>研究对象</span></div>
          <div><strong>0</strong><span>已批准证据</span></div>
          <div><strong>0</strong><span>外部调用</span></div>
        </section>
        <label class="question-label">
          研究问题
          <textarea value={question()} onInput={(event) => setQuestion(event.currentTarget.value)} rows="4" />
        </label>
        <button class="primary-action" type="button" onClick={beginDiscovery}>更新发现台</button>
        <section class="examples" aria-labelledby="examples-title">
          <p id="examples-title" class="rail-kicker">建议问题</p>
          <For each={EXAMPLES}>{(example, index) => (
            <button type="button" onClick={() => loadExample(example)}>
              <span>{String(index() + 1).padStart(2, "0")}</span>{example}
            </button>
          )}</For>
        </section>
        <label class="import-control">
          导入已脱敏 UI JSON
          <input type="file" accept="application/json,.json" onChange={(event) => void importBundle(event.currentTarget.files?.[0])} />
        </label>
        <div class="rail-footer">
          <label>主题
            <select value={theme()} onChange={(event) => setTheme(event.currentTarget.value as Theme)}>
              <option value="light">浅色</option><option value="dark">深色</option><option value="eye">护眼</option>
            </select>
          </label>
          <small>密钥、全文和运行日志不进入浏览器。</small>
        </div>
      </aside>

      <Show when={view() === "discover"} fallback={view() === "workflow" ? <ResearchWorkflow bundle={bundle()} /> : <GraphNetwork bundle={bundle()} />}>
      <main class="discovery-stage">
        <header class="stage-header">
          <div><p class="stage-kicker">COSMATTER / RESEARCH DISCOVERY</p><h1>发现材料分歧</h1><p>{bundle().mission.question}</p></div>
          <div class="stage-tools"><button type="button" aria-label="筛选研究对象">⌘</button><button type="button" aria-label="聚焦画布">◎</button><button type="button" aria-label="放大画布">＋</button></div>
        </header>
        <section class="scope-strip" aria-label="当前任务范围">
          <span>材料 <strong>{bundle().mission.material}</strong></span><span>性质 <strong>{bundle().mission.property}</strong></span><span>范围 <strong>{bundle().mission.scope}</strong></span><span>{bundle().source === "demo" ? "合成演示工件" : "本地导入工件"}</span>
        </section>
        <section class="discovery-toolbar" aria-label="研究对象筛选">
          <p>{status()}</p>
          <div class="filter-group"><For each={["all", "scope", "condition", "evidence", "question"] as const}>{(kind) => <button classList={{ selected: filter() === kind }} type="button" onClick={() => setFilter(kind)}>{kind === "all" ? "全部对象" : KIND_LABEL[kind]}</button>}</For></div>
        </section>
        <section class="discovery-canvas" aria-label="研究发现对象">
          <Show when={visibleObjects().length} fallback={<p class="empty-state">当前筛选没有可显示对象。</p>}>
            <For each={visibleObjects()}>{(item) => (
              <article class={`discovery-object kind-${item.kind}`}>
                <header><span>{String(item.index).padStart(2, "0")}</span><small>{KIND_LABEL[item.kind]}</small></header>
                <h2>{item.title}</h2><p>{item.detail}</p><footer>{item.footer}<b>→</b></footer>
              </article>
            )}</For>
          </Show>
        </section>
        <footer class="stage-note">对象仅由本地任务工件派生；它们是导航信息，不构成材料科学结论。</footer>
      </main>
      </Show>
    </div>
  );
}
