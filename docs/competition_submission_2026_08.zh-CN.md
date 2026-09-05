# 2026 年 8 月赛制修订：CosMatter 提交执行清单

本清单对应 GOAI 赛道三材料科学方向 2026 年 8 月修订对照表中与文献调研 Agent 直接相关的要求。它是提交前操作清单，不是竞赛结果或性能声明。

## 初赛必须提交

1. 源代码：Python 后端、SolidJS 前端、测试、示例配置、`LICENSE` 与本说明；随机种子与关键参数通过 `configs/reproducibility.example.json` 及运行工件记录。
2. 文献调研报告：`main.pdf`、`main.tex`、`references.bib` 和编译所需文件。运行 `export-latex-report --compile` 后，将输出目录整体复制到提交包。
3. 外部资源披露：每个实际使用的数据库/API必须记录来源、访问方式、访问日期/版本、用途、许可证或服务条款边界；没有实际调用的服务不得写成已完成结果。对进入正式报告的实际 run，使用下列命令将**人工填写且不含密钥**的披露表写入运行工件：

```powershell
.\.venv\Scripts\python.exe -m cosmatter record-external-resource-disclosure `
  --run-id YOUR_RUN --input .\external_resource_disclosure.json
```

该工件会被 `check-submission-readiness --run-id YOUR_RUN` 检查；报告的每条已接受 EvidenceCard 还会在 LaTeX 证据表中显示其书目数据来源。

若 `real_corpus_evaluation_run_record.json` 真实声明 `submission_truth_check: completed`，且四类人工指标、失败案例与 API 成本/延迟聚合工件均通过一致性校验，并绑定同一份预注册冻结问题集、`frozen_corpus_readiness.json` 清单哈希、全量人工标注覆盖审计和全覆盖书目来源审计，`build-final-submission-package` 会额外附带冻结问题集及这些**不含全文、路径、逐篇标签、评审备注或服务商原始响应**的聚合评测摘要；未完成或不一致的评测记录不会被打包。

## 最小复跑

```powershell
cd CosMatter
.\.venv\Scripts\python.exe -m pip install -e .
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
cd frontend
npm ci
npm run check
npm test
npm run build
```

初赛不强制提交容器环境。Docker、HPC 与外部计算引擎应当作为可选复现增强项，不能替代清晰的本地安装与测试说明。

## 正式报告生成与核验

```powershell
.\.venv\Scripts\python.exe -m cosmatter build-report --run-id YOUR_RUN
.\.venv\Scripts\python.exe -m cosmatter audit-report-evidence --run-id YOUR_RUN
.\.venv\Scripts\python.exe -m cosmatter export-latex-report --run-id YOUR_RUN --compile
```

最后一条只能处理已接受、带来源定位的 EvidenceCard。它会要求每个来源文档存在候选书目信息和非空书目来源；生成 `main.tex`、`references.bib`、`citation_audit.json` 与 `main.pdf`。结构审计不替代人工核查 DOI、作者、标题、原文定位和引用真实性。
当 `check-submission-readiness --run-id YOUR_RUN` 的所有机器检查通过后，使用以下命令生成最终提交包。它只写入允许的源代码、编译后的报告、引用审计和资源披露；任何失败检查都会阻止打包。

```powershell
.\.venv\Scripts\python.exe -m cosmatter check-submission-readiness --run-id YOUR_RUN
.\.venv\Scripts\python.exe -m cosmatter build-final-submission-package --run-id YOUR_RUN
```

## 进阶路线 B：势函数自动框架测试

该框架不宣称已运行 DFT、DP、MD、Monte Carlo 或 QMC。它只生成确定性的覆盖内、近边界、分布外任务，然后比较经批准的外部计算所导入的能量误差、力 RMSE 与耗时摘要。

```powershell
.\.venv\Scripts\python.exe -m cosmatter create-potential-benchmark-plan `
  --run-id potential_bfo_001 --system "BiFeO3 films" `
  --model baseline --model candidate --reference-method "DFT protocol" `
  --controls .\controls.json --seed 20260811 --baseline-model dp_baseline `
  --samples-per-regime 3

.\.venv\Scripts\python.exe -m cosmatter evaluate-potential-benchmark `
  --run-id potential_bfo_001 --input .\approved_external_results.json
```

`controls.json` 为控制变量到训练包络的映射，例如 `{"strain_percent": [-2, 2], "temperature_k": [300, 900]}`。`--samples-per-regime` 默认是 3，可在 1–32 内调整；每个种子会对训练域内、近边界和域外分别生成同样数量的控制坐标，便于按区域比较误差、力误差与时间，而不是以单点代替能力边界。外部结果必须覆盖计划中的每个“任务 × 势函数”组合；每行必须填写正整数 `atom_count`，同一任务的所有模型行必须拥有相同原子数和参考能量。不完整、重复、原子数/参考不一致或非有限数值会被拒绝。能量比较采用 eV/atom，避免缺陷、厚度或超胞大小改变时的总能量误差混淆。导入比较报告仍须人工审查，不得把数值差异直接写成普适能力结论。

可直接从 [`examples/templates/potential_benchmark_controls.example.json`](../examples/templates/potential_benchmark_controls.example.json) 开始；外部结果的字段约束见 [`examples/templates/potential_benchmark_results.schema.json`](../examples/templates/potential_benchmark_results.schema.json)。完成一次真实导入比较后，运行：

```powershell
.\.venv\Scripts\python.exe -m cosmatter propose-potential-followups --run-id potential_bfo_001
```

该命令只针对导入结果中一个具体“任务 × 势函数”弱点生成下一批**待人工批准**的局部边界加密任务：按每原子绝对能量误差、力 RMSE、壁钟时间依次确定锚点，并围绕该锚点的控制坐标逐项加密。它绝不会提交 DFT、DP、MD、MC 或 QMC 作业，也不把建议任务视作计算结果。
在任何外部计算前，先创建并由人工填写执行协议模板。协议将模型实现/版本、许可、参考方法、单位、结构生成边界和每个测试任务绑定到同一计划；它仍然不是计算执行授权，也不包含结构、轨迹、日志、密钥或绝对路径。

```powershell
.\.venv\Scripts\python.exe -m cosmatter create-potential-execution-protocol-template --run-id potential_bfo_001
# 人工填写 potential_execution_protocol_template.json 后：
.\.venv\Scripts\python.exe -m cosmatter record-potential-execution-protocol `
  --run-id potential_bfo_001 --input .\reviewed_potential_execution_protocol.json
```

### 经典 Monte Carlo 对照（路线 B）

修订版新增了经典统计物理 Monte Carlo（如 Ising）与 QMC 的探索方向，并要求相对经典算法量化说明。CosMatter 提供了一个实际可运行、但严格限定解释范围的二维零场 Ising 基准：Metropolis、Wolff 与 Swendsen–Wang 在相同有限晶格、温度、烧入步数、采样步数和随机种子规则下，比较能量自相关时间、有效样本数、有效样本率和本地壁钟时间。

```powershell
$env:PYTHONPATH = "src"
.\.venv\Scripts\python.exe -m cosmatter create-ising-benchmark-plan `
  --run-id ising_route_b_001 --lattice-size 32 `
  --temperature 2.0 --temperature 2.269 --temperature 2.5 `
  --burn-in-sweeps 200 --measurement-sweeps 1000 --repetitions 3 --seed 20260811
.\.venv\Scripts\python.exe -m cosmatter run-ising-benchmark --run-id ising_route_b_001
.\.venv\Scripts\python.exe -m cosmatter propose-ising-followups --run-id ising_route_b_001
.\.venv\Scripts\python.exe -m cosmatter export-ising-benchmark-summary --run-id ising_route_b_001
```

`run-ising-benchmark` 是本机实际执行的有限模型实验。每个“温度 × 算法”使用固定数量的独立种子重复，输出均值与离散度，并以同温度 Metropolis 为固定基线给出自相关时间比和单位有效样本效率比。结果同时安全记录 CPython 版本、操作系统、机器架构、逻辑 CPU 数、单进程/无 GPU-MPI 的并行边界、数值精度与计时范围；不记录主机名、用户、路径或队列信息。结果仅适用于该晶格大小、温度点、Python 实现、硬件和“扫掠”定义，不能外推为普适算法排序、QMC 性能或材料体系结论。第三个命令只产生待人工批准的温度/尺寸/采样量加密建议，不会自动启动后续计算。

`export-ising-benchmark-summary` 只导出聚合指标、测量边界、计划哈希和已存在的待批准加密建议；它不携带逐次数据、晶格状态或任何私有执行信息，可作为路线 B 的有限范围佐证附件，但不进入材料文献事实或 Gap 的证据链。
## 势函数基线与公平比较

比较计划应通过 `--baseline-model` 明确指定经典或既有势函数基线（默认仅为第一项 `--model`，建议显式填写）。导入结果后，报告会给出相对基线的平均每原子能量误差变化与壁钟时间比；这些数字只有在同一任务坐标、同一原子数、同一参考能量、已审核执行环境、相同计时范围下才可比较，且仍需人工科学审核。外部执行协议必须披露硬件类别、设备/队列、并行度、数值精度和计时范围；没有这些信息不得将速度差写成性能结论。
## 外部资源披露

使用 [`docs/templates/external_resource_disclosure.template.json`](templates/external_resource_disclosure.template.json) 为每个实际使用的数据库、API、模型、解析器或软件记录访问方式、版本/日期、条款和再分发边界。模板中的 `used_in_final_result` 在真实结果未进入提交物时必须保持 `false`。
## 严禁进入提交包

- `.env`、令牌、请求头与浏览器凭据；
- 学校账户访问的 PDF、完整 MinerU Markdown、全文缓存与私有绝对路径；
- 未经许可再分发的 Sci-Base/Sciverse/其他第三方内容；
- 没有来源定位或人工审核的 EvidenceCard、Gap 或科学结论；
- 未实际运行却标记为实验或势函数性能结果的样例数据。
