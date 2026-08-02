import json
from copy import deepcopy
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


from tests.test_deployment_health import _ASGIClient
from webapp import main as webapp_main


class RuntimeCapabilitiesTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = _ASGIClient(webapp_main.app)

    def test_01_light_runtime_defaults_to_real_workbench(self):
        with patch.object(webapp_main, "_legacy_features_available", return_value=False):
            response = self.client.get("/api/runtime-capabilities")
        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertTrue(payload["competition_core_available"])
        self.assertTrue(payload["evidence_workbench_available"])
        self.assertFalse(payload["legacy_features_available"])
        self.assertEqual(payload["default_page"], "today")
        self.assertIn("旧企业分析数据或可选依赖未配置", payload["legacy_unavailable_reason"])

    def test_02_full_legacy_runtime_can_keep_old_dashboard_default(self):
        with patch.object(webapp_main, "_legacy_features_available", return_value=True):
            response = self.client.get("/api/runtime-capabilities")
        payload = response.json()
        self.assertEqual(response.status_code, 200, response.text)
        self.assertTrue(payload["competition_core_available"])
        self.assertTrue(payload["evidence_workbench_available"])
        self.assertTrue(payload["legacy_features_available"])
        self.assertEqual(payload["default_page"], "today")
        self.assertEqual(payload["legacy_unavailable_reason"], "")

    def test_03_capability_endpoint_does_not_load_heavy_legacy_modules(self):
        blocked = {"streamlit", "pandas", "chromadb", "sentence_transformers", "torch"}
        before = {name for name in blocked if name in sys.modules}
        with patch.object(webapp_main, "_module_available", return_value=False):
            response = self.client.get("/api/runtime-capabilities")
        self.assertEqual(response.status_code, 200, response.text)
        after = {name for name in blocked if name in sys.modules}
        self.assertEqual(after - before, set())

    def test_04_capability_endpoint_does_not_create_deepseek_client(self):
        with patch.object(webapp_main, "_create_optional_client", side_effect=AssertionError("should not create client")):
            response = self.client.get("/api/runtime-capabilities")
        self.assertEqual(response.status_code, 200, response.text)

    def test_05_capability_response_does_not_leak_paths_or_secrets(self):
        with patch.object(webapp_main, "_legacy_features_available", return_value=False):
            response = self.client.get("/api/runtime-capabilities")
        text = response.text
        home_marker = "/" + "home" + "/"
        for forbidden in [str(ROOT), home_marker, "traceback", "DEEPSEEK_API_KEY", "sk-"]:
            self.assertNotIn(forbidden, text)
        json.loads(text)

    def test_06_initial_state_combines_capabilities_and_default_workbench(self):
        with patch.object(webapp_main, "_legacy_features_available", return_value=False):
            response = self.client.get("/api/initial-state")
        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertEqual(payload["runtime_capabilities"]["default_page"], "today")
        self.assertFalse(payload["runtime_capabilities"]["legacy_features_available"])
        self.assertEqual(payload["evidence_workbench"]["workbench"]["summary"]["source_count"], 39)
        self.assertEqual(
            payload["evidence_workbench"]["metadata"]["data_scope"],
            "verified_nsclc_multi_company_sample",
        )

    def test_07_initial_state_keeps_existing_endpoints_unchanged(self):
        initial = self.client.get("/api/initial-state").json()
        capabilities = self.client.get("/api/runtime-capabilities").json()
        workbench = self.client.get("/api/evidence/workbench").json()
        self.assertEqual(initial["runtime_capabilities"], capabilities)
        initial_workbench = deepcopy(initial["evidence_workbench"])
        standalone_workbench = deepcopy(workbench)
        initial_workbench["workbench"]["metadata"].pop("generated_at", None)
        standalone_workbench["workbench"]["metadata"].pop("generated_at", None)
        self.assertEqual(initial_workbench, standalone_workbench)


if __name__ == "__main__":
    unittest.main()
