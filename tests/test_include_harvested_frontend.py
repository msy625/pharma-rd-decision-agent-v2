"""Frontend contract tests for the 双轨数据「包含机器采集数据」switch.

The switch optionally layers the API-harvested records (``verification_status ==
"api_harvested"``) on top of the 39 human-verified rows. It must be available on
four pages — 研发决策总览 / 来源检索 / 企业证据画像 / 研发事件时间轴 — default
OFF, share one state key, and never present harvested rows as human-verified.

Like ``tests/test_direction_dataset_frontend.py`` these tests assert on markers in
the frontend sources and in the built ``webapp/static/index.html``. No browser or
Node.js runtime is required.
"""

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

TOGGLE_MARKER = "data-include-harvested-toggle"
NOTE_MARKER = "data-include-harvested-note"
ROW_BADGE_MARKER = "data-include-harvested-row-badge"
STATE_KEY = "includeHarvested"
PARAM = "include_harvested"
# Pages the switch must appear on, expressed through the shared shell binding.
ELIGIBLE_PAGES = ["today", "compare", "timeline"]
HARVESTED_STATUS = "api_harvested"
VERIFIED_STATUS = "已人工核验"


class IncludeHarvestedFrontendTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.component = COMPONENT.read_text(encoding="utf-8")
        cls.template = TEMPLATE.read_text(encoding="utf-8")
        cls.index = STATIC_INDEX.read_text(encoding="utf-8")
        # The shared control lives in shellVals() + the app header/content wrapper.
        cls.shell_vals = cls.component[
            cls.component.index("  shellVals(){") : cls.component.index("  todayVals(){")
        ]
        cls.ih_block = cls.component[
            cls.component.index("  // ---- 双轨数据：人工核验 / 机器采集 切换") :
            cls.component.index("  // ---- research-direction dataset")
        ]
        cls.header_template = cls.template[
            cls.template.index('<header data-header=""') : cls.template.index("</header>")
        ]
        cls.content_open = cls.template[
            cls.template.index('<div data-content=""') : cls.template.index('<sc-if value="{{ isToday }}">')
        ]

    # ------------------------------------------------------------------ #
    # one shared control, default off
    # ------------------------------------------------------------------ #
    def test_01_state_key_exists_once_and_defaults_to_false(self):
        self.assertIn(f"{STATE_KEY}:false", self.component)
        self.assertEqual(self.component.count(f"{STATE_KEY}:false"), 1)
        self.assertNotIn(f"{STATE_KEY}:true", self.component)

    def test_02_toggle_marker_is_rendered_once_in_the_shared_header(self):
        self.assertEqual(self.template.count(f'{TOGGLE_MARKER}=""'), 1)
        self.assertIn(TOGGLE_MARKER, self.header_template)

    def test_03_toggle_is_a_labelled_checkbox_wired_to_the_shared_state(self):
        self.assertIn('id="include-harvested-checkbox"', self.header_template)
        self.assertIn('name="include_harvested"', self.header_template)
        self.assertIn('type="checkbox"', self.header_template)
        self.assertIn('checked="{{ ih_on }}"', self.header_template)
        self.assertIn('onchange="{{ ih_toggle }}"', self.header_template)
        self.assertIn('for="include-harvested-checkbox"', self.header_template)
        self.assertIn("ih_toggle:()=>this.toggleIncludeHarvested()", self.shell_vals)

    def test_04_toggle_visibility_is_limited_to_the_four_pages(self):
        self.assertIn("ih_show:", self.shell_vals)
        show_line = next(
            line for line in self.shell_vals.splitlines() if line.strip().startswith("ih_show:")
        )
        for page in ELIGIBLE_PAGES:
            with self.subTest(page=page):
                self.assertIn(f"s.page==='{page}'", show_line)
        # evidence page only on the 来源检索 tab
        self.assertIn("s.page==='evidence'&&s.evidenceTab==='sources'", show_line)
        # legacy pages must not expose it
        for legacy in ["chat", "research", "whitebox", "database", "advanced"]:
            with self.subTest(legacy=legacy):
                self.assertNotIn(f"s.page==='{legacy}'", show_line)
        self.assertIn('<sc-if value="{{ ih_show }}">', self.header_template)

    def test_05_off_state_sends_an_explicit_false(self):
        self.assertIn(f"_ihParams(){{ return {{{PARAM}:!!this.state.{STATE_KEY}}}; }}", self.component)

    # ------------------------------------------------------------------ #
    # query wiring on the four pages
    # ------------------------------------------------------------------ #
    def test_06_overview_page_passes_the_param_to_the_workbench(self):
        self.assertIn("this._api('/api/evidence/workbench', this._ihParams())", self.component)

    def test_07_sources_tab_passes_the_param_to_summary_and_search(self):
        self.assertIn("this._api('/api/evidence/summary', this._ihParams())", self.component)
        params = self.component[
            self.component.index("  _evidenceParams(){") : self.component.index("  _evidenceText(v){")
        ]
        self.assertIn("this._ihParams()", params)
        self.assertIn("if(s.evidenceKind==='source') return this._ihParams();", params)

    def test_08_all_six_query_modes_reuse_evidence_params(self):
        """company/drug/trial/study/search/source all share one params helper."""
        self.assertIn("this._api(this._evidencePath(s.evidenceKind,q), this._evidenceParams())", self.component)
        self.assertIn("this._api(this._evidencePath('source', sid), this._ihParams())", self.component)

    def test_09_company_profile_page_passes_the_param(self):
        self.assertIn(
            "this._api('/api/evidence/company-profile/'+encodeURIComponent(name), this._ihParams())",
            self.component,
        )

    def test_10_timeline_page_passes_the_param(self):
        timeline = self.component[
            self.component.index("  loadTimeline(){") : self.component.index("  loadTimelineSources")
            if "  loadTimelineSources" in self.component
            else self.component.index("  loadTimeline(){") + 3000
        ]
        self.assertIn(f"{PARAM}:!!s.{STATE_KEY}", timeline)

    def _reload_block(self):
        return self.component[
            self.component.index("  reloadHarvestedScope(){") :
            self.component.index("  // ---- research-direction dataset")
        ]

    def test_11_toggling_reloads_only_the_current_page(self):
        self.assertIn("toggleIncludeHarvested(){", self.component)
        self.assertIn(f"const next=!this.state.{STATE_KEY};", self.component)
        self.assertIn(f"this.setState({{{STATE_KEY}:next}},()=>this.reloadHarvestedScope());", self.component)
        reload_block = self._reload_block()
        self.assertIn("this.loadDashboard()", reload_block)
        self.assertIn("this.loadCompanyEvidenceProfile()", reload_block)
        self.assertIn("this.loadTimeline()", reload_block)
        self.assertIn("this.loadEvidenceSummary()", reload_block)
        self.assertIn("this.loadEvidence()", reload_block)

    def test_12_reload_resets_the_loaded_guard_so_the_workbench_refetches(self):
        self.assertIn("evidenceWorkbenchLoaded:false", self._reload_block())

    # ------------------------------------------------------------------ #
    # scope warning
    # ------------------------------------------------------------------ #
    def test_13_scope_note_marker_and_gate(self):
        self.assertEqual(self.template.count(f'{NOTE_MARKER}=""'), 1)
        self.assertIn('<sc-if value="{{ ih_noteVisible }}">', self.content_open)
        self.assertIn(NOTE_MARKER, self.index)

    def test_14_scope_note_only_shows_when_the_switch_is_on(self):
        self.assertIn("ih_noteVisible:", self.shell_vals)
        line = next(
            line for line in self.shell_vals.splitlines() if line.strip().startswith("ih_noteVisible:")
        )
        self.assertIn(f"&&!!s.{STATE_KEY}", line)
        for page in ELIGIBLE_PAGES:
            with self.subTest(page=page):
                self.assertIn(f"s.page==='{page}'", line)

    def test_15_warning_copy_states_the_two_track_limitation(self):
        for fragment in [
            "已包含机器采集数据（api_harvested，未经人工逐条复核）",
            "未经人工逐条复核",
            "与人工核验资料属于两套口径",
            "不能互相替代",
            "不用于企业研发实力排名",
            "不支持跨试验疗效、安全性或成功率推断",
            "本页不把机器采集记录表述为人工核验",
        ]:
            with self.subTest(fragment=fragment):
                self.assertIn(fragment, self.index)

    def test_16_warning_reuses_the_direction_tab_tone(self):
        """Same warn-toned panel styling as data-direction-scope-note."""
        note = self.template[
            self.template.index(f'{NOTE_MARKER}=""') - 200 : self.template.index(f'{NOTE_MARKER}=""') + 200
        ]
        self.assertIn("var(--warn)", note)
        self.assertIn("var(--warn-bg)", note)

    def test_17_scope_badge_and_mix_line_present(self):
        self.assertIn('data-include-harvested-scope-badge=""', self.template)
        self.assertIn('data-include-harvested-mix=""', self.template)
        self.assertIn("ih_mixText:", self.shell_vals)
        self.assertIn("ih_hasMix:", self.shell_vals)

    def test_18_mix_line_reports_both_counts(self):
        helper = self.component[
            self.component.index("  _ihMixText(){") : self.component.index("  toggleIncludeHarvested(){")
        ]
        self.assertIn("人工核验（verified）", helper)
        self.assertIn(f"机器采集（{HARVESTED_STATUS}）", helper)

    # ------------------------------------------------------------------ #
    # per-row marking
    # ------------------------------------------------------------------ #
    def test_19_row_badge_helper_matches_only_harvested_rows(self):
        self.assertIn(f"_ihIsHarvested(value){{ return String(value==null?'':value).trim().toLowerCase()==='{HARVESTED_STATUS}'; }}", self.component)
        # verified rows must NOT be treated as harvested
        self.assertNotIn(VERIFIED_STATUS, self.component[
            self.component.index("  _ihIsHarvested(") : self.component.index("  _ihIsHarvested(") + 160
        ])

    def test_20_evidence_rows_and_detail_carry_the_badge(self):
        self.assertIn('data-include-harvested-row-badge=""', self.template)
        self.assertIn('data-include-harvested-detail-badge=""', self.template)
        self.assertIn("isHarvested:this._ihIsHarvested(item.verification_status)", self.component)
        self.assertIn("ev_detailIsHarvested:this._ihIsHarvested(detail.verification_status)", self.component)

    def test_21_timeline_events_and_undated_sources_carry_the_badge(self):
        self.assertIn("isHarvested:this._ihIsHarvested(event.verification_status)", self.component)
        self.assertIn("isHarvested:this._ihIsHarvested(item.verification_status)", self.component)
        self.assertIn('sc-if value="{{ e.isHarvested }}"', self.template)
        self.assertIn('sc-if value="{{ u.isHarvested }}"', self.template)

    def test_22_profile_rows_carry_the_badge(self):
        self.assertIn("isHarvested:this._ihIsHarvested(item.verification_status)", self.component)
        self.assertIn('sc-if value="{{ src.isHarvested }}"', self.template)

    def test_23_badges_use_the_shared_label_and_never_claim_verification(self):
        self.assertIn("ih_badgeLabel:'机器采集'", self.shell_vals)
        self.assertIn("{{ ih_badgeLabel }}", self.template)
        badge_context = self.index.count("机器采集")
        self.assertGreater(badge_context, 2)

    # ------------------------------------------------------------------ #
    # the direction tab must keep its own notice
    # ------------------------------------------------------------------ #
    def test_24_direction_tab_scope_note_is_untouched(self):
        self.assertEqual(self.template.count('data-direction-scope-note=""'), 1)
        self.assertIn("dq_spectrumNote:", self.component)
        self.assertIn("本页记录为 API 机器采集（api_harvested），未经人工逐条复核", self.component)

    def test_25_direction_tab_still_routes_and_is_not_displaced(self):
        self.assertIn("if(this.state.evidenceTab==='directions'){ this.loadDirectionPage(); return; }", self.component)
        self.assertIn('data-evidence-direction-tab=""', self.template)
        # the new control must not be injected inside the direction panel
        direction_panel = self.template[
            self.template.index('<sc-if value="{{ ev_isDirectionTab }}">') :
            self.template.index('<sc-if value="{{ ev_isGroundedTab }}">')
        ]
        self.assertNotIn(TOGGLE_MARKER, direction_panel)
        self.assertNotIn(NOTE_MARKER, direction_panel)

    # ------------------------------------------------------------------ #
    # the summary must not mislabel harvested rows as verified
    # ------------------------------------------------------------------ #
    def test_26_verified_count_is_used_for_the_verified_label(self):
        """With the switch on, total_sources is 2830; the 人工核验 label must not show it."""
        ev = self.component[
            self.component.index("  evidenceVals(){") : self.component.index("  navDef(){")
        ]
        self.assertIn("const verifiedTotal=this._evidenceText(sum.verified_source_count!=null?sum.verified_source_count:sum.total_sources);", ev)
        self.assertIn("ev_scopeCount:verifiedTotal,", ev)
        self.assertNotIn("ev_scopeCount:this._evidenceText(sum.total_sources)", ev)

    def test_27_direction_tab_copy_uses_the_verified_count(self):
        ev = self.component[
            self.component.index("  evidenceVals(){") : self.component.index("  navDef(){")
        ]
        self.assertIn("dq_verifiedCount:this._evidenceText(sum.verified_source_count!=null?sum.verified_source_count:sum.total_sources),", ev)

    def test_28_scope_tiles_collapse_when_the_switch_is_on(self):
        """723 harvested companies must not become 723 scope tiles."""
        ev = self.component[
            self.component.index("  evidenceVals(){") : self.component.index("  navDef(){")
        ]
        tiles = ev[ev.index("const evScopeTiles=") : ev.index("const items=(s.evidenceItems||[])")]
        self.assertIn("harvestOn", tiles)
        self.assertIn("'机器采集资料'", tiles)
        self.assertIn("'涉及企业'", tiles)
        # the per-company tile list must be the OFF branch only
        self.assertIn(": [{label:'疾病领域',value:'NSCLC'}]", tiles)
        self.assertIn("ev_scope:evScopeTiles,", ev)

    def test_29_subtitle_suffix_reports_the_harvested_count(self):
        ev = self.component[
            self.component.index("  evidenceVals(){") : self.component.index("  navDef(){")
        ]
        self.assertIn("ev_scopeSuffix:", ev)
        self.assertIn("{{ ev_scopeCount }} 条人工核验资料{{ ev_scopeSuffix }}", self.template)
        self.assertIn("{{ ev_scopeCount }} 条已核验 NSCLC 资料{{ ev_scopeSuffix }}", self.template)

    # ------------------------------------------------------------------ #
    # built artifact
    # ------------------------------------------------------------------ #
    def test_26_built_index_contains_every_new_marker(self):
        for marker in [
            TOGGLE_MARKER,
            NOTE_MARKER,
            ROW_BADGE_MARKER,
            "data-include-harvested-on",
            "data-include-harvested-mix",
            "data-include-harvested-scope-badge",
            "data-include-harvested-detail-badge",
            "include-harvested-checkbox",
        ]:
            with self.subTest(marker=marker):
                self.assertIn(marker, self.index)

    def test_27_built_index_matches_the_frontend_sources(self):
        template = TEMPLATE.read_text(encoding="utf-8")
        component = COMPONENT.read_text(encoding="utf-8")
        self.assertIn("/*__COMPONENT__*/", template)
        expected = template.replace("/*__COMPONENT__*/", component)
        actual = STATIC_INDEX.read_text(encoding="utf-8")
        self.assertEqual(actual.replace("\r\n", "\n"), expected.replace("\r\n", "\n"))

    def test_28_build_script_is_the_documented_entry_point(self):
        build = BUILD_SCRIPT.read_text(encoding="utf-8")
        self.assertIn("/*__COMPONENT__*/", build)
        self.assertIn("index.html", build)


if __name__ == "__main__":
    unittest.main()
