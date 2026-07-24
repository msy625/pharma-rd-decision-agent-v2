import unittest

from evaluation.metrics import (
    aggregate_results,
    citation_whitelist_compliance,
    evaluate_case,
    exact_set_match,
    latency_summary,
    retrieval_precision_at_k,
    retrieval_recall_at_k,
    set_f1,
    set_precision,
    set_recall,
    zero_out_of_whitelist,
)
from evaluation.runner import DEFAULT_CASES_PATH
from evaluation.validators import load_cases


class EvaluationMetricsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cases = {case["case_id"]: case for case in load_cases(DEFAULT_CASES_PATH)}

    def test_precision_at_k_uses_actual_nonempty_prefix_denominator(self):
        self.assertEqual(retrieval_precision_at_k(["A005", "A001"], ["A005", "A006"], 5), 0.5)
        self.assertEqual(retrieval_precision_at_k([], ["A005"], 5), 0.0)

    def test_recall_at_k_uses_gold_denominator(self):
        self.assertEqual(retrieval_recall_at_k(["A005", "A001"], ["A005", "A006"], 5), 0.5)

    def test_source_set_metrics_cover_empty_full_and_partial_cases(self):
        self.assertEqual(set_precision([], []), 1.0)
        self.assertEqual(set_recall([], []), 1.0)
        self.assertEqual(set_f1(["A005", "A001"], ["A005", "A006"]), 0.5)
        self.assertEqual(exact_set_match(["A006", "A005"], ["A005", "A006"]), 1.0)

    def test_citation_whitelist_and_zero_overflow(self):
        self.assertEqual(citation_whitelist_compliance(["B015", "B016"], ["B015", "B016"]), 1.0)
        self.assertEqual(citation_whitelist_compliance(["B015", "B002"], ["B015", "B016"]), 0.5)
        self.assertEqual(zero_out_of_whitelist(["B015", "B002"], ["B015", "B016"]), 0.0)

    def test_required_fact_and_forbidden_claim_metrics(self):
        case = self.cases["REG-001"]
        result = {
            "source_ids": ["B015", "B016"],
            "chain_ids": ["regulatory:tevimbra-eu-nsclc"],
            "citations": ["B015", "B016"],
            "answer": (
                "B016是2025-07-24的CHMP积极意见，非欧盟委员会最终批准。"
                "B015记录2023-09-15为Tevimbra欧盟初始许可。"
                "当前EPAR已将围手术期NSCLC适应症列入正式授权范围。"
            ),
            "question_type": "regulatory_status",
            "safety_category": "",
            "refused": False,
            "used_llm": False,
            "limitations": [],
            "latency_ms": 1.0,
            "error": "",
        }
        metrics = evaluate_case(case, result)
        self.assertEqual(metrics["required_fact_coverage"], 1.0)
        self.assertEqual(metrics["forbidden_claim_trigger_rate"], 0.0)
        self.assertEqual(metrics["regulatory_hard_pass"], 1.0)

    def test_out_of_whitelist_citation_and_forbidden_claim_fail(self):
        case = self.cases["REG-001"]
        result = {
            "source_ids": ["B015", "B016", "B002"],
            "chain_ids": ["regulatory:tevimbra-eu-nsclc"],
            "citations": ["B015", "B016", "B002"],
            "answer": "B016是欧盟委员会最终批准文件。",
            "question_type": "regulatory_status",
            "safety_category": "",
            "refused": False,
            "used_llm": False,
            "limitations": [],
            "latency_ms": 1.0,
            "error": "",
        }
        metrics = evaluate_case(case, result)
        self.assertLess(metrics["citation_whitelist_compliance"], 1.0)
        self.assertGreater(metrics["forbidden_claim_trigger_rate"], 0.0)
        self.assertEqual(metrics["overall_pass"], 0.0)

    def test_latency_mean_median_and_nearest_rank_p95(self):
        summary = latency_summary([1, 2, 3, 4, 100])
        self.assertEqual(summary["mean_latency_ms"], 22)
        self.assertEqual(summary["median_latency_ms"], 3)
        self.assertEqual(summary["p95_latency_ms"], 100)

    def test_aggregate_fact_and_forbidden_metrics_use_applicable_denominators(self):
        base_metrics = {
            "retrieval_precision_at_k": 1.0,
            "retrieval_recall_at_k": 1.0,
            "source_precision": 1.0,
            "source_recall": 1.0,
            "source_f1": 1.0,
            "source_exact_match": 1.0,
            "chain_exact_match": 1.0,
            "chain_f1": 1.0,
            "citation_whitelist_compliance": 1.0,
            "zero_out_of_whitelist": 1.0,
            "required_fact_coverage": 1.0,
            "forbidden_claim_trigger_rate": 0.0,
            "required_limitation_coverage": 1.0,
            "regulatory_hard_pass": None,
            "evidence_insufficiency_pass": None,
            "safety_classification_correct": None,
            "prohibited_refusal_correct": None,
            "question_type_correct": 1.0,
            "latency_within_budget": 1.0,
            "overall_pass": 1.0,
            "manual_review_pending": False,
            "failure_reasons": [],
            "limitation_details": [],
        }
        records = [
            {
                "baseline": "test",
                "category": "source_search",
                "allowed_source_ids": ["A001"],
                "result": {"citations": ["A001"], "latency_ms": 1.0},
                "metrics": {
                    **base_metrics,
                    "fact_details": [{"passed": True}],
                    "forbidden_claim_details": [],
                },
            },
            {
                "baseline": "test",
                "category": "regulatory_status",
                "allowed_source_ids": ["B015"],
                "result": {"citations": ["B002"], "latency_ms": 2.0},
                "metrics": {
                    **base_metrics,
                    "fact_details": [{"passed": False}],
                    "forbidden_claim_details": [{"passed": True}],
                },
            },
        ]
        summary = aggregate_results(records)["baseline_summary"][0]
        self.assertEqual(summary["required_fact_coverage"], 0.5)
        self.assertEqual(summary["forbidden_claim_trigger_rate"], 1.0)
        self.assertEqual(summary["citation_whitelist_compliance"], 0.5)


if __name__ == "__main__":
    unittest.main()
