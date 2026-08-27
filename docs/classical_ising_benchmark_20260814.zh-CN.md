# 经典 Ising Monte Carlo 有限基准记录（2026-08-14）

本记录对应修订手册中路线 B 对经典 Monte Carlo 的最低比较要求。它是一次**已经执行**、但严格受限的本机有限二维 Ising 基准；不是材料体系模拟、热力学极限结论、QMC 结果，也不是跨硬件性能结论。

## 1. 可复现身份

| 项目 | 已执行配置 |
| --- | --- |
| 运行目录 | `runs/ising_route_b_20260814/` |
| 模型 | 二维、零外场、最近邻 Ising 模型 |
| 算法 | Metropolis、Wolff、Swendsen-Wang |
| 晶格 | 16 × 16 |
| 温度 | 2.000、2.269、2.500 |
| 观测量 | 每自旋能量 |
| 预热 / 测量 | 200 / 800 sweeps |
| 独立重复 | 每个“温度 × 算法”3 次 |
| 随机种子 | 20260811；各重复从确定性派生种子启动 |
| 运行环境 | Windows、CPython 3.12.13、单 Python 进程、无 GPU/MPI |
| 计时边界 | 仅测量 sweeps；不含计划创建、初始化、预热、序列化与排队 |

原始计划、结果、汇总和待批准的加密提案分别保存在 `ising_benchmark_plan.json`、`ising_benchmark_result.json`、`ising_benchmark_summary.json`、`ising_benchmark_followups.json`。汇总中的计划哈希为 `5f03cb33034fba6c0e6d3d307d09bbee098042846fe7e133e04307343af0c4ee`。

## 2. 已执行聚合结果

下表的 \(\tau_{int}\) 为积分自相关时间（sweeps），ESS/s 为有效独立样本数每秒；“相对 Metropolis”均在**同一温度**内计算。

| T | 算法 | \(\tau_{int}\) | ESS/s | 测量时间 (s) | \(\tau_{int}\) / Metropolis | ESS/s / Metropolis |
| ---: | --- | ---: | ---: | ---: | ---: | ---: |
| 2.000 | Metropolis | 3.042 | 416.14 | 0.330 | 1.000 | 1.000 |
| 2.000 | Swendsen-Wang | 2.946 | 503.40 | 0.272 | 0.968 | 1.210 |
| 2.000 | Wolff | 0.669 | 1649.24 | 0.372 | 0.220 | 3.963 |
| 2.269 | Metropolis | 10.906 | 160.24 | 0.240 | 1.000 | 1.000 |
| 2.269 | Swendsen-Wang | 3.506 | 437.14 | 0.269 | 0.322 | 2.728 |
| 2.269 | Wolff | 0.677 | 1947.53 | 0.306 | 0.062 | 12.154 |
| 2.500 | Metropolis | 8.284 | 251.02 | 0.244 | 1.000 | 1.000 |
| 2.500 | Swendsen-Wang | 2.568 | 630.53 | 0.252 | 0.310 | 2.512 |
| 2.500 | Wolff | 0.825 | 1882.61 | 0.259 | 0.100 | 7.500 |

## 3. 可报告的观察与禁止外推

- 在该有限晶格和本次 sweep 定义中，Metropolis 在 T = 2.269 的局部自相关信号最高（\(\tau_{int}=10.906\)），因此这是进一步审查临界慢化的**局部触发点**。
- 同一局部测量中，集群算法的自相关时间更低；这只说明本实现、该尺寸、该计时范围内的采样效率差异。
- 不能据此声称热力学临界点、普适动态指数、任何材料相变、QMC 表现，或不受硬件影响的算法绝对排名。

## 4. 主动加密任务（未执行）

系统已基于上述局部触发点生成一个 `approval_required: true` 的后续提案：在 T = 2.20093、2.269、2.33707 以及 L = 16、32 上，将测量长度提高到 1600 sweeps。该提案必须由研究者批准后另行运行；它不是已完成的计算，也不能作为结果写入报告。

## 5. 复跑命令

```powershell
cd CosMatter
$env:PYTHONPATH = "src"
.\.venv\Scripts\python.exe -m cosmatter create-ising-benchmark-plan `
  --run-id ising_route_b_reproduction --lattice-size 16 `
  --temperature 2.0 --temperature 2.269 --temperature 2.5 `
  --burn-in-sweeps 200 --measurement-sweeps 800 --seed 20260811 --repetitions 3
.\.venv\Scripts\python.exe -m cosmatter run-ising-benchmark --run-id ising_route_b_reproduction
.\.venv\Scripts\python.exe -m cosmatter propose-ising-followups --run-id ising_route_b_reproduction
.\.venv\Scripts\python.exe -m cosmatter export-ising-benchmark-summary --run-id ising_route_b_reproduction
```

提交前应重新执行上述命令，并保存所用代码修订、环境版本及新生成工件；不要将本记录中的本机时间直接复制为其他机器或更大晶格的结果。
