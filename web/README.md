# CosMatter 静态 UI 演示

直接用浏览器打开 `index.html` 即可查看。该页面不包含密钥、不调用第三方 API，也不加载真实论文全文。

页面默认展示合成工件。若要查看 Python 输出，请先运行 `cosmatter export-ui --run-id <run_id>`，再通过“导入 Python 导出的 UI JSON”选择 `runs/<run_id>/ui.json`。也可以导入 [`../examples/ui-demo/route_diagnostics.json`](../examples/ui-demo/route_diagnostics.json)；该文件明确标记为合成演示，非论文文本。

生产版本只可消费 Python 导出的、已经过权限与审核门禁的 JSON 工件；字段和安全边界见 [`../docs/architecture/01_UI_JSON契约.md`](../docs/architecture/01_UI_JSON契约.md)。