"""Query service for the verified NSCLC source registry.

This module is intentionally limited to local CSV/JSON files. It does not
import model, vector-store, network, or web framework dependencies.
"""

from __future__ import annotations

import csv
import json
from collections import Counter
from pathlib import Path
from typing import Iterable


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CSV_PATH = PROJECT_ROOT / "data" / "source_registry.csv"
DEFAULT_ALIASES_PATH = PROJECT_ROOT / "config" / "entity_aliases.json"
DEFAULT_EVIDENCE_RULES_PATH = PROJECT_ROOT / "config" / "evidence_rules.json"

REQUIRED_FIELDS = ["source_id", "company", "source_type", "url"]

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

COMPANY_ALIAS_GROUPS = [
    ["百济神州", "BeOne Medicines", "BeiGene", "百济神州（BeOne Medicines，原BeiGene）"],
    ["恒瑞医药", "江苏恒瑞医药股份有限公司", "Jiangsu Hengrui Medicine", "Jiangsu HengRui Medicine"],
    ["阿斯利康", "AstraZeneca", "阿斯利康（AstraZeneca）"],
]


class SourceRegistryError(Exception):
    """Base exception for source registry query failures."""


class SourceRegistryFileNotFound(SourceRegistryError):
    """Raised when a required local data file is missing."""


class SourceRegistryStructureError(SourceRegistryError):
    """Raised when CSV or JSON structure is invalid."""


def _display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(PROJECT_ROOT))
    except ValueError:
        return path.name


def norm(value: object) -> str:
    return str(value or "").casefold()


def contains(value: object, needle: str) -> bool:
    return norm(needle) in norm(value)


def _joined(row: dict[str, str], fields: Iterable[str]) -> str:
    return " ".join(row.get(field, "") for field in fields)


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
    return _joined(
        row,
        [
            "company",
            "company_cn",
            "company_current_name",
            "company_former_name",
            "company_display_name",
            "sponsor_original",
        ],
    )


def is_latest_row(row: dict[str, str]) -> bool:
    return norm(row.get("is_latest_evidence")) != "false"


def is_nsclc_comparison_record(row: dict[str, str]) -> bool:
    if row.get("source_id") == "B014":
        return False
    scope_text = row.get("scope_limitation", "") + row.get("notes", "")
    if "SCLC 项目不计入 NSCLC" in scope_text or "不要将 SCLC 项目计入" in scope_text:
        return False
    return "非小细胞肺癌" in row.get("disease", "") or "NSCLC" in row.get("disease", "")


class SourceRegistryService:
    """Small CSV-backed query service for manually verified source records."""

    def __init__(
        self,
        csv_path: str | Path | None = None,
        aliases_path: str | Path | None = None,
        evidence_rules_path: str | Path | None = None,
    ) -> None:
        self.csv_path = Path(csv_path) if csv_path else DEFAULT_CSV_PATH
        self.aliases_path = Path(aliases_path) if aliases_path else DEFAULT_ALIASES_PATH
        self.evidence_rules_path = Path(evidence_rules_path) if evidence_rules_path else DEFAULT_EVIDENCE_RULES_PATH
        self._rows: list[dict[str, str]] | None = None
        self._fieldnames: list[str] | None = None
        self._alias_map: dict[str, list[str]] | None = None
        self._evidence_rules: dict[str, object] | None = None

    def load_rows(self) -> list[dict[str, str]]:
        if self._rows is None:
            self._fieldnames, self._rows = self._read_csv(self.csv_path)
        return list(self._rows)

    def load_aliases(self) -> dict[str, list[str]]:
        if self._alias_map is None:
            self._alias_map = self._read_aliases(self.aliases_path)
        return dict(self._alias_map)

    def load_evidence_rules(self) -> dict[str, object]:
        if self._evidence_rules is None:
            self._evidence_rules = self._read_json_file(self.evidence_rules_path)
        return dict(self._evidence_rules)

    def summary(self) -> dict[str, object]:
        rows = self.load_rows()
        company_counts = Counter(row.get("company_cn") or row.get("company") for row in rows)
        source_type_counts = Counter(row.get("source_type", "") for row in rows)
        beone_trials = sorted(
            {
                row.get("study_name")
                for row in rows
                if row.get("company_cn") == "百济神州" and row.get("study_name", "").startswith("RATIONALE-")
            }
        )
        return {
            "total_sources": len(rows),
            "company_counts": dict(company_counts),
            "source_type_counts": dict(source_type_counts),
            "beone_unique_nsclc_trials": beone_trials,
            "nsclc_comparison_records": sum(1 for row in rows if is_nsclc_comparison_record(row)),
        }

    def query(
        self,
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
        normalized: bool = True,
    ) -> list[dict[str, str]]:
        study_name_query = str(study_name or "").strip()
        if not any([source_id, company, trial_id, pmid, study_name_query, drug, source_type, status, text]):
            return []

        rows = self.load_rows()
        aliases = self.load_aliases()
        company_terms = self.expand_company_terms(company) if company else []
        drug_terms = self.expand_drug_terms(drug, aliases) if drug else []
        matched: list[dict[str, str]] = []

        for row in rows:
            if latest_only and not is_latest_row(row):
                continue
            if source_id and not contains(row.get("source_id"), source_id):
                continue
            if company and not any(contains(company_text(row), term) for term in company_terms):
                continue
            if trial_id:
                trial_blob = _joined(row, ["registry_id", "parent_trial_id", "official_study_id", "china_trial_id", "notes"])
                if not contains(trial_blob, trial_id):
                    continue
            if pmid:
                pmid_blob = _joined(row, ["pmid", "registry_id", "url"])
                if not contains(pmid_blob, pmid):
                    continue
            if drug:
                drug_blob = _joined(row, ["drug_names", "intervention", "normalized_title_zh", "original_title", "notes"])
                if not any(contains(drug_blob, term) for term in drug_terms):
                    continue
            if source_type and not contains(row.get("source_type"), source_type):
                continue
            if status:
                status_blob = _joined(row, ["study_status", "verification_status", "authorisation_status", "regulatory_event_type"])
                if not contains(status_blob, status):
                    continue
            if text and not contains(_joined(row, SEARCH_FIELDS), text):
                continue
            matched.append(row)

        if study_name_query:
            study_name_key = norm(study_name_query)
            exact_matches = [
                row for row in matched if norm(row.get("study_name", "")).strip() == study_name_key
            ]
            if exact_matches:
                matched = exact_matches
            else:
                matched = [
                    row
                    for row in matched
                    if contains(
                        _joined(row, ["study_name", "normalized_title_zh", "original_title", "original_title_en"]),
                        study_name_query,
                    )
                ]

        return self.to_result_rows(matched) if normalized else matched

    def get_by_source_id(self, source_id: str, *, normalized: bool = True) -> dict[str, str] | None:
        rows = self.query(source_id=source_id, normalized=normalized)
        if not rows:
            return None
        return rows[0]

    def related_evidence(self, trial_id: str, *, latest_only: bool = False, normalized: bool = True) -> list[dict[str, str]]:
        return self.query(trial_id=trial_id, latest_only=latest_only, normalized=normalized)

    def to_result_rows(self, rows: Iterable[dict[str, str]]) -> list[dict[str, str]]:
        return [self.normalize_row(row) for row in rows]

    def normalize_row(self, row: dict[str, str]) -> dict[str, str]:
        risk_notes = "；".join(item for item in [row.get("scope_limitation", ""), row.get("notes", "")] if item)
        return {
            "source_id": row.get("source_id", ""),
            "company_name": row.get("company_cn") or row.get("company", ""),
            "drug_name": row.get("drug_names", ""),
            "trial_id": self.primary_trial_id(row),
            "pmid": row.get("pmid", ""),
            "study_name": row.get("study_name", ""),
            "source_type": row.get("source_type", ""),
            "evidence_level": row.get("evidence_level", ""),
            "study_status": row.get("study_status", ""),
            "verification_status": row.get("verification_status", ""),
            "regulatory_event_type": row.get("regulatory_event_type", ""),
            "authorisation_status": row.get("authorisation_status", ""),
            "marketing_authorisation_holder": row.get("marketing_authorisation_holder", ""),
            "title_original": row.get("original_title") or row.get("original_title_en", ""),
            "description_zh": row.get("normalized_title_zh", ""),
            "source_url": row.get("url", ""),
            "verified_at": row.get("verified_at", ""),
            "is_latest_evidence": row.get("is_latest_evidence", ""),
            "parent_trial_id": row.get("parent_trial_id", ""),
            "risk_notes": risk_notes,
        }

    def expand_company_terms(self, term: str) -> list[str]:
        term_key = norm(term)
        if not term_key:
            return []
        for group in COMPANY_ALIAS_GROUPS:
            keys = [norm(item) for item in group]
            if term_key in keys or any(term_key in key or key in term_key for key in keys):
                return group
        return [term]

    def expand_drug_terms(self, term: str, aliases: dict[str, list[str]] | None = None) -> list[str]:
        aliases = aliases or self.load_aliases()
        return expand_drug_terms(term, aliases)

    @staticmethod
    def primary_trial_id(row: dict[str, str]) -> str:
        for field in ["parent_trial_id", "registry_id", "official_study_id", "china_trial_id"]:
            value = row.get(field, "")
            if value.startswith("NCT"):
                return value
        return row.get("parent_trial_id") or row.get("registry_id", "")

    def _read_csv(self, path: Path) -> tuple[list[str], list[dict[str, str]]]:
        if not path.exists():
            raise SourceRegistryFileNotFound(f"Required source registry file not found: {_display_path(path)}")
        try:
            with path.open("r", encoding="utf-8", newline="") as fh:
                raw_rows = list(csv.reader(fh))
        except UnicodeDecodeError as exc:
            raise SourceRegistryStructureError(f"CSV is not valid UTF-8: {_display_path(path)}: {exc}") from exc
        except OSError as exc:
            raise SourceRegistryFileNotFound(f"Cannot read source registry file: {_display_path(path)}: {exc}") from exc

        if not raw_rows:
            raise SourceRegistryStructureError(f"CSV is empty: {_display_path(path)}")
        fieldnames = raw_rows[0]
        width = len(fieldnames)
        for line_no, row in enumerate(raw_rows[1:], start=2):
            if len(row) != width:
                raise SourceRegistryStructureError(
                    f"CSV field count mismatch in {_display_path(path)} line {line_no}: {len(row)} != {width}"
                )
        missing = [field for field in REQUIRED_FIELDS if field not in fieldnames]
        if missing:
            raise SourceRegistryStructureError(f"CSV missing required fields: {', '.join(missing)}")

        with path.open("r", encoding="utf-8", newline="") as fh:
            rows = list(csv.DictReader(fh))
        return fieldnames, rows

    def _read_aliases(self, path: Path) -> dict[str, list[str]]:
        if not path.exists():
            raise SourceRegistryFileNotFound(f"Required alias file not found: {_display_path(path)}")
        data = self._read_json_file(path)
        alias_map: dict[str, list[str]] = {}
        for entity in data.get("entities", []):
            aliases = [str(item) for item in entity.get("aliases", []) if str(item)]
            for alias in aliases:
                alias_map[norm(alias)] = aliases
        return alias_map

    def _read_json_file(self, path: Path) -> dict[str, object]:
        if not path.exists():
            raise SourceRegistryFileNotFound(f"Required config file not found: {_display_path(path)}")
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise SourceRegistryStructureError(f"JSON is invalid: {_display_path(path)}: {exc}") from exc
        except OSError as exc:
            raise SourceRegistryFileNotFound(f"Cannot read config file: {_display_path(path)}: {exc}") from exc
        if not isinstance(data, dict):
            raise SourceRegistryStructureError(f"JSON root must be an object: {_display_path(path)}")
        return data


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


def get_default_service() -> SourceRegistryService:
    return SourceRegistryService()
