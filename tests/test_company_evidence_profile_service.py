import json
import subprocess
import sys
import unittest
from pathlib import Path

from deepinsight.core.company_evidence_profile_service import CompanyEvidenceProfileService


ROOT = Path(__file__).resolve().parents[1]


def _assert_no_prohibited_fields(testcase, value):
    prohibited = {"score", "ranking", "winner", "success_rate", "success_probability"}
    if isinstance(value, dict):
        for key, item in value.items():
            testcase.assertNotIn(key, prohibited)
            _assert_no_prohibited_fields(testcase, item)
    elif isinstance(value, list):
        for item in value:
            _assert_no_prohibited_fields(testcase, item)


class CompanyEvidenceProfileServiceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.service = CompanyEvidenceProfileService()

    def test_01_source_counts_are_dynamic_registry_counts(self):
        self.assertEqual(self.service.company_summary("恒瑞医药")["source_count"], 15)
        self.assertEqual(self.service.company_summary("百济神州")["source_count"], 16)
        self.assertEqual(self.service.company_summary("AstraZeneca")["source_count"], 8)

    def test_02_company_aliases_normalize_to_one_subject(self):
        for alias in ["百济神州", "BeOne Medicines", "BeiGene"]:
            company = self.service.normalize_company(alias)
            self.assertEqual(company["canonical_name"], "百济神州")
            self.assertEqual(company["display_name"], "百济神州 / BeOne Medicines")
        self.assertEqual(self.service.normalize_company("AstraZeneca")["canonical_name"], "阿斯利康")
        self.assertEqual(len(self.service.available_companies()), 3)

    def test_03_trial_and_regulatory_chain_counts(self):
        hengrui = self.service.company_summary("恒瑞医药")
        beone = self.service.company_summary("BeOne Medicines")
        self.assertEqual((hengrui["trial_chain_count"], hengrui["regulatory_chain_count"]), (6, 0))
        self.assertEqual((beone["trial_chain_count"], beone["regulatory_chain_count"]), (4, 1))
        astrazeneca = self.service.company_summary("阿斯利康")
        self.assertEqual((astrazeneca["trial_chain_count"], astrazeneca["regulatory_chain_count"]), (4, 0))
        self.assertEqual(self.service.regulatory_chains("AstraZeneca"), [])

    def test_04_b016_does_not_increase_trial_chain_or_trial_source_count(self):
        profile = self.service.build_profile("百济神州")
        trial_source_ids = {
            source_id
            for chain in profile["trial_chains"]
            for source_id in chain["source_ids"]
        }
        self.assertEqual(profile["summary"]["trial_chain_count"], 4)
        self.assertNotIn("B016", trial_source_ids)
        self.assertEqual(profile["regulatory_chains"][0]["source_ids"], ["B015", "B016"])

    def test_05_publication_versions_do_not_duplicate_trials(self):
        chains = {chain["trial_id"]: chain for chain in self.service.trial_chains("百济神州")}
        self.assertEqual(len(chains), 4)
        self.assertEqual(chains["NCT03663205"]["source_ids"], ["B003", "B006", "B007"])
        self.assertEqual(chains["NCT03663205"]["historical_count"], 1)
        self.assertEqual(chains["NCT03663205"]["latest_count"], 1)

    def test_06_version_distributions_match_registry_fields(self):
        hengrui = self.service.company_summary("恒瑞医药")
        beone = self.service.company_summary("百济神州")
        self.assertEqual((hengrui["latest_count"], hengrui["historical_count"], hengrui["independent_count"]), (0, 0, 15))
        self.assertEqual((beone["latest_count"], beone["historical_count"], beone["independent_count"]), (4, 2, 10))

    def test_07_source_type_counts_use_source_type_fields(self):
        hengrui = self.service.company_summary("恒瑞医药")
        beone = self.service.company_summary("百济神州")
        self.assertEqual((hengrui["publication_source_count"], hengrui["trial_registry_source_count"]), (5, 5))
        self.assertEqual((beone["publication_source_count"], beone["trial_registry_source_count"]), (6, 4))

    def test_08_unresolved_link_counts(self):
        self.assertEqual(len(self.service.unresolved_links("恒瑞医药")), 6)
        self.assertEqual(len(self.service.unresolved_links("BeOne Medicines")), 1)

    def test_09_regulatory_sources_preserve_b015_b016_meanings(self):
        sources = {item["source_id"]: item for item in self.service.regulatory_chains("百济神州")[0]["sources"]}
        self.assertEqual(sources["B015"]["status_note"], "正式授权")
        self.assertEqual(sources["B016"]["status_note"], "CHMP积极意见，非最终批准")
        self.assertEqual(self.service.regulatory_chains("百济神州")[0]["related_trial_ids"], ["NCT04379635"])

    def test_10_missing_company_returns_empty_profile(self):
        profile = self.service.build_profile("不存在企业")
        self.assertEqual(profile["company"]["canonical_name"], "")
        self.assertEqual(profile["summary"]["source_count"], 0)
        self.assertIn("当前数据不足", profile["limitations"][0])

    def test_11_profile_has_metadata_and_limitations(self):
        profile = self.service.build_profile("恒瑞医药")
        self.assertEqual(profile["metadata"]["data_scope"], "verified_nsclc_multi_company_sample")
        self.assertTrue(profile["metadata"]["data_version"].startswith("sha256:"))
        self.assertEqual(profile["metadata"]["latest_verified_at"], "2026-07-21")
        self.assertIn("响应生成时间", profile["metadata"]["generated_at_note"])
        self.assertTrue(any("完整研发管线" in item for item in profile["limitations"]))

    def test_12_profile_has_no_scores_rankings_or_success_rates(self):
        _assert_no_prohibited_fields(self, self.service.build_profile("百济神州"))

    def test_13_import_does_not_load_heavy_modules(self):
        code = """
import json, sys
blocked = ['chromadb', 'sentence_transformers', 'torch', 'deepinsight.core.retriever']
before = {name for name in blocked if name in sys.modules}
from deepinsight.core.company_evidence_profile_service import CompanyEvidenceProfileService
CompanyEvidenceProfileService().build_profile('恒瑞医药')
after = {name for name in blocked if name in sys.modules}
print(json.dumps(sorted(after - before)))
"""
        result = subprocess.run(
            [sys.executable, "-c", code], cwd=ROOT, text=True, capture_output=True, check=True
        )
        self.assertEqual(json.loads(result.stdout), [])


if __name__ == "__main__":
    unittest.main()
