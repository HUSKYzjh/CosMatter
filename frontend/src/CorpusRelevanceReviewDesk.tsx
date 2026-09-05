import { For, Show, createMemo, createSignal, onMount } from "solid-js";

import {
  bindManifestToHumanGold,
  corpusRelevanceReadiness,
  exportHumanGoldDraft,
  parseCorpusManifest,
  parseHumanGoldDraft,
  type CorpusManifest,
  type HumanGoldDraft,
  type RetrievalRelevance,
} from "./corpusRelevanceReview";

const SESSION_DRAFT_KEY = "cosmatter.corpus-relevance-review-draft/v1";
const PAGE_SIZE = 25;
const RELEVANCE_VALUES: RetrievalRelevance[] = ["unreviewed", "relevant", "partially_relevant", "not_relevant"];

const RELEVANCE_LABELS: Record<RetrievalRelevance, { zh: string; en: string }> = {
  unreviewed: { zh: "待审核", en: "Unreviewed" },
  relevant: { zh: "相关", en: "Relevant" },
  partially_relevant: { zh: "部分相关", en: "Partially relevant" },
  not_relevant: { zh: "不相关", en: "Not relevant" },
};

interface StoredCorpusReview {
  draft: HumanGoldDraft;
  file_name: string | null;
  manifest: CorpusManifest | null;
  manifest_file_name: string | null;
}

export function CorpusRelevanceReviewDesk(props: { locale: "zh" | "en" }) {
  const tr = (zh: string, en: string) => props.locale === "zh" ? zh : en;
  const [draft, setDraft] = createSignal<HumanGoldDraft | null>(null);
  const [fileName, setFileName] = createSignal<string | null>(null);
  const [manifest, setManifest] = createSignal<CorpusManifest | null>(null);
  const [manifestFileName, setManifestFileName] = createSignal<string | null>(null);
  const [error, setError] = createSignal<string | null>(null);
  const [attested, setAttested] = createSignal(false);
  const [clearArmed, setClearArmed] = createSignal(false);
  const [sessionStatus, setSessionStatus] = createSignal<"saved" | "restored" | "unavailable" | null>(null);
  const [filter, setFilter] = createSignal<"all" | RetrievalRelevance>("all");
  const [search, setSearch] = createSignal("");
  const [page, setPage] = createSignal(1);

  const readiness = createMemo(() => draft() ? corpusRelevanceReadiness(draft()!) : null);
  const bibliography = createMemo(() => new Map((manifest()?.documents ?? []).map((item) => [item.document_id, item])));
  const filteredDocuments = createMemo(() => {
    const current = draft();
    if (!current) return [];
    const needle = search().trim().toLocaleLowerCase();
    return current.documents.filter((item) => {
      if (filter() !== "all" && item.retrieval_relevance !== filter()) return false;
      if (!needle) return true;
      const metadata = bibliography().get(item.document_id);
      return [item.document_id, metadata?.title ?? "", metadata?.doi ?? ""].some((value) => value.toLocaleLowerCase().includes(needle));
    });
  });
  const pageCount = createMemo(() => Math.max(1, Math.ceil(filteredDocuments().length / PAGE_SIZE)));
  const pageDocuments = createMemo(() => {
    const currentPage = Math.min(page(), pageCount());
    return filteredDocuments().slice((currentPage - 1) * PAGE_SIZE, currentPage * PAGE_SIZE);
  });

  function persistSession(nextDraft: HumanGoldDraft, nextFileName: string | null, nextManifest: CorpusManifest | null, nextManifestFileName: string | null) {
    try {
      const envelope: StoredCorpusReview = { draft: exportHumanGoldDraft(nextDraft, false), file_name: nextFileName, manifest: nextManifest, manifest_file_name: nextManifestFileName };
      window.sessionStorage.setItem(SESSION_DRAFT_KEY, JSON.stringify(envelope));
      setSessionStatus("saved");
    } catch {
      setSessionStatus("unavailable");
    }
  }

  onMount(() => {
    let stored: string | null;
    try {
      stored = window.sessionStorage.getItem(SESSION_DRAFT_KEY);
    } catch {
      setSessionStatus("unavailable");
      return;
    }
    if (!stored) return;
    try {
      const envelope = JSON.parse(stored) as Partial<StoredCorpusReview>;
      const restoredDraft = exportHumanGoldDraft(parseHumanGoldDraft(envelope.draft), false);
      let restoredManifest: CorpusManifest | null = null;
      if (envelope.manifest) {
        try { restoredManifest = bindManifestToHumanGold(restoredDraft, parseCorpusManifest(envelope.manifest)); } catch { restoredManifest = null; }
      }
      setDraft(restoredDraft);
      setFileName(typeof envelope.file_name === "string" ? envelope.file_name.slice(0, 160) : null);
      setManifest(restoredManifest);
      setManifestFileName(restoredManifest && typeof envelope.manifest_file_name === "string" ? envelope.manifest_file_name.slice(0, 160) : null);
      setSessionStatus("restored");
    } catch {
      try { window.sessionStorage.removeItem(SESSION_DRAFT_KEY); } catch { setSessionStatus("unavailable"); }
    }
  });

  async function importGold(file: File | undefined) {
    if (!file) return;
    setError(null);
    setClearArmed(false);
    if (file.size > 2 * 1024 * 1024) {
      setError(tr("人工金标准文件不得超过 2 MiB。", "Human-gold files must not exceed 2 MiB."));
      return;
    }
    try {
      const parsed = exportHumanGoldDraft(parseHumanGoldDraft(JSON.parse(await file.text())), false);
      const boundedName = file.name.slice(0, 160);
      setDraft(parsed);
      setFileName(boundedName);
      setManifest(null);
      setManifestFileName(null);
      setAttested(false);
      setFilter("all");
      setSearch("");
      setPage(1);
      persistSession(parsed, boundedName, null, null);
    } catch {
      setError(tr("所选文件不是受支持的人工金标准 JSON；当前草稿保持不变。", "The selected file is not a supported human-gold JSON; the current draft was preserved."));
    }
  }

  async function importManifest(file: File | undefined) {
    if (!file) return;
    const current = draft();
    if (!current) {
      setError(tr("请先选择人工金标准模板。", "Select the human-gold template first."));
      return;
    }
    setError(null);
    setClearArmed(false);
    if (file.size > 512 * 1024) {
      setError(tr("语料清单不得超过 512 KiB。", "Corpus manifests must not exceed 512 KiB."));
      return;
    }
    try {
      const parsed = bindManifestToHumanGold(current, parseCorpusManifest(JSON.parse(await file.text())));
      const boundedName = file.name.slice(0, 160);
      setManifest(parsed);
      setManifestFileName(boundedName);
      persistSession(current, fileName(), parsed, boundedName);
    } catch {
      setError(tr("语料清单与当前金标准的任务、语料库或文献 ID 不完全一致；没有替换现有书目信息。", "The manifest does not exactly match the current gold mission, corpus, and document IDs; existing bibliography was preserved."));
    }
  }

  function updateRelevance(documentId: string, relevance: RetrievalRelevance) {
    const current = draft();
    if (!current) return;
    const next = {
      ...current,
      documents: current.documents.map((item) => item.document_id === documentId ? { ...item, retrieval_relevance: relevance } : item),
    };
    setDraft(next);
    setAttested(false);
    setClearArmed(false);
    persistSession(next, fileName(), manifest(), manifestFileName());
  }

  function clearSession() {
    if (!clearArmed()) {
      setClearArmed(true);
      return;
    }
    let unavailable = false;
    try { window.sessionStorage.removeItem(SESSION_DRAFT_KEY); } catch { unavailable = true; }
    setDraft(null);
    setFileName(null);
    setManifest(null);
    setManifestFileName(null);
    setError(null);
    setAttested(false);
    setClearArmed(false);
    setFilter("all");
    setSearch("");
    setPage(1);
    setSessionStatus(unavailable ? "unavailable" : null);
  }

  function exportReview() {
    const current = draft();
    if (!current) return;
    const payload = exportHumanGoldDraft(current, attested());
    const blob = new Blob([JSON.stringify(payload, null, 2) + "\n"], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `${payload.corpus_id.replace(/[^A-Za-z0-9._-]+/g, "-") || "corpus"}.human-gold.json`;
    anchor.click();
    window.setTimeout(() => URL.revokeObjectURL(url), 0);
  }

  function setActiveFilter(value: "all" | RetrievalRelevance) {
    setFilter(value);
    setPage(1);
  }

  return <details class="corpus-review-desk" aria-label={tr("冻结语料相关性人工审核台", "Human frozen-corpus relevance review desk")}>
    <summary>{tr("人工语料相关性审核台", "Human corpus relevance review desk")}</summary>
    <p>{tr("显式选择 CLI 生成的人工金标准模板，逐篇标注检索相关性。草稿只保留在当前浏览器会话；本页不联网、不读取全文，也不写入运行目录。", "Select the CLI-generated human-gold template explicitly and label retrieval relevance document by document. Drafts remain in this browser session; this page does not use the network, read full text, or write into a run directory.")}</p>
    <section class="corpus-review-imports">
      <label><span>{tr("1. 选择人工金标准 JSON", "1. Select human-gold JSON")}</span><input type="file" accept="application/json,.json" onChange={(event) => { const file = event.currentTarget.files?.[0]; event.currentTarget.value = ""; void importGold(file); }} /></label>
      <label classList={{ disabled: !draft() }}><span>{tr("2. 可选：绑定语料清单以显示标题和 DOI", "2. Optional: bind corpus manifest for titles and DOI")}</span><input type="file" disabled={!draft()} accept="application/json,.json" onChange={(event) => { const file = event.currentTarget.files?.[0]; event.currentTarget.value = ""; void importManifest(file); }} /></label>
    </section>
    <Show when={sessionStatus()}>{(status) => <p class="corpus-review-session-note" role="status">{status() === "restored" ? tr("已恢复本浏览器会话中的相关性草稿；独立审核声明需要重新确认。", "The relevance draft was restored from this browser session; independent-review attestation must be confirmed again.") : status() === "saved" ? tr("相关性草稿已暂存在本浏览器会话中。", "The relevance draft is temporarily saved in this browser session.") : tr("浏览器会话暂存不可用；请及时导出本地草稿。", "Browser-session storage is unavailable; export a local draft promptly.")}</p>}</Show>
    <Show when={error()}>{(message) => <p class="corpus-review-error" role="alert">{message()}</p>}</Show>
    <Show when={draft()}>{(current) => <>
      <header class="corpus-review-status" aria-live="polite">
        <div><small>{tr("本地相关性草稿", "LOCAL RELEVANCE DRAFT")}</small><strong>{current().corpus_id}</strong><span>{fileName()} · {current().mission_id}{manifestFileName() ? ` · ${manifestFileName()}` : ""}</span></div>
        <dl>
          <div><dt>{tr("已审核", "Reviewed")}</dt><dd>{readiness()!.reviewedCount}/{readiness()!.documentCount}</dd></div>
          <div><dt>{tr("相关", "Relevant")}</dt><dd>{readiness()!.counts.relevant}</dd></div>
          <div><dt>{tr("部分相关", "Partial")}</dt><dd>{readiness()!.counts.partially_relevant}</dd></div>
          <div><dt>{tr("不相关", "Not relevant")}</dt><dd>{readiness()!.counts.not_relevant}</dd></div>
        </dl>
      </header>
      <section class="corpus-review-toolbar" aria-label={tr("语料筛选", "Corpus filters")}>
        <label>{tr("搜索文献 ID、标题或 DOI", "Search document ID, title, or DOI")}<input type="search" value={search()} onInput={(event) => { setSearch(event.currentTarget.value); setPage(1); }} /></label>
        <div role="group" aria-label={tr("相关性筛选", "Relevance filter")}>
          <button type="button" aria-pressed={filter() === "all"} onClick={() => setActiveFilter("all")}>{tr("全部", "All")} · {current().documents.length}</button>
          <For each={RELEVANCE_VALUES}>{(value) => <button type="button" aria-pressed={filter() === value} onClick={() => setActiveFilter(value)}>{tr(RELEVANCE_LABELS[value].zh, RELEVANCE_LABELS[value].en)} · {readiness()!.counts[value]}</button>}</For>
        </div>
      </section>
      <Show when={pageDocuments().length} fallback={<p class="corpus-review-empty">{tr("当前筛选没有匹配文献。", "No documents match the current filter.")}</p>}>
        <section class="corpus-review-list">
          <For each={pageDocuments()}>{(document) => {
            const metadata = () => bibliography().get(document.document_id);
            const index = () => current().documents.findIndex((item) => item.document_id === document.document_id) + 1;
            const annotationCount = () => document.evidence_annotations.length + document.material_fact_annotations.length + document.comparison_annotations.length + document.gap_annotations.length;
            return <article classList={{ "corpus-review-item": true, reviewed: document.retrieval_relevance !== "unreviewed" }}>
              <header><small>{String(index()).padStart(3, "0")} / {current().documents.length}</small><span>{document.document_id}</span></header>
              <h3>{metadata()?.title ?? tr("未绑定书目标题", "Bibliographic title not bound")}</h3>
              <p>{metadata()?.doi ? `DOI ${metadata()!.doi}` : tr("无 DOI 或尚未绑定语料清单", "No DOI or corpus manifest not yet bound")}</p>
              <label>{tr("检索相关性", "Retrieval relevance")}<select value={document.retrieval_relevance} onChange={(event) => updateRelevance(document.document_id, event.currentTarget.value as RetrievalRelevance)}><For each={RELEVANCE_VALUES}>{(value) => <option value={value}>{tr(RELEVANCE_LABELS[value].zh, RELEVANCE_LABELS[value].en)}</option>}</For></select></label>
              <small>{tr(`其余人工标注保持原样（${annotationCount()} 项）`, `Other human annotations are preserved unchanged (${annotationCount()} item(s))`)}</small>
            </article>;
          }}</For>
        </section>
      </Show>
      <nav class="corpus-review-pagination" aria-label={tr("语料页码", "Corpus pages")}>
        <button type="button" disabled={page() <= 1} onClick={() => setPage((value) => Math.max(1, value - 1))}>{tr("上一页", "Previous")}</button>
        <span>{tr(`第 ${Math.min(page(), pageCount())} / ${pageCount()} 页`, `Page ${Math.min(page(), pageCount())} / ${pageCount()}`)} · {filteredDocuments().length}</span>
        <button type="button" disabled={page() >= pageCount()} onClick={() => setPage((value) => Math.min(pageCount(), value + 1))}>{tr("下一页", "Next")}</button>
      </nav>
      <section class="corpus-review-release">
        <div><small>{tr("评测前人工门禁", "HUMAN GATE BEFORE EVALUATION")}</small><strong>{readiness()!.readyForAttestation ? tr("标签完整；仍需独立审核声明", "Labels complete; independent-review attestation remains") : tr("相关性审核尚未完整", "Relevance review remains incomplete")}</strong><p>{readiness()!.counts.unreviewed ? tr(`仍有 ${readiness()!.counts.unreviewed} 篇待审核。`, `${readiness()!.counts.unreviewed} document(s) remain unreviewed.`) : readiness()!.counts.relevant < 1 ? tr("严格评测至少需要一篇标为“相关”。", "Strict evaluation requires at least one document labelled relevant.") : tr("完成声明后导出文件才会带有可评测信任状态。", "Only an attested export receives the evaluation-eligible trust status.")}</p></div>
        <label class="consent"><input type="checkbox" disabled={!readiness()!.readyForAttestation} checked={attested()} onChange={(event) => setAttested(event.currentTarget.checked)} />{tr("我确认这些相关性标签由独立研究者依据冻结语料逐篇审核；未读取到的全文不得推定为相关。", "I confirm that an independent researcher reviewed these relevance labels against the frozen corpus document by document; unread full text was not assumed relevant.")}</label>
        <div class="corpus-review-actions"><button type="button" classList={{ "clear-armed": clearArmed() }} onClick={clearSession}>{clearArmed() ? tr("再次点击确认清除", "Click again to confirm clear") : tr("清除本会话草稿", "Clear session draft")}</button><button type="button" class="primary-action" onClick={exportReview}>{attested() && readiness()!.readyForAttestation ? tr("导出可评测金标准", "Export evaluation-eligible gold") : tr("导出本地相关性草稿", "Export local relevance draft")}</button></div>
      </section>
    </>}</Show>
  </details>;
}
