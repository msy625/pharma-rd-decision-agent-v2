import csv
import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
COMPONENT = ROOT / "webapp" / "frontend_src" / "component.js"
TEMPLATE = ROOT / "webapp" / "frontend_src" / "template.html"
STATIC_INDEX = ROOT / "webapp" / "static" / "index.html"
BUILD_SCRIPT = ROOT / "webapp" / "frontend_src" / "build.py"
SOURCE_REGISTRY = ROOT / "data" / "source_registry.csv"


def parse_version_state(value):
    if value is True or value == 1:
        return "最新版本"
    if value is False or value == 0:
        return "历史版本"
    text = "" if value is None else str(value).strip().lower()
    if text in {"true", "1"}:
        return "最新版本"
    if text in {"false", "0"}:
        return "历史版本"
    return "独立资料"


class EvidenceFrontendStaticTest(unittest.TestCase):
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
        with SOURCE_REGISTRY.open(encoding="utf-8", newline="") as fh:
            cls.registry_rows = list(csv.DictReader(fh))

    def test_evidence_nav_exists_in_required_position(self):
        timeline = self.component.index("label:'研发事件时间轴'")
        evidence = self.component.index("label:'研发证据中心'")
        grounded = self.component.index("label:'循证问答'")
        self.assertLess(timeline, evidence)
        self.assertLess(evidence, grounded)

    def test_primary_nav_labels_still_exist(self):
        nav = self.component[self.component.index("  navDef(){") : self.component.index("  navItem(it){")]
        for label in ["研发决策总览", "企业证据画像", "研发事件时间轴", "研发证据中心", "循证问答"]:
            self.assertIn(label, nav)

    def test_evidence_state_fields_exist(self):
        for name in [
            "evidenceKind", "evidenceQuery", "evidenceLatestOnly", "evidenceLimit",
            "evidenceSummary", "evidenceItems", "evidenceCount", "evidenceSelected",
            "evidenceLoading", "evidenceSummaryLoading", "evidenceDetailLoading",
            "evidenceError", "evidenceHasSearched", "isEvidence",
        ]:
            self.assertIn(name, self.component)

    def test_all_evidence_api_paths_exist(self):
        for path in [
            "/api/evidence/summary", "/api/evidence/search",
            "/api/evidence/company/", "/api/evidence/drug/",
            "/api/evidence/trial/", "/api/evidence/study/",
            "/api/evidence/source/",
        ]:
            self.assertIn(path, self.evidence_component)

    def test_path_params_use_encode_uri_component(self):
        self.assertIn("encodeURIComponent", self.evidence_component)

    def test_uses_existing_api_get_wrapper_only(self):
        self.assertIn("this._api(", self.evidence_component)
        self.assertNotIn("_apiPost", self.evidence_component)

    def test_template_contains_loading_prompts(self):
        for text in ["统计加载中", "查询加载中", "详情加载中"]:
            self.assertIn(text, self.evidence_template)

    def test_filter_copy_describes_excluding_history_only(self):
        self.assertIn("排除历史版本", self.evidence_template)
        self.assertIn("保留最新版本和没有版本关系的独立资料。", self.evidence_template)
        self.assertNotIn("仅显示最新证据", self.evidence_template)

    def test_template_contains_empty_result_prompt(self):
        self.assertIn("空结果", self.evidence_template)
        self.assertIn("未找到符合条件的证据", self.evidence_template)

    def test_template_contains_error_prompt(self):
        self.assertIn("ev_hasError", self.evidence_template)
        self.assertIn("ev_error", self.evidence_template)

    def test_template_contains_result_and_detail_regions(self):
        self.assertIn("data-evidence-results", self.evidence_template)
        self.assertIn("data-evidence-detail", self.evidence_template)

    def test_external_link_uses_noopener_noreferrer(self):
        self.assertIn('target="_blank"', self.evidence_template)
        self.assertIn('rel="noopener noreferrer"', self.evidence_template)

    def test_external_link_is_limited_to_http_https(self):
        self.assertIn("_safeEvidenceUrl", self.evidence_component)
        self.assertRegex(self.evidence_component, r"\^https\?:")

    def test_evidence_page_has_no_mock_result_text(self):
        forbidden = ["MOCK", "mock", "Mock", "模拟结果", "Demo Data"]
        for word in forbidden:
            self.assertNotIn(word, self.evidence_all)

    def test_evidence_page_has_no_random_or_fixed_rating(self):
        forbidden = ["Math.random", "random", "评分", "score", "0～100", "星级", "成功概率", "投资判断", "治疗建议"]
        for word in forbidden:
            self.assertNotIn(word, self.evidence_all)

    def test_version_state_parser_is_explicit_three_state_logic(self):
        for snippet in [
            "_evidenceVersion(value)",
            "raw===true || raw===1",
            "raw===false || raw===0",
            "v==='true' || v==='1'",
            "v==='false' || v==='0'",
            "独立资料",
            "_filterEvidenceItems(items)",
        ]:
            self.assertIn(snippet, self.evidence_component)
        self.assertNotIn("Boolean(", self.evidence_component)

    def test_expected_source_version_labels_from_registry(self):
        rows = {row["source_id"]: row for row in self.registry_rows}
        self.assertEqual(parse_version_state(rows["B006"]["is_latest_evidence"]), "历史版本")
        self.assertEqual(parse_version_state(rows["B007"]["is_latest_evidence"]), "最新版本")
        self.assertEqual(parse_version_state(rows["H007"]["is_latest_evidence"]), "独立资料")
        self.assertEqual(parse_version_state(rows["H013"]["is_latest_evidence"]), "独立资料")

    def test_rationale_304_filter_excludes_only_explicit_history(self):
        rows = [row for row in self.registry_rows if row["study_name"] == "RATIONALE-304"]
        unfiltered_ids = {row["source_id"] for row in rows}
        filtered_ids = {row["source_id"] for row in rows if parse_version_state(row["is_latest_evidence"]) != "历史版本"}
        self.assertIn("B006", unfiltered_ids)
        self.assertIn("B007", unfiltered_ids)
        self.assertNotIn("B006", filtered_ids)
        self.assertIn("B007", filtered_ids)

    def test_nsclc_filter_keeps_independent_sources(self):
        rows = [row for row in self.registry_rows if "NSCLC" in row["disease"] or "非小细胞肺癌" in row["disease"]]
        filtered_ids = {row["source_id"] for row in rows if parse_version_state(row["is_latest_evidence"]) != "历史版本"}
        self.assertIn("H007", filtered_ids)
        self.assertIn("H013", filtered_ids)
        self.assertEqual(parse_version_state(next(row for row in rows if row["source_id"] == "H007")["is_latest_evidence"]), "独立资料")
        self.assertEqual(parse_version_state(next(row for row in rows if row["source_id"] == "H013")["is_latest_evidence"]), "独立资料")

    def test_evidence_page_does_not_call_model_or_vector_routes(self):
        forbidden = ["_apiPost", "/api/chat", "/api/workflow", "/api/advanced", "Chroma", "vector", "向量模型", "大模型"]
        for word in forbidden:
            self.assertNotIn(word, self.evidence_component)

    def test_evidence_page_avoids_unsafe_dom_apis(self):
        forbidden = ["innerHTML", "eval(", "new Function", "document.write"]
        for word in forbidden:
            self.assertNotIn(word, self.evidence_all)

    def test_static_index_contains_generated_evidence_page(self):
        self.assertIn("研发证据中心", self.static_index)
        self.assertIn("data-evidence-results", self.static_index)
        self.assertIn("/api/evidence/search", self.static_index)

    def test_static_index_is_built_from_source(self):
        self.assertTrue(BUILD_SCRIPT.exists())
        self.assertNotIn("/*__COMPONENT__*/", self.static_index)
        self.assertIn("loadEvidenceSummary()", self.static_index)

    def test_original_page_condition_blocks_still_exist(self):
        for name in ["isToday", "isChat", "isCompare", "isResearch", "isWhitebox", "isDatabase", "isTimeline", "isAdvanced"]:
            self.assertIn(name, self.component)
            self.assertIn(f'value="{{{{ {name} }}}}"', self.template)


if __name__ == "__main__":
    unittest.main()
