"""Evidence-backed R&D decision brief assembled from existing local services."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from deepinsight.core.company_evidence_profile_service import CompanyEvidenceProfileService
from deepinsight.core.evidence_chain_service import EvidenceChainService
from deepinsight.core.rd_event_timeline_service import RDEventTimelineService
from deepinsight.core.source_registry_service import SourceRegistryService


PROHIBITED_INFERENCES = [
    "医疗诊断或个体治疗建议",
    "疗效保证或跨试验简单排名",
    "项目成功率、获批概率或上市概率预测",
    "投资建议或企业总体实力排名",
]


class EvidenceDecisionBriefService:
    def __init__(
        self,
        *,
        source_registry_service: SourceRegistryService | None = None,
        evidence_chain_service: EvidenceChainService | None = None,
        company_profile_service: CompanyEvidenceProfileService | None = None,
        timeline_service: RDEventTimelineService | None = None,
    ) -> None:
        self.source_service = source_registry_service or SourceRegistryService()
        self.chain_service = evidence_chain_service or EvidenceChainService(
            source_registry_service=self.source_service
        )
        self.profile_service = company_profile_service or CompanyEvidenceProfileService(
            source_registry_service=self.source_service,
            evidence_chain_service=self.chain_service,
        )
        self.timeline_service = timeline_service or RDEventTimelineService(
            source_registry_service=self.source_service,
            evidence_chain_service=self.chain_service,
            company_evidence_profile_service=self.profile_service,
        )

    def available_companies(self) -> list[dict[str, Any]]:
        return self.profile_service.available_companies()

    def build_brief(self, company_name: str) -> dict[str, Any]:
        profile = self.profile_service.build_profile(company_name)
        company = profile.get("company") or {}
        if not company.get("canonical_name"):
            raise ValueError(f"未知企业：{company_name}")

        canonical = str(company["canonical_name"])
        timeline = self.timeline_service.build_timeline(company_name=canonical, include_undated=True)
        rows = self.source_service.query(company=canonical)
        source_index = {row["source_id"]: row for row in rows}
        trial_chains = list(profile.get("trial_chains") or [])
        regulatory_chains = list(profile.get("regulatory_chains") or [])
        unresolved = list(profile.get("unresolved_links") or [])
        summary = profile.get("summary") or {}
        metadata = profile.get("metadata") or {}

        chain_cards = [self._chain_card(chain) for chain in trial_chains]
        regulatory_cards = [self._regulatory_card(chain) for chain in regulatory_chains]
        timeline_events = [self._timeline_event(event) for event in (timeline.get("events") or [])]
        citations = [self._citation(row) for row in rows]
        drug_names = sorted({str(row.get("drug_name") or "").strip() for row in rows if row.get("drug_name")})

        executive = [
            self._conclusion(
                "verified_fact",
                f"当前样本收录 {summary.get('verified_source_count', 0)} 条已人工核验来源，形成 {summary.get('trial_chain_count', 0)} 条试验级证据链。",
                list(source_index),
                [item["chain_id"] for item in chain_cards],
            ),
            self._conclusion(
                "structured_summary",
                f"其中 {summary.get('multi_source_trial_chain_count', 0)} 条试验链具有多个来源，可用于核对登记、论文或事件版本关系。",
                [sid for item in chain_cards if item["source_count"] > 1 for sid in item["source_ids"]],
                [item["chain_id"] for item in chain_cards if item["source_count"] > 1],
            ),
        ]
        if unresolved:
            executive.append(
                self._conclusion(
                    "insufficient_evidence",
                    f"当前样本仍有 {len(unresolved)} 条待确认关系，相关结论需等待补充证据。",
                    [str(item.get("source_id") or "") for item in unresolved],
                    [],
                )
            )

        return {
            "brief_id": f"evidence-brief:{canonical}",
            "title": f"{company.get('display_name') or canonical} · 证据决策简报",
            "subject": {
                "company_name": canonical,
                "display_name": company.get("display_name") or canonical,
                "aliases": list(company.get("aliases") or []),
                "drug_names": drug_names,
                "disease_scope": "NSCLC",
                "data_scope": metadata.get("data_scope_label") or "当前人工核验的NSCLC多企业证据样本",
            },
            "executive_summary": executive,
            "overview": {
                "source_count": summary.get("source_count", 0),
                "verified_source_count": summary.get("verified_source_count", 0),
                "trial_chain_count": summary.get("trial_chain_count", 0),
                "regulatory_chain_count": summary.get("regulatory_chain_count", 0),
                "latest_count": summary.get("latest_count", 0),
                "historical_count": summary.get("historical_count", 0),
                "independent_count": summary.get("independent_count", 0),
                "unresolved_link_count": summary.get("unresolved_link_count", 0),
            },
            "clinical_evidence": chain_cards,
            "evidence_evolution": [item for item in chain_cards if item["latest_count"] or item["historical_count"]],
            "timeline": {
                "events": timeline_events,
                "undated_sources": list(timeline.get("undated_sources") or []),
                "date_policy": (timeline.get("metadata") or {}).get("date_policy", ""),
            },
            "regulatory_status": regulatory_cards,
            "evidence_strength": {
                "source_type_distribution": list(profile.get("source_type_distribution") or []),
                "version_distribution": list(profile.get("version_distribution") or []),
                "study_status_distribution": list(profile.get("study_status_distribution") or []),
                "interpretation": "来源构成和多来源链只说明当前样本的可核验程度，不代表疗效强弱或企业实力。",
            },
            "evidence_gaps": [self._gap(item) for item in unresolved],
            "risks_and_limitations": list(profile.get("limitations") or []),
            "next_evidence_directions": self._next_directions(unresolved, timeline.get("undated_sources") or []),
            "citations": citations,
            "prohibited_inferences": list(PROHIBITED_INFERENCES),
            "metadata": {
                "data_version": metadata.get("data_version", ""),
                "latest_verified_at": metadata.get("latest_verified_at", ""),
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "verification_scope": "仅核验当前来源登记表、证据链配置、企业画像和研发事件时间轴。",
                "generated_from": [
                    "SourceRegistryService", "EvidenceChainService",
                    "CompanyEvidenceProfileService", "RDEventTimelineService",
                ],
            },
        }

    @staticmethod
    def _conclusion(status: str, text: str, source_ids: list[str], chain_ids: list[str]) -> dict[str, Any]:
        return {
            "evidence_status": status,
            "text": text,
            "source_ids": sorted({item for item in source_ids if item}),
            "chain_ids": sorted({item for item in chain_ids if item}),
        }

    @staticmethod
    def _chain_card(chain: dict[str, Any]) -> dict[str, Any]:
        return {
            "chain_id": chain.get("chain_id", ""), "chain_name": chain.get("chain_name", ""),
            "study_name": chain.get("study_name", ""), "trial_id": chain.get("trial_id", ""),
            "study_status": chain.get("study_status", ""), "source_count": chain.get("source_count", 0),
            "latest_count": chain.get("latest_count", 0), "historical_count": chain.get("historical_count", 0),
            "independent_count": chain.get("independent_count", 0), "source_ids": list(chain.get("source_ids") or []),
            "sources": list(chain.get("sources") or []), "evidence_gaps": list(chain.get("evidence_gaps") or []),
            "risk_notes": list(chain.get("risk_notes") or []), "evidence_status": "verified_fact",
        }

    @staticmethod
    def _regulatory_card(chain: dict[str, Any]) -> dict[str, Any]:
        return {
            "chain_id": chain.get("chain_id", ""), "chain_name": chain.get("chain_name", ""),
            "source_count": chain.get("source_count", 0), "source_ids": list(chain.get("source_ids") or []),
            "sources": list(chain.get("sources") or []), "counting_note": chain.get("counting_note", ""),
            "evidence_status": "verified_fact",
        }

    @staticmethod
    def _timeline_event(event: dict[str, Any]) -> dict[str, Any]:
        return {
            "source_id": event.get("source_id", ""), "date": (event.get("date") or {}).get("value", ""),
            "date_precision": (event.get("date") or {}).get("precision", ""),
            "event_type": event.get("event_type", ""), "title": event.get("title", ""),
            "trial_id": event.get("trial_id", ""), "chain_id": event.get("chain_id", ""),
            "source_url": event.get("source_url", ""), "evidence_status": "verified_fact",
        }

    @staticmethod
    def _citation(row: dict[str, Any]) -> dict[str, Any]:
        return {
            "source_id": row.get("source_id", ""), "title": row.get("description_zh") or row.get("title_original") or row.get("study_name") or "",
            "source_type": row.get("source_type", ""), "source_url": row.get("source_url", ""),
            "verified_at": row.get("verified_at", ""), "verification_status": row.get("verification_status", ""),
        }

    @staticmethod
    def _gap(item: dict[str, Any]) -> dict[str, Any]:
        return {
            "source_id": item.get("source_id", ""), "title": item.get("title", ""),
            "description": item.get("description", ""), "evidence_gaps": list(item.get("evidence_gaps") or []),
            "evidence_status": "insufficient_evidence",
        }

    @staticmethod
    def _next_directions(unresolved: list[dict[str, Any]], undated: list[dict[str, Any]]) -> list[dict[str, str]]:
        directions = []
        if unresolved:
            directions.append({"priority": "high", "direction": "补充待确认来源的一对一试验或监管关联依据。"})
        if undated:
            directions.append({"priority": "medium", "direction": "补充可核验的事件日期字段，使资料进入时间轴。"})
        directions.append({"priority": "routine", "direction": "持续核对试验登记状态、正式论文和监管机构正式文件的版本变化。"})
        return directions
