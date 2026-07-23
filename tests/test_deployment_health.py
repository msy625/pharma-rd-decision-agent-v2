import asyncio
import json
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.parse import quote, unquote, urlsplit

import anyio.to_thread


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


from deepinsight.core.source_registry_service import SourceRegistryService
from webapp import main as webapp_main


class _ASGIResponse:
    def __init__(self, status_code: int, body: bytes, headers=None):
        self.status_code = status_code
        self.content = body
        self.text = body.decode("utf-8")
        self.headers = headers or {}

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
            headers = {key.decode("latin-1").lower(): value.decode("latin-1") for key, value in start.get("headers", [])}
            return _ASGIResponse(start["status"], body_bytes, headers=headers)

        return asyncio.run(_request())


class DeploymentHealthTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = _ASGIClient(webapp_main.app)

    def test_01_health_returns_fixed_safe_structure(self):
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(
            response.json(),
            {"status": "ok", "service": "pharma-rd-decision-agent"},
        )

    def test_02_ready_returns_core_data_status(self):
        response = self.client.get("/ready")
        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertEqual(payload["status"], "ready")
        self.assertEqual(payload["service"], "pharma-rd-decision-agent")
        self.assertEqual(payload["source_count"], 31)
        self.assertTrue(payload["local_grounded_qa_available"])
        self.assertRegex(payload["data_version"], r"^sha256:[0-9a-f]{16}$")

    def test_03_ready_missing_required_file_returns_friendly_503(self):
        original_factory = webapp_main._evidence_service
        with tempfile.TemporaryDirectory() as tmpdir:
            missing_csv = Path(tmpdir) / "missing_source_registry.csv"
            try:
                webapp_main._evidence_service = lambda: SourceRegistryService(csv_path=missing_csv)
                response = self.client.get("/ready")
            finally:
                webapp_main._evidence_service = original_factory
        self.assertEqual(response.status_code, 503, response.text)
        text = response.text
        self.assertIn("比赛核心数据或规则文件不可用", text)
        home_marker = "/" + "home" + "/"
        for leaked in [str(ROOT), home_marker, "traceback", "DEEPSEEK_API_KEY"]:
            self.assertNotIn(leaked, text)

    def test_04_health_does_not_access_data_services(self):
        with patch.object(webapp_main, "_evidence_service", side_effect=AssertionError("should not read data")):
            response = self.client.get("/health")
        self.assertEqual(response.status_code, 200, response.text)

    def test_05_health_and_ready_do_not_create_deepseek_client(self):
        with patch("deepinsight.core.grounded_qa_llm.create_grounded_llm_client", side_effect=AssertionError("should not create client")):
            self.assertEqual(self.client.get("/health").status_code, 200)
            self.assertEqual(self.client.get("/ready").status_code, 200)

    def test_06_health_and_ready_do_not_load_vector_or_model_modules(self):
        blocked = {"chromadb", "sentence_transformers", "torch"}
        before = {name for name in blocked if name in sys.modules}
        self.assertEqual(self.client.get("/health").status_code, 200)
        self.assertEqual(self.client.get("/ready").status_code, 200)
        after = {name for name in blocked if name in sys.modules}
        self.assertEqual(after - before, set())

    def test_07_import_and_core_api_survive_missing_old_heavy_dependencies(self):
        code = r'''
import asyncio
import builtins
import json
import sys
from urllib.parse import quote, unquote, urlsplit

import anyio.to_thread

blocked = {"streamlit", "pandas", "chromadb", "sentence_transformers", "torch"}
real_import = builtins.__import__

def guarded_import(name, globals=None, locals=None, fromlist=(), level=0):
    if name.split(".", 1)[0] in blocked:
        raise ImportError("blocked old dependency: " + name)
    return real_import(name, globals, locals, fromlist, level)

builtins.__import__ = guarded_import
from webapp import main as webapp_main

async def request(method, path, body=None):
    parsed = urlsplit(path)
    messages = []
    sent = False
    raw_body = b"" if body is None else json.dumps(body).encode("utf-8")
    headers = [(b"host", b"testserver"), (b"accept", b"application/json")]
    if method == "POST":
        headers.extend([(b"content-type", b"application/json"), (b"content-length", str(len(raw_body)).encode("ascii"))])
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
        nonlocal sent
        if not sent:
            sent = True
            return {"type": "http.request", "body": raw_body, "more_body": False}
        await asyncio.sleep(0)
        return {"type": "http.disconnect"}
    async def send(message):
        messages.append(message)
    original_run_sync = anyio.to_thread.run_sync
    async def inline_run_sync(func, *args, abandon_on_cancel=False, cancellable=None, limiter=None):
        return func(*args)
    anyio.to_thread.run_sync = inline_run_sync
    try:
        await webapp_main.app(scope, receive, send)
    finally:
        anyio.to_thread.run_sync = original_run_sync
    start = next(message for message in messages if message["type"] == "http.response.start")
    text = b"".join(message.get("body", b"") for message in messages if message["type"] == "http.response.body").decode("utf-8")
    return start["status"], text

async def main():
    health_status, health_text = await request("GET", "/health")
    ready_status, ready_text = await request("GET", "/ready")
    evidence_status, evidence_text = await request("GET", "/api/evidence/summary")
    qa_status, qa_text = await request("POST", "/api/evidence/grounded-qa", {"question": "B015是什么？", "generation_mode": "local"})
    legacy_status, legacy_text = await request("POST", "/api/workflow", {"topic": "生成报告"})
    out = {
        "health": [health_status, json.loads(health_text)],
        "ready": [ready_status, json.loads(ready_text)],
        "evidence": [evidence_status, json.loads(evidence_text)["total_sources"]],
        "qa": [qa_status, json.loads(qa_text)["metadata"]["generation_mode_used"]],
        "legacy": [legacy_status, legacy_text],
        "loaded": sorted(name for name in blocked if name in sys.modules),
    }
    print(json.dumps(out, ensure_ascii=False))

asyncio.run(main())
'''
        result = subprocess.run(
            [sys.executable, "-c", code],
            cwd=ROOT,
            check=True,
            text=True,
            capture_output=True,
        )
        payload = json.loads(result.stdout)
        self.assertEqual(payload["health"], [200, {"status": "ok", "service": "pharma-rd-decision-agent"}])
        self.assertEqual(payload["ready"][0], 200)
        self.assertEqual(payload["ready"][1]["source_count"], 31)
        self.assertEqual(payload["evidence"], [200, 31])
        self.assertEqual(payload["qa"], [200, "local"])
        self.assertEqual(payload["legacy"][0], 503)
        home_marker = "/" + "home" + "/"
        for leaked in [str(ROOT), home_marker, "traceback", "DEEPSEEK_API_KEY"]:
            self.assertNotIn(leaked, payload["legacy"][1])
        self.assertEqual(payload["loaded"], [])

    def test_08_old_sqlite_backed_endpoint_returns_friendly_503_when_db_unavailable(self):
        with patch.object(webapp_main, "_get_connection", side_effect=sqlite3.OperationalError("no such table: dim_company")):
            response = self.client.get("/api/bootstrap")
        self.assertEqual(response.status_code, 503, response.text)
        text = response.text
        self.assertIn("旧网站功能当前不可用", text)
        home_marker = "/" + "home" + "/"
        for leaked in [str(ROOT), home_marker, "traceback", "no such table", "DEEPSEEK_API_KEY"]:
            self.assertNotIn(leaked, text)


if __name__ == "__main__":
    unittest.main()
