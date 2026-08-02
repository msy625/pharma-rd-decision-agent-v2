import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from deepinsight.core.grounded_qa_llm import grounded_llm_settings
from deepinsight.core.grounded_qa_service import GroundedQAService
from deepinsight.core.source_registry_service import SourceRegistryService
from webapp.main import evidence_workbench, ready, runtime_capabilities


ROOT = Path(__file__).resolve().parents[1]
SOURCE_COMMIT_PLACEHOLDER = "__GENERATED_AT_PACKAGING__"


class CompetitionPackageTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.metadata_path = Path(self.temp_dir.name) / "RELEASE_METADATA.json"
        source_path = ROOT / "RELEASE_METADATA.json"
        if not source_path.is_file():
            source_path = ROOT / "RELEASE_METADATA.template.json"
        self.metadata = json.loads(source_path.read_text(encoding="utf-8"))
        if self.metadata.get("source_commit") == SOURCE_COMMIT_PLACEHOLDER:
            self.metadata["source_commit"] = "c" * 40
        self.metadata_path.write_text(
            json.dumps(self.metadata, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_release_metadata_matches_frozen_submission_scope(self):
        self.assertEqual(self.metadata["project"], "药研罗盘")
        self.assertEqual(self.metadata["version"], "competition-submission-v1.0")
        self.assertEqual(self.metadata["data_version"], "sha256:330ac862f52db200")
        self.assertEqual(self.metadata["company_count"], 3)
        self.assertEqual(self.metadata["source_count"], 39)
        self.assertEqual(self.metadata["trial_chain_count"], 14)
        self.assertEqual(self.metadata["regulatory_chain_count"], 1)
        self.assertEqual(self.metadata["pending_relation_count"], 7)

    def test_repository_has_template_or_package_has_final_metadata(self):
        template_path = ROOT / "RELEASE_METADATA.template.json"
        final_path = ROOT / "RELEASE_METADATA.json"
        self.assertNotEqual(template_path.is_file(), final_path.is_file())
        if template_path.is_file():
            template = json.loads(template_path.read_text(encoding="utf-8"))
            self.assertEqual(template["source_commit"], SOURCE_COMMIT_PLACEHOLDER)
        else:
            final = json.loads(final_path.read_text(encoding="utf-8"))
            self.assertRegex(final["source_commit"], r"^[0-9a-f]{40}$")

    def test_generated_release_metadata_uses_explicit_commit_and_not_placeholder(self):
        payload = json.loads(self.metadata_path.read_text(encoding="utf-8"))
        self.assertRegex(payload["source_commit"], r"^[0-9a-f]{40}$")
        self.assertNotEqual(payload["source_commit"], SOURCE_COMMIT_PLACEHOLDER)
        self.assertNotEqual(self.metadata_path, ROOT / "RELEASE_METADATA.json")

    def test_ready_matches_release_metadata(self):
        payload = ready()
        self.assertEqual(payload["status"], "ready")
        self.assertEqual(payload["source_count"], self.metadata["source_count"])
        self.assertEqual(payload["data_version"], self.metadata["data_version"])
        self.assertTrue(payload["local_grounded_qa_available"])

    def test_workbench_matches_release_metadata(self):
        summary = evidence_workbench()["workbench"]["summary"]
        self.assertEqual(summary["company_count"], self.metadata["company_count"])
        self.assertEqual(summary["source_count"], self.metadata["source_count"])
        self.assertEqual(summary["trial_chain_count"], self.metadata["trial_chain_count"])
        self.assertEqual(summary["regulatory_chain_count"], self.metadata["regulatory_chain_count"])
        self.assertEqual(summary["unresolved_link_count"], self.metadata["pending_relation_count"])

    def test_source_registry_contains_only_verified_submission_sources(self):
        rows = SourceRegistryService().load_rows()
        self.assertEqual(len(rows), 39)
        self.assertEqual({row["verification_status"] for row in rows}, {"已人工核验"})

    def test_no_key_mode_does_not_enable_llm(self):
        clean_env = {
            key: value
            for key, value in os.environ.items()
            if key not in {"DEEPSEEK_API_KEY", "GROUNDED_QA_LLM_ENABLED"}
        }
        with patch.dict(os.environ, clean_env, clear=True):
            settings = grounded_llm_settings()
            response = GroundedQAService().answer_question(
                "RATIONALE-315目前有哪些证据？",
                use_configured_llm=False,
            )
        self.assertFalse(settings["configured"])
        self.assertFalse(response["trace"]["used_llm"])
        self.assertFalse(response["trace"].get("llm_attempted", False))

    def test_runtime_capabilities_keep_competition_core_without_legacy_modules(self):
        payload = runtime_capabilities()
        self.assertTrue(payload["competition_core_available"])
        self.assertTrue(payload["evidence_workbench_available"])
        self.assertTrue(payload["company_evidence_profile_available"])
        self.assertTrue(payload["rd_event_timeline_available"])
        self.assertTrue(payload["evidence_decision_brief_available"])
        self.assertFalse(payload["legacy_features_available"])

    def test_render_config_has_no_secret_or_legacy_data_dependency(self):
        text = (ROOT / "render.yaml").read_text(encoding="utf-8")
        self.assertIn("sync: false", text)
        self.assertNotRegex(text, r"sk-[A-Za-z0-9_-]{12,}")
        for forbidden in ["enterprise_analysis.db", "data/chroma", "demo_cache", "/home/", "/root/"]:
            self.assertNotIn(forbidden, text)

    def test_test_requirements_are_lightweight(self):
        text = (ROOT / "requirements-test.txt").read_text(encoding="utf-8")
        self.assertIn("-r requirements-deploy.txt", text)
        self.assertIn("pytest==9.1.1", text)
        for forbidden in ["streamlit", "chromadb", "sentence-transformers", "torch"]:
            self.assertNotIn(forbidden, text.lower())


if __name__ == "__main__":
    unittest.main()
