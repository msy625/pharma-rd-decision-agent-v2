"""Evidence workbench service for the verified NSCLC sample.

This module composes existing local evidence services. It does not import web
framework, database, vector-store, model, or network dependencies.
"""

from __future__ import annotations

import re
from collections import Counter
from datetime import datetime, timezone
from typing import Iterable

from deepinsight.core.company_evidence_comparison_service import (
    DATA_SCOPE,
    SCOPE_WARNING,
    CompanyEvidenceComparisonService,
)
from deepinsight.core.evidence_chain_service import EvidenceChainService, version_status
from deepinsight.core.grounded_qa_service import GroundedQAService
from deepinsight.core.source_registry_service import SourceRegistryService


LIMITATIONS = [
    SCOPE_WARNING,
    "工作台只统计当前来源登记表和已人工配置的证据链，不代表外部公开证据全集。",
    "药物级监管链单独统计，不计入试验级证据链数量。",
    "待确认关系表示当前样本尚缺少明确一对一关联，不等同于错误数据。",
    "不输出企业定量优劣结论、疗效优劣或投资建议。",
]


class EvidenceWorkbenchService:
    """Build a real evidence decision workbench from verified local services."""

    def __init__(
        self,
        *,
        source_registry_service: SourceRegistryService | None = None,
        evidence_chain_service: EvidenceChainService | None = None,
        company_comparison_service: CompanyEvidenceComparisonService | None = None,
        grounded_qa_service: GroundedQAService | None = None,
    ) -> None:
        self.source_registry_service = source_registry_service or SourceRegistryService()
        self.evidence_chain_service = evidence_chain_service or EvidenceChainService(
            source_registry_service=self.source_registry_service
        )
        self.company_comparison_service = company_comparison_service or CompanyEvidenceComparisonService(
            source_registry_service=self.source_registry_service,
            evidence_chain_service=self.evidence_chain_service,
        )
        self.grounded_qa_service = grounded_qa_service or GroundedQAService(
            source_registry_service=self.source_registry_service,
            evidence_chain_service=self.evidence_chain_service,
            company_comparison_service=self.company_comparison_service,
        )

    def summary(self) -> dict[str, object]:
        rows = self.source_registry_service.load_rows()
        chain_summary = self.evidence_chain_service.summary()
        versions = self._version_distribution(rows)
        return {
            "source_count": len(rows),
            "verified_source_count": sum(1 for row in rows if row.get("verification_status") == "已人工核验"),
            "company_count": len(self.company_comparison_service.available_companies()),
            "trial_chain_count": int(chain_summary.get("trial_chains", 0) or 0),
            "regulatory_chain_count": int(chain_summary.get("regulatory_chains", 0) or 0),
            "latest_count": versions["latest"],
            "historical_count": versions["historical"],
            "independent_count": versions["independent"],
            "unresolved_link_count": int(chain_summary.get("unresolved_links", 0) or 0),
        }

    def company_overview(self) -> list[dict[str, object]]:
        companies = []
        for subject in self.company_comparison_service.available_companies():
            company_name = str(subject.get("company_name", ""))
            profile = self.company_comparison_service.company_profile(company_name)
            rows = self.source_registry_service.query(company=company_name, normalized=False)
            companies.append(
                {
                    "company_name": profile.get("company_name", company_name),
                    "display_name": profile.get("display_name", company_name),
                    "source_count": profile.get("source_count", 0),
                    "verified_source_count": profile.get("verified_source_count", 0),
                    "trial_chain_count": profile.get("trial_chain_count", 0),
                    "regulatory_chain_count": profile.get("regulatory_chain_count", 0),
                    "multi_source_trial_chain_count": profile.get("multi_source_trial_chain_count", 0),
                    "unresolved_link_count": profile.get("unresolved_link_count", 0),
                    "version_distribution": profile.get("version_distribution", {}),
                    "source_type_distribution": profile.get("source_type_distribution", {}),
                    "latest_verified_at": self._latest_verified_at(rows),
                    "drug_names": self._drug_names(rows),
                    "evidence_gaps": profile.get("evidence_gaps", []),
                }
            )
        return companies

    def source_type_distribution(self) -> list[dict[str, object]]:
        rows = self.source_registry_service.load_rows()
        return self._distribution(rows, "source_type")

    def study_status_distribution(self) -> list[dict[str, object]]:
        rows = self.source_registry_service.load_rows()
        return self._distribution(rows, "study_status", empty_label="未填写或不适用")

    def evidence_gaps(self) -> list[dict[str, object]]:
        gaps = []
        for item in self.evidence_chain_service.get_unresolved_links():
            source = item.get("source", {})
            if not isinstance(source, dict):
                source = {}
            gaps.append(
                {
                    "source_id": item.get("source_id", ""),
                    "company_name": source.get("company_name", ""),
                    "source_type": source.get("source_type", ""),
                    "title": source.get("description_zh") or source.get("title_original") or item.get("source_id", ""),
                    "description": item.get("description", ""),
                    "evidence_gaps": list(item.get("evidence_gaps", [])) if isinstance(item.get("evidence_gaps"), list) else [],
                }
            )
        return gaps

    def build_workbench(self) -> dict[str, object]:
        rows = self.source_registry_service.load_rows()
        return {
            "summary": self.summary(),
            "companies": self.company_overview(),
            "source_type_distribution": self.source_type_distribution(),
            "study_status_distribution": self.study_status_distribution(),
            "evidence_gaps": self.evidence_gaps(),
            "metadata": self.metadata(rows),
            "limitations": list(LIMITATIONS),
        }

    def metadata(self, rows: Iterable[dict[str, str]] | None = None) -> dict[str, str]:
        selected_rows = list(rows) if rows is not None else self.source_registry_service.load_rows()
        company_names = "；".join(
            str(subject.get("display_name") or subject.get("company_name") or "")
            for subject in self.company_comparison_service.available_companies()
            if subject.get("display_name") or subject.get("company_name")
        )
        return {
            "data_scope": DATA_SCOPE,
            "data_scope_label": f"NSCLC；{company_names}；{len(selected_rows)}条人工核验来源",
            "data_version": self.grounded_qa_service.data_version(),
            "latest_verified_at": self._latest_verified_at(selected_rows),
            "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "generated_at_note": "响应生成时间，不代表证据事件日期或核验日期。",
        }

    @staticmethod
    def _distribution(
        rows: Iterable[dict[str, str]],
        field: str,
        *,
        empty_label: str = "未填写",
    ) -> list[dict[str, object]]:
        counts = Counter(row.get(field) or empty_label for row in rows)
        return [{"label": label, "count": count} for label, count in sorted(counts.items()) if label]

    @staticmethod
    def _version_distribution(rows: Iterable[dict[str, str]]) -> dict[str, int]:
        counts = {"latest": 0, "historical": 0, "independent": 0}
        for row in rows:
            counts[version_status(row.get("is_latest_evidence", ""))] += 1
        return counts

    @staticmethod
    def _latest_verified_at(rows: Iterable[dict[str, str]]) -> str:
        dates = sorted({row.get("verified_at", "") for row in rows if row.get("verified_at", "")})
        return dates[-1] if dates else ""

    @staticmethod
    def _drug_names(rows: Iterable[dict[str, str]]) -> list[str]:
        names: set[str] = set()
        for row in rows:
            for item in re.split(r"[;,，、/]+", row.get("drug_names", "")):
                item = item.strip()
                if item:
                    names.add(item)
        return sorted(names)


def build_workbench() -> dict[str, object]:
    return EvidenceWorkbenchService().build_workbench()
