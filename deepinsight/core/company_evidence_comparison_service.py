"""Company evidence comparison service for the current verified NSCLC sample.

This module composes SourceRegistryService and EvidenceChainService. It avoids
model, vector-store, network, database, or web framework dependencies.
"""

from __future__ import annotations

from collections import Counter
from typing import Iterable

from deepinsight.core.evidence_chain_service import EvidenceChainService
from deepinsight.core.source_registry_service import SourceRegistryService, norm


DATA_SCOPE = "first_version_nsclc_hengrui_beone"
INTERPRETATION_SCOPE = "current_verified_sample_only"
SCOPE_WARNING = "以下结果仅反映当前收录并核验的NSCLC证据样本，不代表企业整体研发实力。"

COMPANY_SUBJECTS = [
    {
        "company_name": "恒瑞医药",
        "display_name": "恒瑞医药",
        "aliases": ["恒瑞医药", "江苏恒瑞医药股份有限公司", "Jiangsu Hengrui Medicine", "Jiangsu HengRui Medicine"],
    },
    {
        "company_name": "百济神州",
        "display_name": "百济神州/BeOne Medicines",
        "aliases": ["百济神州", "BeOne Medicines", "BeiGene", "百济神州（BeOne Medicines，原BeiGene）"],
    },
]

DIRECTLY_COMPARABLE_METRICS = [
    "source_count",
    "verified_source_count",
    "trial_chain_count",
    "regulatory_chain_count",
    "source_type_distribution",
    "version_distribution",
    "single_source_trial_chain_count",
    "multi_source_trial_chain_count",
    "unresolved_link_count",
]

PARTIALLY_COMPARABLE_DIMENSIONS = [
    {
        "name": "临床研究状态分布",
        "reason": "study_status 混合了登记状态、公告事件状态和监管不适用状态，只能展示原始分布。",
    },
    {
        "name": "临床阶段分布",
        "reason": "study_phase 存在空值、不适用和文件未明确，且来源口径不同。",
    },
    {
        "name": "研究人群覆盖",
        "reason": "population、histology、biomarker_requirements 粒度不一致，不能自动推断完整覆盖。",
    },
    {
        "name": "治疗场景覆盖",
        "reason": "treatment_line、regimen_detail、comparator 不完整，不能从标题或药物名称补全。",
    },
]

COMPARISON_NOTES = [
    SCOPE_WARNING,
    "来源数量、证据链数量和多来源链数量只能说明当前样本覆盖，不代表研发质量或企业实力。",
    "药物级监管链不计入临床试验数量。",
    "多来源试验链可能代表证据关联更完整，也可能只是当前采集覆盖不同。",
    "当前数据不足时应显示“当前数据不足”，不得从标题或药物名称自动推断。",
]

PROHIBITED_CONCLUSIONS = [
    "不输出综合评分。",
    "不输出企业排名或优胜方。",
    "不预测项目成功率。",
    "不比较跨试验疗效或安全性优劣。",
    "不提供投资建议。",
    "不自动推断研究人群、治疗场景、靶点或机制。",
]


class CompanyEvidenceComparisonService:
    """Build company-level evidence sample comparisons from existing services."""

    def __init__(
        self,
        *,
        source_registry_service: SourceRegistryService | None = None,
        evidence_chain_service: EvidenceChainService | None = None,
    ) -> None:
        self.source_registry_service = source_registry_service or SourceRegistryService()
        self.evidence_chain_service = evidence_chain_service or EvidenceChainService(
            source_registry_service=self.source_registry_service
        )

    def available_companies(self) -> list[dict[str, object]]:
        return [dict(subject) for subject in COMPANY_SUBJECTS]

    def company_profile(self, company_name: str) -> dict[str, object]:
        subject = self._resolve_company(company_name)
        if not subject:
            return self._empty_profile(company_name)

        rows = self.source_registry_service.query(company=subject["company_name"], normalized=False)
        chains = self.evidence_chain_service.list_chains(company=subject["company_name"])
        trial_chains = [chain for chain in chains if chain.get("chain_type") == "trial"]
        regulatory_chains = [chain for chain in chains if chain.get("chain_type") == "regulatory"]
        unresolved_links = self._company_unresolved_links(subject["company_name"])

        return {
            "company_name": subject["company_name"],
            "display_name": subject["display_name"],
            "data_scope": DATA_SCOPE,
            "interpretation_scope": INTERPRETATION_SCOPE,
            "source_count": len(rows),
            "verified_source_count": sum(1 for row in rows if row.get("verification_status") == "已人工核验"),
            "trial_chain_count": len(trial_chains),
            "regulatory_chain_count": len(regulatory_chains),
            "source_type_distribution": self._distribution(rows, "source_type"),
            "version_distribution": self._version_distribution(rows),
            "single_source_trial_chain_count": sum(1 for chain in trial_chains if chain.get("source_count", 0) == 1),
            "multi_source_trial_chain_count": sum(1 for chain in trial_chains if chain.get("source_count", 0) > 1),
            "unresolved_link_count": len(unresolved_links),
            "trial_chains": self._chain_summaries(trial_chains),
            "regulatory_chains": self._chain_summaries(regulatory_chains),
            "evidence_gaps": self._evidence_gaps(unresolved_links),
            "comparison_note": SCOPE_WARNING,
        }

    def compare(self, company_a: str, company_b: str) -> dict[str, object]:
        if not str(company_a or "").strip() or not str(company_b or "").strip():
            raise ValueError("企业名称不能为空。")
        if norm(company_a).strip() == norm(company_b).strip():
            raise ValueError("两个企业名称归一后相同，不能进行对比。")

        subject_a = self._resolve_company(company_a)
        subject_b = self._resolve_company(company_b)
        if subject_a and subject_b and subject_a["company_name"] == subject_b["company_name"]:
            raise ValueError("两个企业名称归一后相同，不能进行对比。")

        profile_a = self.company_profile(company_a)
        profile_b = self.company_profile(company_b)

        return {
            "companies": [profile_a, profile_b],
            "metric_definitions": self.metric_rules(),
            "directly_comparable_metrics": list(DIRECTLY_COMPARABLE_METRICS),
            "partially_comparable_dimensions": list(PARTIALLY_COMPARABLE_DIMENSIONS),
            "comparison_notes": list(COMPARISON_NOTES),
            "prohibited_conclusions": list(PROHIBITED_CONCLUSIONS),
            "generated_from": ["SourceRegistryService", "EvidenceChainService", "evidence_chains.json", "source_registry.csv"],
            "data_scope": DATA_SCOPE,
            "interpretation_scope": INTERPRETATION_SCOPE,
        }

    def metric_rules(self) -> list[dict[str, object]]:
        return [
            {
                "name": "当前样本来源数量",
                "field": "source_count",
                "calculation": "按归一化企业名称统计当前来源注册表中的资料条数。",
                "directly_comparable": True,
                "correct_interpretation": "只能解释为当前收录样本内该企业资料覆盖数量。",
                "prohibited_interpretation": "不能解释为企业研发实力、项目质量、市场价值或资料完整程度。",
            },
            {
                "name": "已核验来源数量",
                "field": "verified_source_count",
                "calculation": "在企业来源中统计 verification_status 等于 已人工核验 的条数。",
                "directly_comparable": True,
                "correct_interpretation": "只能解释为当前样本内已完成人工核验的来源数量。",
                "prohibited_interpretation": "不能解释为外部公开证据总量或企业信息披露质量。",
            },
            {
                "name": "试验级证据链数量",
                "field": "trial_chain_count",
                "calculation": "通过 EvidenceChainService 统计 chain_type 为 trial 的证据链数量。",
                "directly_comparable": True,
                "correct_interpretation": "只能解释为当前样本中已人工确认的试验级证据链数量。",
                "prohibited_interpretation": "不能解释为企业临床试验总数或研发能力强弱。",
            },
            {
                "name": "药物级监管链数量",
                "field": "regulatory_chain_count",
                "calculation": "通过 EvidenceChainService 统计 chain_type 为 regulatory 的证据链数量。",
                "directly_comparable": True,
                "correct_interpretation": "只能解释为当前样本中药物级监管事件链数量，且不计入临床试验数量。",
                "prohibited_interpretation": "不能解释为具体试验数量，也不能替代试验级证据。",
            },
            {
                "name": "来源类型构成",
                "field": "source_type_distribution",
                "calculation": "按 source_type 对企业来源分组计数。",
                "directly_comparable": True,
                "correct_interpretation": "可说明当前样本中登记、论文、公司资料和监管资料的来源构成。",
                "prohibited_interpretation": "不能解释为证据质量排序或企业披露充分性。",
            },
            {
                "name": "版本构成",
                "field": "version_distribution",
                "calculation": "is_latest_evidence 为 true 计最新，false 计历史，空值计独立资料。",
                "directly_comparable": True,
                "correct_interpretation": "可说明当前样本内最新、历史和无版本关系资料的构成。",
                "prohibited_interpretation": "不能解释为研究结论更优或项目更成熟。",
            },
            {
                "name": "多来源试验链数量",
                "field": "multi_source_trial_chain_count",
                "calculation": "统计 trial 链中 source_count 大于 1 的证据链数量。",
                "directly_comparable": True,
                "correct_interpretation": "只能解释为当前样本中已建立多来源关联的试验链数量。",
                "prohibited_interpretation": "不能解释为研发质量、企业实力、疗效优势或项目成功概率。",
            },
            {
                "name": "待确认关系数量",
                "field": "unresolved_link_count",
                "calculation": "通过 EvidenceChainService 的 unresolved_links 按归一化企业归属计数。",
                "directly_comparable": True,
                "correct_interpretation": "可说明当前样本内仍缺少明确试验关联或监管归属的一对一关系数量。",
                "prohibited_interpretation": "不能解释为错误数据，也不能解释为企业信息质量差。",
            },
            {
                "name": "临床研究状态、阶段、人群和治疗场景",
                "field": "partial_dimensions",
                "calculation": "仅展示已有结构化字段的原始分布或缺口。",
                "directly_comparable": False,
                "correct_interpretation": "只能作为部分可比较维度，提示当前数据覆盖与缺失情况。",
                "prohibited_interpretation": "不能自动推断完整研究人群、治疗场景、靶点、机制或跨试验疗效结论。",
            },
        ]

    def _resolve_company(self, company_name: str) -> dict[str, object] | None:
        key = norm(company_name).strip()
        if not key:
            return None
        for subject in COMPANY_SUBJECTS:
            aliases = [norm(alias) for alias in subject["aliases"]]
            if key in aliases or any(key in alias or alias in key for alias in aliases):
                return subject
        return None

    def _empty_profile(self, company_name: str) -> dict[str, object]:
        return {
            "company_name": str(company_name or "").strip(),
            "display_name": str(company_name or "").strip(),
            "data_scope": DATA_SCOPE,
            "interpretation_scope": INTERPRETATION_SCOPE,
            "source_count": 0,
            "verified_source_count": 0,
            "trial_chain_count": 0,
            "regulatory_chain_count": 0,
            "source_type_distribution": {},
            "version_distribution": {"latest": 0, "historical": 0, "independent": 0},
            "single_source_trial_chain_count": 0,
            "multi_source_trial_chain_count": 0,
            "unresolved_link_count": 0,
            "trial_chains": [],
            "regulatory_chains": [],
            "evidence_gaps": [f"当前数据不足：未在当前收录样本内识别到企业 {company_name}。"],
            "comparison_note": SCOPE_WARNING,
        }

    def _company_unresolved_links(self, company_name: str) -> list[dict[str, object]]:
        links = []
        for item in self.evidence_chain_service.get_unresolved_links():
            source = item.get("source", {})
            if isinstance(source, dict) and norm(source.get("company_name")) == norm(company_name):
                links.append(item)
        return links

    @staticmethod
    def _distribution(rows: Iterable[dict[str, str]], field: str) -> dict[str, int]:
        counts = Counter(row.get(field) or "未填写" for row in rows)
        return dict(sorted(counts.items()))

    @staticmethod
    def _version_distribution(rows: Iterable[dict[str, str]]) -> dict[str, int]:
        distribution = {"latest": 0, "historical": 0, "independent": 0}
        for row in rows:
            value = norm(row.get("is_latest_evidence"))
            if value == "true":
                distribution["latest"] += 1
            elif value == "false":
                distribution["historical"] += 1
            else:
                distribution["independent"] += 1
        return distribution

    @staticmethod
    def _chain_summaries(chains: Iterable[dict[str, object]]) -> list[dict[str, object]]:
        return [
            {
                "chain_id": chain.get("chain_id", ""),
                "chain_name": chain.get("chain_name", ""),
                "chain_type": chain.get("chain_type", ""),
                "trial_ids": chain.get("trial_ids", []),
                "source_count": chain.get("source_count", 0),
                "source_ids": [item.get("source_id", "") for item in chain.get("evidence_items", [])],
                "evidence_gaps": chain.get("evidence_gaps", []),
            }
            for chain in chains
        ]

    @staticmethod
    def _evidence_gaps(unresolved_links: Iterable[dict[str, object]]) -> list[dict[str, object]]:
        return [
            {
                "source_id": item.get("source_id", ""),
                "description": item.get("description", ""),
                "evidence_gaps": item.get("evidence_gaps", []),
            }
            for item in unresolved_links
        ]


def company_profile(company_name: str) -> dict[str, object]:
    return CompanyEvidenceComparisonService().company_profile(company_name)


def compare(company_a: str, company_b: str) -> dict[str, object]:
    return CompanyEvidenceComparisonService().compare(company_a, company_b)


def metric_rules() -> list[dict[str, object]]:
    return CompanyEvidenceComparisonService().metric_rules()


def available_companies() -> list[dict[str, object]]:
    return CompanyEvidenceComparisonService().available_companies()
