"""Read-only browse service for the normalized research-data template."""

from __future__ import annotations

from typing import Any

from deepinsight.core.template_data_repository import TemplateDataRepository


class NormalizedDataService:
    """Expose sources and explicit entity relations without inferred joins."""

    def __init__(self, repository: TemplateDataRepository | None = None) -> None:
        self.repository = repository or TemplateDataRepository()

    def catalog(self) -> dict[str, Any]:
        return {
            "domains": self.repository.load_table("domains"),
            "counts": {
                name: len(self.repository.load_table(name))
                for name in ["sources", "organizations", "assets", "studies", "publications", "regulatory_events", "facts", "relations"]
            },
        }

    def search_sources(self, *, query: str = "", domain_id: str = "", category: str = "", limit: int = 50) -> dict[str, Any]:
        query_key = query.casefold().strip()
        rows = self.repository.source_rows(domain_id=None)
        items = []
        for row in rows:
            if domain_id and row.get("domain_id") != domain_id:
                continue
            if category and row.get("display_category") != category:
                continue
            blob = " ".join(str(row.get(key, "")) for key in [
                "source_id", "company", "drug_names", "registry_id", "study_name", "original_title", "normalized_title_zh", "source_type",
            ]).casefold()
            if query_key and query_key not in blob:
                continue
            items.append(self._source_card(row))
        return {"query": {"q": query, "domain_id": domain_id, "category": category, "limit": limit}, "count": min(len(items), limit), "items": items[:limit]}

    def source_detail(self, source_id: str) -> dict[str, Any]:
        row = self._source_by_id(source_id)
        if not row:
            return {}
        template_id = row["template_source_id"]
        facts = [fact for fact in self.repository.load_table("facts") if fact.get("source_id") == template_id]
        relations = [relation for relation in self.repository.load_table("relations") if relation.get("source_id") == template_id]
        return {
            "source": self._source_card(row),
            "facts": [self._fact_view(fact) for fact in facts],
            "relations": [self._relation_view(relation) for relation in relations],
        }

    def organization_detail(self, identifier: str) -> dict[str, Any]:
        organization = self._find("organizations", "organization_id", identifier, ["canonical_name", "display_name"])
        if not organization:
            return {}
        source_ids = self._relation_sources("source_about", organization["organization_id"])
        sources = [self._source_card(row) for row in self.repository.source_rows(domain_id=None) if row["template_source_id"] in source_ids]
        studies = [study for study in self.repository.load_table("studies") if study.get("sponsor_org_id") == organization["organization_id"]]
        return {"organization": organization, "sources": sources, "studies": studies}

    def asset_detail(self, identifier: str) -> dict[str, Any]:
        asset = self._find("assets", "asset_id", identifier, ["canonical_name", "generic_name", "development_code", "brand_name"])
        if not asset:
            return {}
        source_ids = self._relation_sources("source_mentions_asset", asset["asset_id"])
        studies = [study for study in self.repository.load_table("studies") if study.get("primary_asset_id") == asset["asset_id"]]
        studies.extend(
            self._subjects_for_relation("study_intervention", asset["asset_id"], "STUDY_")
        )
        return {
            "asset": asset,
            "sources": [self._source_card(row) for row in self.repository.source_rows(domain_id=None) if row["template_source_id"] in source_ids],
            "studies": self._unique_by(studies, "study_id"),
        }

    def study_detail(self, identifier: str) -> dict[str, Any]:
        study = self._find("studies", "study_id", identifier, ["study_name"])
        if not study:
            for item in self.repository.load_table("study_identifiers"):
                if item.get("identifier_value", "").casefold() == identifier.casefold():
                    study = next((row for row in self.repository.load_table("studies") if row["study_id"] == item["study_id"]), None)
                    break
        if not study:
            return {}
        source_ids = self._relation_sources("source_supports", study["study_id"])
        publications = [item for item in self.repository.load_table("publications") if item.get("study_id") == study["study_id"]]
        return {
            "study": study,
            "identifiers": [item for item in self.repository.load_table("study_identifiers") if item.get("study_id") == study["study_id"]],
            "publications": publications,
            "sources": [self._source_card(row) for row in self.repository.source_rows(domain_id=None) if row["template_source_id"] in source_ids],
        }

    def _source_by_id(self, source_id: str) -> dict[str, str] | None:
        key = source_id.casefold().strip()
        return next((row for row in self.repository.source_rows(domain_id=None) if row["source_id"].casefold() == key or row["template_source_id"].casefold() == key), None)

    def _source_card(self, row: dict[str, str]) -> dict[str, str]:
        return {key: row.get(key, "") for key in [
            "source_id", "template_source_id", "domain_id", "company", "company_display_name", "drug_names", "registry_id", "study_name",
            "source_type", "template_source_type", "display_category", "display_category_label", "original_title", "normalized_title_zh", "url", "publication_date", "verified_at",
            "verification_status", "study_status", "authorisation_status", "regulatory_event_type", "is_latest_evidence", "scope_limitation",
        ]}

    def _relation_sources(self, relation_type: str, object_id: str) -> set[str]:
        return {
            item["source_id"] for item in self.repository.load_table("relations")
            if item.get("relation_type") == relation_type and item.get("object_id") == object_id and item.get("relation_status") == "confirmed"
        }

    def _subjects_for_relation(self, relation_type: str, object_id: str, prefix: str) -> list[dict[str, str]]:
        ids = {
            item["subject_id"] for item in self.repository.load_table("relations")
            if item.get("relation_type") == relation_type and item.get("object_id") == object_id and item.get("subject_id", "").startswith(prefix)
        }
        return [item for item in self.repository.load_table("studies") if item.get("study_id") in ids]

    def _relation_view(self, relation: dict[str, str]) -> dict[str, str]:
        return {key: relation.get(key, "") for key in ["relation_type", "subject_id", "object_id", "relation_status", "confidence_level", "scope_note"]}

    def _fact_view(self, fact: dict[str, str]) -> dict[str, str]:
        return {key: fact.get(key, "") for key in ["predicate", "object_value", "event_date", "verification_status", "confidence_level", "scope_note"]}

    def _find(self, table: str, id_field: str, value: str, names: list[str]) -> dict[str, str] | None:
        key = value.casefold().strip()
        return next((row for row in self.repository.load_table(table) if any(row.get(field, "").casefold() == key for field in [id_field, *names])), None)

    @staticmethod
    def _unique_by(items: list[dict[str, str]], key: str) -> list[dict[str, str]]:
        seen: set[str] = set()
        return [item for item in items if item.get(key) and not (item[key] in seen or seen.add(item[key]))]
