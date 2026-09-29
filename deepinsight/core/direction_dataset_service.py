"""Read-only query service for the research-direction dataset.

The service reads the canonical normalized tables in ``data/template/`` plus the
direction catalog in ``config/direction_catalog.json``. Like
``source_registry_service`` it deliberately depends only on the standard library:
no model, vector-store, network or web-framework imports.
"""

from __future__ import annotations

import csv
import json
from collections import Counter, OrderedDict
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_TEMPLATE_DIR = PROJECT_ROOT / "data" / "template"
DEFAULT_CATALOG_PATH = PROJECT_ROOT / "config" / "direction_catalog.json"

TRACKED_TABLES = (
    "domains",
    "organizations",
    "assets",
    "indications",
    "studies",
    "study_identifiers",
    "publications",
    "sources",
    "facts",
    "relations",
)

TRIAL_SOURCE_TYPE = "CLINICAL_TRIAL_REGISTRY"
PUBLICATION_SOURCE_TYPE = "PUBMED_ARTICLE"


class DirectionDatasetError(Exception):
    """Base exception for direction dataset failures."""


class DirectionDatasetFileNotFound(DirectionDatasetError):
    """Raised when a required catalog or table file is missing."""


class DirectionDatasetStructureError(DirectionDatasetError):
    """Raised when the catalog or a table is malformed."""


def _norm(value: object) -> str:
    return str(value or "").casefold()


def _contains(haystack: object, needle: str) -> bool:
    return _norm(needle) in _norm(haystack)


def _display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(PROJECT_ROOT))
    except ValueError:
        return path.name


class DirectionDatasetService:
    """Direction roadmap plus the reviewed evidence records behind each direction."""

    def __init__(
        self,
        template_dir: str | Path | None = None,
        catalog_path: str | Path | None = None,
    ) -> None:
        self.template_dir = Path(template_dir) if template_dir else DEFAULT_TEMPLATE_DIR
        self.catalog_path = Path(catalog_path) if catalog_path else DEFAULT_CATALOG_PATH
        self._catalog: dict | None = None
        self._tables: dict[str, list[dict[str, str]]] | None = None
        self._records: list[dict[str, object]] | None = None
        self._direction_index: "OrderedDict[str, dict]" | None = None
        self._skipped_unverifiable = 0

    # ------------------------------------------------------------------ #
    # loading
    # ------------------------------------------------------------------ #
    def load_catalog(self) -> dict:
        if self._catalog is None:
            if not self.catalog_path.exists():
                raise DirectionDatasetFileNotFound(
                    f"Required direction catalog not found: {_display_path(self.catalog_path)}"
                )
            try:
                data = json.loads(self.catalog_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError as exc:
                raise DirectionDatasetStructureError(
                    f"Direction catalog is not valid JSON: {_display_path(self.catalog_path)}: {exc}"
                ) from exc
            if not isinstance(data, dict) or not isinstance(data.get("stages"), list):
                raise DirectionDatasetStructureError(
                    f"Direction catalog must contain a 'stages' list: {_display_path(self.catalog_path)}"
                )
            self._catalog = data
        return self._catalog

    def load_table(self, name: str) -> list[dict[str, str]]:
        tables = self._load_tables()
        return tables.get(name, [])

    def _load_tables(self) -> dict[str, list[dict[str, str]]]:
        if self._tables is None:
            tables: dict[str, list[dict[str, str]]] = {}
            for name in TRACKED_TABLES:
                path = self.template_dir / f"{name}.csv"
                if not path.exists():
                    tables[name] = []
                    continue
                try:
                    with path.open("r", encoding="utf-8", newline="") as fh:
                        reader = csv.DictReader(fh)
                        tables[name] = [dict(row) for row in reader]
                except UnicodeDecodeError as exc:
                    raise DirectionDatasetStructureError(
                        f"Table is not valid UTF-8: {_display_path(path)}: {exc}"
                    ) from exc
                except OSError as exc:
                    raise DirectionDatasetFileNotFound(f"Cannot read table {_display_path(path)}: {exc}") from exc
            self._tables = tables
        return self._tables

    # ------------------------------------------------------------------ #
    # catalog helpers
    # ------------------------------------------------------------------ #
    def direction_index(self) -> "OrderedDict[str, dict]":
        if self._direction_index is None:
            index: "OrderedDict[str, dict]" = OrderedDict()
            for stage in self.load_catalog()["stages"]:
                for direction in stage["directions"]:
                    index[direction["direction_id"]] = {
                        "direction_id": direction["direction_id"],
                        "direction_key": direction["direction_key"],
                        "name_zh": direction["name_zh"],
                        "name_en": direction.get("name_en", ""),
                        "indication_id": f"IND_{direction['direction_key'].upper()}",
                        "stage_id": stage["stage_id"],
                        "stage_index": stage["stage_index"],
                        "stage_name": stage["stage_name"],
                        "stage_title": stage.get("stage_title", ""),
                        "goal": stage["goal"],
                    }
            self._direction_index = index
        return self._direction_index

    # ------------------------------------------------------------------ #
    # record construction
    # ------------------------------------------------------------------ #
    def records(self) -> list[dict[str, object]]:
        if self._records is None:
            self._records = self._build_records()
        return self._records

    def _build_records(self) -> list[dict[str, object]]:
        tables = self._load_tables()
        direction_by_domain = {d["direction_id"]: d for d in self.direction_index().values()}

        # Prefer the curated Chinese display name; fall back to the raw sponsor
        # name from ClinicalTrials.gov when no authoritative Chinese name exists.
        org_names = {
            row.get("organization_id", ""): (row.get("display_name") or row.get("canonical_name") or "")
            for row in tables.get("organizations", [])
        }
        # Kept alongside the display name so search still matches the English form.
        org_names_en = {
            row.get("organization_id", ""): (row.get("canonical_name") or "")
            for row in tables.get("organizations", [])
        }
        asset_by_id = {
            row.get("asset_id", ""): (row.get("canonical_name") or row.get("generic_name") or row.get("development_code") or "")
            for row in tables.get("assets", [])
        }

        facts_by_source: dict[str, list[dict[str, str]]] = {}
        for fact in tables.get("facts", []):
            facts_by_source.setdefault(fact.get("source_id", ""), []).append(fact)

        assets_by_source: dict[str, list[str]] = {}
        for relation in tables.get("relations", []):
            if relation.get("relation_type") == "source_mentions_asset":
                asset_name = asset_by_id.get(relation.get("object_id", ""))
                if asset_name:
                    assets_by_source.setdefault(relation.get("source_id", ""), []).append(asset_name)

        source_by_id = {row.get("source_id", ""): row for row in tables.get("sources", [])}

        records: list[dict[str, object]] = []
        skipped_unverifiable = 0

        # ---- clinical trials -------------------------------------------------
        identifiers_by_study: dict[str, list[dict[str, str]]] = {}
        for identifier in tables.get("study_identifiers", []):
            identifiers_by_study.setdefault(identifier.get("study_id", ""), []).append(identifier)

        for study in tables.get("studies", []):
            direction = direction_by_domain.get(study.get("domain_id", ""))
            if not direction:
                continue
            identifiers = identifiers_by_study.get(study.get("study_id", ""), [])
            registry_ids = [
                item.get("identifier_value", "")
                for item in identifiers
                if str(item.get("identifier_type", "")).upper() == "NCT"
            ]
            registry_id = next((value for value in registry_ids if value), "")
            if not registry_id:
                registry_id = next(
                    (
                        item.get("identifier_value", "")
                        for item in identifiers
                        if str(item.get("identifier_value", "")).startswith("NCT")
                    ),
                    "",
                )
            # A study row may point at a publication source; always prefer the
            # identifier that resolves to a clinical-trial registry record.
            source_id = ""
            for item in identifiers:
                candidate = source_by_id.get(item.get("source_id", ""), {})
                if candidate.get("source_type") == TRIAL_SOURCE_TYPE:
                    source_id = item.get("source_id", "")
                    break
            if not source_id and identifiers:
                source_id = identifiers[0].get("source_id", "")
            if not source_id and registry_id:
                source_id = f"SRC_CTG_{registry_id}"

            source = source_by_id.get(source_id, {})
            # Trials must link to the registry record for their own identifier,
            # never to an unrelated source that happens to share the study row.
            url = source.get("url", "")
            if registry_id:
                url = f"https://clinicaltrials.gov/study/{registry_id}"
            if not url.startswith("http"):
                skipped_unverifiable += 1
                continue

            facts = {fact.get("predicate", ""): fact.get("object_value", "") for fact in facts_by_source.get(source_id, [])}
            assets = assets_by_source.get(source_id, [])
            if not assets and study.get("primary_asset_id"):
                primary_asset = asset_by_id.get(study.get("primary_asset_id", ""))
                if primary_asset:
                    assets = [primary_asset]
            records.append(
                {
                    "record_id": source_id or f"STUDY_{registry_id}" or study.get("study_id", ""),
                    "record_type": "clinical_trial",
                    "direction_id": direction["direction_id"],
                    "direction_name": direction["name_zh"],
                    "stage_id": direction["stage_id"],
                    "stage_index": direction["stage_index"],
                    "stage_name": direction["stage_name"],
                    "title": source.get("title_original", "") or study.get("study_name", ""),
                    "study_name": study.get("study_name", ""),
                    "company": org_names.get(study.get("sponsor_org_id", ""), ""),
                    "company_en": org_names_en.get(study.get("sponsor_org_id", ""), ""),
                    "assets": assets,
                    "phase": study.get("phase", ""),
                    "study_status": study.get("study_status", ""),
                    "registry_id": registry_id,
                    "pmid": "",
                    "doi": "",
                    "journal": "",
                    "enrollment": study.get("enrollment_actual") or study.get("enrollment_planned") or facts.get("enrollment_count", ""),
                    "conditions": facts.get("condition", ""),
                    "start_date": study.get("start_date", ""),
                    "completion_date": study.get("completion_date", ""),
                    "publication_date": source.get("publication_date", ""),
                    "source_last_updated": source.get("source_last_updated", ""),
                    "verified_at": source.get("verified_at", ""),
                    "verification_status": source.get("verification_status", ""),
                    "source_type": source.get("source_type", TRIAL_SOURCE_TYPE),
                    "url": url,
                }
            )

        # ---- publications ----------------------------------------------------
        for publication in tables.get("publications", []):
            direction = direction_by_domain.get(publication.get("domain_id", ""))
            if not direction:
                continue
            source_id = publication.get("source_id", "")
            source = source_by_id.get(source_id, {})
            pmid = str(publication.get("pmid", "") or "").strip()
            url = source.get("url", "")
            if pmid and not url.startswith("http"):
                url = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"
            if not url.startswith("http"):
                skipped_unverifiable += 1
                continue
            facts = {fact.get("predicate", ""): fact.get("object_value", "") for fact in facts_by_source.get(source_id, [])}
            records.append(
                {
                    "record_id": source_id or f"PUB_{pmid}",
                    "record_type": "publication",
                    "direction_id": direction["direction_id"],
                    "direction_name": direction["name_zh"],
                    "stage_id": direction["stage_id"],
                    "stage_index": direction["stage_index"],
                    "stage_name": direction["stage_name"],
                    "title": publication.get("title_original") or source.get("title_original", ""),
                    "study_name": "",
                    "company": "",
                    "company_en": "",
                    "assets": assets_by_source.get(source_id, []),
                    "phase": "",
                    "study_status": "",
                    "registry_id": "",
                    "pmid": pmid,
                    "doi": publication.get("doi", ""),
                    "journal": publication.get("journal", ""),
                    "enrollment": "",
                    "conditions": facts.get("publication_type", ""),
                    "start_date": "",
                    "completion_date": "",
                    "publication_date": publication.get("online_publication_date") or source.get("publication_date", ""),
                    "source_last_updated": source.get("source_last_updated", ""),
                    "verified_at": source.get("verified_at", ""),
                    "verification_status": source.get("verification_status", ""),
                    "source_type": source.get("source_type", PUBLICATION_SOURCE_TYPE),
                    "url": url,
                }
            )

        records.sort(
            key=lambda item: (
                item["stage_index"],
                str(item["direction_id"]),
                str(item["publication_date"] or item["source_last_updated"]),
                str(item["record_id"]),
            ),
            reverse=False,
        )
        self._skipped_unverifiable = skipped_unverifiable
        return records

    # ------------------------------------------------------------------ #
    # public API
    # ------------------------------------------------------------------ #
    def roadmap(self) -> dict[str, object]:
        records = self.records()
        by_direction: dict[str, Counter] = {}
        for record in records:
            counter = by_direction.setdefault(str(record["direction_id"]), Counter())
            counter[str(record["record_type"])] += 1
            counter["total"] += 1

        stages = []
        all_directions = self.direction_index()
        for stage in self.load_catalog()["stages"]:
            directions = []
            for direction in stage["directions"]:
                meta = all_directions[direction["direction_id"]]
                counter = by_direction.get(direction["direction_id"], Counter())
                directions.append(
                    {
                        "direction_id": meta["direction_id"],
                        "direction_key": meta["direction_key"],
                        "name_zh": meta["name_zh"],
                        "name_en": meta["name_en"],
                        "indication_id": meta["indication_id"],
                        "trial_count": counter.get("clinical_trial", 0),
                        "publication_count": counter.get("publication", 0),
                        "source_count": counter.get("total", 0),
                        "trial_sponsor_count": len(
                            {
                                record.get("company")
                                for record in records
                                if record["direction_id"] == meta["direction_id"] and record.get("company")
                            }
                        ),
                        "phase_counts": dict(
                            Counter(
                                record.get("phase", "")
                                for record in records
                                if record["direction_id"] == meta["direction_id"] and record.get("phase")
                            )
                        ),
                    }
                )
            stage_total = sum(d["source_count"] for d in directions)
            stages.append(
                {
                    "stage_id": stage["stage_id"],
                    "stage_index": stage["stage_index"],
                    "stage_name": stage["stage_name"],
                    "stage_title": stage.get("stage_title", ""),
                    "goal": stage["goal"],
                    "direction_count": len(directions),
                    "source_count": stage_total,
                    "directions": directions,
                }
            )

        return {
            "stages": stages,
            "total_stages": len(stages),
            "total_directions": len(all_directions),
            "total_records": len(records),
            "total_sources": len(records),
            "verification_status_counts": dict(Counter(str(r.get("verification_status", "")) for r in records)),
            "metadata": {
                "data_scope": "research_direction_evidence",
                "data_source": "data/template",
                "catalog": "config/direction_catalog.json",
                "interpretation_scope": "manually_reviewed_records_only",
                "excluded_unverifiable_records": self._skipped_unverifiable,
            },
        }

    def summary(self) -> dict[str, object]:
        records = self.records()
        return {
            "total_records": len(records),
            "trial_count": sum(1 for r in records if r["record_type"] == "clinical_trial"),
            "publication_count": sum(1 for r in records if r["record_type"] == "publication"),
            "direction_count": len(self.direction_index()),
            "stage_count": len(self.load_catalog()["stages"]),
            "records_per_direction": dict(
                Counter(str(r["direction_id"]) for r in records)
            ),
            "metadata": {
                "data_scope": "research_direction_evidence",
                "data_source": "data/template",
            },
        }

    def filter_options(self, direction_id: str | None = None) -> dict[str, list[str]]:
        records = self._filtered(direction_id=direction_id)
        return {
            "source_type": sorted({str(r.get("source_type", "")) for r in records if r.get("source_type")}),
            "phase": sorted({str(r.get("phase", "")) for r in records if r.get("phase")}),
            "study_status": sorted({str(r.get("study_status", "")) for r in records if r.get("study_status")}),
            "company": sorted({str(r.get("company", "")) for r in records if r.get("company")}),
            "stage": [f"{s['stage_name']}：{s.get('stage_title', '')}" for s in self.load_catalog()["stages"]],
            "direction": [f"{d['direction_id']}｜{d['name_zh']}" for d in self.direction_index().values()],
        }

    def resolve_direction_id(self, value: str | None) -> str:
        """Accept either a direction id (``DOM_X``) or its key (``x``)."""
        if not value:
            return ""
        key_map = {d["direction_key"]: d["direction_id"] for d in self.direction_index().values()}
        return key_map.get(str(value).strip().casefold(), str(value).strip())

    def _filtered(
        self,
        *,
        direction_id: str | None = None,
        stage_id: str | None = None,
        record_type: str | None = None,
        source_type: str | None = None,
        phase: str | None = None,
        study_status: str | None = None,
        company: str | None = None,
        text: str | None = None,
    ) -> list[dict[str, object]]:
        results = self.records()
        if direction_id:
            target = self.resolve_direction_id(direction_id)
            results = [r for r in results if _norm(r["direction_id"]) == _norm(target)]
        if stage_id:
            results = [r for r in results if _contains(r["stage_id"], stage_id)]
        if record_type:
            results = [r for r in results if _contains(r["record_type"], record_type)]
        if source_type:
            results = [r for r in results if _contains(r["source_type"], source_type)]
        if phase:
            results = [r for r in results if _contains(r["phase"], phase)]
        if study_status:
            results = [r for r in results if _contains(r["study_status"], study_status)]
        if company:
            results = [
                r for r in results if _contains(r["company"], company) or _contains(r.get("company_en", ""), company)
            ]
        if text:
            needle = text
            results = [
                r
                for r in results
                if _contains(r["title"], needle)
                or _contains(r["study_name"], needle)
                or _contains(r["company"], needle)
                or _contains(r.get("company_en", ""), needle)
                or _contains("；".join(str(a) for a in r["assets"]), needle)
                or _contains(r["registry_id"], needle)
                or _contains(r["pmid"], needle)
                or _contains(r["doi"], needle)
                or _contains(r["journal"], needle)
                or _contains(r["conditions"], needle)
                or _contains(r["record_id"], needle)
            ]
        return results

    def query(
        self,
        *,
        direction_id: str | None = None,
        stage_id: str | None = None,
        record_type: str | None = None,
        source_type: str | None = None,
        phase: str | None = None,
        study_status: str | None = None,
        company: str | None = None,
        text: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> dict[str, object]:
        matched = self._filtered(
            direction_id=direction_id,
            stage_id=stage_id,
            record_type=record_type,
            source_type=source_type,
            phase=phase,
            study_status=study_status,
            company=company,
            text=text,
        )
        limit = max(1, min(int(limit), 500))
        offset = max(0, int(offset))
        page = matched[offset : offset + limit]
        direction = None
        resolved_direction_id = self.resolve_direction_id(direction_id)
        if resolved_direction_id and resolved_direction_id in self.direction_index():
            direction = self.direction_index()[resolved_direction_id]
        return {
            "query": {
                "direction_id": resolved_direction_id,
                "stage_id": stage_id or "",
                "record_type": record_type or "",
                "source_type": source_type or "",
                "phase": phase or "",
                "study_status": study_status or "",
                "company": company or "",
                "text": text or "",
                "limit": limit,
                "offset": offset,
            },
            "direction": direction,
            "total": len(matched),
            "count": len(page),
            "offset": offset,
            "limit": limit,
            "has_more": offset + len(page) < len(matched),
            "items": page,
        }


_DEFAULT_SERVICE: DirectionDatasetService | None = None


def get_default_service() -> DirectionDatasetService:
    global _DEFAULT_SERVICE
    if _DEFAULT_SERVICE is None:
        _DEFAULT_SERVICE = DirectionDatasetService()
    return _DEFAULT_SERVICE
