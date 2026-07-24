import unittest

from evaluation.adapters import ProductionServiceAdapters, RESULT_FIELDS
from evaluation.runner import DEFAULT_CASES_PATH
from evaluation.validators import load_cases


class EvaluationAdaptersTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cases = {case["case_id"]: case for case in load_cases(DEFAULT_CASES_PATH)}
        cls.adapters = ProductionServiceAdapters()

    def test_keyword_laura_keeps_broad_contains_behavior(self):
        result = self.adapters.keyword_contains(self.cases["SRC-001"])
        self.assertEqual(set(result.source_ids), {"A001", "A002", "A005", "A006", "A007", "A008"})

    def test_structured_laura_uses_exact_priority(self):
        result = self.adapters.structured_no_chain(self.cases["SRC-001"])
        self.assertEqual(result.source_ids, ["A005", "A006"])
        self.assertEqual(result.chain_ids, [])

    def test_structured_tagrisso_uses_existing_alias_service(self):
        result = self.adapters.structured_no_chain(self.cases["SRC-002"])
        self.assertEqual(set(result.source_ids), {f"A{i:03d}" for i in range(1, 9)})

    def test_structured_company_pair_unions_existing_company_queries(self):
        result = self.adapters.structured_no_chain(self.cases["COMP-001"])
        self.assertEqual(len(result.source_ids), 24)
        self.assertEqual(set(result.source_ids), set(self.cases["COMP-001"]["expected_source_ids"]))
        self.assertEqual(result.chain_ids, [])

    def test_grounded_adapter_normalizes_existing_response(self):
        result = self.adapters.grounded_qa_local(self.cases["CHAIN-002"]).to_dict()
        self.assertEqual(list(result), RESULT_FIELDS)
        self.assertEqual(result["source_ids"], ["A001", "A002"])
        self.assertEqual(result["chain_ids"], ["trial:NCT02296125"])
        self.assertEqual(result["citations"], ["A001", "A002"])
        self.assertFalse(result["used_llm"])

    def test_unknown_source_is_insufficient_not_refused(self):
        result = self.adapters.grounded_qa_local(self.cases["UNSUP-001"])
        self.assertEqual(result.source_ids, [])
        self.assertFalse(result.refused)
        self.assertEqual(result.safety_category, "")
        self.assertIn("当前数据不足", result.answer)


if __name__ == "__main__":
    unittest.main()
