import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
COMPONENT = ROOT / "webapp" / "frontend_src" / "component.js"
TEMPLATE = ROOT / "webapp" / "frontend_src" / "template.html"
STATIC_INDEX = ROOT / "webapp" / "static" / "index.html"


class CompanyEvidenceProfileFrontendTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.component = COMPONENT.read_text(encoding="utf-8")
        cls.template = TEMPLATE.read_text(encoding="utf-8")
        cls.index = STATIC_INDEX.read_text(encoding="utf-8")
        cls.loader = cls.component[
            cls.component.index("  loadCompanyEvidenceProfilePage(){") : cls.component.index("  loadProfile(){")
        ]
        cls.values = cls.component[
            cls.component.index("  companyProfileVals(){") : cls.component.index("  // ---- chat ----")
        ]
        cls.view = cls.template[
            cls.template.index('<sc-if value="{{ isCompare }}">') : cls.template.index('<sc-if value="{{ isWhitebox }}">')
        ]

    def test_01_main_navigation_is_company_evidence_profile(self):
        self.assertIn("label:'企业证据画像'", self.component)
        self.assertIn("compare:['企业证据画像','单企业核验证据']", self.component)

    def test_02_profile_only_loads_new_profile_endpoints(self):
        self.assertIn("'/api/evidence/company-profile-companies'", self.loader)
        self.assertIn("'/api/evidence/company-profile/'+encodeURIComponent(name)", self.loader)
        for path in ["'/api/profile'", "'/api/compare'", "'/api/dashboard'"]:
            self.assertNotIn(path, self.loader)

    def test_03_default_and_switchable_companies(self):
        self.assertIn("companyProfileCompany:'恒瑞医药'", self.component)
        self.assertIn("百济神州 / BeOne Medicines", self.values)
        self.assertIn("profile_onCompany", self.values + self.view)

    def test_04_scope_warning_is_prominent(self):
        warning = "本画像仅反映当前收录并核验的NSCLC证据样本，不代表企业整体研发实力或完整研发管线。"
        self.assertIn(warning, self.values)
        self.assertIn("profile_scopeWarning", self.view)

    def test_05_core_metrics_and_distributions_are_rendered(self):
        for label in ["当前来源", "已核验来源", "试验级证据链", "药物级监管链", "多来源试验链", "单来源试验链", "论文来源", "试验登记来源", "最新资料", "历史版本", "独立资料", "待确认关系", "来源类型构成", "研究状态构成"]:
            self.assertIn(label, self.values + self.view)

    def test_06_trial_chain_cards_and_jump(self):
        for text in ["chain_id", "trial_id", "来源数量", "版本构成", "研究状态", "查看证据链"]:
            self.assertIn(text, self.values + self.view)
        jump = self.component[
            self.component.index("  openProfileChain(chainId){") : self.component.index("  openProfileSources(){")
        ]
        self.assertIn("page:'evidence'", jump)
        self.assertIn("evidenceTab:'chains'", jump)
        self.assertIn("this.loadChainDetail(cid)", jump)

    def test_07_regulatory_language_is_conservative(self):
        for text in ["正式授权", "CHMP积极意见，非最终批准", "不计入临床试验数量", "关联试验背景"]:
            self.assertIn(text, self.values + self.view)
        self.assertIn("当前样本未收录独立监管链；该表述不代表企业没有监管进展。", self.view)

    def test_08_quick_entries_reuse_existing_evidence_tabs(self):
        for label in ["查看全部来源", "打开企业对比", "进入循证问答"]:
            self.assertIn(label, self.view)
        for tab in ["evidenceTab:'sources'", "evidenceTab:'companyCompare'"]:
            self.assertIn(tab, self.loader)
        self.assertIn("this.openGroundedQa()", self.loader)
        self.assertIn("page:'groundedQa'", self.loader)

    def test_09_metadata_limitations_and_empty_states(self):
        for text in ["数据版本", "核验日期", "生成时间", "限制说明", "正在加载企业证据画像", "当前数据不足", "重新加载"]:
            self.assertIn(text, self.view)

    def test_10_new_profile_path_has_no_old_scoring_language(self):
        combined = self.loader + self.values + self.view
        for forbidden in ["雷达评分", "winner", "领先", "营业收入", "归母净利润", "风险分", "Math.random", "innerHTML", "eval(", "MOCK"]:
            self.assertNotIn(forbidden, combined)

    def test_11_old_profile_is_not_in_current_render_path(self):
        self.assertIn('<sc-if value="{{ isLegacyCompare }}">', self.template)
        self.assertNotIn("isLegacyCompare:", self.component)
        load_page = re.search(r"loadPage\(\)\{(?P<body>.*?)\n  \}", self.component, re.S).group("body")
        self.assertIn("p==='compare') this.loadCompanyEvidenceProfilePage()", load_page)
        self.assertNotIn("this.loadProfile(); this.loadCompare();", load_page)
        render_values = self.component[
            self.component.index("  renderVals(){") : self.component.index("\n  }\n}", self.component.index("  renderVals(){"))
        ]
        self.assertNotIn("this.compareVals()", render_values)

    def test_12_build_artifact_matches_source(self):
        self.assertEqual(self.template.replace("/*__COMPONENT__*/", self.component), self.index)


if __name__ == "__main__":
    unittest.main()
