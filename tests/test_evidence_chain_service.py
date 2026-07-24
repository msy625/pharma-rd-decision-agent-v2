import subprocess
import sys
import unittest
from pathlib import Path

from deepinsight.core.evidence_chain_service import EvidenceChainService
from deepinsight.core.source_registry_service import SourceRegistryService


ROOT = Path(__file__).resolve().parents[1]


class EvidenceChainServiceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source_service = SourceRegistryService()
        cls.service = EvidenceChainService(source_registry_service=cls.source_service)

    def ids(self, items):
        return {item["source_id"] for item in items}

    def test_01_trial_chain_count_is_14(self):
        self.assertEqual(len(self.service.list_chains(chain_type="trial")), 14)
        self.assertEqual(self.service.summary()["trial_chains"], 14)
        self.assertEqual(self.service.summary()["clinical_trial_count"], 14)

    def test_02_regulatory_chain_count_is_1(self):
        self.assertEqual(len(self.service.list_chains(chain_type="regulatory")), 1)
        self.assertEqual(self.service.summary()["regulatory_chains"], 1)
        self.assertEqual(self.service.summary()["total_chains"], 15)

    def test_03_rationale_304_contains_expected_sources(self):
        chain = self.service.get_trial_chain("NCT03663205")
        self.assertEqual(self.ids(chain["evidence_items"]), {"B003", "B006", "B007"})

    def test_04_b006_is_historical_version(self):
        chain = self.service.get_trial_chain("NCT03663205")
        self.assertEqual(self.ids(chain["historical_items"]), {"B006"})

    def test_05_b007_is_latest_version(self):
        chain = self.service.get_trial_chain("NCT03663205")
        self.assertEqual(self.ids(chain["latest_items"]), {"B007"})

    def test_06_rationale_315_trial_chain_has_only_trial_sources(self):
        chain = self.service.get_trial_chain("NCT04379635")
        self.assertEqual(self.ids(chain["evidence_items"]), {"B011", "B012", "B013"})
        self.assertEqual(chain["source_count"], 3)

    def test_07_b016_is_not_counted_in_rationale_315_trial_evidence(self):
        chain = self.service.get_trial_chain("NCT04379635")
        self.assertNotIn("B016", self.ids(chain["evidence_items"]))
        self.assertIn("B016", self.ids(chain["related_regulatory_items"]))
        self.assertEqual(chain["source_count"], 3)

    def test_08_regulatory_chain_contains_b015_b016(self):
        chain = self.service.get_drug_regulatory_chain("Tislelizumab")
        self.assertEqual(chain["chain_id"], "regulatory:tevimbra-eu-nsclc")
        self.assertEqual(self.ids(chain["evidence_items"]), {"B015", "B016"})

    def test_09_b015_is_formal_authorisation(self):
        chain = self.service.get_drug_regulatory_chain("替雷利珠单抗")
        b015 = next(item for item in chain["evidence_items"] if item["source_id"] == "B015")
        self.assertEqual(b015["role"], "regulatory_authorisation")
        self.assertEqual(b015["authorisation_status"], "欧盟正式授权")

    def test_10_b016_is_only_chmp_positive_opinion(self):
        chain = self.service.get_drug_regulatory_chain("TEVIMBRA")
        b016 = next(item for item in chain["evidence_items"] if item["source_id"] == "B016")
        self.assertEqual(b016["role"], "regulatory_opinion")
        self.assertEqual(b016["regulatory_event_type"], "CHMP positive opinion")
        self.assertEqual(b016["authorisation_status"], "")

    def test_11_nct04379635_counts_as_one_trial(self):
        chain = self.service.get_trial_chain("NCT04379635")
        self.assertEqual(chain["chain_id"], "trial:NCT04379635")
        self.assertEqual(len([item for item in self.service.list_chains(chain_type="trial") if "NCT04379635" in item["trial_ids"]]), 1)

    def test_12_hengrui_single_source_trial_chains_exist(self):
        expected = {
            "NCT04818333": {"H003"},
            "NCT03083041": {"H004"},
            "NCT03668496": {"H005"},
            "NCT04619433": {"H006"},
            "NCT02364362": {"H007"},
            "SHR-A2009-301": {"H015"},
        }
        for trial_id, source_ids in expected.items():
            with self.subTest(trial_id=trial_id):
                chain = self.service.get_trial_chain(trial_id)
                self.assertEqual(self.ids(chain["evidence_items"]), source_ids)
                self.assertEqual(chain["source_count"], 1)

    def test_13_h008_to_h012_remain_unresolved(self):
        unresolved_ids = {item["source_id"] for item in self.service.get_unresolved_links()}
        self.assertGreaterEqual(unresolved_ids, {"H008", "H009", "H010", "H011", "H012"})
        trial_source_ids = {
            item["source_id"]
            for chain in self.service.list_chains(chain_type="trial")
            for item in chain["evidence_items"]
        }
        self.assertTrue({"H008", "H009", "H010", "H011", "H012"}.isdisjoint(trial_source_ids))

    def test_14_h014_specific_trial_relation_remains_unresolved(self):
        unresolved = {item["source_id"]: item for item in self.service.get_unresolved_links()}
        self.assertIn("H014", unresolved)
        self.assertIn("一对一关系", unresolved["H014"]["description"])
        trial_source_ids = {
            item["source_id"]
            for chain in self.service.list_chains(chain_type="trial")
            for item in chain["evidence_items"]
        }
        self.assertNotIn("H014", trial_source_ids)

    def test_15_missing_chain_or_trial_returns_empty_result(self):
        self.assertEqual(self.service.get_chain("trial:missing"), {})
        self.assertEqual(self.service.get_trial_chain("NCT00000000"), {})
        self.assertEqual(self.service.get_drug_regulatory_chain("不存在的药物"), {})

    def test_16_import_does_not_load_models_vectors_or_network_clients(self):
        code = f"""
import sys
sys.path.insert(0, {str(ROOT)!r})
import deepinsight.core.evidence_chain_service  # noqa
blocked = ['chromadb', 'sentence_transformers', 'openai']
print(','.join(name for name in blocked if name in sys.modules))
"""
        result = subprocess.run([sys.executable, "-c", code], check=True, text=True, capture_output=True)
        self.assertEqual(result.stdout.strip(), "")

    def test_17_config_source_ids_exist_in_registry(self):
        source_ids = {row["source_id"] for row in self.source_service.load_rows()}
        config = self.service.load_chain_config()
        configured = set()
        for chain in config["chains"]:
            configured.update(item["source_id"] for item in chain["source_ids"])
            configured.update(chain.get("related_regulatory_source_ids", []))
        configured.update(item["source_id"] for item in config.get("unresolved_links", []))
        self.assertTrue(configured)
        self.assertTrue(configured <= source_ids)

    def test_18_source_id_not_repeated_across_trial_chains(self):
        seen = {}
        for chain in self.service.list_chains(chain_type="trial"):
            for item in chain["evidence_items"]:
                source_id = item["source_id"]
                self.assertNotIn(source_id, seen, f"{source_id} also appears in {seen.get(source_id)}")
                seen[source_id] = chain["chain_id"]

    def test_19_astrazeneca_trials_pair_registry_and_publication_once(self):
        expected = {
            "NCT02296125": {"A001", "A002"},
            "NCT02511106": {"A003", "A004"},
            "NCT03521154": {"A005", "A006"},
            "NCT04035486": {"A007", "A008"},
        }
        chains = self.service.list_chains(company="AstraZeneca", chain_type="trial")
        self.assertEqual(len(chains), 4)
        self.assertEqual(
            {chain["trial_ids"][0]: self.ids(chain["evidence_items"]) for chain in chains},
            expected,
        )
        self.assertEqual(self.service.list_chains(company="AstraZeneca", chain_type="regulatory"), [])


if __name__ == "__main__":
    unittest.main()
