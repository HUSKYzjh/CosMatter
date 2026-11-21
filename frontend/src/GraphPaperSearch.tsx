import { For, Show, createEffect, createMemo, createSignal, createUniqueId, on, type JSX } from "solid-js";
import { graphDisplayLabel, graphDoi } from "./graphSearch";
import type { LiteratureGraphCoverage, LiteratureGraphNode } from "./model";
import "./graph-paper-search.css";

const pageSize = 6;

export function GraphPaperSearch(props: {
  children: JSX.Element;
  locale: "zh" | "en";
  query: string;
  setQuery: (value: string) => void;
  matches: LiteratureGraphNode[];
  visibleIds: Set<string>;
  selectedId: string | null;
  coverage?: LiteratureGraphCoverage;
  select: (node: LiteratureGraphNode) => void;
  openChecklist?: () => void;
  inputRef: (input: HTMLInputElement) => void;
}) {
  const t = (zh: string, en: string) => props.locale === "zh" ? zh : en;
  const searchId = createUniqueId();
  let input!: HTMLInputElement;
  let results!: HTMLOListElement;
  const [page, setPage] = createSignal(0);
  const pages = createMemo(() => Math.ceil(props.matches.length / pageSize));
  const current = createMemo(() => Math.min(page(), Math.max(0, pages() - 1)));
  const shown = createMemo(() => props.matches.slice(current() * pageSize, (current() + 1) * pageSize));
  createEffect(on(() => props.query, () => setPage(0)));

  function clear() {
    props.setQuery("");
    input.focus();
  }
  function changePage(index: number) {
    setPage(index);
    results?.querySelector("button")?.focus();
  }

  return <section class="graph-paper-search" aria-labelledby={searchId}>
    <label class="graph-search-name" id={searchId} for={searchId + "-input"}>{t("检索当前星图", "Search this map")}</label>
    <div class="graph-search-input"><input id={searchId + "-input"} ref={element => { input = element; props.inputRef(element); }} type="search" value={props.query} autocomplete="off"
      placeholder={t("题名、DOI 或文档 ID", "Title, DOI or ID")}
      title={t("按题名、DOI、文档 ID、来源或年份检索", "Search by title, DOI, document ID, source or year")}
      onInput={event => props.setQuery(event.currentTarget.value)}
      onKeyDown={event => {
        if (event.isComposing || event.keyCode === 229) return;
        if (event.key === "Escape") clear();
        if (event.key === "ArrowDown" && shown().length) { event.preventDefault(); results?.querySelector("button")?.focus(); }
        if (event.key === "Enter" && props.matches.length === 1) { event.preventDefault(); props.select(shown()[0]); }
      }} />
      <Show when={props.query}><button type="button" onClick={clear}>{t("清除检索", "Clear search")}</button></Show>
    </div>
    {props.children}
    <Show when={props.coverage || props.openChecklist}><div class="graph-search-labels">
      <Show when={props.coverage}>{coverage => <>
        <span>{t(`图中 ${coverage().visibleCandidateCount} / ${coverage().candidateCount} 篇候选`, `${coverage().visibleCandidateCount} of ${coverage().candidateCount} candidates on map`)}</span>
        <Show when={coverage().acceptedEvidenceCount > 0}><span>{t(`已关联 ${coverage().linkedAcceptedEvidenceCount} / ${coverage().acceptedEvidenceCount} 条已接受证据`, `${coverage().linkedAcceptedEvidenceCount} of ${coverage().acceptedEvidenceCount} accepted cards linked`)}</span></Show>
      </>}</Show>
      <Show when={props.openChecklist}>{open => <button class="graph-checklist-link" type="button" onClick={() => open()()}>{t("查看完整候选清单", "Open full candidate checklist")}</button>}</Show>
    </div></Show>
    <Show when={props.query.trim()}>
      <div class="graph-search-count" role="status">{props.matches.length
        ? t(`匹配 ${props.matches.length} 个节点，显示第 ${current() * pageSize + 1}–${current() * pageSize + shown().length} 项`, `${props.matches.length} matching nodes, showing ${current() * pageSize + 1}–${current() * pageSize + shown().length}`)
        : t("当前星图没有匹配项。可缩短检索词或使用文档 ID。", "No matches in this map. Try fewer terms or a document ID.")}</div>
      <Show when={shown().length}><ol class="graph-search-results" ref={results} aria-label={t("检索结果", "Search results")}>
        <For each={shown()}>{node => <li><button type="button" aria-current={props.selectedId === node.nodeId ? "true" : undefined}
          onClick={() => props.select(node)}>
          <strong>{graphDisplayLabel(node)}</strong>
          <span>{[node.publicationYear, node.source, graphDoi(node), node.nodeId].filter(Boolean).join(" · ")}</span>
          <Show when={!props.visibleIds.has(node.nodeId)}><em>{t("显示被筛选隐藏的节点", "Reveal filtered node")}</em></Show>
        </button></li>}</For>
      </ol></Show>
      <Show when={pages() > 1}><nav class="graph-search-pages" aria-label={t("检索结果翻页", "Search result pages")}>
        <button type="button" disabled={current() === 0} onClick={() => changePage(current() - 1)}>{t("上一页", "Previous")}</button>
        <button type="button" disabled={current() + 1 >= pages()} onClick={() => changePage(current() + 1)}>{t("下一页", "Next")}</button>
      </nav></Show>
    </Show>
  </section>;
}
