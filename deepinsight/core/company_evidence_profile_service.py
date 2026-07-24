"""Single-company evidence profiles for the verified NSCLC sample.

The service composes the existing local registry, evidence-chain, workbench,
and company-normalization services. It does not use databases, models,
vector stores, environment secrets, or network access.
"""

from __future__ import annotations

from collections import Counter
from typing import Iterable

from deepinsight.core.company_evidence_comparison_service import (
    DATA_SCOPE,
    CompanyEvidenceComparisonService,
)
from deepinsight.core.evidence_chain_service import EvidenceChainService, version_status
from deepinsight.core.evidence_workbench_service import EvidenceWorkbenchService
from deepinsight.core.source_registry_service import SourceRegistryService, norm


DATA_SCOPE_LABEL = "当前人工核验的NSCLC多企业证据样本"
SCOPE_WARNING = "本画像仅反映当前收录并核验的NSCLC证据样本，不代表企业整体研发实力或完整研发管线。"
PUBLICATION_SOURCE_TYPES = {"pubmed"}
TRIAL_REGISTRY_SOURCE_TYPES = {"clinicaltrials.gov"}

LIMITATIONS = [
    SCOPE_WARNING,
    "来源数量、证据链数量和资料构成只描述当前样本覆盖，不能解释为企业研发实力。",
    "药物级监管链单独统计，不计入临床试验数量；监管背景也不增加关联试验的证据数量。",
    "当前缺少统一的 project_id、target、mechanism 和 drug_type，不能展示为完整项目管线。",
    "不得从 drug_name 字符串推断项目数量，也不输出评分、排名、成功率、疗效或安全性优劣及投资建议。",
    "待确认关系表示当前样本缺少明确的一对一核验依据，不等同于来源错误或企业没有相关进展。",
]


class CompanyEvidenceProfileService:
    """Build a conservative evidence-only profile for one normalized company."""

    def __init__(
        self,
        *,
        source_registry_service: SourceRegistryService | None = None,
        evidence_chain_service: EvidenceChainService | None = None,
        evidence_workbench_service: EvidenceWorkbenchService | None = None,
        company_comparison_service: CompanyEvidenceComparisonService | None = None,
    ) -> None:
        self.source_registry_service = source_registry_service or SourceRegistryService()
        self.evidence_chain_service = evidence_chain_service or EvidenceChainService(
            source_registry_service=self.source_registry_service
        )
        self.company_comparison_service = company_comparison_service or CompanyEvidenceComparisonService(
            source_registry_service=self.source_registry_service,
            evidence_chain_service=self.evidence_chain_service,
        )
        self.evidence_workbench_service = evidence_workbench_service or EvidenceWorkbenchService(
            source_registry_service=self.source_registry_service,
            evidence_chain_service=self.evidence_chain_service,
            company_comparison_service=self.company_comparison_service,
        )

    def normalize_company(self, company_name: str) -> dict[str, object]:
        subject = self.company_comparison_service.normalize_company(company_name)
        if not subject:
            return {}
        display_name = str(subject.get("display_name", "")).replace("/", " / ")
        return {
            "canonical_name": subject.get("company_name", ""),
            "display_name": display_name,
            "aliases": list(subject.get("aliases", [])),
        }

    def available_companies(self) -> list[dict[str, object]]:
        items = []
        for subject in self.company_comparison_service.available_companies():
            normalized = self.normalize_company(str(subject.get("company_name", "")))
            if normalized:
                items.append(normalized)
        return items

    def company_summary(self, company_name: str) -> dict[str, int]:
        subject = self.normalize_company(company_name)
        if not subject:
            return self._empty_summary()
        rows = self._company_rows(subject)
        trial_chains = self.trial_chains(company_name)
        regulatory_chains = self.regulatory_chains(company_name)
        versions = self._version_counts(rows)
        unresolved = self.unresolved_links(company_name)
        source_types = Counter(norm(row.get("source_type")) for row in rows)
        return {
            "source_count": len(rows),
            "verified_source_count": sum(1 for row in rows if row.get("verification_status") == "已人工核验"),
            "trial_chain_count": len(trial_chains),
            "regulatory_chain_count": len(regulatory_chains),
            "multi_source_trial_chain_count": sum(1 for chain in trial_chains if int(chain.get("source_count", 0)) > 1),
            "single_source_trial_chain_count": sum(1 for chain in trial_chains if int(chain.get("source_count", 0)) == 1),
            "publication_source_count": sum(source_types[source_type] for source_type in PUBLICATION_SOURCE_TYPES),
            "trial_registry_source_count": sum(source_types[source_type] for source_type in TRIAL_REGISTRY_SOURCE_TYPES),
            "latest_count": versions["latest"],
            "historical_count": versions["historical"],
            "independent_count": versions["independent"],
            "unresolved_link_count": len(unresolved),
        }

    def trial_chains(self, company_name: str) -> list[dict[str, object]]:
        subject = self.normalize_company(company_name)
        if not subject:
            return []
        chains = self.evidence_chain_service.list_chains(
            company=str(subject["canonical_name"]), chain_type="trial"
        )
        return [self._chain_profile(chain, regulatory=False) for chain in chains]

    def regulatory_chains(self, company_name: str) -> list[dict[str, object]]:
        subject = self.normalize_company(company_name)
        if not subject:
            return []
        chains = self.evidence_chain_service.list_chains(
            company=str(subject["canonical_name"]), chain_type="regulatory"
        )
        return [self._chain_profile(chain, regulatory=True) for chain in chains]

    def independent_sources(self, company_name: str) -> list[dict[str, object]]:
        subject = self.normalize_company(company_name)
        if not subject:
            return []
        linked_chains = self._source_chain_map(str(subject["canonical_name"]))
        unresolved_ids = {str(item.get("source_id", "")) for item in self.unresolved_links(company_name)}
        items = []
        for row in self._company_rows(subject):
            if version_status(row.get("is_latest_evidence", "")) != "independent":
                continue
            item = self._source_profile(row)
            source_id = str(item.get("source_id", ""))
            item["linked_chain_ids"] = linked_chains.get(source_id, [])
            item["link_status"] = "待确认" if source_id in unresolved_ids else ("已确认" if item["linked_chain_ids"] else "独立资料")
            items.append(item)
        return items

    def unresolved_links(self, company_name: str) -> list[dict[str, object]]:
        subject = self.normalize_company(company_name)
        if not subject:
            return []
        comparison_profile = self.company_comparison_service.company_profile(str(subject["canonical_name"]))
        items = []
        for gap in comparison_profile.get("evidence_gaps", []):
            source_id = str(gap.get("source_id", ""))
            row = self.source_registry_service.get_by_source_id(source_id, normalized=False) or {}
            items.append(
                {
                    "source_id": source_id,
                    "source_type": row.get("source_type", ""),
                    "title": self._source_title(row),
                    "relation_level": "unresolved",
                    "description": gap.get("description", ""),
                    "evidence_gaps": list(gap.get("evidence_gaps", [])),
                }
            )
        return items

    def source_type_distribution(self, company_name: str) -> list[dict[str, object]]:
        subject = self.normalize_company(company_name)
        return self._distribution(self._company_rows(subject), "source_type") if subject else []

    def version_distribution(self, company_name: str) -> list[dict[str, object]]:
        subject = self.normalize_company(company_name)
        if not subject:
            return []
        counts = self._version_counts(self._company_rows(subject))
        labels = {"latest": "最新资料", "historical": "历史版本", "independent": "独立资料"}
        return [{"key": key, "label": labels[key], "count": counts[key]} for key in ["latest", "historical", "independent"]]

    def study_status_distribution(self, company_name: str) -> list[dict[str, object]]:
        subject = self.normalize_company(company_name)
        return self._distribution(self._company_rows(subject), "study_status", empty_label="未填写或不适用") if subject else []

    def build_profile(self, company_name: str) -> dict[str, object]:
        subject = self.normalize_company(company_name)
        if not subject:
            return self._empty_profile(company_name)
        rows = self._company_rows(subject)
        return {
            "company": subject,
            "summary": self.company_summary(company_name),
            "trial_chains": self.trial_chains(company_name),
            "regulatory_chains": self.regulatory_chains(company_name),
            "independent_sources": self.independent_sources(company_name),
            "source_type_distribution": self.source_type_distribution(company_name),
            "version_distribution": self.version_distribution(company_name),
            "study_status_distribution": self.study_status_distribution(company_name),
            "unresolved_links": self.unresolved_links(company_name),
            "metadata": self._metadata(rows),
            "limitations": list(LIMITATIONS),
        }

    def _company_rows(self, subject: dict[str, object]) -> list[dict[str, str]]:
        return self.source_registry_service.query(
            company=str(subject.get("canonical_name", "")), normalized=False
        )

    def _chain_profile(self, chain: dict[str, object], *, regulatory: bool) -> dict[str, object]:
        evidence_items = list(chain.get("evidence_items", []))
        latest_count = sum(1 for item in evidence_items if item.get("version_status") == "latest")
        historical_count = sum(1 for item in evidence_items if item.get("version_status") == "historical")
        independent_count = sum(1 for item in evidence_items if item.get("version_status") == "independent")
        study_names = list(chain.get("study_names", []))
        trial_ids = list(chain.get("trial_ids", []))
        profile = {
            "chain_id": chain.get("chain_id", ""),
            "chain_name": chain.get("chain_name", ""),
            "relation_level": chain.get("relation_level", ""),
            "study_name": study_names[0] if study_names else chain.get("chain_name", ""),
            "study_names": study_names,
            "trial_id": trial_ids[0] if trial_ids else "",
            "trial_ids": trial_ids,
            "study_status": chain.get("study_status", ""),
            "source_count": int(chain.get("source_count", 0) or 0),
            "latest_count": latest_count,
            "historical_count": historical_count,
            "independent_count": independent_count,
            "source_ids": [item.get("source_id", "") for item in evidence_items],
            "sources": [self._source_profile(item) for item in evidence_items],
            "evidence_gaps": list(chain.get("evidence_gaps", [])),
            "risk_notes": list(chain.get("risk_notes", [])),
        }
        if regulatory:
            profile.update(
                {
                    "drug_names": list(chain.get("drug_names", [])),
                    "related_trial_ids": list(chain.get("related_trial_ids", [])),
                    "counting_note": "药物级监管链，不计入临床试验数量。",
                }
            )
        return profile

    def _source_chain_map(self, company_name: str) -> dict[str, list[str]]:
        mapping: dict[str, list[str]] = {}
        for chain in self.evidence_chain_service.list_chains(company=company_name):
            chain_id = str(chain.get("chain_id", ""))
            for item in chain.get("evidence_items", []):
                source_id = str(item.get("source_id", ""))
                if source_id:
                    mapping.setdefault(source_id, []).append(chain_id)
        return mapping

    def _metadata(self, rows: Iterable[dict[str, str]]) -> dict[str, str]:
        metadata = self.evidence_workbench_service.metadata(rows)
        return {
            "data_scope": DATA_SCOPE,
            "data_scope_label": DATA_SCOPE_LABEL,
            "data_version": metadata.get("data_version", ""),
            "latest_verified_at": metadata.get("latest_verified_at", ""),
            "generated_at": metadata.get("generated_at", ""),
            "generated_at_note": metadata.get("generated_at_note", ""),
        }

    def _empty_profile(self, company_name: str) -> dict[str, object]:
        return {
            "company": {"canonical_name": "", "display_name": str(company_name or "").strip(), "aliases": []},
            "summary": self._empty_summary(),
            "trial_chains": [],
            "regulatory_chains": [],
            "independent_sources": [],
            "source_type_distribution": [],
            "version_distribution": [],
            "study_status_distribution": [],
            "unresolved_links": [],
            "metadata": self._metadata([]),
            "limitations": [f"当前数据不足：未在当前收录并核验的NSCLC样本中识别到企业“{company_name}”。", *LIMITATIONS],
        }

    @staticmethod
    def _empty_summary() -> dict[str, int]:
        return {
            "source_count": 0,
            "verified_source_count": 0,
            "trial_chain_count": 0,
            "regulatory_chain_count": 0,
            "multi_source_trial_chain_count": 0,
            "single_source_trial_chain_count": 0,
            "publication_source_count": 0,
            "trial_registry_source_count": 0,
            "latest_count": 0,
            "historical_count": 0,
            "independent_count": 0,
            "unresolved_link_count": 0,
        }

    @staticmethod
    def _version_counts(rows: Iterable[dict[str, str]]) -> dict[str, int]:
        counts = {"latest": 0, "historical": 0, "independent": 0}
        for row in rows:
            counts[version_status(row.get("is_latest_evidence", ""))] += 1
        return counts

    @staticmethod
    def _distribution(
        rows: Iterable[dict[str, str]], field: str, *, empty_label: str = "未填写"
    ) -> list[dict[str, object]]:
        counts = Counter(row.get(field) or empty_label for row in rows)
        return [{"label": label, "count": count} for label, count in sorted(counts.items()) if label]

    def _source_profile(self, row: dict[str, object]) -> dict[str, object]:
        normalized = self.source_registry_service.normalize_row(
            {key: str(value or "") for key, value in row.items()}
        )
        role = str(row.get("role", ""))
        status_note = ""
        if role == "regulatory_authorisation":
            status_note = "正式授权"
        elif role == "regulatory_opinion":
            status_note = "CHMP积极意见，非最终批准"
        return {
            "source_id": row.get("source_id") or normalized.get("source_id", ""),
            "source_type": row.get("source_type") or normalized.get("source_type", ""),
            "title": row.get("description_zh") or row.get("normalized_title_zh") or row.get("title_original") or row.get("original_title") or normalized.get("description_zh") or normalized.get("title_original") or row.get("study_name") or normalized.get("study_name") or row.get("source_id") or normalized.get("source_id", ""),
            "study_name": row.get("study_name") or normalized.get("study_name", ""),
            "trial_id": row.get("trial_id") or normalized.get("trial_id", ""),
            "study_status": row.get("study_status") or normalized.get("study_status", ""),
            "verification_status": row.get("verification_status") or normalized.get("verification_status", ""),
            "verified_at": row.get("verified_at") or normalized.get("verified_at", ""),
            "version_status": str(row.get("version_status") or version_status(normalized.get("is_latest_evidence", ""))),
            "regulatory_event_type": row.get("regulatory_event_type") or normalized.get("regulatory_event_type", ""),
            "authorisation_status": row.get("authorisation_status") or normalized.get("authorisation_status", ""),
            "role": role,
            "status_note": status_note,
            "risk_notes": row.get("risk_notes") or normalized.get("risk_notes", ""),
            "source_url": row.get("source_url") or normalized.get("source_url", ""),
        }

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


def build_profile(company_name: str) -> dict[str, object]:
    return CompanyEvidenceProfileService().build_profile(company_name)
