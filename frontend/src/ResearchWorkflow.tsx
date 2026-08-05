import { For, createSignal } from "solid-js";

import type { ImportedBundle } from "./model";

interface RouteNode {
  id: string;
  code: string;
  title: string;
  detail: string;
  guard: string;
  tone: "blue" | "teal" | "violet" | "orange" | "rose";
}

const ROUTE: RouteNode[] = [
  { id: "brief", code: "01", title: "任务锚定", detail: "固定材料、目标性质和适用范围，避免把相邻问题混为同一任务。", guard: "MissionBrief 已锁定", tone: "blue" },
  { id: "corpus", code: "02", title: "候选语料", detail: "记录候选论文与检索式；此处只呈现清单，不推导材料结论。", guard: "等待受控检索", tone: "teal" },
  { id: "conditions", code: "03", title: "条件归一", detail: "把应变、厚度、基底、缺陷与表征方法放入可比较字段。", guard: "ConditionMatrix 待补全", tone: "violet" },
  { id: "evidence", code: "04", title: "证据审查", detail: "每条主张必须能回到来源位置、条件字段与审查状态。", guard: "EvidenceGate 未放行", tone: "orange" },
  { id: "review", code: "05", title: "人工批准", detail: "由研究者确认主检索、反例检索和下一次阅读路线后才可执行。", guard: "FlightPlan 等待批准", tone: "rose" },
];

export function ResearchWorkflow(props: { bundle: ImportedBundle }) {
  const [selected, setSelected] = createSignal(ROUTE[0].id);
  const active = () => ROUTE.find((node) => node.id === selected()) ?? ROUTE[0];

  return (
    <main class="discovery-stage workflow-stage">
      <header class="stage-header">
        <div>
          <p class="stage-kicker">COSMATTER / RESEARCH WORKFLOW</p>
          <h1>证据导航路线</h1>
          <p>围绕「{props.bundle.mission.question}」建立一条可审查的阅读与验证路线。</p>
        </div>
        <div class="stage-tools" aria-label="路线工具">
          <button type="button" aria-label="缩小路线">−</button>
          <button type="button" aria-label="重置路线">◎</button>
          <button type="button" aria-label="放大路线">+</button>
        </div>
      </header>

      <section class="workflow-meta" aria-label="路线边界">
        <span>材料 <strong>{props.bundle.mission.material}</strong></span>
        <span>性质 <strong>{props.bundle.mission.property}</strong></span>
        <span>范围 <strong>{props.bundle.mission.scope}</strong></span>
        <span>状态 <strong>本地预览 / 零外部调用</strong></span>
      </section>

      <section class="workflow-layout" aria-label="研究工作流">
        <aside class="reading-guide">
          <p class="stage-kicker">READING GUIDE</p>
          <h2>当前阅读准则</h2>
          <ol>
            <li>先确认研究对象与可比范围。</li>
            <li>将实验条件与结论分开记录。</li>
            <li>把每条证据锚定到可定位来源。</li>
            <li>将冲突保留为待验证路线。</li>
          </ol>
          <div class="guide-status">
            <small>选中节点</small>
            <strong>{active().title}</strong>
            <p>{active().guard}</p>
          </div>
        </aside>

        <div class="roadmap-canvas">
          <div class="roadmap-heading">
            <span>RESEARCH LEARNING PATH</span>
            <strong>由问题驱动，而不是自动总结</strong>
            <small>每个节点是下一步的审查入口，不是事实结论。</small>
          </div>
          <svg class="workflow-edges" viewBox="0 0 900 530" preserveAspectRatio="none" aria-hidden="true">
            <defs><marker id="workflow-arrow" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M 0 0 L 8 4 L 0 8 z" /></marker></defs>
            <path d="M 220 168 C 290 168, 292 168, 356 168" marker-end="url(#workflow-arrow)" />
            <path d="M 510 168 C 565 168, 620 168, 676 168" marker-end="url(#workflow-arrow)" />
            <path d="M 760 250 C 760 310, 660 350, 540 364" marker-end="url(#workflow-arrow)" />
            <path d="M 410 364 C 290 364, 230 364, 180 364" marker-end="url(#workflow-arrow)" />
          </svg>
          <For each={ROUTE}>{(node, index) => (
            <button
              type="button"
              class={`route-node tone-${node.tone}`}
              classList={{ active: selected() === node.id, [`route-${index() + 1}`]: true }}
              onClick={() => setSelected(node.id)}
            >
              <span class="route-code">{node.code}</span>
              <span class="route-kind">{node.guard}</span>
              <strong>{node.title}</strong>
              <p>{node.detail}</p>
              <footer>审查入口 <b>→</b></footer>
            </button>
          )}</For>
        </div>
      </section>
      <footer class="stage-note">此路线当前仅由本地任务工件派生；后续连接检索或模型服务前，仍需显式批准。</footer>
    </main>
  );
}