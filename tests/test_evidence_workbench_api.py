import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


from deepinsight.core.evidence_workbench_service import EvidenceWorkbenchService
from deepinsight.core.source_registry_service import SourceRegistryService
from tests.test_deployment_health import _ASGIClient
from webapp import main as webapp_main


class EvidenceWorkbenchApiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = _ASGIClient(webapp_main.app)

    def test_01_workbench_returns_200_and_unified_structure(self):
        response = self.client.get("/api/evidence/workbench")
        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertEqual(payload["metadata"]["data_scope"], "first_version_nsclc_hengrui_beone")
        self.assertIn("workbench", payload)
        workbench = payload["workbench"]
        self.assertEqual(workbench["summary"]["source_count"], 31)
        self.assertIn("companies", workbench)
        self.assertIn("source_type_distribution", workbench)
        self.assertIn("study_status_distribution", workbench)
        self.assertIn("evidence_gaps", workbench)

    def test_02_missing_source_file_returns_friendly_503(self):
        bad_service = EvidenceWorkbenchService(
            source_registry_service=SourceRegistryService(csv_path=ROOT / "data" / "missing-source-registry.csv")
        )
        with patch.object(webapp_main, "_evidence_workbench_service", return_value=bad_service):
            response = self.client.get("/api/evidence/workbench")
        self.assertEqual(response.status_code, 503, response.text)
        text = response.text
        self.assertIn("证据资料文件不可用", text)
        self.assertNotIn(str(ROOT), text)
        self.assertNotIn("Traceback", text)

    def test_03_response_does_not_leak_paths_or_secrets(self):
        response = self.client.get("/api/evidence/workbench")
        self.assertEqual(response.status_code, 200, response.text)
        text = response.text
        for forbidden in [str(ROOT), "/" + "home" + "/", "DEEPSEEK_API_KEY", "sk-", "Traceback"]:
            self.assertNotIn(forbidden, text)
        json.loads(text)

    def test_04_request_does_not_load_deepseek_chroma_or_torch(self):
        blocked = {"openai", "chromadb", "sentence_transformers", "torch"}
        before = {name for name in blocked if name in sys.modules}
        response = self.client.get("/api/evidence/workbench")
        self.assertEqual(response.status_code, 200, response.text)
        after = {name for name in blocked if name in sys.modules}
        self.assertEqual(after - before, set())

    def test_05_runtime_capabilities_include_workbench_and_default_today(self):
        with patch.object(webapp_main, "_legacy_features_available", return_value=False):
            response = self.client.get("/api/runtime-capabilities")
        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertTrue(payload["competition_core_available"])
        self.assertTrue(payload["evidence_workbench_available"])
        self.assertFalse(payload["legacy_features_available"])
        self.assertEqual(payload["default_page"], "today")


if __name__ == "__main__":
    unittest.main()
