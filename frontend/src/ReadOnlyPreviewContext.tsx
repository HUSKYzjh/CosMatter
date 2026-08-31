export function ReadOnlyPreviewContext(props: { locale: "zh" | "en"; onExit?: () => void }) {
  const copy = (zh: string, en: string) => props.locale === "zh" ? zh : en;
  const exitPreview = () => { if (props.onExit) props.onExit(); else window.location.reload(); };
  return <section class="readonly-preview-context" aria-label={copy("只读预览数据边界", "Read-only preview data boundary")}>
    <small>{copy("只读预览数据层", "READ-ONLY PREVIEW DATA")}</small>
    <strong>{copy("当前内容仅作只读预览，不代表此预览已执行任务或产生新工件。", "The current content is a read-only preview and does not attest that this preview executed a task or produced a new artifact.")}</strong>
    <p>{copy("此页面只用于检查阶段布局、门禁和导航；预览不会创建任务、上传文件、写入本地工件、调用模型或检索 API，且没有可引用的新结论。", "This page only checks stage layout, gates, and navigation. The preview creates no task, uploads no file, writes no local artifact, calls no model or retrieval API, and produces no citable result.")}</p>
    <button type="button" onClick={() => exitPreview()}>{copy("返回起始页", "Return to launch")}</button>
  </section>;
}
