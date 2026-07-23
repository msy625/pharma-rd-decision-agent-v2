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


def _ids(items):
    return {item["source_id"] for item in items}


def _find(items, source_id):
    return next(item for item in items if item["source_id"] == source_id)


def _assert_no_prohibited_claim_keys(testcase, value):
    prohibited = {"score", "success_rate", "efficacy_ranking", "疗效排名", "成功率"}
    if isinstance(value, dict):
        for key, item in value.items():
            testcase.assertNotIn(key, prohibited)
            _assert_no_prohibited_claim_keys(testcase, item)
    elif isinstance(value, list):
        for item in value:
            _assert_no_prohibited_claim_keys(testcase, item)


@unittest.skipIf(webapp_main is None, f"webapp.main import unavailable: {WEBAPP_IMPORT_ERROR!r}")
class EvidenceChainApiHttpTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = _ASGIClient(webapp_main.app)

    def get_json(self, path: str, expected_status: int = 200):
        response = self.client.get(path)
        self.assertEqual(response.status_code, expected_status, response.text)
        return response.json()

    def test_01_summary_total_chain_count_is_15(self):
        payload = self.get_json("/api/evidence/chain-summary")
        self.assertEqual(payload["total_chain_count"], 15)

    def test_02_summary_trial_chain_count_is_14(self):
        payload = self.get_json("/api/evidence/chain-summary")
        self.assertEqual(payload["trial_chain_count"], 14)

    def test_03_summary_regulatory_chain_count_is_1(self):
        payload = self.get_json("/api/evidence/chain-summary")
        self.assertEqual(payload["regulatory_chain_count"], 1)
        self.assertEqual(payload["nct_registered_trial_count"], 13)

    def test_04_rationale_304_contains_expected_sources(self):
        payload = self.get_json("/api/evidence/chains/trial%3ANCT03663205")
        self.assertEqual(_ids(payload["item"]["evidence_items"]), {"B003", "B006", "B007"})

    def test_05_b006_is_historical_version(self):
        payload = self.get_json("/api/evidence/chains/trial%3ANCT03663205")
        self.assertEqual(_ids(payload["item"]["historical_items"]), {"B006"})

    def test_06_b007_is_latest_version(self):
        payload = self.get_json("/api/evidence/chains/trial%3ANCT03663205")
        self.assertEqual(_ids(payload["item"]["latest_items"]), {"B007"})

    def test_07_nct04379635_contains_only_trial_sources(self):
        payload = self.get_json("/api/evidence/trial-chain/NCT04379635")
        self.assertEqual(_ids(payload["item"]["evidence_items"]), {"B011", "B012", "B013"})

    def test_08_nct04379635_returns_b016_as_related_regulatory_item(self):
        payload = self.get_json("/api/evidence/trial-chain/NCT04379635")
        self.assertEqual(_ids(payload["item"]["related_regulatory_items"]), {"B016"})

    def test_09_b016_does_not_increase_trial_chain_source_count(self):
        payload = self.get_json("/api/evidence/trial-chain/NCT04379635")
        self.assertEqual(payload["item"]["source_count"], 3)
        self.assertNotIn("B016", _ids(payload["item"]["evidence_items"]))

    def test_10_tislelizumab_regulatory_chain_contains_b015_b016(self):
        payload = self.get_json("/api/evidence/drug/tislelizumab/regulatory-chain")
        self.assertEqual(_ids(payload["item"]["evidence_items"]), {"B015", "B016"})

    def test_11_b015_is_formal_authorisation(self):
        payload = self.get_json("/api/evidence/drug/替雷利珠单抗/regulatory-chain")
        b015 = _find(payload["item"]["evidence_items"], "B015")
        self.assertEqual(b015["role"], "regulatory_authorisation")
        self.assertEqual(b015["authorisation_status"], "欧盟正式授权")

    def test_12_b016_is_only_chmp_positive_opinion(self):
        payload = self.get_json("/api/evidence/drug/TEVIMBRA/regulatory-chain")
        b016 = _find(payload["item"]["evidence_items"], "B016")
        self.assertEqual(b016["role"], "regulatory_opinion")
        self.assertEqual(b016["regulatory_event_type"], "CHMP positive opinion")
        self.assertEqual(b016["authorisation_status"], "")

    def test_13_hengrui_company_query_returns_six_trial_chains(self):
        payload = self.get_json("/api/evidence/chains?company=恒瑞医药&chain_type=trial")
        self.assertEqual(payload["count"], 6)
        self.assertEqual({item["chain_type"] for item in payload["items"]}, {"trial"})

    def test_14_invalid_chain_type_returns_400(self):
        response = self.client.get("/api/evidence/chains?chain_type=drug")
        self.assertEqual(response.status_code, 400, response.text)

    def test_15_missing_chain_id_returns_404(self):
        self.client.get("/api/evidence/chains/trial%3ANOT_FOUND")
        response = self.client.get("/api/evidence/chains/trial%3ANOT_FOUND")
        self.assertEqual(response.status_code, 404, response.text)

    def test_16_missing_trial_id_returns_404(self):
        response = self.client.get("/api/evidence/trial-chain/NCT00000000")
        self.assertEqual(response.status_code, 404, response.text)

    def test_17_missing_drug_regulatory_chain_returns_empty_item(self):
        payload = self.get_json("/api/evidence/drug/不存在的药物/regulatory-chain")
        self.assertEqual(payload["item"], {})

    def test_18_unresolved_contains_expected_hengrui_relation_gaps(self):
        payload = self.get_json("/api/evidence/unresolved-links")
        ids = _ids(payload["items"])
        self.assertGreaterEqual(ids, {"H008", "H009", "H010", "H011", "H012", "H014"})
        h014 = _find(payload["items"], "H014")
        self.assertIn("一对一关系", h014["description"])

    def test_19_response_does_not_include_scores_or_rankings(self):
        payload = self.get_json("/api/evidence/chains")
        _assert_no_prohibited_claim_keys(self, payload)

    def test_20_api_request_does_not_load_models_or_vector_modules(self):
        blocked = {"chromadb", "sentence_transformers", "openai"}
        before = {name for name in blocked if name in sys.modules}
        self.get_json("/api/evidence/chain-summary")
        after = {name for name in blocked if name in sys.modules}
        self.assertEqual(after - before, set())

    def test_21_existing_evidence_query_api_still_works(self):
        payload = self.get_json("/api/evidence/summary")
        self.assertEqual(payload["total_sources"], 39)


if __name__ == "__main__":
    unittest.main()
