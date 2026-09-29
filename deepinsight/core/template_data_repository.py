"""Read the normalized local data template without web or model dependencies.

The template keeps evidence in separate source, entity, study, fact and relation
tables.  This repository is the single place that joins those tables for the
application.  It deliberately performs no network access and never infers a
relation that is absent from ``relations.csv``.
"""

from __future__ import annotations

import csv
import re
from collections import defaultdict
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_TEMPLATE_DIR = PROJECT_ROOT / "data" / "template"
DEFAULT_RUNTIME_DOMAIN_ID: str | None = None
WEBSITE_VERIFICATION_STATUSES = {"verified"}
STUDY_RELATION_TYPES = {"source_supports", "source_describes_study"}
ORGANIZATION_RELATION_TYPES = {"source_about", "source_about_org"}


class TemplateDataError(Exception):
    """Base exception for normalized-template read failures."""


class TemplateDataFileNotFound(TemplateDataError):
    """Raised when a required normalized table is missing."""


class TemplateDataStructureError(TemplateDataError):
    """Raised when a normalized table cannot satisfy its table contract."""


TABLE_REQUIRED_FIELDS = {
    "domains": {"domain_id", "domain_name", "domain_type"},
    "indications": {"indication_id", "domain_id", "disease_name"},
    "sources": {"source_id", "source_type", "url", "verification_status"},
    "organizations": {"organization_id", "canonical_name", "display_name"},
    "organization_aliases": {"organization_id", "alias", "language"},
    "assets": {"asset_id", "canonical_name", "generic_name"},
    "asset_aliases": {"asset_id", "alias"},
    "studies": {"study_id", "domain_id", "study_name", "study_status"},
    "study_identifiers": {"study_id", "identifier_type", "identifier_value", "is_primary"},
    "publications": {"publication_id", "title_original", "study_id", "source_id"},
    "regulatory_events": {"regulatory_event_id", "source_id", "event_type", "authorization_status"},
    "facts": {"subject_id", "predicate", "object_value", "source_id"},
    "relations": {"subject_id", "relation_type", "object_id", "source_id", "relation_status"},
}

LEGACY_SOURCE_ID_RE = re.compile(r"(?:^|[;；\s])原始\s*source_id\s*=\s*([^;；\s]+)")
LEGACY_COMPANY_NAMES = {
    "ORG_HENGRUI": "恒瑞医药",
    "ORG_BEONE": "百济神州",
    "ORG_ASTRAZENECA": "阿斯利康",
}


def _display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path)


def _join(values: list[str]) -> str:
    return "; ".join(dict.fromkeys(value for value in values if value))


class TemplateDataRepository:
    """Load normalized tables and expose compatibility rows for the evidence API."""

    def __init__(self, template_dir: str | Path | None = None) -> None:
        self.template_dir = Path(template_dir) if template_dir else DEFAULT_TEMPLATE_DIR
        self._tables: dict[str, list[dict[str, str]]] = {}

    def load_table(self, name: str) -> list[dict[str, str]]:
        if name not in TABLE_REQUIRED_FIELDS:
            raise ValueError(f"Unsupported normalized table: {name}")
        if name not in self._tables:
            self._tables[name] = self._read_table(name)
        return [dict(row) for row in self._tables[name]]

    def source_rows(self, *, domain_id: str | None = DEFAULT_RUNTIME_DOMAIN_ID) -> list[dict[str, str]]:
        """Return source records flattened into the existing evidence-service contract.

        ``domain_id`` is optional. The website default is deliberately cross-domain:
        the normalized template is the canonical website dataset, rather than an
        opt-in supplement to the legacy NSCLC CSV.

        A row is emitted only when it has an HTTP(S) source URL, a known
        verification status, and at least one confirmed explicit relation. This
        prevents rows with unresolved or detached provenance from being displayed.
        """
        sources = self.load_table("sources")
        organizations = self._by_id("organizations", "organization_id")
        assets = self._by_id("assets", "asset_id")
        asset_aliases = self._group_by("asset_aliases", "asset_id")
        studies = self._by_id("studies", "study_id")
        identifiers = self._group_by("study_identifiers", "study_id")
        publications = self._group_by("publications", "source_id")
        regulatory_events = self._group_by("regulatory_events", "source_id")
        facts = self._group_by("facts", "source_id")
        relations = self._group_by("relations", "source_id")
        supporting_sources = self._group_relations_by_object(*STUDY_RELATION_TYPES)
        template_to_legacy_id = {
            source["source_id"]: self._legacy_source_id(source) for source in sources
        }

        rows: list[dict[str, str]] = []
        for source in sources:
            source_id = source["source_id"]
            source_relations = relations.get(source_id, [])
            confirmed_relations = [
                relation for relation in source_relations if relation.get("relation_status") == "confirmed"
            ]
            if not self._is_website_eligible(source, source_relations, confirmed_relations):
                continue
            study_ids = [
                relation["object_id"]
                for relation in confirmed_relations
                if relation["relation_type"] in STUDY_RELATION_TYPES
            ]
            study = studies.get(study_ids[0], {}) if study_ids else {}
            if domain_id and study and study.get("domain_id") != domain_id:
                continue
            if domain_id and not study:
                # Non-study evidence is retained only when an explicit source relation
                # puts it in the requested domain.
                source_domains = {relation.get("domain_id", "") for relation in source_relations}
                if domain_id not in source_domains:
                    continue
            source_domain_id = study.get("domain_id", "") or next(
                (relation.get("domain_id", "") for relation in confirmed_relations if relation.get("domain_id")), ""
            )

            about_org_ids = [
                relation["object_id"]
                for relation in confirmed_relations
                if relation["relation_type"] in ORGANIZATION_RELATION_TYPES
            ]
            organization = organizations.get(about_org_ids[0], {}) if about_org_ids else {}
            asset_rows = [
                assets[relation["object_id"]]
                for relation in confirmed_relations
                if relation["relation_type"] == "source_mentions_asset" and relation["object_id"] in assets
            ]
            source_facts = {fact["predicate"]: fact["object_value"] for fact in facts.get(source_id, [])}
            publication = publications.get(source_id, [{}])[0]
            regulatory = regulatory_events.get(source_id, [{}])[0]
            primary_identifier = self._primary_identifier(identifiers.get(study.get("study_id", ""), []))
            legacy_source_id = self._legacy_source_id(source)
            related_source_ids = [
                template_to_legacy_id.get(relation["source_id"], relation["source_id"])
                for study_id in study_ids
                for relation in supporting_sources.get(study_id, [])
                if relation.get("source_id") != source_id
            ]
            compatibility_notes = [source.get("notes", "")]
            if source_facts.get("analysis_stage"):
                compatibility_notes.append(f"分析阶段：{source_facts['analysis_stage']}。")
            if related_source_ids and primary_identifier:
                compatibility_notes.append(
                    f"关联研究 {primary_identifier} 的来源 {', '.join(dict.fromkeys(related_source_ids))} "
                    "与本来源共同支持同一研究，证据来源不重复计数。"
                )
            supersedes = next(
                (
                    relation["object_id"]
                    for relation in confirmed_relations
                    if relation["relation_type"] == "supersedes_source" and relation.get("object_id")
                ),
                "",
            )

            company = LEGACY_COMPANY_NAMES.get(
                organization.get("organization_id", ""),
                organization.get("display_name") or organization.get("canonical_name", ""),
            )
            title_original = source.get("title_original") or publication.get("title_original", "")
            normalized_title = publication.get("title_normalized", "")
            if study.get("study_name"):
                if publication:
                    normalized_title = (
                        f"{study['study_name']} 主要结果论文："
                        f"{normalized_title or publication.get('title_original', '')}"
                    )
                elif title_original:
                    normalized_title = f"{study['study_name']}：{title_original}"
            scope_limitation = _join(
                [source.get("source_scope", ""), source_facts.get("scope_limitation", "")]
            )
            row = {
                "source_id": legacy_source_id,
                "template_source_id": source_id,
                "domain_id": source_domain_id,
                "company": company,
                "company_cn": company,
                "company_display_name": organization.get("display_name", ""),
                "source_type": source.get("publisher") or source.get("source_type", ""),
                "template_source_type": source.get("source_type", ""),
                "url": source.get("url", ""),
                "registry_id": primary_identifier,
                "parent_trial_id": primary_identifier,
                "pmid": publication.get("pmid", ""),
                "study_name": study.get("study_name", ""),
                "drug_names": _join(
                    [
                        value
                        for asset in asset_rows
                        for value in [
                            asset.get("canonical_name", ""),
                            asset.get("generic_name", ""),
                            asset.get("development_code", ""),
                            asset.get("brand_name", ""),
                            *[alias.get("alias", "") for alias in asset_aliases.get(asset.get("asset_id", ""), [])],
                        ]
                    ]
                ),
                "study_status": source_facts.get("study_status") or study.get("study_status", ""),
                "verification_status": self._legacy_verification_status(source.get("verification_status", "")),
                "authorisation_status": regulatory.get("authorization_status", ""),
                "regulatory_event_type": regulatory.get("event_type", ""),
                "marketing_authorisation_holder": self._organization_name(
                    organizations.get(regulatory.get("holder_org_id", ""), {})
                ),
                "original_title": title_original,
                "normalized_title_zh": normalized_title,
                "publication_date": source.get("publication_date") or publication.get("online_publication_date", ""),
                "source_last_updated": source.get("source_last_updated", ""),
                "verified_at": source.get("verified_at", ""),
                "is_latest_evidence": source_facts.get("is_latest_evidence", ""),
                "analysis_stage": source_facts.get("analysis_stage") or publication.get("analysis_stage", ""),
                "evidence_version": source_facts.get("evidence_version", ""),
                "supersedes_source_id": template_to_legacy_id.get(supersedes, supersedes),
                "population": source_facts.get("population", ""),
                "intervention": source_facts.get("intervention", ""),
                "regimen_detail": source_facts.get("regimen_detail", ""),
                "biomarker_requirements": source_facts.get("biomarker_requirements", ""),
                "scope_limitation": scope_limitation,
                "notes": _join(compatibility_notes),
                "disease": "非小细胞肺癌（NSCLC）" if domain_id == "DOM_NSCLC" else "",
            }
            rows.append(row)
        return rows

    def data_paths(self) -> list[Path]:
        """Return all normalized input files used by this repository."""
        return [self.template_dir / f"{name}.csv" for name in sorted(TABLE_REQUIRED_FIELDS)]

    def _read_table(self, name: str) -> list[dict[str, str]]:
        path = self.template_dir / f"{name}.csv"
        if not path.exists():
            raise TemplateDataFileNotFound(f"Required normalized table not found: {_display_path(path)}")
        try:
            with path.open(encoding="utf-8-sig", newline="") as handle:
                reader = csv.DictReader(handle)
                fieldnames = set(reader.fieldnames or [])
                missing = TABLE_REQUIRED_FIELDS[name] - fieldnames
                if missing:
                    raise TemplateDataStructureError(
                        f"Normalized table missing required fields: {name}.csv: {', '.join(sorted(missing))}"
                    )
                return [{key: value or "" for key, value in row.items()} for row in reader]
        except UnicodeDecodeError as exc:
            raise TemplateDataStructureError(f"Normalized table is not UTF-8: {_display_path(path)}") from exc
        except OSError as exc:
            raise TemplateDataFileNotFound(f"Cannot read normalized table: {_display_path(path)}: {exc}") from exc

    def _by_id(self, name: str, key: str) -> dict[str, dict[str, str]]:
        return {row[key]: row for row in self.load_table(name) if row.get(key)}

    def _group_by(self, name: str, key: str) -> dict[str, list[dict[str, str]]]:
        grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
        for row in self.load_table(name):
            if row.get(key):
                grouped[row[key]].append(row)
        return grouped

    def _group_relations_by_object(self, *relation_types: str) -> dict[str, list[dict[str, str]]]:
        grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
        for row in self.load_table("relations"):
            if row.get("relation_type") in relation_types and row.get("relation_status") == "confirmed":
                grouped[row.get("object_id", "")].append(row)
        return grouped

    @staticmethod
    def _is_website_eligible(
        source: dict[str, str],
        source_relations: list[dict[str, str]],
        confirmed_relations: list[dict[str, str]],
    ) -> bool:
        """Keep only source rows with explicit, usable provenance for the website."""
        return (
            source.get("url", "").startswith(("https://", "http://"))
            and source.get("verification_status", "") in WEBSITE_VERIFICATION_STATUSES
            and bool(confirmed_relations)
            and all(relation.get("relation_status") == "confirmed" for relation in source_relations)
        )

    @staticmethod
    def _legacy_source_id(source: dict[str, str]) -> str:
        match = LEGACY_SOURCE_ID_RE.search(source.get("notes", ""))
        return match.group(1) if match else source["source_id"]

    @staticmethod
    def _legacy_verification_status(value: str) -> str:
        return "已人工核验" if value == "verified" else value

    @staticmethod
    def _organization_name(organization: dict[str, str]) -> str:
        return LEGACY_COMPANY_NAMES.get(
            organization.get("organization_id", ""),
            organization.get("display_name") or organization.get("canonical_name", ""),
        )

    @staticmethod
    def _primary_identifier(rows: list[dict[str, str]]) -> str:
        if not rows:
            return ""
        primary = next((row for row in rows if row.get("is_primary", "").lower() == "true"), rows[0])
        return primary.get("identifier_value", "")
