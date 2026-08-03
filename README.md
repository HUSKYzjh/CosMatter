# CosMatter · 星际材料导航站

面向“材料科学文献驱动的科学发现智能体”赛题的证据优先最小闭环。

当前 M1.1 已实现：

- `MissionBrief`、`EvidenceCard`、`FlightPlan` 等可序列化数据契约；
- 受控任务状态机与拒绝非法状态跳转；
- 追加式 JSONL 黑匣子日志（不写入密钥）；
- Sciverse 适配器的配置、重试、限流和权限检查边界；
- 无密钥可运行的 `check-config`、`create-mission` 与 `demo-flow` 命令。

## 快速开始

在 PowerShell 中（推荐在独立虚拟环境内）：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .
.\.venv\Scripts\python.exe -m cosmatter check-config
.\.venv\Scripts\python.exe -m cosmatter create-mission `
  --question "BiFeO3 薄膜中压缩应变如何影响 T-like 相稳定化？" `
  --material "BiFeO3" `
  --property "T-like phase stability" `
  --scope "epitaxial thin films"
.\.venv\Scripts\python.exe -m cosmatter demo-flow --run-id demo_bfo_001
```

`check-config` 仅报告配置项是否存在，绝不回显令牌。运行产生的审计轨迹写入 `runs/<run_id>/events.jsonl`，该目录不会提交到版本控制。

## 当前边界

`SciverseAdapter` 已实现有界的 `agentic-search` 调用、令牌解析、重试与 `is_content_accessible` 权限门禁。当前仓库仍处于证据优先基础设施阶段：不会把没有原文定位的文本当作科学事实，也不会在首版执行任意代码或提交外部计算。

后续架构、舰队专用设施、数据治理与 GitHub 发布边界见 [项目结构与后续路线图](docs/architecture/00_项目结构与后续路线图.md)。
