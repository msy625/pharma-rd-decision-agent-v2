"""Conservative comparison of normalized institutions.

Only coverage fields shared by both profiles are returned.  The service never
turns counts into a score, rank, winner, or enterprise-quality conclusion.
"""

from __future__ import annotations

from typing import Any

from deepinsight.core.normalized_institution_profile_service import NormalizedInstitutionProfileService
from deepinsight.core.source_registry_service import norm


COMPARABLE_FIELDS = (
    "source_count", "sponsored_study_count", "direction_count", "asset_count",
    "regulatory_event_count", "evidence_gap_count",
)


class NormalizedInstitutionComparisonService:
    def __init__(self, profile_service: NormalizedInstitutionProfileService | None = None) -> None:
        self.profile_service = profile_service or NormalizedInstitutionProfileService()

    def available_institutions(self) -> list[dict[str, str]]:
        return self.profile_service.available_institutions()

    def compare(self, institution_a: str, institution_b: str) -> dict[str, Any]:
        if not str(institution_a or "").strip() or not str(institution_b or "").strip():
            raise ValueError("机构名称不能为空。")
        if norm(institution_a) == norm(institution_b):
            raise ValueError("两个机构名称归一后相同，不能进行对比。")
        left = self.profile_service.build_profile(institution_a)
        right = self.profile_service.build_profile(institution_b)
        if not left.get("institution", {}).get("organization_id") or not right.get("institution", {}).get("organization_id"):
            raise ValueError("未找到待比较机构。")
        return {
            "institutions": [self._comparison_profile(left), self._comparison_profile(right)],
            "comparable_fields": list(COMPARABLE_FIELDS),
            "field_definitions": [
                {"field": field, "label": self._label(field), "meaning": "规范化数据中的明确覆盖数量，不代表机构规模、研发质量或竞争力。"}
                for field in COMPARABLE_FIELDS
            ],
            "comparison_notes": [
                "仅比较双方都可定义的规范化覆盖字段。",
                "缺失关系保留为数据缺口，不自动补关联。",
                "不输出综合评分、排名、优胜方或企业竞争力结论。",
                "医院、大学和研究机构按研究参与及申办覆盖展示。",
            ],
            "data_scope": "all_normalized_organizations",
            "metadata": {"data_backend": "normalized_template", "ranking": False},
        }

    def _comparison_profile(self, profile: dict[str, Any]) -> dict[str, Any]:
        institution = profile.get("institution") or {}
        summary = profile.get("summary") or {}
        identifier = institution.get("canonical_name") or institution.get("display_name") or institution.get("organization_id")
        chains = self.profile_service.chain_service.list_chains(company=identifier) if identifier else []
        return {
            "institution": institution,
            "coverage_status": profile.get("coverage_status", "relationship_insufficient"),
            "coverage": {field: summary.get(field, 0) for field in COMPARABLE_FIELDS},
            "source_type_distribution": profile.get("source_type_distribution", []),
            "study_status_distribution": profile.get("study_status_distribution", []),
            # Use the same chain IDs as the evidence-chain endpoint.  The UI can
            # therefore open a comparison entry directly instead of reconstructing
            # an ID from a study or regulatory-event row.
            "evidence_chains": [
                {
                    "chain_id": chain.get("chain_id", ""),
                    "chain_name": chain.get("chain_name", ""),
                    "chain_type": chain.get("chain_type", ""),
                    "trial_ids": chain.get("trial_ids", []),
                    "source_count": chain.get("source_count", 0),
                }
                for chain in chains
            ],
            "limitations": profile.get("limitations", []),
        }

    @staticmethod
    def _label(field: str) -> str:
        return {
            "source_count": "来源数", "sponsored_study_count": "申办研究数",
            "direction_count": "疾病方向数", "asset_count": "药物实体数",
            "regulatory_event_count": "监管事件数", "evidence_gap_count": "关系缺口数",
        }.get(field, field)
