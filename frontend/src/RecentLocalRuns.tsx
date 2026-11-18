import { For, Show, createMemo, createResource, createSignal } from "solid-js";
import { DshRecentRunsHandoff } from "./DshRunHandoff";
import { getRecentLocalRuns, type RecentLocalRun } from "./localApi";
import { ActionButton, StatusBadge } from "./uiPrimitives";
import type { UiLocale } from "./fleetRegistry";

const FIRST_PAGE_SIZE = 4;

export function RecentLocalRuns(props: {
  locale: UiLocale;
  listOnMount: boolean;
  activeRunId?: string | null;
  openingRunId?: string;
  disabled: boolean;
  onOpen: (runId: string, stopped: boolean) => void;
}) {
  const x = (zh: string, en: string) => props.locale === "zh" ? zh : en;
  const [requestNumber, setRequestNumber] = createSignal(props.listOnMount ? 1 : 0);
  const [expanded, setExpanded] = createSignal(false);
  const [result] = createResource(() => requestNumber() || false, getRecentLocalRuns);
  const rows = createMemo(() => result.state === "ready" || result.state === "refreshing" ? result.latest ?? [] : []);
  const shown = () => expanded() ? rows() : rows().slice(0, FIRST_PAGE_SIZE);
  const dateFormat = createMemo(() => new Intl.DateTimeFormat(props.locale === "zh" ? "zh-CN" : "en", { dateStyle: "medium", timeStyle: "short" }));
  const actionLabel = (run: RecentLocalRun) => run.stopped ? x("查看记录", "View record")
    : run.run_id === props.activeRunId ? x("返回", "Return") : x("打开", "Open");

  return <section class="recent-local-runs" aria-labelledby="recent-local-runs-title" aria-busy={result.loading || undefined}>
    <header>
      <h3 id="recent-local-runs-title">{x("最近的本机任务", "Recent local runs")}</h3>
      <ActionButton size="sm" busy={result.loading} busyLabel={x("正在读取…", "Loading…")} disabled={props.disabled}
        onClick={() => setRequestNumber((number) => number + 1)}>
        {requestNumber() ? x("刷新列表", "Refresh list") : x("查看最近任务", "Show recent runs")}
      </ActionButton>
    </header>
    <Show when={result.state === "errored"}>
      <p role="status">{x("无法读取最近任务。可以刷新列表，或按运行 ID 打开。", "Recent runs are unavailable. Refresh the list or open a run by ID.")}</p>
    </Show>
    <Show when={result.state === "ready" && rows().length === 0}>
      <p role="status">{x("本机暂无已保存的研究任务。", "There are no saved research runs on this machine.")}</p>
    </Show>
    <Show when={rows().length > 0}>
      <ul>
        <For each={shown()}>{(run) => <li>
          <div class="recent-run-label">
            <strong>{run.material} · {run.property}</strong>
            <div><code>{run.run_id}</code><time dateTime={run.updated_at}>{dateFormat().format(new Date(run.updated_at))}</time></div>
          </div>
          <div class="recent-run-actions">
            <Show when={run.stopped}><StatusBadge tone="neutral">{x("已停止", "Stopped")}</StatusBadge></Show>
            <ActionButton size="sm" disabled={props.disabled}
              variant={run.stopped ? "quiet" : "secondary"}
              busy={props.openingRunId === run.run_id} busyLabel={x("正在打开…", "Opening…")}
              aria-label={`${props.openingRunId === run.run_id ? x("正在打开", "Opening") : actionLabel(run)} ${run.run_id}`}
              onClick={() => props.onOpen(run.run_id, run.stopped)}>
              {actionLabel(run)}
            </ActionButton>
          </div>
        </li>}</For>
      </ul>
      <Show when={rows().length > FIRST_PAGE_SIZE}>
        <ActionButton size="sm" aria-expanded={expanded()} onClick={() => setExpanded((value) => !value)}>
          {expanded() ? x("收起", "Show fewer") : x(`查看全部 ${rows().length} 条`, `Show all ${rows().length}`)}
        </ActionButton>
      </Show>
    </Show>
    <DshRecentRunsHandoff locale={props.locale} />
  </section>;
}
