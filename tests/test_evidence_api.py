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


def _build_client(app):
    return _ASGIClient(app), "direct ASGI HTTP"


def _ids(payload):
    return {item["source_id"] for item in payload["items"]}


@unittest.skipIf(webapp_main is None, f"webapp.main import unavailable: {WEBAPP_IMPORT_ERROR!r}")
class EvidenceApiHttpTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client, cls.client_kind = _build_client(webapp_main.app)

    def get_json(self, path: str, expected_status: int = 200):
        response = self.client.get(path)
        self.assertEqual(response.status_code, expected_status, response.text)
        return response.json()

    def test_01_summary_total_is_39(self):
        payload = self.get_json("/api/evidence/summary")
        self.assertEqual(payload["total_sources"], 39)

    def test_02_company_hengrui_returns_15(self):
        payload = self.get_json("/api/evidence/company/恒瑞医药")
        self.assertEqual(payload["count"], 15)

    def test_03_company_beigene_cn_returns_16(self):
        payload = self.get_json("/api/evidence/company/百济神州")
        self.assertEqual(payload["count"], 16)

    def test_04_company_beone_medicines_returns_16(self):
        payload = self.get_json("/api/evidence/company/BeOne%20Medicines")
        self.assertEqual(payload["count"], 16)

    def test_05_drug_shr_1210_returns_camrelizumab_sources(self):
        payload = self.get_json("/api/evidence/drug/SHR-1210")
        self.assertIn("H004", _ids(payload))
        self.assertTrue(any("Camrelizumab" in item.get("drug_name", "") for item in payload["items"]))

    def test_06_trial_nct04379635_returns_three_sources(self):
        payload = self.get_json("/api/evidence/trial/NCT04379635")
        self.assertEqual(_ids(payload), {"B011", "B012", "B013"})
        for item in payload["items"]:
            self.assertEqual(item["parent_trial_id"], "NCT04379635")
        b011 = next(item for item in payload["items"] if item["source_id"] == "B011")
        self.assertNotIn("后续批次补充", b011.get("risk_notes", ""))

    def test_07_trial_nct04619433_is_h006_terminated(self):
        payload = self.get_json("/api/evidence/trial/NCT04619433")
        self.assertEqual(_ids(payload), {"H006"})
        self.assertEqual(payload["items"][0]["study_status"], "Terminated")

    def test_08_study_rationale_304_latest_only(self):
        payload = self.get_json("/api/evidence/study/RATIONALE-304?latest_only=true")
        ids = _ids(payload)
        self.assertIn("B007", ids)
        self.assertNotIn("B006", ids)

    def test_09_source_b015_is_ema_authorised(self):
        payload = self.get_json("/api/evidence/source/B015")
        item = payload["item"]
        self.assertEqual(item["source_id"], "B015")
        self.assertEqual(item["authorisation_status"], "欧盟正式授权")

    def test_10_source_b016_is_not_final_approval(self):
        payload = self.get_json("/api/evidence/source/B016")
        item = payload["item"]
        self.assertEqual(item["source_id"], "B016")
        self.assertEqual(item["regulatory_event_type"], "CHMP positive opinion")
        self.assertNotEqual(item.get("authorisation_status"), "欧盟正式授权")
        self.assertNotIn("最终批准", item.get("description_zh", ""))

    def test_11_missing_source_returns_404(self):
        response = self.client.get("/api/evidence/source/NOT_FOUND")
        self.assertEqual(response.status_code, 404, response.text)

    def test_12_missing_company_does_not_return_500(self):
        response = self.client.get("/api/evidence/company/不存在的企业")
        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertEqual(payload["items"], [])
        self.assertEqual(payload["count"], 0)

    def test_13_empty_search_returns_400_or_422(self):
        response = self.client.get("/api/evidence/search")
        self.assertIn(response.status_code, {400, 422}, response.text)

    def test_14_invalid_limit_returns_400_or_422(self):
        response = self.client.get("/api/evidence/search?q=NSCLC&limit=0")
        self.assertIn(response.status_code, {400, 422}, response.text)

    def test_15_items_include_source_id_and_source_url(self):
        payload = self.get_json("/api/evidence/company/恒瑞医药")
        for item in payload["items"]:
            self.assertTrue(item.get("source_id"))
            self.assertTrue(item.get("source_url"))

    def test_16_evidence_api_does_not_load_model_or_vector_modules(self):
        before = {name for name in ["chromadb", "sentence_transformers"] if name in sys.modules}
        self.get_json("/api/evidence/summary")
        after = {name for name in ["chromadb", "sentence_transformers"] if name in sys.modules}
        self.assertEqual(after - before, set())

    def test_17_existing_safe_api_still_accessible(self):
        response = self.client.get("/api/whitebox")
        self.assertEqual(response.status_code, 200, response.text)
        self.assertIn("answer_markdown", response.json())

    def test_18_laura_trial_query_returns_one_trial_pair(self):
        payload = self.get_json("/api/evidence/trial/NCT03521154")
        self.assertEqual(_ids(payload), {"A005", "A006"})
        self.assertEqual({item["study_name"] for item in payload["items"]}, {"LAURA"})

    def test_19_study_name_exact_match_has_priority(self):
        self.assertEqual(_ids(self.get_json("/api/evidence/study/LAURA")), {"A005", "A006"})
        self.assertEqual(_ids(self.get_json("/api/evidence/study/FLAURA")), {"A001", "A002"})
        self.assertEqual(_ids(self.get_json("/api/evidence/study/FLAURA2")), {"A007", "A008"})

    def test_20_study_name_normalization_and_partial_fallback(self):
        normalized = self.get_json("/api/evidence/study/%20laura%20")
        fallback = self.get_json("/api/evidence/study/LAUR")
        self.assertEqual(_ids(normalized), {"A005", "A006"})
        self.assertEqual(_ids(fallback), {"A001", "A002", "A005", "A006", "A007", "A008"})

    def test_21_keyword_laura_remains_broad(self):
        payload = self.get_json("/api/evidence/search?q=LAURA")
        self.assertEqual(_ids(payload), {"A001", "A002", "A005", "A006", "A007", "A008"})


@unittest.skipIf(webapp_main is None, f"webapp.main import unavailable: {WEBAPP_IMPORT_ERROR!r}")
class EvidenceRouteDirectCallRegressionTest(unittest.TestCase):
    def test_company_route_direct_call_uses_plain_int_default(self):
        signature = inspect.signature(webapp_main.evidence_by_company)
        self.assertIsInstance(signature.parameters["limit"].default, int)
        payload = webapp_main.evidence_by_company("恒瑞医药")
        self.assertEqual(payload["count"], 15)


if __name__ == "__main__":
    unittest.main()
