import unittest
import json
from pathlib import Path

from tests.test_deployment_health import _ASGIClient
from webapp.main import app


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = json.loads((ROOT / "data" / "template" / "data_manifest.json").read_text(encoding="utf-8"))


class NormalizedDataApiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = _ASGIClient(app)

    def get(self, path):
        response = self.client.get(path)
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def test_catalog_and_cross_domain_source_search(self):
        catalog = self.get("/api/normalized/catalog")
        self.assertEqual(catalog["counts"]["sources"], MANIFEST["counts"]["sources"])
        self.assertIn("DOM_METABOLIC", {item["domain_id"] for item in catalog["domains"]})
        result = self.get("/api/normalized/sources?domain_id=DOM_METABOLIC&q=tirzepatide")
        self.assertEqual(result["count"], 2)

    def test_entity_and_trial_details_follow_explicit_relations(self):
        organization = self.get("/api/normalized/organizations/AstraZeneca")
        self.assertEqual(organization["organization"]["organization_id"], "ORG_ASTRAZENECA")
        asset = self.get("/api/normalized/assets/tirzepatide")
        self.assertEqual(asset["asset"]["asset_id"], "ASSET_TIRZEPATIDE")
        study = self.get("/api/normalized/studies/NCT04184622")
        self.assertEqual(study["study"]["study_name"], "SURMOUNT-1")
        source = self.get("/api/normalized/sources/SRC_MET_SURMOUNT1_PUB")
        self.assertTrue(source["facts"])
        self.assertTrue(source["relations"])


if __name__ == "__main__":
    unittest.main()
