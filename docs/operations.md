# CosMatter 受控运行手册

本手册描述从研究问题到可导入 UI 的本地工件流。所有命令均在
`CosMatter/` 目录、虚拟环境中运行。密钥只保存在上级项目根目录的 `../.env`（即`AIforResearch-材料科学Agent/.env`），该文件受保护、只读且不提交；不要把密钥、受限全文或浏览器凭据写进任何 JSON 工件。字段名见上级目录的 `../env.txt`。

## 0. 配置检查

```powershell
.\.venv\Scripts\python.exe -m cosmatter check-config
```

只有 `deepseek_configured` 和/或 `sciverse_configured` 为 `true` 时才会调用对应
服务。没有密钥时，冻结测试、UI 演示和所有本地门禁仍可运行。

## 1. 建立同一任务的身份与舰队

`create-mission` 和 `assign-fleet` 必须共享 `--run-id` 与 `--mission-id`：

```powershell
.\.venv\Scripts\python.exe -m cosmatter create-mission `
  --question "Why can phase reports differ across conditions?" `
  --material BiFeO3 --property "phase stability" --scope "epitaxial films" `
  --run-id bfo_live_001 --mission-id mission_bfo_live_001

.\.venv\Scripts\python.exe -m cosmatter assign-fleet `
  --question "Why can phase reports differ across conditions?" `
  --material BiFeO3 --property "phase stability" --scope "epitaxial films" `
  --run-id bfo_live_001 --mission-id mission_bfo_live_001
```

## 2. 生成草稿、人工审核并批准计划

有 DeepSeek 密钥时，草稿命令只生成 `research_plan_draft.json`，其内容不会自动
被执行：

```powershell
.\.venv\Scripts\python.exe -m cosmatter draft-plan --run-id bfo_live_001
```

人工审核后，创建一个独立 JSON 文件，例如 `reviewed_plan.json`：

```json
{
  "subquestions": ["Which conditions differ?"],
  "queries": ["BiFeO3 epitaxial strain phase stability"],
  "counter_queries": ["BiFeO3 epitaxial phase contradictory thickness substrate"]
}
```

批准命令会检查上限（最多 5 个子问题、8 个查询、4 个反例查询、3 轮、20 篇候选）：

```powershell
.\.venv\Scripts\python.exe -m cosmatter approve-plan `
  --run-id bfo_live_001 --input .\reviewed_plan.json
```

此步写入 `flight_plan.json`；它才是可执行计划。

## 3. 从批准计划执行有界检索

有 Sciverse token 时，按查询索引执行：

```powershell
.\.venv\Scripts\python.exe -m cosmatter execute-plan-query `
  --run-id bfo_live_001 --query-index 0

# 对批准计划中的反例查询使用同一受控通道
.\.venv\Scripts\python.exe -m cosmatter execute-plan-query `
  --run-id bfo_live_001 --query-index 0 --counter
```

两类检索均只接受已批准计划中的索引；审计记录查询类别与索引，不回显查询文本。该命令只保存 `retrieval_candidates.json` 中的元数据卡，不保存 API 原始响应、摘要或
全文。候选必须标记为可访问，后续才能作为证据来源。

## 4. 录入可定位证据并生成交付物

证据草稿由已获授权的内容提取流程产生，至少含有 `claim`、`stance`、材料、性质、
短摘录、`document_id + locator`、条件字段及 `evidence_id`。它必须来自本运行内可
访问的候选：

```powershell
.\.venv\Scripts\python.exe -m cosmatter ingest-evidence `
  --run-id bfo_live_001 --input .\evidence_draft.json

.\.venv\Scripts\python.exe -m cosmatter build-report --run-id bfo_live_001
.\.venv\Scripts\python.exe -m cosmatter export-ui --run-id bfo_live_001
```

`ingest-evidence` 会写入证据卡及不可变审核决策。`build-report` 仅使用已接受的证据
ID 生成清单式报告；`export-ui` 只投影许可范围内的短摘录与报告摘要。

## 5. 验证

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m cosmatter evaluate-fixture `
  --fixture .\examples\frozen\bfo_route_diagnostics.json --run-id frozen_eval_001
```

`runs/` 是本地运行数据，已被 Git 忽略。提交前确认其中没有被误加入暂存区。
