import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
COMPONENT = ROOT / "webapp" / "frontend_src" / "component.js"
TEMPLATE = ROOT / "webapp" / "frontend_src" / "template.html"
STATIC_INDEX = ROOT / "webapp" / "static" / "index.html"


class CompanyEvidenceComparisonFrontendStaticTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.component = COMPONENT.read_text(encoding="utf-8")
        cls.template = TEMPLATE.read_text(encoding="utf-8")
        cls.static_index = STATIC_INDEX.read_text(encoding="utf-8")
        start = cls.component.index("// ---- evidence registry page ----")
        end = cls.component.index("  navDef()", start)
        cls.evidence_component = cls.component[start:end]
        t_start = cls.template.index('<sc-if value="{{ isEvidence }}">')
        t_end = cls.template.index('<sc-if value="{{ isDatabase }}">', t_start)
        cls.evidence_template = cls.template[t_start:t_end]
        cls.evidence_all = cls.evidence_component + "\n" + cls.evidence_template

    def test_01_company_comparison_third_tab_exists(self):
        self.assertIn("企业对比", self.evidence_template)
        self.assertIn("ev_isCompanyCompareTab", self.evidence_template)
        self.assertIn("switchEvidenceTab('companyCompare')", self.evidence_component)

    def test_02_existing_tabs_still_exist(self):
        self.assertIn("来源检索", self.evidence_template)
        self.assertIn("证据链", self.evidence_template)
        self.assertIn("ev_isSourceTab", self.evidence_template)
        self.assertIn("ev_isChainTab", self.evidence_template)

    def test_03_company_comparison_api_is_called(self):
        self.assertIn("/api/evidence/company-comparison", self.evidence_component)
        self.assertIn("loadCompanyComparison", self.evidence_component)

    def test_04_metric_rules_api_is_called(self):
        self.assertIn("/api/evidence/company-comparison/metric-rules", self.evidence_component)
        self.assertIn("loadCompanyMetricRules", self.evidence_component)

    def test_05_default_companies_are_correct(self):
        self.assertIn("comparisonCompanyA:'恒瑞医药'", self.component)
        self.assertIn("comparisonCompanyB:'BeOne Medicines'", self.component)
        self.assertIn("恒瑞医药、百济神州/BeOne Medicines", self.evidence_component)

    def test_06_same_company_is_blocked_on_frontend(self):
        self.assertIn("this._companyKey(a)===this._companyKey(b)", self.evidence_component)
        self.assertIn("请选择两个不同企业后再比较", self.evidence_all)

    def test_07_swap_company_control_exists(self):
        self.assertIn("swapCompareCompanies", self.evidence_component)
        self.assertIn("交换企业", self.evidence_template)

    def test_08_top_scope_warning_mentions_current_sample(self):
        self.assertIn("以下结果仅反映当前收录并核验的NSCLC证据样本，不代表企业整体研发实力", self.evidence_all)
        self.assertIn("数据范围：当前31条已核验NSCLC资料", self.evidence_template)
        self.assertIn("不包含疗效排名、成功率预测或投资建议", self.evidence_template)

    def test_09_source_and_verified_counts_are_displayed(self):
        self.assertIn("当前样本来源数", self.evidence_template)
        self.assertIn("已核验来源数", self.evidence_template)
        self.assertIn("cp.source_count", self.evidence_template)
        self.assertIn("cp.verified_source_count", self.evidence_template)

    def test_10_trial_and_regulatory_chain_counts_are_displayed(self):
        self.assertIn("试验级证据链数", self.evidence_template)
        self.assertIn("药物级监管链数", self.evidence_template)
        self.assertIn("cp.trial_chain_count", self.evidence_template)
        self.assertIn("cp.regulatory_chain_count", self.evidence_template)

    def test_11_single_and_multi_source_chain_counts_are_displayed(self):
        self.assertIn("单来源试验链数", self.evidence_template)
        self.assertIn("多来源试验链数", self.evidence_template)
        self.assertIn("cp.single_source_trial_chain_count", self.evidence_template)
        self.assertIn("cp.multi_source_trial_chain_count", self.evidence_template)

    def test_12_version_three_state_distribution_is_displayed(self):
        for text in ["最新版本", "历史版本", "独立资料", "cp.latest", "cp.historical", "cp.independent"]:
            self.assertIn(text, self.evidence_template)

    def test_13_unresolved_count_and_evidence_gaps_are_displayed(self):
        self.assertIn("待确认关系", self.evidence_template)
        self.assertIn("cp.unresolved_link_count", self.evidence_template)
        self.assertIn("需要补充：{{ g.gapText }}", self.evidence_template)

    def test_14_source_type_distribution_is_displayed(self):
        self.assertIn("来源类型构成", self.evidence_template)
        self.assertIn("source_type_distribution", self.evidence_component)
        self.assertIn("cp.sourceTypes", self.evidence_template)
        self.assertIn("k&&k!=='undefined'&&k!=='null'", self.evidence_component)

    def test_15_metric_rules_show_correct_and_prohibited_interpretations(self):
        self.assertIn("如何理解这些数字", self.evidence_template)
        self.assertIn("正确解释：{{ mr.correct }}", self.evidence_template)
        self.assertIn("禁止解释：{{ mr.prohibited }}", self.evidence_template)

    def test_16_no_winner_or_score_language_is_introduced(self):
        for word in ["领先", "优胜方", "冠军", "综合评分", "胜负色", "排名箭头"]:
            self.assertNotIn(word, self.evidence_all)

    def test_17_view_chain_switches_tab_and_loads_chain_detail(self):
        self.assertIn("openComparisonChain(chainId)", self.evidence_component)
        self.assertIn("evidenceTab:'chains'", self.evidence_component)
        self.assertIn("this.loadChainDetail(cid)", self.evidence_component)
        self.assertIn("查看证据链", self.evidence_template)

    def test_18_chain_id_is_encoded_by_existing_chain_detail_loader(self):
        self.assertIn("encodeURIComponent(cid)", self.evidence_component)
        self.assertIn("'/api/evidence/chains/'+encodeURIComponent(cid)", self.evidence_component)

    def test_19_current_data_insufficient_region_exists(self):
        self.assertIn("当前数据不足", self.evidence_template)
        for text in ["临床阶段", "研究人群", "治疗场景", "靶点", "机制", "药物类型", "疗效与安全性"]:
            self.assertIn(text, self.evidence_all)

    def test_20_does_not_call_model_or_chroma_routes(self):
        for word in ["/api/chat", "/api/workflow", "/api/advanced", "Chroma", "向量模型", "大模型"]:
            self.assertNotIn(word, self.evidence_component)

    def test_21_existing_evidence_tabs_and_nav_remain(self):
        self.assertIn("label:'研发证据中心'", self.component)
        self.assertIn("label:'企业证据画像'", self.component)
        self.assertIn("查询类型", self.evidence_template)
        self.assertIn("证据链列表", self.evidence_template)

    def test_22_static_index_is_synced_with_source(self):
        expected = self.template.replace("/*__COMPONENT__*/", self.component)
        self.assertEqual(self.static_index, expected)
        self.assertIn("/api/evidence/company-comparison", self.static_index)
        self.assertIn("企业对比", self.static_index)

    def test_23_no_unsafe_dom_apis(self):
        for word in ["innerHTML", "eval(", "document.write"]:
            self.assertNotIn(word, self.evidence_all)


if __name__ == "__main__":
    unittest.main()
