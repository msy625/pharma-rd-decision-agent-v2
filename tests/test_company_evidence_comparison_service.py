import inspect
import subprocess
import sys
import unittest
from pathlib import Path

from deepinsight.core.company_evidence_comparison_service import CompanyEvidenceComparisonService
from deepinsight.core.evidence_chain_service import EvidenceChainService
from deepinsight.core.source_registry_service import SourceRegistryService


ROOT = Path(__file__).resolve().parents[1]


def _assert_no_prohibited_keys(testcase, value):
    prohibited = {"score", "ranking", "winner", "success_probability"}
    if isinstance(value, dict):
        for key, item in value.items():
            testcase.assertNotIn(key, prohibited)
            _assert_no_prohibited_keys(testcase, item)
    elif isinstance(value, list):
        for item in value:
            _assert_no_prohibited_keys(testcase, item)


class CompanyEvidenceComparisonServiceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source_service = SourceRegistryService()
        cls.chain_service = EvidenceChainService(source_registry_service=cls.source_service)
        cls.service = CompanyEvidenceComparisonService(
            source_registry_service=cls.source_service,
            evidence_chain_service=cls.chain_service,
        )

    def test_01_hengrui_source_count_is_15(self):
        self.assertEqual(self.service.company_profile("恒瑞医药")["source_count"], 15)

    def test_02_beone_source_count_is_16_for_aliases(self):
        self.assertEqual(self.service.company_profile("百济神州")["source_count"], 16)
        self.assertEqual(self.service.company_profile("BeOne Medicines")["source_count"], 16)
        self.assertEqual(self.service.company_profile("BeiGene")["source_count"], 16)

    def test_03_both_companies_all_sources_are_verified(self):
        hengrui = self.service.company_profile("恒瑞医药")
        beone = self.service.company_profile("BeOne Medicines")
        self.assertEqual(hengrui["verified_source_count"], hengrui["source_count"])
        self.assertEqual(beone["verified_source_count"], beone["source_count"])

    def test_04_trial_chain_counts_are_from_evidence_chain_service(self):
        self.assertEqual(self.service.company_profile("恒瑞医药")["trial_chain_count"], 6)
        self.assertEqual(self.service.company_profile("BeOne Medicines")["trial_chain_count"], 4)

    def test_05_beone_regulatory_chain_count_is_1(self):
        self.assertEqual(self.service.company_profile("BeOne Medicines")["regulatory_chain_count"], 1)
        self.assertEqual(self.service.company_profile("恒瑞医药")["regulatory_chain_count"], 0)

    def test_06_single_and_multi_source_trial_chain_counts(self):
        hengrui = self.service.company_profile("恒瑞医药")
        beone = self.service.company_profile("百济神州")
        self.assertEqual(hengrui["single_source_trial_chain_count"], 6)
        self.assertEqual(hengrui["multi_source_trial_chain_count"], 0)
        self.assertEqual(beone["single_source_trial_chain_count"], 0)
        self.assertEqual(beone["multi_source_trial_chain_count"], 4)

    def test_07_unresolved_link_counts(self):
        self.assertEqual(self.service.company_profile("恒瑞医药")["unresolved_link_count"], 6)
        self.assertEqual(self.service.company_profile("BeOne Medicines")["unresolved_link_count"], 1)

    def test_08_version_distribution(self):
        self.assertEqual(self.service.company_profile("恒瑞医药")["version_distribution"], {"latest": 0, "historical": 0, "independent": 15})
        self.assertEqual(self.service.company_profile("百济神州")["version_distribution"], {"latest": 4, "historical": 2, "independent": 10})

    def test_09_company_aliases_do_not_create_duplicate_subjects(self):
        companies = self.service.available_companies()
        self.assertEqual(len(companies), 3)
        self.assertIn("阿斯利康", {item["company_name"] for item in companies})
        with self.assertRaises(ValueError):
            self.service.compare("百济神州", "BeiGene")

    def test_10_compare_payload_has_required_boundary_sections(self):
        comparison = self.service.compare("恒瑞医药", "BeOne Medicines")
        self.assertEqual(len(comparison["companies"]), 2)
        self.assertIn("directly_comparable_metrics", comparison)
        self.assertIn("partially_comparable_dimensions", comparison)
        self.assertIn("prohibited_conclusions", comparison)
        self.assertEqual(comparison["data_scope"], "verified_nsclc_multi_company_sample")

    def test_astrazeneca_profile_uses_verified_supplement(self):
        profile = self.service.company_profile("AstraZeneca")
        self.assertEqual(profile["company_name"], "阿斯利康")
        self.assertEqual(profile["source_count"], 8)
        self.assertEqual(profile["trial_chain_count"], 4)

    def test_11_payload_does_not_include_prohibited_claim_keys(self):
        comparison = self.service.compare("恒瑞医药", "BeOne Medicines")
        _assert_no_prohibited_keys(self, comparison)

    def test_12_scope_warning_mentions_current_sample(self):
        comparison = self.service.compare("恒瑞医药", "BeOne Medicines")
        self.assertTrue(any("当前收录" in note and "不代表企业整体研发实力" in note for note in comparison["comparison_notes"]))

    def test_13_metric_rules_include_correct_and_prohibited_interpretations(self):
        rules = self.service.metric_rules()
        self.assertTrue(rules)
        for rule in rules:
            self.assertIn("correct_interpretation", rule)
            self.assertIn("prohibited_interpretation", rule)
        multi_source_rule = next(rule for rule in rules if rule["field"] == "multi_source_trial_chain_count")
        self.assertIn("当前样本", multi_source_rule["correct_interpretation"])
        self.assertIn("不能解释为研发质量", multi_source_rule["prohibited_interpretation"])

    def test_14_missing_company_returns_empty_profile(self):
        profile = self.service.company_profile("不存在的企业")
        self.assertEqual(profile["source_count"], 0)
        self.assertEqual(profile["trial_chain_count"], 0)
        self.assertIn("当前数据不足", profile["evidence_gaps"][0])

    def test_15_empty_company_raises_for_compare(self):
        with self.assertRaises(ValueError):
            self.service.compare("", "BeOne Medicines")

    def test_16_counts_are_not_hardcoded_in_service_methods(self):
        source = inspect.getsource(CompanyEvidenceComparisonService)
        for forbidden in ['"source_count": 15', '"source_count": 16', '"trial_chain_count": 6', '"trial_chain_count": 4']:
            self.assertNotIn(forbidden, source)
        self.assertIn("SourceRegistryService", source)
        self.assertIn("EvidenceChainService", source)

    def test_17_import_does_not_load_models_vectors_or_network_clients(self):
        code = f"""
import sys
sys.path.insert(0, {str(ROOT)!r})
import deepinsight.core.company_evidence_comparison_service  # noqa
blocked = ['chromadb', 'sentence_transformers', 'openai']
print(','.join(name for name in blocked if name in sys.modules))
"""
        result = subprocess.run([sys.executable, "-c", code], check=True, text=True, capture_output=True)
        self.assertEqual(result.stdout.strip(), "")


if __name__ == "__main__":
    unittest.main()
