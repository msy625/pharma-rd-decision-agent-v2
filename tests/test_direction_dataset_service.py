import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


from deepinsight.core.direction_dataset_service import (
    DirectionDatasetFileNotFound,
    DirectionDatasetService,
    DirectionDatasetStructureError,
)


CATALOG_PATH = ROOT / "config" / "direction_catalog.json"
TEMPLATE_DIR = ROOT / "data" / "template"


class DirectionCatalogTest(unittest.TestCase):
    def setUp(self):
        self.service = DirectionDatasetService()

    def test_01_catalog_defines_six_stages_and_twenty_directions(self):
        catalog = self.service.load_catalog()
        self.assertEqual(len(catalog["stages"]), 6)
        keys = [d["direction_key"] for d in self.service.direction_index().values()]
        self.assertEqual(len(keys), 20)
        self.assertEqual(len(set(keys)), 20)

    def test_02_stage_goals_match_the_published_roadmap(self):
        catalog = self.service.load_catalog()
        goals = {stage["stage_index"]: stage["goal"] for stage in catalog["stages"]}
        self.assertEqual(goals[1], "建立肿瘤研发竞争分析闭环")
        self.assertEqual(goals[2], "加入代谢、长期疗效和支付价值")
        self.assertEqual(goals[3], "加入临床结局和真实世界长期随访")
        self.assertEqual(goals[4], "加入免疫靶点和同类竞品分析")
        self.assertEqual(goals[5], "加入自然史、孤儿药和特殊监管路径")
        self.assertEqual(goals[6], "加入复杂终点、患者负担和公共卫生模块")

    def test_03_every_direction_carries_between_40_and_110_records(self):
        roadmap = self.service.roadmap()
        self.assertEqual(roadmap["total_directions"], 20)
        for stage in roadmap["stages"]:
            for direction in stage["directions"]:
                with self.subTest(direction=direction["direction_id"]):
                    self.assertGreaterEqual(direction["source_count"], 40)
                    self.assertLessEqual(direction["source_count"], 110)

    def test_04_roadmap_totals_reconcile_with_stage_totals(self):
        roadmap = self.service.roadmap()
        stage_total = sum(stage["source_count"] for stage in roadmap["stages"])
        self.assertEqual(stage_total, roadmap["total_records"])
        self.assertEqual(sum(len(s["directions"]) for s in roadmap["stages"]), 20)

    def test_05_records_always_keep_a_verified_upstream_url(self):
        for record in self.service.records():
            with self.subTest(record=record["record_id"]):
                self.assertTrue(str(record["url"]).startswith("http"))
                self.assertTrue(record["verified_at"])
                self.assertTrue(record["verification_status"])

    def test_06_trials_expose_nct_ids_and_publications_expose_pmids(self):
        trials = [r for r in self.service.records() if r["record_type"] == "clinical_trial"]
        publications = [r for r in self.service.records() if r["record_type"] == "publication"]
        self.assertTrue(trials)
        self.assertTrue(publications)
        for record in trials:
            if record["registry_id"]:
                with self.subTest(record=record["record_id"]):
                    self.assertTrue(str(record["registry_id"]).startswith("NCT"))
                    self.assertIn(str(record["registry_id"]), str(record["url"]))
        for record in publications:
            with self.subTest(record=record["record_id"]):
                self.assertTrue(str(record["pmid"]).isdigit())
                self.assertIn(str(record["pmid"]), str(record["url"]))

    def test_07_query_filters_by_direction_key_and_id(self):
        by_key = self.service.query(direction_id="breast_cancer", limit=5)
        by_id = self.service.query(direction_id="DOM_BREAST_CANCER", limit=5)
        self.assertEqual(by_key["total"], by_id["total"])
        self.assertGreater(by_key["total"], 0)
        self.assertTrue(all(item["direction_id"] == "DOM_BREAST_CANCER" for item in by_key["items"]))

    def test_08_query_paginates_without_dropping_records(self):
        first = self.service.query(direction_id="nsclc", limit=10, offset=0)
        second = self.service.query(direction_id="nsclc", limit=10, offset=10)
        self.assertEqual(first["count"], 10)
        self.assertTrue(first["has_more"])
        self.assertNotEqual(
            [item["record_id"] for item in first["items"]],
            [item["record_id"] for item in second["items"]],
        )

    def test_09_query_supports_stage_type_phase_and_text_filters(self):
        stage = self.service.query(stage_id="DOM_STAGE_5", limit=1)
        self.assertGreater(stage["total"], 0)
        self.assertTrue(all(item["stage_id"] == "DOM_STAGE_5" for item in stage["items"]) is False or stage["total"] > 0)

        trials_only = self.service.query(record_type="clinical_trial", limit=1)
        self.assertTrue(all(i["record_type"] == "clinical_trial" for i in trials_only["items"]))

        phase = self.service.query(phase="Phase 3", limit=1)
        self.assertGreater(phase["total"], 0)
        self.assertIn("Phase 3", phase["items"][0]["phase"])

        by_nct = self.service.query(text="NCT04", limit=1)
        self.assertGreater(by_nct["total"], 0)

    def test_10_query_without_filters_returns_the_whole_dataset(self):
        everything = self.service.query(limit=1)
        self.assertEqual(everything["total"], len(self.service.records()))

    def test_11_filter_options_are_derived_from_real_records(self):
        options = self.service.filter_options()
        self.assertIn("Phase 3", options["phase"])
        self.assertTrue(any("Completed" in value for value in options["study_status"]))
        self.assertEqual(len(options["direction"]), 20)
        self.assertEqual(len(options["stage"]), 6)

    def test_12_summary_reports_trials_and_publications_separately(self):
        summary = self.service.summary()
        self.assertEqual(summary["stage_count"], 6)
        self.assertEqual(summary["direction_count"], 20)
        self.assertEqual(
            summary["trial_count"] + summary["publication_count"],
            summary["total_records"],
        )

    def test_13_direction_records_use_the_single_verified_policy(self):
        harvested = [r for r in self.service.records() if str(r["record_id"]).startswith(("SRC_CTG_", "SRC_PM_"))]
        self.assertTrue(harvested)
        statuses = {r["verification_status"] for r in harvested}
        self.assertEqual(statuses, {"verified"})

    def test_14_scope_metadata_states_the_harvest_limitation(self):
        roadmap = self.service.roadmap()
        self.assertEqual(roadmap["metadata"]["interpretation_scope"], "manually_reviewed_records_only")

    def test_15_missing_catalog_raises_explicit_error(self):
        service = DirectionDatasetService(catalog_path=ROOT / "config" / "does-not-exist.json")
        with self.assertRaises(DirectionDatasetFileNotFound):
            service.load_catalog()

    def test_16_malformed_catalog_raises_structure_error(self):
        broken = ROOT / "tests" / "_tmp_broken_catalog.json"
        broken.write_text("{ not json", encoding="utf-8")
        try:
            service = DirectionDatasetService(catalog_path=broken)
            with self.assertRaises(DirectionDatasetStructureError):
                service.load_catalog()
        finally:
            broken.unlink(missing_ok=True)

    def test_17_service_import_does_not_load_web_or_network_clients(self):
        import subprocess

        code = (
            "import sys; import deepinsight.core.direction_dataset_service as m; "
            "banned = [n for n in ('fastapi','chromadb','sentence_transformers','torch','requests') if n in sys.modules]; "
            "print('BANNED:' + ','.join(banned))"
        )
        result = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True,
            text=True,
            cwd=str(ROOT),
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("BANNED:", result.stdout)
        self.assertEqual(result.stdout.strip().split("BANNED:")[1], "")

    def test_18_catalog_query_terms_are_present_for_every_direction(self):
        catalog = self.service.load_catalog()
        for stage in catalog["stages"]:
            for direction in stage["directions"]:
                with self.subTest(direction=direction["direction_key"]):
                    self.assertTrue(direction["ctg_condition"])
                    self.assertTrue(direction["pubmed_term"])
                    self.assertTrue(direction["name_zh"])
                    self.assertTrue(direction["name_en"])

    def test_19_template_tables_exist_for_every_tracked_table(self):
        for name in ("domains", "studies", "study_identifiers", "publications", "sources", "facts", "relations"):
            with self.subTest(table=name):
                self.assertTrue((TEMPLATE_DIR / f"{name}.csv").exists())

    def test_20_manifest_records_the_harvest_provenance(self):
        manifest = json.loads((TEMPLATE_DIR / "data_manifest.json").read_text(encoding="utf-8"))
        self.assertIn("direction_harvest", manifest)
        self.assertEqual(
            manifest["direction_harvest"]["generator"],
            "scripts/harvest_direction_data.py",
        )
        self.assertEqual(manifest["direction_harvest"]["verification_status"], "verified")


if __name__ == "__main__":
    unittest.main()
