import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
COMPONENT = (ROOT / "webapp" / "frontend_src" / "component.js").read_text(encoding="utf-8")
TEMPLATE = (ROOT / "webapp" / "frontend_src" / "template.html").read_text(encoding="utf-8")


class EvidenceDecisionBriefFrontendTest(unittest.TestCase):
    def test_navigation_and_api_loading_exist(self):
        self.assertIn("key:'brief',label:'证据决策简报'", COMPONENT)
        self.assertIn("/api/evidence/decision-brief/", COMPONENT)
        self.assertIn("openDecisionBrief", COMPONENT)
        self.assertIn("profile_brief", TEMPLATE)

    def test_page_has_expected_decision_sections_and_states(self):
        for text in [
            "执行摘要", "企业与数据概况", "核心临床试验证据", "证据版本演进与研发时间轴",
            "监管状态与时间口径", "证据强度及来源构成", "证据缺口与待确认关系",
            "风险与限制", "下一步证据方向", "引用来源及证据链", "禁止推断",
        ]:
            self.assertIn(text, TEMPLATE)
        for state in ["brief_loading", "brief_hasError", "brief_empty", "brief_hasData"]:
            self.assertIn(state, TEMPLATE)

    def test_print_and_mobile_layout_rules_exist(self):
        self.assertIn("@media print", TEMPLATE)
        self.assertIn("data-brief-paper", TEMPLATE)
        self.assertIn("@media(max-width:700px)", TEMPLATE)


if __name__ == "__main__":
    unittest.main()
