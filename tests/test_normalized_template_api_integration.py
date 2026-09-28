"""Regression coverage for API routes backed by the normalized template."""

import unittest
from unittest.mock import patch

from deepinsight.core.source_registry_service import SourceRegistryService
from tests.test_deployment_health import _ASGIClient
from webapp.main import app


class NormalizedTemplateApiIntegrationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = _ASGIClient(app)

    def test_current_institution_routes_do_not_open_legacy_csv(self):
        paths = [
            "/api/normalized/catalog",
            "/api/evidence/institution-profile/%E6%81%92%E7%91%9E%E5%8C%BB%E8%8D%AF",
            "/api/evidence/institution-comparison",
            "/api/evidence/institution-timeline",
            "/api/evidence/institution-brief/%E6%81%92%E7%91%9E%E5%8C%BB%E8%8D%AF",
        ]
        with patch.object(SourceRegistryService, "_read_csv", side_effect=AssertionError("legacy CSV must not be read")):
            payloads = []
            for path in paths:
                response = self.client.get(path)
                self.assertEqual(response.status_code, 200, response.text)
                payloads.append(response.json())

        self.assertIn("organizations", payloads[0]["counts"])
        self.assertIn("profile", payloads[1])
        self.assertIn("comparison", payloads[2])
        self.assertIn("timeline", payloads[3])
        self.assertEqual(payloads[1]["metadata"]["data_scope"], "all_normalized_organizations")

    def test_normalized_institution_and_brief_routes_serve_new_dataset(self):
        catalog = self.client.get("/api/normalized/catalog")
        directory = self.client.get("/api/evidence/institution-profile-institutions")
        comparison = self.client.get("/api/evidence/institution-comparison")
        timeline = self.client.get("/api/evidence/institution-timeline?institution=%E9%98%BF%E6%96%AF%E5%88%A9%E5%BA%B7")
        brief = self.client.get("/api/evidence/institution-brief/%E9%98%BF%E6%96%AF%E5%88%A9%E5%BA%B7")
        directions = self.client.get("/api/evidence/direction-briefs")
        for response in (catalog, directory, comparison, timeline, brief, directions):
            self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(directory.json()["count"], 225)
        self.assertEqual(len(comparison.json()["comparison"]["institutions"]), 2)
        self.assertGreater(timeline.json()["timeline"]["summary"]["event_count"], 0)
        self.assertEqual(brief.json()["brief"]["brief_type"], "institution_research")
        self.assertGreater(len(directions.json()["items"]), 0)

    def test_normalized_agent_preserves_explicit_relation_states_and_refusals(self):
        cases = (
            ("NCT06667908 有哪些来源支持？", "单来源"),
            ("NCT03529110 有多来源证据吗？", "关系不足"),
            ("阿斯利康研究是否相关？", "无法确认关联"),
            ("请给出机构排名", "不提供此类推断"),
        )
        for question, expected in cases:
            response = self.client.post("/api/evidence/grounded-qa", {"question": question, "generation_mode": "local"})
            self.assertEqual(response.status_code, 200, response.text)
            self.assertIn(expected, response.json()["result"]["answer"])


if __name__ == "__main__":
    unittest.main()
