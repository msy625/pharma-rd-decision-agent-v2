"""Writers for machine-readable and human-readable benchmark results."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Iterable


OUTPUT_FILENAMES = [
    "case_results.jsonl",
    "metric_details.csv",
    "category_summary.csv",
    "baseline_comparison.csv",
    "latency_percentiles.csv",
    "failures.json",
    "report.md",
    "run_manifest.json",
]


def write_evaluation_outputs(
    output_dir: str | Path,
    *,
    run_manifest: dict[str, Any],
    manifest: dict[str, Any],
    records: list[dict[str, Any]],
    aggregates: dict[str, Any],
) -> list[Path]:
    target = Path(output_dir)
    target.mkdir(parents=True, exist_ok=True)

    _write_jsonl(target / "case_results.jsonl", records)
    _write_metric_details(target / "metric_details.csv", records)
    _write_csv(target / "category_summary.csv", aggregates["category_summary"])
    _write_csv(target / "baseline_comparison.csv", aggregates["baseline_summary"])
    _write_csv(target / "latency_percentiles.csv", aggregates["latency_summary"])
    _write_json(target / "failures.json", _failure_rows(records))
    (target / "report.md").write_text(
        build_markdown_report(run_manifest, manifest, records, aggregates), encoding="utf-8"
    )
    _write_json(target / "run_manifest.json", run_manifest)
    return [target / filename for filename in OUTPUT_FILENAMES]


def build_markdown_report(
    run_manifest: dict[str, Any],
    manifest: dict[str, Any],
    records: list[dict[str, Any]],
    aggregates: dict[str, Any],
) -> str:
    latency_by_baseline = {row["baseline"]: row for row in aggregates["latency_summary"]}
    lines = [
        "# 药研罗盘离线量化评测报告",
        "",
        ("> 本报告是12题pilot试运行结果，用于验证评测框架并暴露当前能力缺口，不是最终业务成绩。"
         if run_manifest["benchmark_stage"] == "pilot"
         else f"> 本报告是{run_manifest['case_count']}题{run_manifest['benchmark_stage']}离线评测结果。"),
        "",
        "## 运行信息",
        "",
        f"- Benchmark阶段：`{run_manifest['benchmark_stage']}`",
        f"- 用例数：{run_manifest['case_count']}",
        f"- 数据版本：`{run_manifest['actual_data_version']}`",
        f"- 事实快照起点：`{run_manifest['facts_snapshot_commit']}`",
        f"- 实际Git SHA：`{run_manifest['git_sha']}`",
        f"- 工作区dirty：`{str(run_manifest['git_dirty']).lower()}`",
        f"- Python：`{run_manifest['python_version']}`",
        f"- 开始时间：`{run_manifest['started_at']}`",
        f"- 完成时间：`{run_manifest['completed_at']}`",
        "",
        "## 基线汇总",
        "",
        "| 基线 | 状态通过题数 | 覆盖率 | 适用题通过率 | 端到端通过率 | Source F1 | Chain完全匹配 | 必要事实覆盖 | Median延迟(ms) | P95延迟(ms) |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in aggregates["baseline_summary"]:
        latency = latency_by_baseline[row["baseline"]]
        pass_count = sum(
            int(record["status"] == "passed")
            for record in records
            if record["baseline"] == row["baseline"]
        )
        lines.append(
            "| {baseline} | {passed}/{count} | {coverage:.1%} | {applicable} | {e2e:.1%} | {source_f1:.3f} | {chain:.3f} | "
            "{facts:.3f} | {median:.3f} | {p95:.3f} |".format(
                baseline=row["baseline"],
                passed=pass_count,
                count=row["case_count"],
                coverage=row["coverage"],
                applicable=(f"{row['applicable_pass_rate']:.1%}" if row["applicable_pass_rate"] is not None else "N/A"),
                e2e=row["end_to_end_pass_rate"],
                source_f1=row["source_f1"],
                chain=row["chain_exact_match"],
                facts=row["required_fact_coverage"],
                median=latency["median_latency_ms"],
                p95=latency["p95_latency_ms"],
            )
        )

    lines.extend(
        [
            "",
            "## 按题型汇总",
            "",
            "| 基线 | 题型 | 题数 | 自动通过率 | Source F1 | Chain F1 |",
            "|---|---|---:|---:|---:|---:|",
        ]
    )
    for row in aggregates["category_summary"]:
        lines.append(
            f"| {row['baseline']} | {row['category']} | {row['case_count']} | "
            f"{row['overall_pass_rate']:.1%} | {row['source_f1']:.3f} | {row['chain_f1']:.3f} |"
        )

    failures = _failure_rows(records)
    lines.extend(["", "## 失败案例", ""])
    if not failures:
        lines.append("- 无自动失败案例。")
    else:
        for item in failures:
            reasons = "、".join(item["failure_reasons"])
            lines.append(f"- `{item['baseline']}` / `{item['case_id']}`：{reasons}")

    manual_cases = sorted(
        {
            record["case_id"]
            for record in records
            if record["baseline"] == "grounded_qa_local" and record["metrics"]["manual_review_pending"]
        }
    )
    lines.extend(["", "## 人工复核边界", ""])
    lines.append(
        "- 需要人工复核的pilot用例：" + ("、".join(f"`{case_id}`" for case_id in manual_cases) or "无") + "。"
    )
    lines.append("- 自动字符串匹配只能验证明确短语，不能替代对监管时间口径和误导性暗示的人工判断。")

    lines.extend(["", "## 适用限制", ""])
    for limitation in manifest["limitations"]:
        lines.append(f"- {limitation}")
    lines.extend(
        [
            "- 自动测试通过率仅说明评测工具实现正确，不能写作业务准确率。",
            "- 本次服务层延迟不包含浏览器渲染、网络传输和现场设备差异。",
            "",
        ]
    )
    return "\n".join(lines)


def _write_metric_details(path: Path, records: list[dict[str, Any]]) -> None:
    rows = []
    for record in records:
        metrics = record["metrics"]
        rows.append(
            {
                "baseline": record["baseline"],
                "case_id": record["case_id"],
                "split": record["split"],
                "category": record["category"],
                "target": record["target"],
                "status": record["status"],
                "retrieval_precision_at_k": metrics["retrieval_precision_at_k"],
                "retrieval_recall_at_k": metrics["retrieval_recall_at_k"],
                "source_precision": metrics["source_precision"],
                "source_recall": metrics["source_recall"],
                "source_f1": metrics["source_f1"],
                "source_exact_match": metrics["source_exact_match"],
                "chain_exact_match": metrics["chain_exact_match"],
                "chain_f1": metrics["chain_f1"],
                "citation_whitelist_compliance": metrics["citation_whitelist_compliance"],
                "zero_out_of_whitelist": metrics["zero_out_of_whitelist"],
                "required_fact_coverage": metrics["required_fact_coverage"],
                "forbidden_claim_trigger_rate": metrics["forbidden_claim_trigger_rate"],
                "required_limitation_coverage": metrics["required_limitation_coverage"],
                "regulatory_hard_pass": metrics["regulatory_hard_pass"],
                "evidence_insufficiency_pass": metrics["evidence_insufficiency_pass"],
                "safety_classification_correct": metrics["safety_classification_correct"],
                "prohibited_refusal_correct": metrics["prohibited_refusal_correct"],
                "question_type_correct": metrics["question_type_correct"],
                "latency_ms": record["result"]["latency_ms"],
                "latency_within_budget": metrics["latency_within_budget"],
                "overall_pass": metrics["overall_pass"],
                "manual_review_pending": metrics["manual_review_pending"],
                "failure_reasons": json.dumps(metrics["failure_reasons"], ensure_ascii=False),
            }
        )
    _write_csv(path, rows)


def _failure_rows(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "baseline": record["baseline"],
            "case_id": record["case_id"],
            "category": record["category"],
            "failure_reasons": record["metrics"]["failure_reasons"],
            "source_ids": record["result"]["source_ids"],
            "chain_ids": record["result"]["chain_ids"],
            "citations": record["result"]["citations"],
            "error": record["result"]["error"],
            "manual_review_pending": record["metrics"]["manual_review_pending"],
            "status": record["status"],
        }
        for record in records
        if not record["metrics"]["overall_pass"]
    ]


def _write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def _write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: _csv_value(row.get(key)) for key in fieldnames})


def _csv_value(value: Any) -> Any:
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return value
