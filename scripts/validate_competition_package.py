"""Run the offline validation suite shipped with the competition source package."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TEST_LIST_PATH = PROJECT_ROOT / "tests" / "competition_core_tests.txt"
FINAL_METADATA_PATH = PROJECT_ROOT / "RELEASE_METADATA.json"
TEMPLATE_METADATA_PATH = PROJECT_ROOT / "RELEASE_METADATA.template.json"


def _clean_environment() -> dict[str, str]:
    environment = os.environ.copy()
    for name in (
        "DEEPSEEK_API_KEY",
        "DEEPSEEK_BASE_URL",
        "DEEPSEEK_MODEL",
        "GROUNDED_QA_LLM_ENABLED",
    ):
        environment.pop(name, None)
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    return environment


def _run(args: list[str], *, quiet: bool = False) -> None:
    subprocess.run(
        args,
        cwd=PROJECT_ROOT,
        env=_clean_environment(),
        stdout=subprocess.DEVNULL if quiet else None,
        check=True,
    )


def main() -> int:
    metadata_path = FINAL_METADATA_PATH if FINAL_METADATA_PATH.is_file() else TEMPLATE_METADATA_PATH
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    if metadata.get("data_version") != "sha256:330ac862f52db200":
        raise RuntimeError(f"{metadata_path.name}中的data_version与比赛冻结版本不一致。")

    tests = [
        line.strip()
        for line in TEST_LIST_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    _run([sys.executable, "scripts/validate_source_registry.py"])
    _run([sys.executable, "-m", "json.tool", "config/evidence_chains.json"], quiet=True)
    _run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "--noconftest",
            "-p",
            "no:cacheprovider",
            *tests,
        ]
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
