"""Adapt machine-harvested direction records into the legacy source-registry shape.

The rest of the application (evidence chain, company comparison, company profile,
event timeline, workbench, grounded QA) is written against the 56-column
``source_registry.csv`` row shape. This module projects the harvested records from
``data/template/`` into that same shape so those services keep working unchanged
when the "include machine-harvested data" switch is on.

Only ``verification_status == api_harvested`` records are projected. The human
verified sources already exist in ``source_registry.csv`` and must not be
duplicated, and collapsing the two would destroy the verified/harvested
distinction the project relies on.
"""

from __future__ import annotations

import csv
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CSV_PATH = PROJECT_ROOT / "data" / "source_registry.csv"

HARVESTED_STATUS = "api_harvested"

TRIAL_SOURCE_TYPE = "ClinicalTrials.gov"
PUBLICATION_SOURCE_TYPE = "PubMed"

HARVESTED_SCOPE_NOTE = (
    "机器采集（api_harvested），由 ClinicalTrials.gov v2 / PubMed E-utilities 官方接口批量获取，"
    "未经人工逐条复核；与人工核验资料属于两套口径，不能互相替代。"
)
HARVESTED_SCOPE_LIMITATION = (
    "仅代表当前收录的公开注册研究与公开论文，不代表企业研发实力或完整管线，"
    "不支持跨试验疗效排名、成功率预测或投资建议。"
)

# Columns the legacy registry exposes; harvested rows are padded to match.
LEGACY_FIELDS = [
    "source_id", "company", "company_cn", "company_current_name", "company_former_name",
    "company_display_name", "sponsor_original", "disease", "source_type", "registry_id",
    "original_title_en", "original_title", "original_language", "normalized_title_zh",
    "study_name", "histology", "treatment_line", "population", "intervention", "comparator",
    "regimen_detail", "biomarker_requirements", "drug_names", "study_phase", "study_status",
    "verification_status", "url", "verified_at", "source_pages", "publication_date",
    "announcement_number", "notes", "parent_trial_id", "pmid", "publication_type",
    "analysis_stage", "evidence_version", "supersedes_source_id", "is_latest_evidence",
    "primary_endpoints", "secondary_endpoints", "online_publication_date", "issue_year",
    "journal", "doi", "official_study_id", "china_trial_id", "enrollment_actual",
    "regulatory_authority", "regulatory_event_type", "authorisation_status",
    "marketing_authorisation_holder", "source_last_updated", "data_cutoff_date",
    "evidence_relation", "scope_limitation",
]


def legacy_fieldnames() -> list[str]:
    """Return the header of the checked-in registry, falling back to LEGACY_FIELDS."""
    path = Path(DEFAULT_CSV_PATH)
    if not path.exists():
        return list(LEGACY_FIELDS)
    with path.open("r", encoding="utf-8", newline="") as fh:
        reader = csv.reader(fh)
        header = next(reader, None)
    return list(header) if header else list(LEGACY_FIELDS)


def to_legacy_row(record: dict[str, object], fieldnames: list[str]) -> dict[str, str]:
    """Project one DirectionDatasetService record into the legacy registry shape."""
    record_type = str(record.get("record_type", ""))
    is_trial = record_type == "clinical_trial"

    company_display = str(record.get("company", "") or "")
    company_en = str(record.get("company_en", "") or "") or company_display
    assets = "；".join(str(a) for a in record.get("assets", []) or [])
    direction = str(record.get("direction_name", "") or "")
    stage = str(record.get("stage_name", "") or "")
    registry_id = str(record.get("registry_id", "") or "")

    values = {
        "source_id": str(record.get("record_id", "") or ""),
        "company": company_en or company_display,
        "company_cn": company_display,
        "company_current_name": company_en,
        "company_display_name": company_display,
        "sponsor_original": company_en,
        "disease": direction,
        "source_type": TRIAL_SOURCE_TYPE if is_trial else PUBLICATION_SOURCE_TYPE,
        "registry_id": registry_id,
        "original_title_en": str(record.get("title", "") or ""),
        "original_title": str(record.get("title", "") or ""),
        "original_language": "en",
        "normalized_title_zh": str(record.get("title", "") or ""),
        "study_name": str(record.get("study_name", "") or ""),
        "population": str(record.get("conditions", "") or ""),
        "intervention": assets,
        "drug_names": assets,
        "study_phase": str(record.get("phase", "") or ""),
        "study_status": str(record.get("study_status", "") or ""),
        "verification_status": HARVESTED_STATUS,
        "url": str(record.get("url", "") or ""),
        "verified_at": str(record.get("verified_at", "") or ""),
        "publication_date": str(record.get("publication_date", "") or ""),
        "online_publication_date": str(record.get("publication_date", "") or ""),
        "notes": f"{HARVESTED_SCOPE_NOTE}采集范围：{stage}／{direction}。",
        "pmid": str(record.get("pmid", "") or ""),
        "journal": str(record.get("journal", "") or ""),
        "doi": str(record.get("doi", "") or ""),
        "publication_type": "期刊论文" if not is_trial else "",
        "official_study_id": registry_id,
        "enrollment_actual": str(record.get("enrollment", "") or ""),
        "source_last_updated": str(record.get("source_last_updated", "") or ""),
        "is_latest_evidence": "true",
        "scope_limitation": HARVESTED_SCOPE_LIMITATION,
    }
    row = {field: "" for field in fieldnames}
    for key, value in values.items():
        if key in row:
            row[key] = value
    return row


def harvested_legacy_rows(records: list[dict[str, object]], fieldnames: list[str]) -> list[dict[str, str]]:
    """Project every machine-harvested record, skipping human-verified sources."""
    rows = []
    for record in records:
        if str(record.get("verification_status", "")) != HARVESTED_STATUS:
            continue
        if not str(record.get("url", "") or "").startswith("http"):
            continue
        rows.append(to_legacy_row(record, fieldnames))
    return rows
