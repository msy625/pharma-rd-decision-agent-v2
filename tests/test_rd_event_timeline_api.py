import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


from deepinsight.core.source_registry_service import SourceRegistryFileNotFound, SourceRegistryStructureError
from tests.test_deployment_health import _ASGIClient
from webapp import main as webapp_main


class RDEventTimelineApiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = _ASGIClient(webapp_main.app)

    def test_01_global_endpoint_returns_dynamic_baseline(self):
        response = self.client.get("/api/evidence/timeline")
        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        summary = payload["timeline"]["summary"]
        self.assertEqual(summary["total_source_count"], 39)
        self.assertEqual(summary["dated_source_count"], 16)
        self.assertEqual(summary["core_event_count"], 15)
        self.assertEqual(summary["auxiliary_event_count"], 1)
        self.assertEqual(summary["undated_source_count"], 23)
        self.assertEqual(payload["metadata"]["data_scope"], "verified_nsclc_multi_company_sample")

    def test_02_company_path_supports_chinese_and_english_aliases(self):
        hengrui = self.client.get("/api/evidence/timeline/%E6%81%92%E7%91%9E%E5%8C%BB%E8%8D%AF")
        beone = self.client.get("/api/evidence/timeline/BeOne%20Medicines")
        former = self.client.get("/api/evidence/timeline/BeiGene")
        astrazeneca = self.client.get("/api/evidence/timeline/AstraZeneca")
        self.assertEqual(hengrui.json()["timeline"]["summary"]["core_event_count"], 2)
        self.assertEqual(beone.json()["timeline"]["summary"]["core_event_count"], 9)
        self.assertEqual(former.json()["timeline"]["company"]["canonical_name"], "百济神州")
        self.assertEqual(astrazeneca.json()["timeline"]["summary"]["core_event_count"], 4)

    def test_03_query_company_alias_is_normalized(self):
        response = self.client.get("/api/evidence/timeline?company=%E7%99%BE%E6%B5%8E%E7%A5%9E%E5%B7%9E")
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["timeline"]["company"]["canonical_name"], "百济神州")

    def test_04_unknown_company_returns_friendly_200_empty_timeline(self):
        response = self.client.get("/api/evidence/timeline/%E4%B8%8D%E5%AD%98%E5%9C%A8%E4%BC%81%E4%B8%9A")
        self.assertEqual(response.status_code, 200, response.text)
        timeline = response.json()["timeline"]
        self.assertEqual(timeline["events"], [])
        self.assertEqual(timeline["summary"]["event_count"], 0)
        self.assertIn("当前数据不足", timeline["limitations"][0])

    def test_05_trial_drug_event_type_and_year_filters(self):
        trial = self.client.get("/api/evidence/timeline?trial_id=NCT03663205")
        self.assertEqual({event["source_id"] for event in trial.json()["timeline"]["events"]}, {"B006", "B007"})
        drug = self.client.get("/api/evidence/timeline?drug=TEVIMBRA")
        self.assertIn("B015", {event["source_id"] for event in drug.json()["timeline"]["events"]})
        event_type = self.client.get("/api/evidence/timeline?event_type=final_analysis")
        self.assertEqual({event["source_id"] for event in event_type.json()["timeline"]["events"]}, {"B007", "B009"})
        year = self.client.get("/api/evidence/timeline?year=2024")
        self.assertEqual({event["source_id"] for event in year.json()["timeline"]["events"]}, {"A006", "B007", "B009", "B011"})

    def test_06_auxiliary_and_undated_switches(self):
        default = self.client.get("/api/evidence/timeline")
        auxiliary = self.client.get("/api/evidence/timeline?include_auxiliary=true")
        no_undated = self.client.get("/api/evidence/timeline?include_undated=false")
        self.assertNotIn("B014", {event["source_id"] for event in default.json()["timeline"]["events"]})
        self.assertIn("B014", {event["source_id"] for event in auxiliary.json()["timeline"]["events"]})
        self.assertEqual(no_undated.json()["timeline"]["undated_sources"], [])
        self.assertEqual(no_undated.json()["timeline"]["summary"]["undated_source_count"], 23)

    def test_07_b015_and_b016_regulatory_language_is_preserved(self):
        response = self.client.get("/api/evidence/timeline/BeOne%20Medicines")
        events = {event["source_id"]: event for event in response.json()["timeline"]["events"]}
        self.assertEqual(events["B015"]["date"]["value"], "2023-09-15")
        self.assertIn("Tevimbra欧盟初始许可", events["B015"]["title"])
        self.assertEqual(events["B015"]["source_last_updated"], "2026-05-27")
        self.assertEqual(events["B016"]["date"]["value"], "2025-07-24")
        self.assertIn("CHMP积极意见，非最终批准", events["B016"]["title"])

    def test_08_missing_file_returns_sanitized_503(self):
        with patch.object(
            webapp_main,
            "_rd_event_timeline_service",
            side_effect=SourceRegistryFileNotFound("/private/path/source_registry.csv"),
        ):
            response = self.client.get("/api/evidence/timeline")
        self.assertEqual(response.status_code, 503, response.text)
        self.assertIn("证据资料文件不可用", response.text)
        self.assertNotIn("/private/path", response.text)

    def test_09_structure_error_returns_sanitized_503(self):
        with patch.object(
            webapp_main,
            "_rd_event_timeline_service",
            side_effect=SourceRegistryStructureError("bad columns at /private/path"),
        ):
            response = self.client.get("/api/evidence/timeline/BeOne%20Medicines")
        self.assertEqual(response.status_code, 503, response.text)
        self.assertIn("证据资料结构异常", response.text)
        self.assertNotIn("/private/path", response.text)

    def test_10_unknown_error_returns_sanitized_500(self):
        with patch.object(
            webapp_main,
            "_rd_event_timeline_service",
            side_effect=RuntimeError("sk-secret /home/user/private traceback"),
        ):
            response = self.client.get("/api/evidence/timeline")
        self.assertEqual(response.status_code, 500, response.text)
        for forbidden in ["sk-secret", "/home/user", "traceback"]:
            self.assertNotIn(forbidden, response.text.lower())

    def test_11_runtime_capability_is_independent_from_legacy(self):
        with patch.object(webapp_main, "_legacy_features_available", return_value=False):
            response = self.client.get("/api/runtime-capabilities")
        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertTrue(payload["rd_event_timeline_available"])
        self.assertFalse(payload["legacy_features_available"])

    def test_12_new_timeline_does_not_create_deepseek_or_call_old_timeline(self):
        with patch.object(webapp_main, "_create_optional_client", side_effect=AssertionError("must not create client")), patch.object(
            webapp_main, "fetch_company_timeline_dashboard", side_effect=AssertionError("must not call old timeline")
        ):
            response = self.client.get("/api/evidence/timeline")
        self.assertEqual(response.status_code, 200, response.text)

    def test_13_new_timeline_does_not_load_heavy_modules(self):
        blocked = {"openai", "chromadb", "sentence_transformers", "torch", "deepinsight.core.retriever"}
        before = {name for name in blocked if name in sys.modules}
        response = self.client.get("/api/evidence/timeline")
        self.assertEqual(response.status_code, 200, response.text)
        after = {name for name in blocked if name in sys.modules}
        self.assertEqual(after - before, set())

    def test_14_response_is_json_and_does_not_leak_paths_or_secrets(self):
        response = self.client.get("/api/evidence/timeline")
        self.assertEqual(response.status_code, 200, response.text)
        home_marker = "/" + "home" + "/"
        for forbidden in [str(ROOT), home_marker, "DEEPSEEK_API_KEY", "sk-"]:
            self.assertNotIn(forbidden, response.text)
        json.loads(response.text)


if __name__ == "__main__":
    unittest.main()
