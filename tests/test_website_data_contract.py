"""Regression contract for the curated website root dataset."""

import csv
import hashlib
import json
import unittest
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "data" / "template"
CONTRACT = json.loads((TEMPLATE / "website_data_contract.json").read_text(encoding="utf-8"))
MANIFEST = json.loads((TEMPLATE / "data_manifest.json").read_text(encoding="utf-8"))


class WebsiteDataContractTest(unittest.TestCase):
    def test_contract_and_manifest_describe_the_same_dataset(self):
        self.assertEqual(CONTRACT["dataset"], "website_curated_normalized_v1")
        self.assertEqual(MANIFEST["dataset"], CONTRACT["dataset"])
        self.assertEqual(MANIFEST["counts"], CONTRACT["expected_counts"])

    def test_all_baseline_tables_match_the_frozen_hashes(self):
        for filename, expected_hash in CONTRACT["table_sha256"].items():
            with self.subTest(filename=filename):
                self.assertEqual(hashlib.sha256((TEMPLATE / filename).read_bytes()).hexdigest(), expected_hash)

    def test_source_and_relation_statuses_match_the_display_contract(self):
        with (TEMPLATE / "sources.csv").open(encoding="utf-8", newline="") as handle:
            source_statuses = Counter(row["verification_status"] for row in csv.DictReader(handle))
        with (TEMPLATE / "relations.csv").open(encoding="utf-8", newline="") as handle:
            relation_statuses = Counter(row["relation_status"] for row in csv.DictReader(handle))
        self.assertEqual(dict(source_statuses), CONTRACT["expected_source_status_counts"])
        self.assertEqual(dict(relation_statuses), CONTRACT["expected_relation_status_counts"])
        self.assertTrue(all(item["website_allowed"] for item in CONTRACT["verification_statuses"].values()))


if __name__ == "__main__":
    unittest.main()
