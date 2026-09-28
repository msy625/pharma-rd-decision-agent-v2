"""Frontend contract for the normalized-data default scope."""

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
COMPONENT = (ROOT / "webapp" / "frontend_src" / "component.js").read_text(encoding="utf-8")
TEMPLATE = (ROOT / "webapp" / "frontend_src" / "template.html").read_text(encoding="utf-8")
INDEX = (ROOT / "webapp" / "static" / "index.html").read_text(encoding="utf-8")


class NormalizedScopeFrontendTest(unittest.TestCase):
    def test_normalized_scope_is_default_and_legacy_parameter_is_true(self):
        self.assertIn("includeHarvested:true", COMPONENT)
        self.assertIn("_ihParams(){ return {include_harvested:true}; }", COMPONENT)

    def test_switch_is_not_shown_for_a_dataset_that_is_already_default(self):
        self.assertIn("ih_show:false", COMPONENT)

    def test_scope_note_explains_the_eligibility_gate(self):
        self.assertIn("具有有效来源链接、已声明核验状态且至少一条已确认关系", COMPONENT)
        self.assertIn("缺少明确关系的资料不会进入网站展示", COMPONENT)

    def test_source_center_uses_normalized_language(self):
        self.assertIn("规范化研发证据", COMPONENT)
        self.assertIn("条可展示资料", TEMPLATE)
        self.assertIn("条规范化资料", TEMPLATE)

    def test_normalized_browser_calls_the_direct_normalized_api(self):
        self.assertIn("/api/normalized/catalog", COMPONENT)
        self.assertIn("/api/normalized/sources", COMPONENT)
        self.assertIn("规范化数据浏览", TEMPLATE)
        self.assertIn("明确事实", TEMPLATE)

    def test_built_page_matches_the_sources(self):
        self.assertEqual(TEMPLATE.replace("/*__COMPONENT__*/", COMPONENT), INDEX)


if __name__ == "__main__":
    unittest.main()
