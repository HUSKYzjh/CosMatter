# CosMatter · 星际材料导航站

面向“材料科学文献驱动的科学发现智能体”赛题的证据优先最小闭环。

当前 M1.2 已实现：

- `MissionBrief`、`EvidenceCard`、`FlightPlan` 等可序列化数据契约；
- 受控任务状态机与拒绝非法状态跳转；
- 追加式 JSONL 黑匣子日志（不写入密钥）；
- Sciverse 适配器的配置、重试、限流和权限检查边界；
- 无密钥可运行的 `check-config`、`create-mission`、`assign-fleet`、`export-ui` 与 `demo-flow` 命令；
- 五支舰队的可校验 YAML 配置；调度中心只选择一支主舰队，并记录分派理由与所需设施；
- 静态 HTML 舰桥：只导入已脱敏的本地 UI JSON，不调用浏览器网络接口。

## 快速开始

在 PowerShell 中（推荐在独立虚拟环境内）：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .
.\.venv\Scripts\python.exe -m cosmatter check-config
.\.venv\Scripts\python.exe -m cosmatter create-mission `
  --question "为什么两篇论文对 BiFeO3 应变相变有不同结论？" `
  --material "BiFeO3" `
  --property "phase stability" `
  --scope "epitaxial thin films" `
  --run-id bfo_ui_demo `
  --mission-id mission_bfo_ui_demo
.\.venv\Scripts\python.exe -m cosmatter assign-fleet `
  --question "为什么两篇论文对 BiFeO3 应变相变有不同结论？" `
  --material "BiFeO3" `
  --property "phase stability" `
  --scope "epitaxial thin films" `
  --run-id bfo_ui_demo `
  --mission-id mission_bfo_ui_demo
.\.venv\Scripts\python.exe -m cosmatter export-ui --run-id bfo_ui_demo
.\.venv\Scripts\python.exe -m cosmatter demo-flow --run-id demo_cosmatter_001
```

`create-mission` 与 `assign-fleet` 需要在同一运行目录使用相同的 `--mission-id`，这样 `export-ui` 才能验证两个工件确实属于同一任务。`check-config` 仅报告配置项是否存在，绝不回显令牌。运行时只读上级项目根目录的 `../.env`（对应 `AIforResearch-材料科学Agent/.env`）；该文件受保护、不会被编辑或提交。字段模板见上级目录的 `../env.txt`。运行产生的审计轨迹写入 `runs/<run_id>/events.jsonl`，该目录不会提交到版本控制。

## 静态界面演示

界面原型位于 [`web/index.html`](web/index.html)。可直接用浏览器打开，或在项目根目录运行 `python -m http.server 8765 --directory web` 后访问 `http://127.0.0.1:8765/`。页面初始显示合成演示数据；选择 `runs/<run_id>/ui.json` 或 [`examples/ui-demo/route_diagnostics.json`](examples/ui-demo/route_diagnostics.json) 即可导入本地 UI 工件。它不会读取 `.env`、调用模型或访问第三方 API。

UI JSON 的字段、安全边界和扩展顺序见 [UI JSON 契约](docs/architecture/01_UI_JSON契约.md)。

静态舰桥现分为任务舰桥、研究工作流、星图网络和研究拓展四页，并提供深色、浅色、护眼主题；页面只消费用户选择的本地 JSON 工件。见 [舰桥多页面 UI 设计](docs/architecture/02_舰桥多页面UI设计.md)。

## 当前边界

`SciverseAdapter` 已实现有界的 `agentic-search` 调用、令牌解析、重试与 `is_content_accessible` 权限门禁。当前仓库仍处于证据优先基础设施阶段：不会把没有原文定位的文本当作科学事实，也不会在首版执行任意代码或提交外部计算。

后续架构、舰队专用设施、数据治理与 GitHub 发布边界见 [项目结构与后续路线图](docs/architecture/00_项目结构与后续路线图.md)。