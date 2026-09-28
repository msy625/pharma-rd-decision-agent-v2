import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
COMPONENT = ROOT / "webapp" / "frontend_src" / "component.js"
TEMPLATE = ROOT / "webapp" / "frontend_src" / "template.html"
STATIC_INDEX = ROOT / "webapp" / "static" / "index.html"


class NormalizedInstitutionTimelineFrontendTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.component = COMPONENT.read_text(encoding="utf-8")
        cls.template = TEMPLATE.read_text(encoding="utf-8")
        cls.index = STATIC_INDEX.read_text(encoding="utf-8")

    def test_timeline_uses_structured_normalized_api(self):
        self.assertIn("/api/evidence/institution-timeline", self.component)
        self.assertNotIn("/api/evidence/timeline", self.component)
        for param in ["institution:", "trial_id:", "event_type:", "year:", "include_undated:"]:
            self.assertIn(param, self.component)

    def test_metrics_match_normalized_timeline_response(self):
        for field in ["event_count", "unique_study_count", "study_event_count", "publication_event_count", "regulatory_event_count", "year_count"]:
            self.assertIn(field, self.component)
        for label in ["结构化日期事件", "涉及研究", "研究日期", "论文日期", "监管事件"]:
            self.assertIn(label, self.component)

    def test_timeline_cautions_against_inference_from_missing_dates(self):
        self.assertIn("无日期资料未进入时间轴，不代表事件不存在。", self.component)
        self.assertIn("不代表机构研发活跃度或竞争力", self.component)
        self.assertIn("研究、论文与监管日期", self.component)

    def test_static_artifact_matches_frontend_sources(self):
        self.assertEqual(self.index, self.template.replace("/*__COMPONENT__*/", self.component))


if __name__ == "__main__":
    unittest.main()
