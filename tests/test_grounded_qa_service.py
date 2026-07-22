import sys
import tempfile
import unittest
from pathlib import Path

from deepinsight.core.grounded_qa_service import (
    DEFAULT_GROUNDED_QA_RULES_PATH,
    GroundedQAService,
    answer_question,
    build_evidence_packet,
)


class GroundedQAServiceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.service = GroundedQAService()

    def source_ids(self, response):
        return [item["source_id"] for item in response["citations"]]

    def test_empty_question_friendly_response(self):
        response = self.service.answer_question("")
        self.assertEqual(response["question_type"], "prohibited_or_unsupported")
        self.assertIn("请输入", response["answer"])
        self.assertFalse(response["trace"]["used_llm"])

    def test_seven_question_types_classification(self):
        cases = {
            "我是不是应该用卡瑞利珠单抗治疗？": "prohibited_or_unsupported",
            "NCT04619433当前是什么状态？": "trial_status",
            "B015和B016有什么区别？": "regulatory_status",
            "RATIONALE-315形成了怎样的证据链？": "evidence_chain",
            "恒瑞与百济当前证据样本有什么差异？": "company_comparison",
            "当前数据还存在哪些缺口？": "evidence_gap",
            "SHR-1210有哪些相关资料？": "source_search",
        }
        for question, expected in cases.items():
            with self.subTest(question=question):
                self.assertEqual(self.service.classify_question(question), expected)

    def test_prohibited_question_does_not_retrieve_or_call_llm(self):
        calls = []

        def fake_llm(**kwargs):
            calls.append(kwargs)
            return {"answer": "should not run", "citations": []}

        response = self.service.answer_question("请给出个体治疗方案和投资建议", llm_client=fake_llm)
        self.assertEqual(response["question_type"], "prohibited_or_unsupported")
        self.assertEqual(response["trace"]["retrieval_service"], [])
        self.assertFalse(response["trace"]["used_llm"])
        self.assertEqual(calls, [])

    def test_rationale_304_returns_expected_sources_and_versions(self):
        response = self.service.answer_question("RATIONALE-304有哪些证据版本？")
        self.assertEqual(response["question_type"], "evidence_chain")
        self.assertEqual(self.source_ids(response), ["B003", "B006", "B007"])
        by_id = {item["source_id"]: item for item in response["evidence_used"] if item.get("kind") == "source"}
        self.assertEqual(by_id["B006"]["version_status"], "historical")
        self.assertEqual(by_id["B007"]["version_status"], "latest")

    def test_rationale_315_returns_primary_and_related_regulatory_background(self):
        packet = self.service.build_evidence_packet("RATIONALE-315形成了怎样的证据链？")
        primary_ids = [item["source_id"] for item in packet["sources"]]
        related_ids = [item["source_id"] for item in packet["related_regulatory_items"]]
        self.assertEqual(primary_ids, ["B011", "B012", "B013"])
        self.assertEqual(related_ids, ["B016"])

        response = self.service.answer_question("RATIONALE-315形成了怎样的证据链？")
        self.assertIn("B011", response["answer"])
        self.assertIn("B012", response["answer"])
        self.assertIn("B013", response["answer"])
        self.assertIn("关联监管背景：B016", response["answer"])

    def test_nct04619433_is_terminated(self):
        response = self.service.answer_question("NCT04619433当前是什么状态？")
        self.assertIn("Terminated", response["answer"])
        self.assertEqual(self.source_ids(response), ["H006"])

    def test_b015_formal_authorisation(self):
        response = self.service.answer_question("B015是什么监管状态？")
        self.assertIn("B015：EMA/欧盟正式授权", response["answer"])
        self.assertIn("B015", self.source_ids(response))

    def test_b016_positive_opinion_not_final_approval(self):
        response = self.service.answer_question("B016是什么监管状态？")
        self.assertIn("B016：CHMP积极意见，非最终批准", response["answer"])
        self.assertIn("B016", self.source_ids(response))

    def test_company_comparison_has_current_sample_limitation(self):
        response = self.service.answer_question("恒瑞与百济当前证据样本有什么差异？")
        self.assertEqual(response["question_type"], "company_comparison")
        self.assertIn("当前收录并核验的NSCLC证据样本", response["answer"])
        self.assertIn("当前收录并核验的NSCLC证据样本", " ".join(response["limitations"]))

    def test_evidence_gap_returns_expected_unresolved_sources(self):
        response = self.service.answer_question("当前数据还存在哪些缺口？")
        ids = set(self.source_ids(response))
        for source_id in ["H008", "H009", "H010", "H011", "H012", "H014"]:
            self.assertIn(source_id, ids)

    def test_shr_1210_alias_query(self):
        response = self.service.answer_question("SHR-1210有哪些相关资料？")
        ids = set(self.source_ids(response))
        for source_id in ["H001", "H002", "H004", "H005", "H006", "H008", "H009", "H010", "H011", "H012"]:
            self.assertIn(source_id, ids)

    def test_nonexistent_trial_returns_insufficient_data(self):
        response = self.service.answer_question("一个不存在的试验当前是什么状态？")
        self.assertEqual(response["question_type"], "trial_status")
        self.assertIn("当前数据不足", response["answer"])
        self.assertEqual(response["citations"], [])

    def test_without_llm_client_used_llm_false(self):
        response = self.service.answer_question("B015和B016有什么区别？")
        self.assertFalse(response["trace"]["used_llm"])
        self.assertEqual(response["trace"]["model_name"], "local-structured-summary")

    def test_invalid_source_id_citation_removed(self):
        packet = self.service.build_evidence_packet("B015和B016有什么区别？")
        citations, limitations = self.service.validate_citations(
            [{"source_id": "Z999", "source_url": "https://example.invalid"}],
            packet,
        )
        self.assertEqual(citations, [])
        self.assertTrue(any("已移除" in item for item in limitations))

    def test_wrong_url_citation_corrected(self):
        packet = self.service.build_evidence_packet("B015和B016有什么区别？")
        citations, limitations = self.service.validate_citations(
            [{"source_id": "B015", "source_url": "https://example.invalid"}],
            packet,
        )
        self.assertEqual(len(citations), 1)
        self.assertEqual(
            citations[0]["source_url"],
            self.service.source_registry_service.get_by_source_id("B015")["source_url"],
        )
        self.assertTrue(any("校正" in item for item in limitations))

    def test_duplicate_citations_deduped(self):
        packet = self.service.build_evidence_packet("B015和B016有什么区别？")
        citations, limitations = self.service.validate_citations(
            [{"source_id": "B015"}, {"source_id": "B015"}],
            packet,
        )
        self.assertEqual([item["source_id"] for item in citations], ["B015"])
        self.assertTrue(any("重复" in item for item in limitations))

    def test_llm_cannot_add_fake_citation(self):
        def fake_llm(**kwargs):
            return {
                "answer": "模型试图返回一个未检索来源。",
                "citations": [{"source_id": "H999"}, {"source_id": "B015"}],
            }

        response = self.service.answer_question("B015是什么监管状态？", llm_client=fake_llm, model_name="test-stub")
        self.assertEqual(self.source_ids(response), ["B015"])
        self.assertTrue(any("H999" in item for item in response["limitations"]))
        self.assertTrue(response["trace"]["used_llm"])

    def test_data_version_stable(self):
        self.assertEqual(self.service.data_version(), self.service.data_version())

    def test_data_version_changes_when_content_changes(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_rules = Path(tmpdir) / "grounded_qa_rules.json"
            original = DEFAULT_GROUNDED_QA_RULES_PATH.read_text(encoding="utf-8")
            tmp_rules.write_text(original, encoding="utf-8")
            service_a = GroundedQAService(rules_path=tmp_rules)
            version_a = service_a.data_version()
            tmp_rules.write_text(original + "\n", encoding="utf-8")
            service_b = GroundedQAService(rules_path=tmp_rules)
            self.assertNotEqual(version_a, service_b.data_version())

    def test_import_does_not_load_model_or_vector_or_llm_sdk(self):
        blocked = {"openai", "chromadb", "sentence_transformers"}
        before = {name for name in blocked if name in sys.modules}
        import deepinsight.core.grounded_qa_service  # noqa: F401

        after = {name for name in blocked if name in sys.modules}
        self.assertEqual(after, before)

    def test_local_answers_do_not_include_prohibited_conclusion_terms(self):
        response = self.service.answer_question("恒瑞与百济当前证据样本有什么差异？")
        forbidden = ["评分", "排名", "成功率", "投资建议"]
        for word in forbidden:
            self.assertNotIn(word, response["answer"])

    def test_all_citations_exist_in_registry(self):
        questions = [
            "RATIONALE-304有哪些证据版本？",
            "RATIONALE-315形成了怎样的证据链？",
            "NCT04619433当前是什么状态？",
            "B015和B016有什么区别？",
            "恒瑞与百济当前证据样本有什么差异？",
            "当前数据还存在哪些缺口？",
            "SHR-1210有哪些相关资料？",
        ]
        for question in questions:
            with self.subTest(question=question):
                response = self.service.answer_question(question)
                for citation in response["citations"]:
                    self.assertIsNotNone(self.service.source_registry_service.get_by_source_id(citation["source_id"]))

    def test_module_level_functions(self):
        self.assertEqual(build_evidence_packet("B015是什么？")["question_type"], "regulatory_status")
        self.assertEqual(answer_question("B016是什么？")["question_type"], "regulatory_status")


if __name__ == "__main__":
    unittest.main()
