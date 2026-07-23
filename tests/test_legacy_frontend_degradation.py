import re
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


from tests.test_deployment_health import _ASGIClient
from webapp import main as webapp_main


COMPONENT = ROOT / "webapp" / "frontend_src" / "component.js"
TEMPLATE = ROOT / "webapp" / "frontend_src" / "template.html"
STATIC_INDEX = ROOT / "webapp" / "static" / "index.html"
RUNTIME = ROOT / "webapp" / "static" / "dc-runtime.js"
FAVICON = ROOT / "webapp" / "static" / "favicon.svg"


class LegacyFrontendDegradationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.component = COMPONENT.read_text(encoding="utf-8")
        cls.template = TEMPLATE.read_text(encoding="utf-8")
        cls.index = STATIC_INDEX.read_text(encoding="utf-8")
        cls.runtime = RUNTIME.read_text(encoding="utf-8")
        cls.client = _ASGIClient(webapp_main.app)

    def test_01_startup_calls_runtime_capabilities_before_old_bootstrap(self):
        mount = re.search(r"componentDidMount\(\)\{([^}]+)\}", self.component).group(1)
        self.assertIn("this.loadRuntimeCapabilities()", mount)
        self.assertNotIn("this.loadBootstrap()", mount)
        self.assertNotIn("this.loadPage()", mount)
        self.assertIn("'/api/runtime-capabilities'", self.component)

    def test_02_light_runtime_defaults_to_evidence_and_skips_old_requests(self):
        for snippet in [
            "const legacy=!!caps.legacy_features_available",
            "const nextPage=(legacy||!this._isLegacyPage(page))?page:'evidence'",
            "if(legacy) this.loadBootstrap()",
            "if(this._isLegacyPage(p) && !this._legacyAvailable()) return",
        ]:
            self.assertIn(snippet, self.component)
        for loader in ["loadDashboard()", "loadProfile()", "loadCompare()", "loadTimeline()", "loadDbCatalog()"]:
            start = self.component.index("  " + loader)
            body = self.component[start:start + 220]
            self.assertIn("!this._legacyAvailable()", body)

    def test_03_unavailable_old_navigation_shows_friendly_prompt(self):
        for text in ["旧数据未配置", "legacyNotice", "legacyLabel", "hasLegacyNotice"]:
            self.assertIn(text, self.component + self.template)

    def test_04_fixed_old_business_stats_are_not_rendered_in_light_mode(self):
        light_branch = self.component[self.component.index("if(!this._legacyAvailable()){", self.component.index("todayVals()")):]
        light_branch = light_branch[:light_branch.index("const D=this.D")]
        self.assertIn("today_kpis:[]", light_branch)
        self.assertIn("today_ranking:[]", light_branch)
        self.assertIn("today_alerts:[]", light_branch)
        self.assertNotIn("48", light_branch)
        self.assertNotIn("312", light_branch)
        self.assertNotIn("18642", light_branch)
        self.assertNotIn("1286", light_branch)

    def test_05_no_infinite_retry_loop_for_failed_legacy_503(self):
        runtime_block = self.component[self.component.index("loadRuntimeCapabilities()"):]
        self.assertNotIn("setInterval", runtime_block)
        self.assertNotIn("retry", runtime_block.lower())
        self.assertEqual(self.component.count("this.loadBootstrap()"), 1)

    def test_06_full_legacy_navigation_and_api_code_is_retained(self):
        for text in ["工作台", "智能问答", "公司画像 · 对比", "自动化研报", "白盒溯源", "数据库浏览", "事件时间轴", "高级分析"]:
            self.assertIn(text, self.component)
        for path in ["/api/bootstrap", "/api/profile", "/api/dashboard", "/api/compare", "/api/timeline"]:
            self.assertIn(path, self.component)

    def test_07_svg_templates_do_not_pass_raw_bindings_to_sensitive_attrs(self):
        combined = self.template + "\n" + self.component
        self.assertNotRegex(combined, r"<path[^>]*\sd=\"\{\{")
        self.assertNotRegex(combined, r"<polyline[^>]*\spoints=\"\{\{")
        self.assertNotRegex(combined, r"<line[^>]*\sx[12]=\"\{\{")
        self.assertNotRegex(combined, r"<line[^>]*\sy[12]=\"\{\{")
        self.assertIn("res_trendSvg", self.template)
        self.assertIn("adv_edgeSvg", self.template)
        self.assertIn("createElement('polyline'", self.component)
        self.assertIn("createElement('line'", self.component)

    def test_08_no_console_error_masking(self):
        self.assertNotIn("console.error", self.component)
        self.assertNotIn("console.error", self.template)

    def test_09_favicon_file_and_routes_are_available(self):
        self.assertTrue(FAVICON.exists())
        self.assertIn('/static/favicon.svg', self.template)
        response = self.client.get("/favicon.ico")
        self.assertEqual(response.status_code, 200, response.text[:100])
        self.assertIn("image/svg+xml", response.headers.get("content-type", ""))
        self.assertIn("<svg", response.text)

    def test_10_local_react_reactdom_babel_are_still_referenced(self):
        for expected in [
            "/static/vendor/react/react.production.min-18.3.1.js",
            "/static/vendor/react-dom/react-dom.production.min-18.3.1.js",
            "/static/vendor/babel/babel.min-7.26.4.js",
        ]:
            self.assertIn(expected, self.runtime)

    def test_11_evidence_four_tabs_still_exist(self):
        for label in ["来源检索", "证据链", "企业对比", "循证问答"]:
            self.assertIn(label, self.template)
            self.assertIn(label, self.index)

    def test_12_frontend_build_artifact_matches_source(self):
        expected = self.template.replace("/*__COMPONENT__*/", self.component)
        self.assertEqual(expected, self.index)


if __name__ == "__main__":
    unittest.main()
