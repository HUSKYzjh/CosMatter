# CosMatter 初赛源码复现说明

本仓库按 GOAI 赛道三 2026 年 8 月修订要求提供训练/推理（任务编排、文献工件审计、报告导出和进阶测试框架）源代码、随机种子、关键参数与外部资源披露入口。它不包含密钥、授权全文、私有 Markdown、运行缓存或第三方原始响应。

## 最小复现

```powershell
cd CosMatter
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
cd frontend
npm ci
npm run check
npm test -- --run
npm run build
```

Python 核心仅依赖标准库；`pyproject.toml` 声明构建元数据，`requirements.lock` 明确无强制第三方运行时依赖。前端依赖由 `frontend/package-lock.json` 锁定。

## 随机种子与关键参数

提交安全的默认配置在 [`configs/reproducibility.example.json`](configs/reproducibility.example.json)。其中列出默认随机种子、候选问题生成门槛与防抖时间、势函数边界测试每区采样数及其允许范围、经典 Ising 基准默认种子。真实运行应把实际采用的种子和参数写入其任务计划/评测工件；不要改写本模板来伪装历史运行。

## 外部资源与真实运行边界

外部 API、数据库、模型或解析器只有在用户授权、实际调用并记录访问日期/版本与条款后，才可被写入正式结果。请使用：

```powershell
.\.venv\Scripts\python.exe -m cosmatter record-external-resource-disclosure --run-id YOUR_RUN --input .\external_resource_disclosure.json
```

真实文献评测、势函数外部结果或材料结论并不由本说明或测试样例证明。正式提交前，执行：

```powershell
.\.venv\Scripts\python.exe -m cosmatter check-submission-readiness --run-id YOUR_RUN
.\.venv\Scripts\python.exe -m cosmatter build-final-submission-package --run-id YOUR_RUN
```

前一条命令检查源码、报告、引用审计和资源披露；后一条只会打包白名单源码与经门禁验证的报告工件。
