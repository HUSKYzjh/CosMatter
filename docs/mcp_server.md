# CosMatter MCP 服务：受控文献调研工具

## 目的

`cosmatter serve-mcp` 通过标准输入/输出（stdio）把 CosMatter 的受控工作流暴露给支持 MCP 的外部 Agent。它不是任意学术搜索接口：外部 Agent 也必须遵循“创建任务 → 不可信计划草案 → 人工批准 FlightPlan → 执行已批准检索”。模型草案和论文候选均不是科学证据。

## 可用工具

| 工具 | 外部调用 | 作用与门禁 |
| --- | --- | --- |
| `cosmatter_create_mission` | 否 | 创建问题、材料、性质、范围和舰队分配；只写本地运行工件。 |
| `cosmatter_draft_plan` | 可选 DeepSeek | 生成不可信计划草案；草案不能直接执行检索。 |
| `cosmatter_approve_plan` | 否 | 写入人工审阅的 FlightPlan；是检索的必经门禁。 |
| `cosmatter_execute_approved_search` | 可选 Sciverse/OpenAlex/Crossref | 只执行 FlightPlan 内的查询索引；返回元数据候选并记录回执，不读取全文。 |

最后一个工具只接受 `query_index` 和可选 `counter` 标志，不接受自由文本查询。这样外部 Agent 无法绕过人工批准临时替换检索词。

## 启动

在 `CosMatter/` 目录、已安装项目的虚拟环境中运行：

```powershell
.\.venv\Scripts\python.exe -m cosmatter serve-mcp
```

该命令等待客户端的 JSON-RPC 消息，不会自行调用模型、检索文献或读取论文。

## 客户端配置示意

不同客户端字段不同；通用配置的含义如下：

```json
{
  "mcpServers": {
    "cosmatter": {
      "command": "D:\\…\\CosMatter\\.venv\\Scripts\\python.exe",
      "args": ["-m", "cosmatter", "serve-mcp"],
      "cwd": "D:\\…\\CosMatter"
    }
  }
}
```

不要将 API Token 放入客户端配置、命令行参数、Agent 提示词或 MCP 消息。真实 `.env` 仅由本地运行时在外部工具实际被调用时使用，MCP 响应不返回密钥。

## 推荐交互

1. 调用 `cosmatter_create_mission`，明确科学问题、材料、性质和范围。
2. 可选调用 `cosmatter_draft_plan`，将草案交给人类研究者检查。
3. 人工确认子问题、主检索式、反例检索式和上限后，调用 `cosmatter_approve_plan`。
4. 调用 `cosmatter_execute_approved_search`，例如 `{ "run_id": "bfo_mcp_001", "query_index": 0, "sources": ["sciverse"] }`。
5. 对返回候选继续执行人工筛选、授权全文、MinerU、Source Map 和 EvidenceCard 流程；MCP 不跳过这些步骤。

## 安全与审计边界

- 不返回第三方密钥、完整 API 响应、受限 PDF 或全文；
- 每次实际检索保留受限提供方回执关联和审计事件；
- 候选必须经人工 `include_for_fulltext` 决定、Source Map 定位和证据核验，才可能成为报告事实；
- Research Gap 必须来自接受证据与条件差异，不能由外部 Agent 直接写入。

## 离线验证

```powershell
$env:PYTHONPATH = "src"
.\.venv\Scripts\python.exe -m unittest tests.test_mcp_server -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -q
```

MCP 专用测试覆盖初始化、工具枚举、受控派发、安全错误响应和 stdio JSON-RPC 解析。

## 本地 Sci-Base / 授权语料检索

新增工具 cosmatter_execute_approved_local_corpus_search 用于已准备好的 Sci-Base Open Access 子集或经人工授权的本地 Markdown 索引。它与远程检索共享 FlightPlan 门禁：只能传入已批准的 query_index，可选 counter，不能传入自由检索词。调用者显式给出 index_path，但该私有路径、索引内路径和解析正文只在本地进程读取；MCP 返回、候选工件和审计事件仅保留普通文献元数据、查询索引、来源标签和数量。

因此推荐的双源工作方式为：以 cosmatter_execute_approved_search 通过 Sciverse 执行受控的远程语义检索；以 cosmatter_execute_approved_local_corpus_search 在经过 DOI 精确匹配、授权边界检查后的本地 Sci-Base 或 PDF 库中执行同一 FlightPlan 查询。两者返回的候选会使用已有的 DOI/文献 ID 去重，之后仍必须进行人工筛选、全文授权、MinerU、Source Map 与证据核验。
