"""Two-layer, non-speculative Agent over the normalized template dataset."""

from __future__ import annotations

import re
from collections import Counter
from time import perf_counter
from typing import Any

from deepinsight.core.evidence_chain_service import EvidenceChainService
from deepinsight.core.grounded_qa_service import GroundedQAService
from deepinsight.core.source_registry_service import NormalizedSourceRegistryService


NCT_RE = re.compile(r"\bNCT\d{8}\b", re.IGNORECASE)
PROHIBITED = ("疗效优劣", "疗效比较", "哪个更好", "成功率", "获批概率", "企业排名", "机构排名", "排名", "投资", "股价", "买入", "卖出", "success rate", "investment advice")
FACT_INTENTS = {"regulatory_status", "trial_status", "evidence_chain", "evidence_gap", "company_comparison"}
REGULATORY_TERMS = ("监管", "授权", "获批", "批准", "chmp", "ema", "epar", "上市后变更", "法律授权")


class NormalizedResearchAgentService:
    """Retrieve sources first, then interpret only explicit projected relations."""

    normalized_only = True

    def __init__(self, source_service: NormalizedSourceRegistryService | None = None, chain_service: EvidenceChainService | None = None) -> None:
        self.source_service = source_service or NormalizedSourceRegistryService()
        self.chain_service = chain_service or EvidenceChainService(source_registry_service=self.source_service)
        self.safety_service = GroundedQAService(source_registry_service=self.source_service, evidence_chain_service=self.chain_service)
        # Keep the interface used by the previous decision-agent orchestration:
        # after local retrieval, auto mode may ask the configured model to
        # organize an answer from the same normalized evidence backend.
        self.grounded_qa_service = self.safety_service

    def capabilities(self) -> dict[str, Any]:
        source_rows = self.source_service.load_rows()
        supported_companies = sorted({
            str(row.get("company_name") or row.get("company_cn") or row.get("company") or "").strip()
            for row in source_rows
            if str(row.get("company_name") or row.get("company_cn") or row.get("company") or "").strip()
        })
        return {
            "local_mode_available": True, "auto_mode_available": True, "llm_mode_available": False,
            "supported_generation_modes": ["local", "auto"], "data_scope": "manually_reviewed_normalized_research_evidence",
            "supported_intents": ["source_retrieval", "institution_analysis", "relationship_reasoning", *sorted(FACT_INTENTS), "prohibited_or_unsupported"],
            "supported_companies": supported_companies,
            "source_count": len(source_rows),
            "layers": {
                "safety": "先拦截医疗建议、疗效排名和投资判断。",
                "entity_retrieval": "从机构、药物、研究、NCT 编号和来源编号中识别可检索实体。",
                "institution_analysis": "先汇总当前命中机构的来源、研究证据链与监管链，再给出限定范围内的结构化分析。",
                "relationship_reasoning": "仅依据明确的研究标识和已投影证据链回答具体关系问题。",
                "grounded_summary": "自动模式仅在检索到证据后调用已配置模型组织答案；未配置时保留本地结构化分析。",
            },
            "constraints": ["不从标题、机构名或药物名推断研究关系。", "不输出疗效优劣、成功率、排名或投资结论。"],
        }

    def run(self, question: str, generation_mode: str = "local") -> dict[str, Any]:
        started = perf_counter()
        text = str(question or "").strip()
        result = self._answer(text)
        result.update({"question": text, "generation_mode": "local", "used_llm": False, "latency_ms": round((perf_counter() - started) * 1000, 3)})
        result["execution_metadata"] = {"generation_mode_requested": generation_mode, "generation_mode_used": "local", "used_llm": False, "data_backend": "normalized_template", "fallback_used": generation_mode == "auto", "fallback_reason": "当前 Agent 使用本地确定性证据流程，不依赖外部模型。" if generation_mode == "auto" else ""}
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

        grounded_intent = self.safety_service.classify_question(question)
        if any(term in question.casefold() for term in REGULATORY_TERMS):
            grounded_intent = "regulatory_status"
        if NCT_RE.search(question) and any(term in question for term in ("证据", "来源", "关联", "证据链", "缺口")):
            grounded_intent = "evidence_chain"
        if grounded_intent in FACT_INTENTS:
            return self._grounded_fact_result(question, grounded_intent)

        sources = self._source_retrieval(question)
        ncts = [item.upper() for item in NCT_RE.findall(question)]
        asks_relation = any(term in question for term in ("证据链", "多来源", "关系", "关联", "相关", "缺口", "监管", "支持"))
        chains = [self.chain_service.get_trial_chain(nct) for nct in ncts]
        chains = [item for item in chains if item]
        if asks_relation and ncts:
            return self._relationship_result(question, sources, chains)
        if asks_relation and not ncts:
            # An institution name is enough for a coverage analysis, but never
            # for claiming that two particular studies are related.
            institution_chains = self._institution_chains(sources)
            if sources and institution_chains:
                return self._institution_analysis_result(question, sources, institution_chains)
            message = "当前无法确认具体研究关系：请提供 NCT 编号、来源编号或已展示的证据链。机构名称本身只能用于汇总当前收录覆盖，不能自动连接具体研究。"
            return self._result("relationship_reasoning", message, sources=sources, limitations=[message])
        if not sources:
            return self._result("source_retrieval", "当前未检索到带可回查链接的规范化来源资料。")
        if any(term in question for term in ("研发情况", "研发概览", "研究情况", "研发进展", "资料覆盖", "整体情况", "概况")):
            return self._institution_analysis_result(question, sources, self._institution_chains(sources))
        categories = Counter(item.get("display_category_label") or item.get("source_type") or "其他资料" for item in sources)
        category_text = "、".join(f"{name} {count} 条" for name, count in categories.items())
        return self._result("source_retrieval", f"已检索到 {len(sources)} 条与问题直接匹配的研发资料（{category_text}）。以下结果均保留来源编号、原始链接与核验状态，可继续打开核对。", sources=sources)

    def _grounded_fact_result(self, question: str, intent: str) -> dict[str, Any]:
        """Use the typed evidence packet for questions requiring factual conclusions.

        This avoids replacing a concrete regulatory or trial conclusion with a
        generic count of retrieved records.  The local response is deterministic
        and cites only sources carried by the same packet.
        """
        packet = self.safety_service.build_evidence_packet(question, intent)
        packet = self._focus_packet_for_intent(packet, intent)
        grounded = self.safety_service.build_local_response(question, packet)
        sources = list(packet.get("all_sources") or [])
        chains = list(packet.get("chains") or [])
        source_ids = list(dict.fromkeys(str(item.get("source_id") or "") for item in sources if item.get("source_id")))
        citations = self._dedupe_citations(grounded.get("citations") or [])
        answer = self._fact_answer_with_sections(intent, str(grounded.get("answer") or ""), source_ids)
        result = self._result(intent, answer, sources=sources, chains=chains, limitations=list(grounded.get("limitations") or []))
        result.update({
            "citations": citations,
            "featured_citations": citations[:5],
            "source_ids": source_ids,
            "chain_ids": list(dict.fromkeys(str(item.get("chain_id") or "") for item in chains if item.get("chain_id"))),
            "answer_is_structured": True,
            "answer_quality": "specific_grounded",
        })
        result["source_trace"] = {source_id: ["S2", "S3"] for source_id in source_ids}
        result["steps"][1].update({
            "name": "按问题类型检索精确证据",
            "tool": "GroundedQAService.build_evidence_packet",
            "result_summary": f"完成实体识别，按 {intent} 口径返回 {len(source_ids)} 条去重来源",
            "source_ids": source_ids,
        })
        result["steps"][2].update({
            "name": "基于结构化事实生成结论",
            "tool": "GroundedQAService.build_local_response",
            "result_summary": "逐条使用来源中的监管、试验或证据链字段，不以命中数量代替结论",
            "source_ids": source_ids,
        })
        decision = result["decision"]
        decision["summary"] = answer
        decision["key_findings"] = [
            citation.get("support_summary") or f"{citation.get('source_id')} 提供直接事实支持。"
            for citation in citations
        ]
        decision["next_evidence_actions"] = [self._next_action_for_intent(intent)]
        return result

    @staticmethod
    def _focus_packet_for_intent(packet: dict[str, Any], intent: str) -> dict[str, Any]:
        """Keep a regulatory answer scoped to regulatory records only.

        A drug-name query can retrieve clinical trials and publications as
        background.  They are useful elsewhere but must not crowd out a direct
        answer about legal/regulatory status.
        """
        if intent != "regulatory_status":
            return packet
        relevant = [
            item for item in packet.get("all_sources") or []
            if item.get("regulatory_event_type") or item.get("authorisation_status")
        ]
        if not relevant:
            return packet
        focused = dict(packet)
        focused["sources"] = relevant
        focused["all_sources"] = relevant
        focused["allowed_source_ids"] = [item["source_id"] for item in relevant if item.get("source_id")]
        focused["primary_source_ids"] = list(focused["allowed_source_ids"])
        return focused

    @staticmethod
    def _dedupe_citations(citations: list[dict[str, Any]]) -> list[dict[str, Any]]:
        seen: set[str] = set()
        result = []
        for citation in citations:
            source_id = str(citation.get("source_id") or "")
            if not source_id or source_id in seen:
                continue
            seen.add(source_id)
            result.append(dict(citation, produced_by_steps=["S2", "S3"]))
        return result

    @staticmethod
    def _next_action_for_intent(intent: str) -> str:
        actions = {
            "regulatory_status": "打开监管原始页面，分别核对事件日期、机构意见与当前授权状态。",
            "trial_status": "打开研究登记页，核对研究状态、状态更新时间与完成日期类型。",
            "evidence_chain": "打开证据链详情，核对每条来源的角色与已确认关系。",
            "evidence_gap": "优先补充能明确连接研究、论文或监管事件的原始来源。",
            "company_comparison": "仅在同一数据范围内比较覆盖情况；需要具体研究时继续指定来源或 NCT 编号。",
        }
        return actions.get(intent, "打开引用来源核对原始字段和适用范围。")

    def _fact_answer_with_sections(self, intent: str, direct: str, source_ids: list[str]) -> str:
        return direct.strip() or "当前数据不足：未找到可支持该问题的已核验结构化证据。"

    @staticmethod
    def direct_answer_text(answer: str) -> str:
        """Keep only the direct-answer block from a model response, if present."""
        text = str(answer or "").strip()
        if "【直接回答】" not in text:
            return text
        direct = text.split("【直接回答】", 1)[1]
        for marker in ("【分析】", "【下一步核验】"):
            direct = direct.split(marker, 1)[0]
        return direct.strip()

    def _institution_chains(self, sources: list[dict[str, Any]]) -> list[dict[str, Any]]:
        companies = list(dict.fromkeys(str(item.get("company_name") or "").strip() for item in sources if item.get("company_name")))
        chains: list[dict[str, Any]] = []
        for company in companies:
            chains.extend(self.chain_service.list_chains(company=company))
        seen: set[str] = set()
        return [chain for chain in chains if chain.get("chain_id") and not (str(chain["chain_id"]) in seen or seen.add(str(chain["chain_id"])))]

    def _institution_analysis_result(self, question: str, sources: list[dict[str, Any]], chains: list[dict[str, Any]]) -> dict[str, Any]:
        companies = list(dict.fromkeys(str(item.get("company_name") or "").strip() for item in sources if item.get("company_name")))
        company_text = "、".join(companies) or "当前机构"
        categories = Counter(item.get("display_category_label") or item.get("source_type") or "其他资料" for item in sources)
        category_text = "、".join(f"{name} {count} 条" for name, count in categories.items())
        trial_chains = [chain for chain in chains if chain.get("chain_type") == "trial"]
        regulatory_chains = [chain for chain in chains if chain.get("chain_type") == "regulatory"]
        formed = [chain for chain in chains if chain.get("projection_status") == "formed"]
        text = (
            f"基于本次检索命中的 {len(sources)} 条可回查研发资料，{company_text} 的来源构成为：{category_text}。"
            f"当前可追溯到 {len(chains)} 条证据链，其中研究证据链 {len(trial_chains)} 条、监管链 {len(regulatory_chains)} 条，"
            f"已形成多来源关联的链 {len(formed)} 条。"
        )
        limitations = [
            "机构名称用于汇总当前收录的来源和已投影证据链；不据此自动推断具体研究之间存在关联。",
            "本分析反映当前规范化数据覆盖，不代表机构完整研发管线、疗效优劣或研发能力。",
        ]
        if any(term in question for term in ("缺口", "待确认", "不足")):
            incomplete = [chain for chain in chains if chain.get("projection_status") in {"single_source", "relationship_insufficient"}]
            text += f" 当前有 {len(incomplete)} 条链仍是单来源或关系不足，建议从链详情核对缺失的来源关系。"
        result = self._result("institution_analysis", text, sources=sources, chains=chains, limitations=limitations)
        result["decision"]["key_findings"] = [
            f"当前收录来源：{len(sources)} 条。",
            f"研究证据链：{len(trial_chains)} 条；监管链：{len(regulatory_chains)} 条。",
            f"已形成多来源关联：{len(formed)} 条。",
        ]
        result["decision"]["evidence_gaps"] = [
            "具体研究关系只在存在明确研究标识或已投影链时确认。"
        ]
        result["decision"]["next_evidence_actions"] = [
            "如需核对具体研究，请继续提供 NCT 编号、来源编号或选择证据链。"
        ]
        return result

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
        text_key = self._key(question)
        rows = self.source_service.load_rows()
        matched: list[dict[str, Any]] = []

        def add(items: list[dict[str, Any]]) -> None:
            matched.extend(items)

        for company in self._matching_values(rows, ("company_cn", "company"), text_key):
            add(self.source_service.query(company=company, latest_only=False))
        for drug in self._matching_drugs(rows, text_key):
            add(self.source_service.query(drug=drug, latest_only=False))
        for study in self._matching_values(rows, ("study_name",), text_key):
            add(self.source_service.query(study_name=study, latest_only=False))
        for trial_id in NCT_RE.findall(question):
            add(self.source_service.query(trial_id=trial_id.upper(), latest_only=False))
        for source_id in re.findall(r"\b[A-Z]{1,8}\d{3,8}\b", question.upper()):
            add(self.source_service.query(source_id=source_id, latest_only=False))

        # Keep a short keyword fallback for questions that contain neither a
        # normalized entity nor an identifier. The full sentence is never used
        # as a literal query because it would make ordinary natural questions
        # return an empty result.
        if not matched:
            for token in re.findall(r"[A-Za-z][A-Za-z0-9_-]{2,}|[\u4e00-\u9fff]{2,}", question):
                if token in {"哪些", "什么", "当前", "资料", "研发", "证据", "问题", "有关", "可以"}:
                    continue
                found = self.source_service.query(text=token, latest_only=False)
                if found:
                    add(found)
                    break
        return self._dedupe(matched)[:20]

    @staticmethod
    def _key(value: str) -> str:
        return re.sub(r"[^a-z0-9\u4e00-\u9fff]", "", str(value or "").casefold())

    def _matching_values(self, rows: list[dict[str, Any]], fields: tuple[str, ...], text_key: str) -> list[str]:
        values: list[str] = []
        for row in rows:
            for field in fields:
                value = str(row.get(field) or "").strip()
                key = self._key(value)
                if len(key) >= 2 and key in text_key:
                    values.append(value)
        return list(dict.fromkeys(values))

    def _matching_drugs(self, rows: list[dict[str, Any]], text_key: str) -> list[str]:
        values: list[str] = []
        for row in rows:
            for value in re.split(r"[;,，；/|]", str(row.get("drug_names") or "")):
                value = value.strip()
                key = self._key(value)
                if len(key) >= 2 and key in text_key:
                    values.append(value)
        return list(dict.fromkeys(values))

    @staticmethod
    def _dedupe(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        seen, out = set(), []
        for row in rows:
            source_id = str(row.get("source_id") or "")
            if source_id and source_id not in seen:
                seen.add(source_id)
                out.append({"source_id": source_id, "title": row.get("title") or row.get("title_original") or row.get("study_name") or "", "source_url": row.get("source_url") or row.get("url") or "", "source_type": row.get("source_type") or "", "display_category_label": row.get("display_category_label") or "", "company_name": row.get("company_name") or row.get("company_cn") or "", "verification_status": row.get("verification_status") or "", "verified_at": row.get("verified_at") or ""})
        return out

    @staticmethod
    def _result(intent: str, answer: str, sources: list[dict[str, Any]] | None = None, chains: list[dict[str, Any]] | None = None, limitations: list[str] | None = None) -> dict[str, Any]:
        sources, chains = sources or [], chains or []
        ids = [item["source_id"] for item in sources if item.get("source_id")]
        chain_ids = [str(item.get("chain_id")) for item in chains if item.get("chain_id")]
        companies = list(dict.fromkeys(str(item.get("company_name") or item.get("company_cn") or "").strip() for item in sources if item.get("company_name") or item.get("company_cn")))
        drugs = list(dict.fromkeys(value.strip() for item in sources for value in re.split(r"[;,，；/|]", str(item.get("drug_names") or "")) if value.strip()))
        studies = list(dict.fromkeys(str(item.get("study_name") or "").strip() for item in sources if item.get("study_name")))
        trial_ids = list(dict.fromkeys(match.upper() for item in sources for match in NCT_RE.findall(" ".join(str(item.get(field) or "") for field in ("trial_ids", "study_name", "title", "title_original")))))
        entities = {"companies": companies, "drugs": drugs, "studies": studies, "trial_ids": trial_ids, "source_ids": ids}
        citations = [dict(item, produced_by_steps=["S2"], support_summary="由已匹配的规范化来源记录提供。") for item in sources]
        return {"intent": intent, "answer": answer, "entities": entities, "citations": citations, "featured_citations": citations[:5], "source_ids": ids, "chain_ids": chain_ids, "limitations": limitations or ["回答仅基于规范化来源及其明确关系，不从标题或名称补充推断。"], "warnings": [], "error": "", "refused": intent == "prohibited_or_unsupported", "decision": {"summary": answer, "key_findings": [f"已匹配 {len(sources)} 条可回查来源资料。"] if sources else [], "evidence_gaps": [] if sources else ["当前问题未命中可回查的规范化来源。"], "next_evidence_actions": ["可继续使用机构名称、药物名称、研究名称、NCT 编号或来源编号缩小范围。"], "supported_conclusions": ["结论仅覆盖本次返回的来源记录。"] if sources else [], "unsupported_conclusions": ["不输出疗效优劣、获批概率、机构排名或投资判断。"], "risk_flags": [], "comparison_dimensions": [], "evidence_maturity": [{"title": "本次来源覆盖", "rows": [{"label": "可回查来源", "value": f"{len(sources)} 条"}, {"label": "明确证据链", "value": f"{len(chain_ids)} 条"}]}], "scope_statement": "本回答基于当前网站的规范化研发证据数据，不代表完整研发管线或临床医疗建议。"}, "steps": [{"step_id": "S1", "name": "安全范围校验", "tool": "GroundedQAService.check_safety", "status": "completed", "input_summary": "校验问题是否属于研发证据查询范围", "result_summary": "问题在可回答的研发证据范围内", "source_ids": []}, {"step_id": "S2", "name": "实体识别与来源检索", "tool": "NormalizedSourceRegistryService.query", "status": "completed", "input_summary": "识别机构、药物、研究、NCT编号和来源编号", "result_summary": f"识别 {sum(len(values) for values in entities.values())} 个实体，返回 {len(sources)} 条匹配资料", "source_ids": ids}, {"step_id": "S3", "name": "明确关系核验与本地总结", "tool": "EvidenceChainService normalized projection", "status": "completed", "input_summary": "核对已确认的来源与证据链关系", "result_summary": f"使用 {len(chain_ids)} 条明确证据链，不补充未确认关系", "source_ids": ids}], "source_trace": {source_id: ["S2"] for source_id in ids}}
