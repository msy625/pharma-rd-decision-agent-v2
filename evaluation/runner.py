"""CLI and callable runner for the offline pilot benchmark."""

from __future__ import annotations

import argparse
import json
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from typing import Any

from deepinsight.core.company_evidence_comparison_service import CompanyEvidenceComparisonService
from deepinsight.core.evidence_chain_service import EvidenceChainService
from deepinsight.core.grounded_qa_service import GroundedQAService
from deepinsight.core.source_registry_service import SourceRegistryService
from evaluation.adapters import ProductionServiceAdapters
from evaluation.baselines import BASELINE_NAMES, build_baselines
from evaluation.metrics import aggregate_results, evaluate_case, result_status
from evaluation.report import write_evaluation_outputs
from evaluation.validators import (
    PROJECT_ROOT,
    assert_data_version,
    ensure_safe_output_directory,
    load_cases,
    load_json,
    validate_suite,
)


DEFAULT_MANIFEST_PATH = PROJECT_ROOT / "evaluation" / "cases" / "pilot_manifest.json"
DEFAULT_CASES_PATH = PROJECT_ROOT / "evaluation" / "cases" / "pilot_cases.jsonl"
DEFAULT_REVIEWS_PATH = PROJECT_ROOT / "evaluation" / "reviews" / "pilot_manual_reviews.json"
RELEASE_METADATA_PATH = PROJECT_ROOT / "RELEASE_METADATA.json"


def run_benchmark(
    *,
    output_dir: str | Path,
    manifest_path: str | Path = DEFAULT_MANIFEST_PATH,
    cases_path: str | Path = DEFAULT_CASES_PATH,
    baseline_names: list[str] | None = None,
    reviews_path: str | Path | None = DEFAULT_REVIEWS_PATH,
) -> dict[str, Any]:
    started_clock = perf_counter()
    started_at = _utc_now()
    manifest = load_json(manifest_path)
    cases = load_cases(cases_path)
    reviews = _load_reviews(reviews_path) if manifest.get("benchmark_stage") == "pilot" else {}

    source_service = SourceRegistryService()
    chain_service = EvidenceChainService(source_registry_service=source_service)
    comparison_service = CompanyEvidenceComparisonService(
        source_registry_service=source_service,
        evidence_chain_service=chain_service,
    )
    qa_service = GroundedQAService(
        source_registry_service=source_service,
        evidence_chain_service=chain_service,
        company_comparison_service=comparison_service,
    )
    adapters = ProductionServiceAdapters(
        source_registry_service=source_service,
        evidence_chain_service=chain_service,
        company_comparison_service=comparison_service,
        grounded_qa_service=qa_service,
    )

    known_source_ids = {row["source_id"] for row in source_service.load_rows()}
    known_chain_ids = {chain["chain_id"] for chain in chain_service.list_chains()}
    validate_suite(
        manifest,
        cases,
        known_source_ids=known_source_ids,
        known_chain_ids=known_chain_ids,
    )
    actual_data_version = qa_service.data_version()
    assert_data_version(manifest["expected_data_version"], actual_data_version)

    output_path = ensure_safe_output_directory(output_dir)
    selected_names = baseline_names or list(BASELINE_NAMES)
    baselines = build_baselines(adapters, selected_names)
    records: list[dict[str, Any]] = []
    for baseline in baselines:
        for case in cases:
            result = baseline.run(case)
            metrics = evaluate_case(case, result)
            manual_review = reviews.get(case["case_id"])
            records.append(
                {
                    "baseline": baseline.name,
                    "case_id": case["case_id"],
                    "split": case["split"],
                    "category": case["category"],
                    "target": case["target"],
                    "question": case["question"],
                    "expected_question_type": case["expected_question_type"],
                    "expected_source_ids": case["expected_source_ids"],
                    "allowed_source_ids": case["allowed_source_ids"],
                    "expected_chain_ids": case["expected_chain_ids"],
                    "result": result,
                    "metrics": metrics,
                    "manual_review": manual_review,
                    "status": result_status(baseline.name, case["category"], metrics, manual_review),
                }
            )

    aggregates = aggregate_results(records)
    git_info = _git_info(PROJECT_ROOT)
    completed_at = _utc_now()
    run_manifest = {
        "benchmark_name": manifest["benchmark_name"],
        "benchmark_stage": manifest["benchmark_stage"],
        "schema_version": manifest["schema_version"],
        "case_count": len(cases),
        "result_count": len(records),
        "baselines": selected_names,
        "expected_data_version": manifest["expected_data_version"],
        "actual_data_version": actual_data_version,
        "facts_snapshot_commit": manifest["facts_snapshot_commit"],
        "git_sha": git_info["sha"],
        "git_branch": git_info["branch"],
        "git_dirty": git_info["dirty"],
        "python_version": platform.python_version(),
        "platform": platform.platform(),
        "started_at": started_at,
        "completed_at": completed_at,
        "duration_ms": (perf_counter() - started_clock) * 1000,
        "arguments": {
            "manifest_path": str(Path(manifest_path)),
            "cases_path": str(Path(cases_path)),
            "output_dir": str(output_path),
            "baseline_names": selected_names,
            "reviews_path": str(Path(reviews_path)) if reviews_path else "",
        },
        "notes": [
            "本次运行未读取.env，也未创建或调用模型客户端。",
            "facts_snapshot_commit只表示事实快照起点，不要求实际Git SHA与其相同。",
            "服务层延迟不等于浏览器端到端延迟。",
        ],
    }
    output_files = write_evaluation_outputs(
        output_path,
        run_manifest=run_manifest,
        manifest=manifest,
        records=records,
        aggregates=aggregates,
    )
    return {
        "run_manifest": run_manifest,
        "records": records,
        "aggregates": aggregates,
        "output_files": [str(path) for path in output_files],
    }


def _git_info(repo_root: Path) -> dict[str, Any]:
    def run(*args: str) -> str:
        completed = subprocess.run(
            ["git", *args],
            cwd=repo_root,
            check=True,
            text=True,
            capture_output=True,
        )
        return completed.stdout.strip()

    try:
        return {
            "sha": run("rev-parse", "HEAD"),
            "branch": run("branch", "--show-current"),
            "dirty": bool(run("status", "--porcelain")),
            "source": "git",
        }
    except (OSError, subprocess.CalledProcessError) as exc:
        metadata_path = repo_root / RELEASE_METADATA_PATH.name
        try:
            payload = json.loads(metadata_path.read_text(encoding="utf-8"))
            source_commit = str(payload.get("source_commit") or "").strip()
            if source_commit:
                return {
                    "sha": source_commit,
                    "branch": "release-metadata",
                    "dirty": False,
                    "source": "release_metadata",
                }
        except (OSError, json.JSONDecodeError, TypeError):
            pass
        return {
            "sha": "unknown",
            "branch": "unknown",
            "dirty": False,
            "source": "unknown",
            "error": f"Git和{metadata_path.name}均不可用：{type(exc).__name__}",
        }


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_reviews(path: str | Path | None) -> dict[str, dict[str, Any]]:
    if not path or not Path(path).exists():
        return {}
    payload = load_json(path)
    reviews = payload.get("reviews") or []
    return {str(item["case_id"]): item for item in reviews}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="运行药研罗盘离线量化评测")
    parser.add_argument("--output-dir", required=True, help="结果输出目录；不得位于data或config事实目录")
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST_PATH), help="pilot manifest路径")
    parser.add_argument("--cases", default=str(DEFAULT_CASES_PATH), help="pilot JSONL用例路径")
    parser.add_argument(
        "--baselines",
        default=",".join(BASELINE_NAMES),
        help="逗号分隔的基线名称",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    baseline_names = [item.strip() for item in args.baselines.split(",") if item.strip()]
    result = run_benchmark(
        output_dir=args.output_dir,
        manifest_path=args.manifest,
        cases_path=args.cases,
        baseline_names=baseline_names,
    )
    summary = {
        "benchmark_stage": result["run_manifest"]["benchmark_stage"],
        "case_count": result["run_manifest"]["case_count"],
        "result_count": result["run_manifest"]["result_count"],
        "actual_data_version": result["run_manifest"]["actual_data_version"],
        "output_files": result["output_files"],
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
