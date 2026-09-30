import json
import os
import unittest
from unittest.mock import patch

from deepinsight.core.normalized_research_agent_service import NormalizedResearchAgentService


class NormalizedResearchAgentServiceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.service = NormalizedResearchAgentService()

    def test_company_question_uses_entity_retrieval_instead_of_full_sentence_match(self):
        result = self.service.run("恒瑞医药有哪些研发资料？", generation_mode="auto")
        self.assertIn("H003", result["source_ids"])
        self.assertIn("已检索到", result["answer"])
        self.assertNotIn("【分析】", result["answer"])
        self.assertNotIn("【下一步核验】", result["answer"])
        self.assertEqual(result["execution_metadata"]["generation_mode_used"], "local")
        self.assertTrue(result["execution_metadata"]["fallback_used"])
        self.assertTrue(result["decision"])

    def test_capabilities_report_current_company_coverage(self):
        capabilities = self.service.capabilities()
        self.assertGreater(len(capabilities["supported_companies"]), 0)
        self.assertIn("恒瑞医药", capabilities["supported_companies"])
        self.assertEqual(capabilities["source_count"], len(self.service.source_service.load_rows()))

    def test_trial_question_returns_traceable_source_and_steps(self):
        result = self.service.run("NCT04818333 有哪些证据？")
        self.assertEqual(result["source_ids"], ["H003"])
        self.assertEqual(result["source_trace"]["H003"], ["S2", "S3"])
        self.assertEqual([step["step_id"] for step in result["steps"]], ["S1", "S2", "S3"])

    def test_institution_question_returns_current_data_analysis(self):
        result = self.service.run("恒瑞医药的研发情况如何？", generation_mode="local")
        self.assertEqual(result["intent"], "institution_analysis")
        self.assertIn("本次检索命中", result["answer"])
        self.assertIn("研究证据链", result["answer"])
        self.assertNotIn("【直接回答】", result["answer"])
        self.assertNotIn("【下一步核验】", result["answer"])
        self.assertIn("H003", result["source_ids"])
        self.assertTrue(result["chain_ids"])

    def test_unknown_question_returns_a_grounded_empty_result(self):
        result = self.service.run("未知研究XYZ有什么证据？")
        self.assertEqual(result["source_ids"], [])
        self.assertIn("未检索到", result["answer"])
        self.assertFalse(result["error"])

    def test_regulatory_question_returns_specific_non_redundant_conclusion(self):
        result = self.service.run("请说明B016与B015的监管状态和区别", generation_mode="auto")
        self.assertEqual(result["intent"], "regulatory_status")
        self.assertEqual(result["source_ids"], ["B015", "B016"])
        self.assertEqual([item["source_id"] for item in result["citations"]], ["B015", "B016"])
        self.assertIn("B016是2025-07-24的CHMP积极意见", result["answer"])
        self.assertIn("B015是EMA/欧盟正式授权记录", result["answer"])
        self.assertNotIn("已检索到 20 条", result["answer"])
        self.assertNotIn("【分析】", result["answer"])
        self.assertNotIn("【下一步核验】", result["answer"])
        self.assertTrue(result["answer_is_structured"])

    def test_steps_expose_actual_input_and_entities_without_empty_source_placeholder(self):
        result = self.service.run("请说明B016与B015的监管状态和区别")
        self.assertTrue(result["entities"]["source_ids"])
        self.assertTrue(result["steps"][0]["input_summary"])
        self.assertTrue(result["steps"][0]["result_summary"])
        self.assertEqual(result["steps"][0]["source_ids"], [])
        self.assertIn("识别", result["steps"][1]["result_summary"])

    def test_model_sectioned_answer_is_reduced_to_direct_answer(self):
        answer = "【直接回答】这是结论。\n\n【分析】这是分析。\n\n【下一步核验】这是建议。"
        self.assertEqual(self.service.direct_answer_text(answer), "这是结论。")

    def test_auto_mode_uses_model_for_specific_grounded_question(self):
        from starlette.requests import Request
        from deepinsight.core import grounded_qa_llm
        from webapp import main

        class FakeResponse:
            def __init__(self, content):
                self.choices = [type("Choice", (), {"message": type("Message", (), {"content": content})()})()]

        class FakeClient:
            def __init__(self):
                self.calls = []
                self.chat = type("Chat", (), {})()
                self.chat.completions = type("Completions", (), {})()
                self.chat.completions.create = self.create

            def create(self, **kwargs):
                self.calls.append(kwargs)
                return FakeResponse(json.dumps({
                    "answer": "B016是CHMP积极意见，不是最终法律授权；B015是欧盟正式授权记录。",
                    "citations": [
                        {"source_id": "B015", "support_summary": "欧盟正式授权记录"},
                        {"source_id": "B016", "support_summary": "CHMP积极意见"},
                    ],
                    "limitations": [],
                }, ensure_ascii=False))

        question = "请说明B016与B015的监管状态和区别"
        local = self.service.run(question, generation_mode="auto")
        client = FakeClient()
        scope = {
            "type": "http", "method": "POST", "path": "/api/evidence/decision-agent",
            "headers": [], "client": ("testclient", 0), "server": ("test", 80),
            "scheme": "http", "query_string": b"",
        }
        main._GROUNDED_QA_USAGE_GUARD = None
        with patch.dict(os.environ, {"DEEPSEEK_API_KEY": "test-key", "GROUNDED_QA_LLM_ENABLED": "true"}, clear=False), patch.object(
            grounded_qa_llm, "create_grounded_llm_client", return_value=client
        ):
            result = main._decision_agent_auto_result(self.service, local, question, Request(scope))
        self.assertEqual(len(client.calls), 1)
        self.assertTrue(result["used_llm"])
        self.assertEqual(result["execution_metadata"]["generation_mode_used"], "llm")
        self.assertNotIn("【分析】", result["answer"])

    def test_trial_evidence_question_uses_chain_facts_instead_of_count_summary(self):
        result = self.service.run("NCT04818333 有哪些证据？")
        self.assertEqual(result["intent"], "evidence_chain")
        self.assertEqual(result["source_ids"], ["H003"])
        self.assertIn("SHR-A1811 / NCT04818333", result["answer"])
        self.assertIn("证据缺口", result["answer"])
        self.assertNotIn("已检索到 1 条", result["answer"])
