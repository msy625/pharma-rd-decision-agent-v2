"""Two explicit brief projections for normalized institutions and disease directions."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from deepinsight.core.normalized_institution_profile_service import NormalizedInstitutionProfileService
from deepinsight.core.normalized_institution_timeline_service import NormalizedInstitutionTimelineService
from deepinsight.core.template_data_repository import TemplateDataRepository


class NormalizedInstitutionBriefService:
    def __init__(self, repository: TemplateDataRepository | None = None) -> None:
        self.repository = repository or TemplateDataRepository()
        self.profile_service = NormalizedInstitutionProfileService(self.repository)
        self.timeline_service = NormalizedInstitutionTimelineService(self.repository)

    def available_institutions(self) -> list[dict[str, str]]:
        return self.profile_service.available_institutions()

    def available_directions(self) -> list[dict[str, str]]:
        return [{"domain_id": row["domain_id"], "domain_name": row.get("domain_name", "")} for row in self.repository.load_table("domains")]

    def build_institution_brief(self, identifier: str) -> dict[str, Any]:
        profile = self.profile_service.build_profile(identifier)
        institution = profile.get("institution") or {}
        if not institution.get("organization_id"):
            raise ValueError(f"未知机构：{identifier}")
        timeline = self.timeline_service.build_timeline(institution=institution["organization_id"])
        summary = profile.get("summary") or {}
        return {"brief_id": f"institution-brief:{institution['organization_id']}", "brief_type": "institution_research", "title": f"{institution.get('display_name') or institution.get('canonical_name')} · 机构研发画像简报", "subject": {"institution": institution, "data_scope": "all_normalized_organizations"}, "overview": summary, "research": profile.get("research", []), "sources": profile.get("sources", []), "regulatory_events": profile.get("regulatory_events", []), "timeline": timeline, "evidence_gaps": profile.get("evidence_gaps", []), "limitations": profile.get("limitations", []), "metadata": self._metadata("NormalizedInstitutionProfileService", "NormalizedInstitutionTimelineService")}

    def build_direction_brief(self, domain_id: str) -> dict[str, Any]:
        domains = {row["domain_id"]: row for row in self.repository.load_table("domains")}
        domain = domains.get(domain_id)
        if not domain:
            raise ValueError(f"未知疾病方向：{domain_id}")
        studies = [row for row in self.repository.load_table("studies") if row.get("domain_id") == domain_id]
        study_ids = {row["study_id"] for row in studies}
        orgs = {row["organization_id"]: row for row in self.repository.load_table("organizations")}
        indications = {row["indication_id"]: row for row in self.repository.load_table("indications")}
        identifiers: dict[str, list[str]] = {}
        for row in self.repository.load_table("study_identifiers"):
            if row.get("study_id") in study_ids and row.get("identifier_value"):
                identifiers.setdefault(row["study_id"], []).append(row["identifier_value"])
        research = [{"organization": orgs.get(row.get("sponsor_org_id"), {}), "study_id": row.get("study_id", ""), "study_name": row.get("study_name", ""), "phase": row.get("phase", ""), "status": row.get("study_status", ""), "identifiers": identifiers.get(row["study_id"], []), "indication": indications.get(row.get("primary_indication_id", ""), {}).get("disease_name", ""), "start_date": row.get("start_date", ""), "primary_completion_date": row.get("primary_completion_date", "")} for row in studies]
        relations = [row for row in self.repository.load_table("relations") if row.get("relation_status") == "confirmed"]
        relation_sources = {row.get("source_id") for row in relations if row.get("relation_type") in {"source_describes_study", "source_supports"} and row.get("object_id") in study_ids}
        publications = [row for row in self.repository.load_table("publications") if row.get("study_id") in study_ids]
        relation_sources.update(row.get("source_id") for row in publications if row.get("source_id"))
        regulatory_events = [row for row in self.repository.load_table("regulatory_events") if row.get("domain_id") == domain_id]
        relation_sources.update(row.get("source_id") for row in regulatory_events if row.get("source_id"))
        eligible_sources = self.repository.source_rows(domain_id=None)
        sources = [self._source_card(row) for row in eligible_sources if row.get("template_source_id") in relation_sources]
        display_source_id = {row.get("template_source_id", ""): row.get("source_id", "") for row in eligible_sources}
        timeline_events = []
        for row in studies:
            for field, label in (("start_date", "研究开始"), ("primary_completion_date", "主要完成"), ("completion_date", "研究完成")):
                if row.get(field):
                    timeline_events.append({"date": {"value": row[field], "precision": "day" if len(row[field]) == 10 else "month", "semantic": label}, "event_type": "study_date", "event_type_label": label, "title": row.get("study_name") or row["study_id"], "study_id": row["study_id"], "source_id": ""})
        for row in publications:
            raw_date = row.get("online_publication_date") or row.get("issue_year", "")
            if raw_date:
                timeline_events.append({"date": {"value": raw_date, "precision": "day" if len(raw_date) == 10 else ("year" if len(raw_date) == 4 else "month"), "semantic": "论文发表"}, "event_type": "publication_date", "event_type_label": "论文发表", "title": row.get("title_normalized") or row.get("title_original") or row.get("publication_id"), "study_id": row.get("study_id", ""), "source_id": display_source_id.get(row.get("source_id", ""), row.get("source_id", ""))})
        for row in regulatory_events:
            if row.get("event_date"):
                timeline_events.append({"date": {"value": row["event_date"], "precision": "day" if len(row["event_date"]) == 10 else "month", "semantic": "监管事件"}, "event_type": "regulatory_date", "event_type_label": "监管事件", "title": row.get("event_type") or row.get("regulatory_event_id", ""), "study_id": "", "source_id": display_source_id.get(row.get("source_id", ""), row.get("source_id", ""))})
        timeline_events.sort(key=lambda row: row["date"]["value"], reverse=True)
        return {"brief_id": f"direction-brief:{domain_id}", "brief_type": "disease_direction_evidence", "title": f"{domain.get('domain_name', domain_id)} · 疾病方向证据简报", "subject": {"domain_id": domain_id, "domain_name": domain.get("domain_name", ""), "data_scope": "normalized_direction_records"}, "overview": {"study_count": len(studies), "organization_count": len({row.get('sponsor_org_id') for row in studies if row.get('sponsor_org_id')}), "source_count": len(sources)}, "research": research, "sources": sources, "regulatory_events": regulatory_events, "timeline": {"events": timeline_events, "summary": {"event_count": len(timeline_events)}}, "evidence_gaps": [], "limitations": ["仅汇总该疾病方向的结构化研究和明确来源覆盖，不输出机构排名或疗效结论。", "缺少明确关系的记录不自动补入研究或证据链。"], "metadata": self._metadata("TemplateDataRepository")}

    @staticmethod
    def _source_card(row: dict[str, str]) -> dict[str, str]:
        return {"source_id": row.get("source_id", ""), "title": row.get("original_title") or row.get("normalized_title_zh") or row.get("study_name") or "", "source_type": row.get("source_type", ""), "source_url": row.get("url", ""), "verification_status": row.get("verification_status", ""), "verified_at": row.get("verified_at", "")}

    @staticmethod
    def _metadata(*generated_from: str) -> dict[str, Any]:
        return {"generated_at": datetime.now(timezone.utc).isoformat(), "generated_from": list(generated_from), "data_backend": "normalized_template"}
