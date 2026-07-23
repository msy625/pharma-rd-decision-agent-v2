import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
COMPONENT = ROOT / "webapp" / "frontend_src" / "component.js"
TEMPLATE = ROOT / "webapp" / "frontend_src" / "template.html"
STATIC_INDEX = ROOT / "webapp" / "static" / "index.html"


class GroundedQAFrontendStaticTest(unittest.TestCase):
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

    def test_01_grounded_qa_fourth_tab_exists(self):
        self.assertIn("循证问答", self.evidence_template)
        self.assertIn("ev_isGroundedTab", self.evidence_template)
        self.assertIn("switchEvidenceTab('groundedQa')", self.evidence_component)

    def test_02_original_three_evidence_tabs_still_exist(self):
        for text in ["来源检索", "证据链", "企业对比", "ev_isSourceTab", "ev_isChainTab", "ev_isCompanyCompareTab"]:
            self.assertIn(text, self.evidence_all)

    def test_03_capabilities_api_is_called(self):
        self.assertIn("/api/evidence/grounded-qa/capabilities", self.evidence_component)
        self.assertIn("loadGroundedCapabilities", self.evidence_component)
        self.assertIn("gqa_capLoading", self.evidence_template)

    def test_04_grounded_qa_post_api_is_called(self):
        self.assertIn("fetch('/api/evidence/grounded-qa'", self.evidence_component)
        self.assertIn("generation_mode:this.state.groundedMode", self.evidence_component)

    def test_05_old_generation_routes_are_not_called(self):
        for path in ["/api/chat", "/api/whitebox", "/api/workflow", "/api/advanced"]:
            self.assertNotIn(path, self.evidence_component)

    def test_06_deepseek_available_defaults_to_auto(self):
        self.assertIn("groundedMode:deepseekOk?'auto':'local'", self.evidence_component)

    def test_07_deepseek_unavailable_defaults_to_local(self):
        self.assertIn("groundedMode:'local'", self.evidence_component)
        self.assertIn("DeepSeek智能生成当前未启用，本地循证摘要仍可使用", self.evidence_component)

    def test_08_auto_fallback_notice_exists(self):
        self.assertIn("auto 失败时会自动回退本地摘要", self.evidence_component)
        self.assertIn("DeepSeek暂不可用，已回退本地证据摘要", self.evidence_component)

    def test_09_six_example_questions_exist(self):
        for question in [
            "RATIONALE-304有哪些证据版本？",
            "RATIONALE-315形成了怎样的证据链？",
            "NCT04619433当前是什么状态？",
            "B015和B016有什么区别？",
            "恒瑞与百济当前证据样本有什么差异？",
            "当前数据还存在哪些缺口？",
        ]:
            self.assertIn(question, self.evidence_component)
        self.assertIn("gqa_examples", self.evidence_template)

    def test_10_examples_only_fill_input(self):
        self.assertIn("setGroundedExample(question)", self.evidence_component)
        self.assertIn("groundedQuestion:String(question||'').slice(0,1000)", self.evidence_component)
        example_method = self.evidence_component[
            self.evidence_component.index("setGroundedExample(question)") : self.evidence_component.index("  submitGroundedQA()", self.evidence_component.index("setGroundedExample(question)"))
        ]
        self.assertNotIn("submitGroundedQA", example_method)
        self.assertNotIn("fetch(", example_method)

    def test_11_empty_question_cannot_submit(self):
        self.assertIn("if(!question)", self.evidence_component)
        self.assertIn("请输入问题后再提交", self.evidence_component)
        self.assertIn("gqa_submitDisabled", self.evidence_template)

    def test_12_question_has_1000_character_limit(self):
        self.assertIn("question.length>1000", self.evidence_component)
        self.assertIn('maxlength="1000"', self.evidence_template)
        self.assertIn("字符数：{{ gqa_questionCount }} / 1000", self.evidence_template)

    def test_13_submit_prevents_duplicate_requests(self):
        self.assertIn("if(this.state.groundedLoading) return", self.evidence_component)
        self.assertIn("groundedLoading:true", self.evidence_component)
        self.assertIn('disabled="{{ gqa_submitDisabled }}"', self.evidence_template)

    def test_14_stale_request_cannot_override_newer_result(self):
        self.assertIn("groundedSeq", self.evidence_component)
        self.assertIn("AbortController", self.evidence_component)
        self.assertIn("seq!==this.state.groundedSeq", self.evidence_component)

    def test_14b_rate_limit_429_shows_friendly_message_without_retry(self):
        self.assertIn("status===429", self.evidence_component)
        self.assertIn("Retry-After", self.evidence_component)
        self.assertIn("切换 local 继续使用", self.evidence_component)
        self.assertNotIn("setTimeout(()=>this.submitGroundedQA", self.evidence_component)

    def test_15_answer_uses_safe_text_binding(self):
        self.assertIn("{{ gqa_answer }}", self.evidence_template)
        self.assertIn("white-space:pre-wrap", self.evidence_template)

    def test_16_no_unsafe_dom_apis_are_added(self):
        for word in ["innerHTML", "eval(", "document.write", "new Function"]:
            self.assertNotIn(word, self.evidence_all)

    def test_17_citations_display_source_id_and_url(self):
        self.assertIn("gqa_citations", self.evidence_template)
        self.assertIn("{{ ct.source_id }}", self.evidence_template)
        self.assertIn("{{ ct.source_url }}", self.evidence_template)

    def test_18_external_links_are_safe(self):
        self.assertIn("_safeEvidenceUrl", self.evidence_component)
        self.assertIn('target="_blank"', self.evidence_template)
        self.assertIn('rel="noopener noreferrer"', self.evidence_template)

    def test_19_limitations_region_exists(self):
        self.assertIn("限制说明", self.evidence_template)
        self.assertIn("gqa_limitations", self.evidence_template)
        self.assertIn("gqa_hasLimitations", self.evidence_template)

    def test_20_safety_notice_region_exists(self):
        self.assertIn("安全提示", self.evidence_template)
        self.assertIn("gqa_safetyNotice", self.evidence_template)
        self.assertIn("prohibited_or_unsupported:'安全边界'", self.evidence_component)

    def test_21_whitebox_trace_fields_are_complete(self):
        for label in ["检索服务", "检索来源ID", "检索证据链ID", "检索来源总数", "试验证据数量", "关联监管背景", "执行方式", "安全类别", "数据版本", "生成时间", "内部模型标识", "是否使用DeepSeek", "是否命中缓存"]:
            self.assertIn(label, self.evidence_component)
        self.assertIn("typeof trace.trial_evidence_count==='number'", self.evidence_component)
        self.assertIn("typeof trace.related_regulatory_count==='number'", self.evidence_component)
        self.assertIn("白盒过程", self.evidence_template)

    def test_22_no_secret_or_internal_error_details_are_shown(self):
        for word in ["DEEPSEEK_API_KEY", "sk-", "/home/", "traceback", "stack"]:
            self.assertNotIn(word, self.evidence_all)

    def test_23_chain_id_jump_uses_existing_encoded_loader(self):
        self.assertIn("openGroundedChain(chainId)", self.evidence_component)
        self.assertIn("this.loadChainDetail(cid)", self.evidence_component)
        self.assertIn("'/api/evidence/chains/'+encodeURIComponent(cid)", self.evidence_component)
        self.assertIn("查看证据链 {{ ch.chain_id }}", self.evidence_template)

    def test_24_prohibited_question_can_show_safety_boundary(self):
        self.assertIn("安全边界", self.evidence_component)
        self.assertIn("安全提示", self.evidence_template)
        self.assertIn("安全规则拦截", self.evidence_component)
        self.assertIn("未调用模型", self.evidence_component)
        self.assertIn("safety_block", self.evidence_component)
        self.assertIn("gqa_noCitationText", self.evidence_all)
        self.assertIn("当前回答不需要引用", self.evidence_component)

    def test_25_no_fixed_answer_mock_or_random_rating(self):
        for word in ["MOCK", "mock", "模拟结果", "Math.random", "random", "综合评分", "固定回答"]:
            self.assertNotIn(word, self.evidence_all)

    def test_26_page_load_does_not_auto_post_paid_api(self):
        load_method = self.evidence_component[
            self.evidence_component.index("  loadGroundedCapabilities(){") : self.evidence_component.index("  setGroundedMode(mode)")
        ]
        self.assertIn("capabilities", load_method)
        self.assertNotIn("fetch('/api/evidence/grounded-qa'", load_method)
        self.assertNotIn("submitGroundedQA", load_method)

    def test_27_existing_evidence_features_remain_present(self):
        for text in ["data-evidence-results", "证据链列表", "data-evidence-company-compare", "/api/evidence/search", "/api/evidence/chains", "/api/evidence/company-comparison"]:
            self.assertIn(text, self.evidence_all)

    def test_28_static_index_is_synced_with_source(self):
        expected = self.template.replace("/*__COMPONENT__*/", self.component)
        self.assertEqual(self.static_index, expected)
        self.assertIn("data-grounded-qa", self.static_index)
        self.assertIn("/api/evidence/grounded-qa/capabilities", self.static_index)

    def test_29_grounded_role_labels_are_user_friendly(self):
        for raw, label in [
            ("trial_registry", "临床试验登记"),
            ("interim_publication", "中期分析论文"),
            ("final_publication", "最终分析论文"),
            ("regulatory_authorisation", "EMA正式授权信息"),
            ("regulatory_opinion", "CHMP积极意见"),
        ]:
            self.assertIn(raw, self.evidence_component)
            self.assertIn(label, self.evidence_component)

    def test_30_grounded_unknown_role_does_not_display_snake_case(self):
        self.assertIn("_groundedRoleLabel(role)", self.evidence_component)
        self.assertIn("||'其他证据资料'", self.evidence_component)
        self.assertIn("\\b[a-z]+_[a-z_]+\\b", self.evidence_component)

    def test_31_grounded_model_names_are_user_friendly(self):
        self.assertIn("_groundedModelLabel(model)", self.evidence_component)
        self.assertIn("local-structured-summary", self.evidence_component)
        self.assertIn("本地循证摘要", self.evidence_component)
        self.assertIn("deepseek-v4-flash", self.evidence_component)
        self.assertIn("DeepSeek V4 Flash", self.evidence_component)
        self.assertIn("safe-policy", self.evidence_component)
        self.assertIn("模型：'+this._groundedModelLabel", self.evidence_component)

    def test_35_safety_block_does_not_use_capability_model_as_actual_model(self):
        self.assertIn("groundedGenerationMode==='safety_block'", self.evidence_component)
        self.assertIn("groundedUsedLlm", self.evidence_component)
        self.assertIn("(groundedMeta&&groundedMeta.model_name)||groundedTrace.model_name", self.evidence_component)
        self.assertNotIn("模型：'+this._groundedModelLabel(groundedCap.model_name)", self.evidence_component)

    def test_36_safety_category_has_chinese_display_fallback(self):
        self.assertIn("_safetyCategoryLabel(category)", self.evidence_component)
        for raw, label in [
            ("individual_diagnosis", "个体诊断建议"),
            ("individual_medication_or_treatment", "个体治疗或用药建议"),
            ("efficacy_guarantee", "疗效保证"),
            ("cross_trial_efficacy_ranking", "跨试验疗效排名"),
            ("success_probability_prediction", "成功率预测"),
            ("investment_advice", "投资建议"),
            ("company_overall_ranking", "企业综合排名"),
        ]:
            self.assertIn(raw, self.evidence_component)
            self.assertIn(label, self.evidence_component)
        self.assertIn("其他不支持的问题类型", self.evidence_component)
        self.assertIn("trace.safety_category?this._safetyCategoryLabel(trace.safety_category):'暂无'", self.evidence_component)

    def test_32_grounded_study_status_labels_are_user_friendly(self):
        for raw, label in [
            ("completed", "已完成"),
            ("terminated", "已终止"),
            ("active, not recruiting", "活跃、停止招募"),
            ("recruiting", "招募中"),
            ("not yet recruiting", "尚未招募"),
        ]:
            self.assertIn(raw, self.evidence_component)
            self.assertIn(label, self.evidence_component)
        self.assertIn("暂无明确状态", self.evidence_component)
        self.assertIn("研究状态：'+this._studyStatusLabel", self.evidence_component)
        self.assertIn("_friendlyGroundedSupportSummary(text)", self.evidence_component)
        self.assertIn("support_summary:this._friendlyGroundedSupportSummary", self.evidence_component)

    def test_32b_whitebox_service_and_generation_mode_labels_are_user_friendly(self):
        for raw, label in [
            ("EvidenceChainService", "证据链服务"),
            ("SourceRegistryService", "来源登记服务"),
            ("CompanyEvidenceComparisonService", "企业证据对比服务"),
            ("GroundedQAService", "循证问答服务"),
            ("llm", "DeepSeek智能生成"),
            ("local", "本地循证摘要"),
            ("safety_block", "安全规则拦截"),
        ]:
            self.assertIn(raw, self.evidence_component)
            self.assertIn(label, self.evidence_component)
        self.assertIn("_retrievalServiceLabel(name)", self.evidence_component)
        self.assertIn("_generationModeLabel(mode)", self.evidence_component)

    def test_33_grounded_answer_and_support_summary_are_cleaned(self):
        self.assertIn("gqa_answer:this._friendlyGroundedText(groundedResult.answer)", self.evidence_component)
        self.assertIn("support_summary:this._friendlyGroundedSupportSummary(item.support_summary)", self.evidence_component)
        self.assertIn("study_status=", self.evidence_component)

    def test_34_source_identity_fields_remain_raw_bindings(self):
        for binding in ["{{ ct.source_id }}", "{{ ct.source_url }}", "{{ ct.title }}"]:
            self.assertIn(binding, self.evidence_template)


if __name__ == "__main__":
    unittest.main()
