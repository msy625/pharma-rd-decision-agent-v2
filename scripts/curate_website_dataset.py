#!/usr/bin/env python3
"""Curate the canonical template into the smaller website root dataset.

Selection policy:
* retain organizations with a Chinese display name first, then the most
  connected organizations, for a target of 225;
* retain their linked clinical studies and the newest 20 publications per
  disease direction;
* retain clean manually reviewed records;
* exclude a source when it has no confirmed relation or any unresolved
  relation, even if it otherwise has a valid URL.

The script rewrites ``data/template`` only with ``--apply``.  It is deliberately
deterministic so a future refresh can reproduce the same curation policy.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter, defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "data" / "template"
TARGET_ORGANIZATIONS = 225
PUBLICATIONS_PER_DIRECTION = 20
CHINESE = re.compile(r"[\u3400-\u9fff]")
CONFIRMED = "confirmed"
MANUAL_STATUSES = {"verified", "partially_verified"}
STUDY_RELATIONS = {"source_supports", "source_describes_study"}
ORG_RELATIONS = {"source_about", "source_about_org"}


def load(name: str) -> list[dict[str, str]]:
    with (TEMPLATE / f"{name}.csv").open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write(name: str, rows: list[dict[str, str]], fields: list[str]) -> None:
    with (TEMPLATE / f"{name}.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def headers(name: str) -> list[str]:
    with (TEMPLATE / f"{name}.csv").open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle).fieldnames or [])


def is_clean_source(source_id: str, source_relations: dict[str, list[dict[str, str]]]) -> bool:
    rows = source_relations[source_id]
    return bool(rows) and all(row.get("relation_status") == CONFIRMED for row in rows)


def build_selection(tables: dict[str, list[dict[str, str]]]) -> tuple[dict[str, set[str]], dict[str, list[dict[str, str]]]]:
    sources = {row["source_id"]: row for row in tables["sources"]}
    organizations = {row["organization_id"]: row for row in tables["organizations"]}
    studies = {row["study_id"]: row for row in tables["studies"]}
    relations_by_source: dict[str, list[dict[str, str]]] = defaultdict(list)
    source_studies: dict[str, set[str]] = defaultdict(set)
    source_organizations: dict[str, set[str]] = defaultdict(set)
    study_sources: dict[str, set[str]] = defaultdict(set)
    publications_by_domain: dict[str, list[dict[str, str]]] = defaultdict(list)

    for relation in tables["relations"]:
        source_id = relation.get("source_id", "")
        if source_id:
            relations_by_source[source_id].append(relation)
        if relation.get("relation_status") != CONFIRMED:
            continue
        if relation.get("relation_type") in STUDY_RELATIONS:
            source_studies[source_id].add(relation.get("object_id", ""))
            study_sources[relation.get("object_id", "")].add(source_id)
        if relation.get("relation_type") in ORG_RELATIONS:
            source_organizations[source_id].add(relation.get("object_id", ""))
    for publication in tables["publications"]:
        publications_by_domain[publication.get("domain_id", "")].append(publication)

    organization_score: Counter[str] = Counter()
    for study in studies.values():
        if study.get("sponsor_org_id"):
            organization_score[study["sponsor_org_id"]] += 3
    for org_ids in source_organizations.values():
        for org_id in org_ids:
            organization_score[org_id] += 1

    selected_orgs = {
        org_id
        for org_id, organization in organizations.items()
        if CHINESE.search(organization.get("display_name", ""))
    }
    selected_orgs.update({"ORG_HENGRUI", "ORG_BEONE", "ORG_ASTRAZENECA"})
    for org_id, _ in organization_score.most_common():
        if len(selected_orgs) >= TARGET_ORGANIZATIONS:
            break
        selected_orgs.add(org_id)

    selected_studies = {
        study_id for study_id, study in studies.items() if study.get("sponsor_org_id") in selected_orgs
    }
    selected_sources = {
        source_id for study_id in selected_studies for source_id in study_sources.get(study_id, set())
    }
    selected_sources.update(
        source_id
        for source_id, source in sources.items()
        if source.get("verification_status") in MANUAL_STATUSES and is_clean_source(source_id, relations_by_source)
    )
    for publications in publications_by_domain.values():
        for publication in sorted(
            publications,
            key=lambda row: (row.get("publication_date", ""), row.get("publication_id", "")),
            reverse=True,
        )[:PUBLICATIONS_PER_DIRECTION]:
            if publication.get("source_id"):
                selected_sources.add(publication["source_id"])

    selected_sources = {
        source_id for source_id in selected_sources if source_id in sources and is_clean_source(source_id, relations_by_source)
    }
    selected_studies.update(
        study_id for source_id in selected_sources for study_id in source_studies.get(source_id, set()) if study_id in studies
    )
    selected_studies.update(
        publication.get("study_id", "")
        for publication in tables["publications"]
        if publication.get("source_id") in selected_sources and publication.get("study_id") in studies
    )

    selected_relations = [
        relation
        for relation in tables["relations"]
        if relation.get("source_id") in selected_sources and relation.get("relation_status") == CONFIRMED
    ]
    selected_orgs = {
        org_id
        for org_id in selected_orgs
        if org_id in organizations
    }
    selected_orgs.update(
        study.get("sponsor_org_id", "") for study_id, study in studies.items()
        if study_id in selected_studies and study.get("sponsor_org_id") in organizations
    )
    selected_orgs.update(
        relation.get("object_id", "") for relation in selected_relations
        if relation.get("relation_type") in ORG_RELATIONS and relation.get("object_id") in organizations
    )
    selected_orgs.update(
        event.get("holder_org_id", "") for event in tables["regulatory_events"]
        if event.get("source_id") in selected_sources and event.get("holder_org_id") in organizations
    )
    if not 200 <= len(selected_orgs) <= 300:
        raise ValueError(f"Organization selection left requested range: {len(selected_orgs)}")

    selected_assets = {
        relation.get("object_id", "") for relation in selected_relations if relation.get("object_id", "").startswith("ASSET_")
    }
    selected_assets.update(
        study.get("primary_asset_id", "") for study_id, study in studies.items()
        if study_id in selected_studies and study.get("primary_asset_id")
    )
    selected_indications = {
        relation.get("object_id", "") for relation in selected_relations if relation.get("object_id", "").startswith("IND_")
    }
    selected_indications.update(
        study.get("primary_indication_id", "") for study_id, study in studies.items()
        if study_id in selected_studies and study.get("primary_indication_id")
    )
    selected_publications = {
        row.get("publication_id", "") for row in tables["publications"] if row.get("source_id") in selected_sources
    }
    selected_domains = {
        row.get("domain_id", "")
        for table_name in ("sources", "studies", "publications", "assets", "indications")
        for row in tables[table_name]
        if (
            (table_name == "sources" and row.get("source_id") in selected_sources)
            or (table_name == "studies" and row.get("study_id") in selected_studies)
            or (table_name == "publications" and row.get("publication_id") in selected_publications)
            or (table_name == "assets" and row.get("asset_id") in selected_assets)
            or (table_name == "indications" and row.get("indication_id") in selected_indications)
        )
    }
    domains = {row["domain_id"]: row for row in tables["domains"]}
    selected_domains.update(
        domains[domain_id].get("parent_domain_id", "") for domain_id in list(selected_domains) if domain_id in domains
    )

    selection = {
        "sources": selected_sources,
        "organizations": selected_orgs,
        "assets": selected_assets,
        "indications": selected_indications,
        "studies": selected_studies,
        "publications": selected_publications,
        "domains": selected_domains - {""},
    }
    return selection, {"relations": selected_relations}


def curated_tables(tables: dict[str, list[dict[str, str]]], selection: dict[str, set[str]], helpers: dict[str, list[dict[str, str]]]) -> dict[str, list[dict[str, str]]]:
    rows = {
        "domains": [row for row in tables["domains"] if row["domain_id"] in selection["domains"]],
        "organizations": [row for row in tables["organizations"] if row["organization_id"] in selection["organizations"]],
        "assets": [row for row in tables["assets"] if row["asset_id"] in selection["assets"]],
        "indications": [row for row in tables["indications"] if row["indication_id"] in selection["indications"]],
        "studies": [row for row in tables["studies"] if row["study_id"] in selection["studies"]],
        "publications": [row for row in tables["publications"] if row["publication_id"] in selection["publications"]],
        "sources": [row for row in tables["sources"] if row["source_id"] in selection["sources"]],
    }
    rows["organization_aliases"] = [row for row in tables["organization_aliases"] if row["organization_id"] in selection["organizations"]]
    rows["asset_aliases"] = [row for row in tables["asset_aliases"] if row["asset_id"] in selection["assets"]]
    rows["study_identifiers"] = [
        row for row in tables["study_identifiers"]
        if row["study_id"] in selection["studies"] and (not row.get("source_id") or row["source_id"] in selection["sources"])
    ]
    rows["regulatory_events"] = [row for row in tables["regulatory_events"] if row["source_id"] in selection["sources"]]
    rows["market_events"] = []
    rows["facts"] = [row for row in tables["facts"] if not row.get("source_id") or row["source_id"] in selection["sources"]]
    rows["relations"] = helpers["relations"]
    return rows


def update_manifest(rows: dict[str, list[dict[str, str]]]) -> dict[str, object]:
    path = TEMPLATE / "data_manifest.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    manifest["dataset"] = "website_curated_normalized_v1"
    manifest["created_at"] = "2026-09-28"
    manifest["counts"] = {name: len(value) for name, value in rows.items()}
    manifest["limitations"] = [
        "Website root dataset is a curated subset of the prior normalized corpus.",
        "Sources with no confirmed relation or any unresolved relation are excluded from website display.",
        "Organizations prioritize existing Chinese display names, then observed source and study connectivity.",
        "api_harvested records remain unreviewed and are not evidence of efficacy, success probability, or investment value.",
    ]
    manifest["curation"] = {
        "source_target_range": [1200, 1500],
        "organization_target_range": [200, 300],
        "organization_target": TARGET_ORGANIZATIONS,
        "publication_per_direction": PUBLICATIONS_PER_DIRECTION,
        "eligibility": "valid source URL, declared verification status, and only confirmed explicit relations",
    }
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="rewrite data/template with the curated root dataset")
    args = parser.parse_args()
    table_names = [path.stem for path in sorted(TEMPLATE.glob("*.csv"))]
    tables = {name: load(name) for name in table_names}
    selection, helpers = build_selection(tables)
    rows = curated_tables(tables, selection, helpers)
    source_count = len(rows["sources"])
    if not 1200 <= source_count <= 1500:
        raise ValueError(f"Source selection left requested range: {source_count}")
    print("curated counts:", ", ".join(f"{name}={len(rows[name])}" for name in table_names))
    print("selected sources by verification:", dict(Counter(row["verification_status"] for row in rows["sources"])))
    print("selected Chinese organization names:", sum(bool(CHINESE.search(row.get("display_name", ""))) for row in rows["organizations"]))
    if not args.apply:
        print("dry run only; pass --apply to rewrite data/template")
        return 0
    for name in table_names:
        write(name, rows[name], headers(name))
    (TEMPLATE / "data_manifest.json").write_text(
        json.dumps(update_manifest(rows), ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print("data/template rewritten as the curated website root dataset")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
