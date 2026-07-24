import unittest

from tests.test_deployment_health import _ASGIClient
from webapp.main import app


class EvidenceDecisionBriefApiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = _ASGIClient(app)

    def test_company_list_and_brief(self):
        companies = self.client.get("/api/evidence/decision-brief/companies")
        self.assertEqual(companies.status_code, 200)
        self.assertGreaterEqual(companies.json()["count"], 3)
        response = self.client.get("/api/evidence/decision-brief/%E9%98%BF%E6%96%AF%E5%88%A9%E5%BA%B7")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["brief"]["subject"]["company_name"], "阿斯利康")

    def test_unknown_company_is_404(self):
        response = self.client.get("/api/evidence/decision-brief/unknown-company")
        self.assertEqual(response.status_code, 404)

    def test_runtime_capability_exposes_brief(self):
        response = self.client.get("/api/runtime-capabilities")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["evidence_decision_brief_available"])


if __name__ == "__main__":
    unittest.main()
