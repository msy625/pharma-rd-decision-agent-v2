import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.build_competition_staging import (
    SOURCE_COMMIT_PLACEHOLDER,
    _git_source_commit,
    build_staging,
    materialize_release_metadata,
    resolve_source_commit,
)


ROOT = Path(__file__).resolve().parents[1]


def completed(stdout: str) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(args=["git"], returncode=0, stdout=stdout, stderr="")


class CompetitionStagingTest(unittest.TestCase):
    def test_template_materializes_final_metadata_in_temporary_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "RELEASE_METADATA.json"
            payload = materialize_release_metadata(
                ROOT / "RELEASE_METADATA.template.json",
                output,
                "d" * 40,
            )
            saved = json.loads(output.read_text(encoding="utf-8"))
        self.assertEqual(payload, saved)
        self.assertEqual(saved["source_commit"], "d" * 40)
        self.assertNotEqual(saved["source_commit"], SOURCE_COMMIT_PLACEHOLDER)

    def test_formal_mode_reads_clean_git_head(self):
        with patch(
            "scripts.build_competition_staging.subprocess.run",
            side_effect=[completed("e" * 40 + "\n"), completed("")],
        ):
            self.assertEqual(_git_source_commit(), "e" * 40)

    def test_formal_mode_stops_when_git_is_unavailable(self):
        with patch(
            "scripts.build_competition_staging.subprocess.run",
            side_effect=FileNotFoundError("git"),
        ):
            with self.assertRaisesRegex(RuntimeError, "Git可用"):
                _git_source_commit()

    def test_formal_mode_stops_before_output_when_worktree_is_dirty(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "must-not-exist"
            with patch(
                "scripts.build_competition_staging.subprocess.run",
                side_effect=[completed("f" * 40 + "\n"), completed(" M README.md\n")],
            ):
                with self.assertRaisesRegex(RuntimeError, "工作区干净"):
                    build_staging(output)
            self.assertFalse(output.exists())

    def test_preview_mode_accepts_explicit_sha_without_git(self):
        with patch("scripts.build_competition_staging._git_source_commit") as git_source:
            self.assertEqual(resolve_source_commit("A" * 40), "a" * 40)
        git_source.assert_not_called()
        with self.assertRaises(ValueError):
            resolve_source_commit("not-a-sha")


if __name__ == "__main__":
    unittest.main()
