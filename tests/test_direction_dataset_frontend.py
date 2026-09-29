"""Frontend contract tests for the 「疾病方向」 (research-direction) evidence tab.

The tab surfaces the API-harvested research-direction dataset on top of the
existing 研发证据中心 page: a 6-stage roadmap, per-direction record lists with
疾病方向 / 研发阶段 filtering, pagination and an explicit data-scope disclaimer.

Like ``tests/test_evidence_frontend.py`` these tests assert on markers present in
the frontend sources and in the built ``webapp/static/index.html``. No browser or
Node.js runtime is required.
"""

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
BUILD_SCRIPT = ROOT / "webapp" / "frontend_src" / "build.py"

DIRECTION_TAB = "疾病方向"
DIRECTION_STATE_KEYS = [
    "directionRoadmap",
    "directionStage",
    "directionId",
    "directionRecords",
    "directionLoading",
    "directionError",
    "directionFilters",
    "directionLimit",
    "directionOffset",
]
DIRECTION_API_PATHS = [
    "/api/directions/roadmap",
    "/api/directions/filters",
    "/api/directions/records",
]
# Bindings provided by the ``sc-for`` loop variables of the direction template.
LOOP_LOCALS = {"st", "d", "r", "b", "o"}


class DirectionDatasetFrontendTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.component = COMPONENT.read_text(encoding="utf-8")
        cls.template = TEMPLATE.read_text(encoding="utf-8")
        cls.index = STATIC_INDEX.read_text(encoding="utf-8")
        start = cls.component.index("// ---- research-direction dataset")
        end = cls.component.index("  loadEvidenceChainPage(){", start)
        cls.direction_component = cls.component[start:end]
        t_start = cls.template.index('<sc-if value="{{ ev_isDirectionTab }}">')
        t_end = cls.template.index('<sc-if value="{{ ev_isGroundedTab }}">', t_start)
        cls.direction_template = cls.template[t_start:t_end]
        cls.all = cls.direction_component + "\n" + cls.direction_template
        cls.evidence_vals = cls.component[
            cls.component.index("  evidenceVals(){") : cls.component.index("  navDef(){")
        ]

    # ------------------------------------------------------------------ #
    # tab wiring
    # ------------------------------------------------------------------ #
    def test_01_direction_tab_is_the_fourth_evidence_tab(self):
        start = self.template.index('data-evidence-center-tabs=""')
        tabs = self.template[start : self.template.index("</div>", start)]
        self.assertIn("data-evidence-direction-tab", tabs)
        self.assertIn(DIRECTION_TAB, tabs)
        # the three pre-existing tabs must survive, and in order
        order = [tabs.index("来源检索"), tabs.index("证据链"), tabs.index("机构对比"), tabs.index(DIRECTION_TAB)]
        self.assertEqual(order, sorted(order))
        for label in ["来源检索", "证据链", "机构对比", "进入智能决策 Agent"]:
            self.assertIn(label, tabs)

    def test_02_direction_tab_is_gated_by_evidence_tab_state(self):
        self.assertIn("ev_tabDirection:()=>this.switchEvidenceTab('directions')", self.evidence_vals)
        self.assertIn("ev_isDirectionTab:s.page==='evidence'&&s.evidenceTab==='directions'", self.evidence_vals)
        self.assertIn("ev_tabDirectionStyle:tabStyle(s.evidenceTab==='directions')", self.evidence_vals)
        self.assertIn("data-evidence-direction-tab", self.template)
        self.assertIn('onclick="{{ ev_tabDirection }}"', self.template)
        self.assertIn('style="{{ ev_tabDirectionStyle }}"', self.template)
        self.assertIn('value="{{ ev_isDirectionTab }}"', self.template)

    def test_03_load_evidence_page_routes_directions_tab(self):
        loader = self.component[
            self.component.index("  loadEvidencePage(){") : self.component.index("  loadEvidenceSummary(){")
        ]
        self.assertIn("if(this.state.evidenceTab==='directions'){ this.loadDirectionPage(); return; }", loader)
        # existing tabs keep their own routes
        self.assertIn("this.loadEvidenceChainPage()", loader)
        self.assertIn("this.loadCompanyComparisonPage()", loader)

    def test_04_direction_state_keys_are_namespaced_and_initialised(self):
        state_block = self.component[self.component.index("  state = {") : self.component.index("  D = {")]
        for key in DIRECTION_STATE_KEYS:
            self.assertIn("direction", key)
            self.assertIn(key, state_block)

    # ------------------------------------------------------------------ #
    # API usage
    # ------------------------------------------------------------------ #
    def test_05_all_direction_api_paths_are_used(self):
        for path in DIRECTION_API_PATHS:
            self.assertIn("'" + path + "'", self.direction_component)
        self.assertIn("'/api/directions/roadmap'", self.direction_component)
        self.assertIn("'/api/directions/filters'", self.direction_component)
        self.assertIn("'/api/directions/records'", self.direction_component)

    def test_06_uses_existing_api_get_wrapper_only(self):
        self.assertIn("this._api(", self.direction_component)
        self.assertNotIn("_apiPost", self.all)
        self.assertNotIn("XMLHttpRequest", self.all)

    def test_07_record_query_sends_direction_stage_and_every_filter(self):
        query = self.direction_component[
            self.direction_component.index("  loadDirectionRecords(") : self.direction_component.index(
                "  selectDirectionStage("
            )
        ]
        for name in [
            "direction_id",
            "stage_id",
            "record_type",
            "source_type",
            "phase",
            "study_status",
            "company",
            "limit",
            "offset",
        ]:
            self.assertIn(name + ":", query)
        self.assertIn("q:String(f.q||'').trim()", query)

    def test_08_filters_endpoint_is_scoped_to_selected_direction(self):
        self.assertIn(
            "this._api('/api/directions/filters',{direction_id:this.state.directionId||''})",
            self.direction_component,
        )

    def test_09_pagination_uses_limit_offset_and_has_more(self):
        self.assertIn("directionHasMore", self.direction_component)
        self.assertIn("directionOffset:offset", self.direction_component)
        self.assertIn("directionTotal:Number(d&&d.total)||0", self.direction_component)
        self.assertIn("directionHasMore:!!(d&&d.has_more)", self.direction_component)
        self.assertIn("directionNextPage(){", self.direction_component)
        self.assertIn("directionPrevPage(){", self.direction_component)
        self.assertIn("data-direction-pager", self.direction_template)
        self.assertIn("data-direction-previous", self.direction_template)
        self.assertIn("data-direction-next", self.direction_template)
        self.assertIn("上一页", self.direction_template)
        self.assertIn("下一页", self.direction_template)
        self.assertIn('disabled="{{ dq_prevDisabled }}"', self.direction_template)
        self.assertIn('disabled="{{ dq_nextDisabled }}"', self.direction_template)
        self.assertIn("dq_prevDisabled:!(dirOffset>0)", self.evidence_vals)
        self.assertIn("dq_nextDisabled:!s.directionHasMore", self.evidence_vals)
        self.assertIn("dq_hasNext:!!s.directionHasMore", self.evidence_vals)

    def test_10_page_size_options_come_from_limit_state(self):
        for size in ["20", "50", "100"]:
            self.assertIn('value="%s"' % size, self.direction_template)
        self.assertIn("directionOnLimit(value)", self.direction_component)

    # ------------------------------------------------------------------ #
    # roadmap block
    # ------------------------------------------------------------------ #
    def test_11_roadmap_renders_every_stage_field(self):
        self.assertIn("data-direction-roadmap", self.direction_template)
        self.assertIn("data-direction-stage-grid", self.direction_template)
        self.assertIn("data-direction-stage=", self.direction_template)
        for binding in [
            "{{ st.stageLabel }}",
            "{{ st.goal }}",
            "{{ st.directionCountText }}",
            "{{ st.recordCountText }}",
            "{{ st.actionLabel }}",
        ]:
            self.assertIn(binding, self.direction_template)
        for label in ["目标：", "方向数 ", "收录记录 "]:
            self.assertIn(label, self.direction_template)

    def test_12_roadmap_mirrors_the_six_stage_table(self):
        self.assertIn("stage_name", self.direction_component)
        self.assertIn("stage_title", self.evidence_vals)
        self.assertIn("this._directionText(stage.stage_name)+'：'+this._directionText(stage.stage_title)", self.evidence_vals)
        self.assertIn("goal:this._directionText(stage.goal)", self.evidence_vals)
        self.assertIn("directionCountText:this._directionText(stage.direction_count)", self.evidence_vals)
        self.assertIn("recordCountText:this._directionText(stage.source_count)", self.evidence_vals)
        self.assertIn("dq_totalStages:this._directionText(dirRoadmap.total_stages)", self.evidence_vals)
        self.assertIn("dq_totalDirections:this._directionText(dirRoadmap.total_directions)", self.evidence_vals)
        self.assertIn("dq_totalRecords:this._directionText(dirRoadmap.total_records)", self.evidence_vals)

    def test_13_direction_chip_shows_counts_and_selects_direction(self):
        self.assertIn("data-direction-chip=", self.direction_template)
        self.assertIn('onclick="{{ d.onClick }}"', self.direction_template)
        self.assertIn("onClick:()=>this.selectDirection(dirId)", self.evidence_vals)
        self.assertIn("countText:'试验 '+this._directionText(dir.trial_count)+' / 论文 '+this._directionText(dir.publication_count)", self.evidence_vals)
        self.assertIn("sourceText:'收录记录 '+this._directionText(dir.source_count)+' 条'", self.evidence_vals)
        self.assertIn("{{ d.name }}", self.direction_template)
        self.assertIn("{{ d.sourceText }}", self.direction_template)
        self.assertIn("{{ d.countText }}", self.direction_template)

    def test_14_stage_filter_button_toggles_stage_scope(self):
        self.assertIn("data-direction-stage-filter=", self.direction_template)
        self.assertIn('onclick="{{ st.onSelectStage }}"', self.direction_template)
        self.assertIn("onSelectStage:()=>this.selectDirectionStage(stageId)", self.evidence_vals)
        self.assertIn("'取消阶段筛选'", self.evidence_vals)
        self.assertIn("'只看该阶段'", self.evidence_vals)

    # ------------------------------------------------------------------ #
    # filters
    # ------------------------------------------------------------------ #
    def test_15_all_required_filters_exist(self):
        self.assertIn("data-direction-filters", self.direction_template)
        for element_id in [
            "direction-scope-select",
            "direction-stage-select",
            "direction-record-type-select",
            "direction-phase-select",
            "direction-status-select",
            "direction-source-type-select",
            "direction-company-select",
            "direction-query-input",
        ]:
            self.assertIn('id="%s"' % element_id, self.direction_template)
        for label in ["疾病方向", "研发阶段", "记录类型", "分期", "状态", "来源类型", "申办方", "关键词"]:
            self.assertIn(label, self.direction_template)

    def test_16_record_type_choices_are_all_trial_publication(self):
        self.assertIn(
            "dq_recordTypeOptions:dirOptionList(['clinical_trial','publication'])",
            self.evidence_vals,
        )
        for label in ["'临床试验'", "'论文'", "'全部'"]:
            self.assertIn(label, self.evidence_vals)

    def test_17_filter_handlers_reset_the_offset(self):
        handler = self.direction_component[
            self.direction_component.index("  directionOnFilter(") : self.direction_component.index(
                "  directionOnQuery("
            )
        ]
        self.assertIn("this.setState({directionFilters:next,directionOffset:0}", handler)
        self.assertIn("this.loadDirectionRecords(0)", handler)
        for binding, key in [
            ("dq_onRecordType:(e)=>this.directionOnFilter('record_type'", "record_type"),
            ("dq_onPhase:(e)=>this.directionOnFilter('phase'", "phase"),
            ("dq_onStatus:(e)=>this.directionOnFilter('study_status'", "study_status"),
            ("dq_onSourceType:(e)=>this.directionOnFilter('source_type'", "source_type"),
            ("dq_onCompany:(e)=>this.directionOnFilter('company'", "company"),
        ]:
            self.assertIn(binding, self.evidence_vals)
            self.assertIn(key, self.evidence_vals)
        self.assertIn("dq_onStage:(e)=>this.directionChooseStage(e.target.value)", self.evidence_vals)
        self.assertIn("dq_onDirection:(e)=>this.directionChoose(e.target.value)", self.evidence_vals)

    def test_18_keyword_search_is_submitted_not_fired_per_keystroke(self):
        self.assertIn("dq_onQuery:(e)=>this.directionOnQuery(e.target.value)", self.evidence_vals)
        self.assertIn("dq_onKey:(e)=>{ if(e.key==='Enter') this.loadDirectionRecords(0); }", self.evidence_vals)
        self.assertIn("dq_search:()=>this.loadDirectionRecords(0)", self.evidence_vals)
        on_query = self.direction_component[
            self.direction_component.index("  directionOnQuery(") : self.direction_component.index(
                "  directionOnLimit("
            )
        ]
        self.assertNotIn("loadDirectionRecords", on_query)
        self.assertIn("data-direction-search", self.direction_template)
        self.assertIn('onclick="{{ dq_search }}"', self.direction_template)

    def test_19_scope_reset_and_refresh_controls_exist(self):
        self.assertIn("data-direction-reset-scope", self.direction_template)
        self.assertIn('onclick="{{ dq_resetScope }}"', self.direction_template)
        self.assertIn("data-direction-reload", self.direction_template)
        self.assertIn('onclick="{{ dq_refresh }}"', self.direction_template)
        self.assertIn("directionResetScope(){", self.direction_component)
        self.assertIn("directionRefresh(){ this.loadDirectionPage(); }", self.direction_component)

    def test_20_total_count_and_empty_and_error_states_are_shown(self):
        self.assertIn("共 {{ dq_total }} 条", self.direction_template)
        self.assertIn("当前收录记录 {{ dq_total }} 条", self.direction_template)
        self.assertIn("{{ dq_pageText }}", self.direction_template)
        for text in ["dq_loading", "dq_filtersLoading", "dq_hasError", "dq_error", "dq_empty", "空结果"]:
            self.assertIn(text, self.direction_template)
        for text in ["记录加载中", "筛选项加载中", "疾病方向记录加载失败"]:
            self.assertIn(text, self.all)

    # ------------------------------------------------------------------ #
    # record rows
    # ------------------------------------------------------------------ #
    def test_21_record_row_shows_all_required_fields(self):
        self.assertIn("data-direction-record-list", self.direction_template)
        self.assertIn("data-direction-record-row", self.direction_template)
        self.assertIn("data-direction-record-fields", self.direction_template)
        for binding in [
            "{{ r.title }}",
            "{{ r.studyName }}",
            "{{ r.directionText }}",
            "{{ r.sponsorLabel }}",
            "{{ r.sponsorText }}",
            "{{ r.dateText }}",
            "{{ r.recordTypeLabel }}",
            "{{ r.verifyLabel }}",
            "{{ r.idLabel }}",
            "{{ r.idValue }}",
        ]:
            self.assertIn(binding, self.direction_template)
        for label in ["研究名称：", "方向 / 阶段：", "日期：", "药物："]:
            self.assertIn(label, self.direction_template)

    def test_22_nct_identifier_is_a_link_and_pmid_doi_are_shown(self):
        self.assertIn('href="{{ r.idUrl }}"', self.direction_template)
        self.assertIn("registryId?'NCT'", self.direction_component)
        self.assertIn("'https://clinicaltrials.gov/study/'+encodeURIComponent(registryId)", self.direction_component)
        self.assertIn("pmid?'PMID'", self.direction_component)
        self.assertIn("doi?'DOI'", self.direction_component)
        self.assertRegex(self.direction_component, r"registryId=/\^NCT\\d\+\$/i")

    def test_23_original_source_link_uses_target_blank_and_noopener(self):
        self.assertIn("打开原始来源", self.direction_template)
        self.assertIn('href="{{ r.url }}"', self.direction_template)
        self.assertIn('target="_blank"', self.direction_template)
        self.assertIn('rel="noopener"', self.direction_template)
        # external links are restricted to http(s)
        self.assertIn("_safeDirectionUrl", self.direction_component)
        self.assertRegex(self.direction_component, r"\^https\?:\\/\\/")

    def test_24_phase_and_status_badges_are_derived_from_record(self):
        self.assertIn("_directionRecordVm(item)", self.direction_component)
        self.assertIn("badges.push({text:'分期 '+String(item.phase)})", self.direction_component)
        self.assertIn("badges.push({text:'状态 '+String(item.study_status)})", self.direction_component)
        self.assertIn("data-direction-record-row", self.direction_template)
        self.assertIn('as="b"', self.direction_template)
        self.assertIn("{{ b.text }}", self.direction_template)

    def test_25_verification_status_per_record_is_surfaced(self):
        self.assertIn("_directionVerification(value)", self.direction_component)
        self.assertIn("return {label:'人工核验', color:'var(--pos)'}", self.direction_component)
        self.assertIn("verifyLabel:verification.label", self.direction_component)
        self.assertIn("{{ r.verifyLabel }}", self.direction_template)

    # ------------------------------------------------------------------ #
    # The user-facing direction tab intentionally has no global scope/risk card.
    # ------------------------------------------------------------------ #
    def test_26_global_scope_disclaimer_is_not_rendered(self):
        self.assertNotIn("data-direction-scope-note", self.direction_template)
        self.assertNotIn("data-direction-verification-mix", self.direction_template)

    def test_26b_global_verification_mix_is_not_rendered(self):
        self.assertNotIn("dq_verificationMix", self.direction_template)
        self.assertNotIn("{{ dq_verificationMix }}", self.direction_template)

    def test_27_record_area_has_no_global_scope_or_risk_text(self):
        self.assertNotIn("data-direction-scope-note", self.direction_template)

    def test_28_no_ranking_or_efficacy_claims_in_direction_ui(self):
        for forbidden in [
            "榜单",
            "疗效最好",
            "成功率预测",
            "投资建议",
            "Math.random",
            "innerHTML",
            "eval(",
        ]:
            self.assertNotIn(forbidden, self.all)
        self.assertNotIn("不输出排名或评分", self.all)

    # ------------------------------------------------------------------ #
    # graceful degradation
    # ------------------------------------------------------------------ #
    def test_29_tab_hides_and_shows_note_when_dataset_unavailable(self):
        self.assertIn(
            "const caps={competition_core_available:true,evidence_workbench_available:true,company_evidence_profile_available:true,rd_event_timeline_available:true,direction_dataset_available:false",
            self.component,
        )
        self.assertIn("_directionAvailable(){ const c=this.state.runtimeCapabilities; return !!(c&&c.direction_dataset_available); }", self.component)
        self.assertIn("ev_hasDirectionTab:dirAvailable", self.evidence_vals)
        self.assertIn('data-evidence-direction-tab=""', self.template)
        self.assertIn('style="{{ ev_tabDirectionStyle }}"', self.template)
        self.assertIn('value="{{ !ev_hasDirectionTab }}"', self.template)
        self.assertIn("data-direction-tab-note", self.template)
        self.assertIn("疾病方向数据集未部署，已隐藏「疾病方向」页签。", self.template)

    def test_30_unavailable_state_renders_a_note_and_skips_requests(self):
        self.assertIn("data-direction-unavailable", self.direction_template)
        self.assertIn("疾病方向数据集未部署：缺少 config/direction_catalog.json", self.direction_template)
        self.assertIn('value="{{ dq_available }}"', self.direction_template)
        load_page = self.direction_component[
            self.direction_component.index("  loadDirectionPage(){") : self.direction_component.index(
                "  loadDirectionRoadmap(){"
            )
        ]
        self.assertIn("if(!this._directionAvailable()) return;", load_page)
        self.assertIn("dq_available:dirAvailable", self.evidence_vals)

    def test_31_direction_loaders_degrade_to_error_copy(self):
        for text in [
            "疾病方向路线图加载失败，请稍后重试",
            "疾病方向记录加载失败，请稍后重试",
        ]:
            self.assertIn(text, self.direction_component)
        for state in ["directionRoadmapError", "directionError"]:
            self.assertIn(state, self.evidence_vals)

    # ------------------------------------------------------------------ #
    # binding integrity + build artifact
    # ------------------------------------------------------------------ #
    def test_32_every_template_binding_resolves_to_a_defined_value(self):
        returned = set(
            re.findall(r"^\s+([A-Za-z_$][\w$]*):", self.evidence_vals, re.M)
        )
        self.assertTrue(returned)
        identifiers = set()
        for raw in re.findall(r"\{\{([^}]*)\}\}", self.direction_template):
            expr = raw.strip().lstrip("!")
            match = re.match(r"[A-Za-z_$][\w$]*", expr.strip())
            if match:
                identifiers.add(match.group(0))
        self.assertTrue(identifiers)
        unresolved = sorted(
            name for name in identifiers if name not in returned and name not in LOOP_LOCALS
        )
        self.assertEqual(unresolved, [], "template bindings without a view-model value: %s" % unresolved)
        for required in ["dq_stages", "dq_items", "dq_hasStages", "dq_hasItems", "dq_hasError", "dq_empty"]:
            self.assertIn(required, returned)

    def test_32b_bindings_use_only_expressions_the_runtime_supports(self):
        # dc-runtime resolve() understands paths, '!', '==='/'!=='/'=='/'!=' and literals only.
        for raw in re.findall(r"\{\{([^}]*)\}\}", self.direction_template):
            expr = raw.strip()
            self.assertNotRegex(
                expr,
                r"[?&|+*/()\[\]]|&&|\|\||=>",
                "unsupported binding expression for dc-runtime: {{ %s }}" % expr,
            )
            self.assertRegex(expr, r"^!?\s*[A-Za-z_$][\w$]*(\.[A-Za-z_$][\w$]*)*$")

    def test_33_template_custom_elements_are_balanced(self):
        for tag in ["sc-if", "sc-for", "section", "article", "button", "select", "label"]:
            opened = len(re.findall(r"<%s[\s>]" % tag, self.direction_template))
            closed = len(re.findall(r"</%s>" % tag, self.direction_template))
            self.assertEqual(opened, closed, "%s: %s open vs %s close" % (tag, opened, closed))
        self.assertGreater(len(re.findall(r"<sc-if[\s>]", self.direction_template)), 10)
        self.assertGreater(len(re.findall(r"<sc-for[\s>]", self.direction_template)), 6)

    def test_34_static_index_contains_generated_direction_tab(self):
        for marker in [
            "data-evidence-direction-tab",
            "data-direction-dataset",
            "data-direction-roadmap",
            "data-direction-record-row",
            "data-direction-pager",
            "data-direction-tab-note",
            "疾病方向研发路线图",
            "打开原始来源",
        ]:
            self.assertIn(marker, self.index)
        for path in DIRECTION_API_PATHS:
            self.assertIn(path, self.index)
        self.assertIn("loadDirectionPage()", self.index)
        self.assertIn("_directionRecordVm(item)", self.index)
        # the tabs container marker and the original tabs must survive the rebuild
        self.assertIn("data-evidence-center-tabs", self.index)
        for label in ["来源检索", "证据链", "机构对比", "进入智能决策 Agent"]:
            self.assertIn(label, self.index)

    def test_35_static_index_is_built_from_source(self):
        self.assertTrue(BUILD_SCRIPT.exists())
        self.assertNotIn("/*__COMPONENT__*/", self.index)
        expected = self.template.replace("/*__COMPONENT__*/", self.component)
        self.assertEqual(expected, self.index)


if __name__ == "__main__":
    unittest.main()
