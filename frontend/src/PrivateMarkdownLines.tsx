import { For, Show, createMemo, createSignal, onCleanup } from "solid-js";
import { createLatestRequestGate } from "./latestRequestGate";
import { getPrivateMarkdownLines, LocalApiRequestError, PRIVATE_MARKDOWN_WINDOW_SIZE, type PrivateMarkdownLineSource, type PrivateMarkdownWindow } from "./localApi";
import { ActionButton } from "./uiPrimitives";
import { uiLanguage } from "./zh";

const tr = (zh: string, en: string) => uiLanguage() === "zh" ? zh : en;

export function PrivateMarkdownLines(props: {
  source: PrivateMarkdownLineSource;
  onDraft?: (locator: string, quote: string) => void;
}) {
  const [open, setOpen] = createSignal(false);
  const [page, setPage] = createSignal<PrivateMarkdownWindow | null>(null);
  const [loading, setLoading] = createSignal(false);
  const [error, setError] = createSignal<string | null>(null);
  const [jump, setJump] = createSignal("");
  const [first, setFirst] = createSignal<number | null>(null);
  const [last, setLast] = createSignal<number | null>(null);
  const [staged, setStaged] = createSignal(false);
  const request = createLatestRequestGate();
  let sourceList: HTMLOListElement | undefined;
  let requestedStart = 1;
  onCleanup(request.invalidate);

  const range = createMemo(() => {
    const anchor = first();
    if (anchor === null) return null;
    const end = last() ?? anchor;
    return { start: Math.min(anchor, end), end: Math.max(anchor, end) };
  });
  const chosen = createMemo(() => {
    const selection = range();
    if (!selection) return null;
    const lines = page()?.lines.filter((line) => line.number >= selection.start && line.number <= selection.end) ?? [];
    const quote = lines.map((line) => line.text).join("\n").trim();
    return {
      locator: `markdown_line:${selection.start}-${selection.end}`,
      quote,
      canDraft: lines.length === selection.end - selection.start + 1 && !lines.some((line) => line.truncated) && quote.length > 0 && quote.length <= 500,
    };
  });
  const jumpTarget = () => /^[1-9][0-9]{0,8}$/.test(jump()) && Number(jump()) <= (page()?.total_lines ?? 0) ? Number(jump()) : null;
  const lineSelected = (number: number) => {
    const selection = range();
    return Boolean(selection && number >= selection.start && number <= selection.end);
  };

  function clearRange() {
    setFirst(null);
    setLast(null);
    setStaged(false);
  }

  async function load(start: number) {
    const isLatest = request.begin();
    requestedStart = start;
    setLoading(true);
    setError(null);
    clearRange();
    try {
      const result = await getPrivateMarkdownLines(props.source, start);
      if (isLatest()) {
        setPage(result);
        setJump(String(result.start));
        if (sourceList) sourceList.scrollTop = 0;
      }
    } catch (failure) {
      if (!isLatest()) return;
      const forbidden = failure instanceof LocalApiRequestError && failure.httpStatus === 403;
      setPage(null);
      setError(forbidden
        ? tr("当前筛选记录未允许核对这篇论文。", "The current screening record does not permit review of this paper.")
        : tr("无法读取原文行，请重试。", "Could not open source lines. Try again."));
    } finally {
      if (isLatest()) setLoading(false);
    }
  }

  function toggle() {
    if (!open()) { setOpen(true); void load(1); return; }
    request.invalidate();
    setOpen(false);
    setLoading(false);
    setPage(null);
    setError(null);
    clearRange();
  }

  function select(line: number) {
    setStaged(false);
    if (first() === null || last() !== null) { setFirst(line); setLast(null); }
    else setLast(line);
  }

  function draft() {
    const selection = chosen();
    if (!selection?.canDraft || !props.onDraft || loading() || staged()) return;
    props.onDraft(selection.locator, selection.quote);
    setStaged(true);
  }

  return <section class="private-markdown-lines" aria-label={tr("原文行号", "Source lines")}>
    <ActionButton size="sm" aria-expanded={open()} onClick={toggle}>{open() ? tr("收起原文", "Collapse source") : tr("查看带行号的原文", "View source with line numbers")}</ActionButton>
    <Show when={open()}>
      <Show when={loading()}><p role="status">{tr("正在读取原文行…", "Reading source lines…")}</p></Show>
      <Show when={error()}>{(message) => <div class="source-line-tools"><p role="status">{message()}</p><ActionButton size="sm" onClick={() => void load(requestedStart)}>{tr("重新读取", "Retry")}</ActionButton></div>}</Show>
      <Show when={page()}>{(current) => <>
        <div class="source-line-tools">
          <p aria-live="polite">{tr(`第 ${current().start}–${current().start + current().lines.length - 1} 行，共 ${current().total_lines} 行`, `Lines ${current().start}–${current().start + current().lines.length - 1} of ${current().total_lines}`)}</p>
          <div class="source-line-tools">
            <ActionButton size="sm" disabled={loading() || current().start === 1} onClick={() => void load(Math.max(1, current().start - PRIVATE_MARKDOWN_WINDOW_SIZE))}>{tr("上一段", "Previous lines")}</ActionButton>
            <ActionButton size="sm" disabled={loading() || current().start + current().lines.length > current().total_lines} onClick={() => void load(current().start + current().lines.length)}>{tr("下一段", "Next lines")}</ActionButton>
          </div>
          <form class="source-line-tools" onSubmit={(event) => { event.preventDefault(); const target = jumpTarget(); if (target !== null && !loading()) void load(target); }}>
            <label>{tr("行号", "Line")}<input value={jump()} inputmode="numeric" maxLength={9} onInput={(event) => setJump(event.currentTarget.value)} /></label>
            <ActionButton size="sm" type="submit" disabled={loading() || jumpTarget() === null}>{tr("跳转", "Go to line")}</ActionButton>
          </form>
        </div>
        <Show when={props.onDraft}><p>{tr("点击行号选择单行，再点另一行可选连续范围。", "Choose a line number, then a second number to select a range.")}</p></Show>
        <ol ref={sourceList} class="source-line-list" aria-label={tr("Markdown 原文", "Markdown text")}>
          <For each={current().lines}>{(line) => <li classList={{ selected: lineSelected(line.number) }}>
            <Show when={props.onDraft} fallback={<span class="source-line-number">{line.number}</span>}>
              <ActionButton size="sm" variant="quiet" class="source-line-number" disabled={loading()}
                aria-pressed={lineSelected(line.number)}
                aria-label={tr(`第 ${line.number} 行`, `Line ${line.number}`)} onClick={() => select(line.number)}>{line.number}</ActionButton>
            </Show>
            <div class="source-line-text">{line.text}<Show when={line.truncated}><small>{tr("（已截断，完整行可下载查看）", " (truncated; download to see the complete line)")}</small></Show></div>
          </li>}</For>
        </ol>
        <Show when={props.onDraft && chosen()}>{(selection) => <div class="source-line-tools">
          <code>{selection().locator}</code>
          <ActionButton size="sm" disabled={!selection().canDraft || loading() || staged()} onClick={draft}>{tr("填入来源草稿", "Use in source draft")}</ActionButton>
          <ActionButton size="sm" variant="quiet" onClick={clearRange}>{tr("清除选择", "Clear selection")}</ActionButton>
          <Show when={!selection().canDraft}><p role="status">{tr("请选择 500 字符以内的完整短引文，或手动填写草稿。", "Select a complete excerpt of up to 500 characters, or enter it manually.")}</p></Show>
          <Show when={staged()}><p role="status">{tr("已填入草稿。核对后请勾选人工确认。", "Added to the draft. Review it before confirming.")}</p></Show>
        </div>}</Show>
      </>}</Show>
    </Show>
  </section>;
}
