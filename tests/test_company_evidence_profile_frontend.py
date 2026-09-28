import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
COMPONENT = ROOT / "webapp" / "frontend_src" / "component.js"
TEMPLATE = ROOT / "webapp" / "frontend_src" / "template.html"
STATIC_INDEX = ROOT / "webapp" / "static" / "index.html"


class InstitutionProfileFrontendTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.component = COMPONENT.read_text(encoding="utf-8")
        cls.template = TEMPLATE.read_text(encoding="utf-8")
        cls.index = STATIC_INDEX.read_text(encoding="utf-8")

    def test_institution_profile_uses_normalized_institution_routes(self):
        self.assertIn("/api/evidence/institution-profile-institutions", self.component)
        self.assertIn("/api/evidence/institution-profile/", self.component)
        self.assertIn("机构研发画像", self.component)
        self.assertIn("institution-profile", self.index)
        for retired_path in ["/api/evidence/company-profile-companies", "/api/evidence/company-profile/"]:
            self.assertNotIn(retired_path, self.component)

    def test_profile_shows_organization_coverage_and_gaps(self):
        for term in ["机构数据覆盖", "申办研究数", "药物实体", "关系缺口", "尚不足以形成完整画像"]:
            self.assertIn(term, self.component + self.template)
        self.assertIn("profile_groups", self.component)
        self.assertIn("profile_limitations", self.component)

    def test_profile_navigation_links_to_current_evidence_features(self):
        for path in ["evidenceTab:'sources'", "evidenceTab:'companyCompare'", "page:'groundedQa'"]:
            self.assertIn(path, self.component)
        self.assertIn("机构对比", self.template)
        self.assertIn("智能决策 Agent", self.template)

    def test_static_artifact_matches_frontend_sources(self):
        self.assertEqual(self.index, self.template.replace("/*__COMPONENT__*/", self.component))


if __name__ == "__main__":
    unittest.main()
