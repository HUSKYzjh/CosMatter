import { batch, createEffect, createResource, createSignal, For, onCleanup, Show } from "solid-js";
import { continuationStageLabel } from "./continuationStage";
import type { UiLocale } from "./fleetRegistry";
import { isLocalRunId, localRunLink } from "./liveRunIdentity";
import { getReminderPage, type OperationalReminderAction, type ReminderPriority } from "./localApi";
import "./runReminderInbox.css";

const actionTitles: Record<OperationalReminderAction, [string, string]> = {
  inspect_runtime_invariants: ["核对运行异常", "Inspect runtime issues"],
  review_stage_boundary: ["检查阶段前置条件", "Check stage prerequisites"],
  complete_human_review: ["完成人工复核", "Complete the review"],
  verify_dispatch_before_recovery: ["核对中断的调用", "Inspect the interrupted dispatch"],
  verify_provider_outcome_before_recovery: ["核对服务商返回结果", "Check the provider outcome"],
  review_operational_todo: ["复核已到期的项目待办", "Review the overdue project item"],
};

export function RunReminderInbox(props: { locale: UiLocale }) {
  let resultsEl!: HTMLDivElement;
  const x = (zh: string, en: string) => props.locale === "zh" ? zh : en;
  const [open, setOpen] = createSignal(false);
  const [priority, setPriority] = createSignal<ReminderPriority>("all");
  const [input, setInput] = createSignal("");
  const [identifier, setIdentifier] = createSignal("");
  const [page, setPage] = createSignal(1);
  const [refresh, setRefresh] = createSignal(0);
  const [data] = createResource(() => open() && { page: page(), priority: priority(), identifier: identifier(), refresh: refresh() },
    async params => ({ ...await getReminderPage(params.page, params.priority, params.identifier), query: params }));
  const result = () => {
    if (data.state !== "ready" && data.state !== "refreshing") return;
    const last = data.latest;
    if (last?.query.page === page() && last.query.priority === priority() && last.query.identifier === identifier()) return last;
  };
  createEffect(() => {
    if (!open()) return;
    const timer = window.setInterval(() => {
      if (!document.hidden && !resultsEl.contains(document.activeElement) && !data.loading) setRefresh(n => n + 1);
    }, 30_000);
    onCleanup(() => window.clearInterval(timer));
  });
  return <details class="run-reminder-inbox" onToggle={e => setOpen(e.currentTarget.open)}>
    <summary>{x("跨任务待办", "Research inbox")}</summary>
    <form onSubmit={e => { e.preventDefault(); batch(() => { setPage(1); setIdentifier(input().trim()); }); }}>
      <label>{x("运行或项目条目 ID", "Run or project item ID")}
        <input type="search" value={input()} maxLength={255} onInput={e => setInput(e.currentTarget.value)} />
      </label>
      <label>{x("优先级", "Priority")}
        <select value={priority()} onChange={e => batch(() => { setPage(1); setPriority(e.currentTarget.value as ReminderPriority); })}>
          <option value="all">{x("全部", "All")}</option>
          <option value="attention">{x("需要处理", "Needs attention")}</option>
          <option value="review">{x("待复核", "Needs review")}</option>
        </select>
      </label>
      <button type="submit">{x("查找", "Find")}</button>
    </form>
    <div class="reminder-results" ref={resultsEl} tabIndex={-1} aria-busy={data.loading}>
      <Show when={data.loading}><p role="status">{x("正在读取待办…", "Loading reminders…")}</p></Show>
      <Show when={data.state === "errored"}><p role="status">{x("暂时无法读取待办。", "Reminders could not be loaded.")}</p></Show>
      <Show when={result()}>{snapshot => <>
        <p role="status">{snapshot().total_count
          ? x(`共 ${snapshot().total_count} 条 · 第 ${snapshot().page} 页`, `${snapshot().total_count} reminders · Page ${snapshot().page}`)
          : x("没有符合条件的待办。", "No matching reminders.")}</p>
        <ul><For each={snapshot().board.reminders}>{item => <li>
          <strong>{x(...actionTitles[item.action_label])}</strong>
          <Show when={item.stage}>{stage => <span>{continuationStageLabel(stage(), props.locale)}</span>}</Show>
          <Show when={item.scope === "run" && isLocalRunId(item.identifier)} fallback={<code>{item.identifier}</code>}>
            <a href={localRunLink(window.location.origin, item.identifier)} target="_blank" rel="noopener"
              aria-label={x(`在新标签页打开运行 ${item.identifier}`, `Open run ${item.identifier} in a new tab`)}>{item.identifier} ↗</a>
          </Show>
        </li>}</For></ul>
        <Show when={snapshot().total_count > snapshot().page_size}><div class="reminder-pagination">
          <button type="button" disabled={snapshot().page === 1} onClick={() => { resultsEl.focus(); setPage(snapshot().page - 1); }}>{x("上一页", "Previous")}</button>
          <button type="button" disabled={snapshot().page * snapshot().page_size >= snapshot().total_count}
            onClick={() => { resultsEl.focus(); setPage(snapshot().page + 1); }}>{x("下一页", "Next")}</button>
        </div></Show>
      </>}</Show>
      <button type="button" disabled={data.loading} onClick={() => setRefresh(n => n + 1)}>{x("刷新待办", "Refresh reminders")}</button>
    </div>
  </details>;
}
