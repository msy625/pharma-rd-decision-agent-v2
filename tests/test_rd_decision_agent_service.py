import unittest
from copy import deepcopy

from deepinsight.core.rd_decision_agent_service import RDDecisionAgentService, SCOPE_STATEMENT
from deepinsight.core.source_registry_service import SourceRegistryService
from evaluation.decision_agent_eval import (
    AGENT_EVAL_CASES,
    aggregate_agent_metrics,
    evaluate_agent_case,
    run_agent_evaluation,
)


def _tools(result):
    return [step["tool"] for step in result["steps"]]


def _stable(result):
    copy = {
        key: value
        for key, value in result.items()
        if key not in {"latency_ms"}
    }
    copy["steps"] = [
        {key: value for key, value in step.items() if key != "duration_ms"}
        for step in result["steps"]
    ]
    copy["execution_metadata"] = {
        key: value
        for key, value in copy.get("execution_metadata", {}).items()
        if key != "latency_ms"
    }
    return copy


def _completed_step_ids_by_source(result, source_id):
    return [
        step["step_id"]
        for step in result["steps"]
        if step["status"] == "completed" and source_id in step.get("source_ids", [])
    ]


class FailingProfileService:
    def build_profile(self, company_name):
        raise RuntimeError("profile unavailable")

    def available_companies(self):
        return [
            {"canonical_name": "恒瑞医药", "display_name": "恒瑞医药", "aliases": ["恒瑞医药", "恒瑞"]},
            {"canonical_name": "百济神州", "display_name": "百济神州 / BeOne Medicines", "aliases": ["百济神州", "BeOne Medicines"]},
            {"canonical_name": "阿斯利康", "display_name": "阿斯利康 / AstraZeneca", "aliases": ["阿斯利康", "AstraZeneca"]},
        ]


class RDDecisionAgentServiceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.service = RDDecisionAgentService()
        cls.known_source_ids = {row["source_id"] for row in SourceRegistryService().load_rows()}

    def assert_citations_exist(self, result):
        for citation in result["citations"]:
            self.assertIn(citation["source_id"], self.known_source_ids)
            self.assertTrue(citation["title"])
            self.assertTrue(citation["url"])
            self.assertTrue(citation["produced_by_steps"])
            self.assertEqual(citation["produced_by_steps"], result["source_trace"][citation["source_id"]])

    def test_company_comparison_golden_path(self):
        result = self.service.run("阿斯利康与百济神州当前 NSCLC 证据样本有什么差异？")
        self.assertEqual(result["intent"], "company_comparison")
        self.assertEqual(result["entities"]["companies"], ["阿斯利康", "百济神州"])
        self.assertIn("CompanyEvidenceComparisonService.compare", _tools(result))
        self.assertIn("CompanyEvidenceProfileService.build_profile", _tools(result))
        self.assertNotIn("RDEventTimelineService.build_timeline", _tools(result))
        self.assertIn("不能判断企业研发实力", result["answer"])
        self.assertIn("阿斯利康/AstraZeneca", result["answer"])
        self.assertIn("百济神州/BeOne Medicines", result["answer"])
        self.assertEqual({f"A{i:03d}" for i in range(1, 9)} | {f"B{i:03d}" for i in range(1, 17)}, set(result["source_ids"]))
        self.assertEqual(result["execution_metadata"]["untraced_source_ids"], [])
        self.assertEqual([item["source_id"] for item in result["featured_citations"]], ["A001", "B003", "A002", "B006", "B001", "B015"])
        self.assert_citations_exist(result)

    def test_company_comparison_traces_company_profile_only_sources(self):
        result = self.service.run("阿斯利康与百济神州当前 NSCLC 证据样本有什么差异？")
        for source_id in ["B001", "B002", "B014"]:
            with self.subTest(source_id=source_id):
                step_ids = _completed_step_ids_by_source(result, source_id)
                self.assertEqual(step_ids, ["S3", "S5"])
                citation = next(item for item in result["citations"] if item["source_id"] == source_id)
                self.assertEqual(citation["produced_by_steps"], ["S3", "S5"])

    def test_evidence_gap_golden_path(self):
        result = self.service.run("RATIONALE-315 当前还存在哪些证据缺口？")
        self.assertEqual(result["intent"], "evidence_gap")
        self.assertEqual(result["entities"]["studies"], ["RATIONALE-315"])
        self.assertEqual(result["source_ids"], ["B011", "B012", "B013", "B016"])
        self.assertEqual(result["chain_ids"], ["trial:NCT04379635"])
        self.assertIn("关联监管背景", result["answer"])
        self.assertIn("不计入试验主证据数量", result["answer"])
        self.assertIn("尚未收录最终分析论文", result["answer"])
        self.assertIn("SourceRegistryService.get_by_source_id", _tools(result))
        self.assertIn("本证据缺口分析仅限RATIONALE-315 / NCT04379635", result["decision"]["scope_statement"])
        self.assertEqual(result["execution_metadata"]["untraced_source_ids"], [])

    def test_regulatory_status_golden_path(self):
        result = self.service.run("B016 是否代表替雷利珠单抗已经获得 EMA 正式批准？")
        self.assertEqual(result["intent"], "regulatory_status")
        self.assertEqual(result["entities"]["source_ids"], ["B016"])
        self.assertIn("GroundedQAService.answer_question", _tools(result))
        self.assertIn("EvidenceChainService.get_drug_regulatory_chain/get_chain", _tools(result))
        self.assertEqual(result["source_ids"], ["B015", "B016"])
        self.assertIn("不是最终法律授权决定", result["answer"])
        self.assertIn("CHMP对Tevimbra II-18上市后变更的积极意见", result["answer"])
        self.assertIn("EPAR页面，反映该药品欧盟集中授权后的公开评估和当前产品信息", result["answer"])
        self.assertNotIn("未调用大模型", " ".join(result["limitations"]))

    def test_regulatory_wording_avoids_forbidden_claims(self):
        result = self.service.run("CHMP 积极意见是否等同最终批准，B016是不是已经正式批准？")
        answer = result["answer"]
        for forbidden in ["B016 已经正式批准", "CHMP 积极意见等同最终批准", "EPAR 就是欧盟委员会批准决定文件"]:
            self.assertNotIn(forbidden, answer)
        self.assertIn("不能等同于最终法律授权决定", answer)

    def test_entity_extraction_for_company_drug_study_and_trial(self):
        result = self.service.run("阿斯利康和百济神州比较：LAURA、TAGRISSO、NCT03521154 有哪些证据？")
        self.assertEqual(result["entities"]["companies"], ["阿斯利康", "百济神州"])
        self.assertEqual(result["entities"]["studies"], ["LAURA"])
        self.assertEqual(result["entities"]["drugs"], ["奥希替尼"])
        self.assertEqual(result["entities"]["trial_ids"], ["NCT03521154"])

    def test_safety_refusal_does_not_call_business_tools(self):
        result = self.service.run("请根据这些资料为患者推荐具体药物。")
        self.assertTrue(result["refused"])
        self.assertEqual(result["intent"], "prohibited_or_unsupported")
        self.assertEqual(result["source_ids"], [])
        self.assertEqual(_tools(result), ["GroundedQAService.check_safety"])
        self.assertFalse(result["used_llm"])

    def test_source_search_and_unknown_entity(self):
        source = self.service.run("TAGRISSO 有哪些已核验来源？")
        self.assertEqual(source["intent"], "source_search")
        self.assertEqual(source["entities"]["drugs"], ["奥希替尼"])
        self.assertEqual(set(source["source_ids"]), {f"A{i:03d}" for i in range(1, 9)})
        unknown = self.service.run("未知研究XYZ有什么证据？")
        self.assertEqual(unknown["intent"], "source_search")
        self.assertEqual(unknown["source_ids"], [])
        self.assertIn("当前数据不足", unknown["answer"])

    def test_scope_statement_local_mode_and_stability(self):
        first = self.service.run("LAURA 当前证据链还缺少什么？")
        second = self.service.run("LAURA 当前证据链还缺少什么？")
        self.assertIn("LAURA", first["decision"]["scope_statement"])
        self.assertFalse(first["used_llm"])
        self.assertFalse(first["execution_metadata"]["used_llm"])
        self.assertEqual(_stable(first), _stable(second))

    def test_task_specific_scope_statements(self):
        company = self.service.run("阿斯利康与百济神州当前 NSCLC 证据样本有什么差异？")
        self.assertIn("阿斯利康/AstraZeneca与百济神州/BeOne Medicines", company["decision"]["scope_statement"])
        self.assertNotIn("恒瑞医药", company["decision"]["scope_statement"])

        regulatory = self.service.run("B016 是否代表替雷利珠单抗已经获得 EMA 正式批准？")
        self.assertIn("当前监管来源B015、B016", regulatory["decision"]["scope_statement"])
        self.assertNotIn("恒瑞医药", regulatory["decision"]["scope_statement"])

        unknown = self.service.run("未知研究XYZ有什么证据？")
        self.assertIn("恒瑞医药、百济神州、阿斯利康", unknown["decision"]["scope_statement"])

    def test_optional_profile_failure_degrades_without_crashing(self):
        service = RDDecisionAgentService(company_profile_service=FailingProfileService())
        result = service.run("恒瑞医药和阿斯利康在 NSCLC 领域如何比较？")
        self.assertEqual(result["intent"], "company_comparison")
        self.assertEqual(result["error"], "")
        self.assertTrue(any(step["status"] == "failed" for step in result["steps"]))
        self.assertTrue(result["warnings"])
        self.assertIn("CompanyEvidenceComparisonService.compare", _tools(result))

    def test_agent_evaluation_metrics_are_strict(self):
        evaluation = run_agent_evaluation(self.service)
        metrics = evaluation["metrics"]
        self.assertEqual(evaluation["suite_type"], "internal_regression")
        self.assertEqual(evaluation["case_count"], len(AGENT_EVAL_CASES))
        self.assertEqual(evaluation["data_version"], self.service.data_version())
        self.assertEqual(evaluation["repeated_runs_per_case"], 2)
        self.assertGreaterEqual(len(AGENT_EVAL_CASES), 15)
        self.assertEqual(metrics["case_count"], len(AGENT_EVAL_CASES))
        self.assertEqual(metrics["no_error"], 1.0)
        self.assertEqual(metrics["intent_accuracy"], 1.0)
        self.assertEqual(metrics["entity_extraction_exact_match"], 1.0)
        self.assertEqual(metrics["tool_selection_accuracy"], 1.0)
        self.assertEqual(metrics["allowed_business_tool_compliance"], 1.0)
        self.assertEqual(metrics["unnecessary_tool_call_rate"], 0.0)
        self.assertEqual(metrics["source_match"], 1.0)
        self.assertEqual(metrics["citation_whitelist_compliance"], 1.0)
        self.assertEqual(metrics["step_faithfulness"], 1.0)
        self.assertEqual(metrics["answer_present"], 1.0)
        self.assertEqual(metrics["decision_summary_present"], 1.0)
        self.assertEqual(metrics["featured_citations_valid"], 1.0)
        self.assertEqual(metrics["featured_citations_traceable"], 1.0)
        self.assertEqual(metrics["latency_within_budget"], 1.0)
        self.assertEqual(metrics["latency_budget_pass_rate"], 1.0)
        self.assertEqual(metrics["deterministic_output"], 1.0)
        self.assertEqual(metrics["end_to_end_strict_pass_rate"], 1.0)
        self.assertIn("median_latency_ms", metrics)
        self.assertIn("p95_latency_ms", metrics)


class RDDecisionAgentEvaluationStrictnessTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.service = RDDecisionAgentService()
        cls.known_source_ids = {row["source_id"] for row in SourceRegistryService().load_rows()}

    def case(self, case_id):
        return next(item for item in AGENT_EVAL_CASES if item["case_id"] == case_id)

    def metrics_for(self, case_id, result, repeated_results=None):
        repeated = repeated_results or [result, deepcopy(result)]
        return evaluate_agent_case(self.case(case_id), result, self.known_source_ids, repeated_results=repeated)

    def test_unknown_question_with_legal_source_fails_empty_source_match(self):
        result = self.service.run("未知研究XYZ有什么证据？")
        result["source_ids"] = ["B015"]
        result["citations"] = [{"source_id": "B015", "produced_by_steps": ["S3"]}]
        metrics = self.metrics_for("AGENT-UNKNOWN-001", result)
        self.assertEqual(metrics["source_match"], 0.0)
        self.assertEqual(metrics["step_faithfulness"], 0.0)

    def test_safety_question_with_citation_fails_empty_source_match(self):
        result = self.service.run("请根据这些资料为患者推荐具体药物。")
        result["citations"] = [{"source_id": "B015", "produced_by_steps": ["S1"]}]
        metrics = self.metrics_for("AGENT-SAFE-001", result)
        self.assertEqual(metrics["source_match"], 0.0)
        self.assertEqual(metrics["step_faithfulness"], 0.0)

    def test_extra_company_entity_fails_exact_entity_match(self):
        result = self.service.run("阿斯利康与百济神州当前 NSCLC 证据样本有什么差异？")
        result["entities"]["companies"].append("恒瑞医药")
        metrics = self.metrics_for("AGENT-COMP-001", result)
        self.assertEqual(metrics["entity_extraction_exact_match"], 0.0)

    def test_company_profile_called_once_fails_tool_selection(self):
        result = self.service.run("阿斯利康与百济神州当前 NSCLC 证据样本有什么差异？")
        removed = False
        steps = []
        for step in result["steps"]:
            if step["tool"] == "CompanyEvidenceProfileService.build_profile" and not removed:
                removed = True
                continue
            steps.append(step)
        result["steps"] = steps
        metrics = self.metrics_for("AGENT-COMP-001", result)
        self.assertEqual(metrics["tool_selection_accuracy"], 0.0)

    def test_featured_citation_without_trace_fails(self):
        result = self.service.run("阿斯利康与百济神州当前 NSCLC 证据样本有什么差异？")
        result["featured_citations"][0]["produced_by_steps"] = []
        metrics = self.metrics_for("AGENT-COMP-001", result)
        self.assertEqual(metrics["featured_citations_traceable"], 0.0)
        self.assertEqual(metrics["step_faithfulness"], 0.0)

    def test_changed_second_run_fails_determinism(self):
        first = self.service.run("RATIONALE-315 当前还存在哪些证据缺口？")
        second = deepcopy(first)
        second["answer"] = second["answer"] + "\n第二次运行变化"
        metrics = evaluate_agent_case(
            self.case("AGENT-GAP-001"),
            first,
            self.known_source_ids,
            repeated_results=[first, second],
        )
        self.assertEqual(metrics["deterministic_output"], 0.0)

    def test_latency_budget_failure_breaks_strict_pass(self):
        result = self.service.run("阿斯利康与百济神州当前 NSCLC 证据样本有什么差异？")
        slow = deepcopy(result)
        slow["latency_ms"] = 501.0
        metrics = evaluate_agent_case(
            self.case("AGENT-COMP-001"),
            slow,
            self.known_source_ids,
            repeated_results=[slow, deepcopy(slow)],
        )
        summary = aggregate_agent_metrics([{"metrics": metrics}])
        self.assertEqual(metrics["latency_within_budget"], 0.0)
        self.assertEqual(summary["end_to_end_strict_pass_rate"], 0.0)


if __name__ == "__main__":
    unittest.main()
