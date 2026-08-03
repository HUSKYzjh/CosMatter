# CosMatter 静态 UI 演示

直接用浏览器打开 `index.html` 即可查看。该页面不包含密钥、不调用第三方 API，也不加载真实论文全文。

页面默认展示合成工件。若要查看 Python 输出，请先运行 `cosmatter export-ui --run-id <run_id>`，再通过“导入 Python 导出的 UI JSON”选择 `runs/<run_id>/ui.json`。也可以导入 [`../examples/ui-demo/route_diagnostics.json`](../examples/ui-demo/route_diagnostics.json)；该文件明确标记为合成演示，非论文文本。

生产版本只可消费 Python 导出的、已经过权限与审核门禁的 JSON 工件；字段和安全边界见 [`../docs/architecture/01_UI_JSON契约.md`](../docs/architecture/01_UI_JSON契约.md)。

## 多页面舰桥

- `index.html`：任务舰桥，导入 UI 工件、筛选已批准证据并展开条件矩阵；
- `workflow.html`：研究工作流，投影计划、检索、核验和报告门禁，并给出受控 CLI 的下一步提示；
- `network.html`：星图网络，从任务、已批准证据、条件簇和未知项派生可点击关系图；
- `extensions.html`：研究拓展，选择跨库核验、实验、计算或评测设施，并下载标记为 `untrusted` 的规划草案。

所有页面的右上角均可切换深色、浅色、护眼主题。主题只保存在浏览器本地偏好中；页面不会发送网络请求。更完整的页面职责、图语义与后续演进见 [`../docs/architecture/02_舰桥多页面UI设计.md`](../docs/architecture/02_舰桥多页面UI设计.md)。