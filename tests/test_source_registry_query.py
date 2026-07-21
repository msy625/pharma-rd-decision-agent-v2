import importlib.util
import json
import subprocess
import sys
import unittest
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


query_tool = load_module("query_source_registry", ROOT / "scripts" / "query_source_registry.py")
validate_tool = load_module("validate_source_registry", ROOT / "scripts" / "validate_source_registry.py")


class SourceRegistryQueryTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = query_tool.load_registry()
        cls.aliases = query_tool.load_aliases()

    def ids(self, rows):
        return {row["source_id"] for row in rows}

    def test_read_31_sources(self):
        self.assertEqual(len(self.rows), 31)

    def test_source_id_unique(self):
        counts = Counter(row["source_id"] for row in self.rows)
        self.assertFalse([sid for sid, count in counts.items() if count > 1])

    def test_company_counts(self):
        counts = Counter(row.get("company_cn") or row.get("company") for row in self.rows)
        self.assertEqual(counts["恒瑞医药"], 15)
        self.assertEqual(counts["百济神州"], 16)

    def test_validate_registry_has_no_errors(self):
        self.assertEqual(validate_tool.validate(), [])

    def test_nct03663205_returns_rationale_304_registry_and_papers(self):
        rows = query_tool.query_rows(self.rows, trial_id="NCT03663205")
        self.assertEqual(self.ids(rows), {"B003", "B006", "B007"})

    def test_nct04379635_returns_rationale_315_sources(self):
        rows = query_tool.query_rows(self.rows, trial_id="NCT04379635")
        self.assertEqual(self.ids(rows), {"B011", "B012", "B013"})

    def test_nct04619433_is_terminated(self):
        rows = query_tool.query_rows(self.rows, text="NCT04619433")
        self.assertEqual(self.ids(rows), {"H006"})
        self.assertEqual(rows[0]["study_status"], "Terminated")

    def test_camrelizumab_alias_query(self):
        shr_rows = query_tool.query_rows(self.rows, drug="SHR-1210", aliases=self.aliases)
        cam_rows = query_tool.query_rows(self.rows, drug="Camrelizumab", aliases=self.aliases)
        self.assertEqual(self.ids(shr_rows), self.ids(cam_rows))
        self.assertIn("H004", self.ids(shr_rows))

    def test_nonexistent_query_returns_empty_list(self):
        self.assertEqual(query_tool.query_rows(self.rows, company="不存在的企业"), [])
        self.assertEqual(query_tool.query_rows(self.rows, trial_id="NCT00000000"), [])

    def test_json_output_is_valid(self):
        result = subprocess.run(
            [
                sys.executable,
                "scripts/query_source_registry.py",
                "--study-name",
                "RATIONALE-304",
                "--latest-only",
                "--format",
                "json",
            ],
            cwd=ROOT,
            check=True,
            text=True,
            capture_output=True,
        )
        parsed = json.loads(result.stdout)
        self.assertIsInstance(parsed, list)

    def test_latest_only_keeps_final_not_interim_for_rationale_304(self):
        rows = query_tool.query_rows(self.rows, study_name="RATIONALE-304", latest_only=True)
        ids = self.ids(rows)
        self.assertIn("B007", ids)
        self.assertNotIn("B006", ids)

    def test_b015_b016_regulatory_status_not_mixed(self):
        by_id = {row["source_id"]: row for row in self.rows}
        self.assertEqual(by_id["B015"]["authorisation_status"], "欧盟正式授权")
        self.assertEqual(by_id["B016"]["regulatory_event_type"], "CHMP positive opinion")
        self.assertNotEqual(by_id["B016"].get("authorisation_status"), "欧盟正式授权")

    def test_sclc_pipeline_record_not_in_nsclc_comparison(self):
        b014 = next(row for row in self.rows if row["source_id"] == "B014")
        self.assertFalse(query_tool.is_nsclc_comparison_record(b014))


if __name__ == "__main__":
    unittest.main()
