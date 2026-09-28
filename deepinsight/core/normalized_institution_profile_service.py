"""Institution research profiles backed only by normalized template tables."""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

from deepinsight.core.evidence_chain_service import EvidenceChainService
from deepinsight.core.source_registry_service import NormalizedSourceRegistryService, norm
from deepinsight.core.template_data_repository import TemplateDataRepository


class NormalizedInstitutionProfileService:
    """Build conservative profiles for companies, hospitals, universities, and research bodies."""

    def __init__(self, repository: TemplateDataRepository | None = None, chain_service: EvidenceChainService | None = None) -> None:
        self.repository = repository or TemplateDataRepository()
        self.source_service = NormalizedSourceRegistryService()
        self.source_service.repository = self.repository
        self.chain_service = chain_service or EvidenceChainService(source_registry_service=self.source_service)

    def available_institutions(self) -> list[dict[str, str]]:
        return [self._institution_card(row) for row in self.repository.load_table("organizations")]

    def build_profile(self, identifier: str) -> dict[str, Any]:
        institution = self._find_institution(identifier)
        if not institution:
            return {"institution": {}, "summary": {}, "limitations": ["当前数据不足，未找到该机构。"]}
        oid = institution["organization_id"]
        relations = [row for row in self.repository.load_table("relations") if row.get("relation_status") == "confirmed"]
        studies = [row for row in self.repository.load_table("studies") if row.get("sponsor_org_id") == oid]
        study_ids = {row["study_id"] for row in studies}
        source_ids = {
            row.get("source_id", "") for row in relations
            if row.get("relation_type") in {"source_about", "source_about_org"} and row.get("object_id") == oid
        }
        source_ids.update(
            row.get("source_id", "") for row in relations
            if row.get("relation_type") in {"source_describes_study", "source_supports"} and row.get("object_id") in study_ids
        )
        source_rows = [row for row in self.source_service.load_rows() if row.get("template_source_id") in source_ids]
        source_by_id = {row.get("source_id", ""): row for row in source_rows}
        study_source_ids: dict[str, set[str]] = defaultdict(set)
        for relation in relations:
            if relation.get("relation_type") in {"source_describes_study", "source_supports"} and relation.get("object_id") in study_ids:
                source = next((item for item in source_rows if item.get("template_source_id") == relation.get("source_id")), None)
                if source:
                    study_source_ids[relation["object_id"]].add(source.get("source_id", ""))
        domains = {row["domain_id"]: row for row in self.repository.load_table("domains")}
        stage_names = {
            row["domain_id"]: row.get("domain_name", "")
            for row in domains.values()
            if row.get("domain_type") in {"research_stage", "stage"}
        }
        indications = {row["indication_id"]: row for row in self.repository.load_table("indications")}
        assets = {row["asset_id"]: row for row in self.repository.load_table("assets")}
        identifiers = defaultdict(list)
        for row in self.repository.load_table("study_identifiers"):
            if row.get("study_id") in study_ids and row.get("identifier_value"):
                identifiers[row["study_id"]].append(row["identifier_value"])
        research = []
        for study in studies:
            ids = identifiers.get(study["study_id"], [])
            source_list = sorted(study_source_ids.get(study["study_id"], set()))
            asset = assets.get(study.get("primary_asset_id", ""), {})
            research.append({
                "study_id": study["study_id"], "chain_id": f"trial:{ids[0] if ids else study['study_id']}", "study_name": study.get("study_name", ""),
                "stage": stage_names.get(domains.get(study.get("domain_id", ""), {}).get("parent_domain_id", ""), domains.get(study.get("domain_id", ""), {}).get("parent_domain_id", "")),
                "direction": domains.get(study.get("domain_id", ""), {}).get("display_name", study.get("domain_id", "")),
                "study_status": study.get("study_status", ""), "phase": study.get("phase", ""),
                "identifiers": ids, "indication": indications.get(study.get("primary_indication_id", ""), {}).get("display_name", ""),
                "asset": asset.get("display_name", asset.get("canonical_name", "")),
                "start_date": study.get("start_date", ""), "primary_completion_date": study.get("primary_completion_date", ""),
                "source_ids": source_list,
                "chain_status": "formed" if len(source_list) >= 2 else ("single_source" if len(source_list) == 1 else "relationship_insufficient"),
            })
        asset_ids = {row.get("primary_asset_id", "") for row in studies if row.get("primary_asset_id")}
        asset_ids.update(row.get("object_id", "") for row in relations if row.get("relation_type") == "source_mentions_asset" and row.get("source_id") in {item.get("template_source_id") for item in source_rows})
        directions = {row.get("domain_id", "") for row in studies if row.get("domain_id")}
        regulatory = [row for row in self.repository.load_table("regulatory_events") if row.get("holder_org_id") == oid or row.get("asset_id") in asset_ids]
        gaps = [{"study_id": item["study_id"], "description": "当前没有指向该研究的已确认来源关系，尚未形成证据链。"} for item in research if item["chain_status"] == "relationship_insufficient"]
        regulatory_chains = []
        for event in regulatory:
            event_sources = [self._source_card(row) for row in source_rows if row.get("template_source_id") == event.get("source_id")]
            regulatory_chains.append({
                "chain_id": f"projected:regulatory:{event.get('regulatory_event_id', '')}",
                "chain_name": event.get("event_type", "监管事件"),
                "asset_id": event.get("asset_id", ""),
                "source_count": len(event_sources),
                "counting_note": "仅展示监管事件表与机构明确关联的来源。",
                "related_trial_ids": [], "sources": event_sources,
            })
        summary = {
            "source_count": len(source_rows), "sponsored_study_count": len(studies),
            "direction_count": len(directions), "asset_count": len(asset_ids),
            "verified_source_count": sum(row.get("verification_status") in {"verified", "已人工核验", "partially_verified", "api_harvested"} for row in source_rows),
            "api_harvested_source_count": sum(row.get("verification_status") == "api_harvested" for row in source_rows),
            "regulatory_event_count": len(regulatory), "evidence_gap_count": len(gaps),
        }
        if not source_rows and not studies:
            coverage_status = "entity_only"
        elif not source_rows:
            coverage_status = "research_only"
        else:
            coverage_status = "covered"
        return {
            "institution": self._institution_card(institution), "summary": summary,
            "coverage_status": coverage_status, "research": research,
            "sources": [self._source_card(row) for row in source_rows],
            "regulatory_events": regulatory, "regulatory_chains": regulatory_chains, "evidence_gaps": gaps,
            "independent_sources": [self._source_card(row) for row in source_rows],
            "unresolved_links": gaps,
            "source_type_distribution": self._distribution(source_rows, "source_type"),
            "study_status_distribution": self._distribution(studies, "study_status"),
            "metadata": {"data_scope": "eligible_normalized_research_evidence", "data_backend": "normalized_template"},
            "limitations": [
                "本画像仅反映规范化数据中已确认的机构、研究和来源覆盖，不代表机构整体研发实力。",
                "研究机构、医院和大学显示研究参与及申办覆盖，不作为企业竞争力评价。",
                "没有明确关系的研究保留为关系缺口，不自动补充证据链。",
            ],
        }

    def _find_institution(self, identifier: str) -> dict[str, str] | None:
        key = norm(identifier)
        organizations = self.repository.load_table("organizations")
        exact = next((row for row in organizations if key in {norm(row.get("organization_id")), norm(row.get("canonical_name")), norm(row.get("display_name"))}), None)
        if exact:
            return exact
        aliases = [row for row in self.repository.load_table("organization_aliases") if key and norm(row.get("alias")) == key]
        alias_org_ids = {row.get("organization_id") for row in aliases}
        # When a curated/manual alias and a harvest-generated duplicate coexist,
        # use the alias carrying source provenance. Do not collapse unprovenanced
        # duplicate entities by fuzzy name matching.
        if len(alias_org_ids) > 1:
            sourced = {row.get("organization_id") for row in aliases if row.get("source_id")}
            if len(sourced) == 1:
                alias_org_ids = sourced
        if len(alias_org_ids) == 1:
            org_id = next(iter(alias_org_ids))
            return next((row for row in organizations if row.get("organization_id") == org_id), None)
        return None

    @staticmethod
    def _institution_card(row: dict[str, str]) -> dict[str, str]:
        return {key: row.get(key, "") for key in ["organization_id", "canonical_name", "display_name", "organization_type", "country_or_region", "website", "status"]}

    @staticmethod
    def _source_card(row: dict[str, str]) -> dict[str, str]:
        return {key: row.get(key, "") for key in ["source_id", "company", "company_display_name", "source_type", "verification_status", "study_status", "study_name", "registry_id", "title_original", "normalized_title_zh", "source_url", "verified_at"]}

    @staticmethod
    def _distribution(rows: list[dict[str, str]], key: str) -> list[dict[str, Any]]:
        counts = Counter(row.get(key, "") or "未填写或不适用" for row in rows)
        return [{"label": label, "count": count} for label, count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))]
