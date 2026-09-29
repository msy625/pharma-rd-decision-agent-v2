"""Regression tests for explicit normalized-table evidence-chain projection."""

import unittest

from deepinsight.core.evidence_chain_service import EvidenceChainService
from deepinsight.core.source_registry_service import NormalizedSourceRegistryService
from tests.test_deployment_health import _ASGIClient
from webapp.main import app


class NormalizedEvidenceChainProjectionTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.service = EvidenceChainService(source_registry_service=NormalizedSourceRegistryService())

    def test_new_trial_is_projected_as_single_source_without_inference(self):
        chain = self.service.get_trial_chain("NCT07836530")
        self.assertEqual(chain["chain_origin"], "template_projection")
        self.assertEqual(chain["projection_status"], "single_source")
        self.assertEqual({item["source_id"] for item in chain["evidence_items"]}, {"SRC_CTG_NCT07836530"})
        self.assertTrue(chain["evidence_gaps"])

    def test_manual_config_is_an_overlay_for_an_existing_trial(self):
        chain = self.service.get_trial_chain("NCT03663205")
        self.assertEqual(chain["chain_origin"], "manual_config")
        self.assertEqual(chain["projection_status"], "formed")
        self.assertTrue(chain["manual_override"])

    def test_relationship_insufficient_is_explicit_not_inferred(self):
        chain = next(item for item in self.service.list_chains(chain_type="trial") if item["projection_status"] == "relationship_insufficient")
        self.assertEqual(chain["chain_origin"], "template_projection")
        self.assertEqual(chain["source_count"], 0)
        self.assertIn("不能自动补关联", chain["evidence_gaps"][0])

    def test_projection_exposes_all_three_chain_states(self):
        states = {item["projection_status"] for item in self.service.list_chains(chain_type="trial")}
        self.assertTrue({"formed", "single_source", "relationship_insufficient"}.issubset(states))

    def test_asset_and_regulatory_event_form_a_regulatory_chain(self):
        chain = self.service.get_drug_regulatory_chain("tirzepatide")
        self.assertEqual(chain["chain_id"], "projected:regulatory:ASSET_TIRZEPATIDE")
        self.assertEqual(chain["chain_origin"], "template_projection")
        self.assertTrue(chain["regulatory_events"])

    def test_organization_coverage_uses_only_explicit_relations_and_sponsorship(self):
        coverage = self.service.organization_coverage("ORG_ASTRAZENECA")
        self.assertEqual(coverage["organization"]["organization_id"], "ORG_ASTRAZENECA")
        self.assertEqual(coverage["coverage"]["explicit_source_count"], 57)
        self.assertEqual(coverage["coverage"]["sponsored_study_count"], 53)


class NormalizedEvidenceChainProjectionApiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = _ASGIClient(app)

    def test_trial_chain_api_returns_a_projection_state(self):
        response = self.client.get("/api/evidence/trial-chain/NCT07836530")
        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertEqual(payload["item"]["projection_status"], "single_source")
        self.assertEqual(payload["metadata"]["data_backend"], "normalized_template_projection")

    def test_organization_coverage_api_returns_the_explicit_coverage_view(self):
        response = self.client.get("/api/evidence/organization-coverage/ORG_ASTRAZENECA")
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["item"]["coverage"]["sponsored_study_count"], 53)


if __name__ == "__main__":
    unittest.main()
