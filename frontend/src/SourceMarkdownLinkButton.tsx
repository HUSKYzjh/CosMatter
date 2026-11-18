import { Show, createSignal } from "solid-js";
import { safeMutationFeedback } from "./importFeedback";
import { LocalApiRequestError } from "./localApi";
import { ActionButton } from "./uiPrimitives";

export function SourceMarkdownLinkButton(props: {
  locale: "zh" | "en";
  paperTitle: string;
  onLink: (file: File) => Promise<void>;
}) {
  let fileInput!: HTMLInputElement;
  const [busy, setBusy] = createSignal(false);
  const [message, setMessage] = createSignal<string | null>(null);
  const t = (zh: string, en: string) => props.locale === "zh" ? zh : en;
  const label = () => t("关联本机 Markdown", "Link local Markdown");

  async function link(file: File) {
    if (busy()) return;
    if (!/\.(md|markdown)$/i.test(file.name) || file.size < 1 || file.size > 5 * 1024 * 1024) {
      setMessage(t("请选择 5 MiB 以内的 .md 或 .markdown 原文件。", "Choose the original .md or .markdown file, up to 5 MiB."));
      return;
    }
    setMessage(null);
    setBusy(true);
    try {
      await props.onLink(file);
    } catch (error) {
      if (error instanceof LocalApiRequestError && error.httpStatus === 422) {
        setMessage(t("文件与该候选的 MinerU 回执不匹配。请选择取回时保存的原文件。", "The file does not match this candidate’s MinerU receipt. Choose the original saved file."));
      } else {
        setMessage(safeMutationFeedback(error, t("关联失败，请刷新解析记录后重试。", "Linking failed. Refresh the parse records and try again."),
          t("关联结果待确认，请刷新解析记录。", "Refresh the parse records to confirm the link.")));
      }
    } finally {
      setBusy(false);
    }
  }

  return <div class="source-markdown-link">
    <input ref={fileInput} type="file" accept=".md,.markdown" hidden onChange={(event) => {
      const file = event.currentTarget.files?.[0];
      event.currentTarget.value = "";
      if (file) void link(file);
    }} />
    <ActionButton size="sm" aria-label={`${label()} · ${props.paperTitle}`} busy={busy()}
      busyLabel={t("正在核对…", "Checking…")} onClick={() => fileInput.click()}>{label()}</ActionButton>
    <Show when={message()}>{(value) => <p role="status">{value()}</p>}</Show>
  </div>;
}
