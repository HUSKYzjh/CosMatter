import { For, Show, createMemo, createSignal } from "solid-js";
import { recordedIncludedCandidates } from "./candidateScreeningDraft";
import { reviewablePaperForDocumentId } from "./evidenceLinking";
import type { CandidateScreening, CandidateScreeningCandidate, PdfTaskStatus, SavedSourceParseHealth, SavedSourceParseTask } from "./localApi";
import type { LiteratureGraphNode } from "./model";
import { candidatePdfAction } from "./paperPdfIntake";
import { ActionButton, StatusBadge } from "./uiPrimitives";

export function CandidateFulltextQueue(props: {
  locale: "zh" | "en";
  screening: CandidateScreening | null;
  nodes: LiteratureGraphNode[];
  pdfTasks: readonly PdfTaskStatus[];
  sourceTasks: readonly SavedSourceParseTask[];
  sourceHealth: SavedSourceParseHealth;
  refresh: () => void;
  choosePdf: (candidate: CandidateScreeningCandidate) => void;
  openReader: (paper: LiteratureGraphNode) => void;
  openBridge: (paper: LiteratureGraphNode) => void;
}) {
  const t = (zh: string, en: string) => props.locale === "zh" ? zh : en;
  const [expanded, setExpanded] = createSignal(false);
  const rows = createMemo(() => recordedIncludedCandidates(props.screening).map((candidate) => {
    const id = candidate.document_id;
    const paper = reviewablePaperForDocumentId(props.nodes, id);
    const local = props.pdfTasks.find((task) => task.candidate_document_id === id) ?? null;
    const saved = props.sourceTasks.find((task) => task.document_id === id) ?? null;
    const action = candidatePdfAction(local, saved);
    return { candidate, paper, action, saved };
  }));

  return <Show when={rows().length > 0}>
    <section class="candidate-fulltext-queue" aria-labelledby="candidate-fulltext-title">
      <header>
        <div><h2 id="candidate-fulltext-title">{t("全文核对队列", "Full-text review queue")}</h2>
          <p>{t(`${rows().length} 篇已人工纳入`, `${rows().length} human-included candidate(s)`)}</p></div>
        <ActionButton size="sm" busy={props.sourceHealth === "loading"} busyLabel={t("正在读取…", "Reading…")} onClick={props.refresh}>
          {t("刷新本机解析记录", "Refresh local parse records")}
        </ActionButton>
      </header>
      <Show when={props.sourceHealth === "unavailable"}><p role="status">{t("暂时无法读取解析账本，请刷新后核对。", "The parse ledger is temporarily unavailable. Refresh it to check the saved states.")}</p></Show>
      <ul>
        <For each={expanded() ? rows() : rows().slice(0, 6)}>{(row) => {
          const labels = {
            choose_pdf: t("待选择 PDF", "PDF needed"),
            retry_pdf: t("上次解析失败", "Previous parse failed"),
            open_reader: t("本机 Markdown 就绪", "Local Markdown ready"),
            open_bridge: t("本机 PDF 已关联", "Local PDF linked"),
            recorded_active: row.saved?.state === "running" ? t("来源解析中", "Source parsing") : t("来源解析排队中", "Source parse pending"),
            recorded_done: t("来源解析完成", "Source parse complete"),
          };
          const actions = {
            choose_pdf: { label: t("选择授权 PDF", "Choose authorised PDF"), run: () => props.choosePdf(row.candidate) },
            retry_pdf: { label: t("重新选择授权 PDF", "Choose authorised PDF again"), run: () => props.choosePdf(row.candidate) },
            open_bridge: { label: t("查看 PDF 状态", "View PDF status"), run: () => { if (row.paper) props.openBridge(row.paper); } },
            open_reader: { label: t("进入阅读页", "Open reader"), run: () => { if (row.paper) props.openReader(row.paper); } },
          };
          const availableAction = row.action === "recorded_active" || row.action === "recorded_done" ? null : actions[row.action];
          return <li>
            <div class="fulltext-queue-paper">
              <strong>{row.candidate.title}</strong>
              <span>{row.candidate.source}{row.candidate.publication_year ? ` · ${row.candidate.publication_year}` : ""}</span>
              <StatusBadge tone={row.action === "open_reader" ? "ready" : row.action === "retry_pdf" ? "attention" : "neutral"}>{labels[row.action]}</StatusBadge>
              <Show when={row.action === "recorded_done"}><p>{t("阅读页尚无本机 Markdown。可在终端用", "The reader has no local Markdown yet. Use")} <code>cosmatter mineru-fetch-markdown</code> {t("取回解析结果。", "to retrieve the result.")}</p>
                <code>{row.candidate.document_id}</code>
              </Show>
              <Show when={row.action === "recorded_active"}><p>{t("这里显示已保存的进度。DSH 轮询后可刷新查看。", "This shows saved progress. Refresh after polling through DSH.")}</p></Show>
              <Show when={!row.paper}><p>{t("文献星图尚无对应论文。", "The literature map has no matching paper yet.")}</p></Show>
            </div>
            <Show when={row.paper && availableAction}>{(action) =>
              <ActionButton size="sm" disabled={props.sourceHealth === "loading" && (row.action === "choose_pdf" || row.action === "retry_pdf")}
                aria-label={action().label + " · " + row.candidate.title}
                onClick={action().run}>{action().label}</ActionButton>
            }
            </Show>
          </li>;
        }}</For>
      </ul>
      <Show when={rows().length > 6}>
        <ActionButton size="sm" aria-expanded={expanded()} onClick={() => setExpanded((value) => !value)}>
          {expanded() ? t("收起其余候选", "Show fewer candidates") : t(`查看全部 ${rows().length} 篇`, `Show all ${rows().length}`)}
        </ActionButton>
      </Show>
    </section>
  </Show>;
}
