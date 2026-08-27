# Sci-Base 本地 RAG：从受控 Parquet 子集到 CosMatter BM25 索引

本文说明如何把**已经下载并预筛选在本机的** Sci-Base Parquet 分片接入 CosMatter。本功能不下载数据集、不调用外部 API，也不会把全文、Markdown 或本地路径写入 mission 的 `runs/` 工件。

Sci-Base 的 Hugging Face 数据卡标明其发布格式为 Parquet，并提供 `title`、`doi`、`sha256`、`is_oa`、`abstract` 和 `content_list` 等字段；数据集本身规模很大，不能把“扫描一个小分片”误写成“已完成全库检索”。请先在本地准备面向材料方向的受控小分片，并记录数据版本和筛选条件。

官方数据卡：[opendatalab/Sci-Base](https://huggingface.co/datasets/opendatalab/Sci-Base)

## 适用边界

此适配器的目标是建立可重复的**本地 BM25 基线**：

- 输入：一个显式指定的本地 `.parquet` 文件，以及已人工审核的 `corpus_manifest.json`；
- 对齐：仅按规范化 DOI 精确匹配，绝不按相似题名猜测对应关系；
- 许可：匹配行必须显式为 `is_oa=true`；
- 输出：用户指定的私有目录内的 Markdown、路径索引与转换回执；
- run 工件：只会得到后续检索候选元数据和审计事件，不会得到索引路径、全文或原始 Parquet 内容。

它不能代替 Sciverse 的在线覆盖，也不是向量检索、语义检索或混合检索的性能证明。对于没有 DOI 的已审核文献，适配器会在回执中计数，但不会通过题名强行匹配。

## 前置条件

1. 已通过 `record-corpus-manifest-from-selection-review`（或等价的人审流程）冻结语料清单；
2. 已在授权、许可范围内获得 Sci-Base 的一个本地 Parquet 子集；
3. 在 CosMatter 环境中安装可选 Parquet 读取器：

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[scibase]"
```

该可选组件当前只引入 `pyarrow`。它不读取项目根目录的密钥，也不调用 Hugging Face、Sciverse、DeepSeek 或 MinerU。

## 1. 生成私有索引

假设 mission 的 run ID 为 `bfo_90_v1`，而 Parquet 子集和输出目录都在私有受控位置：

```powershell
.\.venv\Scripts\python.exe -m cosmatter prepare-scibase-local-index `
  --run-id bfo_90_v1 `
  --input "D:\\private\\scibase\\materials_bfo_subset.parquet" `
  --output-dir "D:\\private\\cosmatter_indexes\\bfo_90_scibase_v1" `
  --dataset-revision "【填写实际下载快照或提交标识】" `
  --max-rows 500000 `
  --require-all-doi-matched
```

`--max-rows` 是扫描上限，默认 500,000，最大 5,000,000。应先从小分片试运行；不要对完整数据集进行无界扫描。若目前只拿到分批分片，可以暂时不加 `--require-all-doi-matched`，但必须查看输出回执中的未匹配数量，并在最终评测前冻结完整的 DOI 覆盖边界。

输出目录必须是新的或空的目录，且不能位于 `runs/<run-id>/` 内。成功后会包含：

```text
scibase_markdown/                    # 私有转换结果，不提交、不上传
scibase_local_source_index.json      # 仅供本地 BM25 读取，含本地路径
scibase_local_index_receipt.json     # 私有转换回执与覆盖计数
```

其中回执会记录数据集标识、版本字段是否提供、精确 DOI 匹配策略、OA 要求、匹配数量、无 DOI 数量和许可提醒。它不会写入 mission run。

## 2. 用批准的检索计划执行本地检索

先完成任务规划和人工批准的 FlightPlan。随后让本地与在线路线使用同一个受控查询：

```powershell
.\.venv\Scripts\python.exe -m cosmatter execute-plan-local-corpus-query `
  --run-id bfo_90_v1 `
  --index "D:\\private\\cosmatter_indexes\\bfo_90_scibase_v1\\scibase_local_source_index.json" `
  --query-index 0
```

如计划中有反例查询：

```powershell
.\.venv\Scripts\python.exe -m cosmatter execute-plan-local-corpus-query `
  --run-id bfo_90_v1 `
  --index "D:\\private\\cosmatter_indexes\\bfo_90_scibase_v1\\scibase_local_source_index.json" `
  --query-index 0 --counter
```

该命令只接受已批准查询的索引号，使用 FlightPlan 的候选上限，并在内存中完成字段加权 BM25。生成的 `retrieval_candidates.json` 只有文献卡片与分数；本地路径和正文仍不进入 run。

## 3. 接下来的证据门禁

检索得到的候选仍只是候选，不是材料事实：

1. 生成人工筛选模板并记录筛选结论；
2. 对纳入全文的文献走受权的解析/审阅流程；
3. 仅把人工选定的短片段写入 Source Map；
4. 再让 LLM 起草抽取或 Gap，最后由证据核验门禁决定能否进入报告。

不要因为文献来自 Sci-Base 或本地索引就跳过原文定位和人工审核。Sci-Base 的结构化解析有助于检索和阅读，但不自动证明某个具体材料结论正确。

## 失败处理

- 缺少 `pyarrow`：安装 `.[scibase]` 后重试；
- Parquet 缺少 `sha256`、`title`、`doi`、`is_oa` 或 `content_list`：先检查实际分片模式，不要擅自伪造字段；
- DOI 不匹配：返回到人工审核清单，核对 DOI 规范化、版本论文和重复记录；
- 行不标记 OA：不进入私有索引；
- 输出目录已有文件：使用新目录，适配器不会覆盖既有私有数据；
- 未匹配数量不为零：将该数字与分片范围一同记录，在评测报告中说明其覆盖边界。

## 复现记录建议

每次构建都应在团队私有记录中保留：Parquet 文件来源和下载日期、数据集版本/修订、分片筛选规则、命令、行扫描上限、回执摘要、冻结清单 ID、人工审核人和失败案例。公开仓库只应提交代码、配置模板、合成夹具和不含路径/全文的聚合结果。
