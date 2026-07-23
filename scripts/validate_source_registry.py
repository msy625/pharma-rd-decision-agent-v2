#!/usr/bin/env python3
"""Validate the source registry and its required verified data sets."""

from __future__ import annotations

import csv
import sys
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CSV_PATH = ROOT / "data" / "source_registry.csv"

REQUIRED_FIELDS = [
    "source_id",
    "company",
    "company_cn",
    "registry_id",
    "parent_trial_id",
    "pmid",
    "study_name",
    "drug_names",
    "study_status",
    "verification_status",
    "source_type",
    "url",
    "verified_at",
]


def load_rows(path: Path = CSV_PATH) -> tuple[list[str], list[dict[str, str]], list[str]]:
    errors: list[str] = []
    try:
        with path.open("r", encoding="utf-8", newline="") as fh:
            raw_rows = list(csv.reader(fh))
    except UnicodeDecodeError as exc:
        return [], [], [f"CSV is not valid UTF-8: {exc}"]
    except OSError as exc:
        return [], [], [f"Cannot read CSV: {path}: {exc}"]

    if not raw_rows:
        return [], [], ["CSV is empty"]

    header = raw_rows[0]
    expected_len = len(header)
    for line_no, row in enumerate(raw_rows[1:], start=2):
        if len(row) != expected_len:
            errors.append(
                f"line {line_no}: field count {len(row)} != header count {expected_len}"
            )

    with path.open("r", encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        rows = list(reader)
        fieldnames = reader.fieldnames or []

    for field in REQUIRED_FIELDS:
        if field not in fieldnames:
            errors.append(f"missing required field: {field}")

    return fieldnames, rows, errors


def row_by_id(rows: list[dict[str, str]], source_id: str) -> dict[str, str] | None:
    for row in rows:
        if row.get("source_id") == source_id:
            return row
    return None


def require(errors: list[str], condition: bool, message: str) -> None:
    if not condition:
        errors.append(message)


def validate(path: Path = CSV_PATH) -> list[str]:
    _fieldnames, rows, errors = load_rows(path)
    if errors:
        return errors

    ids = [row.get("source_id", "") for row in rows]
    id_counts = Counter(ids)

    for index, row in enumerate(rows, start=2):
        sid = row.get("source_id", "")
        require(errors, bool(sid), f"line {index}: source_id is empty")
        if sid and id_counts[sid] > 1:
            errors.append(f"{sid}: duplicate source_id")

        url = row.get("url", "")
        require(
            errors,
            url.startswith(("http://", "https://")),
            f"{sid or 'line ' + str(index)}: url must start with http:// or https://",
        )
        require(
            errors,
            bool(row.get("verification_status", "")),
            f"{sid}: verification_status is empty",
        )

        source_type = row.get("source_type", "")
        registry_id = row.get("registry_id", "")
        pmid = row.get("pmid", "")
        if source_type == "ClinicalTrials.gov":
            require(
                errors,
                registry_id.startswith("NCT"),
                f"{sid}: ClinicalTrials.gov record must have NCT registry_id",
            )
        if source_type == "PubMed":
            require(errors, bool(pmid), f"{sid}: PubMed record must have pmid")

    expected_h = {f"H{i:03d}" for i in range(1, 16)}
    expected_b = {f"B{i:03d}" for i in range(1, 17)}
    expected_a = {f"A{i:03d}" for i in range(1, 9)}
    id_set = set(ids)
    require(errors, expected_h.issubset(id_set), f"missing H ids: {sorted(expected_h - id_set)}")
    require(errors, expected_b.issubset(id_set), f"missing B ids: {sorted(expected_b - id_set)}")
    require(errors, expected_a.issubset(id_set), f"missing A ids: {sorted(expected_a - id_set)}")
    require(errors, len(rows) >= 39, f"total source count must be at least 39, got {len(rows)}")

    company_counts = Counter(row.get("company_cn") or row.get("company") for row in rows)
    require(errors, company_counts["恒瑞医药"] == 15, f"恒瑞医药 count must be 15, got {company_counts['恒瑞医药']}")
    require(errors, company_counts["百济神州"] == 16, f"百济神州 count must be 16, got {company_counts['百济神州']}")
    require(errors, company_counts["阿斯利康"] >= 8, f"阿斯利康 count must be at least 8, got {company_counts['阿斯利康']}")

    for sid in ["B006", "B007"]:
        row = row_by_id(rows, sid)
        require(errors, row is not None and row.get("parent_trial_id") == "NCT03663205", f"{sid}: parent_trial_id must be NCT03663205")
    for sid in ["B008", "B009"]:
        row = row_by_id(rows, sid)
        require(errors, row is not None and row.get("parent_trial_id") == "NCT03594747", f"{sid}: parent_trial_id must be NCT03594747")
    for sid in ["B011", "B012", "B013"]:
        row = row_by_id(rows, sid)
        require(errors, row is not None and row.get("parent_trial_id") == "NCT04379635", f"{sid}: parent_trial_id must be NCT04379635")

    h006 = row_by_id(rows, "H006")
    require(errors, h006 is not None and h006.get("study_status") == "Terminated", "H006/NCT04619433: study_status must be Terminated")

    for sid in ["B012", "B013"]:
        row = row_by_id(rows, sid)
        require(errors, row is not None and row.get("study_status") == "Active, not recruiting", f"{sid}: study_status must be Active, not recruiting")

    b015 = row_by_id(rows, "B015")
    require(errors, b015 is not None and b015.get("authorisation_status") == "欧盟正式授权", "B015: authorisation_status must be 欧盟正式授权")

    b016 = row_by_id(rows, "B016")
    require(errors, b016 is not None and b016.get("regulatory_event_type") == "CHMP positive opinion", "B016: regulatory_event_type must be CHMP positive opinion")
    require(errors, b016 is not None and b016.get("authorisation_status", "") != "欧盟正式授权", "B016: must not be marked as formal authorisation")

    return errors


def main() -> int:
    errors = validate(CSV_PATH)
    if errors:
        print("source_registry validation failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1
    _fields, rows, _errors = load_rows()
    print(f"source_registry validation passed: {len(rows)} verified sources across required data sets.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
