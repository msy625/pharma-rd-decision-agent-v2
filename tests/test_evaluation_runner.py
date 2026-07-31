import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from evaluation.report import OUTPUT_FILENAMES
from evaluation.runner import DEFAULT_CASES_PATH, DEFAULT_MANIFEST_PATH, _git_info, run_benchmark
from evaluation.validators import DataVersionMismatchError, EvaluationValidationError, PROJECT_ROOT


def subprocess_result(stdout: str):
    from subprocess import CompletedProcess

    return CompletedProcess(args=["git"], returncode=0, stdout=stdout, stderr="")


class EvaluationRunnerTest(unittest.TestCase):
    def test_git_info_prefers_available_git(self):
        completed = [
            subprocess_result("a" * 40),
            subprocess_result("main"),
            subprocess_result(""),
        ]
        with patch("evaluation.runner.subprocess.run", side_effect=completed):
            result = _git_info(Path("/temporary/repository"))
        self.assertEqual(result["sha"], "a" * 40)
        self.assertEqual(result["branch"], "main")
        self.assertFalse(result["dirty"])
        self.assertEqual(result["source"], "git")

    def test_git_info_uses_release_metadata_when_git_is_unavailable(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "RELEASE_METADATA.json").write_text(
                json.dumps({"source_commit": "b" * 40}),
                encoding="utf-8",
            )
            with patch("evaluation.runner.subprocess.run", side_effect=FileNotFoundError("git")):
                result = _git_info(root)
        self.assertEqual(result["sha"], "b" * 40)
        self.assertEqual(result["branch"], "release-metadata")
        self.assertFalse(result["dirty"])
        self.assertEqual(result["source"], "release_metadata")

    def test_git_info_returns_unknown_when_git_and_metadata_are_unavailable(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch("evaluation.runner.subprocess.run", side_effect=FileNotFoundError("git")):
                result = _git_info(Path(tmp))
        self.assertEqual(result["sha"], "unknown")
        self.assertEqual(result["branch"], "unknown")
        self.assertFalse(result["dirty"])
        self.assertEqual(result["source"], "unknown")
        self.assertIn("RELEASE_METADATA.json", result["error"])

    def test_runner_writes_all_outputs_to_caller_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp) / "pilot results with spaces"
            result = run_benchmark(output_dir=output_dir)
            self.assertEqual(result["run_manifest"]["case_count"], 12)
            self.assertEqual(result["run_manifest"]["result_count"], 36)
            self.assertEqual({path.name for path in output_dir.iterdir()}, set(OUTPUT_FILENAMES))
            self.assertTrue(all((output_dir / filename).exists() for filename in OUTPUT_FILENAMES))

    def test_all_output_formats_are_parseable(self):
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp) / "results"
            run_benchmark(output_dir=output_dir, baseline_names=["grounded_qa_local"])
            json.loads((output_dir / "run_manifest.json").read_text(encoding="utf-8"))
            json.loads((output_dir / "failures.json").read_text(encoding="utf-8"))
            rows = [json.loads(line) for line in (output_dir / "case_results.jsonl").read_text(encoding="utf-8").splitlines()]
            self.assertEqual(len(rows), 12)
            for filename in ["metric_details.csv", "category_summary.csv", "baseline_comparison.csv", "latency_percentiles.csv"]:
                self.assertIn(",", (output_dir / filename).read_text(encoding="utf-8").splitlines()[0])

    def test_data_version_mismatch_stops_before_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp) / "must-not-exist"
            with patch("evaluation.runner.GroundedQAService.data_version", return_value="sha256:0000000000000000"):
                with self.assertRaises(DataVersionMismatchError):
                    run_benchmark(output_dir=output_dir)
            self.assertFalse(output_dir.exists())

    def test_runner_rejects_production_fact_directories(self):
        with self.assertRaises(EvaluationValidationError):
            run_benchmark(
                output_dir=PROJECT_ROOT / "data" / "evaluation-output",
                baseline_names=["grounded_qa_local"],
            )

    def test_grounded_pilot_records_no_model_and_no_case_errors(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = run_benchmark(output_dir=Path(tmp) / "results", baseline_names=["grounded_qa_local"])
            self.assertEqual(len(result["records"]), 12)
            self.assertTrue(all(record["result"]["used_llm"] is False for record in result["records"]))
            self.assertTrue(all(record["result"]["error"] == "" for record in result["records"]))

    def test_snapshot_commit_is_recorded_but_not_used_as_head_gate(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch(
                "evaluation.runner._git_info",
                return_value={"sha": "f" * 40, "branch": "future-evaluation-commit", "dirty": False},
            ):
                result = run_benchmark(
                    output_dir=Path(tmp) / "results",
                    baseline_names=["structured_no_chain"],
                )
            self.assertEqual(result["run_manifest"]["git_sha"], "f" * 40)
            self.assertEqual(
                result["run_manifest"]["facts_snapshot_commit"],
                "656626b8756a01e4f6280f4451be503a92439e71",
            )


if __name__ == "__main__":
    unittest.main()
