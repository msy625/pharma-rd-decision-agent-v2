"""R&D event timeline for the manually verified NSCLC evidence sample.

The service composes the existing local registry, evidence-chain, company-profile,
and workbench services. Dates are read only from explicit structured fields; it
does not infer dates from titles, URLs, identifiers, or the current year.
"""

from __future__ import annotations

import re
from collections import Counter
from typing import Iterable

from deepinsight.core.company_evidence_profile_service import CompanyEvidenceProfileService
from deepinsight.core.evidence_chain_service import EvidenceChainService, version_status
from deepinsight.core.evidence_workbench_service import EvidenceWorkbenchService
from deepinsight.core.source_registry_service import SourceRegistryService, norm


EVENT_TYPE_LABELS = {
    "company_disclosure": "公司正式披露",
    "registration_authorisation": "公司公告披露注册获批",
    "interim_analysis": "中期分析",
    "final_analysis": "最终分析",
    "combined_analysis_publication": "中期与最终合并论文",
    "evidence_update": "证据版本更新",
    "formal_authorisation": "正式授权",
    "regulatory_opinion": "监管意见",
    "source_publication": "资料发布",
}

REGULATORY_EVENT_TYPES = {
    "registration_authorisation",
    "formal_authorisation",
    "regulatory_opinion",
}

LIMITATIONS = [
    "本时间轴只反映当前收录并核验的NSCLC证据样本，不代表企业完整研发管线。",
    "事件数量只描述当前样本中的可用日期记录，不能解释为企业研发实力、研发活跃度、成功率或投资价值。",
    "资料缺少可核验事件日期时进入无日期资料，不根据标题、URL、PMID、试验编号或当前年份推测日期。",
    "同一试验可以存在多个证据事件，但唯一试验数按试验证据链去重；药物级监管事件不计入试验数。",
    "核验日期和响应生成时间均不是研发事件日期。",
]

MONTHS = {
    "jan": 1,
    "feb": 2,
    "mar": 3,
    "apr": 4,
    "may": 5,
    "jun": 6,
    "jul": 7,
    "aug": 8,
    "sep": 9,
    "oct": 10,
    "nov": 11,
    "dec": 12,
}


class RDEventTimelineService:
    """Build a conservative, source-level R&D event timeline."""

    def __init__(
        self,
        *,
        source_registry_service: SourceRegistryService | None = None,
        evidence_chain_service: EvidenceChainService | None = None,
        company_evidence_profile_service: CompanyEvidenceProfileService | None = None,
        evidence_workbench_service: EvidenceWorkbenchService | None = None,
    ) -> None:
        self.source_registry_service = source_registry_service or SourceRegistryService()
        self.evidence_chain_service = evidence_chain_service or EvidenceChainService(
            source_registry_service=self.source_registry_service
        )
        self.evidence_workbench_service = evidence_workbench_service or EvidenceWorkbenchService(
            source_registry_service=self.source_registry_service,
            evidence_chain_service=self.evidence_chain_service,
        )
        self.company_evidence_profile_service = (
            company_evidence_profile_service
            or CompanyEvidenceProfileService(
                source_registry_service=self.source_registry_service,
                evidence_chain_service=self.evidence_chain_service,
                evidence_workbench_service=self.evidence_workbench_service,
            )
        )

    def normalize_company(self, company_name: str) -> dict[str, object]:
        return self.company_evidence_profile_service.normalize_company(company_name)

    def available_companies(self) -> list[dict[str, object]]:
        return self.company_evidence_profile_service.available_companies()

    def build_events(self, include_auxiliary: bool = False) -> list[dict[str, object]]:
        rows = self.source_registry_service.load_rows()
        chain_index, related_trial_index = self._chain_indexes()
        superseded_by = {
            row.get("supersedes_source_id", ""): row.get("source_id", "")
            for row in rows
            if row.get("supersedes_source_id") and row.get("source_id")
        }
        events: list[dict[str, object]] = []
        seen_source_ids: set[str] = set()
        for row in rows:
            source_id = row.get("source_id", "")
            if not source_id or source_id in seen_source_ids:
                continue
            event_type, is_auxiliary = self._event_type(row)
            date = self._event_date(row, is_auxiliary=is_auxiliary)
            if not date or (is_auxiliary and not include_auxiliary):
                continue
            chain = chain_index.get(source_id, {})
            chain_type = str(chain.get("chain_type", ""))
            direct_trial_ids = list(chain.get("trial_ids", [])) if chain_type == "trial" else []
            related_trial_ids = sorted(related_trial_index.get(source_id, set()))
            trial_id = self._primary_chain_trial_id(direct_trial_ids)
            if not trial_id and chain_type != "regulatory":
                trial_id = self.source_registry_service.primary_trial_id(row)
            limitations = self._event_limitations(row, event_type)
            events.append(
                {
                    "event_id": f"source:{source_id}",
                    "source_id": source_id,
                    "company": self._company_for_row(row),
                    "date": date,
                    "event_type": event_type,
                    "event_type_label": EVENT_TYPE_LABELS[event_type],
                    "title": self._event_title(row, event_type),
                    "drug_names": self._split_values(row.get("drug_names", "")),
                    "trial_id": trial_id,
                    "related_trial_ids": related_trial_ids,
                    "is_trial_evidence": bool(chain_type == "trial" or trial_id),
                    "chain_id": str(chain.get("chain_id", "")),
                    "chain_type": chain_type,
                    "chain_role": str(chain.get("role", "")),
                    "version_status": version_status(row.get("is_latest_evidence", "")),
                    "evidence_version": row.get("evidence_version", ""),
                    "supersedes_source_id": row.get("supersedes_source_id", ""),
                    "superseded_by_source_id": superseded_by.get(source_id, ""),
                    "source_type": row.get("source_type", ""),
                    "source_url": row.get("url", ""),
                    "verification_status": row.get("verification_status", ""),
                    "verified_at": row.get("verified_at", ""),
                    "source_last_updated": row.get("source_last_updated", ""),
                    "is_auxiliary": is_auxiliary,
                    "limitations": limitations,
                }
            )
            seen_source_ids.add(source_id)
        return sorted(events, key=self._event_sort_key, reverse=True)

    def events_by_company(
        self, company_name: str, include_auxiliary: bool = False
    ) -> list[dict[str, object]]:
        subject = self.normalize_company(company_name)
        if not subject:
            return []
        canonical_name = str(subject.get("canonical_name", ""))
        return [
            event
            for event in self.build_events(include_auxiliary=include_auxiliary)
            if event.get("company", {}).get("canonical_name") == canonical_name
        ]

    def events_by_trial(self, trial_id: str) -> list[dict[str, object]]:
        query = norm(trial_id)
        if not query:
            return []
        return [
            event
            for event in self.build_events(include_auxiliary=True)
            if query == norm(event.get("trial_id"))
            or query in {norm(item) for item in event.get("related_trial_ids", [])}
        ]

    def events_by_drug(self, drug_name: str) -> list[dict[str, object]]:
        source_ids = self._matching_source_ids(drug_name=drug_name)
        return [
            event
            for event in self.build_events(include_auxiliary=True)
            if event.get("source_id") in source_ids
        ]

    def event_type_distribution(
        self, events: Iterable[dict[str, object]] | None = None
    ) -> list[dict[str, object]]:
        selected = list(events) if events is not None else self.build_events()
        counts = Counter(str(event.get("event_type", "")) for event in selected)
        return [
            {"key": key, "label": EVENT_TYPE_LABELS.get(key, key), "count": counts[key]}
            for key in EVENT_TYPE_LABELS
            if counts[key]
        ]

    def year_distribution(
        self, events: Iterable[dict[str, object]] | None = None
    ) -> list[dict[str, object]]:
        selected = list(events) if events is not None else self.build_events()
        counts = Counter(
            str(event.get("date", {}).get("value", ""))[:4]
            for event in selected
            if str(event.get("date", {}).get("value", ""))[:4].isdigit()
        )
        return [{"year": year, "count": counts[year]} for year in sorted(counts, reverse=True)]

    def undated_sources(
        self,
        company_name: str | None = None,
        trial_id: str | None = None,
        drug_name: str | None = None,
    ) -> list[dict[str, object]]:
        subject = self.normalize_company(company_name) if company_name else None
        if company_name and not subject:
            return []
        source_ids = self._matching_source_ids(
            company_name=str(subject.get("canonical_name", "")) if subject else None,
            trial_id=trial_id,
            drug_name=drug_name,
        )
        dated_source_ids = {event["source_id"] for event in self.build_events(include_auxiliary=True)}
        chain_index, related_trial_index = self._chain_indexes()
        items = []
        for row in self.source_registry_service.load_rows():
            source_id = row.get("source_id", "")
            if source_id in dated_source_ids or source_id not in source_ids:
                continue
            chain = chain_index.get(source_id, {})
            direct_trial_ids = list(chain.get("trial_ids", [])) if chain.get("chain_type") == "trial" else []
            trial_value = self._primary_chain_trial_id(direct_trial_ids) or self.source_registry_service.primary_trial_id(row)
            items.append(
                {
                    "source_id": source_id,
                    "company": self._company_for_row(row),
                    "title": self._source_title(row),
                    "drug_names": self._split_values(row.get("drug_names", "")),
                    "trial_id": trial_value,
                    "related_trial_ids": sorted(related_trial_index.get(source_id, set())),
                    "chain_id": str(chain.get("chain_id", "")),
                    "version_status": version_status(row.get("is_latest_evidence", "")),
                    "source_type": row.get("source_type", ""),
                    "source_url": row.get("url", ""),
                    "verification_status": row.get("verification_status", ""),
                    "verified_at": row.get("verified_at", ""),
                    "reason": "未提供可用于研发事件排序的结构化日期；未进入时间轴，不代表事件不存在。",
                }
            )
        return sorted(items, key=lambda item: str(item.get("source_id", "")))

    def build_timeline(
        self,
        company_name: str | None = None,
        trial_id: str | None = None,
        drug_name: str | None = None,
        event_type: str | None = None,
        year: int | str | None = None,
        include_auxiliary: bool = False,
        include_undated: bool = True,
    ) -> dict[str, object]:
        subject = self.normalize_company(company_name) if company_name else None
        if company_name and not subject:
            return self._empty_timeline(company_name)

        source_ids = self._matching_source_ids(
            company_name=str(subject.get("canonical_name", "")) if subject else None,
            trial_id=trial_id,
            drug_name=drug_name,
        )
        all_events = [
            event
            for event in self.build_events(include_auxiliary=True)
            if event.get("source_id") in source_ids
        ]
        if trial_id:
            trial_key = norm(trial_id)
            all_events = [
                event
                for event in all_events
                if trial_key == norm(event.get("trial_id"))
                or trial_key in {norm(item) for item in event.get("related_trial_ids", [])}
            ]
        if event_type:
            all_events = [event for event in all_events if norm(event.get("event_type")) == norm(event_type)]
        if year not in (None, ""):
            year_value = str(year)
            all_events = [
                event
                for event in all_events
                if str(event.get("date", {}).get("value", "")).startswith(f"{year_value}-")
                or str(event.get("date", {}).get("value", "")) == year_value
            ]

        core_events = [event for event in all_events if not event.get("is_auxiliary")]
        auxiliary_events = [event for event in all_events if event.get("is_auxiliary")]
        visible_events = all_events if include_auxiliary else core_events
        all_undated = self.undated_sources(
            company_name=company_name,
            trial_id=trial_id,
            drug_name=drug_name,
        )
        undated = all_undated if include_undated else []
        scope_rows = [row for row in self.source_registry_service.load_rows() if row.get("source_id") in source_ids]
        unique_trial_chain_ids = {
            str(event.get("chain_id"))
            for event in visible_events
            if event.get("is_trial_evidence") and str(event.get("chain_id", "")).startswith("trial:")
        }
        standalone_trial_ids = {
            str(event.get("trial_id"))
            for event in visible_events
            if event.get("is_trial_evidence")
            and event.get("trial_id")
            and not str(event.get("chain_id", "")).startswith("trial:")
        }
        metadata = self.evidence_workbench_service.metadata(scope_rows)
        return {
            "company": subject or {},
            "filters": {
                "company": company_name or "",
                "trial_id": trial_id or "",
                "drug": drug_name or "",
                "event_type": event_type or "",
                "year": str(year or ""),
                "include_auxiliary": bool(include_auxiliary),
                "include_undated": bool(include_undated),
            },
            "available_companies": self.available_companies(),
            "events": visible_events,
            "undated_sources": undated,
            "event_type_distribution": self.event_type_distribution(visible_events),
            "year_distribution": self.year_distribution(visible_events),
            "summary": {
                "total_source_count": len(self.source_registry_service.load_rows()),
                "scope_source_count": len(scope_rows),
                "dated_source_count": len({event.get("source_id") for event in all_events}),
                "core_event_count": len(core_events),
                "auxiliary_event_count": len(auxiliary_events),
                "event_count": len(visible_events),
                "unique_trial_count": len(unique_trial_chain_ids) + len(standalone_trial_ids),
                "regulatory_event_count": sum(
                    1 for event in visible_events if event.get("event_type") in REGULATORY_EVENT_TYPES
                ),
                "undated_source_count": len(all_undated),
            },
            "metadata": {
                **metadata,
                "date_policy": "仅使用online_publication_date、publication_date或辅助资料的data_cutoff_date；verified_at、generated_at和source_last_updated不作为事件日期。",
            },
            "limitations": list(LIMITATIONS),
        }

    def _matching_source_ids(
        self,
        *,
        company_name: str | None = None,
        trial_id: str | None = None,
        drug_name: str | None = None,
    ) -> set[str]:
        rows = self.source_registry_service.load_rows()
        selected_ids = {row.get("source_id", "") for row in rows}
        if company_name:
            selected_ids &= {
                row.get("source_id", "")
                for row in self.source_registry_service.query(company=company_name, normalized=False)
            }
        if trial_id:
            direct_ids = {
                row.get("source_id", "")
                for row in self.source_registry_service.query(trial_id=trial_id, normalized=False)
            }
            _, related_trial_index = self._chain_indexes()
            related_ids = {
                source_id
                for source_id, trial_ids in related_trial_index.items()
                if norm(trial_id) in {norm(item) for item in trial_ids}
            }
            selected_ids &= direct_ids | related_ids
        if drug_name:
            selected_ids &= {
                row.get("source_id", "")
                for row in self.source_registry_service.query(drug=drug_name, normalized=False)
            }
        return selected_ids

    def _chain_indexes(self) -> tuple[dict[str, dict[str, object]], dict[str, set[str]]]:
        direct: dict[str, dict[str, object]] = {}
        related_trials: dict[str, set[str]] = {}
        for chain in self.evidence_chain_service.list_chains():
            base = {
                "chain_id": chain.get("chain_id", ""),
                "chain_type": chain.get("chain_type", ""),
                "trial_ids": list(chain.get("trial_ids", [])),
            }
            for item in chain.get("evidence_items", []):
                source_id = str(item.get("source_id", ""))
                if source_id:
                    direct[source_id] = {**base, "role": item.get("role", "")}
            if chain.get("chain_type") == "trial":
                trial_ids = {str(item) for item in chain.get("trial_ids", []) if str(item)}
                for item in chain.get("related_regulatory_items", []):
                    source_id = str(item.get("source_id", ""))
                    if source_id:
                        related_trials.setdefault(source_id, set()).update(trial_ids)
        return direct, related_trials

    def _company_for_row(self, row: dict[str, str]) -> dict[str, object]:
        company_name = row.get("company_cn") or row.get("company", "")
        subject = self.normalize_company(company_name)
        return subject or {
            "canonical_name": company_name,
            "display_name": company_name,
            "aliases": [],
        }

    @staticmethod
    def _event_type(row: dict[str, str]) -> tuple[str, bool]:
        if row.get("data_cutoff_date"):
            return "evidence_update", True
        if "chmp positive opinion" in norm(row.get("regulatory_event_type")):
            return "regulatory_opinion", False
        if "正式授权" in row.get("authorisation_status", ""):
            return "formal_authorisation", False
        if "药品注册获批" in row.get("study_status", ""):
            return "registration_authorisation", False
        if norm(row.get("source_type")) == "pubmed":
            analysis_stage = row.get("analysis_stage", "")
            evidence_version = norm(row.get("evidence_version"))
            if evidence_version == "interim_and_final_combined" or "合并报告" in analysis_stage:
                return "combined_analysis_publication", False
            if evidence_version == "final" or "最终分析" in analysis_stage:
                return "final_analysis", False
            if evidence_version == "interim" or "中期分析" in analysis_stage:
                return "interim_analysis", False
            return "source_publication", False
        if row.get("publication_date"):
            return "company_disclosure", False
        return "source_publication", False

    def _event_date(self, row: dict[str, str], *, is_auxiliary: bool) -> dict[str, str]:
        if is_auxiliary and row.get("data_cutoff_date"):
            field = "data_cutoff_date"
            semantic = "辅助证据截点"
        elif norm(row.get("source_type")) == "pubmed" and row.get("online_publication_date"):
            field = "online_publication_date"
            semantic = "在线发表日期"
        elif row.get("publication_date"):
            field = "publication_date"
            semantic = self._publication_semantic(row)
        else:
            return {}
        parsed = self._parse_date(row.get(field, ""))
        if not parsed:
            return {}
        return {
            **parsed,
            "original_value": row.get(field, ""),
            "field": field,
            "semantic": semantic,
        }

    @staticmethod
    def _publication_semantic(row: dict[str, str]) -> str:
        if row.get("regulatory_event_type") or row.get("authorisation_status"):
            return "监管事件日期"
        if "药品注册获批" in row.get("study_status", ""):
            return "公司公告披露日期"
        return "资料发布日期"

    @staticmethod
    def _parse_date(value: str) -> dict[str, str]:
        raw = str(value or "").strip()
        if not raw:
            return {}
        match = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", raw)
        if match:
            return {"value": raw, "precision": "day"}
        match = re.fullmatch(r"(\d{4})-(\d{2})", raw)
        if match:
            return {"value": raw, "precision": "month"}
        match = re.fullmatch(r"(\d{4})年(\d{1,2})月(\d{1,2})日", raw)
        if match:
            return {
                "value": f"{int(match.group(1)):04d}-{int(match.group(2)):02d}-{int(match.group(3)):02d}",
                "precision": "day",
            }
        match = re.fullmatch(r"(\d{4})年(\d{1,2})月", raw)
        if match:
            return {
                "value": f"{int(match.group(1)):04d}-{int(match.group(2)):02d}",
                "precision": "month",
            }
        match = re.fullmatch(r"(\d{4})\s+([A-Za-z]{3})(?:\s+(\d{1,2}))?", raw)
        if match and norm(match.group(2)) in MONTHS:
            year = int(match.group(1))
            month = MONTHS[norm(match.group(2))]
            day = match.group(3)
            if day:
                return {"value": f"{year:04d}-{month:02d}-{int(day):02d}", "precision": "day"}
            return {"value": f"{year:04d}-{month:02d}", "precision": "month"}
        return {}

    @staticmethod
    def _event_title(row: dict[str, str], event_type: str) -> str:
        if event_type == "formal_authorisation":
            return "Tevimbra欧盟初始许可"
        if event_type == "regulatory_opinion":
            return "Tevimbra CHMP积极意见，非最终批准"
        if event_type == "registration_authorisation":
            return "公司公告披露瑞康曲妥珠单抗注册获批"
        return RDEventTimelineService._source_title(row)

    @staticmethod
    def _source_title(row: dict[str, str]) -> str:
        return (
            row.get("normalized_title_zh")
            or row.get("original_title")
            or row.get("original_title_en")
            or row.get("study_name")
            or row.get("source_id")
            or ""
        )

    @staticmethod
    def _event_limitations(row: dict[str, str], event_type: str) -> list[str]:
        notes = [item for item in [row.get("scope_limitation", ""), row.get("notes", "")] if item]
        if event_type == "formal_authorisation":
            notes.append("该日期表示Tevimbra欧盟初始许可，不表示围手术期NSCLC适应症在同日获得最终批准。")
        elif event_type == "regulatory_opinion":
            notes.append("CHMP积极意见不是欧盟委员会最终批准。")
        elif event_type == "registration_authorisation":
            notes.append("来源为公司公告，不冒充NMPA/CDE原始监管记录。")
        return notes

    @staticmethod
    def _split_values(value: str) -> list[str]:
        return [item.strip() for item in re.split(r"[;,，、]+", value or "") if item.strip()]

    @staticmethod
    def _primary_chain_trial_id(trial_ids: Iterable[object]) -> str:
        values = [str(item) for item in trial_ids if str(item)]
        for value in values:
            if value.startswith("NCT"):
                return value
        return values[0] if values else ""

    @staticmethod
    def _event_sort_key(event: dict[str, object]) -> tuple[str, str]:
        return (
            str(event.get("date", {}).get("value", "")),
            str(event.get("source_id", "")),
        )

    def _empty_timeline(self, company_name: str) -> dict[str, object]:
        metadata = self.evidence_workbench_service.metadata([])
        return {
            "company": {"canonical_name": "", "display_name": str(company_name or "").strip(), "aliases": []},
            "filters": {"company": company_name or ""},
            "available_companies": self.available_companies(),
            "events": [],
            "undated_sources": [],
            "event_type_distribution": [],
            "year_distribution": [],
            "summary": {
                "total_source_count": len(self.source_registry_service.load_rows()),
                "scope_source_count": 0,
                "dated_source_count": 0,
                "core_event_count": 0,
                "auxiliary_event_count": 0,
                "event_count": 0,
                "unique_trial_count": 0,
                "regulatory_event_count": 0,
                "undated_source_count": 0,
            },
            "metadata": metadata,
            "limitations": [
                f"当前数据不足：未在当前收录并核验的NSCLC样本中识别到企业“{company_name}”。",
                *LIMITATIONS,
            ],
        }


def build_timeline(**filters: object) -> dict[str, object]:
    return RDEventTimelineService().build_timeline(**filters)
