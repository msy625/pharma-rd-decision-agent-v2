#!/usr/bin/env python3
"""Apply the curated Chinese organization-name table to ``data/template/``.

Only organizations listed in ``config/organization_names_zh.json`` are renamed, and
only where an authoritative Chinese name actually exists. Anything not covered
keeps its original English name: this script never machine-translates and never
invents a Chinese name.

What it changes
---------------
* ``organizations.csv``  -> ``display_name`` becomes ``中文名（English short name）``
  (``canonical_name`` is left untouched: it is the join key used by facts/relations)
* ``organization_aliases.csv`` -> adds one ``language=zh``, ``alias_type=display_name``
  alias holding the plain Chinese name. The existing English alias is kept.

The script is idempotent and only rewrites files whose content actually changed.

Usage
-----
    python scripts/localize_organization_names.py
    python scripts/localize_organization_names.py --report-unmatched
    python scripts/localize_organization_names.py --report-unmatched --unmatched-limit 200
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_DIR = PROJECT_ROOT / "data" / "template"
CONFIG_PATH = PROJECT_ROOT / "config" / "organization_names_zh.json"

ORG_TABLE = "organizations"
ALIAS_TABLE = "organization_aliases"
HARVEST_PREFIX = "ORG_HARVEST_"


def read_table(name: str) -> tuple[list[str], list[dict[str, str]]]:
    path = TEMPLATE_DIR / f"{name}.csv"
    with path.open("r", encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        return list(reader.fieldnames or []), [dict(row) for row in reader]


def write_table(name: str, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    path = TEMPLATE_DIR / f"{name}.csv"
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def load_rules() -> list[dict[str, str]]:
    data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    rules = []
    for rule in data["rules"]:
        rules.append({**rule, "_regex": re.compile(rule["match"])})
    return rules


def match_rule(name: str, rules: list[dict[str, str]]) -> dict[str, str] | None:
    for rule in rules:
        if rule["_regex"].search(name):
            return rule
    return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--report-unmatched", action="store_true", help="list harvested organizations with no Chinese name")
    parser.add_argument("--unmatched-limit", type=int, default=120, help="how many unmatched names to print")
    parser.add_argument("--dry-run", action="store_true", help="report what would change, write nothing")
    args = parser.parse_args(argv)

    rules = load_rules()
    org_fields, orgs = read_table(ORG_TABLE)
    alias_fields, aliases = read_table(ALIAS_TABLE)
    alias_ids = {row.get("alias_id", "") for row in aliases}

    matched: list[tuple[str, str, str]] = []
    unmatched: list[str] = []
    new_aliases: list[dict[str, str]] = []

    for org in orgs:
        org_id = org.get("organization_id", "")
        canonical = org.get("canonical_name", "")
        # Curated (non-harvest) rows already carry an authoritative display name.
        if not org_id.startswith(HARVEST_PREFIX):
            continue
        rule = match_rule(canonical, rules)
        if not rule:
            unmatched.append(canonical)
            continue

        display = f"{rule['zh']}（{rule['short_en']}）"
        if org.get("display_name") != display:
            org["display_name"] = display
        matched.append((org_id, canonical, rule["zh"]))

        alias_id = f"ALIAS_{org_id}_ZH"
        if alias_id not in alias_ids:
            new_aliases.append(
                {
                    "alias_id": alias_id,
                    "organization_id": org_id,
                    "alias": rule["zh"],
                    "language": "zh",
                    "alias_type": "display_name",
                    "valid_from": "",
                    "valid_to": "",
                    "source_id": "",
                    "notes": f"中文名对照：{rule['id']}；来源 config/organization_names_zh.json。",
                }
            )

    print(f"harvested organizations : {sum(1 for o in orgs if o.get('organization_id','').startswith(HARVEST_PREFIX))}")
    print(f"matched with a Chinese name : {len(matched)}")
    print(f"left as English (no authoritative Chinese name) : {len(unmatched)}")
    print(f"new zh aliases to add : {len(new_aliases)}")

    if args.report_unmatched:
        print(f"\n--- unmatched (first {args.unmatched_limit}) ---")
        for name in sorted(unmatched)[: args.unmatched_limit]:
            print("  " + name)

    if args.dry_run:
        print("\ndry-run: nothing written")
        return 0

    changed = 0
    if matched:
        merged_aliases = aliases + new_aliases
        _, current_orgs = read_table(ORG_TABLE)
        if orgs != current_orgs:
            write_table(ORG_TABLE, org_fields, orgs)
            changed += 1
        if merged_aliases != aliases:
            write_table(ALIAS_TABLE, alias_fields, merged_aliases)
            changed += 1

    print(f"\nfiles written: {changed}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
