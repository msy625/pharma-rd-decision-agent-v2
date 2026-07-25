import asyncio
import json
import sys
import unittest
from pathlib import Path
from urllib.parse import quote, unquote, urlsplit

import anyio.to_thread


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


WEBAPP_IMPORT_ERROR = None
webapp_main = None
try:
    from webapp import main as webapp_main
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


@unittest.skipIf(webapp_main is None, f"webapp.main import unavailable: {WEBAPP_IMPORT_ERROR!r}")
class RDDecisionAgentApiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = _ASGIClient(webapp_main.app)

    def post_agent(self, question, generation_mode="local", expected_status=200):
        response = self.client.post(
            "/api/evidence/decision-agent",
            {"question": question, "generation_mode": generation_mode},
        )
        self.assertEqual(response.status_code, expected_status, response.text)
        return response.json()

    def test_capabilities_endpoint(self):
        response = self.client.get("/api/evidence/decision-agent/capabilities")
        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertTrue(payload["local_mode_available"])
        self.assertIn("company_comparison", payload["supported_intents"])
        self.assertIn("tool_mapping", payload)
        self.assertTrue(payload["data_version"].startswith("sha256:"))

    def test_post_company_comparison_protocol(self):
        payload = self.post_agent("阿斯利康与百济神州当前 NSCLC 证据样本有什么差异？")
        self.assertEqual(payload["intent"], "company_comparison")
        for key in [
            "question",
            "entities",
            "plan",
            "steps",
            "decision",
            "answer",
            "citations",
            "featured_citations",
            "source_ids",
            "source_trace",
            "chain_ids",
            "warnings",
            "execution_metadata",
        ]:
            self.assertIn(key, payload)
        self.assertTrue(payload["steps"])
        self.assertTrue(payload["decision"]["comparison_dimensions"])
        self.assertEqual({f"A{i:03d}" for i in range(1, 9)} | {f"B{i:03d}" for i in range(1, 17)}, set(payload["source_ids"]))
        self.assertTrue(all(item["source_id"] and item["produced_by_steps"] for item in payload["citations"]))
        self.assertEqual([item["source_id"] for item in payload["featured_citations"]], ["A001", "B003", "A002", "B006", "B001", "B015"])
        self.assertEqual(payload["execution_metadata"]["untraced_source_ids"], [])

    def test_empty_question_and_invalid_mode_return_400(self):
        self.post_agent("   ", expected_status=400)
        self.post_agent("B016是什么？", generation_mode="remote", expected_status=400)

    def test_safety_api_refuses_without_business_tools(self):
        payload = self.post_agent("请根据这些资料为患者推荐具体药物。")
        self.assertTrue(payload["refused"])
        self.assertEqual(payload["source_ids"], [])
        self.assertEqual([step["tool"] for step in payload["steps"]], ["GroundedQAService.check_safety"])

    def test_decision_agent_does_not_break_grounded_qa(self):
        agent_payload = self.post_agent("RATIONALE-315 当前还存在哪些证据缺口？")
        self.assertEqual(agent_payload["intent"], "evidence_gap")
        grounded_response = self.client.post(
            "/api/evidence/grounded-qa",
            {"question": "RATIONALE-315当前还存在哪些证据缺口？", "generation_mode": "local"},
        )
        self.assertEqual(grounded_response.status_code, 200, grounded_response.text)
        grounded_payload = grounded_response.json()
        self.assertEqual(grounded_payload["result"]["question_type"], "evidence_gap")
        self.assertEqual(grounded_payload["result"]["trace"]["retrieved_source_ids"], ["B011", "B012", "B013", "B016"])


if __name__ == "__main__":
    unittest.main()
