import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
COMPONENT = ROOT / "webapp" / "frontend_src" / "component.js"
TEMPLATE = ROOT / "webapp" / "frontend_src" / "template.html"
STATIC_INDEX = ROOT / "webapp" / "static" / "index.html"
MAIN = ROOT / "webapp" / "main.py"


class CompetitionNavigationFrontendTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.component = COMPONENT.read_text(encoding="utf-8")
        cls.template = TEMPLATE.read_text(encoding="utf-8")
        cls.index = STATIC_INDEX.read_text(encoding="utf-8")
        cls.main = MAIN.read_text(encoding="utf-8")
        cls.nav_block = cls.component[
            cls.component.index("  navDef(){") : cls.component.index("  navItem(it){")
        ]
        cls.mount_block = cls.component[
            cls.component.index("componentDidMount()") : cls.component.index("  // ===================== 多会话")
        ]
        cls.runtime_block = cls.component[
            cls.component.index("  loadRuntimeCapabilities(){") : cls.component.index("  loadBootstrap(){")
        ]
        cls.render_block = cls.component[
            cls.component.index("  renderVals(){") : cls.component.rindex("\n}")
        ]
        cls.nav_template = cls.template[
            cls.template.index('<nav data-competition-nav=""') : cls.template.index("</nav>", cls.template.index('<nav data-competition-nav=""'))
        ]
        cls.evidence_header = cls.template[
            cls.template.index('<sc-if value="{{ isEvidenceCenter }}">') : cls.template.index('<sc-if value="{{ ev_isSourceTab }}">')
        ]

    def test_01_navigation_has_exactly_five_entries_in_order(self):
        entries = re.findall(r"\{key:'([^']+)',label:'([^']+)'", self.nav_block)
        self.assertEqual(
            entries,
            [
                ("today", "研发决策总览"),
                ("compare", "企业证据画像"),
                ("timeline", "研发事件时间轴"),
                ("evidence", "研发证据中心"),
                ("groundedQa", "循证问答"),
            ],
        )

    def test_02_competition_navigation_has_no_legacy_groups_or_entries(self):
        for forbidden in ["工作流", "数据与分析", "智能问答", "自动化研报", "白盒溯源", "数据库浏览", "高级分析"]:
            self.assertNotIn(forbidden, self.nav_template)
        for forbidden in ["disabled", "legacyLabel", "旧数据未配置"]:
            self.assertNotIn(forbidden, self.nav_template)

    def test_03_old_global_controls_and_notice_are_not_rendered(self):
        for forbidden in [
            "hasLegacyNotice",
            "legacyNotice",
            "global-company-select",
            "global-year-select",
            "global-top-k-range",
            "排名范围",
            "向量 Top K",
            "toggleMode",
            "togglePresent",
            "演示动线",
        ]:
            self.assertNotIn(forbidden, self.template)

    def test_04_brand_html_title_and_fastapi_title_are_consistent(self):
        for expected in ["药研制策", "可信医药研发证据智能分析", "药研制策｜可信医药研发证据智能分析"]:
            self.assertIn(expected, self.template)
            self.assertIn(expected, self.index)
        self.assertIn('FastAPI(title="药研制策｜可信医药研发证据智能分析")', self.main)
        for old in ["医策智脑", "DeepInsight · 决策支持"]:
            self.assertNotIn(old, self.template)

    def test_05_grounded_qa_is_a_real_top_level_page_using_existing_state(self):
        self.assertIn("else if(p==='groundedQa') this.loadGroundedCapabilities()", self.component)
        self.assertIn("isGroundedQaPage:s.page==='groundedQa'", self.component)
        self.assertIn("ev_isGroundedTab:s.page==='groundedQa'", self.component)
        self.assertIn("submitGroundedQA()", self.component)
        self.assertIn("data-grounded-qa", self.template)

    def test_06_grounded_qa_only_uses_new_evidence_endpoints(self):
        evidence_block = self.component[
            self.component.index("  // ---- evidence registry page ----") : self.component.index("  navDef()")
        ]
        self.assertIn("/api/evidence/grounded-qa/capabilities", evidence_block)
        self.assertIn("fetch('/api/evidence/grounded-qa'", evidence_block)
        self.assertNotIn("/api/chat", evidence_block)

    def test_07_capability_failure_keeps_local_mode_available(self):
        for expected in [
            "local_mode_available:true",
            "llm_mode_available:false",
            "groundedMode:'local'",
            "已保留本地循证摘要模式",
        ]:
            self.assertIn(expected, self.component)

    def test_08_evidence_center_has_three_internal_tabs_and_top_level_qa_entry(self):
        for expected in ["来源检索", "证据链", "企业对比", "进入循证问答"]:
            self.assertIn(expected, self.evidence_header)
        self.assertNotIn("ev_tabGrounded", self.component)
        self.assertNotIn("switchEvidenceTab('groundedQa')", self.component)
        self.assertIn("ev_openGrounded:()=>this.openGroundedQa()", self.component)

    def test_09_startup_does_not_initialize_legacy_chat_or_bootstrap(self):
        self.assertNotIn("_initConvs", self.mount_block)
        self.assertNotIn("loadBootstrap", self.runtime_block)
        self.assertNotIn("/api/bootstrap", self.runtime_block)

    def test_10_competition_render_does_not_eagerly_build_legacy_views(self):
        self.assertIn("const competition=Object.assign", self.render_block)
        self.assertIn("if(!this._isLegacyPage(this.state.page)) return competition", self.render_block)
        self.assertIn("research:()=>this.researchVals()", self.render_block)
        self.assertNotRegex(self.render_block, r"competition=.*researchVals")

    def test_11_closed_loop_jumps_pass_only_local_context(self):
        for expected in [
            "companyProfileCompany:companyName",
            "page:'compare'",
            "page==='groundedQa'?this.openGroundedQa():this.go(page)",
            "page:'evidence',evidenceTab:'chains'",
            "page:'evidence',evidenceTab:'sources'",
            "onClick:()=>this.openGroundedSource(sourceId)",
            "查看企业画像",
            "查看研发事件时间轴",
            "查看来源详情",
        ]:
            self.assertIn(expected, self.component + self.template)

    def test_12_legacy_code_and_api_routes_remain_but_are_not_in_navigation(self):
        for expected in ["_legacyPages()", "chatVals()", "researchVals()", "whiteboxVals()", "databaseVals()", "advancedVals()"]:
            self.assertIn(expected, self.component)
        for route in ['@app.get("/api/profile")', '@app.get("/api/compare")', '@app.get("/api/timeline")', '@app.post("/api/chat")']:
            self.assertIn(route, self.main)
        for key in ["chat", "research", "whitebox", "database", "advanced"]:
            self.assertNotRegex(self.nav_block, rf"key:'{key}'")

    def test_13_responsive_navigation_and_narrow_screen_rules_remain(self):
        for expected in ["@media(max-width:1080px)", "@media(max-width:640px)", "data-sidebar", "data-hamburger"]:
            self.assertIn(expected, self.template)

    def test_14_static_index_matches_frontend_sources(self):
        self.assertEqual(self.template.replace("/*__COMPONENT__*/", self.component), self.index)


if __name__ == "__main__":
    unittest.main()
