#!/usr/bin/env python3
"""Remove individual-investigator entries that were harvested as organizations.

``ClinicalTrials.gov``'s ``leadSponsor.name`` is free text. Some registered studies
are investigator-initiated, so a person's name was written into
``organizations.csv`` as if it were an organisation, which then showed up in the
direction explorer's sponsor filter.

This script removes exactly the names listed in
``config/individual_investigator_names.json`` - an explicit, human-reviewed list.
It deliberately does NOT use a name-shape heuristic: such a heuristic also flags
real organisations that simply lack an English suffix (Kaiser Permanente, Pierre
Fabre Dermo Cosmetique, UMC Utrecht, Universidad Rey Juan Carlos, ...).

What it cleans up
-----------------
* ``organizations.csv``        - drops the matching rows
* ``organization_aliases.csv`` - drops their aliases
* ``relations.csv``            - drops ``source_about_org`` edges pointing at them
* ``studies.csv``              - clears ``sponsor_org_id`` on affected studies

``facts.csv`` rows with ``predicate=lead_sponsor`` are intentionally kept: they
record what the registry actually states about the study, which remains true even
though the person is no longer modelled as an organisation.

Usage
-----
    python scripts/drop_individual_investigators.py --report
    python scripts/drop_individual_investigators.py
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_DIR = PROJECT_ROOT / "data" / "template"
CONFIG_PATH = PROJECT_ROOT / "config" / "individual_investigator_names.json"

ORG_TABLE = "organizations"
ALIAS_TABLE = "organization_aliases"
STUDY_TABLE = "studies"
RELATION_TABLE = "relations"

ORG_KEY = "organization_id"
ALIAS_KEY = "alias_id"
STUDY_KEY = "study_id"
RELATION_KEY = "relation_id"


def read_table(name: str) -> tuple[list[str], list[dict[str, str]]]:
    with (TEMPLATE_DIR / f"{name}.csv").open("r", encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        return list(reader.fieldnames or []), [dict(row) for row in reader]


def write_table(name: str, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    with (TEMPLATE_DIR / f"{name}.csv").open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--report", action="store_true", help="show what would be removed, write nothing")
    args = parser.parse_args(argv)

    names = set(json.loads(CONFIG_PATH.read_text(encoding="utf-8"))["individuals"])

    org_fields, orgs = read_table(ORG_TABLE)
    alias_fields, aliases = read_table(ALIAS_TABLE)
    study_fields, studies = read_table(STUDY_TABLE)
    relation_fields, relations = read_table(RELATION_TABLE)

    doomed_ids = {
        row[ORG_KEY] for row in orgs if row.get("canonical_name", "").strip() in names
    }
    matched_names = {row["canonical_name"].strip() for row in orgs if row[ORG_KEY] in doomed_ids}
    unmatched = sorted(names - matched_names)

    removed_orgs = [row for row in orgs if row[ORG_KEY] in doomed_ids]
    kept_orgs = [row for row in orgs if row[ORG_KEY] not in doomed_ids]
    removed_aliases = [row for row in aliases if row.get("organization_id", "") in doomed_ids]
    kept_aliases = [row for row in aliases if row.get("organization_id", "") not in doomed_ids]
    removed_relations = [
        row
        for row in relations
        if row.get("relation_type") == "source_about_org" and row.get("object_id", "") in doomed_ids
    ]
    kept_relations = [row for row in relations if row not in removed_relations]
    touched_studies = [row for row in studies if row.get("sponsor_org_id", "") in doomed_ids]
    for row in touched_studies:
        row["sponsor_org_id"] = ""

    print(f"names listed              : {len(names)}")
    print(f"matched organizations     : {len(removed_orgs)}")
    print(f"aliases removed           : {len(removed_aliases)}")
    print(f"source_about_org relations removed : {len(removed_relations)}")
    print(f"studies with sponsor cleared       : {len(touched_studies)}")
    if unmatched:
        print(f"listed but not present in data ({len(unmatched)}): {unmatched}")

    if args.report:
        print("\n--- organizations that would be removed ---")
        for row in sorted(removed_orgs, key=lambda r: r["canonical_name"]):
            print(f"  {row[ORG_KEY]:<58} {row['canonical_name']}")
        print("\nreport only: nothing written")
        return 0

    if not removed_orgs:
        print("\nnothing to remove: data is already clean")
        return 0

    if kept_orgs != orgs:
        write_table(ORG_TABLE, org_fields, kept_orgs)
    if kept_aliases != aliases:
        write_table(ALIAS_TABLE, alias_fields, kept_aliases)
    if kept_relations != relations:
        write_table(RELATION_TABLE, relation_fields, kept_relations)
    if touched_studies:
        write_table(STUDY_TABLE, study_fields, studies)

    print("\nfiles updated: organizations, organization_aliases, relations, studies")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
