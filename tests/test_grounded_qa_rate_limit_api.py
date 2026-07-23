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
grounded_qa_llm = None
try:
    from webapp import main as webapp_main
    from deepinsight.core import grounded_qa_llm
except Exception as exc:  # pragma: no cover
    WEBAPP_IMPORT_ERROR = exc


class _ASGIResponse:
    def __init__(self, status_code: int, headers: dict[str, str], body: bytes):
        self.status_code = status_code
        self.headers = headers
        self.content = body
        self.text = body.decode("utf-8")

    def json(self):
        return json.loads(self.text)


class _ASGIClient:
    def __init__(self, app):
        self.app = app

    def get(self, path: str):
        return self._request("GET", path)

    def post(self, path: str, json_body=None, *, client=("testclient", 50000)):
        return self._request("POST", path, json_body=json_body, client=client)

    def _request(self, method: str, path: str, json_body=None, *, client=("testclient", 50000)):
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
                "client": client,
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
            response_headers = {
                key.decode("latin1").lower(): value.decode("latin1")
                for key, value in start.get("headers", [])
            }
            return _ASGIResponse(start["status"], response_headers, body_bytes)

        return asyncio.run(_request())


class FakeResponse:
    def __init__(self, content):
        self.choices = [type("Choice", (), {"message": type("Message", (), {"content": content})()})()]


class FakeLLMClient:
    def __init__(self, error=None):
        self.error = error
        self.calls = []
        self.chat = type("Chat", (), {})()
        self.chat.completions = type("Completions", (), {})()
        self.chat.completions.create = self.create

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if self.error:
            raise self.error
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
class GroundedQARateLimitApiTest(unittest.TestCase):
    def setUp(self):
        self.client = _ASGIClient(webapp_main.app)
        webapp_main._GROUNDED_QA_USAGE_GUARD = None
        self.env = patch.dict(
            os.environ,
            {
                "DEEPSEEK_API_KEY": "",
                "DEEPSEEK_MODEL": "deepseek-v4-flash",
                "GROUNDED_QA_LLM_ENABLED": "false",
                "GROUNDED_QA_LLM_PER_CLIENT_LIMIT": "5",
                "GROUNDED_QA_LLM_GLOBAL_LIMIT": "30",
                "GROUNDED_QA_LLM_WINDOW_SECONDS": "600",
                "GROUNDED_QA_LLM_MAX_CONCURRENCY": "2",
            },
            clear=False,
        )
        self.env.start()

    def tearDown(self):
        self.env.stop()
        webapp_main._GROUNDED_QA_USAGE_GUARD = None

    def post(self, question="B015是什么？", mode="auto", expected_status=200, client=("testclient", 50000)):
        response = self.client.post(
            "/api/evidence/grounded-qa",
            {"question": question, "generation_mode": mode},
            client=client,
        )
        self.assertEqual(response.status_code, expected_status, response.text)
        return response

    def test_01_default_switch_is_closed(self):
        payload = self.client.get("/api/evidence/grounded-qa/capabilities").json()
        self.assertTrue(payload["local_mode_available"])
        self.assertFalse(payload["llm_enabled"])
        self.assertFalse(payload["llm_mode_available"])
        self.assertIn("本地循证摘要仍可使用", payload["description"])

    def test_02_switch_closed_with_key_does_not_create_client(self):
        fake_client = FakeLLMClient()
        with patch.dict(os.environ, {"DEEPSEEK_API_KEY": "test-secret", "GROUNDED_QA_LLM_ENABLED": "false"}, clear=False):
            with patch.object(grounded_qa_llm, "create_grounded_llm_client", side_effect=RuntimeError("should not create")):
                payload = self.post().json()
        self.assertEqual(fake_client.calls, [])
        self.assertEqual(payload["metadata"]["generation_mode_used"], "local")
        self.assertFalse(payload["metadata"]["llm_used"])
        self.assertIn("DeepSeek智能生成当前未启用", "\n".join(payload["result"]["limitations"]))

    def test_03_capabilities_require_switch_and_key(self):
        with patch.dict(os.environ, {"DEEPSEEK_API_KEY": "test-secret", "GROUNDED_QA_LLM_ENABLED": "false"}, clear=False):
            self.assertFalse(self.client.get("/api/evidence/grounded-qa/capabilities").json()["llm_mode_available"])
        with patch.dict(os.environ, {"DEEPSEEK_API_KEY": "", "GROUNDED_QA_LLM_ENABLED": "true"}, clear=False):
            self.assertFalse(self.client.get("/api/evidence/grounded-qa/capabilities").json()["llm_mode_available"])
        with patch.dict(os.environ, {"DEEPSEEK_API_KEY": "test-secret", "GROUNDED_QA_LLM_ENABLED": "true"}, clear=False):
            payload = self.client.get("/api/evidence/grounded-qa/capabilities").json()
        self.assertTrue(payload["llm_mode_available"])
        self.assertTrue(payload["llm_rate_limit_enabled"])
        self.assertEqual(payload["per_client_limit"], 5)
        self.assertEqual(payload["window_seconds"], 600)
        self.assertNotIn("test-secret", json.dumps(payload, ensure_ascii=False))

    def test_04_local_and_safety_and_no_evidence_do_not_count(self):
        fake_client = FakeLLMClient()
        with patch.dict(
            os.environ,
            {
                "DEEPSEEK_API_KEY": "test-secret",
                "GROUNDED_QA_LLM_ENABLED": "true",
                "GROUNDED_QA_LLM_PER_CLIENT_LIMIT": "1",
            },
            clear=False,
        ), patch.object(grounded_qa_llm, "create_grounded_llm_client", return_value=fake_client):
            self.post("B015是什么？", "local")
            self.post("患者应该用什么药？", "auto")
            self.post("一个不存在的试验当前是什么状态？", "auto")
            first = self.post("B015是什么？", "auto").json()
            second = self.post("B015是什么？", "auto", expected_status=429)
        self.assertEqual(len(fake_client.calls), 1)
        self.assertTrue(first["metadata"]["llm_used"])
        self.assertEqual(second.headers["retry-after"], "600")
        self.assertIn("本地循证摘要仍可使用", second.text)

    def test_05_global_limit_returns_429(self):
        fake_client = FakeLLMClient()
        with patch.dict(
            os.environ,
            {
                "DEEPSEEK_API_KEY": "test-secret",
                "GROUNDED_QA_LLM_ENABLED": "true",
                "GROUNDED_QA_LLM_PER_CLIENT_LIMIT": "5",
                "GROUNDED_QA_LLM_GLOBAL_LIMIT": "1",
            },
            clear=False,
        ), patch.object(grounded_qa_llm, "create_grounded_llm_client", return_value=fake_client):
            self.post("B015是什么？", "auto", client=("client-a", 50000))
            blocked = self.post("B015是什么？", "auto", expected_status=429, client=("client-b", 50001))
        self.assertIn("总量上限", blocked.json()["detail"])
        self.assertRegex(blocked.headers["retry-after"], r"^[1-9][0-9]*$")

    def test_06_concurrency_limit_returns_429(self):
        with patch.dict(
            os.environ,
            {
                "DEEPSEEK_API_KEY": "test-secret",
                "GROUNDED_QA_LLM_ENABLED": "true",
                "GROUNDED_QA_LLM_MAX_CONCURRENCY": "1",
            },
            clear=False,
        ):
            guard = webapp_main._grounded_qa_usage_guard()
            held = guard.acquire("anonymous")
            try:
                blocked = self.post("B015是什么？", "auto", expected_status=429)
            finally:
                guard.release(held)
        self.assertIn("并发请求较多", blocked.json()["detail"])
        self.assertEqual(blocked.headers["retry-after"], "1")

    def test_07_window_end_restores_api_limit(self):
        fake_client = FakeLLMClient()
        with patch.dict(
            os.environ,
            {
                "DEEPSEEK_API_KEY": "test-secret",
                "GROUNDED_QA_LLM_ENABLED": "true",
                "GROUNDED_QA_LLM_PER_CLIENT_LIMIT": "1",
                "GROUNDED_QA_LLM_WINDOW_SECONDS": "60",
            },
            clear=False,
        ), patch.object(grounded_qa_llm, "create_grounded_llm_client", return_value=fake_client):
            self.post("B015是什么？", "auto")
            self.post("B015是什么？", "auto", expected_status=429)
            guard = webapp_main._grounded_qa_usage_guard()
            window_start = next(iter(guard._client_windows.values()))[0]
            guard._clock = lambda: window_start + 61
            restored = self.post("B015是什么？", "auto")
        self.assertEqual(restored.status_code, 200)
        self.assertEqual(len(fake_client.calls), 2)

    def test_08_deepseek_exception_falls_back_and_releases_permit(self):
        fake_client = FakeLLMClient(error=RuntimeError("/srv/app/secret.py DEEPSEEK_API_KEY traceback"))
        with patch.dict(os.environ, {"DEEPSEEK_API_KEY": "test-secret", "GROUNDED_QA_LLM_ENABLED": "true"}, clear=False):
            with patch.object(grounded_qa_llm, "create_grounded_llm_client", return_value=fake_client):
                response = self.post("B015是什么？", "auto")
                guard = webapp_main._grounded_qa_usage_guard()
        payload = response.json()
        self.assertEqual(payload["metadata"]["generation_mode_used"], "local")
        self.assertTrue(payload["metadata"]["fallback_used"])
        self.assertEqual(guard.snapshot()["in_flight"], 0)
        text = response.text
        for leaked in ["/srv/app", "DEEPSEEK_API_KEY", "traceback", "test-secret", "client"]:
            self.assertNotIn(leaked, text)

    def test_09_local_stays_available_when_llm_rate_limited(self):
        fake_client = FakeLLMClient()
        with patch.dict(
            os.environ,
            {
                "DEEPSEEK_API_KEY": "test-secret",
                "GROUNDED_QA_LLM_ENABLED": "true",
                "GROUNDED_QA_LLM_PER_CLIENT_LIMIT": "1",
            },
            clear=False,
        ), patch.object(grounded_qa_llm, "create_grounded_llm_client", return_value=fake_client):
            self.post("B015是什么？", "auto")
            self.post("B015是什么？", "auto", expected_status=429)
            local = self.post("B015是什么？", "local")
        self.assertEqual(local.status_code, 200)
        self.assertFalse(local.json()["metadata"]["llm_used"])

    def test_10_rate_limit_response_does_not_expose_internals(self):
        fake_client = FakeLLMClient()
        with patch.dict(
            os.environ,
            {
                "DEEPSEEK_API_KEY": "test-secret",
                "GROUNDED_QA_LLM_ENABLED": "true",
                "GROUNDED_QA_LLM_PER_CLIENT_LIMIT": "1",
            },
            clear=False,
        ), patch.object(grounded_qa_llm, "create_grounded_llm_client", return_value=fake_client):
            self.post("B015是什么？", "auto", client=("203.0.113.5", 50000))
            blocked = self.post("B015是什么？", "auto", expected_status=429, client=("203.0.113.5", 50001))
        text = blocked.text
        for leaked in ["203.0.113.5", "test-secret", "DEEPSEEK_API_KEY", "/home/", "traceback", "_client_windows"]:
            self.assertNotIn(leaked, text)


if __name__ == "__main__":
    unittest.main()
