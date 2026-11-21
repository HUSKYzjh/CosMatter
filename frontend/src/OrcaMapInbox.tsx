import { For, Show, createMemo, createSignal, onCleanup } from "solid-js";
import { documentIdForReviewablePaper } from "./evidenceLinking";
import { graphDisplayLabel } from "./graphSearch";
import type { LiteratureGraphNode } from "./model";
import { readOrcaInbox, type OrcaPaperReceipt } from "./orcaInbox";
import "./orca-map-inbox.css";

export function OrcaMapInbox(props: { runId: string; locale: "zh" | "en"; nodes: LiteratureGraphNode[]; select: (paper: LiteratureGraphNode) => void }) {
  const t = (zh: string, en: string) => props.locale === "zh" ? zh : en;
  const papers = createMemo(() => {
    const result = new Map<string, LiteratureGraphNode>();
    for (const node of props.nodes) {
      const id = documentIdForReviewablePaper(node);
      if (id) result.set(id, node);
    }
    return result;
  });
  const [receipts, setReceipts] = createSignal<OrcaPaperReceipt[]>([]);
  const [status, setStatus] = createSignal<"initial" | "loading" | "ready" | "invalid" | "large">("initial");
  const matched = createMemo(() => receipts().filter(row => papers().has(row.document)));
  let revision = 0;
  onCleanup(() => { revision++; });
  async function read(file: File) {
    const current = ++revision;
    setReceipts([]);
    if (file.size > 8 * 1024 * 1024) { setStatus("large"); return; }
    setStatus("loading");
    try {
      const text = await file.text();
      if (current !== revision) return;
      setReceipts(readOrcaInbox(JSON.parse(text.replace(/^\uFEFF/, "")), window.location.origin, props.runId, new Set(papers().keys())));
      setStatus("ready");
    } catch {
      if (current === revision) setStatus("invalid");
    }
  }
  return <details class="orca-map-inbox">
    <summary><span>{t("Orca 派工回执", "Orca dispatch receipts")}</span><Show when={status() === "ready"}><small>{matched().length}</small></Show></summary>
    <div class="orca-inbox-body">
      <p>{t("打开协调者导出的收件箱，按论文查看工作终端报告的派工结果。文件只在此页面读取，论文审核状态由证据记录决定。", "Open the coordinator’s inbox export to trace worker reports back to their papers. The file stays on this page. Evidence records determine paper review status.")}</p>
      <label>{t("选择 Orca 收件箱 JSON", "Choose an Orca inbox JSON file")}
        <input type="file" accept=".json,application/json" onChange={event => {
          const file = event.currentTarget.files?.[0];
          if (file) void read(file);
        }} />
      </label>
      <details><summary>{t("如何从 Orca 导出", "How to export from Orca")}</summary>
        <p>{t("在 Orca 所在的 PowerShell 中将 $orcaRun 设为目标 Orca 运行 ID，再执行以下命令。", "In the PowerShell session connected to Orca, set $orcaRun to the Orca run ID and run this command.")}</p>
        <code>orca orchestration inbox --terminal "run:$orcaRun" --limit 100 --full --json | Out-File -Encoding utf8 orca-inbox.json</code>
      </details>
      <div role="status"><Show when={status() === "ready"}>{matched().length
        ? t(`为当前星图匹配到 ${matched().length} 条回执。`, `Matched ${matched().length} receipts to this map.`)
        : t("文件中没有与当前工作台地址、运行和论文相符的派工回执。", "No receipts in this file match the workbench address, run and papers on this map.")}</Show>
        <Show when={status() === "invalid"}>{t("无法读取 Orca 收件箱。请使用上述命令导出的 UTF-8 JSON 文件。", "Unable to read this inbox. Choose the UTF-8 JSON file produced by the command above.")}</Show>
        <Show when={status() === "large"}>{t("文件超过 8 MiB。请减小导出的消息条数后重试。", "The file exceeds 8 MiB. Export fewer messages and try again.")}</Show>
        <Show when={status() === "loading"}>{t("正在读取文件…", "Reading file…")}</Show>
      </div>
      <Show when={matched().length}><ul><For each={matched()}>{row => <li>
        <button type="button" onClick={() => { const paper = papers().get(row.document); if (paper) props.select(paper); }}>{graphDisplayLabel(papers().get(row.document)!)}</button>
        <span>{row.outcome === "succeeded" ? t("执行成功", "Succeeded") : t("执行失败", "Failed")}</span>
        <details><summary>{t("查看派工标识", "Inspect dispatch IDs")}</summary><dl>
          <For each={[[t("工作终端", "Worker terminal"), row.worker], [t("派工", "Dispatch"), row.dispatch], [t("任务", "Task"), row.task], [t("Orca 运行", "Orca run"), row.run], [t("消息", "Message"), row.message]]}>{([label, value]) =>
            <><dt>{label}</dt><dd><code>{value}</code></dd></>}</For>
        </dl></details>
      </li>}</For></ul></Show>
    </div>
  </details>;
}
