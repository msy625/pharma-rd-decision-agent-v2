"""Thin adapters over production services; no evidence rules are reimplemented here."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Iterable

from deepinsight.core.company_evidence_comparison_service import CompanyEvidenceComparisonService
from deepinsight.core.evidence_chain_service import EvidenceChainService
from deepinsight.core.grounded_qa_service import GroundedQAService
from deepinsight.core.source_registry_service import SourceRegistryService


RESULT_FIELDS = [
    "source_ids",
    "chain_ids",
    "citations",
    "answer",
    "question_type",
    "safety_category",
    "refused",
    "used_llm",
    "limitations",
    "latency_ms",
    "error",
]


@dataclass
class NormalizedResult:
    source_ids: list[str] = field(default_factory=list)
    chain_ids: list[str] = field(default_factory=list)
    citations: list[str] = field(default_factory=list)
    answer: str = ""
    question_type: str = ""
    safety_category: str = ""
    refused: bool = False
    used_llm: bool = False
    limitations: list[str] = field(default_factory=list)
    latency_ms: float = 0.0
    error: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ProductionServiceAdapters:
    """Call existing production services and normalize their outputs."""

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

    def keyword_contains(self, case: dict[str, Any]) -> NormalizedResult:
        rows: list[dict[str, Any]] = []
        for keyword in case["request"]["keyword_queries"]:
            rows.extend(self.source_registry_service.query(text=keyword))
        return NormalizedResult(
            source_ids=self._source_ids(rows),
            question_type=self.grounded_qa_service.classify_question(case["question"]),
            limitations=["该基线仅执行来源登记表关键词包含检索，不扩展证据链或生成业务回答。"],
        )

    def structured_no_chain(self, case: dict[str, Any]) -> NormalizedResult:
        request = case["request"]
        mode = request["query_mode"]
        value = request["query_value"]
        rows: list[dict[str, Any]] = []
        if mode == "none":
            rows = []
        elif mode == "company_pair":
            for company in self._as_list(value):
                rows.extend(self.source_registry_service.query(company=company))
        elif mode == "source_ids":
            for source_id in self._as_list(value):
                rows.extend(self.source_registry_service.query(source_id=source_id))
        else:
            query_fields = {
                "study_name": "study_name",
                "drug": "drug",
                "trial_id": "trial_id",
                "source_id": "source_id",
                "company": "company",
            }
            field_name = query_fields.get(mode)
            if field_name:
                rows = self.source_registry_service.query(**{field_name: str(value)})
        return NormalizedResult(
            source_ids=self._source_ids(rows),
            question_type=self.grounded_qa_service.classify_question(case["question"]),
            limitations=["该基线仅执行现有结构化来源检索，不调用EvidenceChainService扩展证据链。"],
        )

    def grounded_qa_local(self, case: dict[str, Any]) -> NormalizedResult:
        response = self.grounded_qa_service.answer_question(case["question"])
        trace = response.get("trace") or {}
        citations = [
            str(item.get("source_id") or "")
            for item in response.get("citations") or []
            if item.get("source_id")
        ]
        safety_category = str(response.get("safety_category") or "")
        question_type = str(response.get("question_type") or "")
        return NormalizedResult(
            source_ids=self._unique(trace.get("retrieved_source_ids") or []),
            chain_ids=self._unique(trace.get("retrieved_chain_ids") or []),
            citations=self._unique(citations),
            answer=str(response.get("answer") or ""),
            question_type=question_type,
            safety_category=safety_category,
            refused=question_type == "prohibited_or_unsupported" and bool(safety_category),
            used_llm=bool(trace.get("used_llm")),
            limitations=[str(item) for item in response.get("limitations") or []],
        )

    @staticmethod
    def _as_list(value: Any) -> list[str]:
        if isinstance(value, list):
            return [str(item) for item in value]
        return [str(value)]

    @classmethod
    def _source_ids(cls, rows: Iterable[dict[str, Any]]) -> list[str]:
        return cls._unique([str(row.get("source_id") or "") for row in rows if row.get("source_id")])

    @staticmethod
    def _unique(values: Iterable[str]) -> list[str]:
        seen: set[str] = set()
        out: list[str] = []
        for value in values:
            if value and value not in seen:
                seen.add(value)
                out.append(value)
        return out
