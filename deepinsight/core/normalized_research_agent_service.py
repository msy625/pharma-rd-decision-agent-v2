"""Two-layer, non-speculative Agent over the normalized template dataset."""

from __future__ import annotations

import re
from time import perf_counter
from typing import Any

from deepinsight.core.evidence_chain_service import EvidenceChainService
from deepinsight.core.grounded_qa_service import GroundedQAService
from deepinsight.core.source_registry_service import NormalizedSourceRegistryService


NCT_RE = re.compile(r"\bNCT\d{8}\b", re.IGNORECASE)
PROHIBITED = ("疗效优劣", "疗效比较", "哪个更好", "成功率", "获批概率", "企业排名", "机构排名", "排名", "投资", "股价", "买入", "卖出", "success rate", "investment advice")


class NormalizedResearchAgentService:
    """Retrieve sources first, then interpret only explicit projected relations."""

    normalized_only = True

    def __init__(self, source_service: NormalizedSourceRegistryService | None = None, chain_service: EvidenceChainService | None = None) -> None:
        self.source_service = source_service or NormalizedSourceRegistryService()
        self.chain_service = chain_service or EvidenceChainService(source_registry_service=self.source_service)
        self.safety_service = GroundedQAService(source_registry_service=self.source_service, evidence_chain_service=self.chain_service)

    def capabilities(self) -> dict[str, Any]:
        return {
            "local_mode_available": True, "auto_mode_available": False, "llm_mode_available": False,
            "supported_generation_modes": ["local"], "data_scope": "manually_reviewed_normalized_research_evidence",
            "layers": {
                "source_retrieval": "返回 source_id、原始 URL 与核验状态。",
                "relationship_reasoning": "仅依据新版证据链投影和确认关系回答多来源、缺口与监管关联。",
            },
            "constraints": ["不从标题、机构名或药物名推断研究关系。", "不输出疗效优劣、成功率、排名或投资结论。"],
        }

    def run(self, question: str, generation_mode: str = "local") -> dict[str, Any]:
        started = perf_counter()
        text = str(question or "").strip()
        result = self._answer(text)
        result.update({"generation_mode": "local", "used_llm": False, "latency_ms": round((perf_counter() - started) * 1000, 3)})
        result["execution_metadata"] = {"generation_mode_requested": generation_mode, "generation_mode_used": "local", "used_llm": False, "data_backend": "normalized_template"}
        return result

    def answer_question(self, question: str, **_: Any) -> dict[str, Any]:
        result = self.run(question)
        return {
            "answer": result["answer"], "citations": result["citations"], "limitations": result["limitations"],
            "trace": {"used_llm": False, "generation_mode_used": "local", "fallback_used": False, "model_name": "normalized-template-rules"},
            "question_type": result["intent"], "evidence_used": result["source_ids"], "chain_ids": result["chain_ids"],
        }

    def _answer(self, question: str) -> dict[str, Any]:
        if not question:
            return self._result("prohibited_or_unsupported", "请输入需要检索的来源、NCT 号或证据链问题。")
        safety = self.safety_service.check_safety(question)
        if not safety.get("allowed"):
            return self._result("prohibited_or_unsupported", "该问题涉及个体医疗建议，本系统不提供此类建议；可以查询和核对研发证据。")
        if any(term in question for term in PROHIBITED):
            return self._result("prohibited_or_unsupported", "该问题涉及疗效比较、成功率、机构排名或投资结论，本系统不提供此类推断。")
        sources = self._source_retrieval(question)
        ncts = [item.upper() for item in NCT_RE.findall(question)]
        asks_relation = any(term in question for term in ("证据链", "多来源", "关系", "关联", "相关", "缺口", "监管", "支持"))
        chains = [self.chain_service.get_trial_chain(nct) for nct in ncts]
        chains = [item for item in chains if item]
        if asks_relation and ncts:
            return self._relationship_result(question, sources, chains)
        if asks_relation and not ncts:
            # A name alone may retrieve documents, but is never sufficient to join a study.
            message = "当前无法确认关联：关系推理仅接受明确的研究标识（如 NCT 号）或已投影证据链，不从标题、机构名或药物名自动关联研究。"
            return self._result("relationship_reasoning", message, sources=sources, limitations=[message])
        if not sources:
            return self._result("source_retrieval", "当前未检索到带可回查链接的规范化来源资料。")
        return self._result("source_retrieval", f"当前检索到 {len(sources)} 条规范化来源资料；以下引用包含来源编号、原始链接和核验状态。", sources=sources)

    def _relationship_result(self, question: str, sources: list[dict[str, Any]], chains: list[dict[str, Any]]) -> dict[str, Any]:
        if not chains:
            message = "当前仅检索到单来源资料；当前无法确认关联。" if len(sources) == 1 else "当前无法确认关联：未找到该研究对应的已投影证据链。"
            return self._result("relationship_reasoning", message, sources=sources, limitations=["没有明确关系时不自动补关联。"])
        chain = chains[0]
        status = chain.get("projection_status") or chain.get("chain_status") or "relationship_insufficient"
        chain_sources = [item for item in chain.get("evidence_items") or [] if item.get("source_id")]
        all_sources = self._dedupe([*sources, *chain_sources])
        # A formed chain may come from either the generated projection or the
        # retained human-curated override layer. Both are explicit evidence.
        if status == "formed" and len(chain_sources) >= 2:
            text = f"该研究已形成证据链：当前投影包含 {len(chain_sources)} 条已确认来源支持。"
        elif len(chain_sources) == 1 or status == "single_source":
            text = "当前仅检索到单来源资料；尚未形成多来源支持。"
        else:
            text = "当前无法确认关联：该研究关系不足，尚未形成证据链。"
        if "监管" in question:
            text += " 监管关联仅在存在明确 regulatory_event_id / asset_id 关系时展示；当前未自动从药物名称推断。"
        return self._result("relationship_reasoning", text, sources=all_sources, chains=chains, limitations=["关系结论只来自已确认关系和证据链投影。"])

    def _source_retrieval(self, question: str) -> list[dict[str, Any]]:
        rows = self.source_service.query(text=question, latest_only=False)[:20]
        return self._dedupe(rows)

    @staticmethod
    def _dedupe(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        seen, out = set(), []
        for row in rows:
            source_id = str(row.get("source_id") or "")
            if source_id and source_id not in seen:
                seen.add(source_id)
                out.append({"source_id": source_id, "title": row.get("title") or row.get("title_original") or row.get("study_name") or "", "source_url": row.get("source_url") or row.get("url") or "", "source_type": row.get("source_type") or "", "verification_status": row.get("verification_status") or "", "verified_at": row.get("verified_at") or ""})
        return out

    @staticmethod
    def _result(intent: str, answer: str, sources: list[dict[str, Any]] | None = None, chains: list[dict[str, Any]] | None = None, limitations: list[str] | None = None) -> dict[str, Any]:
        sources, chains = sources or [], chains or []
        ids = [item["source_id"] for item in sources if item.get("source_id")]
        chain_ids = [str(item.get("chain_id")) for item in chains if item.get("chain_id")]
        return {"intent": intent, "answer": answer, "citations": sources, "featured_citations": sources[:5], "source_ids": ids, "chain_ids": chain_ids, "limitations": limitations or ["回答仅基于规范化模板来源和证据链投影。"], "warnings": [], "error": "", "refused": intent == "prohibited_or_unsupported", "steps": [{"step_id": "S1", "name": "来源检索层", "tool": "NormalizedSourceRegistryService", "status": "completed", "result_summary": f"返回{len(sources)}条带来源编号、URL与核验状态的资料", "source_ids": ids}, {"step_id": "S2", "name": "关系推理层", "tool": "EvidenceChainService normalized projection", "status": "completed", "result_summary": f"使用{len(chain_ids)}条明确证据链", "source_ids": ids}], "source_trace": {"retrieved_source_ids": ids, "retrieved_chain_ids": chain_ids}}
