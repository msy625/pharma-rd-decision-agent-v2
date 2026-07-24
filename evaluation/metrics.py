"""Deterministic metrics for source, chain, citation, safety, and latency evaluation."""

from __future__ import annotations

import math
from collections import defaultdict
from statistics import mean, median
from typing import Any, Iterable


def retrieval_precision_at_k(actual: list[str], expected: list[str], k: int) -> float:
    prefix = actual[:k]
    if not prefix:
        return 0.0
    return len(set(prefix) & set(expected)) / len(prefix)


def retrieval_recall_at_k(actual: list[str], expected: list[str], k: int) -> float:
    gold = set(expected)
    if not gold:
        return 1.0 if not actual[:k] else 0.0
    return len(set(actual[:k]) & gold) / len(gold)


def set_precision(actual: Iterable[str], expected: Iterable[str]) -> float:
    actual_set = set(actual)
    expected_set = set(expected)
    if not actual_set:
        return 1.0 if not expected_set else 0.0
    return len(actual_set & expected_set) / len(actual_set)


def set_recall(actual: Iterable[str], expected: Iterable[str]) -> float:
    actual_set = set(actual)
    expected_set = set(expected)
    if not expected_set:
        return 1.0 if not actual_set else 0.0
    return len(actual_set & expected_set) / len(expected_set)


def f1_score(precision: float, recall: float) -> float:
    if precision + recall == 0:
        return 0.0
    return 2 * precision * recall / (precision + recall)


def set_f1(actual: Iterable[str], expected: Iterable[str]) -> float:
    return f1_score(set_precision(actual, expected), set_recall(actual, expected))


def exact_set_match(actual: Iterable[str], expected: Iterable[str]) -> float:
    return float(set(actual) == set(expected))


def citation_whitelist_compliance(citations: Iterable[str], allowed_source_ids: Iterable[str]) -> float:
    citation_list = list(citations)
    if not citation_list:
        return 1.0
    allowed = set(allowed_source_ids)
    return sum(1 for source_id in citation_list if source_id in allowed) / len(citation_list)


def zero_out_of_whitelist(citations: Iterable[str], allowed_source_ids: Iterable[str]) -> float:
    return float(not (set(citations) - set(allowed_source_ids)))


def percentile_nearest_rank(values: list[float], percentile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    rank = max(1, math.ceil(percentile * len(ordered)))
    return ordered[rank - 1]


def latency_summary(values: Iterable[float]) -> dict[str, float]:
    samples = [float(value) for value in values]
    if not samples:
        return {"mean_latency_ms": 0.0, "median_latency_ms": 0.0, "p95_latency_ms": 0.0}
    return {
        "mean_latency_ms": mean(samples),
        "median_latency_ms": median(samples),
        "p95_latency_ms": percentile_nearest_rank(samples, 0.95),
    }


def evaluate_match_rule(rule: dict[str, Any], result: dict[str, Any]) -> bool:
    actual = _field_value(result, rule["field_path"])
    expected = rule.get("expected")
    operator = rule["operator"]
    if operator == "exact":
        return actual == expected
    if operator == "casefold_exact":
        return _text(actual).casefold() == _text(expected).casefold()
    if operator == "contains":
        return _text(expected).casefold() in _text(actual).casefold()
    if operator == "contains_all":
        return all(_text(item).casefold() in _text(actual).casefold() for item in _as_list(expected))
    if operator == "contains_any":
        return any(_text(item).casefold() in _text(actual).casefold() for item in _as_list(expected))
    if operator == "set_equal":
        return set(_as_list(actual)) == set(_as_list(expected))
    if operator == "set_contains_all":
        return set(_as_list(expected)) <= set(_as_list(actual))
    raise ValueError(f"Unsupported operator: {operator}")


def evaluate_case(case: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    actual_sources = list(result.get("source_ids") or [])
    expected_sources = list(case["expected_source_ids"])
    actual_chains = list(result.get("chain_ids") or [])
    expected_chains = list(case["expected_chain_ids"])
    citations = list(result.get("citations") or [])
    k = int(case["retrieval_k"])

    source_precision = set_precision(actual_sources, expected_sources)
    source_recall = set_recall(actual_sources, expected_sources)
    chain_precision = set_precision(actual_chains, expected_chains)
    chain_recall = set_recall(actual_chains, expected_chains)

    fact_details = _evaluate_required_facts(case["required_facts"], result)
    limitation_details = _evaluate_rules(case["required_limitations"], result)
    forbidden_details = _evaluate_rules(case["forbidden_claims"], result)

    fact_coverage = _passed_rate(fact_details, default=1.0)
    limitation_coverage = _passed_rate(limitation_details, default=1.0)
    forbidden_trigger_rate = _passed_rate(forbidden_details, default=0.0)
    forbidden_source_hits = sorted(set(actual_sources) & set(case["forbidden_source_ids"]))
    unallowed_source_ids = sorted(set(actual_sources) - set(case["allowed_source_ids"]))

    citation_compliance = citation_whitelist_compliance(citations, case["allowed_source_ids"])
    zero_outside = zero_out_of_whitelist(citations, case["allowed_source_ids"])
    question_type_correct = float(result.get("question_type") == case["expected_question_type"])
    safety_category_correct = float(result.get("safety_category", "") == case["expected_safety_category"])
    refusal_correct = float(bool(result.get("refused")) == bool(case["expected_refusal"]))
    source_exact = exact_set_match(actual_sources, expected_sources)
    chain_exact = exact_set_match(actual_chains, expected_chains)
    latency_pass = float(float(result.get("latency_ms") or 0.0) <= float(case["latency_budget_ms"]))
    no_error = float(not result.get("error"))
    no_model = float(not result.get("used_llm"))

    hard_conditions = {
        "no_error": no_error,
        "question_type_correct": question_type_correct,
        "source_exact_match": source_exact,
        "no_forbidden_source": float(not forbidden_source_hits),
        "no_unallowed_source": float(not unallowed_source_ids),
        "chain_exact_match": chain_exact,
        "citation_whitelist_compliance": float(citation_compliance == 1.0),
        "zero_out_of_whitelist": zero_outside,
        "required_fact_coverage": float(fact_coverage == 1.0),
        "no_forbidden_claim": float(forbidden_trigger_rate == 0.0),
        "required_limitation_coverage": float(limitation_coverage == 1.0),
        "refusal_correct": refusal_correct,
        "safety_category_correct": safety_category_correct,
        "no_model_used": no_model,
        "latency_within_budget": latency_pass,
    }
    overall_pass = float(all(value == 1.0 for value in hard_conditions.values()))

    regulatory_hard_pass = None
    if case["category"] == "regulatory_status":
        regulatory_hard_pass = overall_pass

    insufficiency_applicable = case["category"] == "evidence_gap" or "insufficient_data" in case["tags"]
    insufficiency_pass = None
    if insufficiency_applicable:
        insufficiency_pass = float(
            limitation_coverage == 1.0
            and forbidden_trigger_rate == 0.0
            and not unallowed_source_ids
            and question_type_correct == 1.0
        )

    safety_applicable = bool(case["expected_safety_category"])
    refusal_applicable = bool(case["expected_refusal"])
    failure_reasons = [name for name, passed in hard_conditions.items() if passed != 1.0]

    return {
        "retrieval_precision_at_k": retrieval_precision_at_k(actual_sources, expected_sources, k),
        "retrieval_recall_at_k": retrieval_recall_at_k(actual_sources, expected_sources, k),
        "source_precision": source_precision,
        "source_recall": source_recall,
        "source_f1": f1_score(source_precision, source_recall),
        "source_exact_match": source_exact,
        "chain_exact_match": chain_exact,
        "chain_f1": f1_score(chain_precision, chain_recall),
        "citation_whitelist_compliance": citation_compliance,
        "zero_out_of_whitelist": zero_outside,
        "required_fact_coverage": fact_coverage,
        "forbidden_claim_trigger_rate": forbidden_trigger_rate,
        "required_limitation_coverage": limitation_coverage,
        "regulatory_hard_pass": regulatory_hard_pass,
        "evidence_insufficiency_pass": insufficiency_pass,
        "safety_classification_correct": safety_category_correct if safety_applicable else None,
        "prohibited_refusal_correct": refusal_correct if refusal_applicable else None,
        "question_type_correct": question_type_correct,
        "latency_within_budget": latency_pass,
        "overall_pass": overall_pass,
        "manual_review_pending": bool(
            case["manual_review_required"]
            or any(detail["manual_review_required"] for detail in [*fact_details, *limitation_details, *forbidden_details])
        ),
        "forbidden_source_hits": forbidden_source_hits,
        "unallowed_source_ids": unallowed_source_ids,
        "fact_details": fact_details,
        "limitation_details": limitation_details,
        "forbidden_claim_details": forbidden_details,
        "failure_reasons": failure_reasons,
    }


def result_status(
    baseline: str,
    category: str,
    metrics: dict[str, Any],
    manual_review: dict[str, Any] | None = None,
) -> str:
    """Return one mutually-exclusive case status without inflating pass rates."""
    if baseline != "grounded_qa_local" and category != "source_search":
        return "unsupported"
    if metrics.get("manual_review_pending"):
        verdict = str((manual_review or {}).get("verdict") or "manual_review")
        if verdict in {"passed", "failed"}:
            return verdict if metrics.get("overall_pass") else "failed"
        return "manual_review"
    return "passed" if metrics.get("overall_pass") else "failed"


def aggregate_results(records: list[dict[str, Any]]) -> dict[str, Any]:
    by_baseline: dict[str, list[dict[str, Any]]] = defaultdict(list)
    by_baseline_category: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        by_baseline[record["baseline"]].append(record)
        by_baseline_category[(record["baseline"], record["category"])].append(record)

    baseline_summary = []
    latency_rows = []
    category_summary = []
    for baseline, items in sorted(by_baseline.items()):
        summary = _aggregate_group(items)
        category_rates = [
            _aggregate_group(category_items)["overall_pass_rate"]
            for (item_baseline, _), category_items in by_baseline_category.items()
            if item_baseline == baseline
        ]
        summary["baseline"] = baseline
        summary["macro_category_pass_rate"] = mean(category_rates) if category_rates else 0.0
        baseline_summary.append(summary)
        latency_rows.append({"baseline": baseline, **latency_summary(item["result"]["latency_ms"] for item in items)})

    for (baseline, category), items in sorted(by_baseline_category.items()):
        category_summary.append({"baseline": baseline, "category": category, **_aggregate_group(items)})

    return {
        "baseline_summary": baseline_summary,
        "category_summary": category_summary,
        "latency_summary": latency_rows,
    }


def _aggregate_group(records: list[dict[str, Any]]) -> dict[str, Any]:
    metric_names = [
        "retrieval_precision_at_k",
        "retrieval_recall_at_k",
        "source_precision",
        "source_recall",
        "source_f1",
        "source_exact_match",
        "chain_exact_match",
        "chain_f1",
        "zero_out_of_whitelist",
        "question_type_correct",
        "latency_within_budget",
        "overall_pass",
    ]
    statuses = [record.get("status") or ("passed" if record["metrics"]["overall_pass"] else "failed") for record in records]
    counts = {name: statuses.count(name) for name in ["passed", "failed", "not_applicable", "unsupported", "manual_review"]}
    covered = counts["passed"] + counts["failed"] + counts["manual_review"]
    applicable = counts["passed"] + counts["failed"]
    summary: dict[str, Any] = {
        "case_count": len(records),
        **{f"{name}_count": count for name, count in counts.items()},
        "coverage": covered / len(records) if records else 0.0,
        "applicable_pass_rate": counts["passed"] / applicable if applicable else None,
        "end_to_end_pass_rate": counts["passed"] / len(records) if records else 0.0,
    }
    for name in metric_names:
        values = [float(record["metrics"][name]) for record in records]
        output_name = "overall_pass_rate" if name == "overall_pass" else name
        summary[output_name] = mean(values) if values else 0.0

    citation_count = sum(len(record["result"]["citations"]) for record in records)
    allowed_citation_count = sum(
        len(set(record["result"]["citations"]) & set(record["allowed_source_ids"])) for record in records
    )
    summary["citation_whitelist_compliance"] = (
        allowed_citation_count / citation_count if citation_count else 1.0
    )

    fact_details = [detail for record in records for detail in record["metrics"]["fact_details"]]
    summary["required_fact_coverage"] = _passed_rate(fact_details, default=1.0)
    limitation_details = [detail for record in records for detail in record["metrics"]["limitation_details"]]
    summary["required_limitation_coverage"] = _passed_rate(limitation_details, default=1.0)
    forbidden_applicable = [
        record for record in records if record["metrics"]["forbidden_claim_details"]
    ]
    summary["forbidden_claim_trigger_rate"] = (
        sum(
            any(detail["passed"] for detail in record["metrics"]["forbidden_claim_details"])
            for record in forbidden_applicable
        )
        / len(forbidden_applicable)
        if forbidden_applicable
        else 0.0
    )

    optional_metrics = {
        "regulatory_hard_pass": "regulatory_hard_pass_rate",
        "evidence_insufficiency_pass": "evidence_insufficiency_correct_rate",
        "safety_classification_correct": "safety_classification_accuracy",
        "prohibited_refusal_correct": "prohibited_refusal_rate",
    }
    for source_name, output_name in optional_metrics.items():
        values = [record["metrics"][source_name] for record in records if record["metrics"][source_name] is not None]
        summary[output_name] = mean(float(value) for value in values) if values else None
    summary["manual_review_pending_count"] = sum(bool(record["metrics"]["manual_review_pending"]) for record in records)
    return summary


def _evaluate_required_facts(rules: list[dict[str, Any]], result: dict[str, Any]) -> list[dict[str, Any]]:
    details = []
    citations = set(result.get("citations") or [])
    for rule in rules:
        automatic_match = evaluate_match_rule(rule, result)
        supporting_ids = set(rule.get("supporting_source_ids") or [])
        citation_support = not supporting_ids or bool(citations & supporting_ids)
        details.append(
            {
                "rule_id": rule["rule_id"],
                "automatic_match": automatic_match,
                "citation_support": citation_support,
                "passed": automatic_match and citation_support,
                "manual_review_required": bool(rule["manual_review_required"]),
            }
        )
    return details


def _evaluate_rules(rules: list[dict[str, Any]], result: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "rule_id": rule["rule_id"],
            "passed": evaluate_match_rule(rule, result),
            "manual_review_required": bool(rule["manual_review_required"]),
        }
        for rule in rules
    ]


def _passed_rate(details: list[dict[str, Any]], default: float) -> float:
    if not details:
        return default
    return sum(bool(detail["passed"]) for detail in details) / len(details)


def _field_value(result: dict[str, Any], field_path: str) -> Any:
    if field_path == "response_text":
        return "\n".join([str(result.get("answer") or ""), *[str(item) for item in result.get("limitations") or []]])
    value: Any = result
    for part in field_path.split("."):
        if not isinstance(value, dict):
            return None
        value = value.get(part)
    return value


def _text(value: Any) -> str:
    if isinstance(value, list):
        return "\n".join(str(item) for item in value)
    return str(value or "")


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else [value]
