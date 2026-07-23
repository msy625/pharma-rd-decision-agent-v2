import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from deepinsight.core.source_registry_service import SourceRegistryService


ROOT = Path(__file__).resolve().parents[1]


class SourceRegistryServiceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.service = SourceRegistryService()

    def ids(self, rows):
        return {row["source_id"] for row in rows}

    def test_01_summary_total_is_39(self):
        self.assertEqual(self.service.summary()["total_sources"], 39)

    def test_02_hengrui_returns_15(self):
        self.assertEqual(len(self.service.query(company="恒瑞医药")), 15)

    def test_03_beigene_cn_returns_16(self):
        self.assertEqual(len(self.service.query(company="百济神州")), 16)

    def test_04_beone_medicines_returns_16(self):
        self.assertEqual(len(self.service.query(company="BeOne Medicines")), 16)

    def test_05_company_alias_queries_are_consistent(self):
        self.assertEqual(
            self.ids(self.service.query(company="百济神州")),
            self.ids(self.service.query(company="BeiGene")),
        )

    def test_astrazeneca_alias_and_osimertinib_queries(self):
        self.assertEqual(len(self.service.query(company="AstraZeneca")), 8)
        self.assertEqual(len(self.service.query(company="阿斯利康")), 8)
        self.assertEqual(self.ids(self.service.query(drug="AZD9291")), self.ids(self.service.query(drug="奥希替尼")))

    def test_06_shr_1210_matches_camrelizumab_sources(self):
        shr_rows = self.service.query(drug="SHR-1210")
        cam_rows = self.service.query(drug="Camrelizumab")
        self.assertEqual(self.ids(shr_rows), self.ids(cam_rows))
        self.assertIn("H004", self.ids(shr_rows))

    def test_07_nct04379635_returns_three_related_sources(self):
        rows = self.service.query(trial_id="NCT04379635")
        self.assertEqual(self.ids(rows), {"B011", "B012", "B013"})
        for row in rows:
            self.assertEqual(row["parent_trial_id"], "NCT04379635")

    def test_08_nct04619433_is_h006_terminated(self):
        rows = self.service.query(trial_id="NCT04619433")
        self.assertEqual(self.ids(rows), {"H006"})
        self.assertEqual(rows[0]["study_status"], "Terminated")
        self.assertEqual(rows[0]["verification_status"], "已人工核验")

    def test_09_rationale_304_latest_only_excludes_interim(self):
        ids = self.ids(self.service.query(study_name="RATIONALE-304", latest_only=True))
        self.assertIn("B007", ids)
        self.assertNotIn("B006", ids)

    def test_study_name_exact_match_has_priority_over_substrings(self):
        self.assertEqual(self.ids(self.service.query(study_name="LAURA")), {"A005", "A006"})
        self.assertEqual(self.ids(self.service.query(study_name="FLAURA")), {"A001", "A002"})
        self.assertEqual(self.ids(self.service.query(study_name="FLAURA2")), {"A007", "A008"})

    def test_study_name_exact_match_normalizes_case_and_outer_whitespace(self):
        self.assertEqual(self.ids(self.service.query(study_name="  laura  ")), {"A005", "A006"})

    def test_study_name_partial_match_remains_as_fallback(self):
        self.assertEqual(
            self.ids(self.service.query(study_name="LAUR")),
            {"A001", "A002", "A005", "A006", "A007", "A008"},
        )

    def test_keyword_laura_keeps_broad_substring_search(self):
        self.assertEqual(
            self.ids(self.service.query(text="LAURA")),
            {"A001", "A002", "A005", "A006", "A007", "A008"},
        )

    def test_10_nct03663205_related_evidence(self):
        rows = self.service.related_evidence("NCT03663205")
        self.assertEqual(self.ids(rows), {"B003", "B006", "B007"})

    def test_11_nonexistent_company_returns_empty_list(self):
        self.assertEqual(self.service.query(company="不存在的企业"), [])

    def test_12_nonexistent_source_id_returns_empty(self):
        self.assertEqual(self.service.query(source_id="Z999"), [])
        self.assertIsNone(self.service.get_by_source_id("Z999"))

    def test_13_result_rows_include_source_id_and_url(self):
        for row in self.service.query(company="恒瑞医药"):
            self.assertTrue(row.get("source_id"))
            self.assertTrue(row.get("source_url"))

    def test_14_default_paths_work_outside_repo_root(self):
        original_cwd = Path.cwd()
        with tempfile.TemporaryDirectory() as tmpdir:
            os.chdir(tmpdir)
            try:
                service = SourceRegistryService()
                self.assertEqual(service.summary()["total_sources"], 39)
            finally:
                os.chdir(original_cwd)

    def test_15_import_does_not_load_models_vectors_or_network_clients(self):
        code = f"""
import sys
sys.path.insert(0, {str(ROOT)!r})
import deepinsight.core.source_registry_service  # noqa
blocked = ['chromadb', 'sentence_transformers', 'requests', 'openai']
print(','.join(name for name in blocked if name in sys.modules))
"""
        result = subprocess.run([sys.executable, "-c", code], check=True, text=True, capture_output=True)
        self.assertEqual(result.stdout.strip(), "")

    def test_16_b011_notes_reference_current_rationale_315_links(self):
        row = self.service.get_by_source_id("B011")
        self.assertIsNotNone(row)
        risk_notes = row.get("risk_notes", "")
        self.assertNotIn("后续批次补充", risk_notes)
        self.assertIn("中期分析", risk_notes)
        self.assertIn("B012", risk_notes)
        self.assertIn("B013", risk_notes)
        self.assertIn("NCT04379635", risk_notes)
        self.assertIn("不重复计数", risk_notes)


if __name__ == "__main__":
    unittest.main()
