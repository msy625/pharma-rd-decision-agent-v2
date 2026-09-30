import re
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


COMPONENT = ROOT / "webapp" / "frontend_src" / "component.js"
TEMPLATE = ROOT / "webapp" / "frontend_src" / "template.html"
STATIC_INDEX = ROOT / "webapp" / "static" / "index.html"


class EvidenceWorkbenchFrontendTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.component = COMPONENT.read_text(encoding="utf-8")
        cls.template = TEMPLATE.read_text(encoding="utf-8")
        cls.index = STATIC_INDEX.read_text(encoding="utf-8")
        cls.today_vals = cls.component[
            cls.component.index("  todayVals(){") : cls.component.index("  // ---- chat ----")
        ]
        cls.today_template = cls.template[
            cls.template.index('<sc-if value="{{ isToday }}">') : cls.template.index('<sc-if value="{{ isChat }}">')
        ]

    def test_01_navigation_labels_real_evidence_workbench(self):
        self.assertIn("研发决策总览", self.component)
        self.assertIn("真实证据总览", self.component)

    def test_02_today_loads_evidence_workbench_api(self):
        loader = re.search(r"loadDashboard\(\)\{(?P<body>.*?)\n  \}", self.component, re.S).group("body")
        self.assertIn("'/api/evidence/workbench'", loader)
        for path in ["/api/bootstrap", "/api/dashboard", "/api/profile"]:
            self.assertNotIn(path, loader)

    def test_03_startup_default_today_does_not_auto_call_old_dashboard(self):
        runtime_block = self.component[
            self.component.index("  loadRuntimeCapabilities(){") : self.component.index("  loadBootstrap(){")
        ]
        self.assertIn("const requestedPage=caps.default_page||'today'", runtime_block)
        self.assertIn(
            "const nextPage=this._isLegacyPage(requestedPage)?(caps.evidence_workbench_available?'today':'evidence'):requestedPage",
            runtime_block,
        )
        self.assertNotIn("this.loadBootstrap()", runtime_block)
        self.assertNotIn("'/api/dashboard'", runtime_block)
        self.assertNotIn("'/api/profile'", runtime_block)
        self.assertNotIn("'/api/bootstrap'", runtime_block)

    def test_04_today_view_does_not_render_old_fixed_workbench_values(self):
        combined = self.today_vals + self.today_template
        for forbidden in ["48", "312", "18642", "1286", "同业营收排名", "营业收入趋势", "风险预警中心", "雷达评分", "模拟预警"]:
            self.assertNotIn(forbidden, combined)

    def test_05_today_displays_data_type_metrics(self):
        for label in ["人工核验来源", "企业主体", "证据链", "临床试验", "论文证据", "监管与公司资料", "待确认关系"]:
            self.assertIn(label, self.today_vals + self.today_template)

    def test_05b_three_primary_metrics_share_the_available_width(self):
        self.assertIn("[data-home-metrics-new]{display:grid;grid-template-columns:repeat(3,minmax(0,1fr))", self.template)
        self.assertIn('hint-placeholder-count="3"', self.today_template)

    def test_06_today_displays_sample_companies_only(self):
        for text in [
            "示范样例总览",
            "today_companies:sampleCompanies",
            ".slice(0,10)",
            "this._companyLabel(c.display_name||c.company_name)",
        ]:
            self.assertIn(text, self.today_vals + self.today_template)

    def test_07_today_displays_current_domains_and_study_statuses(self):
        for text in ["研究领域与研究状态", "展示全部研究领域及研究状态", "today_domains", "today_studyStatuses", "today_toggleDomains", "today_toggleStudyStatuses"]:
            self.assertIn(text, self.today_vals + self.today_template)

    def test_08_quick_links_cover_evidence_timeline_and_grounded_qa(self):
        for label in ["查看来源检索", "查看证据链", "查看研发事件时间轴", "查看机构对比", "进入智能决策 Agent"]:
            self.assertIn(label, self.today_vals + self.today_template)
        self.assertIn("evidenceTab:tab", self.today_vals)
        for tab in ["'sources'", "'chains'", "'companyCompare'"]:
            self.assertIn(tab, self.today_vals)
        self.assertIn("this.openGroundedQa()", self.today_vals)
        self.assertIn("this.go(page)", self.today_vals)
        self.assertNotIn("page:'sources'", self.today_vals)

    def test_08b_company_cards_open_company_evidence_profile(self):
        self.assertIn("companyProfileCompany:companyName", self.today_vals)
        self.assertIn("page:'compare'", self.today_vals)
        self.assertIn("查看企业画像", self.today_template)

    def test_09_loading_empty_and_error_states_exist(self):
        for text in ["today_loading", "today_empty", "today_hasError", "证据工作台加载失败", "正在加载证据工作台", "当前没有可展示"]:
            self.assertIn(text, self.today_vals + self.today_template + self.component)

    def test_10_no_innerhtml_eval_random_mock_or_fixed_score_in_today_path(self):
        combined = self.today_vals + self.today_template
        for forbidden in ["innerHTML", "eval(", "Math.random", "MOCK", "mock", "综合评分", "ranking", "winner"]:
            self.assertNotIn(forbidden, combined)

    def test_11_frontend_build_artifact_matches_source(self):
        expected = self.template.replace("/*__COMPONENT__*/", self.component)
        self.assertEqual(expected, self.index)


if __name__ == "__main__":
    unittest.main()
