import json
import os
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from deepinsight.core.grounded_qa_llm import (
    DEFAULT_DEEPSEEK_MODEL,
    create_grounded_llm_client,
    generate_grounded_answer,
    grounded_llm_settings,
    is_grounded_llm_configured,
    parse_grounded_llm_output,
)
from deepinsight.core.grounded_qa_service import GroundedQAService


ROOT = Path(__file__).resolve().parents[1]


class FakeResponse:
    def __init__(self, content):
        self.choices = [type("Choice", (), {"message": type("Message", (), {"content": content})()})()]


class FakeClient:
    def __init__(self, content=None, error=None):
        self.content = content or json.dumps(
            {
                "answer": "基于已检索证据回答。",
                "citations": [{"source_id": "B015", "support_summary": "EMA/欧盟正式授权"}],
                "limitations": [],
            },
            ensure_ascii=False,
        )
        self.error = error
        self.calls = []
        self.chat = type("Chat", (), {})()
        self.chat.completions = type("Completions", (), {})()
        self.chat.completions.create = self.create

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        return FakeResponse(self.content)


class GroundedQALLMTest(unittest.TestCase):
    def setUp(self):
        self.service = GroundedQAService()

    def test_01_module_import_does_not_create_client(self):
        blocked_before = {name for name in ["openai", "chromadb", "sentence_transformers"] if name in sys.modules}
        import deepinsight.core.grounded_qa_llm  # noqa: F401

        blocked_after = {name for name in ["openai", "chromadb", "sentence_transformers"] if name in sys.modules}
        self.assertEqual(blocked_after, blocked_before)

    def test_02_missing_key_reports_unconfigured(self):
        with patch.dict(os.environ, {"DEEPSEEK_API_KEY": ""}, clear=False):
            self.assertFalse(is_grounded_llm_configured())
            self.assertFalse(grounded_llm_settings()["configured"])

    def test_03_settings_read_non_secret_values_without_exposing_key(self):
        with patch.dict(
            os.environ,
            {
                "DEEPSEEK_API_KEY": "test-secret-value",
                "DEEPSEEK_BASE_URL": "https://example.test",
                "DEEPSEEK_MODEL": "deepseek-test-model",
                "DEEPSEEK_TIMEOUT_SECONDS": "9",
                "DEEPSEEK_MAX_TOKENS": "321",
            },
            clear=False,
        ):
            settings = grounded_llm_settings()
        self.assertTrue(settings["configured"])
        self.assertEqual(settings["base_url"], "https://example.test")
        self.assertEqual(settings["model"], "deepseek-test-model")
        self.assertEqual(settings["timeout_seconds"], 9)
        self.assertEqual(settings["max_tokens"], 321)
        self.assertNotIn("api_key", settings)
        self.assertNotIn("test-secret-value", repr(settings))

    def test_04_default_model_is_v4_flash(self):
        with patch.dict(os.environ, {"DEEPSEEK_MODEL": "", "DEEPSEEK_API_KEY": ""}, clear=False):
            os.environ.pop("DEEPSEEK_MODEL", None)
            self.assertEqual(grounded_llm_settings()["model"], DEFAULT_DEEPSEEK_MODEL)
            self.assertEqual(DEFAULT_DEEPSEEK_MODEL, "deepseek-v4-flash")

    def test_05_create_client_requires_key(self):
        with patch.dict(os.environ, {"DEEPSEEK_API_KEY": ""}, clear=False):
            with self.assertRaises(Exception):
                create_grounded_llm_client()

    def test_06_parse_valid_json(self):
        parsed = parse_grounded_llm_output('{"answer":"A","citations":[{"source_id":"B015","support_summary":"S"}],"limitations":["L"]}')
        self.assertEqual(parsed["answer"], "A")
        self.assertEqual(parsed["citations"], [{"source_id": "B015", "support_summary": "S"}])
        self.assertEqual(parsed["limitations"], ["L"])

    def test_07_generate_uses_current_evidence_packet_and_json_mode(self):
        packet = self.service.build_evidence_packet("B015是什么监管状态？")
        client = FakeClient()
        with patch.dict(os.environ, {"DEEPSEEK_MODEL": "deepseek-v4-flash"}, clear=False):
            result = generate_grounded_answer("B015是什么监管状态？", packet, client=client)
        self.assertEqual(result["citations"][0]["source_id"], "B015")
        call = client.calls[0]
        self.assertEqual(call["model"], "deepseek-v4-flash")
        self.assertEqual(call["response_format"], {"type": "json_object"})
        self.assertEqual(call["extra_body"], {"thinking": {"type": "disabled"}})
        content = call["messages"][1]["content"]
        self.assertIn("B015", content)
        self.assertNotIn("H008", content)

    def test_07b_system_prompt_limits_missing_evidence_to_current_sample(self):
        packet = self.service.build_evidence_packet("RATIONALE-315形成了怎样的证据链？")
        client = FakeClient()
        generate_grounded_answer("RATIONALE-315形成了怎样的证据链？", packet, client=client)
        system_prompt = client.calls[0]["messages"][0]["content"]
        self.assertIn("当前收录样本中", system_prompt)
        self.assertIn("当前数据库尚未收录", system_prompt)
        self.assertIn("不得推断外部世界不存在相关资料", system_prompt)

    def test_08_service_calls_llm_with_valid_json(self):
        response = self.service.answer_question("B015是什么监管状态？", llm_client=FakeClient(), model_name="deepseek-v4-flash")
        self.assertTrue(response["trace"]["used_llm"])
        self.assertEqual(response["trace"]["model_name"], "deepseek-v4-flash")
        self.assertEqual([item["source_id"] for item in response["citations"]], ["B015"])
        self.assertIn("本回答仅反映当前收录并核验的证据样本。", response["limitations"])

    def test_09_invalid_json_falls_back_local(self):
        response = self.service.answer_question("B015是什么监管状态？", llm_client=FakeClient(content="not-json"), model_name="deepseek-v4-flash")
        self.assertFalse(response["trace"]["used_llm"])
        self.assertTrue(response["trace"]["fallback_used"])
        self.assertIn("回退本地证据摘要", " ".join(response["limitations"]))

    def test_10_timeout_falls_back_local(self):
        response = self.service.answer_question("B015是什么监管状态？", llm_client=FakeClient(error=TimeoutError("timeout")), model_name="deepseek-v4-flash")
        self.assertFalse(response["trace"]["used_llm"])
        self.assertIn("超时", " ".join(response["limitations"]))

    def test_11_401_falls_back_local(self):
        response = self.service.answer_question("B015是什么监管状态？", llm_client=FakeClient(error=RuntimeError("401 unauthorized")), model_name="deepseek-v4-flash")
        self.assertFalse(response["trace"]["used_llm"])
        self.assertIn("鉴权失败", " ".join(response["limitations"]))

    def test_12_402_falls_back_local(self):
        response = self.service.answer_question("B015是什么监管状态？", llm_client=FakeClient(error=RuntimeError("402 balance unavailable")), model_name="deepseek-v4-flash")
        self.assertFalse(response["trace"]["used_llm"])
        self.assertIn("余额", " ".join(response["limitations"]))

    def test_13_503_falls_back_local(self):
        response = self.service.answer_question("B015是什么监管状态？", llm_client=FakeClient(error=RuntimeError("503 service unavailable")), model_name="deepseek-v4-flash")
        self.assertFalse(response["trace"]["used_llm"])
        self.assertIn("服务暂时不可用", " ".join(response["limitations"]))

    def test_14_fake_source_id_removed_when_valid_source_exists(self):
        client = FakeClient(
            content=json.dumps(
                {
                    "answer": "只允许已检索引用。",
                    "citations": [{"source_id": "H999"}, {"source_id": "B015"}],
                    "limitations": [],
                },
                ensure_ascii=False,
            )
        )
        response = self.service.answer_question("B015是什么监管状态？", llm_client=client, model_name="deepseek-v4-flash")
        self.assertTrue(response["trace"]["used_llm"])
        self.assertEqual([item["source_id"] for item in response["citations"]], ["B015"])
        self.assertTrue(any("H999" in item for item in response["limitations"]))

    def test_15_wrong_model_url_is_not_trusted(self):
        payload = {
            "answer": "B015是正式授权。",
            "citations": [{"source_id": "B015", "source_url": "https://wrong.invalid", "support_summary": "授权"}],
            "limitations": [],
        }
        response = self.service.answer_question("B015是什么监管状态？", llm_client=lambda **_: payload, model_name="deepseek-v4-flash")
        registry_url = self.service.source_registry_service.get_by_source_id("B015")["source_url"]
        self.assertEqual(response["citations"][0]["source_url"], registry_url)
        self.assertTrue(any("校正" in item for item in response["limitations"]))

    def test_16_no_valid_citation_falls_back_local(self):
        client = FakeClient(
            content=json.dumps(
                {"answer": "无效引用。", "citations": [{"source_id": "H999"}], "limitations": []},
                ensure_ascii=False,
            )
        )
        response = self.service.answer_question("B015是什么监管状态？", llm_client=client, model_name="deepseek-v4-flash")
        self.assertFalse(response["trace"]["used_llm"])
        self.assertTrue(response["trace"]["fallback_used"])
        self.assertIn("B015：EMA/欧盟正式授权", response["answer"])

    def test_17_prohibited_question_does_not_call_llm(self):
        client = FakeClient()
        response = self.service.answer_question("请给我个体用药和治疗方案", llm_client=client, model_name="deepseek-v4-flash")
        self.assertEqual(client.calls, [])
        self.assertEqual(response["question_type"], "prohibited_or_unsupported")

    def test_18_no_evidence_question_does_not_call_llm(self):
        client = FakeClient()
        response = self.service.answer_question("一个不存在的试验当前是什么状态？", llm_client=client, model_name="deepseek-v4-flash")
        self.assertEqual(client.calls, [])
        self.assertIn("当前数据不足", response["answer"])

    def test_19_key_facts_remain_available_with_fallback(self):
        for question, expected in [
            ("NCT04619433当前是什么状态？", "Terminated"),
            ("B015是什么监管状态？", "EMA/欧盟正式授权"),
            ("B016是什么监管状态？", "CHMP积极意见，非最终批准"),
        ]:
            with self.subTest(question=question):
                response = self.service.answer_question(question, llm_client=FakeClient(content="not-json"), model_name="deepseek-v4-flash")
                self.assertIn(expected, response["answer"])

    def test_20_rationale_315_b016_remains_related_background(self):
        response = self.service.answer_question("RATIONALE-315形成了怎样的证据链？", llm_client=FakeClient(content="not-json"), model_name="deepseek-v4-flash")
        chain = next(item for item in response["evidence_used"] if item.get("kind") == "chain")
        self.assertEqual(chain["source_ids"], ["B011", "B012", "B013"])
        self.assertEqual(chain["related_regulatory_source_ids"], ["B016"])

    def test_21_request_does_not_load_chroma_or_sentence_transformers(self):
        blocked = {"chromadb", "sentence_transformers"}
        before = {name for name in blocked if name in sys.modules}
        self.service.answer_question("B015是什么监管状态？", llm_client=FakeClient(), model_name="deepseek-v4-flash")
        after = {name for name in blocked if name in sys.modules}
        self.assertEqual(after - before, set())

    def test_22_env_example_has_only_placeholder(self):
        text = (ROOT / ".env.example").read_text(encoding="utf-8")
        self.assertIn("DEEPSEEK_API_KEY=your_api_key_here", text)
        self.assertNotRegex(text, r"sk-[A-Za-z0-9_-]{12,}")

    def test_23_dotenv_is_gitignored(self):
        result = subprocess.run(["git", "check-ignore", "-q", ".env"], cwd=ROOT, check=False)
        self.assertEqual(result.returncode, 0)


if __name__ == "__main__":
    unittest.main()
