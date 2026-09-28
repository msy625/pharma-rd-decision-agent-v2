"""Timeline projection from explicit normalized study, publication and regulatory dates."""

from __future__ import annotations

from collections import Counter
from datetime import date
from typing import Any

from deepinsight.core.template_data_repository import TemplateDataRepository


class NormalizedInstitutionTimelineService:
    def __init__(self, repository: TemplateDataRepository | None = None) -> None:
        self.repository = repository or TemplateDataRepository()

    def available_institutions(self) -> list[dict[str, str]]:
        return [
            {key: row.get(key, "") for key in ("organization_id", "canonical_name", "display_name", "organization_type")}
            for row in self.repository.load_table("organizations")
        ]

    def build_timeline(
        self, institution: str | None = None, trial_id: str | None = None,
        event_type: str | None = None, year: int | str | None = None,
    ) -> dict[str, Any]:
        organizations = {row["organization_id"]: row for row in self.repository.load_table("organizations")}
        org = self._find_org(institution, organizations) if institution else None
        if institution and not org:
            return self._empty()
        studies = self.repository.load_table("studies")
        ids = self.repository.load_table("study_identifiers")
        id_by_study: dict[str, list[str]] = {}
        for row in ids:
            if row.get("identifier_value"):
                id_by_study.setdefault(row["study_id"], []).append(row["identifier_value"])
        source_rows = {row["template_source_id"]: row for row in self.repository.source_rows(domain_id=None)}
        relations = [row for row in self.repository.load_table("relations") if row.get("relation_status") == "confirmed"]
        source_by_study: dict[str, list[str]] = {}
        for relation in relations:
            if relation.get("relation_type") in {"source_describes_study", "source_supports"}:
                source_by_study.setdefault(relation.get("object_id", ""), []).append(relation.get("source_id", ""))
        study_by_source = {
            relation.get("source_id", ""): relation.get("object_id", "")
            for relation in relations
            if relation.get("relation_type") in {"source_describes_study", "source_supports"}
            and relation.get("source_id") and relation.get("object_id", "").startswith("STUDY_")
        }
        study_by_id = {row["study_id"]: row for row in studies}
        events: list[dict[str, Any]] = []
        selected_studies = [row for row in studies if not org or row.get("sponsor_org_id") == org["organization_id"]]
        for row in selected_studies:
            identifiers = id_by_study.get(row["study_id"], [])
            if trial_id and str(trial_id).strip() not in identifiers and str(trial_id).strip() != row["study_id"]:
                continue
            source_id = (source_by_study.get(row["study_id"]) or [""])[0]
            for field, label in (("start_date", "研究开始"), ("primary_completion_date", "主要完成"), ("completion_date", "研究完成"), ("last_status_date", "状态更新")):
                if row.get(field):
                    events.append(self._event(row.get(field), "study_date", label, row.get("study_name") or row["study_id"], row["study_id"], identifiers, source_id, source_rows, org))
        for row in self.repository.load_table("publications"):
            publication_study_id = row.get("study_id") or study_by_source.get(row.get("source_id", ""), "")
            study = next((item for item in selected_studies if item.get("study_id") == publication_study_id), None)
            if org and not study:
                continue
            raw = row.get("online_publication_date") or row.get("issue_year")
            if raw:
                events.append(self._event(raw, "publication_date", "论文发表", row.get("title_normalized") or row.get("title_original") or row.get("publication_id"), publication_study_id, id_by_study.get(publication_study_id, []), row.get("source_id", ""), source_rows, org))
        for row in self.repository.load_table("regulatory_events"):
            if org and row.get("holder_org_id") != org["organization_id"]:
                continue
            if row.get("event_date"):
                events.append(self._event(row["event_date"], "regulatory_date", "监管事件", row.get("event_type") or row.get("regulatory_event_id", ""), "", [], row.get("source_id", ""), source_rows, org))
        events = [event for event in events if self._matches(event, event_type, year)]
        events.sort(key=lambda event: event["date"]["value"], reverse=True)
        years = Counter(event["date"]["value"][:4] for event in events)
        types = Counter(event["event_type"] for event in events)
        unique_studies = {event.get("study_id") for event in events if event.get("study_id")}
        return {
            "events": events, "undated_sources": [],
            "summary": {"event_count": len(events), "study_event_count": sum(event["event_type"] == "study_date" for event in events), "publication_event_count": sum(event["event_type"] == "publication_date" for event in events), "regulatory_event_count": sum(event["event_type"] == "regulatory_date" for event in events), "unique_study_count": len(unique_studies), "undated_record_count": 0, "year_count": len(years)},
            "event_type_distribution": [{"key": key, "label": key, "count": count} for key, count in sorted(types.items())],
            "year_distribution": [{"year": year_key, "count": count} for year_key, count in sorted(years.items(), reverse=True)],
            "available_institutions": self.available_institutions(),
            "metadata": {"data_scope": "all_normalized_structured_dates", "date_policy": "仅使用 studies、publications、regulatory_events 中的结构化日期；不从标题、编号或当前时间推测。", "data_backend": "normalized_template"},
            "limitations": ["只展示明确结构化日期。缺少日期的记录不进入排序时间轴。", "事件数量是数据覆盖统计，不代表机构研发活跃度或竞争力。"],
        }

    def _find_org(self, value: str, organizations: dict[str, dict[str, str]]) -> dict[str, str] | None:
        key = str(value or "").strip().casefold()
        exact = next((row for row in organizations.values() if key in {str(row.get("organization_id", "")).casefold(), str(row.get("canonical_name", "")).casefold(), str(row.get("display_name", "")).casefold()}), None)
        if exact:
            return exact
        aliases = [row for row in self.repository.load_table("organization_aliases") if key and str(row.get("alias", "")).strip().casefold() == key]
        matches = {row.get("organization_id") for row in aliases}
        if len(matches) > 1:
            sourced = {row.get("organization_id") for row in aliases if row.get("source_id")}
            if len(sourced) == 1:
                matches = sourced
        return organizations.get(next(iter(matches))) if len(matches) == 1 else None

    @staticmethod
    def _matches(event: dict[str, Any], event_type: str | None, year: int | str | None) -> bool:
        return (not event_type or event["event_type"] == event_type) and (not year or event["date"]["value"].startswith(str(year)))

    @staticmethod
    def _event(raw: str, kind: str, label: str, title: str, study_id: str, identifiers: list[str], source_id: str, source_rows: dict[str, dict[str, str]], org: dict[str, str] | None) -> dict[str, Any]:
        value = str(raw).strip()
        precision = "day" if len(value) == 10 else ("year" if len(value) == 4 else "month")
        source = source_rows.get(source_id, {})
        return {"event_id": f"{kind}:{study_id or source_id}:{value}", "source_id": source.get("source_id", source_id), "institution": {"organization_id": (org or {}).get("organization_id", ""), "display_name": (org or {}).get("display_name", "")}, "date": {"value": value, "precision": precision, "field": kind, "semantic": label}, "event_type": kind, "event_type_label": label, "title": title, "study_id": study_id, "trial_id": identifiers[0] if identifiers else "", "source_type": source.get("source_type", ""), "source_url": source.get("url", ""), "verification_status": source.get("verification_status", ""), "limitations": []}

    @staticmethod
    def _empty() -> dict[str, Any]:
        return {"events": [], "undated_sources": [], "summary": {}, "available_institutions": [], "metadata": {"data_scope": "all_normalized_structured_dates", "date_policy": "仅使用结构化日期。"}, "limitations": ["未找到该机构。"]}
