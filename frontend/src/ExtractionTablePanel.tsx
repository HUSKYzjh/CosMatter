import { For, Show, createMemo, createResource, createSignal } from "solid-js";
import { extractionCsv, extractionOrcaTasks, extractionStatuses, filterExtractionRows, readExtractionTable, type ExtractionStatus } from "./extractionTable";
import { isLoopbackWorkbenchLocation, localRunLink } from "./liveRunIdentity";
import { getExtractionTable } from "./localApi";
import { ActionButton } from "./uiPrimitives";
import "./extraction-table.css";

const labels: Record<ExtractionStatus, [string, string]> = {
  reviewed: ["已核对来源", "Source verified"],
  awaiting_extraction: ["待提取", "Awaiting extraction"],
  awaiting_review: ["待审核", "Awaiting review"],
  unverified_source: ["待核对来源", "Source unverified"],
};
const stances: Record<string, [string, string]> = {
  support: ["支持", "Support"], contradict: ["反证", "Contradiction"], context: ["背景", "Context"],
};
const pageSize = 20;

export function ExtractionTablePanel(props: { runId: string; locale: "zh" | "en" }) {
  const t = (zh: string, en: string) => props.locale === "zh" ? zh : en;
  const [table, { refetch }] = createResource(() => props.runId, async id => readExtractionTable(await getExtractionTable(id), id));
  const [query, setQuery] = createSignal("");
  const [status, setStatus] = createSignal<ExtractionStatus | "all">("all");
  const [property, setProperty] = createSignal("");
  const [page, setPage] = createSignal(1);
  const ready = () => table.state === "ready" ? table() : undefined;
  const properties = createMemo(() => [...new Set((ready()?.rows ?? []).flatMap(row => row.property_name ? [row.property_name] : []))].sort());
  const filtered = createMemo(() => filterExtractionRows(ready()?.rows ?? [], query(), status(), property()));
  const lastPage = () => Math.max(1, Math.ceil(filtered().length / pageSize));
  const currentPage = () => Math.min(page(), lastPage());
  const visibleRows = () => filtered().slice((currentPage() - 1) * pageSize, currentPage() * pageSize);
  const missing = () => t("未记录", "Unrecorded");
  const stance = (value: string) => Object.hasOwn(stances, value) ? t(...stances[value]) : value;
  const entries = (fields: Record<string, string | number | boolean | null>) => Object.entries(fields).map(([key, value]) => key + " = " + (value ?? missing())).join(" · ");
  const reset = () => { setQuery(""); setStatus("all"); setProperty(""); setPage(1); };
  async function download(format: "csv" | "orca") {
    const runId = ready()?.run_id;
    const rows = filtered();
    if (!runId || runId !== props.runId || !rows.length) return;
    const blob = format === "orca"
      ? new Blob([JSON.stringify(await extractionOrcaTasks(window.location.origin, runId, rows), null, 2), "\n"], { type: "application/json;charset=utf-8" })
      : new Blob(["\uFEFF", extractionCsv(runId, rows)], { type: "text/csv;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = runId + (format === "orca" ? "-orca-tasks.json" : "-extraction.csv");
    document.body.append(anchor);
    anchor.click();
    anchor.remove();
    window.setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  return <section class="extraction-panel" aria-label={t("跨文献证据对照表", "Cross-paper evidence table")}>
    <header class="extraction-heading"><div>
      <h2>{t("跨文献证据对照表", "Cross-paper evidence table")}</h2>
      <p>{t("按论文核对研究对象、测量条件和来源定位。已纳入但缺少已核对证据的论文单列为缺口。", "Compare materials, measurement conditions and sources by paper. Included papers awaiting verified evidence appear as gaps.")}</p>
    </div><ActionButton size="sm" busy={table.loading} busyLabel={t("读取中", "Loading")} onClick={() => void refetch()}>{t("刷新对照表", "Refresh table")}</ActionButton></header>
    <Show when={table.loading}><p role="status">{t("正在读取本次运行的文献和审核记录…", "Loading papers and review records for this run…")}</p></Show>
    <Show when={table.state === "errored"}><p role="alert">{t("无法读取本次运行的对照表。请检查本机工作台连接，再刷新对照表。", "The table for this run could not be read. Check the local workbench connection, then refresh the table.")}</p></Show>
    <Show when={ready()}>{current => <>
      <Show when={current().screening_status !== "current"}><p class="extraction-screening-note" role="status">{current().screening_status === "outdated"
        ? t("候选列表已变更。请在文献关系图中重新核对筛选清单，以更新纳入文献。", "The candidate list changed. Recheck screening in the literature map to update the included papers.")
        : t("本次运行尚未登记文献筛选清单。已核对的来源可单独列出。", "This run has no recorded screening checklist. Independently verified sources can still appear.")}</p></Show>
      <div class="extraction-counts">
        <span><strong>{current().summary.document_count}</strong> {t("篇文献", "papers")}</span>
        <span><strong>{current().summary.reviewed_count}</strong> {t("条已核对证据", "verified evidence rows")}</span>
        <span><strong>{current().summary.gap_count}</strong> {t("篇有待补齐", "papers with gaps")}</span>
      </div>
      <Show when={current().rows.length}>
        <div class="extraction-filters">
          <label>{t("搜索对照表", "Search the table")}<input type="search" value={query()} placeholder={t("文献、材料、条件或图号", "Paper, material, condition or figure")} onInput={event => { setQuery(event.currentTarget.value); setPage(1); }} /></label>
          <label>{t("审核状态", "Review status")}<select value={status()} onChange={event => { setStatus(event.currentTarget.value as ExtractionStatus | "all"); setPage(1); }}>
            <option value="all">{t("全部状态", "All statuses")}</option><For each={extractionStatuses}>{item => <option value={item}>{t(...labels[item])}</option>}</For>
          </select></label>
          <Show when={properties().length || property()}><label>{t("测量性质", "Measured property")}<select value={property()} onChange={event => { setProperty(event.currentTarget.value); setPage(1); }}>
            <option value="">{t("全部性质", "All properties")}</option><For each={properties()}>{value => <option value={value}>{value}</option>}</For>
            <Show when={property() && !properties().includes(property())}><option value={property()}>{property()} · {t("当前无记录", "no current records")}</option></Show>
          </select></label></Show>
        </div>
      </Show>
      <div class="extraction-controls"><p role="status">{t(`匹配 ${filtered().length} / ${current().rows.length} 行`, `${filtered().length} of ${current().rows.length} rows match`)}</p>
        <Show when={Boolean(query() || property() || status() !== "all")}><ActionButton size="sm" variant="quiet" onClick={reset}>{t("清除对照筛选", "Clear table filters")}</ActionButton></Show>
        <ActionButton size="sm" disabled={!filtered().length} onClick={() => void download("csv")}>{t("导出匹配行 CSV", "Export matching rows as CSV")}</ActionButton>
        <Show when={isLoopbackWorkbenchLocation(window.location)}><ActionButton size="sm" disabled={!filtered().length} onClick={() => void download("orca")}>{t("导出 Orca 核验任务", "Export Orca verification tasks")}</ActionButton></Show>
      </div>
      <Show when={current().rows.length} fallback={<p role="status">{t("当前没有可展示的纳入文献或已核对证据。可在关系图中核对文献筛选。", "No included papers or verified evidence are available to display. Check paper screening in the map.")}</p>}>
        <Show when={filtered().length} fallback={<p>{t("当前筛选未匹配记录。", "No records match these filters.")}</p>}>
          <table class="extraction-table" aria-label={t("文献与测量记录", "Papers and measurements")}>
            <thead><tr><th scope="col">{t("文献", "Paper")}</th><th scope="col">{t("材料与性质", "Material and property")}</th><th scope="col">{t("证据与条件", "Evidence and conditions")}</th><th scope="col">{t("来源定位", "Source location")}</th></tr></thead>
            <tbody><For each={visibleRows()}>{row => <tr>
              <th scope="row"><span class="extraction-status" classList={{ verified: row.status === "reviewed" }}>{t(...labels[row.status])}</span><span class="extraction-title">{row.title || row.document_id}</span>
                <Show when={row.doi}>{doi => <span class="extraction-reference">DOI {doi()}</span>}</Show></th>
              <Show when={row.status === "reviewed"} fallback={<td colspan="3" class="extraction-gap">{row.status === "awaiting_extraction"
                ? t("已纳入，等待提取原文中的测量和条件。", "Included. Measurements and conditions await extraction.")
                : row.status === "awaiting_review" ? t("已有提取记录，等待人工审核。", "Extraction records await human review.")
                : t("已有审核记录，仍需核对原文版本和来源定位。", "Review records exist. The original version and source location still need checking.")}</td>}>
                <td data-heading={t("材料与性质", "Material and property")}><strong>{row.material ?? missing()}</strong><span>{row.property_name ?? missing()}</span>
                  <Show when={row.stance}>{value => <small class="extraction-conditions">{t("证据立场", "Stance")} · {stance(value())}</small>}</Show>
                </td>
                <td data-heading={t("证据与条件", "Evidence and conditions")}><span>{row.claim ?? missing()}</span>
                  <Show when={row.reported_facts.length}><div class="extraction-facts"><small>{t("同一来源片段记录值", "Values recorded at this source segment")}</small><ul><For each={row.reported_facts}>{fact => <li>{fact.name} · <strong>{fact.value ?? missing()} {fact.unit ?? ""}</strong><Show when={Object.keys(fact.qualifiers).length}><span>{entries(fact.qualifiers)}</span></Show></li>}</For></ul></div></Show>
                  <span class="extraction-conditions">{t("条件", "Conditions")} · {entries(row.conditions) || missing()}</span>
                </td>
                <td data-heading={t("来源定位", "Source location")}><strong>{row.locator}</strong><span>{row.document_version ?? t("版本未记录", "Version unrecorded")}</span>
                  <Show when={row.source}>{source => <span class="extraction-reference">{source()}</span>}</Show>
                  <Show when={row.reader_available && row.evidence_id} fallback={<small>{t("本机阅读链接暂不可用", "Local reader link unavailable")}</small>}>{id =>
                    <a href={localRunLink(window.location.origin, props.runId, row.document_id, id())} target="_blank" rel="noopener" aria-label={t(`在新标签页核对 ${row.title} 的 ${row.locator}`, `Verify ${row.locator} in ${row.title} in a new tab`)}>{t("核对原文 ↗", "Verify source ↗")}</a>
                  }</Show>
                </td>
              </Show>
            </tr>}</For></tbody>
          </table>
          <Show when={lastPage() > 1}><div class="extraction-controls">
            <ActionButton size="sm" disabled={currentPage() === 1} onClick={() => setPage(currentPage() - 1)}>{t("上一页", "Previous")}</ActionButton>
            <span role="status">{t(`第 ${currentPage()} / ${lastPage()} 页`, `Page ${currentPage()} of ${lastPage()}`)}</span>
            <ActionButton size="sm" disabled={currentPage() === lastPage()} onClick={() => setPage(currentPage() + 1)}>{t("下一页", "Next")}</ActionButton>
          </div></Show>
        </Show>
      </Show>
    </>}</Show>
  </section>;
}
