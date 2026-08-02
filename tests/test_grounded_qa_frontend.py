import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
COMPONENT = ROOT / "webapp" / "frontend_src" / "component.js"
TEMPLATE = ROOT / "webapp" / "frontend_src" / "template.html"
STATIC_INDEX = ROOT / "webapp" / "static" / "index.html"


class DecisionAgentFrontendStaticTest(unittest.TestCase):
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

    def test_01_top_level_label_changed_but_page_key_is_stable(self):
        self.assertIn("{key:'groundedQa',label:'智能决策 Agent'", self.component)
        self.assertIn("isGroundedQaPage:s.page==='groundedQa'", self.component)
        self.assertIn("ev_isGroundedTab:s.page==='groundedQa'", self.component)
        self.assertIn("data-grounded-qa", self.template)
        self.assertNotIn("key:'decisionAgent'", self.component)

    def test_02_page_loads_decision_agent_capabilities(self):
        self.assertIn("else if(p==='groundedQa') this.loadDecisionAgentCapabilities()", self.component)
        self.assertIn("/api/evidence/decision-agent/capabilities", self.evidence_component)
        self.assertIn("agent_capLoading", self.evidence_template)
        load_method = self.evidence_component[
            self.evidence_component.index("  loadDecisionAgentCapabilities(){") : self.evidence_component.index("  setDecisionAgentQuestion(question)")
        ]
        self.assertNotIn("submitDecisionAgent", load_method)
        self.assertNotIn("fetch('/api/evidence/decision-agent'", load_method)

    def test_03_post_uses_decision_agent_api_and_selected_mode(self):
        self.assertIn("fetch('/api/evidence/decision-agent'", self.evidence_component)
        self.assertIn("agentGenerationMode:'auto'", self.component)
        self.assertIn("generation_mode:this.state.agentGenerationMode||'auto'", self.evidence_component)
        self.assertNotIn("generation_mode:this.state.groundedMode", self.evidence_component)
        self.assertNotIn("/api/evidence/grounded-qa/capabilities", self.evidence_component)
        self.assertNotIn("fetch('/api/evidence/grounded-qa'", self.evidence_component)

    def test_04_agent_state_is_independent_from_grounded_result(self):
        for name in [
            "agentCapabilities", "agentCapabilitiesLoading", "agentCapabilitiesLoaded",
            "agentQuestion", "agentLoading", "agentError", "agentResult",
            "agentSeq", "agentTraceOpen", "agentAllCitationsOpen",
        ]:
            self.assertIn(name, self.component)
        self.assertNotIn("groundedResult", self.evidence_template)
        self.assertNotIn("gqa_", self.evidence_template)

    def test_05_input_controls_cover_empty_length_duplicate_and_race(self):
        submit = self.evidence_component[
            self.evidence_component.index("  submitDecisionAgent(questionOverride)") : self.evidence_component.index("  _questionTypeLabel(type)")
        ]
        for snippet in [
            "if(!question)",
            "问题不能超过 1000 个字符",
            "if(this.state.agentLoading && !hasOverride) return",
            "AbortController",
            "seq!==this._agentSeq",
            "agentAllCitationsOpen:false",
        ]:
            self.assertIn(snippet, submit)
        self.assertIn('maxlength="1000"', self.evidence_template)
        self.assertIn("字符数：{{ agent_questionCount }} / 1000", self.evidence_template)
        self.assertIn('disabled="{{ agent_submitDisabled }}"', self.evidence_template)

    def test_06_non_2xx_network_and_backend_errors_are_system_errors(self):
        submit = self.evidence_component[
            self.evidence_component.index("  submitDecisionAgent(questionOverride)") : self.evidence_component.index("  _questionTypeLabel(type)")
        ]
        for snippet in [
            "if(!ok)",
            "status===400?detail",
            "决策 Agent 返回结构不可用",
            "if(result.error)",
            "网络或服务暂时不可用",
            "data-agent-system-error",
        ]:
            self.assertIn(snippet, submit + self.evidence_template)

    def test_07_three_golden_demo_cards_run_immediately(self):
        for text in [
            "阿斯利康与百济神州当前 NSCLC 证据样本有什么差异？",
            "RATIONALE-315 当前还存在哪些证据缺口？",
            "B016 是否代表替雷利珠单抗已经获得 EMA 正式批准？",
            "企业决策", "比较两家企业的当前证据结构", "生成企业比较结论",
            "证据诊断", "定位试验当前的证据缺口", "生成缺口分析",
            "监管判断", "辨析监管文件代表的真实状态", "生成监管判断",
        ]:
            self.assertIn(text, self.evidence_all)
        self.assertIn("data-agent-golden-cases", self.evidence_template)
        self.assertIn("runDecisionAgentExample(question)", self.evidence_component)
        self.assertIn("this.submitDecisionAgent(q)", self.evidence_component)
        self.assertIn("buttonText:'生成企业比较结论'", self.evidence_component)

    def test_08_page_has_required_information_architecture(self):
        for text in [
            "智能研发决策 Agent",
            "当前仅覆盖已收录并核验的 NSCLC 证据样本",
            "不代表企业完整研发实力",
            "不提供个体医疗建议",
            "不提供疗效保证",
            "不进行跨试验疗效排名",
            "不提供成功率预测或投资建议",
            "推荐演示",
            "提出你的研发问题",
            "本次决策问题",
            "Agent 判断",
            "Agent 决策过程",
            "运行详情",
            "数据范围与技术详情",
        ]:
            self.assertIn(text, self.evidence_all)

    def test_09_plan_and_steps_use_real_api_fields(self):
        for field in [
            "agent_plan", "agent_steps", "source_trace", "step_id",
            "tool", "status", "source_ids", "duration_ms",
            "result_summary", "input_summary",
        ]:
            self.assertIn(field, self.evidence_component + self.evidence_template)
        for label in ["已完成", "已跳过", "执行失败", "产出来源", "耗时"]:
            self.assertIn(label, self.evidence_all)

    def test_10_decision_object_is_structurally_mapped(self):
        for field in [
            "decision.summary", "decision.key_findings", "decision.comparison_dimensions",
            "decision.risk_flags", "decision.evidence_gaps", "decision.next_evidence_actions",
            "decision.supported_conclusions", "decision.unsupported_conclusions",
            "decision.evidence_maturity", "decision.scope_statement",
        ]:
            self.assertIn(field, self.evidence_component)
        for label in [
            "Agent 判断", "关键依据", "对比依据", "证据结构与可追溯性",
            "决策边界", "当前证据缺口", "建议核验行动",
            "当前证据支持", "当前证据暂不支持",
            "完整分析说明",
        ]:
            self.assertIn(label, self.evidence_template)

    def test_11_featured_citations_are_preferred_and_full_citations_toggle(self):
        for snippet in [
            "featured_citations", "agent_featuredCitations",
            "agent_featuredFallback", "agent_allCitations",
            "agent_toggleAllCitations", "agentAllCitationsOpen",
            "agentFullCitations.length",
        ]:
            self.assertIn(snippet, self.evidence_component)
        for text in ["支撑本次判断的关键证据", "完整证据清单"]:
            self.assertIn(text, self.evidence_template)
        for text in ["查看全部证据", "收起完整证据清单", "agent_allCitationsToggleText"]:
            self.assertIn(text, self.evidence_component)

    def test_12_citations_show_trace_and_safe_links(self):
        for snippet in [
            "produced_by_steps", "producedText", "由步骤 ",
            "item.url||item.source_url", "_safeEvidenceUrl",
        ]:
            self.assertIn(snippet, self.evidence_component)
        for text in ['data-produced-by-steps', 'target="_blank"', 'rel="noopener noreferrer"', "查看证据详情"]:
            self.assertIn(text, self.evidence_template)

    def test_13_safety_refusal_is_separate_from_normal_decision(self):
        self.assertIn("agent_refused", self.evidence_component + self.evidence_template)
        self.assertIn("data-agent-safety", self.evidence_template)
        self.assertIn("该问题超出系统安全边界", self.evidence_template)
        self.assertRegex(self.evidence_template, r'<sc-if value="\{\{ agent_hasDecision \}\}">')

    def test_14_data_insufficient_is_separate_from_system_error(self):
        self.assertIn("_agentDataInsufficient(result)", self.evidence_component)
        self.assertIn("agent_dataInsufficient", self.evidence_component + self.evidence_template)
        self.assertIn("data-agent-data-insufficient", self.evidence_template)
        self.assertIn("当前证据不足以形成完整判断", self.evidence_template)
        self.assertIn("仍需补充的证据", self.evidence_template)
        self.assertIn("data-agent-system-error", self.evidence_template)

    def test_15_capabilities_show_only_api_backed_fields(self):
        for field in [
            "supported_generation_modes", "supported_intents", "supported_companies",
            "data_version", "data_scope", "scope_statement", "tool_mapping",
        ]:
            self.assertIn(field, self.evidence_component + self.evidence_template)
        for forbidden in ["17/17", "P95", "评测通过"]:
            self.assertNotIn(forbidden, self.evidence_template)
        self.assertNotRegex(self.evidence_template, r"100%\s*(评测|通过|pass)")

    def test_15b_capabilities_value_mapping_uses_agent_value_helper(self):
        self.assertNotIn("this_agentValueText", self.component)
        self.assertIn(
            "fields.push({label:'数据版本', value:this._agentValueText(cap.data_version)})",
            self.evidence_component,
        )
        self.assertIn(
            "fields.push({label:'适用边界', value:this._agentValueText(cap.safety_scope)})",
            self.evidence_component,
        )

    def test_16_auto_is_default_and_local_remains_selectable(self):
        for required in [
            "data-agent-generation-mode", "智能生成（auto）", "本地证据分析（local）",
            "agent_chooseAuto", "agent_chooseLocal", "setDecisionAgentMode(mode)",
            "DeepSeek不可用时回退本地分析", "始终不调用模型",
        ]:
            self.assertIn(required, self.evidence_all)

    def test_17_cross_page_prefill_writes_agent_question_without_auto_run(self):
        open_method = self.component[
            self.component.index("  openGroundedQa(question)") : self.component.index("  openProfileGroundedQa()")
        ]
        self.assertIn("patch.agentQuestion=String(question).slice(0,1000)", open_method)
        self.assertIn("this.loadDecisionAgentCapabilities()", open_method)
        self.assertNotIn("submitDecisionAgent", open_method)
        for snippet in [
            "this.openGroundedQa('请基于当前已核验证据样本说明 '+company",
            "openChainGroundedQa(chain)",
            "this.openGroundedQa(question)",
            "进入智能决策 Agent",
        ]:
            self.assertIn(snippet, self.component + self.template)

    def test_18_old_evidence_tabs_and_grounded_qa_backend_are_not_removed(self):
        for text in ["来源检索", "证据链", "企业对比", "ev_isSourceTab", "ev_isChainTab", "ev_isCompanyCompareTab"]:
            self.assertIn(text, self.evidence_all)
        self.assertIn('/api/evidence/grounded-qa', (ROOT / "webapp" / "main.py").read_text(encoding="utf-8"))

    def test_19_answer_uses_safe_text_binding(self):
        self.assertIn("{{ agent_answer }}", self.evidence_template)
        self.assertIn("white-space:pre-wrap", self.evidence_template)
        for word in ["innerHTML", "eval(", "document.write", "new Function"]:
            self.assertNotIn(word, self.evidence_all)

    def test_20_source_and_chain_jumps_use_existing_loaders(self):
        for snippet in [
            "onClick:()=>this.openGroundedSource(sourceId)",
            "openGroundedChain(chainId)",
            "page:'evidence',evidenceTab:'sources'",
            "page:'evidence',evidenceTab:'chains'",
            "this.loadChainDetail(cid)",
            "'/api/evidence/chains/'+encodeURIComponent(cid)",
        ]:
            self.assertIn(snippet, self.component)

    def test_21_no_undefined_null_or_object_bindings_are_expected(self):
        self.assertIn("_agentValueText(value, empty)", self.evidence_component)
        self.assertIn("_agentEntityText(value)", self.evidence_component)
        self.assertNotIn("[object Object]", self.evidence_template)
        self.assertNotRegex(self.evidence_template, r"\{\{\s*agentResult")

    def test_22_static_index_is_synced_with_agent_sources(self):
        expected = self.template.replace("/*__COMPONENT__*/", self.component)
        self.assertEqual(self.static_index, expected)
        for text in [
            "data-agent-page",
            "/api/evidence/decision-agent/capabilities",
            "/api/evidence/decision-agent",
            "智能研发决策 Agent",
        ]:
            self.assertIn(text, self.static_index)

    def test_23_agent_frontend_does_not_expose_secrets_or_internal_exception_details(self):
        for forbidden in [
            "DEEPSEEK_API_KEY",
            "sk-",
            "/home/",
            "traceback",
            "Traceback (most recent call last)",
            "stack_trace",
            "stackTrace",
            "error.stack",
            "Stack trace",
            "stack trace",
            "异常堆栈",
            "错误堆栈",
        ]:
            self.assertNotIn(forbidden.lower(), self.evidence_all.lower())

    def test_24_agent_demo_does_not_use_fake_results_random_scores_or_fixed_answers(self):
        agent_template_start = self.evidence_template.index('<sc-if value="{{ ev_isGroundedTab }}">')
        agent_template = self.evidence_template[agent_template_start:]
        agent_component = "\n".join([
            self.evidence_component[
                self.evidence_component.index("  loadDecisionAgentCapabilities(){") :
                self.evidence_component.index("  _questionTypeLabel(type)")
            ],
            self.evidence_component[
                self.evidence_component.index("  _agentArray(value)") :
                self.evidence_component.index("  _chainTypeLabel(t)")
            ],
            self.evidence_component[
                self.evidence_component.index("    const agentCap=s.agentCapabilities||{};") :
                self.evidence_component.index("      agent_capLoading:s.agentCapabilitiesLoading,")
            ],
            self.evidence_component[
                self.evidence_component.index("      agent_capLoading:s.agentCapabilitiesLoading,") :
                self.evidence_component.index("      agent_scopeItems:", self.evidence_component.index("      agent_capLoading:s.agentCapabilitiesLoading,"))
            ],
        ])
        agent_all = agent_component + "\n" + agent_template
        for forbidden in [
            "Math.random",
            "模拟结果",
            "综合评分",
            "固定回答",
            "MOCK_AGENT",
            "mockAgentResult",
            "agentMockResult",
            "agent_mock_result",
            "mock_agent_result",
        ]:
            self.assertNotIn(forbidden, agent_all)

    def test_25_visual_hierarchy_and_progressive_disclosure_contracts(self):
        for snippet in [
            'grid-template-columns:minmax(0,1.8fr) minmax(300px,.8fr)',
            'data-agent-hero-stat',
            'data-agent-judgment',
            'data-agent-boundary="gap"',
            'data-agent-boundary="unsupported"',
            'data-agent-fold',
            'data-agent-fold-button',
        ]:
            self.assertIn(snippet, self.template)
        for snippet in [
            "agentChainLinksOpen:false",
            "agentFeaturedCitationsOpen:false",
            "agentChainLinksAll.slice(0,3)",
            "agentFeaturedAll.slice(0,3)",
            "agent_featuredTotalCount:agentFeaturedAll.length",
        ]:
            self.assertIn(snippet, self.evidence_component)
        for binding in [
            'aria-expanded="{{ agent_processOpen }}"',
            'aria-expanded="{{ agent_chainLinksOpen }}"',
            'aria-expanded="{{ agent_featuredCitationsOpen }}"',
            'aria-expanded="{{ agent_allCitationsOpen }}"',
            'aria-expanded="{{ agent_runDetailsOpen }}"',
            'aria-expanded="{{ agent_capabilitiesOpen }}"',
        ]:
            self.assertIn(binding, self.evidence_template)

    def test_25b_technical_details_is_the_unique_last_agent_module(self):
        agent_start = self.evidence_template.index('<div data-grounded-qa="" data-agent-page=""')
        agent_page = self.evidence_template[agent_start:]
        hero = agent_page.index('data-agent-hero=""')
        stats = agent_page.index('data-agent-hero-stats=""')
        question = agent_page.index('data-agent-question=""')
        demo = agent_page.index('data-agent-demo=""')
        result = agent_page.index('data-agent-result=""')
        capabilities = agent_page.index('data-agent-capabilities=""')
        self.assertTrue(hero < stats < question < demo < result < capabilities)
        self.assertEqual(agent_page.count('data-agent-capabilities=""'), 1)
        self.assertEqual(agent_page.count('数据范围与技术详情'), 1)
        for forbidden in [
            '[data-agent-page]>[data-agent-hero]{order:',
            '[data-agent-page]>[data-agent-hero-stats]{order:',
            '[data-agent-page]>[data-agent-question]{order:',
            '[data-agent-page]>[data-agent-demo]{order:',
            '[data-agent-page]>[data-agent-result]{order:',
        ]:
            self.assertNotIn(forbidden, self.template)

    def test_26_agent_responsive_rules_prevent_wide_mobile_layouts(self):
        for snippet in [
            '@media(max-width:1080px)',
            '@media(max-width:768px)',
            '@media(max-width:420px)',
            '[data-agent-workflow]{grid-template-columns:1fr',
            '[data-agent-golden-cases],[data-agent-decision-sections]{grid-template-columns:minmax(0,1fr)',
            '[data-agent-golden-cases]{grid-template-columns:minmax(0,1fr)',
            'overflow-wrap:anywhere',
        ]:
            self.assertIn(snippet, self.template)


if __name__ == "__main__":
    unittest.main()
