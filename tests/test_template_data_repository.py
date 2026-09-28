import unittest
import json
from pathlib import Path

from deepinsight.core.template_data_repository import TemplateDataRepository


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = json.loads((ROOT / "data" / "template" / "data_manifest.json").read_text(encoding="utf-8"))


class TemplateDataRepositoryTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.repository = TemplateDataRepository(ROOT / "data" / "template")

    def test_normalized_template_is_readable(self):
        self.assertEqual(len(self.repository.load_table("sources")), MANIFEST["counts"]["sources"])
        self.assertEqual(len(self.repository.load_table("relations")), MANIFEST["counts"]["relations"])

    def test_runtime_rows_preserve_legacy_chain_identifiers(self):
        rows = self.repository.source_rows()
        source_ids = {row["source_id"] for row in rows}
        # Detached rows and rows with unresolved relations are withheld.
        self.assertEqual(len(rows), MANIFEST["counts"]["sources"])
        self.assertIn("B006", source_ids)
        self.assertIn("A005", source_ids)
        self.assertIn("SRC_MET_SURPASS2_PUB", source_ids)

    def test_template_relations_supply_query_fields(self):
        row = next(row for row in self.repository.source_rows() if row["source_id"] == "B006")
        self.assertEqual(row["company_cn"], "百济神州")
        self.assertEqual(row["parent_trial_id"], "NCT03663205")
        self.assertIn("替雷利珠单抗", row["drug_names"])
        self.assertEqual(row["is_latest_evidence"], "false")


if __name__ == "__main__":
    unittest.main()
