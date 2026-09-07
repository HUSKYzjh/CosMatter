"""Guard the public governance entry points and their privacy boundary."""

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class GovernanceDocumentationTests(unittest.TestCase):
    def test_public_governance_documents_are_linked_from_the_readme(self) -> None:
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        for relative_path in ("docs/data-governance.md", "docs/evaluation.md", "SECURITY.md"):
            self.assertIn(relative_path, readme)

    def test_governance_docs_state_machine_enforced_boundaries_without_private_paths(self) -> None:
        governance = (ROOT / "docs" / "data-governance.md").read_text(encoding="utf-8")
        evaluation = (ROOT / "docs" / "evaluation.md").read_text(encoding="utf-8")
        security = (ROOT / "SECURITY.md").read_text(encoding="utf-8")
        self.assertIn("哈希绑定", governance)
        self.assertIn("原子发布", governance)
        self.assertIn("人工审核", evaluation)
        self.assertIn("四级证据成熟度", evaluation)
        self.assertIn("revoke or rotate", security)
        for text in (governance, evaluation, security):
            self.assertNotIn("C:\\Users\\", text)
            self.assertNotIn("/home/", text.lower())

    def test_pst_md_only_configuration_search_plan_preserves_claim_boundaries(self) -> None:
        plan = (
            ROOT / "docs" / "PST_MD_ONLY_CONFIGURATION_SEARCH_PLAN.zh-CN.md"
        ).read_text(encoding="utf-8")
        roadmap = (
            ROOT / "docs" / "COMPUTATIONAL_SIMULATION_WORKFLOW_COMPETITIVE_ANALYSIS.zh-CN.md"
        ).read_text(encoding="utf-8")
        todo = (ROOT / "TODO.md").read_text(encoding="utf-8")

        for required in (
            "8×8×8",
            "512",
            "n_Pb + n_Sr = 512",
            "Pb ↔ Sr",
            "Pareto",
            "随机基线",
            "至少 3 个独立",
            "代理预测产生的排名数为 0",
            "不能证明全局最优",
            "plan_only / framework_only",
        ):
            self.assertIn(required, plan)
        self.assertIn("PST_MD_ONLY_CONFIGURATION_SEARCH_PLAN.zh-CN.md", roadmap)
        self.assertIn("PST_MD_ONLY_CONFIGURATION_SEARCH_PLAN.zh-CN.md", todo)
        self.assertNotIn("C:\\Users\\", plan)
        self.assertNotIn("/home/", plan.lower())

    def test_pst_research_audit_records_observed_limits_and_improvement_gates(self) -> None:
        audit = (
            ROOT / "docs" / "PST_COSMATTER_RESEARCH_AUDIT_AND_IMPROVEMENT_PLAN.zh-CN.md"
        ).read_text(encoding="utf-8")
        plan = (
            ROOT / "docs" / "PST_MD_ONLY_CONFIGURATION_SEARCH_PLAN.zh-CN.md"
        ).read_text(encoding="utf-8")

        for required in (
            "367 个唯一 `document_id`",
            "21 个检索回执 + 6 个上下文回执",
            "367 条候选均缺 DOI",
            "已筛选候选进入阅读路线",
            "1/3",
            "0/3",
            "provider_advertised → confirmed → failed/expired",
            "prepare-sciverse-context-review",
            "property_prediction_count = 0",
            "不是人工审核结果",
            "6 个委托 Source Map",
            "正式材料事实模板会拒绝它们",
            "敏感工件发现类别",
        ):
            self.assertIn(required, audit)
        self.assertIn("MD Response-guided Motif Tempering", plan)
        self.assertIn("PST_COSMATTER_RESEARCH_AUDIT_AND_IMPROVEMENT_PLAN.zh-CN.md", plan)
        self.assertNotIn("C:\\Users\\", audit)
        self.assertNotIn("/home/", audit.lower())
