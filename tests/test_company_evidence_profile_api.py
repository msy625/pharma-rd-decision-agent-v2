import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


from deepinsight.core.source_registry_service import SourceRegistryFileNotFound, SourceRegistryStructureError
from tests.test_deployment_health import _ASGIClient
from webapp import main as webapp_main


class CompanyEvidenceProfileApiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = _ASGIClient(webapp_main.app)

    def test_01_chinese_company_path(self):
        response = self.client.get("/api/evidence/company-profile/%E6%81%92%E7%91%9E%E5%8C%BB%E8%8D%AF")
        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertEqual(payload["profile"]["company"]["canonical_name"], "恒瑞医药")
        self.assertEqual(payload["profile"]["summary"]["source_count"], 15)

    def test_02_beone_space_path(self):
        response = self.client.get("/api/evidence/company-profile/BeOne%20Medicines")
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["profile"]["company"]["canonical_name"], "百济神州")

    def test_03_company_list_has_two_normalized_subjects(self):
        response = self.client.get("/api/evidence/company-profile-companies")
        payload = response.json()
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(payload["count"], 2)
        self.assertEqual([item["canonical_name"] for item in payload["items"]], ["恒瑞医药", "百济神州"])

    def test_04_missing_company_is_friendly_200(self):
        response = self.client.get("/api/evidence/company-profile/%E4%B8%8D%E5%AD%98%E5%9C%A8%E4%BC%81%E4%B8%9A")
        self.assertEqual(response.status_code, 200, response.text)
        profile = response.json()["profile"]
        self.assertEqual(profile["summary"]["source_count"], 0)
        self.assertIn("当前数据不足", profile["limitations"][0])

    def test_05_missing_file_returns_friendly_503(self):
        with patch.object(webapp_main, "_company_evidence_profile_service", side_effect=SourceRegistryFileNotFound("/private/path/source_registry.csv")):
            response = self.client.get("/api/evidence/company-profile/%E6%81%92%E7%91%9E%E5%8C%BB%E8%8D%AF")
        self.assertEqual(response.status_code, 503, response.text)
        self.assertNotIn("/private/path", response.text)
        self.assertIn("证据资料文件不可用", response.text)

    def test_06_structure_error_returns_friendly_503(self):
        with patch.object(webapp_main, "_company_evidence_profile_service", side_effect=SourceRegistryStructureError("bad columns at /private/path")):
            response = self.client.get("/api/evidence/company-profile/%E6%81%92%E7%91%9E%E5%8C%BB%E8%8D%AF")
        self.assertEqual(response.status_code, 503, response.text)
        self.assertNotIn("/private/path", response.text)
        self.assertIn("证据资料结构异常", response.text)

    def test_07_unknown_error_is_sanitized(self):
        with patch.object(webapp_main, "_company_evidence_profile_service", side_effect=RuntimeError("sk-secret /home/user/private")):
            response = self.client.get("/api/evidence/company-profile/%E6%81%92%E7%91%9E%E5%8C%BB%E8%8D%AF")
        self.assertEqual(response.status_code, 500, response.text)
        for forbidden in ["sk-secret", "/home/user", "traceback"]:
            self.assertNotIn(forbidden, response.text.lower())

    def test_08_runtime_capabilities_contains_profile_capability(self):
        with patch.object(webapp_main, "_legacy_features_available", return_value=False):
            response = self.client.get("/api/runtime-capabilities")
        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertTrue(payload["company_evidence_profile_available"])
        self.assertFalse(payload["legacy_features_available"])

    def test_09_profile_request_does_not_create_deepseek_client(self):
        with patch.object(webapp_main, "_create_optional_client", side_effect=AssertionError("must not create client")):
            response = self.client.get("/api/evidence/company-profile/%E6%81%92%E7%91%9E%E5%8C%BB%E8%8D%AF")
        self.assertEqual(response.status_code, 200, response.text)

    def test_10_profile_request_does_not_load_heavy_modules(self):
        blocked = {"chromadb", "sentence_transformers", "torch", "deepinsight.core.retriever"}
        before = {name for name in blocked if name in sys.modules}
        response = self.client.get("/api/evidence/company-profile/BeOne%20Medicines")
        self.assertEqual(response.status_code, 200, response.text)
        after = {name for name in blocked if name in sys.modules}
        self.assertEqual(after - before, set())

    def test_11_response_has_expected_wrapper(self):
        response = self.client.get("/api/evidence/company-profile/%E7%99%BE%E6%B5%8E%E7%A5%9E%E5%B7%9E")
        payload = response.json()
        self.assertEqual(payload["metadata"]["data_scope"], "first_version_nsclc_hengrui_beone")
        json.loads(response.text)


if __name__ == "__main__":
    unittest.main()
