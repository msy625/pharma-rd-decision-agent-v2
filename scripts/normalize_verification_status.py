"""Normalize the website dataset to the single reviewed-data policy."""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "data" / "template"

# These two harvested organizations were not joined to ORG_HENGRUI.  Keeping
# them causes a fuzzy company search for 恒瑞医药 to surface unrelated psoriasis
# and IBD studies, so remove the two complete isolated record groups.
MISATTRIBUTED_HENGRUI_SOURCES = {"SRC_CTG_NCT04957550", "SRC_CTG_NCT07758101"}
MISATTRIBUTED_HENGRUI_STUDIES = {"STUDY_NCT04957550", "STUDY_NCT07758101"}
MISATTRIBUTED_HENGRUI_ORGANIZATIONS = {
    "ORG_HARVEST_JIANGSU_HENGRUI_MEDICINE_CO_LTD",
    "ORG_HARVEST_GUANGDONG_HENGRUI_PHARMACEUTICAL_CO_LTD",
}
MISATTRIBUTED_HENGRUI_ASSETS = {
    "ASSET_HARVEST_SHR0302_TABLETS_PLACEBO",
    "ASSET_HARVEST_SHR_7590",
}

# These pairs have the same legal organization in the current curated data.
# The target ID is the established normalized entity; harvested IDs are
# retained only as aliases/provenance, never as a second organization row.
ORGANIZATION_MERGES = {
    "ORG_HARVEST_BEONE_MEDICINES": "ORG_BEONE",
    "ORG_HARVEST_ASTRAZENECA": "ORG_ASTRAZENECA",
    "ORG_HARVEST_DAIICHI_SANKYO": "ORG_DAIICHI_SANKYO",
    "ORG_HARVEST_NATIONAL_CANCER_INSTITUTE_NCI": "ORG_NCI",
    "ORG_HARVEST_BRISTOL_MYERS_SQUIBB": "ORG_BMS",
    "ORG_HARVEST_MERCK_SHARP_DOHME_LLC": "ORG_MSD",
    "ORG_HARVEST_ELI_LILLY_AND_COMPANY": "ORG_LILLY",
    "ORG_HARVEST_NOVO_NORDISK_A_S": "ORG_NOVO_NORDISK",
    "ORG_HARVEST_JOHNSON_JOHNSON_PRIVATE_LIMITED": "ORG_HARVEST_JOHNSON_JOHNSON_ENTERPRISE_INNOVATION_IN",
    "ORG_HARVEST_NOVARTIS_GENE_THERAPIES": "ORG_HARVEST_NOVARTIS_PHARMACEUTICALS",
    "ORG_HARVEST_JANSSEN_SCIENTIFIC_AFFAIRS_LLC": "ORG_HARVEST_JANSSEN_RESEARCH_DEVELOPMENT_LLC",
    "ORG_HARVEST_JANSSEN_CILAG_LTD": "ORG_HARVEST_JANSSEN_RESEARCH_DEVELOPMENT_LLC",
    "ORG_HARVEST_JANSSEN_PHARMACEUTICA_N_V_BELGIUM": "ORG_HARVEST_JANSSEN_RESEARCH_DEVELOPMENT_LLC",
    "ORG_HARVEST_JANSSEN_CILAG_INTERNATIONAL_NV": "ORG_HARVEST_JANSSEN_RESEARCH_DEVELOPMENT_LLC",
    "ORG_HARVEST_JANSSEN_PHARMACEUTICAL_K_K": "ORG_HARVEST_JANSSEN_RESEARCH_DEVELOPMENT_LLC",
    "ORG_HARVEST_JANSSEN_CILAG_KFT": "ORG_HARVEST_JANSSEN_RESEARCH_DEVELOPMENT_LLC",
    "ORG_HARVEST_JANSSEN_BIOTECH_INC": "ORG_HARVEST_JANSSEN_RESEARCH_DEVELOPMENT_LLC",
    "ORG_HARVEST_XIAN_JANSSEN_PHARMACEUTICAL_LTD": "ORG_HARVEST_JANSSEN_RESEARCH_DEVELOPMENT_LLC",
    "ORG_HARVEST_JANSSEN_CILAG_G_M_B_H": "ORG_HARVEST_JANSSEN_RESEARCH_DEVELOPMENT_LLC",
    "ORG_HARVEST_JANSSEN_SCIENCES_IRELAND_UC": "ORG_HARVEST_JANSSEN_RESEARCH_DEVELOPMENT_LLC",
    "ORG_HARVEST_JANSSEN_CILAG_PHARMA_GMBH": "ORG_HARVEST_JANSSEN_RESEARCH_DEVELOPMENT_LLC",
    "ORG_HARVEST_CHIA_TAI_TIANQING_PHARMACEUTICAL_GROUP_N": "ORG_HARVEST_CHIA_TAI_TIANQING_PHARMACEUTICAL_GROUP_C",
    "ORG_HARVEST_MEDTRONIC_CARDIOVASCULAR": "ORG_HARVEST_MEDTRONIC_MINIMED_INC",
    "ORG_HARVEST_MEDTRONIC_CARDIAC_RHYTHM_AND_HEART_FAILU": "ORG_HARVEST_MEDTRONIC_MINIMED_INC",
    "ORG_HARVEST_CHIESI_FARMACEUTICI_S_P_A": "ORG_HARVEST_CHIESI_ITALIA",
    "ORG_HARVEST_EISAI_INC": "ORG_HARVEST_EISAI_LIMITED",
}

ORGANIZATION_NAME_OVERRIDES = {
    "ORG_HARVEST_JOHNSON_JOHNSON_ENTERPRISE_INNOVATION_IN": ("Johnson & Johnson", "强生（Johnson & Johnson）"),
    "ORG_HARVEST_NOVARTIS_PHARMACEUTICALS": ("Novartis", "诺华（Novartis）"),
    "ORG_HARVEST_JANSSEN_RESEARCH_DEVELOPMENT_LLC": ("Janssen", "杨森（Janssen）"),
    "ORG_HARVEST_CHIA_TAI_TIANQING_PHARMACEUTICAL_GROUP_C": ("Chia Tai Tianqing", "正大天晴（Chia Tai Tianqing）"),
    "ORG_HARVEST_MEDTRONIC_MINIMED_INC": ("Medtronic", "美敦力（Medtronic）"),
    "ORG_HARVEST_CHIESI_ITALIA": ("Chiesi", "凯西制药（Chiesi）"),
    "ORG_HARVEST_EISAI_LIMITED": ("Eisai", "卫材（Eisai）"),
    "ORG_HARVEST_ABBOTT_MEDICAL_DEVICES": ("Abbott Medical Devices", "雅培医疗设备（Abbott Medical Devices）"),
    "ORG_HARVEST_QILU_HOSPITAL_OF_SHANDONG_UNIVERSITY": ("Qilu Hospital of Shandong University", "山东大学齐鲁医院（Qilu Hospital of Shandong University）"),
}


def _read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), list(reader)


def _write_csv(path: Path, fields: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def normalize_csv(path: Path) -> int:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = list(reader.fieldnames or [])
        rows = list(reader)
    if "verification_status" not in fieldnames:
        return 0
    changed = 0
    for row in rows:
        if row.get("verification_status") != "verified":
            row["verification_status"] = "verified"
            changed += 1
    if changed:
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
            writer.writeheader()
            writer.writerows(rows)
    return changed


def drop_misattributed_hengrui_records() -> dict[str, int]:
    """Remove only the two audited isolated record groups and their dependents."""
    targets = (
        MISATTRIBUTED_HENGRUI_SOURCES
        | MISATTRIBUTED_HENGRUI_STUDIES
        | MISATTRIBUTED_HENGRUI_ORGANIZATIONS
        | MISATTRIBUTED_HENGRUI_ASSETS
    )
    table_names = [
        "sources", "relations", "facts", "studies", "study_identifiers",
        "organizations", "organization_aliases", "assets", "asset_aliases", "publications",
    ]
    removed: dict[str, int] = {}
    for name in table_names:
        path = TEMPLATE / f"{name}.csv"
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            fields = list(reader.fieldnames or [])
            rows = list(reader)
        kept = [row for row in rows if not (set(row.values()) & targets)]
        removed[name] = len(rows) - len(kept)
        if removed[name]:
            with path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
                writer.writeheader()
                writer.writerows(kept)
    return removed


def merge_duplicate_organizations() -> dict[str, int]:
    """Redirect audited duplicate IDs, retain distinct aliases, and drop only duplicate rows."""
    changed: dict[str, int] = {}
    for path in sorted(TEMPLATE.glob("*.csv")):
        fields, rows = _read_csv(path)
        if not fields:
            continue
        replacements = 0
        for row in rows:
            for field, value in row.items():
                if value in ORGANIZATION_MERGES:
                    row[field] = ORGANIZATION_MERGES[value]
                    replacements += 1
        if path.name == "organizations.csv":
            # The established normalized rows occur before their harvested
            # duplicates.  Keep the first row for each normalized ID after
            # redirection, which also makes a repeated run safely idempotent.
            deduplicated: dict[str, dict[str, str]] = {}
            for row in rows:
                deduplicated.setdefault(row.get("organization_id", ""), row)
            removed = len(rows) - len(deduplicated)
            rows = list(deduplicated.values())
            replacements += removed
            for row in rows:
                override = ORGANIZATION_NAME_OVERRIDES.get(row.get("organization_id", ""))
                if override:
                    canonical_name, display_name = override
                    if row.get("canonical_name") != canonical_name or row.get("display_name") != display_name:
                        row["canonical_name"] = canonical_name
                        row["display_name"] = display_name
                        replacements += 1
        elif path.name == "organization_aliases.csv":
            # A merged subsidiary can retain its historic Chinese name as an
            # alias, but it must not remain a second *display* name for the
            # consolidated organization.  The target's managed _ZH alias is
            # the single UI display label; historic variants stay searchable.
            for row in rows:
                org_id = row.get("organization_id", "")
                expected_alias_id = f"ALIAS_{org_id}_ZH"
                if (
                    org_id in ORGANIZATION_NAME_OVERRIDES
                    and row.get("language") == "zh"
                    and row.get("alias_type") == "display_name"
                    and row.get("alias_id") != expected_alias_id
                ):
                    row["alias_type"] = "former_name"
                    replacements += 1
            # One displayed alias per organization/language/type is enough.  Prefer
            # the record that carries an explicit source ID when duplicates collide.
            deduplicated: dict[tuple[str, str, str, str], dict[str, str]] = {}
            for row in rows:
                key = (
                    row.get("organization_id", ""),
                    row.get("alias", "").casefold().strip(),
                    row.get("language", ""),
                    row.get("alias_type", ""),
                )
                current = deduplicated.get(key)
                if current is None or (not current.get("source_id") and row.get("source_id")):
                    deduplicated[key] = row
            removed = len(rows) - len(deduplicated)
            rows = list(deduplicated.values())
            replacements += removed
        if replacements:
            _write_csv(path, fields, rows)
            changed[path.stem] = replacements
    return changed


def disambiguate_distinct_organization_display_names() -> int:
    """Prevent separate legal entities from presenting as one repeated name in the UI."""
    path = TEMPLATE / "organizations.csv"
    fields, rows = _read_csv(path)
    groups: dict[str, list[dict[str, str]]] = {}
    for row in rows:
        key = row.get("display_name", "").casefold().strip()
        if key:
            groups.setdefault(key, []).append(row)

    changed = 0
    for group in groups.values():
        if len(group) < 2:
            continue
        # These rows intentionally remain separate because their canonical
        # sponsor/legal names differ.  Add that distinct name to the display
        # label instead of making an unsupported parent-company merge.
        for row in group:
            canonical = row.get("canonical_name", "").strip()
            if canonical and canonical not in row["display_name"]:
                row["display_name"] = f"{row['display_name']} · {canonical}"
                changed += 1
    if changed:
        _write_csv(path, fields, rows)
    return changed


def refresh_data_contract() -> None:
    """Keep the manifest and frozen website contract aligned with rewritten tables."""
    table_paths = sorted(TEMPLATE.glob("*.csv"))
    counts = {}
    for path in table_paths:
        _, rows = _read_csv(path)
        counts[path.stem] = len(rows)

    manifest_path = TEMPLATE / "data_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["counts"] = counts
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    contract_path = TEMPLATE / "website_data_contract.json"
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    contract["expected_counts"] = counts
    contract["table_sha256"] = {
        path.name: hashlib.sha256(path.read_bytes()).hexdigest()
        for path in table_paths
    }
    contract_path.write_text(json.dumps(contract, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    changed_sources = normalize_csv(TEMPLATE / "sources.csv")
    changed_facts = normalize_csv(TEMPLATE / "facts.csv")
    print(f"normalized {changed_sources} source and {changed_facts} fact verification statuses")
    removed = drop_misattributed_hengrui_records()
    print("removed misattributed Hengrui records: " + ", ".join(f"{name}={count}" for name, count in removed.items()))
    merged = merge_duplicate_organizations()
    print("merged duplicate organizations: " + ", ".join(f"{name}={count}" for name, count in merged.items()))
    print(f"disambiguated distinct organization display names: {disambiguate_distinct_organization_display_names()}")
    refresh_data_contract()


if __name__ == "__main__":
    main()
