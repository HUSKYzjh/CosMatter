import { For, Show, createEffect, createMemo, createSignal, on } from "solid-js";
import { graphDoi } from "./graphSearch";
import type { LiteratureGraphNode } from "./model";
import { displayPaperTitle } from "./paperTitle";
import type { PaperWorkflowState } from "./paperWorkflowState";
import type { ReadingRouteAction, ReadingRouteEntry } from "./readingRoute";
import "./atlas-reading-index.css";

const pageSize = 6;

export function AtlasReadingIndex(props: {
  locale: "zh" | "en";
  entries: ReadingRouteEntry[];
  nodes: Map<string, LiteratureGraphNode>;
  scope: string;
  selectedId: string | null;
  select: (node: LiteratureGraphNode) => void;
  stateLabel: (state: PaperWorkflowState) => string;
  routeSummary: string;
  hasGuide: boolean;
  shortfall: string | null;
}) {
  const t = (zh: string, en: string) => props.locale === "zh" ? zh : en;
  const titleAnchorLabel = (match: "material-and-context" | "context" | "material" | "none") => ({
    "material-and-context": t("任务对象与维度双命中", "material + task-context title anchors"),
    material: t("仅对象命中 · 研究维度待核对", "material only · task context needs review"),
    context: t("仅维度命中 · 研究对象待核对", "task context only · material needs review"),
    none: t("题名未命中任务锚点 · 优先人工判读", "no task title anchor · review first"),
  }[match]);
  const researchTrackLabel = (track: "exact_material" | "mechanism_analogue" | "algorithm" | "unclassified_legacy", counterevidenceOnly: boolean) => {
    const labels = {
      exact_material: t("同体系", "exact material"),
      mechanism_analogue: t("机制类比", "mechanism analogue"),
      algorithm: t("算法路线", "algorithm route"),
      unclassified_legacy: t("旧版未分类", "legacy unclassified"),
    };
    return `${labels[track]}${counterevidenceOnly ? t(" · 仅反证", " · counterevidence only") : ""}`;
  };
  const routeActionLabel = (action: ReadingRouteAction) => ({
    "recover-pdf": t("恢复 PDF 解析", "recover PDF parsing"), "register-source-map": t("登记来源定位", "register source locations"),
    "review-evidence": t("审核材料事实与证据", "review facts and evidence"), "audit-provenance": t("完成精确来源审计", "complete exact provenance audit"),
    "verify-evidence": t("核对已接受证据", "verify accepted evidence"), "select-pdf": t("选择授权 PDF", "select an authorized PDF"),
    "screen-paper": t("完成人工筛选", "complete human screening"), "load-screening": t("载入人工筛选清单", "load the human checklist"),
    "wait-for-parse": t("等待私有解析", "wait for private parsing"),
    "inspect-saved-parse": t("查看解析记录", "inspect saved parse"),
  } satisfies Record<ReadingRouteAction, string>)[action];

  const [page, setPage] = createSignal(0);
  const pageCount = () => Math.ceil(props.entries.length / pageSize);
  const current = () => Math.min(page(), Math.max(0, pageCount() - 1));
  const start = () => current() * pageSize;
  const shown = createMemo(() => props.entries.slice(start(), start() + pageSize));
  const selectedIndex = () => props.entries.findIndex(entry => entry.nodeId === props.selectedId);
  createEffect(on(() => props.scope, () => setPage(0)));
  createEffect(on(selectedIndex, index => { if (index >= 0) setPage(Math.floor(index / pageSize)); }));
  let list: HTMLOListElement | undefined;
  function changePage(next: number) {
    setPage(next);
    list?.querySelector("button")?.focus();
  }
  return <div class="atlas-reading-index">
    <div class="reading-index-heading">
      <h2>{t("文献阅读目录", "Paper reading index")}</h2>
      <Show when={props.entries.length}><div class="reading-index-controls">
        <span role="status">{t(`第 ${start() + 1}–${start() + shown().length} 篇，共 ${props.entries.length} 篇`,
          `${start() + 1}–${start() + shown().length} of ${props.entries.length} papers`)}</span>
        <Show when={pageCount() > 1}><nav aria-label={t("阅读目录翻页", "Reading index pages")}>
          <button type="button" disabled={current() === 0} onClick={() => changePage(current() - 1)} aria-label={t("上一页", "Previous page")}>←</button>
          <button type="button" disabled={current() + 1 >= pageCount()} onClick={() => changePage(current() + 1)} aria-label={t("下一页", "Next page")}>→</button>
        </nav></Show>
      </div></Show>
    </div>
    <details class="reading-index-policy">
      <summary>{t("阅读顺序依据", "How papers are ordered")}</summary>
      <p>{props.routeSummary} · {props.hasGuide
        ? t("先按已登记的审核动作排序，再采用后端三轨阅读顺序。题名和任务边界决定轨道，科学相关性仍需核对原文。仅反证条目只用于核对反例。",
          "Recorded review actions come first, followed by the guide’s three tracks. Tracks use titles and mission scope. Scientific relevance requires source review. Counterevidence-only entries are reserved for checking counterexamples.")
        : t("先按审核动作排序，同一动作内按题名与任务对象、研究维度的匹配情况排列。科学相关性仍需核对原文。",
          "Recorded review actions come first. Within each action, titles matching the task material and context take priority. Scientific relevance requires source review.")}</p>
    </details>
    <Show when={props.shortfall}>{summary => <p class="route-shortfall-warning" role="status">{summary()}</p>}</Show>
    <Show when={shown().length} fallback={<p>{t("当前没有待查阅论文。", "No papers in the reading queue.")}</p>}>
      <ol class="fleet-reading-cards" start={start() + 1} ref={list} aria-label={t("按阅读顺序排列的论文", "Papers in reading order")}>
        <For each={shown()}>{entry => {
          const node = () => props.nodes.get(entry.nodeId);
          const details = () => {
            const paper = node();
            return paper ? [paper.publicationYear, paper.source, graphDoi(paper)].filter(Boolean).join(" · ") : "";
          };
          const isCurrent = () => props.selectedId === entry.nodeId;
          return <li><button type="button" class="fleet-formation-slot" data-document-id={entry.documentId}
            aria-current={isCurrent() ? "true" : undefined} onClick={() => { const paper = node(); if (paper) props.select(paper); }}>
            <span class="reading-index-number"><span class="reading-index-sr">{t("航线 ", "Route ")}</span>{String(entry.ordinal).padStart(2, "0")}</span>
            <span class="reading-index-paper">
              <strong>{displayPaperTitle(entry.title)}</strong>
              <span class="reading-index-citation" title={entry.documentId}>{details() || entry.documentId}</span>
            </span>
            <span class="reading-index-review">
              <span>{entry.researchTrack ? researchTrackLabel(entry.researchTrack, entry.routeEligibility === "counterevidence_only") : titleAnchorLabel(entry.titleAnchorMatch)}</span>
              <span title={props.stateLabel(entry.workflowState)}>{routeActionLabel(entry.action)}</span>
            </span>
            <span class="reading-index-location" aria-hidden="true">{isCurrent() ? t("已选中", "Selected") : "↗"}</span>
          </button></li>;
        }}</For>
      </ol>
    </Show>
  </div>;
}
