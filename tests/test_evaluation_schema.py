import copy
import unittest
from collections import Counter

from evaluation.runner import DEFAULT_CASES_PATH, DEFAULT_MANIFEST_PATH
from evaluation.validators import (
    PROJECT_ROOT,
    EvaluationValidationError,
    load_cases,
    load_json,
    validate_case,
    validate_suite,
)


class EvaluationSchemaTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = load_json(DEFAULT_MANIFEST_PATH)
        cls.cases = load_cases(DEFAULT_CASES_PATH)

    def test_pilot_manifest_and_cases_are_valid(self):
        validate_suite(self.manifest, self.cases)

    def test_formal_suite_is_frozen_with_required_distribution_and_split(self):
        manifest = load_json(PROJECT_ROOT / "evaluation" / "cases" / "formal_manifest.json")
        cases = load_cases(PROJECT_ROOT / "evaluation" / "cases" / "formal_cases.jsonl")
        validate_suite(manifest, cases)
        self.assertEqual(Counter(item["split"] for item in cases), {"dev": 42, "acceptance": 18})
        self.assertEqual(
            Counter(item["category"] for item in cases),
            {
                "source_search": 10, "trial_status": 8, "evidence_chain": 10,
                "regulatory_status": 8, "company_comparison": 8, "evidence_gap": 6,
                "prohibited_or_unsupported": 10,
            },
        )
        self.assertEqual(self.manifest["case_count"], 12)
        self.assertEqual(len(self.cases), 12)

    def test_pilot_distribution_matches_design(self):
        counts = Counter(case["category"] for case in self.cases)
        self.assertEqual(
            counts,
            {
                "source_search": 2,
                "trial_status": 2,
                "evidence_chain": 2,
                "regulatory_status": 2,
                "company_comparison": 1,
                "evidence_gap": 1,
                "prohibited_or_unsupported": 2,
            },
        )
        self.assertTrue(all(case["split"] == "pilot" for case in self.cases))

    def test_case_ids_are_unique(self):
        case_ids = [case["case_id"] for case in self.cases]
        self.assertEqual(len(case_ids), len(set(case_ids)))

    def test_missing_required_field_is_rejected(self):
        invalid = copy.deepcopy(self.cases[0])
        invalid.pop("allowed_source_ids")
        with self.assertRaises(EvaluationValidationError):
            validate_case(invalid)

    def test_invalid_source_and_chain_ids_are_rejected(self):
        invalid_source = copy.deepcopy(self.cases[0])
        invalid_source["expected_source_ids"] = ["BAD-1"]
        with self.assertRaises(EvaluationValidationError):
            validate_case(invalid_source)

        invalid_chain = copy.deepcopy(self.cases[2])
        invalid_chain["expected_chain_ids"] = ["legacy:NCT04619433"]
        with self.assertRaises(EvaluationValidationError):
            validate_case(invalid_chain)

    def test_text_fact_requires_supporting_sources(self):
        invalid = copy.deepcopy(next(case for case in self.cases if case["case_id"] == "REG-001"))
        invalid["required_facts"][0]["supporting_source_ids"] = []
        with self.assertRaises(EvaluationValidationError):
            validate_case(invalid)

    def test_duplicate_case_id_and_wrong_manifest_count_are_rejected(self):
        duplicate = [*copy.deepcopy(self.cases), copy.deepcopy(self.cases[0])]
        duplicate_manifest = {**self.manifest, "case_count": 13}
        with self.assertRaises(EvaluationValidationError):
            validate_suite(duplicate_manifest, duplicate)

        wrong_count = {**self.manifest, "case_count": 11}
        with self.assertRaises(EvaluationValidationError):
            validate_suite(wrong_count, self.cases)

    def test_b016_gold_contract_is_narrow_and_manual(self):
        case = next(case for case in self.cases if case["case_id"] == "REG-001")
        self.assertEqual(case["allowed_source_ids"], ["B015", "B016"])
        self.assertEqual(case["expected_chain_ids"], ["regulatory:tevimbra-eu-nsclc"])
        self.assertTrue(set(f"B{i:03d}" for i in range(2, 15)) <= set(case["forbidden_source_ids"]))
        self.assertTrue(case["manual_review_required"])


if __name__ == "__main__":
    unittest.main()
