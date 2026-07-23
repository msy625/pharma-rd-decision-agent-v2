import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


class EvidenceWorkbenchServiceTest(unittest.TestCase):
    def setUp(self):
        from deepinsight.core.evidence_workbench_service import EvidenceWorkbenchService

        self.service = EvidenceWorkbenchService()
        self.workbench = self.service.build_workbench()

    def test_01_summary_counts_are_dynamic_from_verified_services(self):
        summary = self.workbench["summary"]
        self.assertEqual(summary["source_count"], 31)
        self.assertEqual(summary["verified_source_count"], 31)
        self.assertEqual(summary["company_count"], 2)
        self.assertEqual(summary["trial_chain_count"], 10)
        self.assertEqual(summary["regulatory_chain_count"], 1)
        self.assertEqual(summary["latest_count"], 4)
        self.assertEqual(summary["historical_count"], 2)
        self.assertEqual(summary["independent_count"], 25)
        self.assertEqual(summary["unresolved_link_count"], 7)

    def test_02_beone_aliases_are_one_company_subject(self):
        companies = self.workbench["companies"]
        names = [item["display_name"] for item in companies]
        self.assertEqual(len(companies), 2)
        self.assertIn("恒瑞医药", names)
        self.assertIn("百济神州/BeOne Medicines", names)

    def test_03_b016_regulatory_context_does_not_increase_trial_count(self):
        chains = self.service.evidence_chain_service.list_chains()
        trial_ids = {trial_id for chain in chains if chain["chain_type"] == "trial" for trial_id in chain.get("trial_ids", [])}
        self.assertEqual(self.workbench["summary"]["trial_chain_count"], 10)
        self.assertEqual(len([chain for chain in chains if chain["chain_type"] == "trial"]), 10)
        self.assertIn("NCT04379635", trial_ids)
        regulatory_sources = [
            item.get("source_id")
            for chain in chains
            if chain["chain_type"] == "regulatory"
            for item in chain.get("evidence_items", [])
        ]
        self.assertIn("B016", regulatory_sources)

    def test_04_distribution_and_metadata_are_present(self):
        self.assertTrue(self.workbench["source_type_distribution"])
        self.assertTrue(self.workbench["study_status_distribution"])
        metadata = self.workbench["metadata"]
        self.assertEqual(metadata["data_scope"], "first_version_nsclc_hengrui_beone")
        self.assertTrue(metadata["data_version"].startswith("sha256:"))
        self.assertEqual(metadata["latest_verified_at"], "2026-07-21")
        self.assertIn("响应生成时间", metadata["generated_at_note"])

    def test_05_no_score_ranking_winner_or_success_probability_output(self):
        text = json.dumps(self.workbench, ensure_ascii=False).lower()
        for forbidden in ["score", "ranking", "winner", "success probability", "成功率", "综合评分", "企业排名", "优胜方"]:
            self.assertNotIn(forbidden, text)

    def test_06_importing_service_does_not_load_heavy_dependencies(self):
        blocked = {"openai", "chromadb", "sentence_transformers", "torch", "streamlit", "pandas"}
        before = {name for name in blocked if name in sys.modules}
        import deepinsight.core.evidence_workbench_service  # noqa: F401

        after = {name for name in blocked if name in sys.modules}
        self.assertEqual(after - before, set())


if __name__ == "__main__":
    unittest.main()
