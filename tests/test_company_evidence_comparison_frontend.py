import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
COMPONENT = ROOT / "webapp" / "frontend_src" / "component.js"
TEMPLATE = ROOT / "webapp" / "frontend_src" / "template.html"
STATIC_INDEX = ROOT / "webapp" / "static" / "index.html"


class InstitutionComparisonFrontendTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.component = COMPONENT.read_text(encoding="utf-8")
        cls.template = TEMPLATE.read_text(encoding="utf-8")
        cls.index = STATIC_INDEX.read_text(encoding="utf-8")

    def test_institution_comparison_route_and_controls_are_wired(self):
        self.assertIn("/api/evidence/institution-comparison", self.component)
        self.assertIn("loadCompanyComparison", self.component)
        self.assertIn("cmp_onCompanyA", self.component)
        self.assertIn("cmp_onCompanyB", self.component)
        self.assertIn("交换机构", self.template)
        self.assertIn("机构对比", self.template)

    def test_fields_come_from_comparable_coverage_without_ranking(self):
        self.assertIn("field_definitions", self.component)
        self.assertIn("可比数据覆盖", self.component)
        self.assertIn("不输出排名、评分或竞争力结论", self.component)
        self.assertNotIn("/api/evidence/company-comparison/metric-rules", self.component)
        self.assertNotIn("loadCompanyMetricRules", self.component)

    def test_evidence_tabs_remain_available(self):
        for label in ["来源检索", "规范化数据", "证据链", "机构对比"]:
            self.assertIn(label, self.template)

    def test_static_artifact_matches_frontend_sources(self):
        expected = self.template.replace("/*__COMPONENT__*/", self.component)
        self.assertEqual(self.index, expected)


if __name__ == "__main__":
    unittest.main()
