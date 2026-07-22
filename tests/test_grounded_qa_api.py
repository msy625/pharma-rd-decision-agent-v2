import asyncio
import json
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.parse import quote, unquote, urlsplit

import anyio.to_thread


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


WEBAPP_IMPORT_ERROR = None
webapp_main = None
try:
    from webapp import main as webapp_main
    from deepinsight.core import grounded_qa_llm
except Exception as exc:  # pragma: no cover
    WEBAPP_IMPORT_ERROR = exc


class _ASGIResponse:
    def __init__(self, status_code: int, body: bytes):
        self.status_code = status_code
        self.content = body
        self.text = body.decode("utf-8")

    def json(self):
        return json.loads(self.text)


class _ASGIClient:
    def __init__(self, app):
        self.app = app

    def get(self, path: str):
        return self._request("GET", path)

    def post(self, path: str, json_body=None):
        return self._request("POST", path, json_body=json_body)

    def _request(self, method: str, path: str, json_body=None):
        async def _request():
            parsed = urlsplit(path)
            messages = []
            request_sent = False
            body = b"" if json_body is None else json.dumps(json_body).encode("utf-8")
            headers = [(b"host", b"testserver"), (b"accept", b"application/json")]
            if method == "POST":
                headers.extend([(b"content-type", b"application/json"), (b"content-length", str(len(body)).encode("ascii"))])

            scope = {
                "type": "http",
                "asgi": {"version": "3.0", "spec_version": "2.3"},
                "http_version": "1.1",
                "method": method,
                "scheme": "http",
                "path": unquote(parsed.path),
                "raw_path": quote(parsed.path, safe="/%").encode("ascii"),
                "query_string": quote(parsed.query, safe="=&%").encode("ascii"),
                "headers": headers,
                "client": ("testclient", 50000),
                "server": ("testserver", 80),
                "root_path": "",
            }

            async def receive():
                nonlocal request_sent
                if not request_sent:
                    request_sent = True
                    return {"type": "http.request", "body": body, "more_body": False}
                await asyncio.sleep(0)
                return {"type": "http.disconnect"}

            async def send(message):
                messages.append(message)

            original_run_sync = anyio.to_thread.run_sync

            async def inline_run_sync(func, *args, abandon_on_cancel=False, cancellable=None, limiter=None):
                return func(*args)

            anyio.to_thread.run_sync = inline_run_sync
            try:
                await self.app(scope, receive, send)
            finally:
                anyio.to_thread.run_sync = original_run_sync
            start = next(message for message in messages if message["type"] == "http.response.start")
            body_bytes = b"".join(message.get("body", b"") for message in messages if message["type"] == "http.response.body")
            return _ASGIResponse(start["status"], body_bytes)

        return asyncio.run(_request())


class FakeResponse:
    def __init__(self, content):
        self.choices = [type("Choice", (), {"message": type("Message", (), {"content": content})()})()]


class FakeLLMClient:
    def __init__(self):
        self.calls = []
        self.chat = type("Chat", (), {})()
        self.chat.completions = type("Completions", (), {})()
        self.chat.completions.create = self.create

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return FakeResponse(
            json.dumps(
                {
                    "answer": "LLM基于B015组织答案。",
                    "citations": [{"source_id": "B015", "support_summary": "EMA/欧盟正式授权"}],
                    "limitations": [],
                },
                ensure_ascii=False,
            )
        )


@unittest.skipIf(webapp_main is None, f"webapp.main import unavailable: {WEBAPP_IMPORT_ERROR!r}")
class GroundedQAApiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = _ASGIClient(webapp_main.app)
        cls.source_service = webapp_main._evidence_service()

    def setUp(self):
        self.env_patcher = patch.dict(
            os.environ,
            {"DEEPSEEK_API_KEY": "", "DEEPSEEK_MODEL": "deepseek-v4-flash"},
            clear=False,
        )
        self.env_patcher.start()

    def tearDown(self):
        self.env_patcher.stop()

    def get_json(self, path: str, expected_status: int = 200):
        response = self.client.get(path)
        self.assertEqual(response.status_code, expected_status, response.text)
        return response.json()

    def post_json(self, question, generation_mode="auto", expected_status=200):
        body = {"generation_mode": generation_mode}
        if question is not None:
            body["question"] = question
        response = self.client.post("/api/evidence/grounded-qa", body)
        self.assertEqual(response.status_code, expected_status, response.text)
        return response.json()

    def result(self, question, generation_mode="auto"):
        return self.post_json(question, generation_mode)["result"]

    def citation_ids(self, result):
        return [item["source_id"] for item in result["citations"]]

    def test_01_capabilities_modes(self):
        payload = self.get_json("/api/evidence/grounded-qa/capabilities")
        self.assertTrue(payload["local_mode_available"])
        self.assertFalse(payload["llm_mode_available"])
        self.assertTrue(payload["requires_api_key_for_llm"])
        self.assertEqual(payload["model_name"], "deepseek-v4-flash")
        self.assertIn("DeepSeek尚未启用", payload["description"])

    def test_02_capabilities_contains_seven_question_types(self):
        payload = self.get_json("/api/evidence/grounded-qa/capabilities")
        self.assertEqual(
            set(payload["supported_question_types"]),
            {
                "source_search",
                "trial_status",
                "evidence_chain",
                "regulatory_status",
                "company_comparison",
                "evidence_gap",
                "prohibited_or_unsupported",
            },
        )

    def test_03_empty_question_returns_400(self):
        self.post_json("   ", expected_status=400)
        self.post_json(None, expected_status=400)

    def test_04_long_question_returns_400(self):
        self.post_json("问" * 1001, expected_status=400)

    def test_05_invalid_generation_mode_returns_400_or_422(self):
        response = self.client.post("/api/evidence/grounded-qa", {"question": "B015是什么？", "generation_mode": "remote"})
        self.assertIn(response.status_code, {400, 422}, response.text)

    def test_06_auto_without_client_uses_local(self):
        payload = self.post_json("B015是什么？", "auto")
        self.assertEqual(payload["metadata"]["generation_mode_requested"], "auto")
        self.assertEqual(payload["metadata"]["generation_mode_used"], "local")
        self.assertFalse(payload["metadata"]["llm_used"])
        self.assertFalse(payload["result"]["trace"]["used_llm"])

    def test_07_local_does_not_create_client(self):
        original_create = grounded_qa_llm.create_grounded_llm_client
        try:
            grounded_qa_llm.create_grounded_llm_client = lambda: (_ for _ in ()).throw(RuntimeError("should not create"))
            payload = self.post_json("B016是什么？", "local")
        finally:
            grounded_qa_llm.create_grounded_llm_client = original_create
        self.assertEqual(payload["metadata"]["generation_mode_requested"], "local")
        self.assertEqual(payload["metadata"]["generation_mode_used"], "local")
        self.assertIn("本地证据摘要", payload["result"]["answer"])

    def test_07b_auto_with_test_client_uses_llm(self):
        fake_client = FakeLLMClient()
        original_create = grounded_qa_llm.create_grounded_llm_client
        try:
            grounded_qa_llm.create_grounded_llm_client = lambda: fake_client
            with patch.dict(os.environ, {"DEEPSEEK_API_KEY": "test-secret", "DEEPSEEK_MODEL": "deepseek-v4-flash"}, clear=False):
                payload = self.post_json("B015是什么？", "auto")
        finally:
            grounded_qa_llm.create_grounded_llm_client = original_create
        self.assertEqual(len(fake_client.calls), 1)
        self.assertTrue(payload["metadata"]["llm_used"])
        self.assertEqual(payload["metadata"]["generation_mode_used"], "llm")
        self.assertEqual(payload["metadata"]["model_name"], "deepseek-v4-flash")
        self.assertIn("LLM基于B015", payload["result"]["answer"])

    def test_07c_capabilities_do_not_expose_key(self):
        with patch.dict(os.environ, {"DEEPSEEK_API_KEY": "test-secret", "DEEPSEEK_MODEL": "deepseek-v4-flash"}, clear=False):
            payload = self.get_json("/api/evidence/grounded-qa/capabilities")
        self.assertTrue(payload["llm_mode_available"])
        self.assertNotIn("test-secret", json.dumps(payload, ensure_ascii=False))
        self.assertNotIn("api_key", payload)

    def test_08_rationale_304_sources(self):
        result = self.result("RATIONALE-304有哪些证据版本？")
        self.assertEqual(self.citation_ids(result), ["B003", "B006", "B007"])

    def test_09_b006_historical_b007_latest(self):
        result = self.result("RATIONALE-304有哪些证据版本？")
        by_id = {item["source_id"]: item for item in result["evidence_used"] if item.get("kind") == "source"}
        self.assertEqual(by_id["B006"]["version_status"], "historical")
        self.assertEqual(by_id["B007"]["version_status"], "latest")

    def test_10_rationale_315_sources(self):
        result = self.result("RATIONALE-315形成了怎样的证据链？")
        self.assertGreaterEqual(set(self.citation_ids(result)), {"B011", "B012", "B013"})
        chain = next(item for item in result["evidence_used"] if item.get("kind") == "chain")
        self.assertEqual(chain["source_ids"], ["B011", "B012", "B013"])

    def test_11_b016_related_regulatory_background_only(self):
        result = self.result("RATIONALE-315形成了怎样的证据链？")
        chain = next(item for item in result["evidence_used"] if item.get("kind") == "chain")
        self.assertEqual(chain["related_regulatory_source_ids"], ["B016"])
        self.assertNotIn("B016", chain["source_ids"])

    def test_12_nct04619433_terminated(self):
        result = self.result("NCT04619433当前是什么状态？")
        self.assertIn("Terminated", result["answer"])
        self.assertEqual(self.citation_ids(result), ["H006"])

    def test_13_b015_formal_authorisation(self):
        result = self.result("B015为正式授权吗？")
        self.assertIn("B015：EMA/欧盟正式授权", result["answer"])

    def test_14_b016_positive_opinion_not_final(self):
        result = self.result("B016是什么监管状态？")
        self.assertIn("B016：CHMP积极意见，非最终批准", result["answer"])

    def test_15_company_comparison_current_sample_limit(self):
        result = self.result("恒瑞与百济当前证据样本有什么差异？")
        self.assertEqual(result["question_type"], "company_comparison")
        self.assertIn("当前收录并核验的NSCLC证据样本", result["answer"])

    def test_16_evidence_gap_returns_unresolved_links(self):
        result = self.result("当前数据还存在哪些缺口？")
        self.assertGreaterEqual(set(self.citation_ids(result)), {"H008", "H009", "H010", "H011", "H012", "H014"})

    def test_17_shr_1210_alias_query(self):
        result = self.result("SHR-1210有哪些相关资料？")
        self.assertGreaterEqual(set(self.citation_ids(result)), {"H001", "H002", "H004", "H005", "H006", "H008", "H009", "H010", "H011", "H012"})

    def test_18_missing_trial_returns_insufficient_data(self):
        result = self.result("一个不存在的试验当前是什么状态？")
        self.assertEqual(result["question_type"], "trial_status")
        self.assertIn("当前数据不足", result["answer"])
        self.assertEqual(result["citations"], [])

    def test_19_prohibited_question_returns_safety_notice(self):
        result = self.result("我该怎么治疗并买哪家公司股票？")
        self.assertEqual(result["question_type"], "prohibited_or_unsupported")
        self.assertIn("安全边界", result["answer"])
        self.assertIn("安全边界", result["safety_notice"])

    def test_20_prohibited_question_has_no_citations(self):
        result = self.result("请给出个体用药和成功率预测")
        self.assertEqual(result["citations"], [])
        self.assertEqual(result["trace"]["retrieval_service"], [])

    def test_21_all_citation_ids_and_urls_are_real(self):
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
                result = self.result(question)
                for citation in result["citations"]:
                    row = self.source_service.get_by_source_id(citation["source_id"])
                    self.assertIsNotNone(row)
                    self.assertEqual(citation["source_url"], row["source_url"])
                    self.assertTrue(citation["source_url"].startswith("http"))

    def test_22_metadata_llm_used_false(self):
        payload = self.post_json("B015是什么？")
        self.assertFalse(payload["metadata"]["llm_used"])
        self.assertFalse(payload["result"]["trace"]["used_llm"])

    def test_23_request_does_not_load_model_or_vector_modules(self):
        blocked = {"openai", "chromadb", "sentence_transformers"}
        before = {name for name in blocked if name in sys.modules}
        self.result("B015是什么？")
        after = {name for name in blocked if name in sys.modules}
        self.assertEqual(after - before, set())

    def test_24_existing_evidence_apis_still_work(self):
        self.assertEqual(self.get_json("/api/evidence/summary")["total_sources"], 31)
        self.assertEqual(self.get_json("/api/evidence/chain-summary")["total_chain_count"], 11)
        self.assertEqual(self.get_json("/api/evidence/company-comparison")["metadata"]["data_scope"], "first_version_nsclc_hengrui_beone")

    def test_25_error_response_does_not_leak_path_stack_or_key(self):
        original_factory = webapp_main._grounded_qa_service

        class BrokenService:
            def answer_question(self, *args, **kwargs):
                raise RuntimeError("/home/msy625/projects/pharma-rd-decision-agent-clean/secret.py DEEPSEEK_API_KEY traceback")

        try:
            webapp_main._grounded_qa_service = lambda: BrokenService()
            response = self.client.post("/api/evidence/grounded-qa", {"question": "B015是什么？"})
        finally:
            webapp_main._grounded_qa_service = original_factory
        self.assertEqual(response.status_code, 500, response.text)
        text = response.text
        self.assertNotIn("/home/", text)
        self.assertNotIn("DEEPSEEK_API_KEY", text)
        self.assertNotIn("traceback", text)


if __name__ == "__main__":
    unittest.main()
