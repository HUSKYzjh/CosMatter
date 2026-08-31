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

## 初赛提交与复现

2026 年 8 月赛制要求初赛同时提供源代码与 PDF/LaTeX 文献调研报告。提交步骤、资源披露、引用审计和势函数框架测试的边界见 [`docs/competition_submission_2026_08.zh-CN.md`](docs/competition_submission_2026_08.zh-CN.md)。

- 初赛报告源：`python -m cosmatter export-latex-report --run-id YOUR_RUN --compile`；
- 可复现默认参数：[`configs/reproducibility.example.json`](configs/reproducibility.example.json)；
- 开源许可证：MIT（仅覆盖本仓库代码与文档，不授予第三方数据或 API 内容的再分发权限）。
- 数据与安全边界：[数据治理](docs/data-governance.md)、[评测规范](docs/evaluation.md)、[安全政策](SECURITY.md)。
- 进阶势函数边界框架：计划、人工执行协议、外部汇总结果比较与待批准的边界加密任务；不会自行提交外部计算。
- 引用与贡献：[CITATION.cff](CITATION.cff)、[CONTRIBUTING.md](CONTRIBUTING.md)；修订要求的逐项映射见 [docs/competition_requirement_traceability.zh-CN.md](docs/competition_requirement_traceability.zh-CN.md)。
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

`create-mission` 与 `assign-fleet` 需要在同一运行目录使用相同的 `--mission-id`，这样 `export-ui` 才能验证两个工件确实属于同一任务。`check-config` 仅报告配置项是否存在，绝不回显令牌。标准工作区布局下，运行时只读开发环境根目录的 `../.env`（即 `development/.env`）；该文件受保护、不会被编辑或提交。字段模板位于相邻的 `../AIforResearch-Materials-Agent-Workspace/env.txt`。案例运行工件写入 `../../case-data/runtime/runs/<run_id>/events.jsonl`，私有缓存写入 `../../case-data/runtime/private/`；它们均不提交到版本控制。

## 全量验收测试

从任意新开的 PowerShell 进入项目根目录后运行：

```powershell
.\scripts\acceptance.ps1
```

该入口依次执行 Python 测试、前端类型检查与测试、DSH 发布/回放/配方门禁、七个本地 DSH 包测试和 `npm pack --dry-run`，最后检查 Git 空白错误。它不读取 `.env`，不调用任何提供商。如需指定解释器，可传入 `-Python C:\Python314\python.exe`；仅检查 Python 套件时可运行 `.\scripts\test-all.ps1`。完整通过时，最后单独输出 `OK - CosMatter full local acceptance passed.`。

若需保存验收收据，请显式指定一个新 JSON 文件：

```powershell
.\scripts\acceptance.ps1 -ReportPath D:\safe-local-folder\cosmatter-acceptance.json
```

收据只包含固定步骤名、通过/失败状态、耗时、起止时间和是否启用了严格 DSH 步骤；不包含命令、路径、测试日志、问题、URL、全文、提供商响应或凭据。默认拒绝覆盖已有收据；仅在明确需要替换时才附加 `-OverwriteReport`。

验收收据使用 schema `1.1`，并附带对全部固定字段的 SHA-256 内容绑定。验证脚本兼容 Windows PowerShell 5 和 PowerShell 7，可离线验证且不会输出收据路径或原始内容：

```powershell
.\scripts\verify-acceptance-receipt.ps1 -Path D:\safe-local-folder\cosmatter-acceptance.json
```

## 本机只读界面预览

优先使用仅绑定 `127.0.0.1` 的 Solid 预览服务。它只服务前端静态文件，且仅在明确给出 `-RunId` 时暴露该运行已经导出的脱敏 `/ui.json`：

```powershell
.\scripts\start-solid-preview.ps1 -RunId bfo_ui_demo
```

脚本与 Python 运行时使用相同的数据根目录规则：优先 `COSMATTER_DATA_ROOT`，否则使用工作区 `case-data/runtime`，最后才回退到独立仓库的本地目录。它不会列出运行目录、读取 `.env`、暴露事件日志、私有缓存或任意路径。

不要附加 `-Api`，除非是在明确授权的本地受控任务会话中需要写入 API；`-Api` 会启用独立的 allowlisted 本机任务接口，因此不属于只读预览模式。页面初始显示合成演示数据；用户仍可显式选择 [`examples/ui-demo/route_diagnostics.json`](examples/ui-demo/route_diagnostics.json) 进行浏览器内导入。

UI JSON 的字段、安全边界和扩展顺序见 [UI JSON 契约](docs/architecture/01_UI_JSON契约.md)。

静态舰桥现分为任务舰桥、研究工作流、星图网络、论文导读和研究拓展五页，并提供深色、浅色、护眼主题；页面只消费用户选择的本地 JSON 工件。见 [舰桥多页面 UI 设计](docs/architecture/02_舰桥多页面UI设计.md)。

## 当前边界

`SciverseAdapter` 使用官方 `sciverse` Python SDK 的有界 `semantic_search` 与 `read_content` 调用。候选仅在上游明确声明全文可访问，或人工筛选后由显式本地读取命令写入哈希确认时，才可进入受控解析。详见 [SciVerse 提供方契约](docs/SCIVERSE_PROVIDER_CONTRACT.zh-CN.md)。当前仓库仍处于证据优先基础设施阶段：不会把没有原文定位的文本当作科学事实，也不会在首版执行任意代码或提交外部计算。

后续架构、舰队专用设施、数据治理与 GitHub 发布边界见 [项目结构与后续路线图](docs/architecture/00_项目结构与后续路线图.md)。
