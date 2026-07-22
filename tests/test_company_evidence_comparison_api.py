import asyncio
import inspect
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
except Exception as exc:  # pragma: no cover - exercised only when optional deps are absent
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
        async def _request():
            parsed = urlsplit(path)
            messages = []
            request_sent = False

            scope = {
                "type": "http",
                "asgi": {"version": "3.0", "spec_version": "2.3"},
                "http_version": "1.1",
                "method": "GET",
                "scheme": "http",
                "path": unquote(parsed.path),
                "raw_path": quote(parsed.path, safe="/%").encode("ascii"),
                "query_string": quote(parsed.query, safe="=&%").encode("ascii"),
                "headers": [(b"host", b"testserver"), (b"accept", b"application/json")],
                "client": ("testclient", 50000),
                "server": ("testserver", 80),
                "root_path": "",
            }

            async def receive():
                nonlocal request_sent
                if not request_sent:
                    request_sent = True
                    return {"type": "http.request", "body": b"", "more_body": False}
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
            body = b"".join(message.get("body", b"") for message in messages if message["type"] == "http.response.body")
            return _ASGIResponse(start["status"], body)

        return asyncio.run(_request())


def _profile(payload, company_name):
    return next(item for item in payload["comparison"]["companies"] if item["company_name"] == company_name)


def _assert_no_prohibited_keys(testcase, value):
    prohibited = {"score", "ranking", "winner", "success_probability"}
    if isinstance(value, dict):
        for key, item in value.items():
            testcase.assertNotIn(key, prohibited)
            _assert_no_prohibited_keys(testcase, item)
    elif isinstance(value, list):
        for item in value:
            _assert_no_prohibited_keys(testcase, item)


@unittest.skipIf(webapp_main is None, f"webapp.main import unavailable: {WEBAPP_IMPORT_ERROR!r}")
class CompanyEvidenceComparisonApiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = _ASGIClient(webapp_main.app)

    def get_json(self, path: str, expected_status: int = 200):
        response = self.client.get(path)
        self.assertEqual(response.status_code, expected_status, response.text)
        return response.json()

    def test_01_default_comparison_returns_expected_source_counts(self):
        payload = self.get_json("/api/evidence/company-comparison")
        self.assertEqual(_profile(payload, "恒瑞医药")["source_count"], 15)
        self.assertEqual(_profile(payload, "百济神州")["source_count"], 16)

    def test_02_both_companies_all_sources_are_verified(self):
        payload = self.get_json("/api/evidence/company-comparison")
        hengrui = _profile(payload, "恒瑞医药")
        beone = _profile(payload, "百济神州")
        self.assertEqual(hengrui["verified_source_count"], hengrui["source_count"])
        self.assertEqual(beone["verified_source_count"], beone["source_count"])

    def test_03_trial_and_regulatory_chain_counts(self):
        payload = self.get_json("/api/evidence/company-comparison")
        self.assertEqual(_profile(payload, "恒瑞医药")["trial_chain_count"], 6)
        self.assertEqual(_profile(payload, "百济神州")["trial_chain_count"], 4)
        self.assertEqual(_profile(payload, "百济神州")["regulatory_chain_count"], 1)

    def test_04_single_and_multi_source_trial_chain_counts(self):
        payload = self.get_json("/api/evidence/company-comparison")
        self.assertEqual(_profile(payload, "恒瑞医药")["single_source_trial_chain_count"], 6)
        self.assertEqual(_profile(payload, "百济神州")["multi_source_trial_chain_count"], 4)

    def test_05_unresolved_link_counts(self):
        payload = self.get_json("/api/evidence/company-comparison")
        self.assertEqual(_profile(payload, "恒瑞医药")["unresolved_link_count"], 6)
        self.assertEqual(_profile(payload, "百济神州")["unresolved_link_count"], 1)

    def test_06_version_distribution(self):
        payload = self.get_json("/api/evidence/company-comparison")
        self.assertEqual(_profile(payload, "恒瑞医药")["version_distribution"], {"latest": 0, "historical": 0, "independent": 15})
        self.assertEqual(_profile(payload, "百济神州")["version_distribution"], {"latest": 4, "historical": 2, "independent": 10})

    def test_07_company_aliases_are_normalized(self):
        payload = self.get_json("/api/evidence/company-comparison?company_a=恒瑞医药&company_b=BeiGene")
        beone = _profile(payload, "百济神州")
        self.assertEqual(beone["display_name"], "百济神州/BeOne Medicines")
        self.assertEqual(beone["source_count"], 16)

    def test_08_same_normalized_company_returns_400(self):
        response = self.client.get("/api/evidence/company-comparison?company_a=百济神州&company_b=BeiGene")
        self.assertEqual(response.status_code, 400, response.text)

    def test_09_empty_company_parameter_returns_400(self):
        response = self.client.get("/api/evidence/company-comparison?company_a=&company_b=BeOne%20Medicines")
        self.assertEqual(response.status_code, 400, response.text)

    def test_10_missing_company_returns_empty_profile_not_500(self):
        payload = self.get_json("/api/evidence/company-comparison?company_a=不存在的企业&company_b=恒瑞医药")
        missing = _profile(payload, "不存在的企业")
        self.assertEqual(missing["source_count"], 0)
        self.assertIn("当前数据不足", missing["evidence_gaps"][0])

    def test_11_payload_does_not_include_prohibited_claim_keys(self):
        payload = self.get_json("/api/evidence/company-comparison")
        _assert_no_prohibited_keys(self, payload)

    def test_12_scope_warning_mentions_current_sample(self):
        payload = self.get_json("/api/evidence/company-comparison")
        notes = payload["comparison"]["comparison_notes"]
        self.assertTrue(any("当前收录" in note and "不代表企业整体研发实力" in note for note in notes))

    def test_13_metric_rules_endpoint_returns_interpretation_rules(self):
        payload = self.get_json("/api/evidence/company-comparison/metric-rules")
        self.assertGreater(payload["count"], 0)
        for item in payload["items"]:
            self.assertIn("correct_interpretation", item)
            self.assertIn("prohibited_interpretation", item)

    def test_14_metadata_uses_current_verified_sample_scope(self):
        payload = self.get_json("/api/evidence/company-comparison")
        self.assertEqual(payload["metadata"]["data_scope"], "first_version_nsclc_hengrui_beone")
        self.assertEqual(payload["metadata"]["interpretation_scope"], "current_verified_sample_only")

    def test_15_api_route_does_not_hardcode_current_counts(self):
        source = inspect.getsource(webapp_main.evidence_company_comparison)
        for forbidden in [
            '"source_count": 15',
            '"source_count": 16',
            '"trial_chain_count": 6',
            '"trial_chain_count": 4',
        ]:
            self.assertNotIn(forbidden, source)

    def test_16_request_does_not_load_models_or_vector_modules(self):
        blocked = {"chromadb", "sentence_transformers", "openai"}
        before = {name for name in blocked if name in sys.modules}
        self.get_json("/api/evidence/company-comparison")
        after = {name for name in blocked if name in sys.modules}
        self.assertEqual(after - before, set())

    def test_17_existing_evidence_api_still_works(self):
        payload = self.get_json("/api/evidence/summary")
        self.assertEqual(payload["total_sources"], 31)

    def test_18_existing_evidence_chain_api_still_works(self):
        payload = self.get_json("/api/evidence/chain-summary")
        self.assertEqual(payload["total_chain_count"], 11)


if __name__ == "__main__":
    unittest.main()
