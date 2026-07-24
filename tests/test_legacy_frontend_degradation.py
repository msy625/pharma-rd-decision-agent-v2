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

    def test_02_light_runtime_defaults_to_real_workbench_and_skips_old_requests(self):
        for snippet in [
            "const requestedPage=caps.default_page||'today'",
            "const nextPage=this._isLegacyPage(requestedPage)?(caps.evidence_workbench_available?'today':'evidence'):requestedPage",
            "if(this._isLegacyPage(p) && !this._legacyAvailable()) return",
        ]:
            self.assertIn(snippet, self.component)
        runtime = self.component[self.component.index("  loadRuntimeCapabilities(){") : self.component.index("  loadBootstrap(){")]
        self.assertNotIn("this.loadBootstrap()", runtime)
        dashboard = self.component[self.component.index("  loadDashboard()") : self.component.index("  loadProfile()")]
        self.assertIn("'/api/evidence/workbench'", dashboard)
        self.assertNotIn("'/api/dashboard'", dashboard)
        for loader in ["loadProfile()", "loadCompare()", "loadDbCatalog()"]:
            start = self.component.index("  " + loader)
            body = self.component[start:start + 220]
            self.assertIn("!this._legacyAvailable()", body)
        timeline_start = self.component.index("  loadTimeline(){")
        timeline_body = self.component[timeline_start:self.component.index("  loadWhitebox(){", timeline_start)]
        self.assertNotIn("!this._legacyAvailable()", timeline_body)
        self.assertIn("'/api/evidence/timeline'", timeline_body)
        self.assertNotIn("'/api/timeline'", timeline_body)

    def test_03_legacy_notice_state_is_not_rendered_in_competition_shell(self):
        self.assertIn("legacyNotice", self.component)
        for text in ["legacyNotice", "legacyLabel", "hasLegacyNotice", "旧数据未配置"]:
            self.assertNotIn(text, self.template)

    def test_04_fixed_old_business_stats_are_not_rendered_in_real_workbench(self):
        today_block = self.component[self.component.index("  todayVals(){") : self.component.index("  // ---- chat ----")]
        self.assertIn("today_metrics", today_block)
        self.assertIn("today_scopeWarning", today_block)
        for forbidden in ["48", "312", "18642", "1286", "today_ranking", "today_alerts", "today_trendLabels"]:
            self.assertNotIn(forbidden, today_block)

    def test_05_no_infinite_retry_loop_for_failed_legacy_503(self):
        start = self.component.index("  loadRuntimeCapabilities(){")
        runtime_block = self.component[start:self.component.index("  loadBootstrap(){", start)]
        self.assertNotIn("setInterval", runtime_block)
        self.assertNotIn("retry", runtime_block.lower())
        self.assertEqual(self.component.count("this.loadBootstrap()"), 1)

    def test_06_competition_navigation_and_remaining_legacy_api_code_are_retained(self):
        nav = self.component[self.component.index("  navDef(){") : self.component.index("  navItem(it){")]
        for text in ["研发决策总览", "企业证据画像", "研发事件时间轴", "研发证据中心", "循证问答"]:
            self.assertIn(text, nav)
        for text in ["智能问答", "自动化研报", "白盒溯源", "数据库浏览", "高级分析"]:
            self.assertNotIn(text, nav)
        self.assertNotIn("label:'公司画像 · 对比'", self.component)
        self.assertIn('<sc-if value="{{ isLegacyCompare }}">', self.template)
        for path in ["/api/bootstrap", "/api/profile", "/api/compare"]:
            self.assertIn(path, self.component)
        self.assertNotIn("'/api/timeline'", self.component)
        main = Path(ROOT / "webapp" / "main.py").read_text(encoding="utf-8")
        self.assertIn("@app.get(\"/api/dashboard\")", main)
        self.assertIn("@app.get(\"/api/timeline\")", main)
        self.assertIn("@app.get(\"/api/evidence/timeline\")", main)

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

    def test_11_evidence_three_tabs_and_top_level_grounded_qa_exist(self):
        for label in ["来源检索", "证据链", "企业对比", "进入循证问答"]:
            self.assertIn(label, self.template)
            self.assertIn(label, self.index)
        self.assertIn("label:'循证问答'", self.component)

    def test_12_frontend_build_artifact_matches_source(self):
        expected = self.template.replace("/*__COMPONENT__*/", self.component)
        self.assertEqual(expected, self.index)


if __name__ == "__main__":
    unittest.main()
