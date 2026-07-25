import csv
import json
import tempfile
import unittest
from pathlib import Path

from evaluation.runner import run_benchmark


class EvaluationReportTest(unittest.TestCase):
    def test_report_contains_required_pilot_boundaries(self):
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp) / "report"
            run_benchmark(output_dir=output_dir, baseline_names=["grounded_qa_local"])
            report = (output_dir / "report.md").read_text(encoding="utf-8")
            self.assertIn("12题pilot试运行结果", report)
            self.assertIn("不是最终业务成绩", report)
            self.assertIn("不能外推到整个医药研发领域", report)
            self.assertIn("自由文本监管语义仍需人工复核", report)
            self.assertIn("服务层延迟不等于浏览器端到端延迟", report)

    def test_csv_and_json_outputs_expose_failures_and_metrics(self):
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp) / "report"
            run_benchmark(output_dir=output_dir)
            failures = json.loads((output_dir / "failures.json").read_text(encoding="utf-8"))
            self.assertTrue(any(item["baseline"] == "keyword_contains" for item in failures))
            self.assertFalse(any(item["baseline"] == "grounded_qa_local" for item in failures))
            with (output_dir / "baseline_comparison.csv").open(encoding="utf-8", newline="") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual({row["baseline"] for row in rows}, {"keyword_contains", "structured_no_chain", "grounded_qa_local"})
            self.assertTrue(all("overall_pass_rate" in row for row in rows))

    def test_dynamic_results_are_only_written_below_requested_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp) / "nested" / "pilot"
            result = run_benchmark(output_dir=output_dir, baseline_names=["keyword_contains"])
            self.assertTrue(all(Path(path).parent == output_dir for path in result["output_files"]))


if __name__ == "__main__":
    unittest.main()
