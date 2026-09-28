import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
COMPONENT = ROOT / "webapp" / "frontend_src" / "component.js"
TEMPLATE = ROOT / "webapp" / "frontend_src" / "template.html"
STATIC_INDEX = ROOT / "webapp" / "static" / "index.html"


class NormalizedEvidenceBriefFrontendTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.component = COMPONENT.read_text(encoding="utf-8")
        cls.template = TEMPLATE.read_text(encoding="utf-8")
        cls.index = STATIC_INDEX.read_text(encoding="utf-8")

    def test_brief_page_loads_institution_and_disease_direction_apis(self):
        self.assertIn("/api/evidence/institution-brief/", self.component)
        self.assertIn("/api/evidence/direction-brief/", self.component)
        self.assertIn("/api/evidence/direction-briefs", self.component)
        self.assertNotIn("/api/evidence/decision-brief/", self.component)
        self.assertIn("机构研发画像简报", self.component)
        self.assertIn("疾病方向证据简报", self.component)

    def test_brief_renders_structured_sources_relations_and_limitations(self):
        for name in ["brief_metrics", "brief_events", "brief_regulatory", "brief_gaps", "brief_limitations", "brief_citations"]:
            self.assertIn(name, self.component)
        for label in ["证据缺口", "风险与限制", "引用来源及证据链", "打开原始来源"]:
            self.assertIn(label, self.template)

    def test_brief_has_loading_error_empty_and_print_states(self):
        for state in ["brief_loading", "brief_hasError", "brief_empty", "brief_hasData"]:
            self.assertIn(state, self.template)
        self.assertIn("@media print", self.template)

    def test_static_artifact_matches_frontend_sources(self):
        self.assertEqual(self.index, self.template.replace("/*__COMPONENT__*/", self.component))


if __name__ == "__main__":
    unittest.main()
