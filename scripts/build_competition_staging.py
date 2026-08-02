"""Build the competition source staging directory from an explicit whitelist."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_PATH = PROJECT_ROOT / "RELEASE_METADATA.template.json"
SOURCE_COMMIT_PLACEHOLDER = "__GENERATED_AT_PACKAGING__"
SHA_PATTERN = re.compile(r"^[0-9a-f]{40}$")

ROOT_FILES = [
    "README.md",
    ".python-version",
    ".gitignore",
    ".gitattributes",
    ".env.example",
    "Makefile",
    "requirements-deploy.txt",
    "requirements-test.txt",
    "render.yaml",
]
CONFIG_AND_DATA_FILES = [
    "config/entity_aliases.json",
    "config/evidence_chains.json",
    "config/evidence_rules.json",
    "config/grounded_qa_rules.json",
    "data/source_registry.csv",
]
CORE_FILES = [
    "deepinsight/__init__.py",
    "deepinsight/config.py",
    "deepinsight/core/__init__.py",
    "deepinsight/core/company_evidence_comparison_service.py",
    "deepinsight/core/company_evidence_profile_service.py",
    "deepinsight/core/evidence_chain_service.py",
    "deepinsight/core/evidence_decision_brief_service.py",
    "deepinsight/core/evidence_workbench_service.py",
    "deepinsight/core/grounded_qa_llm.py",
    "deepinsight/core/grounded_qa_service.py",
    "deepinsight/core/grounded_qa_usage_guard.py",
    "deepinsight/core/industry_taxonomy.py",
    "deepinsight/core/rd_decision_agent_service.py",
    "deepinsight/core/rd_event_timeline_service.py",
    "deepinsight/core/source_registry_service.py",
]
WEB_FILES = [
    "webapp/__init__.py",
    "webapp/main.py",
    "webapp/frontend_src/README.md",
    "webapp/frontend_src/build.py",
    "webapp/frontend_src/component.js",
    "webapp/frontend_src/template.html",
    "webapp/static/index.html",
    "webapp/static/dc-runtime.js",
    "webapp/static/favicon.svg",
]
SCRIPT_AND_DOC_FILES = [
    "scripts/README.md",
    "scripts/validate_source_registry.py",
    "scripts/query_source_registry.py",
    "scripts/build_formal_evaluation_cases.py",
    "scripts/validate_competition_package.py",
    "docs/data_dictionary.md",
    "docs/project_architecture.md",
    "docs/evaluation_protocol.md",
    "docs/decision_agent_protocol.md",
]
TREE_DIRECTORIES = [
    "webapp/static/fonts",
    "webapp/static/vendor",
    "evaluation",
]


def _copy_file(relative_path: str, output_dir: Path) -> None:
    source = PROJECT_ROOT / relative_path
    target = output_dir / relative_path
    if not source.is_file():
        raise FileNotFoundError(f"白名单文件不存在：{relative_path}")
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)


def _copy_tree(relative_path: str, output_dir: Path) -> None:
    source = PROJECT_ROOT / relative_path
    target = output_dir / relative_path
    if not source.is_dir():
        raise FileNotFoundError(f"白名单目录不存在：{relative_path}")
    shutil.copytree(
        source,
        target,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".pytest_cache"),
    )


def _git_source_commit() -> str:
    try:
        commit = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=PROJECT_ROOT,
            check=True,
            text=True,
            capture_output=True,
        ).stdout.strip()
        status = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=PROJECT_ROOT,
            check=True,
            text=True,
            capture_output=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError) as exc:
        raise RuntimeError("正式暂存要求Git可用，当前无法读取HEAD或工作区状态。") from exc
    if status:
        raise RuntimeError("正式暂存要求Git工作区干净；当前存在未提交改动。")
    if not SHA_PATTERN.fullmatch(commit):
        raise RuntimeError("git rev-parse HEAD未返回有效的40位提交SHA。")
    return commit


def resolve_source_commit(explicit_source_commit: str | None) -> str:
    if explicit_source_commit is None:
        return _git_source_commit()
    commit = explicit_source_commit.strip().lower()
    if not SHA_PATTERN.fullmatch(commit):
        raise ValueError("预打包验证SHA必须是40位小写十六进制Git提交。")
    return commit


def materialize_release_metadata(template_path: Path, output_path: Path, source_commit: str) -> dict[str, object]:
    payload = json.loads(template_path.read_text(encoding="utf-8"))
    if payload.get("source_commit") != SOURCE_COMMIT_PLACEHOLDER:
        raise RuntimeError("发布元数据模板缺少预期的source_commit占位值。")
    if not SHA_PATTERN.fullmatch(source_commit):
        raise ValueError("source_commit必须是40位小写十六进制Git提交。")
    payload["source_commit"] = source_commit
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return payload


def build_staging(output_dir: Path, *, explicit_source_commit: str | None = None) -> dict[str, object]:
    output_dir = output_dir.resolve()
    if output_dir.exists():
        raise FileExistsError(f"暂存目录已存在，拒绝覆盖：{output_dir}")
    source_commit = resolve_source_commit(explicit_source_commit)

    output_dir.mkdir(parents=True)
    for path in [*ROOT_FILES, *CONFIG_AND_DATA_FILES, *CORE_FILES, *WEB_FILES, *SCRIPT_AND_DOC_FILES]:
        _copy_file(path, output_dir)
    for path in TREE_DIRECTORIES:
        _copy_tree(path, output_dir)

    test_list_path = PROJECT_ROOT / "tests" / "competition_core_tests.txt"
    tests = [
        line.strip()
        for line in test_list_path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    _copy_file("tests/competition_core_tests.txt", output_dir)
    for path in tests:
        _copy_file(path, output_dir)

    metadata = materialize_release_metadata(
        TEMPLATE_PATH,
        output_dir / "RELEASE_METADATA.json",
        source_commit,
    )
    return {
        "output_dir": str(output_dir),
        "source_commit": source_commit,
        "metadata": metadata,
        "file_count": sum(1 for path in output_dir.rglob("*") if path.is_file()),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="创建药研罗盘比赛源码白名单暂存目录")
    parser.add_argument("--output-dir", required=True, help="必须是尚不存在的目标目录")
    parser.add_argument(
        "--source-commit",
        help="仅用于预打包验证；正式暂存必须省略，以便从干净Git HEAD自动生成",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    result = build_staging(Path(args.output_dir), explicit_source_commit=args.source_commit)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
