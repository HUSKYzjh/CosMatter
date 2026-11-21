export function ReadOnlyPreviewContext(props: { locale: "zh" | "en"; onExit?: () => void }) {
  const copy = (zh: string, en: string) => props.locale === "zh" ? zh : en;
  const exitPreview = () => { if (props.onExit) props.onExit(); else window.location.reload(); };
  return <section class="readonly-preview-context" aria-label={copy("只读预览数据边界", "Read-only preview data boundary")}>
    <small>{copy("只读预览数据层", "READ-ONLY PREVIEW DATA")}</small>
    <p>{copy("可浏览本阶段的操作与审核条件。返回起始页即可建立自己的研究任务。", "Explore this stage and its review criteria. Return to the launch page to start your own research task.")}</p>
    <button type="button" onClick={() => exitPreview()}>{copy("返回起始页", "Return to launch")}</button>
  </section>;
}
