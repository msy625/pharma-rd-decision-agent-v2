import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
COMPONENT = ROOT / "webapp" / "frontend_src" / "component.js"
TEMPLATE = ROOT / "webapp" / "frontend_src" / "template.html"
STATIC_INDEX = ROOT / "webapp" / "static" / "index.html"


class RDEventTimelineFrontendTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.component = COMPONENT.read_text(encoding="utf-8")
        cls.template = TEMPLATE.read_text(encoding="utf-8")
        cls.index = STATIC_INDEX.read_text(encoding="utf-8")
        cls.loader = cls.component[
            cls.component.index("  loadTimeline(){") : cls.component.index("  loadWhitebox(){")
        ]
        cls.values = cls.component[
            cls.component.index("  timelineVals(){") : cls.component.index("  advancedVals(){")
        ]
        cls.view = cls.template[
            cls.template.index('<sc-if value="{{ isTimeline }}">') : cls.template.index('<sc-if value="{{ isAdvanced }}">')
        ]

    def test_01_navigation_uses_rd_event_timeline_and_is_not_legacy(self):
        self.assertIn("label:'研发事件时间轴'", self.component)
        self.assertIn("timeline:['研发事件时间轴','核验证据事件']", self.component)
        legacy = re.search(r"_legacyPages\(\)\{ return \{(?P<body>.*?)\}; \}", self.component).group("body")
        self.assertNotIn("timeline", legacy)

    def test_02_timeline_only_requests_new_evidence_endpoints(self):
        self.assertIn("'/api/evidence/timeline/'", self.loader)
        self.assertIn("'/api/evidence/timeline'", self.loader)
        self.assertNotIn("'/api/timeline'", self.loader)
        for path in ["'/api/dashboard'", "'/api/profile'", "'/api/compare'"]:
            self.assertNotIn(path, self.loader)
        self.assertNotIn("this.state.company", self.loader)

    def test_03_old_fixed_fallback_events_are_removed(self):
        combined = self.values + self.view
        for forbidden in [
            "瑞维鲁胺新适应症获批上市",
            "GLP-1 类创新药 III 期临床达主要终点",
            "收到交易所年报问询函",
            "应收账款周转放缓预警",
            "财务事件",
            "风险事件",
            "创新事件",
        ]:
            self.assertNotIn(forbidden, combined)

    def test_04_all_required_filters_and_auxiliary_switch_exist(self):
        for marker in [
            "timeline-company-select",
            "timeline-trial-select",
            "timeline-drug-select",
            "timeline-event-type-select",
            "timeline-year-select",
            "timeline-auxiliary-checkbox",
        ]:
            self.assertIn(marker, self.view)
        for parameter in ["trial_id", "drug", "event_type", "year", "include_auxiliary", "include_undated"]:
            self.assertIn(parameter, self.loader)
        self.assertIn("timelineIncludeAuxiliary:false", self.component)

    def test_05_dynamic_metrics_cover_events_trials_regulatory_and_undated(self):
        for label in ["核心事件", "唯一试验", "监管相关事件", "无日期资料", "辅助更新", "有日期来源"]:
            self.assertIn(label, self.values + self.view)
        for key in ["core_event_count", "unique_trial_count", "regulatory_event_count", "undated_source_count"]:
            self.assertIn(key, self.values)

    def test_06_event_cards_render_backend_date_semantics_and_regulatory_titles(self):
        self.assertIn("title:clean(event.title)", self.values)
        for marker in ["date.semantic", "date.precision", "date.field", "date.original_value", "source_last_updated"]:
            self.assertIn(marker, self.values)
        self.assertIn("页面更新时间：{{ e.source_last_updated }}，仅作为元信息，不是事件日期。", self.view)
        self.assertIn("{{ e.title }}", self.view)

    def test_07_version_progression_is_rendered_in_both_directions(self):
        self.assertIn("event.supersedes_source_id", self.values)
        self.assertIn("event.superseded_by_source_id", self.values)
        self.assertIn(" → ", self.values)
        self.assertIn("data-timeline-version", self.view)
        self.assertIn("版本演进", self.view)

    def test_08_source_chain_and_grounded_qa_entries_are_wired(self):
        for label in ["查看来源", "查看证据链", "进入循证问答"]:
            self.assertIn(label, self.view)
        self.assertIn("encodeURIComponent(cid)", self.component)
        self.assertIn("page:'evidence',evidenceTab:'sources'", self.component)
        self.assertIn("page:'groundedQa'", self.component)
        self.assertIn("this.openGroundedQa(question)", self.component)

    def test_09_undated_sources_have_required_notice_and_are_separate(self):
        self.assertIn("无日期资料未进入时间轴，不代表事件不存在。", self.values)
        self.assertIn("data-timeline-undated", self.view)
        self.assertIn("{{ u.reason }}", self.view)

    def test_10_loading_empty_and_error_states_are_friendly(self):
        for text in [
            "正在加载真实研发事件与无日期资料",
            "研发事件时间轴加载失败，请稍后重试",
            "当前数据不足",
            "重试",
            "重置筛选",
        ]:
            self.assertIn(text, self.component + self.view)

    def test_11_timeline_path_has_no_unsafe_or_claim_language(self):
        combined = self.loader + self.values + self.view
        for forbidden in [
            "innerHTML",
            "eval(",
            "Math.random",
            "MOCK",
            "领先",
            "成功率",
            "疗效优劣",
            "投资建议",
            "综合评分",
            "ranking",
        ]:
            self.assertNotIn(forbidden, combined)

    def test_12_narrow_screen_rules_cover_filters_metrics_layout_and_events(self):
        for selector in [
            "[data-timeline-filters]",
            "[data-timeline-grid]",
            "[data-timeline-layout]",
            "[data-timeline-event]",
        ]:
            self.assertIn(selector, self.template)
        self.assertIn("@media(max-width:640px)", self.template)

    def test_13_build_artifact_matches_frontend_sources(self):
        self.assertEqual(self.template.replace("/*__COMPONENT__*/", self.component), self.index)


if __name__ == "__main__":
    unittest.main()
