import sys
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.parse import quote, urlencode


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


from tests.test_deployment_health import _ASGIClient
from webapp import main as webapp_main


def _with_query(path: str, **params) -> str:
    """The shared ASGI test client only accepts a path, so build the query here.

    ``quote_via=quote`` keeps spaces as ``%20``; ``urlencode``'s default ``+``
    would be re-encoded to ``%2B`` by the test client's raw_path quoting.
    """
    pairs = [(key, str(value)) for key, value in params.items() if value is not None]
    if not pairs:
        return path
    return f"{path}?{urlencode(pairs, quote_via=quote)}"


class DirectionDatasetApiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = _ASGIClient(webapp_main.app)

    def get_json(self, path: str, **params):
        response = self.client.get(_with_query(path, **params))
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    # ------------------------------------------------------------------ #
    def test_01_roadmap_exposes_six_stages_and_twenty_directions(self):
        payload = self.get_json("/api/directions/roadmap")
        self.assertEqual(payload["total_stages"], 6)
        self.assertEqual(payload["total_directions"], 20)
        self.assertEqual(len(payload["stages"]), 6)
        self.assertEqual(sum(len(s["directions"]) for s in payload["stages"]), 20)

    def test_02_roadmap_directions_stay_within_the_30_to_110_range(self):
        payload = self.get_json("/api/directions/roadmap")
        for stage in payload["stages"]:
            for direction in stage["directions"]:
                with self.subTest(direction=direction["direction_id"]):
                    self.assertGreaterEqual(direction["source_count"], 30)
                    self.assertLessEqual(direction["source_count"], 110)

    def test_03_roadmap_carries_the_stage_goals_from_the_catalog(self):
        payload = self.get_json("/api/directions/roadmap")
        goals = [stage["goal"] for stage in payload["stages"]]
        self.assertIn("建立肿瘤研发竞争分析闭环", goals)
        self.assertIn("加入自然史、孤儿药和特殊监管路径", goals)

    def test_04_roadmap_stage_totals_reconcile(self):
        payload = self.get_json("/api/directions/roadmap")
        self.assertEqual(
            sum(stage["source_count"] for stage in payload["stages"]),
            payload["total_records"],
        )

    def test_05_records_endpoint_returns_direction_metadata_and_items(self):
        payload = self.get_json("/api/directions/records", direction_id="breast_cancer", limit=5)
        self.assertEqual(payload["direction"]["direction_id"], "DOM_BREAST_CANCER")
        self.assertEqual(payload["limit"], 5)
        self.assertLessEqual(payload["count"], 5)
        self.assertGreater(payload["total"], 0)
        for item in payload["items"]:
            self.assertEqual(item["direction_id"], "DOM_BREAST_CANCER")
            self.assertTrue(item["url"].startswith("http"))

    def test_06_records_endpoint_supports_type_phase_status_and_text_filters(self):
        trials = self.get_json("/api/directions/records", record_type="clinical_trial", limit=3)
        self.assertTrue(trials["items"])
        self.assertTrue(all(item["record_type"] == "clinical_trial" for item in trials["items"]))

        publications = self.get_json("/api/directions/records", record_type="publication", limit=3)
        self.assertTrue(publications["items"])
        self.assertTrue(all(item["record_type"] == "publication" for item in publications["items"]))

        phase3 = self.get_json("/api/directions/records", phase="Phase 3", limit=3)
        self.assertGreater(phase3["total"], 0)
        self.assertTrue(all("Phase 3" in item["phase"] for item in phase3["items"]))

        completed = self.get_json("/api/directions/records", study_status="Completed", limit=3)
        self.assertGreater(completed["total"], 0)

        by_nct = self.get_json("/api/directions/records", q="NCT04", limit=3)
        self.assertGreater(by_nct["total"], 0)

    def test_07_records_endpoint_paginates(self):
        first = self.get_json("/api/directions/records", direction_id="nsclc", limit=5, offset=0)
        second = self.get_json("/api/directions/records", direction_id="nsclc", limit=5, offset=5)
        self.assertEqual(first["offset"], 0)
        self.assertEqual(second["offset"], 5)
        self.assertTrue(first["has_more"])
        self.assertNotEqual(
            [i["record_id"] for i in first["items"]],
            [i["record_id"] for i in second["items"]],
        )

    def test_08_records_endpoint_filters_by_stage(self):
        payload = self.get_json("/api/directions/records", stage_id="DOM_STAGE_6", limit=5)
        self.assertGreater(payload["total"], 0)
        self.assertTrue(all(item["stage_id"] == "DOM_STAGE_6" for item in payload["items"]))

    def test_09_filters_endpoint_lists_real_values(self):
        options = self.get_json("/api/directions/filters")["options"]
        self.assertIn("Phase 3", options["phase"])
        self.assertEqual(len(options["direction"]), 20)
        self.assertEqual(len(options["stage"]), 6)
        self.assertTrue(options["company"])

    def test_10_summary_endpoint_reconciles_counts(self):
        payload = self.get_json("/api/directions/summary")
        self.assertEqual(payload["stage_count"], 6)
        self.assertEqual(payload["direction_count"], 20)
        self.assertEqual(payload["trial_count"] + payload["publication_count"], payload["total_records"])

    def test_11_roadmap_uses_the_single_verified_policy(self):
        payload = self.get_json("/api/directions/roadmap")
        self.assertEqual(payload["metadata"]["interpretation_scope"], "manually_reviewed_records_only")
        self.assertEqual(set(payload["verification_status_counts"]), {"verified"})

    def test_12_runtime_capabilities_reports_direction_dataset(self):
        response = self.client.get("/api/runtime-capabilities")
        self.assertEqual(response.status_code, 200, response.text)
        self.assertTrue(response.json()["direction_dataset_available"])

    def test_13_missing_catalog_returns_503_not_500(self):
        from deepinsight.core.direction_dataset_service import DirectionDatasetFileNotFound

        with patch.object(
            webapp_main,
            "_direction_dataset_service",
            side_effect=DirectionDatasetFileNotFound("config/direction_catalog.json"),
        ):
            response = self.client.get("/api/directions/roadmap")
        self.assertEqual(response.status_code, 503)
        self.assertIn("疾病方向数据", response.json()["detail"])

    def test_14_malformed_table_returns_503_not_500(self):
        from deepinsight.core.direction_dataset_service import DirectionDatasetStructureError

        with patch.object(
            webapp_main,
            "_direction_dataset_service",
            side_effect=DirectionDatasetStructureError("domains.csv"),
        ):
            response = self.client.get("/api/directions/records")
        self.assertEqual(response.status_code, 503)

    def test_15_unknown_direction_returns_empty_page_not_error(self):
        payload = self.get_json("/api/directions/records", direction_id="not_a_direction")
        self.assertEqual(payload["total"], 0)
        self.assertEqual(payload["items"], [])

    def test_16_limit_is_clamped_to_a_safe_maximum(self):
        payload = self.get_json("/api/directions/records", limit=100000)
        self.assertLessEqual(payload["limit"], 500)

    def test_17_direction_records_keep_their_own_upstream_identifier(self):
        payload = self.get_json("/api/directions/records", record_type="clinical_trial", limit=50)
        checked = 0
        for item in payload["items"]:
            if item["registry_id"]:
                with self.subTest(record=item["record_id"]):
                    self.assertIn(item["registry_id"], item["url"])
                checked += 1
        self.assertGreater(checked, 0)

    def test_18_publication_records_link_to_pubmed(self):
        payload = self.get_json("/api/directions/records", record_type="publication", limit=50)
        checked = 0
        for item in payload["items"]:
            if item["pmid"]:
                with self.subTest(record=item["record_id"]):
                    self.assertIn(item["pmid"], item["url"])
                    self.assertIn("pubmed.ncbi.nlm.nih.gov", item["url"])
                checked += 1
        self.assertGreater(checked, 0)


if __name__ == "__main__":
    unittest.main()
