# 离线端到端航程验证

测试文件 tests/test_offline_end_to_end_workflow.py 使用两条**合成的、非科研事实**的短文本记录，验证 CosMatter 的生产工件和门禁如何串联。它不读取 .env、不调用 DeepSeek、Sciverse、MinerU 或其他外部服务，也不应被用作 BiFeO3 的性能或相稳定性结论。

运行方式：

    $env:PYTHONPATH = "src"
    .\.venv\Scripts\python.exe -m unittest tests.test_offline_end_to_end_workflow -v

该航程依次执行：

1. 创建 Mission Brief、舰队分配和人工批准的 FlightPlan；
2. 为主检索和反例检索各写入一个受控候选，再进行完整人工筛选；
3. 为两篇候选记录完成的 MinerU 任务和人工 Source Map；
4. 通过正式 evidence-ingestion 门禁写入带完整条件的支持与反驳 EvidenceCard；
5. 通过正式材料事实复核接口写入带 Source Map 定位的结构化事实，执行条件差异与跨文献融合；
6. 从已接受证据与已执行反例查询生成 review-required Research Gap 候选；
7. 生成 Markdown/JSON 报告、来源审计、报告审计、UI 投影和 workflow readiness。

断言同时要求检索、筛选、解析、抽取、Gap 与报告阶段均完成；报告的文献 ID 与定位符覆盖率为 100%；UI 中允许出现经人工批准的短摘录，但不得出现解析任务 ID 或全文来源 URL。实际 90 篇 BiFeO3 评测仍必须使用经授权的真实文献和人工金标准，不能以该合成航程代替。
