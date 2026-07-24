import unittest

from evaluation.adapters import RESULT_FIELDS
from evaluation.baselines import BASELINE_NAMES, build_baselines
from evaluation.runner import DEFAULT_CASES_PATH
from evaluation.validators import load_cases


class EvaluationBaselinesTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cases = {case["case_id"]: case for case in load_cases(DEFAULT_CASES_PATH)}
        cls.baselines = {baseline.name: baseline for baseline in build_baselines()}

    def test_three_offline_baselines_exist(self):
        self.assertEqual(list(self.baselines), BASELINE_NAMES)

    def test_all_baselines_share_exact_result_protocol(self):
        case = self.cases["TRIAL-001"]
        for baseline in self.baselines.values():
            with self.subTest(baseline=baseline.name):
                result = baseline.run(case)
                self.assertEqual(list(result), RESULT_FIELDS)
                self.assertIsInstance(result["latency_ms"], float)
                self.assertFalse(result["used_llm"])

    def test_grounded_safety_case_has_zero_retrieval_and_no_model(self):
        result = self.baselines["grounded_qa_local"].run(self.cases["SAFE-001"])
        self.assertEqual(result["source_ids"], [])
        self.assertEqual(result["chain_ids"], [])
        self.assertEqual(result["citations"], [])
        self.assertTrue(result["refused"])
        self.assertFalse(result["used_llm"])

    def test_b016_anchor_does_not_expand_beyond_regulatory_chain(self):
        result = self.baselines["grounded_qa_local"].run(self.cases["REG-001"])
        self.assertEqual(result["source_ids"], ["B015", "B016"])
        self.assertEqual(result["chain_ids"], ["regulatory:tevimbra-eu-nsclc"])
        self.assertEqual(result["citations"], ["B015", "B016"])
        self.assertTrue(set(result["source_ids"]).isdisjoint({f"B{i:03d}" for i in range(2, 15)}))

    def test_grounded_local_runs_all_twelve_without_errors(self):
        baseline = self.baselines["grounded_qa_local"]
        results = [baseline.run(case) for case in self.cases.values()]
        self.assertEqual(len(results), 12)
        self.assertTrue(all(result["error"] == "" for result in results))
        self.assertTrue(all(result["used_llm"] is False for result in results))


if __name__ == "__main__":
    unittest.main()
