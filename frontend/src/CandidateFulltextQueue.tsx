import { For, Show, createMemo, createSignal } from "solid-js";
import { recordedIncludedCandidates } from "./candidateScreeningDraft";
import { reviewablePaperForDocumentId } from "./evidenceLinking";
import type { CandidateScreening, CandidateScreeningCandidate, PdfTaskStatus, SavedSourceParseHealth, SavedSourceParseTask } from "./localApi";
import type { LiteratureGraphNode } from "./model";
import { candidatePdfAction } from "./paperPdfIntake";
import { SourceMarkdownLinkButton } from "./SourceMarkdownLinkButton";
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
  linkMarkdown?: (documentId: string, file: File) => Promise<void>;
}) {
  const t = (zh: string, en: string) => props.locale === "zh" ? zh : en;
  const [expanded, setExpanded] = createSignal(false);
  const rows = createMemo(() => recordedIncludedCandidates(props.screening));

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
        <For each={expanded() ? rows() : rows().slice(0, 6)}>{(candidate) => {
          const id = candidate.document_id;
          const paper = createMemo(() => reviewablePaperForDocumentId(props.nodes, id));
          const saved = createMemo(() => props.sourceTasks.find((task) => task.document_id === id) ?? null);
          const action = createMemo(() => candidatePdfAction(props.pdfTasks.find((task) => task.candidate_document_id === id) ?? null, saved()));
          const canLink = () => action() === "recorded_done" && saved()?.can_link_markdown && props.linkMarkdown;
          const label = () => ({
            choose_pdf: t("待选择 PDF", "PDF needed"),
            retry_pdf: t("上次解析失败", "Previous parse failed"),
            open_reader: t("本机 Markdown 就绪", "Local Markdown ready"),
            recorded_reader: saved()?.source_map_segment_count ? t("已登记来源定位", "Source locations recorded") : t("本机 Markdown 就绪", "Local Markdown ready"),
            open_bridge: t("本机 PDF 已关联", "Local PDF linked"),
            recorded_active: saved()?.state === "running" ? t("来源解析中", "Source parsing") : t("来源解析排队中", "Source parse pending"),
            recorded_done: canLink() ? t("等待关联原文件", "Saved file needed") : t("来源解析完成", "Source parse complete"),
          })[action()];
          const availableAction = () => {
            const target = paper();
            const next = action();
            if (!target || next === "recorded_active" || next === "recorded_done") return null;
            const reader = { label: t("进入阅读页", "Open reader"), run: () => props.openReader(target) };
            return {
              choose_pdf: { label: t("选择授权 PDF", "Choose authorised PDF"), run: () => props.choosePdf(candidate) },
              retry_pdf: { label: t("重新选择授权 PDF", "Choose authorised PDF again"), run: () => props.choosePdf(candidate) },
              open_bridge: { label: t("查看 PDF 状态", "View PDF status"), run: () => props.openBridge(target) },
              open_reader: reader,
              recorded_reader: reader,
            }[next];
          };
          return <li>
            <div class="fulltext-queue-paper">
              <strong>{candidate.title}</strong>
              <span>{candidate.source}{candidate.publication_year ? ` · ${candidate.publication_year}` : ""}</span>
              <StatusBadge tone={["open_reader", "recorded_reader"].includes(action()) ? "ready" : action() === "retry_pdf" ? "attention" : "neutral"}>{label()}</StatusBadge>
              <Show when={action() === "recorded_done"}>
                <Show when={canLink()} fallback={<><p>{t("在终端运行", "Run")} <code>cosmatter mineru-fetch-markdown</code> {t("取回原文件，再刷新解析记录。", "in the terminal, then refresh the parse records.")}</p><code>{id}</code></>}>
                  <p>{t("选择之前取回的原文件，系统将在本机核对回执。", "Choose the original saved file to check it against the local receipt.")}</p>
                </Show>
              </Show>
              <Show when={action() === "recorded_active"}><p>{t("DSH 轮询后可刷新进度。", "Refresh after polling through DSH.")}</p></Show>
              <Show when={!paper()}><p>{t("文献星图尚无对应论文。", "The literature map has no matching paper yet.")}</p></Show>
            </div>
            <Show when={canLink()}>{(link) => <SourceMarkdownLinkButton locale={props.locale} paperTitle={candidate.title} onLink={(file) => link()(id, file)} />}</Show>
            <Show when={availableAction()}>{(next) =>
              <ActionButton size="sm" disabled={props.sourceHealth === "loading" && (action() === "choose_pdf" || action() === "retry_pdf")}
                aria-label={next().label + " · " + candidate.title}
                onClick={next().run}>{next().label}</ActionButton>
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
