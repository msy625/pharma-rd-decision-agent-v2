import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


from deepinsight.core.harvested_registry_adapter import HARVESTED_STATUS
from deepinsight.core.source_registry_service import SourceRegistryService
from tests.test_deployment_health import _ASGIClient
from webapp import main as webapp_main


VERIFIED_TOTAL = 39


class SourceRegistrySwitchTest(unittest.TestCase):
    """The include_harvested switch must be strictly additive and default off."""

    def test_01_default_service_returns_only_verified_sources(self):
        service = SourceRegistryService()
        rows = service.load_rows()
        self.assertEqual(len(rows), VERIFIED_TOTAL)
        self.assertTrue(all(row["verification_status"] != HARVESTED_STATUS for row in rows))

    def test_02_switch_on_appends_harvested_rows(self):
        service = SourceRegistryService(include_harvested=True)
        rows = service.load_rows()
        self.assertGreater(len(rows), VERIFIED_TOTAL)
        harvested = [r for r in rows if r["verification_status"] == HARVESTED_STATUS]
        self.assertGreater(len(harvested), 2000)
        self.assertEqual(len(rows) - len(harvested), VERIFIED_TOTAL)

    def test_03_verified_rows_stay_first_and_unchanged(self):
        plain = SourceRegistryService().load_rows()
        extended = SourceRegistryService(include_harvested=True).load_rows()
        self.assertEqual(extended[: len(plain)], plain)

    def test_04_harvested_rows_keep_the_legacy_column_shape(self):
        service = SourceRegistryService(include_harvested=True)
        fieldnames = set(service.load_rows()[0].keys())
        harvested = [r for r in service.load_rows() if r["verification_status"] == HARVESTED_STATUS]
        self.assertTrue(harvested)
        for row in harvested[:200]:
            with self.subTest(source_id=row["source_id"]):
                self.assertEqual(set(row.keys()), fieldnames)
                self.assertTrue(row["source_id"].startswith(("SRC_CTG_", "SRC_PM_")))
                self.assertTrue(row["url"].startswith("http"))
                self.assertTrue(row["disease"])
                self.assertTrue(row["scope_limitation"])

    def test_05_trials_and_publications_map_to_legacy_source_types(self):
        service = SourceRegistryService(include_harvested=True)
        harvested = [r for r in service.load_rows() if r["verification_status"] == HARVESTED_STATUS]
        trials = [r for r in harvested if r["source_id"].startswith("SRC_CTG_")]
        papers = [r for r in harvested if r["source_id"].startswith("SRC_PM_")]
        self.assertTrue(trials)
        self.assertTrue(papers)
        self.assertTrue(all(r["source_type"] == "ClinicalTrials.gov" for r in trials))
        self.assertTrue(all(r["source_type"] == "PubMed" for r in papers))
        self.assertTrue(all(r["registry_id"].startswith("NCT") for r in trials))
        self.assertTrue(all(r["pmid"].isdigit() for r in papers))

    def test_06_queries_reach_harvested_rows(self):
        service = SourceRegistryService(include_harvested=True)
        self.assertTrue(service.query(source_type="PubMed"))
        self.assertTrue(service.query(drug="Pembrolizumab"))
        self.assertTrue(service.query(company="辉瑞"))

    def test_07_harvested_rows_are_marked_by_scope_note(self):
        service = SourceRegistryService(include_harvested=True)
        harvested = [r for r in service.load_rows() if r["verification_status"] == HARVESTED_STATUS]
        for row in harvested[:100]:
            with self.subTest(source_id=row["source_id"]):
                self.assertIn("api_harvested", row["notes"])
                self.assertIn("未经人工逐条复核", row["notes"])

    def test_08_missing_direction_dataset_does_not_break_the_verified_layer(self):
        service = SourceRegistryService(include_harvested=True)
        service._rows = None
        rows = service.load_rows()
        # Whether or not the direction dataset is present, verified rows must survive.
        self.assertGreaterEqual(len(rows), VERIFIED_TOTAL)


class IncludeHarvestedApiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = _ASGIClient(webapp_main.app)

    def get_json(self, path: str):
        response = self.client.get(path)
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def test_10_summary_defaults_to_verified_only(self):
        payload = self.get_json("/api/evidence/summary")
        self.assertEqual(payload["total_sources"], VERIFIED_TOTAL)
        self.assertFalse(payload["include_harvested"])
        self.assertEqual(payload["verified_source_count"], VERIFIED_TOTAL)
        self.assertEqual(payload["harvested_source_count"], 0)
        self.assertIn("人工核验来源", payload["data_scope"])
        self.assertEqual(payload["metadata"]["data_source"], "source_registry.csv")

    def test_11_summary_with_switch_includes_harvested(self):
        payload = self.get_json("/api/evidence/summary?include_harvested=true")
        self.assertTrue(payload["include_harvested"])
        self.assertEqual(payload["verified_source_count"], VERIFIED_TOTAL)
        self.assertGreater(payload["harvested_source_count"], 2000)
        self.assertEqual(
            payload["total_sources"],
            payload["verified_source_count"] + payload["harvested_source_count"],
        )
        self.assertIn("机器采集", payload["data_scope"])
        self.assertEqual(payload["metadata"]["data_source"], "source_registry.csv + data/template")

    def test_12_search_switch_changes_result_set(self):
        default = self.get_json("/api/evidence/search?q=Pembrolizumab")
        extended = self.get_json("/api/evidence/search?q=Pembrolizumab&include_harvested=true")
        self.assertGreater(extended["count"], default["count"])
        self.assertTrue(extended["query"]["include_harvested"])

    def test_13_search_default_is_unchanged(self):
        payload = self.get_json("/api/evidence/search?q=NSCLC")
        for item in payload["items"]:
            with self.subTest(source_id=item["source_id"]):
                self.assertNotEqual(item["verification_status"], HARVESTED_STATUS)

    def test_14_workbench_accepts_the_switch(self):
        default = self.get_json("/api/evidence/workbench")
        extended = self.get_json("/api/evidence/workbench?include_harvested=true")
        self.assertFalse(default["include_harvested"])
        self.assertTrue(extended["include_harvested"])

    def test_15_company_profile_accepts_the_switch(self):
        default = self.get_json("/api/evidence/company-profile/%E6%81%92%E7%91%9E%E5%8C%BB%E8%8D%AF")
        extended = self.get_json(
            "/api/evidence/company-profile/%E6%81%92%E7%91%9E%E5%8C%BB%E8%8D%AF?include_harvested=true"
        )
        self.assertFalse(default["include_harvested"])
        self.assertTrue(extended["include_harvested"])

    def test_16_timeline_accepts_the_switch(self):
        default = self.get_json("/api/evidence/timeline")
        extended = self.get_json("/api/evidence/timeline?include_harvested=true")
        self.assertFalse(default["include_harvested"])
        self.assertTrue(extended["include_harvested"])

    def test_17_initial_state_matches_the_workbench_endpoint(self):
        initial = self.get_json("/api/initial-state")["evidence_workbench"]
        standalone = self.get_json("/api/evidence/workbench")
        self.assertEqual(initial["include_harvested"], standalone["include_harvested"])

    def test_18_grounded_qa_stays_on_verified_evidence(self):
        """QA must not silently start citing unreviewed machine-harvested rows."""
        import inspect

        signature = inspect.signature(webapp_main._grounded_qa_service)
        self.assertNotIn("include_harvested", signature.parameters)

    # ------------------------------------------------------------------ #
    # The five lookup endpoints behind 来源检索 must honour the switch too,
    # otherwise the toggle silently does nothing for those query modes.
    # ------------------------------------------------------------------ #
    def _count(self, path: str) -> int:
        return self.get_json(path)["count"]

    def test_19_company_lookup_honours_the_switch(self):
        off = self._count("/api/evidence/company/%E6%81%92%E7%91%9E%E5%8C%BB%E8%8D%AF")
        on = self._count("/api/evidence/company/%E6%81%92%E7%91%9E%E5%8C%BB%E8%8D%AF?include_harvested=true")
        self.assertGreaterEqual(on, off)
        self.assertGreater(on, off, "company lookup ignored include_harvested")

    def test_20_drug_lookup_honours_the_switch(self):
        off = self._count("/api/evidence/drug/%E5%8D%A1%E7%91%9E%E5%88%A9%E7%8F%A0%E5%8D%95%E6%8A%97")
        on = self._count("/api/evidence/drug/%E5%8D%A1%E7%91%9E%E5%88%A9%E7%8F%A0%E5%8D%95%E6%8A%97?include_harvested=true")
        self.assertGreaterEqual(on, off)

    def test_21_trial_lookup_honours_the_switch(self):
        off = self._count("/api/evidence/trial/NCT04379635")
        on = self._count("/api/evidence/trial/NCT04379635?include_harvested=true")
        self.assertGreaterEqual(on, off)

    def test_22_study_lookup_honours_the_switch(self):
        off = self._count("/api/evidence/study/CameL")
        on = self._count("/api/evidence/study/CameL?include_harvested=true")
        self.assertGreaterEqual(on, off)

    def test_23_harvested_records_accept_the_flag_in_the_query_echo(self):
        payload = self.get_json("/api/evidence/company/%E6%81%92%E7%91%9E%E5%8C%BB%E8%8D%AF?include_harvested=true")
        self.assertTrue(payload["query"]["include_harvested"])

    def test_24_source_detail_resolves_harvested_ids_with_the_switch(self):
        """Every harvested row is clickable in the UI, so its detail must resolve."""
        listed = self.get_json("/api/evidence/search?q=Pembrolizumab&include_harvested=true")
        harvested = [i for i in listed["items"] if i["verification_status"] == HARVESTED_STATUS]
        self.assertTrue(harvested)
        source_id = harvested[0]["source_id"]

        response = self.client.get(f"/api/evidence/source/{source_id}?include_harvested=true")
        self.assertEqual(response.status_code, 200, response.text)
        item = response.json()["item"]
        self.assertEqual(item["source_id"], source_id)
        self.assertEqual(item["verification_status"], HARVESTED_STATUS)
        self.assertTrue(item["source_url"].startswith("http"))

    def test_25_source_detail_for_harvested_id_is_404_without_the_switch(self):
        """Documents the contract: harvested ids are only visible when opted in."""
        listed = self.get_json("/api/evidence/search?q=Pembrolizumab&include_harvested=true")
        source_id = next(i for i in listed["items"] if i["verification_status"] == HARVESTED_STATUS)["source_id"]
        response = self.client.get(f"/api/evidence/source/{source_id}")
        self.assertEqual(response.status_code, 404)

    def test_26_verified_source_detail_still_works_by_default(self):
        response = self.client.get("/api/evidence/source/B015")
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["item"]["source_id"], "B015")

    def test_27_harvested_rows_are_independent_not_latest(self):
        """A harvested row has no version relation, so it is 独立资料, not 最新版本."""
        service = SourceRegistryService(include_harvested=True)
        harvested = [r for r in service.load_rows() if r["verification_status"] == HARVESTED_STATUS]
        self.assertTrue(harvested)
        for row in harvested[:200]:
            with self.subTest(source_id=row["source_id"]):
                self.assertEqual(row["is_latest_evidence"], "")

    def test_28_harvested_rows_are_not_excluded_by_latest_only(self):
        """Verified rows include historical versions; harvested rows must not be dropped."""
        service = SourceRegistryService(include_harvested=True)

        def harvested_count(rows):
            return sum(1 for r in rows if r["verification_status"] == HARVESTED_STATUS)

        everything = service.query(source_type="PubMed", normalized=False)
        latest_only = service.query(source_type="PubMed", latest_only=True, normalized=False)
        self.assertGreater(harvested_count(everything), 0)
        self.assertEqual(harvested_count(latest_only), harvested_count(everything))

    def test_29_company_profile_lists_harvested_rows_when_opted_in(self):
        """The 企业证据画像 row list must actually contain harvested rows."""
        from deepinsight.core.company_evidence_profile_service import CompanyEvidenceProfileService
        from deepinsight.core.evidence_chain_service import EvidenceChainService

        counts = {}
        for flag in (False, True):
            source = SourceRegistryService(include_harvested=flag)
            profile = CompanyEvidenceProfileService(
                source_registry_service=source,
                evidence_chain_service=EvidenceChainService(source_registry_service=source),
            ).build_profile("恒瑞医药")
            counts[flag] = len(profile.get("independent_sources", []))
        self.assertGreater(counts[True], counts[False])


if __name__ == "__main__":
    unittest.main()
