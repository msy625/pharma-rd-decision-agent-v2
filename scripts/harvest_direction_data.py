#!/usr/bin/env python3
"""Harvest reproducible ClinicalTrials.gov / PubMed evidence per research direction.

This script is the only entry point for external collection into the canonical
tables under ``data/template/``. It follows the rule stated in
``data/template/README.md``:外部采集必须向同一套表追加，并保留 ``source_id`` 和核验状态。

Data sources
------------
* ClinicalTrials.gov API v2  -- https://clinicaltrials.gov/api/v2/studies
* NCBI PubMed E-utilities    -- esearch.fcgi + esummary.fcgi

Every harvested row carries the exact upstream identifier (NCT id / PMID) plus a
direct URL, so any row can be re-checked by hand. Rows are marked
``api_harvested`` rather than ``verified``: they are machine-collected from the
official APIs and have NOT been individually reviewed by a human.

Usage
-----
    python scripts/harvest_direction_data.py                    # all 20 directions
    python scripts/harvest_direction_data.py --stage 1          # one stage
    python scripts/harvest_direction_data.py --direction nsclc  # one direction
    python scripts/harvest_direction_data.py --target 120       # records per direction
    python scripts/harvest_direction_data.py --dry-run          # no writes
    python scripts/harvest_direction_data.py --refresh          # ignore cache
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from collections import OrderedDict
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_DIR = PROJECT_ROOT / "data" / "template"
CATALOG_PATH = PROJECT_ROOT / "config" / "direction_catalog.json"
MANIFEST_PATH = TEMPLATE_DIR / "data_manifest.json"
CACHE_DIR = PROJECT_ROOT / ".codex-doc-work" / "harvest_cache"

CTG_ENDPOINT = "https://clinicaltrials.gov/api/v2/studies"
EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"

VERIFICATION_STATUS = "api_harvested"
HARVEST_VERSION = "direction_harvest_v1.0"
SCOPE_NOTE = "由 ClinicalTrials.gov v2 / PubMed E-utilities 官方接口批量采集，未经人工逐条复核。"

TABLES = [
    "domains",
    "organizations",
    "organization_aliases",
    "assets",
    "asset_aliases",
    "indications",
    "studies",
    "study_identifiers",
    "publications",
    "regulatory_events",
    "market_events",
    "sources",
    "facts",
    "relations",
]


# --------------------------------------------------------------------------- #
# small helpers
# --------------------------------------------------------------------------- #
def log(message: str) -> None:
    print(message, flush=True)


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


def upsert(existing: list[dict[str, str]], key: str, additions: list[dict[str, str]]) -> list[dict[str, str]]:
    """Merge ``additions`` into ``existing``; order is stable.

    Harvest tables are refreshed (same id -> new content) so a re-run picks up
    upstream status/date changes. Reference tables are insert-only: they hold
    hand-curated rows that a bulk harvest must never overwrite.
    """
    index = {row.get(key, ""): position for position, row in enumerate(existing)}
    insert_only = key in INSERT_ONLY_KEYS
    # Copy rows so callers can mutate the result (e.g. link_direction_domains)
    # without aliasing the caller's `existing` list.
    result = [dict(row) for row in existing]
    for row in additions:
        row_key = row.get(key, "")
        if row_key and row_key in index:
            if insert_only:
                continue
            result[index[row_key]] = row
        else:
            index[row_key] = len(result)
            result.append(row)
    return result


# Primary keys of reference tables whose existing rows must never be rewritten.
INSERT_ONLY_KEYS = {
    "domain_id",
    "organization_id",
    "asset_id",
    "indication_id",
    "alias_id",
}


def link_direction_domains(existing: list[dict[str, str]], catalog: dict) -> None:
    """Set parent_domain_id on direction domains without touching other fields."""
    stage_of = {}
    for stage in catalog["stages"]:
        for direction in stage["directions"]:
            stage_of[direction["direction_id"]] = stage["stage_id"]
    for row in existing:
        stage_id = stage_of.get(row.get("domain_id", ""))
        if stage_id:
            row["parent_domain_id"] = stage_id



_SLUG_STRIP = re.compile(r"[^A-Za-z0-9]+")


def slug(text: str, *, limit: int = 40) -> str:
    value = unicodedata.normalize("NFKD", str(text or ""))
    value = _SLUG_STRIP.sub("_", value).strip("_").upper()
    return (value[:limit] or "UNKNOWN").strip("_")


def title_case_status(value: str) -> str:
    mapping = {
        "ACTIVE_NOT_RECRUITING": "Active, not recruiting",
        "ENROLLING_BY_INVITATION": "Enrolling by invitation",
        "NOT_YET_RECRUITING": "Not yet recruiting",
        "RECRUITING": "Recruiting",
        "SUSPENDED": "Suspended",
        "TERMINATED": "Terminated",
        "WITHDRAWN": "Withdrawn",
        "COMPLETED": "Completed",
        "UNKNOWN": "Unknown",
    }
    return mapping.get(str(value or "").upper(), str(value or "").title())


def format_phase(phases: list[str]) -> str:
    if not phases:
        return ""
    order = {"EARLY_PHASE1": 0, "PHASE1": 1, "PHASE2": 2, "PHASE3": 3, "PHASE4": 4, "NA": 9}
    normalised = sorted({str(p).upper() for p in phases}, key=lambda p: order.get(p, 8))
    if normalised == ["NA"]:
        return "Not Applicable"
    labels = []
    for phase in normalised:
        if phase == "EARLY_PHASE1":
            labels.append("Early Phase 1")
        elif phase.startswith("PHASE"):
            labels.append(f"Phase {phase[-1]}")
        else:
            labels.append(phase.title())
    if len(labels) == 2 and labels[0].startswith("Phase") and labels[1].startswith("Phase"):
        return f"{labels[0]}/{labels[1].split()[-1]}"
    return "/".join(labels)


def iter_phases(phase_text: str) -> list[str]:
    return [part.strip() for part in str(phase_text or "").split("/") if part.strip()]


# --------------------------------------------------------------------------- #
# HTTP with cache + retry
# --------------------------------------------------------------------------- #
class Fetcher:
    def __init__(self, user_agent: str, refresh: bool) -> None:
        self.user_agent = user_agent
        self.refresh = refresh
        CACHE_DIR.mkdir(parents=True, exist_ok=True)

    def _cache_path(self, key: str) -> Path:
        return CACHE_DIR / f"{key}.json"

    def get_json(self, url: str, cache_key: str, *, attempts: int = 4, pause: float = 0.6) -> dict:
        cached = self._cache_path(cache_key)
        if cached.exists() and not self.refresh:
            return json.loads(cached.read_text(encoding="utf-8"))

        last_error: Exception | None = None
        for attempt in range(attempts):
            try:
                request = urllib.request.Request(url, headers={"User-Agent": self.user_agent})
                with urllib.request.urlopen(request, timeout=60) as response:
                    payload = json.loads(response.read().decode("utf-8"))
                cached.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
                return payload
            except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError) as exc:
                last_error = exc
                time.sleep(pause * (attempt + 1) * 2)
        raise RuntimeError(f"request failed after {attempts} attempts: {url}: {last_error}")


# --------------------------------------------------------------------------- #
# ClinicalTrials.gov
# --------------------------------------------------------------------------- #
def fetch_ctg_studies(fetcher: Fetcher, direction: dict, limit: int, page_size: int, max_pages: int) -> list[dict]:
    studies: "OrderedDict[str, dict]" = OrderedDict()
    token = None
    for page in range(max_pages):
        params = {
            "query.cond": direction["ctg_condition"],
            "pageSize": str(page_size),
            "countTotal": "true",
            "sort": "LastUpdatePostDate:desc",
        }
        if token:
            params["pageToken"] = token
        url = f"{CTG_ENDPOINT}?{urllib.parse.urlencode(params)}"
        payload = fetcher.get_json(url, f"ctg_{direction['direction_key']}_p{page}")
        for study in payload.get("studies", []):
            nct = study.get("protocolSection", {}).get("identificationModule", {}).get("nctId", "")
            if nct and nct not in studies:
                studies[nct] = study
            if len(studies) >= limit:
                break
        token = payload.get("nextPageToken")
        if len(studies) >= limit or not token:
            break
        time.sleep(0.4)
    return list(studies.values())[:limit]


def ctg_study_rows(study: dict, direction: dict, stage: dict, harvest_date: str) -> dict:
    protocol = study.get("protocolSection", {})
    ident = protocol.get("identificationModule", {})
    status_mod = protocol.get("statusModule", {})
    design = protocol.get("designModule", {})
    sponsor = protocol.get("sponsorCollaboratorsModule", {}).get("leadSponsor", {})
    conditions = protocol.get("conditionsModule", {}).get("conditions", []) or []
    interventions = protocol.get("armsInterventionsModule", {}).get("interventions", []) or []
    eligibility = protocol.get("eligibilityModule", {})

    nct = ident.get("nctId", "")
    title = ident.get("officialTitle") or ident.get("briefTitle") or ""
    acronym = ident.get("acronym") or ""
    phase = format_phase(design.get("phases") or [])
    status = title_case_status(status_mod.get("overallStatus"))
    sponsor_name = sponsor.get("name", "") or ""
    enrollment = design.get("enrollmentInfo", {}) or {}
    enrollment_count = str(enrollment.get("count", "") or "")

    drugs = [
        item.get("name", "")
        for item in interventions
        if str(item.get("type", "")).upper() in {"DRUG", "BIOLOGICAL", "COMBINATION_PRODUCT"}
    ]
    other_interventions = [
        item.get("name", "")
        for item in interventions
        if str(item.get("type", "")).upper() not in {"DRUG", "BIOLOGICAL", "COMBINATION_PRODUCT"}
    ]

    last_update = status_mod.get("lastUpdateSubmitDate", "") or ""
    start_date = (status_mod.get("startDateStruct") or {}).get("date", "") or ""
    completion_date = (status_mod.get("completionDateStruct") or {}).get("date", "") or ""
    primary_completion = (status_mod.get("primaryCompletionDateStruct") or {}).get("date", "") or ""

    source_id = f"SRC_CTG_{nct}"
    study_id = f"STUDY_{nct}"
    org_id = f"ORG_HARVEST_{slug(sponsor_name)}" if sponsor_name else ""
    asset_ids = [f"ASSET_HARVEST_{slug(name)}" for name in drugs if name]
    indication_id = direction["indication_id"]

    study_row = {
        "study_id": study_id,
        "domain_id": direction["direction_id"],
        "study_type": "clinical_trial",
        "study_name": acronym,
        "phase": phase,
        "study_status": status,
        "sponsor_org_id": org_id,
        "primary_asset_id": asset_ids[0] if asset_ids else "",
        "primary_indication_id": indication_id,
        "enrollment_planned": enrollment_count if str(enrollment.get("type", "")).upper() == "ESTIMATED" else "",
        "enrollment_actual": enrollment_count if str(enrollment.get("type", "")).upper() == "ACTUAL" else "",
        "start_date": start_date,
        "primary_completion_date": primary_completion,
        "completion_date": completion_date,
        "last_status_date": last_update,
        "notes": f"{HARVEST_VERSION}；方向 {direction['name_zh']}（{stage['stage_name']}）；来源 ClinicalTrials.gov v2。",
    }
    identifier_row = {
        "study_identifier_id": f"SID_{nct}",
        "study_id": study_id,
        "identifier_type": "NCT",
        "identifier_value": nct,
        "is_primary": "true",
        "source_id": source_id,
        "notes": "ClinicalTrials.gov 官方注册号。",
    }
    source_row = {
        "source_id": source_id,
        "source_type": "CLINICAL_TRIAL_REGISTRY",
        "publisher": "ClinicalTrials.gov",
        "title_original": title,
        "url": f"https://clinicaltrials.gov/study/{nct}",
        "language": "en",
        "publication_date": start_date,
        "source_last_updated": last_update,
        "verified_at": harvest_date,
        "verification_status": VERIFICATION_STATUS,
        "source_scope": f"{stage['stage_name']}／{direction['name_zh']}",
        "source_locator": nct,
        "content_hash": "",
        "notes": SCOPE_NOTE,
    }
    return {
        "study": study_row,
        "identifier": identifier_row,
        "source": source_row,
        "nct": nct,
        "title": title,
        "acronym": acronym,
        "phase": phase,
        "status": status,
        "sponsor_name": sponsor_name,
        "org_id": org_id,
        "drugs": drugs,
        "asset_ids": asset_ids,
        "other_interventions": other_interventions,
        "conditions": conditions,
        "enrollment_count": enrollment_count,
        "last_update": last_update,
        "start_date": start_date,
        "eligibility": eligibility,
        "indication_id": indication_id,
        "direction": direction,
        "stage": stage,
    }


# --------------------------------------------------------------------------- #
# PubMed
# --------------------------------------------------------------------------- #
def fetch_pubmed(fetcher: Fetcher, direction: dict, retmax: int, tool: str, email: str) -> list[dict]:
    search_url = f"{EUTILS}/esearch.fcgi?" + urllib.parse.urlencode(
        {
            "db": "pubmed",
            "term": direction["pubmed_term"],
            "retmax": str(retmax),
            "retmode": "json",
            "sort": "date",
            "tool": tool,
            "email": email,
        }
    )
    payload = fetcher.get_json(search_url, f"pubmed_search_{direction['direction_key']}_n{retmax}")
    ids = payload.get("esearchresult", {}).get("idlist", []) or []
    if not ids:
        return []
    time.sleep(0.4)
    summary_url = f"{EUTILS}/esummary.fcgi?" + urllib.parse.urlencode(
        {"db": "pubmed", "id": ",".join(ids), "retmode": "json", "tool": tool, "email": email}
    )
    summary = fetcher.get_json(summary_url, f"pubmed_summary_{direction['direction_key']}_n{retmax}")
    result = summary.get("result", {})
    return [result[uid] for uid in ids if uid in result]


def normalize_pubdate(pubdate: str) -> tuple[str, str]:
    """Return (iso_date_or_year_month, issue_year)."""
    text = str(pubdate or "").strip()
    match = re.match(r"^(\d{4})\s*([A-Za-z]{3})?", text)
    if not match:
        return "", ""
    year = match.group(1)
    month_token = match.group(2)
    months = {
        "jan": "01", "feb": "02", "mar": "03", "apr": "04", "may": "05", "jun": "06",
        "jul": "07", "aug": "08", "sep": "09", "oct": "10", "nov": "11", "dec": "12",
    }
    month = months.get((month_token or "").lower(), "")
    return (f"{year}-{month}" if month else year), year


def pubmed_publication_row(doc: dict, direction: dict, stage: dict, harvest_date: str) -> dict:
    pmid = str(doc.get("uid", ""))
    title = str(doc.get("title", "") or "").rstrip(".")
    journal = str(doc.get("source", "") or "")
    full_journal = str(doc.get("fulljournalname", "") or "")
    doi = ""
    for article_id in doc.get("articleids", []) or []:
        if str(article_id.get("idtype", "")).lower() == "doi":
            doi = str(article_id.get("value", ""))
            break
    if not doi:
        elocation = str(doc.get("elocationid", "") or "")
        if elocation.lower().startswith("doi:"):
            doi = elocation[4:].strip()
    date_value, issue_year = normalize_pubdate(doc.get("pubdate", ""))
    pub_types = [str(item) for item in (doc.get("pubtype") or [])]
    publication_type = "；".join(pub_types) if pub_types else "Journal Article"

    source_id = f"SRC_PM_{pmid}"
    publication_id = f"PUB_{pmid}"
    publication_row = {
        "publication_id": publication_id,
        "domain_id": direction["direction_id"],
        "title_original": title,
        "title_normalized": "",
        "publication_type": publication_type,
        "pmid": pmid,
        "doi": doi,
        "journal": full_journal or journal,
        "online_publication_date": date_value,
        "issue_year": issue_year,
        "analysis_stage": "",
        "study_id": "",
        "source_id": source_id,
        "notes": f"{HARVEST_VERSION}；方向 {direction['name_zh']}（{stage['stage_name']}）；来源 PubMed E-utilities。",
    }
    source_row = {
        "source_id": source_id,
        "source_type": "PUBMED_ARTICLE",
        "publisher": journal,
        "title_original": title,
        "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
        "language": str(doc.get("lang", "") or "")[:2].lower() or "en",
        "publication_date": date_value,
        "source_last_updated": "",
        "verified_at": harvest_date,
        "verification_status": VERIFICATION_STATUS,
        "source_scope": f"{stage['stage_name']}／{direction['name_zh']}",
        "source_locator": f"PMID {pmid}",
        "content_hash": "",
        "notes": SCOPE_NOTE,
    }
    return {
        "publication": publication_row,
        "source": source_row,
        "pmid": pmid,
        "title": title,
        "journal": full_journal or journal,
        "doi": doi,
        "date": date_value,
        "issue_year": issue_year,
        "publication_type": publication_type,
        "direction": direction,
        "stage": stage,
    }


# --------------------------------------------------------------------------- #
# build all rows for one direction
# --------------------------------------------------------------------------- #
def build_direction_rows(
    studies: list[dict],
    publications: list[dict],
    direction: dict,
    stage: dict,
    harvest_date: str,
) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {name: [] for name in TABLES}

    seen_orgs: dict[str, str] = {}
    seen_assets: dict[str, str] = {}

    for study in studies:
        row = ctg_study_rows(study, direction, stage, harvest_date)
        out["studies"].append(row["study"])
        out["study_identifiers"].append(row["identifier"])
        out["sources"].append(row["source"])

        if row["sponsor_name"] and row["org_id"] not in seen_orgs:
            seen_orgs[row["org_id"]] = row["sponsor_name"]
            out["organizations"].append(
                {
                    "organization_id": row["org_id"],
                    "canonical_name": row["sponsor_name"],
                    "display_name": row["sponsor_name"],
                    "organization_type": "trial_sponsor",
                    "country_or_region": "",
                    "website": "",
                    "status": "active",
                    "notes": f"{HARVEST_VERSION}；来自 ClinicalTrials.gov 申办方字段，未经人工复核。",
                }
            )
            out["organization_aliases"].append(
                {
                    "alias_id": f"ALIAS_{row['org_id']}_CANONICAL",
                    "organization_id": row["org_id"],
                    "alias": row["sponsor_name"],
                    "language": "en",
                    "alias_type": "canonical_or_code",
                    "valid_from": "",
                    "valid_to": "",
                    "source_id": row["source"]["source_id"],
                    "notes": SCOPE_NOTE,
                }
            )

        for asset_id, drug_name in zip(row["asset_ids"], row["drugs"]):
            if asset_id in seen_assets:
                continue
            seen_assets[asset_id] = drug_name
            out["assets"].append(
                {
                    "asset_id": asset_id,
                    "domain_id": direction["direction_id"],
                    "canonical_name": drug_name,
                    "generic_name": "",
                    "development_code": "",
                    "brand_name": "",
                    "asset_type": "drug_or_biologic",
                    "modality": "",
                    "target": "",
                    "originator_org_id": row["org_id"],
                    "owner_org_id": "",
                    "development_status": row["status"],
                    "first_known_date": row["start_date"],
                    "last_known_date": row["last_update"],
                    "notes": f"{HARVEST_VERSION}；来自 ClinicalTrials.gov 干预字段，靶点与权属未经核实。",
                }
            )
            out["asset_aliases"].append(
                {
                    "alias_id": f"ALIAS_{asset_id}_CANONICAL",
                    "asset_id": asset_id,
                    "alias": drug_name,
                    "language": "en",
                    "alias_type": "canonical_or_code",
                    "source_id": row["source"]["source_id"],
                    "notes": SCOPE_NOTE,
                }
            )

        out["facts"].extend(ctg_facts(row))
        out["relations"].extend(ctg_relations(row))

    for doc in publications:
        row = pubmed_publication_row(doc, direction, stage, harvest_date)
        out["publications"].append(row["publication"])
        out["sources"].append(row["source"])
        out["facts"].extend(pubmed_facts(row))
        out["relations"].extend(pubmed_relations(row))

    return out


def _fact(fact_id: str, domain_id: str, subject: str, predicate: str, value: str, source_id: str) -> dict:
    return {
        "fact_id": fact_id,
        "domain_id": domain_id,
        "subject_id": subject,
        "predicate": predicate,
        "object_id": "",
        "object_value": value,
        "value_type": "source_assertion",
        "unit": "",
        "event_date": "",
        "valid_from": "",
        "valid_to": "",
        "source_id": source_id,
        "verification_status": VERIFICATION_STATUS,
        "confidence_level": "medium",
        "scope_note": SCOPE_NOTE,
    }


def _relation(relation_id: str, domain_id: str, subject: str, relation_type: str, obj: str, source_id: str) -> dict:
    return {
        "relation_id": relation_id,
        "domain_id": domain_id,
        "subject_id": subject,
        "relation_type": relation_type,
        "object_id": obj,
        "relation_status": "confirmed",
        "source_id": source_id,
        "valid_from": "",
        "valid_to": "",
        "confidence_level": "medium",
        "scope_note": SCOPE_NOTE,
    }


def ctg_facts(row: dict) -> list[dict]:
    direction = row["direction"]
    domain_id = direction["direction_id"]
    base = row["nct"]
    source_id = row["source"]["source_id"]
    facts = [
        _fact(f"FACT_CTG_{base}_DIRECTION", domain_id, source_id, "research_direction", direction["name_zh"], source_id),
        _fact(f"FACT_CTG_{base}_TITLE", domain_id, source_id, "official_title", row["title"], source_id),
        _fact(f"FACT_CTG_{base}_STATUS", domain_id, source_id, "study_status", row["status"], source_id),
    ]
    if row["phase"]:
        facts.append(_fact(f"FACT_CTG_{base}_PHASE", domain_id, source_id, "study_phase", row["phase"], source_id))
    if row["sponsor_name"]:
        facts.append(_fact(f"FACT_CTG_{base}_SPONSOR", domain_id, source_id, "lead_sponsor", row["sponsor_name"], source_id))
    if row["enrollment_count"]:
        facts.append(_fact(f"FACT_CTG_{base}_ENROLLMENT", domain_id, source_id, "enrollment_count", row["enrollment_count"], source_id))
    if row["conditions"]:
        facts.append(
            _fact(f"FACT_CTG_{base}_CONDITION", domain_id, source_id, "condition", "；".join(row["conditions"][:6]), source_id)
        )
    if row["drugs"]:
        facts.append(_fact(f"FACT_CTG_{base}_INTERVENTION", domain_id, source_id, "intervention", "；".join(row["drugs"][:8]), source_id))
    if row["start_date"]:
        facts.append(_fact(f"FACT_CTG_{base}_START", domain_id, source_id, "start_date", row["start_date"], source_id))
    return facts


def ctg_relations(row: dict) -> list[dict]:
    direction = row["direction"]
    domain_id = direction["direction_id"]
    base = row["nct"]
    source_id = row["source"]["source_id"]
    relations = [
        _relation(f"REL_CTG_{base}_STUDY", domain_id, source_id, "source_describes_study", f"STUDY_{base}", source_id),
        _relation(
            f"REL_CTG_{base}_INDICATION",
            domain_id,
            source_id,
            "source_about_indication",
            row["indication_id"],
            source_id,
        ),
    ]
    if row["org_id"]:
        relations.append(_relation(f"REL_CTG_{base}_SPONSOR", domain_id, source_id, "source_about_org", row["org_id"], source_id))
    for asset_id in row["asset_ids"][:5]:
        relations.append(
            _relation(f"REL_CTG_{base}_ASSET_{asset_id.split('_')[-1]}", domain_id, source_id, "source_mentions_asset", asset_id, source_id)
        )
    return relations


def pubmed_facts(row: dict) -> list[dict]:
    direction = row["direction"]
    domain_id = direction["direction_id"]
    pmid = row["pmid"]
    source_id = row["source"]["source_id"]
    facts = [
        _fact(f"FACT_PM_{pmid}_DIRECTION", domain_id, source_id, "research_direction", direction["name_zh"], source_id),
        _fact(f"FACT_PM_{pmid}_TITLE", domain_id, source_id, "publication_title", row["title"], source_id),
    ]
    if row["journal"]:
        facts.append(_fact(f"FACT_PM_{pmid}_JOURNAL", domain_id, source_id, "journal", row["journal"], source_id))
    if row["publication_type"]:
        facts.append(_fact(f"FACT_PM_{pmid}_PUBTYPE", domain_id, source_id, "publication_type", row["publication_type"], source_id))
    if row["date"]:
        facts.append(_fact(f"FACT_PM_{pmid}_DATE", domain_id, source_id, "publication_date", row["date"], source_id))
    if row["doi"]:
        facts.append(_fact(f"FACT_PM_{pmid}_DOI", domain_id, source_id, "doi", row["doi"], source_id))
    return facts


def pubmed_relations(row: dict) -> list[dict]:
    direction = row["direction"]
    domain_id = direction["direction_id"]
    pmid = row["pmid"]
    source_id = row["source"]["source_id"]
    return [
        _relation(f"REL_PM_{pmid}_PUBLICATION", domain_id, source_id, "source_describes_publication", f"PUB_{pmid}", source_id),
        _relation(
            f"REL_PM_{pmid}_INDICATION",
            domain_id,
            source_id,
            "source_about_indication",
            direction["indication_id"],
            source_id,
        ),
    ]


# --------------------------------------------------------------------------- #
# domains / indications
# --------------------------------------------------------------------------- #
def build_domain_rows(catalog: dict) -> tuple[list[dict], list[dict]]:
    domain_rows: list[dict] = []
    indication_rows: list[dict] = []
    for stage in catalog["stages"]:
        domain_rows.append(
            {
                "domain_id": stage["stage_id"],
                "parent_domain_id": "",
                "domain_name": f"{stage['stage_name']}：{stage['stage_title']}",
                "domain_type": "research_stage",
                "description": stage["goal"],
                "active": "true",
            }
        )
        for direction in stage["directions"]:
            domain_rows.append(
                {
                    "domain_id": direction["direction_id"],
                    "parent_domain_id": stage["stage_id"],
                    "domain_name": direction["name_zh"],
                    "domain_type": "disease_research_domain",
                    "description": f"{stage['stage_name']}（{stage['stage_title']}）方向；目标：{stage['goal']}",
                    "active": "true",
                }
            )
            indication_rows.append(
                {
                    "indication_id": direction["indication_id"],
                    "domain_id": direction["direction_id"],
                    "disease_name": direction["name_zh"],
                    "disease_code": direction["direction_key"].upper(),
                    "histology": "",
                    "biomarker": "",
                    "treatment_line": "",
                    "population_description": f"ClinicalTrials.gov 条件检索 “{direction['ctg_condition']}” 返回的注册研究人群。",
                    "geography": "",
                    "notes": f"{HARVEST_VERSION}；批量采集，未按人群细分人工复核。",
                }
            )
    return domain_rows, indication_rows


# --------------------------------------------------------------------------- #
# main
# --------------------------------------------------------------------------- #
def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--stage", type=int, help="only harvest this stage index (1-6)")
    parser.add_argument("--direction", help="only harvest this direction key, e.g. nsclc")
    parser.add_argument("--target", type=int, help="target total records per direction (default from catalog)")
    parser.add_argument("--pubmed-per-direction", type=int, help="max PubMed records per direction")
    parser.add_argument("--dry-run", action="store_true", help="report what would be written, write nothing")
    parser.add_argument("--refresh", action="store_true", help="ignore the local response cache")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv if argv is not None else sys.argv[1:])
    catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    harvest_cfg = catalog["harvest"]
    target = args.target or harvest_cfg["default_target_per_direction"]
    pubmed_max = args.pubmed_per_direction or harvest_cfg["pubmed_retmax"]

    harvest_date = time.strftime("%Y-%m-%d")
    fetcher = Fetcher(harvest_cfg["user_agent"], args.refresh)

    # derive ids for every direction first, then apply the selection filters
    for stage in catalog["stages"]:
        for direction in stage["directions"]:
            direction["indication_id"] = f"IND_{direction['direction_key'].upper()}"
            direction["stage_id"] = stage["stage_id"]

    selected: list[tuple[dict, dict]] = []
    for stage in catalog["stages"]:
        if args.stage and stage["stage_index"] != args.stage:
            continue
        for direction in stage["directions"]:
            if args.direction and direction["direction_key"] != args.direction:
                continue
            selected.append((stage, direction))

    if not selected:
        log("no direction matched the given filters")
        return 1

    domain_rows, indication_rows = build_domain_rows(catalog)
    if args.stage or args.direction:
        keep = {d["direction_id"] for _s, d in selected}
        keep_stages = {s["stage_id"] for s, _d in selected}
        domain_rows = [r for r in domain_rows if r["domain_id"] in keep | keep_stages]
        indication_rows = [r for r in indication_rows if r["domain_id"] in keep]

    collected: dict[str, list[dict]] = {name: [] for name in TABLES}
    collected["domains"] = domain_rows
    collected["indications"] = indication_rows

    log(f"harvesting {len(selected)} direction(s); target={target} records each; harvest_date={harvest_date}")
    for stage, direction in selected:
        nct_limit = max(target - min(pubmed_max, target // 2), 1)
        studies = fetch_ctg_studies(
            fetcher,
            direction,
            limit=nct_limit,
            page_size=harvest_cfg["ctg_page_size"],
            max_pages=harvest_cfg["ctg_max_pages"],
        )
        time.sleep(0.4)
        remaining = max(target - len(studies), 0)
        publications = fetch_pubmed(
            fetcher,
            direction,
            retmax=min(pubmed_max, remaining) if remaining else 0,
            tool=harvest_cfg["pubmed_tool"],
            email=harvest_cfg["pubmed_email"],
        )
        rows = build_direction_rows(studies, publications, direction, stage, harvest_date)
        for name in TABLES:
            collected[name].extend(rows[name])
        log(
            f"  [{stage['stage_name']}] {direction['name_zh']}: "
            f"{len(studies)} trials + {len(publications)} publications = {len(studies) + len(publications)} records"
        )
        time.sleep(0.4)

    if args.dry_run:
        total = {name: len(rows) for name, rows in collected.items() if rows}
        log(f"dry-run summary: {json.dumps(total, ensure_ascii=False)}")
        return 0

    summary: dict[str, int] = {}
    for name in TABLES:
        fieldnames, existing = read_table(name)
        merged = upsert(existing, _primary_key(name), collected[name])
        if name == "domains":
            link_direction_domains(merged, catalog)
        if merged == existing:
            summary[name] = len(merged)
            log(f"  {name}.csv unchanged ({len(merged)} rows)")
            continue
        write_table(name, fieldnames, merged)
        summary[name] = len(merged)
        log(f"  wrote {name}.csv: {len(existing)} -> {len(merged)} rows (+{len(merged) - len(existing)})")

    update_manifest(summary, harvest_date)
    log("harvest complete")
    return 0


def _primary_key(table: str) -> str:
    return {
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
    }[table]


def update_manifest(counts: dict[str, int], harvest_date: str) -> None:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    manifest["counts"] = counts
    manifest["dataset"] = "canonical_data_v1+direction_harvest_v1"
    manifest["direction_harvest"] = {
        "harvest_version": HARVEST_VERSION,
        "harvested_at": harvest_date,
        "catalog": "config/direction_catalog.json",
        "generator": "scripts/harvest_direction_data.py",
        "verification_status": VERIFICATION_STATUS,
    }
    limitations = [
        item
        for item in manifest.get("limitations", [])
        if "bulk-harvest data are not yet present" not in item
    ]
    harvest_limitation = (
        "方向批量采集数据由 ClinicalTrials.gov v2 与 PubMed E-utilities 生成，"
        "verification_status=api_harvested，未经人工逐条复核；不能替代人工核验样本。"
    )
    if harvest_limitation not in limitations:
        limitations.append(harvest_limitation)
    manifest["limitations"] = limitations
    MANIFEST_PATH.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
