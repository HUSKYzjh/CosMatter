import { For, createSignal } from "solid-js";

import type { ImportedBundle } from "./model";

type NodeTone = "blue" | "teal" | "violet" | "orange" | "rose";
interface GraphNode { id: string; title: string; kind: string; detail: string; tone: NodeTone; x: number; y: number; }

const BASE_NODES: GraphNode[] = [
  { id: "material", title: "材料体系", kind: "SCOPE", detail: "研究对象的命名与组成边界。", tone: "blue", x: 14, y: 25 },
  { id: "property", title: "目标性质", kind: "QUESTION", detail: "要比较或解释的性质定义。", tone: "teal", x: 41, y: 14 },
  { id: "conditions", title: "实验条件", kind: "CONDITION", detail: "应变、厚度、基底、缺陷与表征字段。", tone: "violet", x: 67, y: 25 },
  { id: "evidence", title: "证据门槛", kind: "EVIDENCE", detail: "来源定位、条件字段与人工审查状态。", tone: "orange", x: 58, y: 62 },
  { id: "counter", title: "反例路线", kind: "ROUTE", detail: "保留冲突及其待检验的来源路径。", tone: "rose", x: 25, y: 68 },
];

export function GraphNetwork(props: { bundle: ImportedBundle }) {
  const [selected, setSelected] = createSignal(BASE_NODES[0].id);
  const active = () => BASE_NODES.find((node) => node.id === selected()) ?? BASE_NODES[0];

  return (
    <main class="discovery-stage graph-stage">
      <header class="stage-header">
        <div><p class="stage-kicker">COSMATTER / GRAPH NETWORK</p><h1>任务关系图谱</h1><p>用图谱浏览研究边界与证据依赖；当前尚未连接外部文献库。</p></div>
        <div class="stage-tools"><button type="button" aria-label="缩小图谱">−</button><button type="button" aria-label="聚焦图谱">◎</button><button type="button" aria-label="放大图谱">+</button></div>
      </header>
      <section class="graph-meta" aria-label="图谱筛选"><span>任务 <strong>{props.bundle.mission.missionId}</strong></span><span>材料 <strong>{props.bundle.mission.material}</strong></span><span>外部节点 <strong>0</strong></span><span>已批准证据 <strong>0</strong></span></section>
      <section class="graph-workspace" aria-label="任务关系网络">
        <div class="graph-canvas">
          <div class="graph-title"><span>LOCAL RESEARCH MAP</span><strong>概念节点与审查关系</strong><small>边线说明依赖关系，不表示因果或文献引用。</small></div>
          <svg class="graph-edges" viewBox="0 0 1000 590" preserveAspectRatio="none" aria-hidden="true">
            <path d="M 250 215 C 360 132, 392 124, 468 140" /><path d="M 555 150 C 650 155, 690 205, 720 254" /><path d="M 728 315 C 685 410, 625 435, 595 448" /><path d="M 505 465 C 370 480, 316 465, 290 425" /><path d="M 245 347 C 218 305, 216 270, 233 230" /><path class="dashed" d="M 315 415 C 450 340, 570 286, 690 260" />
          </svg>
          <For each={BASE_NODES}>{(node) => <button type="button" class={`graph-node tone-${node.tone}`} classList={{ active: selected() === node.id }} style={{ left: `${node.x}%`, top: `${node.y}%` }} onClick={() => setSelected(node.id)}><span>{node.kind}</span><strong>{node.title}</strong><small>{node.detail}</small></button>}</For>
        </div>
        <aside class="graph-inspector" aria-label="节点检查器"><p class="stage-kicker">NODE INSPECTOR</p><span class={`inspector-dot tone-${active().tone}`} /> <h2>{active().title}</h2><small>{active().kind}</small><p>{active().detail}</p><dl><div><dt>任务材料</dt><dd>{props.bundle.mission.material}</dd></div><div><dt>当前状态</dt><dd>本地导航对象</dd></div><div><dt>证据结论</dt><dd>未生成</dd></div></dl><button type="button">将此节点加入审查计划 →</button></aside>
      </section>
      <footer class="stage-note">图谱只用于界面导航与数据结构预览；当真实论文进入系统时，每条边须带有可定位的来源与审查记录。</footer>
    </main>
  );
}