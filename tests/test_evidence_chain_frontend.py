import json
import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
COMPONENT = ROOT / "webapp" / "frontend_src" / "component.js"
TEMPLATE = ROOT / "webapp" / "frontend_src" / "template.html"
STATIC_INDEX = ROOT / "webapp" / "static" / "index.html"
CHAIN_CONFIG = ROOT / "config" / "evidence_chains.json"


class EvidenceChainFrontendStaticTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.component = COMPONENT.read_text(encoding="utf-8")
        cls.template = TEMPLATE.read_text(encoding="utf-8")
        cls.static_index = STATIC_INDEX.read_text(encoding="utf-8")
        cls.chain_config = json.loads(CHAIN_CONFIG.read_text(encoding="utf-8"))
        start = cls.component.index("// ---- evidence registry page ----")
        end = cls.component.index("  navDef()", start)
        cls.evidence_component = cls.component[start:end]
        t_start = cls.template.index('<sc-if value="{{ isEvidence }}">')
        t_end = cls.template.index('<sc-if value="{{ isDatabase }}">', t_start)
        cls.evidence_template = cls.template[t_start:t_end]
        cls.evidence_all = cls.evidence_component + "\n" + cls.evidence_template

    def test_01_source_search_tab_still_exists(self):
        self.assertIn("来源检索", self.evidence_template)
        self.assertIn("ev_isSourceTab", self.evidence_template)
        self.assertIn("/api/evidence/search", self.evidence_component)

    def test_02_evidence_chain_tab_exists(self):
        self.assertIn("证据链", self.evidence_template)
        self.assertIn("ev_isChainTab", self.evidence_template)
        self.assertIn("switchEvidenceTab('chains')", self.evidence_component)

    def test_03_chain_summary_api_is_called(self):
        self.assertIn("/api/evidence/chain-summary", self.evidence_component)
        self.assertIn("loadChainSummary", self.evidence_component)

    def test_04_chains_api_is_called(self):
        self.assertIn("/api/evidence/chains", self.evidence_component)
        self.assertIn("loadChains", self.evidence_component)

    def test_05_chain_id_uses_encode_uri_component(self):
        self.assertIn("encodeURIComponent(cid)", self.evidence_component)
        self.assertIn("'/api/evidence/chains/'+encodeURIComponent(cid)", self.evidence_component)

    def test_06_company_and_type_filters_exist(self):
        for text in ["企业", "全部", "类型", "试验级", "药物级监管"]:
            self.assertIn(text, self.evidence_template)
        self.assertIn("chain_companyOptions", self.evidence_component)
        self.assertIn('<sc-for list="{{ chain_companyOptions }}" as="co">', self.evidence_template)
        self.assertIn("chain_onCompany", self.evidence_component)
        self.assertIn("chain_onType", self.evidence_component)

    def test_07_summary_numbers_can_be_displayed(self):
        for key in ["chain_total", "chain_trial", "chain_regulatory", "chain_unresolvedCount"]:
            self.assertIn(key, self.evidence_template)
        for label in ["总证据链", "试验级证据链", "药物级监管链", "待确认关系数量"]:
            self.assertIn(label, self.evidence_template)

    def test_08_chain_cards_include_source_count(self):
        self.assertIn("source_count", self.evidence_component)
        self.assertIn("资料数：{{ c.source_count }}", self.evidence_template)

    def test_09_detail_shows_latest_historical_independent_groups(self):
        for text in ["最新版本", "历史版本", "独立资料", "latest_items", "historical_items", "independent_items"]:
            self.assertIn(text, self.evidence_component)
        for section in ["临床试验登记", "中期论文", "最终论文", "独立资料"]:
            self.assertIn(section, self.evidence_all)

    def test_10_regulatory_authorisation_role_label_is_clear(self):
        self.assertIn("regulatory_authorisation:'EMA正式授权信息'", self.evidence_component)

    def test_11_regulatory_opinion_role_label_is_clear(self):
        self.assertIn("regulatory_opinion:'CHMP积极意见'", self.evidence_component)

    def test_12_b015_authorisation_status_can_render_as_formal_authorisation(self):
        chain = next(item for item in self.chain_config["chains"] if item["chain_id"] == "regulatory:tevimbra-eu-nsclc")
        b015 = next(item for item in chain["source_ids"] if item["source_id"] == "B015")
        self.assertEqual(b015["role"], "regulatory_authorisation")
        self.assertIn("授权状态：{{ it.authorisationDisplay }}", self.evidence_template)

    def test_13_b016_authorisation_status_can_render_as_positive_opinion_not_final_approval(self):
        chain = next(item for item in self.chain_config["chains"] if item["chain_id"] == "regulatory:tevimbra-eu-nsclc")
        b016 = next(item for item in chain["source_ids"] if item["source_id"] == "B016")
        self.assertEqual(b016["role"], "regulatory_opinion")
        self.assertIn("积极意见，非最终批准", self.evidence_component)
        self.assertNotIn("regulatory_opinion:'EMA正式授权信息'", self.evidence_component)

    def test_14_regulatory_primary_tag_is_regulatory_not_independent(self):
        self.assertIn("return {kind:'regulatory', label:'监管资料'", self.evidence_component)
        self.assertIn("if(this._isRegulatoryEvidence(item))", self.evidence_component)
        regulatory_branch = self.evidence_component[
            self.evidence_component.index("if(this._isRegulatoryEvidence(item))"):
            self.evidence_component.index("const s=String((item&&item.version_status)||'');")
        ]
        self.assertNotIn("独立资料", regulatory_branch)

    def test_15_not_applicable_study_status_is_hidden(self):
        self.assertIn("_hasStudyStatus(value)", self.evidence_component)
        self.assertIn("'不适用'", self.evidence_component)
        self.assertIn("it.hasStudyStatus", self.evidence_template)

    def test_16_regulatory_logic_is_not_hardcoded_by_source_id(self):
        start = self.evidence_component.index("_roleLabel(role)")
        end = self.evidence_component.index("_sourceTitle(item)", start)
        regulatory_logic = self.evidence_component[start:end]
        self.assertNotIn("B015", regulatory_logic)
        self.assertNotIn("B016", regulatory_logic)
        self.assertIn("role==='regulatory_opinion'", self.evidence_component)
        self.assertIn("role==='regulatory_authorisation'", self.evidence_component)

    def test_17_non_regulatory_evidence_still_uses_version_labels(self):
        self.assertIn("return this._evidenceVersion(true)", self.evidence_component)
        self.assertIn("return this._evidenceVersion(false)", self.evidence_component)
        self.assertIn("return this._evidenceVersion('')", self.evidence_component)

    def test_18_rationale_315_trial_sources_can_be_rendered(self):
        chain = next(item for item in self.chain_config["chains"] if item["chain_id"] == "trial:NCT04379635")
        self.assertEqual({item["source_id"] for item in chain["source_ids"]}, {"B011", "B012", "B013"})
        self.assertIn("{{ it.source_id }}", self.evidence_template)
        self.assertIn("试验证据", self.evidence_template)

    def test_19_b016_is_related_regulatory_background(self):
        chain = next(item for item in self.chain_config["chains"] if item["chain_id"] == "trial:NCT04379635")
        self.assertEqual(chain["related_regulatory_source_ids"], ["B016"])
        self.assertIn("related_regulatory_items", self.evidence_component)
        self.assertIn("关联监管背景", self.evidence_template)

    def test_20_background_not_counted_copy_exists(self):
        self.assertIn("关联监管背景不计入该试验的证据数量", self.evidence_template)

    def test_21_unresolved_api_and_region_exist(self):
        self.assertIn("/api/evidence/unresolved-links", self.evidence_component)
        self.assertIn("待确认关系", self.evidence_template)
        self.assertIn("不能关联的原因", self.evidence_template)
        self.assertIn("需要补充", self.evidence_template)

    def test_22_no_unsafe_dom_apis(self):
        for word in ["innerHTML", "eval(", "document.write"]:
            self.assertNotIn(word, self.evidence_all)

    def test_23_does_not_call_model_or_chroma_routes(self):
        for word in ["/api/chat", "/api/workflow", "/api/advanced", "Chroma", "向量模型", "大模型"]:
            self.assertNotIn(word, self.evidence_component)

    def test_24_original_source_search_and_nav_remain(self):
        self.assertIn("label:'研发证据查询'", self.component)
        self.assertIn("label:'白盒溯源'", self.component)
        self.assertIn("查询类型", self.evidence_template)
        self.assertIn("排除历史版本", self.evidence_template)
        self.assertIn("结果列表", self.evidence_template)

    def test_25_static_index_is_synced_with_source(self):
        expected = self.template.replace("/*__COMPONENT__*/", self.component)
        self.assertEqual(self.static_index, expected)
        self.assertIn("/api/evidence/chain-summary", self.static_index)
        self.assertIn("关联监管背景不计入该试验的证据数量", self.static_index)


if __name__ == "__main__":
    unittest.main()
