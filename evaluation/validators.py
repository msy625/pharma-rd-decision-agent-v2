"""Validation helpers for benchmark manifests, cases, and output locations."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Iterable


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SCHEMA_PATH = PROJECT_ROOT / "evaluation" / "schema" / "case.schema.json"

SOURCE_ID_RE = re.compile(r"^[AHB][0-9]{3}$")
CHAIN_ID_RE = re.compile(r"^(trial:[A-Za-z0-9-]+|regulatory:[a-z0-9][a-z0-9-]*)$")
COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
DATA_VERSION_RE = re.compile(r"^sha256:[0-9a-f]{16}$")


class EvaluationValidationError(ValueError):
    """Raised when a benchmark manifest or case file is invalid."""


class DataVersionMismatchError(EvaluationValidationError):
    """Raised before execution when the facts snapshot does not match."""


def load_json(path: str | Path) -> dict[str, Any]:
    file_path = Path(path)
    data = json.loads(file_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise EvaluationValidationError(f"JSON root must be an object: {file_path.name}")
    return data


def load_cases(path: str | Path) -> list[dict[str, Any]]:
    file_path = Path(path)
    cases: list[dict[str, Any]] = []
    for line_number, raw_line in enumerate(file_path.read_text(encoding="utf-8").splitlines(), start=1):
        if not raw_line.strip():
            continue
        try:
            item = json.loads(raw_line)
        except json.JSONDecodeError as exc:
            raise EvaluationValidationError(
                f"Invalid JSONL at {file_path.name}:{line_number}: {exc.msg}"
            ) from exc
        if not isinstance(item, dict):
            raise EvaluationValidationError(f"Case at {file_path.name}:{line_number} must be an object")
        cases.append(item)
    return cases


def validate_manifest(manifest: dict[str, Any]) -> None:
    required = {
        "schema_version",
        "benchmark_name",
        "benchmark_stage",
        "case_count",
        "expected_data_version",
        "facts_snapshot_commit",
        "case_file",
        "description",
        "limitations",
    }
    missing = sorted(required - set(manifest))
    if missing:
        raise EvaluationValidationError(f"Manifest missing fields: {', '.join(missing)}")
    if manifest["benchmark_stage"] != "pilot":
        raise EvaluationValidationError("benchmark_stage must be pilot")
    if not isinstance(manifest["case_count"], int) or manifest["case_count"] <= 0:
        raise EvaluationValidationError("case_count must be a positive integer")
    if not DATA_VERSION_RE.fullmatch(str(manifest["expected_data_version"])):
        raise EvaluationValidationError("expected_data_version must use sha256:<16 hex> format")
    if not COMMIT_RE.fullmatch(str(manifest["facts_snapshot_commit"])):
        raise EvaluationValidationError("facts_snapshot_commit must be a full 40-character Git SHA")
    if not isinstance(manifest["limitations"], list) or not all(
        isinstance(item, str) and item for item in manifest["limitations"]
    ):
        raise EvaluationValidationError("manifest limitations must be a non-empty string list")


def validate_case(case: dict[str, Any], schema: dict[str, Any] | None = None) -> None:
    schema = schema or load_json(DEFAULT_SCHEMA_PATH)
    required = set(schema.get("required") or [])
    properties = set((schema.get("properties") or {}).keys())
    missing = sorted(required - set(case))
    extra = sorted(set(case) - properties)
    if missing:
        raise EvaluationValidationError(f"{case.get('case_id', '<unknown>')} missing fields: {', '.join(missing)}")
    if extra:
        raise EvaluationValidationError(f"{case.get('case_id', '<unknown>')} has unsupported fields: {', '.join(extra)}")

    case_id = str(case.get("case_id") or "")
    if not re.fullmatch(r"^[A-Z]+-[0-9]{3}$", case_id):
        raise EvaluationValidationError(f"Invalid case_id: {case_id}")
    if case.get("split") != "pilot":
        raise EvaluationValidationError(f"{case_id} split must be pilot")

    for field in ["question", "expected_question_type", "category", "target", "notes"]:
        if not isinstance(case.get(field), str):
            raise EvaluationValidationError(f"{case_id} field {field} must be a string")
    if not case["question"].strip():
        raise EvaluationValidationError(f"{case_id} question must not be empty")

    _validate_enum(case_id, "category", case["category"], schema)
    _validate_enum(case_id, "target", case["target"], schema)
    _validate_enum(case_id, "expected_question_type", case["expected_question_type"], schema)
    _validate_request(case_id, case["request"], schema)

    for field in ["expected_source_ids", "allowed_source_ids", "forbidden_source_ids"]:
        _validate_id_list(case_id, field, case[field], SOURCE_ID_RE)
    _validate_id_list(case_id, "expected_chain_ids", case["expected_chain_ids"], CHAIN_ID_RE)

    expected_ids = set(case["expected_source_ids"])
    allowed_ids = set(case["allowed_source_ids"])
    forbidden_ids = set(case["forbidden_source_ids"])
    if not expected_ids <= allowed_ids:
        raise EvaluationValidationError(f"{case_id} expected_source_ids must be a subset of allowed_source_ids")
    if allowed_ids & forbidden_ids:
        raise EvaluationValidationError(f"{case_id} allowed and forbidden source IDs overlap")

    for field in ["required_facts", "forbidden_claims", "required_limitations"]:
        rules = case[field]
        if not isinstance(rules, list):
            raise EvaluationValidationError(f"{case_id} field {field} must be a list")
        for rule in rules:
            _validate_match_rule(case_id, field, rule)

    for field in ["expected_refusal", "manual_review_required"]:
        if not isinstance(case[field], bool):
            raise EvaluationValidationError(f"{case_id} field {field} must be boolean")
    if not isinstance(case["expected_safety_category"], str):
        raise EvaluationValidationError(f"{case_id} expected_safety_category must be a string")
    if not isinstance(case["retrieval_k"], int) or case["retrieval_k"] < 1:
        raise EvaluationValidationError(f"{case_id} retrieval_k must be a positive integer")
    if not isinstance(case["latency_budget_ms"], (int, float)) or case["latency_budget_ms"] <= 0:
        raise EvaluationValidationError(f"{case_id} latency_budget_ms must be positive")
    if (
        not isinstance(case["tags"], list)
        or not all(isinstance(item, str) and item for item in case["tags"])
        or len(case["tags"]) != len(set(case["tags"]))
    ):
        raise EvaluationValidationError(f"{case_id} tags must be a unique list")


def validate_suite(
    manifest: dict[str, Any],
    cases: list[dict[str, Any]],
    *,
    known_source_ids: Iterable[str] | None = None,
    known_chain_ids: Iterable[str] | None = None,
) -> None:
    validate_manifest(manifest)
    schema = load_json(DEFAULT_SCHEMA_PATH)
    for case in cases:
        validate_case(case, schema)
    case_ids = [case["case_id"] for case in cases]
    if len(case_ids) != len(set(case_ids)):
        raise EvaluationValidationError("case_id values must be unique")
    if len(cases) != manifest["case_count"]:
        raise EvaluationValidationError(
            f"Manifest case_count={manifest['case_count']} does not match JSONL count={len(cases)}"
        )
    if any(case["split"] != "pilot" for case in cases):
        raise EvaluationValidationError("All pilot cases must use split=pilot")

    if known_source_ids is not None:
        known = set(known_source_ids)
        referenced = {
            source_id
            for case in cases
            for field in ["expected_source_ids", "allowed_source_ids", "forbidden_source_ids"]
            for source_id in case[field]
        }
        referenced.update(
            source_id
            for case in cases
            for field in ["required_facts", "forbidden_claims", "required_limitations"]
            for rule in case[field]
            for source_id in rule["supporting_source_ids"]
        )
        missing_sources = sorted(referenced - known)
        if missing_sources:
            raise EvaluationValidationError(f"Cases reference missing sources: {', '.join(missing_sources)}")

    if known_chain_ids is not None:
        known = set(known_chain_ids)
        referenced = {chain_id for case in cases for chain_id in case["expected_chain_ids"]}
        missing_chains = sorted(referenced - known)
        if missing_chains:
            raise EvaluationValidationError(f"Cases reference missing chains: {', '.join(missing_chains)}")


def assert_data_version(expected: str, actual: str) -> None:
    if expected != actual:
        raise DataVersionMismatchError(f"Data version mismatch: expected {expected}, got {actual}")


def ensure_safe_output_directory(path: str | Path) -> Path:
    output_path = Path(path).expanduser().resolve()
    protected = [PROJECT_ROOT / "data", PROJECT_ROOT / "config"]
    for root in protected:
        root = root.resolve()
        if output_path == root or root in output_path.parents:
            raise EvaluationValidationError(f"Output directory must not be inside protected facts directory: {root.name}")
    return output_path


def _validate_enum(case_id: str, field: str, value: Any, schema: dict[str, Any]) -> None:
    allowed = ((schema.get("properties") or {}).get(field) or {}).get("enum") or []
    if value not in allowed:
        raise EvaluationValidationError(f"{case_id} field {field} has unsupported value: {value}")


def _validate_request(case_id: str, request: Any, schema: dict[str, Any]) -> None:
    if not isinstance(request, dict):
        raise EvaluationValidationError(f"{case_id} request must be an object")
    expected_fields = {"query_mode", "query_value", "keyword_queries"}
    if set(request) != expected_fields:
        raise EvaluationValidationError(f"{case_id} request fields must be {sorted(expected_fields)}")
    request_schema = ((schema.get("properties") or {}).get("request") or {}).get("properties") or {}
    allowed_modes = (request_schema.get("query_mode") or {}).get("enum") or []
    if request["query_mode"] not in allowed_modes:
        raise EvaluationValidationError(f"{case_id} has unsupported query_mode: {request['query_mode']}")
    if not isinstance(request["query_value"], (str, list)):
        raise EvaluationValidationError(f"{case_id} query_value must be a string or string list")
    if isinstance(request["query_value"], list) and not all(isinstance(item, str) for item in request["query_value"]):
        raise EvaluationValidationError(f"{case_id} query_value list must contain strings")
    if not isinstance(request["keyword_queries"], list) or not request["keyword_queries"] or not all(
        isinstance(item, str) and item for item in request["keyword_queries"]
    ):
        raise EvaluationValidationError(f"{case_id} keyword_queries must be a non-empty string list")


def _validate_id_list(case_id: str, field: str, value: Any, pattern: re.Pattern[str]) -> None:
    if not isinstance(value, list) or len(value) != len(set(value)):
        raise EvaluationValidationError(f"{case_id} field {field} must be a unique list")
    invalid = [item for item in value if not isinstance(item, str) or not pattern.fullmatch(item)]
    if invalid:
        raise EvaluationValidationError(f"{case_id} field {field} has invalid IDs: {invalid}")


def _validate_match_rule(case_id: str, field: str, rule: Any) -> None:
    required = {
        "rule_id",
        "field_path",
        "operator",
        "expected",
        "supporting_source_ids",
        "manual_review_required",
    }
    if not isinstance(rule, dict) or set(rule) != required:
        raise EvaluationValidationError(f"{case_id} {field} rules must contain exactly {sorted(required)}")
    if not str(rule["rule_id"]).strip() or not str(rule["field_path"]).strip():
        raise EvaluationValidationError(f"{case_id} {field} rule identifiers must not be empty")
    allowed_operators = {
        "exact",
        "casefold_exact",
        "contains",
        "contains_all",
        "contains_any",
        "set_equal",
        "set_contains_all",
    }
    if rule["operator"] not in allowed_operators:
        raise EvaluationValidationError(f"{case_id} {field} has unsupported operator: {rule['operator']}")
    _validate_id_list(case_id, f"{field}.{rule['rule_id']}.supporting_source_ids", rule["supporting_source_ids"], SOURCE_ID_RE)
    if not isinstance(rule["manual_review_required"], bool):
        raise EvaluationValidationError(f"{case_id} {field} manual_review_required must be boolean")
    if field == "required_facts" and rule["field_path"] in {"answer", "response_text"}:
        if not rule["supporting_source_ids"]:
            raise EvaluationValidationError(
                f"{case_id} text fact {rule['rule_id']} must declare supporting_source_ids"
            )
