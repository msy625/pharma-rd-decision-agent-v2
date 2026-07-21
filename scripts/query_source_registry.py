#!/usr/bin/env python3
"""CLI wrapper for the source registry query service."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from deepinsight.core.source_registry_service import (  # noqa: E402
    DEFAULT_ALIASES_PATH,
    DEFAULT_CSV_PATH,
    SourceRegistryError,
    SourceRegistryService,
    company_text,
    contains,
    expand_drug_terms,
    is_latest_row,
    is_nsclc_comparison_record,
    norm,
    row_status,
    row_title,
)


CSV_PATH = DEFAULT_CSV_PATH
ALIASES_PATH = DEFAULT_ALIASES_PATH

DISPLAY_FIELDS = ["source_id", "company", "source_type", "title", "status", "url"]


def load_registry(path: Path = CSV_PATH) -> list[dict[str, str]]:
    return SourceRegistryService(csv_path=path).load_rows()


def load_aliases(path: Path = ALIASES_PATH) -> dict[str, list[str]]:
    return SourceRegistryService(aliases_path=path).load_aliases()


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
    service = SourceRegistryService()
    service._rows = list(rows)
    service._fieldnames = list(service._rows[0].keys()) if service._rows else []
    service._alias_map = aliases or service.load_aliases()
    return service.query(
        source_id=source_id,
        company=company,
        trial_id=trial_id,
        pmid=pmid,
        study_name=study_name,
        drug=drug,
        source_type=source_type,
        status=status,
        text=text,
        latest_only=latest_only,
        normalized=False,
    )


def summarize(rows: list[dict[str, str]]) -> dict[str, object]:
    service = SourceRegistryService()
    service._rows = rows
    service._fieldnames = list(rows[0].keys()) if rows else []
    return service.summary()


def to_output_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    output = []
    for row in rows:
        output.append(
            {
                "source_id": row.get("source_id", ""),
                "company": row.get("company_name") or row.get("company_cn") or row.get("company", ""),
                "source_type": row.get("source_type", ""),
                "title": row.get("study_name") or row.get("description_zh") or row_title(row),
                "status": row.get("study_status") or row.get("status") or row_status(row),
                "url": row.get("source_url") or row.get("url", ""),
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
        service = SourceRegistryService()
        if args.summary:
            summary = service.summary()
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

        matched = service.query(
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
            normalized=True,
        )
        if args.format == "json":
            print(json.dumps(to_output_rows(matched), ensure_ascii=False, indent=2))
        else:
            print_table(matched)
        return 0
    except SourceRegistryError as exc:
        print(f"query error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
