"""Regression tests for the completed normalized-data migration.

``include_harvested`` is retained for old URLs, but no longer gates data: the
eligible normalized template is the default website scope.
"""

import unittest
import json
from pathlib import Path

from deepinsight.core.source_registry_service import NormalizedSourceRegistryService
from tests.test_deployment_health import _ASGIClient
from webapp import main as webapp_main


ROOT = Path(__file__).resolve().parents[1]
WEBSITE_TOTAL = json.loads((ROOT / "data" / "template" / "data_manifest.json").read_text(encoding="utf-8"))["counts"]["sources"]


class NormalizedWebsiteScopeTest(unittest.TestCase):
    def test_projection_excludes_detached_sources(self):
        service = NormalizedSourceRegistryService()
        rows = service.load_rows()
        self.assertEqual(len(rows), WEBSITE_TOTAL)
        self.assertTrue(all(row["url"].startswith("http") for row in rows))
        source_ids = {row["source_id"] for row in rows}
        self.assertNotIn("SRC_MET_SURMOUNT1_REG", source_ids)
        self.assertNotIn("H008", source_ids)

    def test_machine_harvested_rows_are_in_the_default_scope(self):
        rows = NormalizedSourceRegistryService().load_rows()
        self.assertGreater(sum(row["verification_status"] == "api_harvested" for row in rows), 1000)


class NormalizedWebsiteScopeApiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = _ASGIClient(webapp_main.app)

    def get_json(self, path: str):
        response = self.client.get(path)
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def test_default_summary_uses_normalized_template(self):
        payload = self.get_json("/api/evidence/summary")
        self.assertEqual(payload["total_sources"], WEBSITE_TOTAL)
        self.assertTrue(payload["include_harvested"])
        self.assertEqual(payload["metadata"]["data_backend"], "normalized_template")
        self.assertEqual(payload["metadata"]["data_source"], "data/template/*.csv")

    def test_legacy_parameter_cannot_hide_default_normalized_rows(self):
        default = self.get_json("/api/evidence/search?q=Pembrolizumab")
        legacy_parameter = self.get_json("/api/evidence/search?q=Pembrolizumab&include_harvested=false")
        self.assertEqual(default["count"], legacy_parameter["count"])
        self.assertTrue(any(item["verification_status"] == "api_harvested" for item in default["items"]))

    def test_workbench_profile_and_timeline_report_normalized_backend(self):
        for path in [
            "/api/evidence/workbench",
            "/api/evidence/company-profile/%E6%81%92%E7%91%9E%E5%8C%BB%E8%8D%AF",
            "/api/evidence/timeline",
        ]:
            with self.subTest(path=path):
                payload = self.get_json(path)
                self.assertEqual(payload["metadata"]["data_backend"], "normalized_template")


if __name__ == "__main__":
    unittest.main()
