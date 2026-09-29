#!/usr/bin/env python3
"""Validate the research-direction dataset in ``data/template/``.

Checks that
* the catalog defines 6 stages and 20 directions;
* every direction carries between ``--min`` and ``--max`` selected records;
* the curated website corpus has the requested source and organization size;
* every harvested row keeps a real upstream identifier and a direct URL;
* primary keys are unique and referential links resolve.

Exit code 0 means the dataset is consistent. This validator never touches the
network: it only reads the files that ``scripts/harvest_direction_data.py`` wrote.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
from collections import Counter
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_DIR = PROJECT_ROOT / "data" / "template"
CATALOG_PATH = PROJECT_ROOT / "config" / "direction_catalog.json"
CONTRACT_PATH = TEMPLATE_DIR / "website_data_contract.json"

PRIMARY_KEYS = {
    "domains": "domain_id",
    "organizations": "organization_id",
    "organization_aliases": "alias_id",
    "assets": "asset_id",
    "asset_aliases": "alias_id",
    "indications": "indication_id",
    "studies": "study_id",
    "study_identifiers": "study_identifier_id",
    "publications": "publication_id",
    "regulatory_events": "regulatory_event_id",
    "market_events": "market_event_id",
    "sources": "source_id",
    "facts": "fact_id",
    "relations": "relation_id",
}

CTG_SOURCE_TYPE = "CLINICAL_TRIAL_REGISTRY"
PUBMED_SOURCE_TYPE = "PUBMED_ARTICLE"
NCT_PATTERN = re.compile(r"^NCT\d{8}$")
PMID_PATTERN = re.compile(r"^\d{6,9}$")


def load_table(name: str) -> list[dict[str, str]]:
    path = TEMPLATE_DIR / f"{name}.csv"
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as fh:
        return [dict(row) for row in csv.DictReader(fh)]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--min", type=int, default=40, help="minimum records per direction (default 40)")
    parser.add_argument("--max", type=int, default=110, help="maximum records per direction (default 110)")
    parser.add_argument("--source-min", type=int, default=1200, help="minimum eligible sources (default 1200)")
    parser.add_argument("--source-max", type=int, default=1500, help="maximum eligible sources (default 1500)")
    parser.add_argument("--organization-min", type=int, default=150, help="minimum organizations after deduplication (default 150)")
    parser.add_argument("--organization-max", type=int, default=300, help="maximum organizations (default 300)")
    args = parser.parse_args(argv)

    errors: list[str] = []
    catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    stages = catalog["stages"]
    directions = [d for stage in stages for d in stage["directions"]]

    if len(stages) != 6:
        errors.append(f"catalog must define 6 stages, found {len(stages)}")
    if len(directions) != 20:
        errors.append(f"catalog must define 20 directions, found {len(directions)}")

    tables = {name: load_table(name) for name in PRIMARY_KEYS}

    # ---- frozen website data contract ------------------------------------
    try:
        contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f"website data contract is unreadable: {exc}")
        contract = {}
    try:
        manifest = json.loads((TEMPLATE_DIR / "data_manifest.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f"data manifest is unreadable: {exc}")
        manifest = {}

    expected_counts = contract.get("expected_counts", {})
    if manifest.get("dataset") != contract.get("dataset"):
        errors.append("data_manifest.json and website_data_contract.json declare different datasets")
    for name, expected in expected_counts.items():
        actual = len(tables.get(name, []))
        if actual != expected:
            errors.append(f"contract count mismatch for {name}: expected {expected}, got {actual}")
        if manifest.get("counts", {}).get(name) != expected:
            errors.append(f"manifest count mismatch for {name}: expected {expected}, got {manifest.get('counts', {}).get(name)}")
    for filename, expected_hash in contract.get("table_sha256", {}).items():
        path = TEMPLATE_DIR / filename
        actual_hash = hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else "missing"
        if actual_hash != expected_hash:
            errors.append(f"contract hash mismatch for {filename}")

    if not args.source_min <= len(tables["sources"]) <= args.source_max:
        errors.append(
            f"sources has {len(tables['sources'])} rows, outside the "
            f"{args.source_min}-{args.source_max} curated range"
        )
    if not args.organization_min <= len(tables["organizations"]) <= args.organization_max:
        errors.append(
            f"organizations has {len(tables['organizations'])} rows, outside the "
            f"{args.organization_min}-{args.organization_max} curated range"
        )

    # ---- primary key uniqueness -------------------------------------------
    for name, key in PRIMARY_KEYS.items():
        rows = tables[name]
        if not rows:
            continue
        fieldnames = set(rows[0].keys())
        if key not in fieldnames:
            errors.append(f"{name}.csv is missing primary key column {key}")
            continue
        counts = Counter(row.get(key, "") for row in rows)
        duplicates = [value for value, count in counts.items() if count > 1]
        if duplicates:
            errors.append(f"{name}.csv has {len(duplicates)} duplicate {key} value(s), e.g. {duplicates[:3]}")
        blanks = counts.get("", 0)
        if blanks:
            errors.append(f"{name}.csv has {blanks} row(s) with an empty {key}")

    # ---- per-direction record counts --------------------------------------
    studies_by_domain = Counter(row.get("domain_id", "") for row in tables["studies"])
    pubs_by_domain = Counter(row.get("domain_id", "") for row in tables["publications"])

    per_direction: dict[str, dict[str, int]] = {}
    for direction in directions:
        domain_id = direction["direction_id"]
        total = studies_by_domain.get(domain_id, 0) + pubs_by_domain.get(domain_id, 0)
        per_direction[direction["direction_key"]] = {
            "studies": studies_by_domain.get(domain_id, 0),
            "publications": pubs_by_domain.get(domain_id, 0),
            "total": total,
        }
        if total < args.min:
            errors.append(f"{direction['name_zh']} ({domain_id}) has {total} records, below the {args.min} minimum")
        if total > args.max:
            errors.append(f"{direction['name_zh']} ({domain_id}) has {total} records, above the {args.max} maximum")

    # ---- sources: identifiers + urls --------------------------------------
    sources = tables["sources"]
    ctg_sources = [row for row in sources if row.get("source_type") == CTG_SOURCE_TYPE]
    pubmed_sources = [row for row in sources if row.get("source_type") == PUBMED_SOURCE_TYPE]

    for row in sources:
        source_id = row.get("source_id", "")
        url = row.get("url", "")
        if not url.startswith(("http://", "https://")):
            errors.append(f"{source_id}: url must start with http(s)://, got {url!r}")
        if not row.get("verification_status"):
            errors.append(f"{source_id}: verification_status is empty")
        if not row.get("verified_at"):
            errors.append(f"{source_id}: verified_at is empty")

    source_status_counts = Counter(row.get("verification_status", "") for row in sources)
    if dict(source_status_counts) != contract.get("expected_source_status_counts", {}):
        errors.append("source verification-status counts do not match the website data contract")
    relation_status_counts = Counter(row.get("relation_status", "") for row in tables["relations"])
    if dict(relation_status_counts) != contract.get("expected_relation_status_counts", {}):
        errors.append("relation-status counts do not match the website data contract")

    for row in ctg_sources:
        locator = row.get("source_locator", "")
        if not NCT_PATTERN.match(locator):
            errors.append(f"{row.get('source_id')}: ClinicalTrials.gov locator {locator!r} is not an NCT id")
        if f"/{locator}" not in row.get("url", ""):
            errors.append(f"{row.get('source_id')}: url does not contain its NCT id {locator}")

    for row in pubmed_sources:
        locator = row.get("source_locator", "").replace("PMID ", "").strip()
        if not PMID_PATTERN.match(locator):
            errors.append(f"{row.get('source_id')}: PubMed locator {locator!r} is not a PMID")
        if f"/{locator}/" not in row.get("url", ""):
            errors.append(f"{row.get('source_id')}: url does not contain its PMID {locator}")

    # ---- referential integrity -------------------------------------------
    source_ids = {row.get("source_id", "") for row in sources}
    study_ids = {row.get("study_id", "") for row in tables["studies"]}
    publication_ids = {row.get("publication_id", "") for row in tables["publications"]}
    domain_ids = {row.get("domain_id", "") for row in tables["domains"]}
    org_ids = {row.get("organization_id", "") for row in tables["organizations"]}
    asset_ids = {row.get("asset_id", "") for row in tables["assets"]}
    indication_ids = {row.get("indication_id", "") for row in tables["indications"]}

    for row in tables["studies"]:
        if row.get("domain_id") not in domain_ids:
            errors.append(f"{row.get('study_id')}: unknown domain_id {row.get('domain_id')!r}")
        if row.get("sponsor_org_id") and row["sponsor_org_id"] not in org_ids:
            errors.append(f"{row.get('study_id')}: unknown sponsor_org_id {row['sponsor_org_id']!r}")
        if row.get("primary_indication_id") and row["primary_indication_id"] not in indication_ids:
            errors.append(f"{row.get('study_id')}: unknown primary_indication_id {row['primary_indication_id']!r}")

    for row in tables["study_identifiers"]:
        if row.get("study_id") not in study_ids:
            errors.append(f"{row.get('study_identifier_id')}: unknown study_id {row.get('study_id')!r}")
        if row.get("source_id") and row["source_id"] not in source_ids:
            errors.append(f"{row.get('study_identifier_id')}: unknown source_id {row['source_id']!r}")

    for row in tables["publications"]:
        if row.get("domain_id") not in domain_ids:
            errors.append(f"{row.get('publication_id')}: unknown domain_id {row.get('domain_id')!r}")
        if row.get("source_id") and row["source_id"] not in source_ids:
            errors.append(f"{row.get('publication_id')}: unknown source_id {row['source_id']!r}")

    for row in tables["facts"]:
        if row.get("source_id") and row["source_id"] not in source_ids:
            errors.append(f"{row.get('fact_id')}: unknown source_id {row['source_id']!r}")

    for row in tables["relations"]:
        if row.get("source_id") and row["source_id"] not in source_ids:
            errors.append(f"{row.get('relation_id')}: unknown source_id {row['source_id']!r}")
        target = row.get("object_id", "")
        if target.startswith("ASSET_") and target not in asset_ids:
            errors.append(f"{row.get('relation_id')}: unknown asset {target!r}")

    for row in tables["organizations"]:
        if not row.get("canonical_name"):
            errors.append(f"{row.get('organization_id')}: canonical_name is empty")

    # ---- report -----------------------------------------------------------
    print(f"direction catalog : {len(stages)} stages / {len(directions)} directions")
    print(
        f"harvested records : {sum(v['total'] for v in per_direction.values())} "
        f"({sum(v['studies'] for v in per_direction.values())} trials + "
        f"{sum(v['publications'] for v in per_direction.values())} publications)"
    )
    width = max(len(d["name_zh"]) for d in directions)
    for stage in stages:
        print(f"  {stage['stage_name']}（{stage.get('stage_title', '')}）— {stage['goal']}")
        for direction in stage["directions"]:
            stats = per_direction[direction["direction_key"]]
            print(
                f"    {direction['name_zh']:<{width}}  "
                f"{stats['total']:>4} 条  (试验 {stats['studies']:>3} / 论文 {stats['publications']:>3})"
            )
    print("table sizes       : " + ", ".join(f"{name}={len(rows)}" for name, rows in tables.items()))

    if errors:
        print(f"\nvalidation FAILED with {len(errors)} problem(s):", file=sys.stderr)
        for error in errors[:60]:
            print(f"  - {error}", file=sys.stderr)
        if len(errors) > 60:
            print(f"  ... and {len(errors) - 60} more", file=sys.stderr)
        return 1
    print("\nvalidation passed: curated counts are in range and all links resolve.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
