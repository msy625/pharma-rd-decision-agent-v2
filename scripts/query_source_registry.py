#!/usr/bin/env python3
"""Minimal CLI query tool for the frozen source registry."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parents[1]
CSV_PATH = ROOT / "data" / "source_registry.csv"
ALIASES_PATH = ROOT / "config" / "entity_aliases.json"

DISPLAY_FIELDS = [
    "source_id",
    "company",
    "source_type",
    "title",
    "status",
    "url",
]

SEARCH_FIELDS = [
    "source_id",
    "company",
    "company_cn",
    "company_current_name",
    "company_former_name",
    "company_display_name",
    "sponsor_original",
    "source_type",
    "registry_id",
    "parent_trial_id",
    "pmid",
    "study_name",
    "drug_names",
    "study_status",
    "verification_status",
    "authorisation_status",
    "regulatory_event_type",
    "original_title",
    "original_title_en",
    "normalized_title_zh",
    "population",
    "intervention",
    "regimen_detail",
    "biomarker_requirements",
    "notes",
    "evidence_relation",
    "scope_limitation",
]


class RegistryError(Exception):
    """Raised for invalid registry or configuration state."""


def norm(value: object) -> str:
    return str(value or "").casefold()


def contains(value: object, needle: str) -> bool:
    return norm(needle) in norm(value)


def load_registry(path: Path = CSV_PATH) -> list[dict[str, str]]:
    try:
        with path.open("r", encoding="utf-8", newline="") as fh:
            reader = csv.DictReader(fh)
            rows = list(reader)
            fields = reader.fieldnames or []
    except UnicodeDecodeError as exc:
        raise RegistryError(f"CSV is not valid UTF-8: {exc}") from exc
    except OSError as exc:
        raise RegistryError(f"Cannot read CSV: {path}: {exc}") from exc

    required = ["source_id", "company", "source_type", "url"]
    missing = [field for field in required if field not in fields]
    if missing:
        raise RegistryError(f"CSV missing required fields: {', '.join(missing)}")
    return rows


def load_aliases(path: Path = ALIASES_PATH) -> dict[str, list[str]]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise RegistryError(f"Alias config is not valid JSON: {path}: {exc}") from exc

    alias_map: dict[str, list[str]] = {}
    for entity in data.get("entities", []):
        aliases = [str(item) for item in entity.get("aliases", []) if str(item)]
        for alias in aliases:
            alias_map[norm(alias)] = aliases
    return alias_map


def expand_drug_terms(term: str, aliases: dict[str, list[str]]) -> list[str]:
    term_key = norm(term)
    if not term_key:
        return []
    expanded = aliases.get(term_key)
    if expanded:
        return expanded
    for alias_key, alias_group in aliases.items():
        if term_key in alias_key or alias_key in term_key:
            return alias_group
    return [term]


def row_title(row: dict[str, str]) -> str:
    return (
        row.get("study_name")
        or row.get("normalized_title_zh")
        or row.get("original_title")
        or row.get("original_title_en")
        or row.get("registry_id")
        or row.get("source_id")
        or ""
    )


def row_status(row: dict[str, str]) -> str:
    return (
        row.get("study_status")
        or row.get("authorisation_status")
        or row.get("regulatory_event_type")
        or row.get("verification_status")
        or ""
    )


def company_text(row: dict[str, str]) -> str:
    fields = [
        "company",
        "company_cn",
        "company_current_name",
        "company_former_name",
        "company_display_name",
        "sponsor_original",
    ]
    return " ".join(row.get(field, "") for field in fields)


def is_latest_row(row: dict[str, str]) -> bool:
    return norm(row.get("is_latest_evidence")) != "false"


def is_nsclc_comparison_record(row: dict[str, str]) -> bool:
    if row.get("source_id") == "B014":
        return False
    scope_text = row.get("scope_limitation", "") + row.get("notes", "")
    if "SCLC 项目不计入 NSCLC" in scope_text or "不要将 SCLC 项目计入" in scope_text:
        return False
    return "非小细胞肺癌" in row.get("disease", "") or "NSCLC" in row.get("disease", "")


def match_text(row: dict[str, str], text: str) -> bool:
    joined = " ".join(row.get(field, "") for field in SEARCH_FIELDS)
    return contains(joined, text)


def query_rows(
    rows: Iterable[dict[str, str]],
    *,
    source_id: str | None = None,
    company: str | None = None,
    trial_id: str | None = None,
    pmid: str | None = None,
    study_name: str | None = None,
    drug: str | None = None,
    source_type: str | None = None,
    status: str | None = None,
    text: str | None = None,
    latest_only: bool = False,
    aliases: dict[str, list[str]] | None = None,
) -> list[dict[str, str]]:
    aliases = aliases or {}
    drug_terms = expand_drug_terms(drug, aliases) if drug else []
    results: list[dict[str, str]] = []

    for row in rows:
        if latest_only and not is_latest_row(row):
            continue
        if source_id and not contains(row.get("source_id"), source_id):
            continue
        if company and not contains(company_text(row), company):
            continue
        if trial_id:
            trial_blob = " ".join(
                row.get(field, "")
                for field in ["registry_id", "parent_trial_id", "official_study_id", "china_trial_id", "notes"]
            )
            if not contains(trial_blob, trial_id):
                continue
        if pmid:
            pmid_blob = " ".join(row.get(field, "") for field in ["pmid", "registry_id", "url"])
            if not contains(pmid_blob, pmid):
                continue
        if study_name and not contains(
            " ".join(row.get(field, "") for field in ["study_name", "normalized_title_zh", "original_title", "original_title_en"]),
            study_name,
        ):
            continue
        if drug and not any(
            contains(
                " ".join(row.get(field, "") for field in ["drug_names", "intervention", "normalized_title_zh", "original_title", "notes"]),
                term,
            )
            for term in drug_terms
        ):
            continue
        if source_type and not contains(row.get("source_type"), source_type):
            continue
        if status:
            status_blob = " ".join(
                row.get(field, "")
                for field in ["study_status", "verification_status", "authorisation_status", "regulatory_event_type"]
            )
            if not contains(status_blob, status):
                continue
        if text and not match_text(row, text):
            continue
        results.append(row)
    return results


def summarize(rows: list[dict[str, str]]) -> dict[str, object]:
    company_counts = Counter(row.get("company_cn") or row.get("company") for row in rows)
    source_type_counts = Counter(row.get("source_type", "") for row in rows)
    beone_trials = sorted(
        {
            row.get("study_name")
            for row in rows
            if (row.get("company_cn") == "百济神州" and row.get("study_name", "").startswith("RATIONALE-"))
        }
    )
    return {
        "total_sources": len(rows),
        "company_counts": dict(company_counts),
        "source_type_counts": dict(source_type_counts),
        "beone_unique_nsclc_trials": beone_trials,
        "nsclc_comparison_records": sum(1 for row in rows if is_nsclc_comparison_record(row)),
    }


def to_output_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    output = []
    for row in rows:
        output.append(
            {
                "source_id": row.get("source_id", ""),
                "company": row.get("company_cn") or row.get("company", ""),
                "source_type": row.get("source_type", ""),
                "title": row_title(row),
                "status": row_status(row),
                "url": row.get("url", ""),
            }
        )
    return output


def print_table(rows: list[dict[str, str]]) -> None:
    output_rows = to_output_rows(rows)
    if not output_rows:
        print("No matching sources found.")
        return

    widths = {
        field: min(
            max(len(field), *(len(str(row.get(field, ""))) for row in output_rows)),
            48 if field == "title" else 28,
        )
        for field in DISPLAY_FIELDS
    }
    header = " | ".join(field.ljust(widths[field]) for field in DISPLAY_FIELDS)
    print(header)
    print("-+-".join("-" * widths[field] for field in DISPLAY_FIELDS))
    for row in output_rows:
        cells = []
        for field in DISPLAY_FIELDS:
            value = str(row.get(field, ""))
            if len(value) > widths[field]:
                value = value[: widths[field] - 1] + "…"
            cells.append(value.ljust(widths[field]))
        print(" | ".join(cells))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Query frozen pharma source registry.")
    parser.add_argument("--source-id")
    parser.add_argument("--company")
    parser.add_argument("--trial-id")
    parser.add_argument("--pmid")
    parser.add_argument("--study-name")
    parser.add_argument("--drug")
    parser.add_argument("--source-type")
    parser.add_argument("--status")
    parser.add_argument("--text")
    parser.add_argument("--latest-only", action="store_true")
    parser.add_argument("--format", choices=["table", "json"], default="table")
    parser.add_argument("--summary", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        rows = load_registry(CSV_PATH)
        aliases = load_aliases(ALIASES_PATH)
        if args.summary:
            summary = summarize(rows)
            if args.format == "json":
                print(json.dumps(summary, ensure_ascii=False, indent=2))
            else:
                print(f"Total sources: {summary['total_sources']}")
                print("Company counts:")
                for company, count in summary["company_counts"].items():
                    print(f"- {company}: {count}")
                print("Source type counts:")
                for source_type, count in summary["source_type_counts"].items():
                    print(f"- {source_type}: {count}")
                print("BeOne unique NSCLC trials: " + ", ".join(summary["beone_unique_nsclc_trials"]))
            return 0

        matched = query_rows(
            rows,
            source_id=args.source_id,
            company=args.company,
            trial_id=args.trial_id,
            pmid=args.pmid,
            study_name=args.study_name,
            drug=args.drug,
            source_type=args.source_type,
            status=args.status,
            text=args.text,
            latest_only=args.latest_only,
            aliases=aliases,
        )
        if args.format == "json":
            print(json.dumps(to_output_rows(matched), ensure_ascii=False, indent=2))
        else:
            print_table(matched)
        return 0
    except RegistryError as exc:
        print(f"query error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
