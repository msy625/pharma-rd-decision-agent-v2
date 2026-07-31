"""Lightweight R&D decision Agent over the verified NSCLC evidence services.

The service is intentionally deterministic in local mode. It coordinates the
existing local evidence services and records only user-facing execution
metadata, not hidden reasoning.
"""

from __future__ import annotations

import re
from time import perf_counter
from typing import Any, Callable

from deepinsight.core.company_evidence_comparison_service import (
    SCOPE_WARNING as COMPANY_SCOPE_WARNING,
    CompanyEvidenceComparisonService,
)
from deepinsight.core.company_evidence_profile_service import CompanyEvidenceProfileService
from deepinsight.core.evidence_chain_service import EvidenceChainService, version_status
from deepinsight.core.grounded_qa_service import GroundedQAService, NCT_RE, SOURCE_ID_RE
from deepinsight.core.rd_event_timeline_service import RDEventTimelineService
from deepinsight.core.source_registry_service import SourceRegistryService, norm


SUPPORTED_INTENTS = [
    "company_comparison",
    "evidence_gap",
    "regulatory_status",
    "trial_status",
    "evidence_chain",
    "source_search",
    "prohibited_or_unsupported",
]
DATA_SCOPE = "verified_nsclc_multi_company_sample"
SCOPE_STATEMENT = (
    "本分析仅限当前本地已核验的NSCLC证据样本，覆盖恒瑞医药、百济神州、阿斯利康三家公司及"
    "Source Registry中已有来源；不代表完整研发管线、疗效优劣、医疗建议或投资建议。"
)
EXTRA_DRUG_ALIASES = {
    "奥希替尼": ["奥希替尼", "泰瑞沙", "TAGRISSO", "Osimertinib", "AZD9291"],
}
REGULATORY_DRUG_TERMS = ["替雷利珠单抗", "Tislelizumab", "TEVIMBRA", "Tevimbra", "BGB-A317"]
COMPANY_COMPARISON_TERMS = ["比较", "对比", "差异", "区别", "各自特点", "相比"]
MODEL_EXECUTION_LIMITATION_TERMS = ["未调用大模型", "未调用语言模型", "模型调用", "模型输出", "模型服务", "模型鉴权", "模型账户"]
FEATURED_SOURCE_TYPE_PRIORITY = ["trial_registry", "publication", "company", "regulatory"]


def _unique(values: list[str]) -> list[str]:
    seen = set()
    out = []
    for value in values:
        item = str(value or "").strip()
        key = norm(item)
        if item and key not in seen:
            seen.add(key)
            out.append(item)
    return out


def _term_match_start(text: str, term: str) -> int | None:
    raw_text = str(text or "")
    raw_term = str(term or "").strip()
    if not raw_term:
        return None
    if re.search(r"[A-Za-z0-9]", raw_term):
        pattern = re.escape(raw_term).replace(r"\ ", r"\s+")
        match = re.search(rf"(?<![A-Za-z0-9]){pattern}(?![A-Za-z0-9])", raw_text, re.IGNORECASE)
        return match.start() if match else None
    index = norm(raw_text).find(norm(raw_term))
    return index if index >= 0 else None


def _contains_term(text: str, term: str) -> bool:
    return _term_match_start(text, term) is not None


def _source_sort_key(source_id: str) -> tuple[str, int, str]:
    match = re.match(r"^([A-Z]+)(\d+)$", str(source_id or "").upper())
    if match:
        return (match.group(1), int(match.group(2)), "")
    return (str(source_id or ""), 0, str(source_id or ""))


class RDDecisionAgentService:
    """Deterministic backend MVP for evidence-grounded R&D decision workflows."""

    def __init__(
        self,
        *,
        source_registry_service: SourceRegistryService | None = None,
        evidence_chain_service: EvidenceChainService | None = None,
        company_comparison_service: CompanyEvidenceComparisonService | None = None,
        company_profile_service: CompanyEvidenceProfileService | None = None,
        rd_event_timeline_service: RDEventTimelineService | None = None,
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
        self.company_profile_service = company_profile_service or CompanyEvidenceProfileService(
            source_registry_service=self.source_registry_service,
            evidence_chain_service=self.evidence_chain_service,
            company_comparison_service=self.company_comparison_service,
        )
        self.rd_event_timeline_service = rd_event_timeline_service or RDEventTimelineService(
            source_registry_service=self.source_registry_service,
            evidence_chain_service=self.evidence_chain_service,
            company_evidence_profile_service=self.company_profile_service,
        )
        self.grounded_qa_service = grounded_qa_service or GroundedQAService(
            source_registry_service=self.source_registry_service,
            evidence_chain_service=self.evidence_chain_service,
            company_comparison_service=self.company_comparison_service,
        )

    def capabilities(self) -> dict[str, Any]:
        return {
            "local_mode_available": True,
            "auto_mode_available": True,
            "llm_mode_available": False,
            "supported_generation_modes": ["local", "auto"],
            "supported_intents": list(SUPPORTED_INTENTS),
            "supported_companies": self.company_profile_service.available_companies(),
            "data_scope": DATA_SCOPE,
            "scope_statement": SCOPE_STATEMENT,
            "data_version": self.data_version(),
            "tool_mapping": {
                "company_comparison": [
                    "CompanyEvidenceComparisonService.compare",
                    "CompanyEvidenceProfileService.build_profile",
                ],
                "evidence_gap": [
                    "EvidenceChainService.get_trial_chain/list_chains",
                    "SourceRegistryService.get_by_source_id",
                ],
                "regulatory_status": [
                    "GroundedQAService.answer_question",
                    "EvidenceChainService.get_drug_regulatory_chain/get_chain",
                ],
                "trial_status": [
                    "GroundedQAService.answer_question",
                    "EvidenceChainService.get_trial_chain/list_chains",
                ],
                "evidence_chain": [
                    "GroundedQAService.answer_question",
                    "EvidenceChainService.get_trial_chain/list_chains",
                ],
                "source_search": ["GroundedQAService.answer_question"],
                "prohibited_or_unsupported": ["GroundedQAService.check_safety"],
            },
            "evaluation_metrics": [
                "intent_accuracy",
                "entity_extraction_exact_match",
                "tool_selection_accuracy",
                "unnecessary_tool_call_rate",
                "citation_whitelist_compliance",
                "step_faithfulness",
                "end_to_end_strict_pass_rate",
                "latency_ms",
            ],
            "golden_demo_paths": [
                "企业研发证据比较",
                "证据缺口分析",
                "监管状态辨析",
            ],
        }

    def run(self, question: str, generation_mode: str = "local") -> dict[str, Any]:
        started = perf_counter()
        text = str(question or "").strip()
        mode = str(generation_mode or "local").strip().lower()
        warnings: list[str] = []
        if mode not in {"local", "auto"}:
            warnings.append("generation_mode只支持local或auto，已回退到local。")
            mode = "local"
        response = self._base_response(text, mode)
        response["warnings"] = warnings
        if not text:
            response["intent"] = "prohibited_or_unsupported"
            response["error"] = "question 不能为空。"
            response["answer"] = "请输入需要分析的研发决策问题。"
            response["latency_ms"] = self._elapsed_ms(started)
            return response

        try:
            safety = self._run_step(
                response,
                name="安全检查",
                tool="GroundedQAService.check_safety",
                reason="在任何业务工具调用前识别医疗个体建议等不支持问题",
                input_summary="用户问题",
                func=lambda: self.grounded_qa_service.check_safety(text),
                summary_func=lambda result: "允许继续" if result.get("allowed") else f"拒答类别：{result.get('safety_category', '')}",
                record_source_ids=False,
            )
            if not safety.get("allowed"):
                response.update(self._refusal_payload(text, safety))
                response["plan"] = self._plan_for("prohibited_or_unsupported", response["entities"])
                response["latency_ms"] = self._elapsed_ms(started)
                return response

            recognition = self._run_step(
                response,
                name="识别任务与实体",
                tool="GroundedQAService.classify_question + RDDecisionAgentService.extract_entities",
                reason="确定任务类型、企业、研究、药物、试验编号和来源编号",
                input_summary="用户问题",
                func=lambda: self._recognize(text),
                summary_func=lambda result: f"识别为{result['intent']}，实体数{sum(len(v) for v in result['entities'].values())}",
                record_source_ids=False,
            )
            response["intent"] = recognition["intent"]
            response["entities"] = recognition["entities"]
            response["plan"] = self._plan_for(response["intent"], response["entities"])

            if response["intent"] == "company_comparison":
                self._handle_company_comparison(response)
            elif response["intent"] == "evidence_gap":
                self._handle_evidence_gap(response)
            elif response["intent"] == "regulatory_status":
                self._handle_regulatory_status(response)
            elif response["intent"] in {"trial_status", "evidence_chain"}:
                self._handle_grounded_chain_task(response)
            else:
                self._handle_source_search(response)
        except Exception as exc:
            response["error"] = self._safe_error(exc)
            response["warnings"].append("决策Agent执行失败，未返回内部异常堆栈。")
            if not response["answer"]:
                response["answer"] = "当前决策Agent服务暂时不可用，请检查本地证据文件或稍后重试。"
        response["source_ids"] = self._sorted_source_ids(response["source_ids"])
        response["chain_ids"] = _unique(response["chain_ids"])
        response["limitations"] = self._business_limitations(response["limitations"])
        source_trace = self._source_trace_from_steps(response["steps"])
        response["source_trace"] = {
            source_id: source_trace[source_id]
            for source_id in response["source_ids"]
            if source_id in source_trace
        }
        untraced_source_ids = [
            source_id for source_id in response["source_ids"] if source_id not in source_trace
        ]
        response["execution_metadata"]["untraced_source_ids"] = untraced_source_ids
        response["citations"] = self._citations_for_source_ids(response["source_ids"], response["source_trace"])
        response["featured_citations"] = self._featured_citations(response)
        response["latency_ms"] = self._elapsed_ms(started)
        response["execution_metadata"]["latency_ms"] = response["latency_ms"]
        return response

    def data_version(self) -> str:
        return self.grounded_qa_service.data_version()

    def _base_response(self, question: str, generation_mode: str) -> dict[str, Any]:
        return {
            "question": question,
            "intent": "",
            "entities": {
                "companies": [],
                "drugs": [],
                "studies": [],
                "trial_ids": [],
                "source_ids": [],
            },
            "plan": [],
            "steps": [],
            "decision": self._empty_decision(),
            "answer": "",
            "citations": [],
            "featured_citations": [],
            "source_ids": [],
            "source_trace": {},
            "chain_ids": [],
            "limitations": [],
            "warnings": [],
            "refused": False,
            "safety_category": "",
            "generation_mode": generation_mode,
            "used_llm": False,
            "execution_metadata": {
                "generation_mode_requested": generation_mode,
                "generation_mode_used": "local",
                "used_llm": False,
                "llm_attempted": False,
                "fallback_used": False,
                "fallback_reason": "",
                "model_name": "local-deterministic-agent",
                "data_version": self.data_version(),
                "untraced_source_ids": [],
                "latency_ms": 0.0,
            },
            "data_version": self.data_version(),
            "latency_ms": 0.0,
            "error": "",
        }

    @staticmethod
    def _empty_decision() -> dict[str, Any]:
        return {
            "summary": "",
            "key_findings": [],
            "comparison_dimensions": [],
            "risk_flags": [],
            "evidence_gaps": [],
            "next_evidence_actions": [],
            "supported_conclusions": [],
            "unsupported_conclusions": [],
            "evidence_maturity": [],
            "scope_statement": SCOPE_STATEMENT,
        }

    def _refusal_payload(self, question: str, safety: dict[str, Any]) -> dict[str, Any]:
        category = str(safety.get("safety_category") or "")
        label = self.grounded_qa_service.safety_category_label(category)
        answer = (
            f"该问题涉及{label}，本决策Agent不能提供此类建议。"
            "可改为查询已核验研发证据、证据链、监管状态或企业样本差异。"
        )
        decision = self._empty_decision()
        decision.update(
            {
                "summary": answer,
                "risk_flags": [f"安全拒答：{label}。"],
                "next_evidence_actions": ["改写为研发证据查询问题，不包含个体治疗、用药、投资或疗效保证请求。"],
                "scope_statement": "本安全边界仅说明当前研发证据Agent不能处理个体医疗、疗效保证、投资建议或企业实力排名请求。",
            }
        )
        return {
            "intent": "prohibited_or_unsupported",
            "answer": answer,
            "decision": decision,
            "limitations": ["该类请求超出当前研发证据查询范围，不能由当前证据样本支持。"],
            "refused": True,
            "safety_category": category,
        }

    def _recognize(self, question: str) -> dict[str, Any]:
        entities = self._extract_entities(question)
        intent = self.grounded_qa_service.classify_question(question)
        if (
            entities["companies"]
            and not entities["source_ids"]
            and self._has_company_comparison_intent(question)
            and intent not in {"prohibited_or_unsupported", "regulatory_status", "evidence_gap"}
        ):
            intent = "company_comparison"
        return {"intent": intent, "entities": entities}

    @staticmethod
    def _has_company_comparison_intent(question: str) -> bool:
        return any(_contains_term(question, term) for term in COMPANY_COMPARISON_TERMS)

    def _extract_entities(self, question: str) -> dict[str, list[str]]:
        return {
            "companies": self._extract_companies(question),
            "drugs": self._extract_drugs(question),
            "studies": self._extract_studies(question),
            "trial_ids": _unique([item.upper() for item in NCT_RE.findall(question or "")]),
            "source_ids": _unique([item.upper() for item in SOURCE_ID_RE.findall(question or "")]),
        }

    def _extract_companies(self, question: str) -> list[str]:
        matches = []
        for subject in self.company_comparison_service.available_companies():
            company_name = str(subject.get("company_name") or "")
            aliases = _unique(
                [
                    company_name,
                    str(subject.get("display_name") or ""),
                    *[str(alias) for alias in subject.get("aliases") or []],
                ]
            )
            positions = [
                position
                for position in (_term_match_start(question, alias) for alias in aliases)
                if position is not None
            ]
            if positions:
                matches.append((min(positions), company_name))
        return _unique([company for _, company in sorted(matches)])

    def _extract_studies(self, question: str) -> list[str]:
        studies = []
        for chain in self.evidence_chain_service.list_chains():
            studies.extend(str(study) for study in chain.get("study_names") or [])
        matches = []
        for study in _unique(studies):
            position = _term_match_start(question, study)
            if position is not None:
                matches.append((position, study))
        return _unique([study for _, study in sorted(matches)])

    def _extract_drugs(self, question: str) -> list[str]:
        groups: dict[str, list[str]] = {}
        for aliases in self.source_registry_service.load_aliases().values():
            if aliases:
                groups.setdefault(str(aliases[0]), [])
                groups[str(aliases[0])].extend(str(alias) for alias in aliases)
        for canonical, aliases in EXTRA_DRUG_ALIASES.items():
            groups.setdefault(canonical, [])
            groups[canonical].extend(aliases)
        matches = []
        for canonical, aliases in groups.items():
            positions = [
                position
                for position in (_term_match_start(question, alias) for alias in _unique(aliases))
                if position is not None
            ]
            if positions:
                matches.append((min(positions), canonical))
        return _unique([drug for _, drug in sorted(matches)])

    def _plan_for(self, intent: str, entities: dict[str, list[str]]) -> list[dict[str, Any]]:
        plan = [
            {
                "step_id": "P1",
                "name": "安全检查",
                "tool": "GroundedQAService.check_safety",
                "reason": "先拦截医疗个体建议等不支持问题",
                "input_summary": "用户问题",
            }
        ]
        if intent == "prohibited_or_unsupported":
            return plan
        plan.append(
            {
                "step_id": "P2",
                "name": "识别任务与实体",
                "tool": "GroundedQAService.classify_question + RDDecisionAgentService.extract_entities",
                "reason": "生成任务特定工具计划",
                "input_summary": self._entity_summary(entities),
            }
        )
        mapping = {
            "company_comparison": [
                ("比较企业证据", "CompanyEvidenceComparisonService.compare", "比较两家企业当前证据样本"),
                ("读取企业画像", "CompanyEvidenceProfileService.build_profile", "补充来源类型、链数量和待确认关系"),
            ],
            "evidence_gap": [
                ("定位证据链", "EvidenceChainService.get_trial_chain/list_chains", "按研究名或试验编号定位证据链"),
                ("核验来源", "SourceRegistryService.get_by_source_id", "核验主证据与关联监管背景来源"),
            ],
            "regulatory_status": [
                ("生成监管辨析", "GroundedQAService.answer_question", "复用监管状态本地循证回答"),
                ("读取监管链", "EvidenceChainService.get_drug_regulatory_chain/get_chain", "区分CHMP意见与EPAR当前产品信息"),
            ],
            "trial_status": [
                ("生成试验状态回答", "GroundedQAService.answer_question", "读取结构化试验状态"),
                ("定位试验证据链", "EvidenceChainService.get_trial_chain/list_chains", "补充链路和来源边界"),
            ],
            "evidence_chain": [
                ("生成证据链回答", "GroundedQAService.answer_question", "读取本地证据链摘要"),
                ("定位证据链", "EvidenceChainService.get_trial_chain/list_chains", "补充链路结构"),
            ],
            "source_search": [
                ("检索已核验来源", "GroundedQAService.answer_question", "复用本地来源检索与引用校验"),
            ],
        }
        for index, (name, tool, reason) in enumerate(mapping.get(intent, mapping["source_search"]), start=3):
            plan.append(
                {
                    "step_id": f"P{index}",
                    "name": name,
                    "tool": tool,
                    "reason": reason,
                    "input_summary": self._entity_summary(entities),
                }
            )
        return plan

    def _handle_company_comparison(self, response: dict[str, Any]) -> None:
        companies = response["entities"]["companies"]
        if len(companies) < 2:
            self._insufficient(response, "当前数据不足：未能识别出两个可比较企业。")
            return
        company_a, company_b = companies[:2]
        comparison = self._run_step(
            response,
            name="比较企业证据",
            tool="CompanyEvidenceComparisonService.compare",
            reason=f"问题要求比较{company_a}与{company_b}当前证据样本",
            input_summary=f"{company_a} vs {company_b}",
            func=lambda: self.company_comparison_service.compare(company_a, company_b),
            summary_func=lambda result: "完成两家企业当前样本结构比较",
        )
        profiles = []
        for company in [company_a, company_b]:
            profile = self._run_step(
                response,
                name=f"读取企业画像：{company}",
                tool="CompanyEvidenceProfileService.build_profile",
                reason="补充来源类型、试验链、监管链和待确认关系",
                input_summary=company,
                func=lambda company=company: self.company_profile_service.build_profile(company),
                summary_func=lambda result: f"来源{result.get('summary', {}).get('source_count', 0)}条",
                optional=True,
            )
            if profile:
                profiles.append(profile)

        source_ids = self._source_ids_from_comparison(comparison)
        chain_ids = self._chain_ids_from_comparison(comparison)
        response["source_ids"].extend(source_ids)
        response["chain_ids"].extend(chain_ids)
        response["limitations"].extend(_unique([COMPANY_SCOPE_WARNING, *comparison.get("comparison_notes", [])]))
        response["decision"] = self._company_decision(comparison, profiles)
        response["answer"] = self._answer_from_decision(response["decision"])

    def _handle_evidence_gap(self, response: dict[str, Any]) -> None:
        chains = self._run_step(
            response,
            name="定位证据链",
            tool="EvidenceChainService.get_trial_chain/list_chains",
            reason="证据缺口问题需要先确定研究或试验链",
            input_summary=self._entity_summary(response["entities"]),
            func=lambda: self._matching_chains(response["entities"]),
            summary_func=lambda result: f"找到{len(result)}条证据链",
        )
        if not chains:
            self._insufficient(response, "当前数据不足：未在当前已核验证据链中定位到该研究或试验。")
            response["decision"]["next_evidence_actions"] = ["补充明确研究名称、NCT编号或已核验来源编号后重新查询。"]
            return
        source_ids = []
        for chain in chains:
            source_ids.extend(item.get("source_id", "") for item in chain.get("evidence_items") or [])
            source_ids.extend(item.get("source_id", "") for item in chain.get("related_regulatory_items") or [])
            if chain.get("chain_id"):
                response["chain_ids"].append(str(chain["chain_id"]))
        verified_sources = self._run_step(
            response,
            name="核验来源",
            tool="SourceRegistryService.get_by_source_id",
            reason="确认主证据和关联监管背景都来自Source Registry",
            input_summary="、".join(_unique(source_ids)),
            func=lambda: [self.source_registry_service.get_by_source_id(source_id) for source_id in _unique(source_ids)],
            summary_func=lambda result: f"核验{len([item for item in result if item])}条来源",
        )
        response["source_ids"].extend(item["source_id"] for item in verified_sources if item and item.get("source_id"))
        response["decision"] = self._gap_decision(chains)
        response["limitations"].append("本回答仅反映当前收录样本中的证据缺口，关联监管背景不计入试验主证据数量。")
        response["answer"] = self._answer_from_decision(response["decision"])

    def _handle_regulatory_status(self, response: dict[str, Any]) -> None:
        qa_result = self._run_step(
            response,
            name="生成监管辨析",
            tool="GroundedQAService.answer_question",
            reason="监管问题需要复用已校验的本地监管状态回答",
            input_summary=response["question"],
            func=lambda: self.grounded_qa_service.answer_question(response["question"]),
            summary_func=lambda result: f"返回{len(result.get('citations') or [])}条引用",
        )
        trace = qa_result.get("trace") or {}
        response["source_ids"].extend(trace.get("retrieved_source_ids") or [])
        response["chain_ids"].extend(trace.get("retrieved_chain_ids") or [])
        chain = self._run_step(
            response,
            name="读取监管链",
            tool="EvidenceChainService.get_drug_regulatory_chain/get_chain",
            reason="明确CHMP积极意见和EPAR当前产品信息的链路关系",
            input_summary=self._entity_summary(response["entities"]),
            func=lambda: self._regulatory_chain(response["entities"]),
            summary_func=lambda result: result.get("chain_id", "未找到监管链") if result else "未找到监管链",
            optional=True,
        )
        if chain:
            response["chain_ids"].append(str(chain.get("chain_id", "")))
            response["source_ids"].extend(item.get("source_id", "") for item in chain.get("evidence_items") or [])
        response["decision"] = self._regulatory_decision(qa_result, chain)
        response["limitations"].extend(qa_result.get("limitations") or [])
        response["answer"] = self._answer_from_decision(response["decision"])

    def _handle_grounded_chain_task(self, response: dict[str, Any]) -> None:
        qa_result = self._run_step(
            response,
            name="生成循证回答",
            tool="GroundedQAService.answer_question",
            reason="复用本地试验状态或证据链回答",
            input_summary=response["question"],
            func=lambda: self.grounded_qa_service.answer_question(response["question"]),
            summary_func=lambda result: f"返回{len(result.get('citations') or [])}条引用",
        )
        trace = qa_result.get("trace") or {}
        response["source_ids"].extend(trace.get("retrieved_source_ids") or [])
        response["chain_ids"].extend(trace.get("retrieved_chain_ids") or [])
        chains = self._run_step(
            response,
            name="定位证据链",
            tool="EvidenceChainService.get_trial_chain/list_chains",
            reason="补充可展示的链路结构",
            input_summary=self._entity_summary(response["entities"]),
            func=lambda: self._matching_chains(response["entities"]),
            summary_func=lambda result: f"找到{len(result)}条证据链",
            optional=True,
        )
        for chain in chains or []:
            response["chain_ids"].append(str(chain.get("chain_id", "")))
        response["decision"] = self._grounded_decision(qa_result, chains)
        response["limitations"].extend(qa_result.get("limitations") or [])
        response["answer"] = self._answer_from_decision(response["decision"])

    def _handle_source_search(self, response: dict[str, Any]) -> None:
        qa_result = self._run_step(
            response,
            name="检索已核验来源",
            tool="GroundedQAService.answer_question",
            reason="来源查询复用本地检索和引用校验",
            input_summary=response["question"],
            func=lambda: self.grounded_qa_service.answer_question(response["question"]),
            summary_func=lambda result: f"返回{len(result.get('citations') or [])}条引用",
        )
        trace = qa_result.get("trace") or {}
        response["source_ids"].extend(trace.get("retrieved_source_ids") or [])
        response["chain_ids"].extend(trace.get("retrieved_chain_ids") or [])
        response["decision"] = self._grounded_decision(qa_result, [])
        response["limitations"].extend(qa_result.get("limitations") or [])
        response["answer"] = self._answer_from_decision(response["decision"])

    def _company_decision(self, comparison: dict[str, Any], profiles: list[dict[str, Any]]) -> dict[str, Any]:
        decision = self._empty_decision()
        companies = comparison.get("companies") or []
        if len(companies) < 2:
            decision["summary"] = "当前数据不足：无法形成企业证据样本对比。"
            decision["evidence_gaps"].append("未识别到两个可比较企业。")
            return decision
        left, right = companies[:2]
        decision["summary"] = (
            f"当前样本中，{left.get('display_name')}包含来源{left.get('source_count', 0)}条、"
            f"试验链{left.get('trial_chain_count', 0)}条、监管链{left.get('regulatory_chain_count', 0)}条；"
            f"{right.get('display_name')}包含来源{right.get('source_count', 0)}条、"
            f"试验链{right.get('trial_chain_count', 0)}条、监管链{right.get('regulatory_chain_count', 0)}条。"
            "这些差异只反映当前收录样本覆盖，不能判断企业研发实力强弱。"
        )
        decision["key_findings"] = [
            (
                f"{left.get('display_name')}来源类型为{self._format_distribution(left.get('source_type_distribution', {}))}；"
                f"{right.get('display_name')}来源类型为{self._format_distribution(right.get('source_type_distribution', {}))}。"
            ),
            (
                f"最新、历史和独立资料构成：{left.get('display_name')} "
                f"{self._format_version_distribution(left.get('version_distribution', {}))}；"
                f"{right.get('display_name')} "
                f"{self._format_version_distribution(right.get('version_distribution', {}))}。"
            ),
            (
                f"试验链数量：{left.get('display_name')} {left.get('trial_chain_count', 0)}条，"
                f"其中多来源链{left.get('multi_source_trial_chain_count', 0)}条；"
                f"{right.get('display_name')} {right.get('trial_chain_count', 0)}条，"
                f"其中多来源链{right.get('multi_source_trial_chain_count', 0)}条。"
            ),
            (
                f"监管链数量：{left.get('display_name')} {left.get('regulatory_chain_count', 0)}条，"
                f"{right.get('display_name')} {right.get('regulatory_chain_count', 0)}条；药物级监管链不计入临床试验数量。"
            ),
            (
                f"待确认关系：{left.get('display_name')} {left.get('unresolved_link_count', 0)}条，"
                f"{right.get('display_name')} {right.get('unresolved_link_count', 0)}条。"
            ),
        ]
        decision["comparison_dimensions"] = [
            self._comparison_dimension("来源数量", left, right, "source_count", "当前Source Registry来源条数。"),
            self._comparison_distribution_dimension("来源多样性", left, right, "source_type_distribution", "当前样本中登记、论文、公司资料和监管资料等来源类型构成。"),
            self._comparison_dimension("试验链数量", left, right, "trial_chain_count", "已人工确认的试验级证据链数量。"),
            self._comparison_trial_chain_dimension(left, right),
            self._comparison_distribution_dimension("最新/历史/独立资料构成", left, right, "version_distribution", "仅说明当前样本中资料版本关系，不代表研究结论优劣。"),
            self._comparison_dimension("监管链数量", left, right, "regulatory_chain_count", "药物级监管事件链，不能计入临床试验数量。"),
            self._comparison_dimension("待确认关系", left, right, "unresolved_link_count", "当前样本缺少明确一对一关系的资料。"),
            self._comparison_traceability_dimension(left, right),
        ]
        decision["risk_flags"] = [
            "不得用来源数量、链数量或监管链数量推断企业研发实力、疗效优劣、成功率或投资价值。",
            "来源类型差异可能来自当前采集覆盖差异，不代表外部公开证据总量。",
            "待确认关系代表当前样本缺少明确一对一核验依据，不等同于来源错误或企业没有相关进展。",
        ]
        decision["supported_conclusions"] = [
            "可以比较两家公司在当前样本中的来源类型、试验级证据链、监管事件链、资料版本构成和待确认关系。",
            "可以指出哪些来源已经被当前工具步骤返回并可由最终引用追溯。",
            "可以说明当前样本内哪些结论仍需补充项目级字段、试验编号或监管原始文件核验。",
        ]
        decision["unsupported_conclusions"] = [
            "不能据此判断企业研发实力、项目质量、疗效优劣、成功率、上市概率或投资价值。",
            "不能生成当前事实数据中不存在的靶点、机制、临床阶段、治疗线别或适用人群结论。",
            "不能把公司资料、论文数量或监管资料数量解释为外部公开证据总量或披露质量排名。",
        ]
        decision["evidence_maturity"] = [
            self._company_evidence_maturity(left),
            self._company_evidence_maturity(right),
        ]
        for profile in profiles:
            for item in profile.get("unresolved_links", []) or []:
                source_id = str(item.get("source_id") or "")
                desc = str(item.get("description") or "待确认关系")
                decision["evidence_gaps"].append(f"{source_id}：{desc}")
        if not decision["evidence_gaps"]:
            decision["evidence_gaps"].append("当前比较未发现已登记的待确认关系，但仍缺少完整管线、靶点和项目级统一字段。")
        decision["next_evidence_actions"] = [
            "补充或核验项目级project_id、靶点、机制和适应症线别字段。",
            "对待确认来源补充NCT编号、论文PMID、公司披露或监管原始文件的对应关系。",
            "如需时间趋势，再按企业或试验调用时间轴视图；本次比较未为展示而额外调用时间轴。",
        ]
        decision["scope_statement"] = (
            f"本企业比较仅限{left.get('display_name')}与{right.get('display_name')}在当前本地已核验"
            "NSCLC证据样本中的来源、证据链和待确认关系；不代表两家公司完整研发管线或研发实力。"
        )
        return decision

    @staticmethod
    def _comparison_dimension(
        name: str,
        left: dict[str, Any],
        right: dict[str, Any],
        field: str,
        interpretation: str,
    ) -> dict[str, Any]:
        return {
            "dimension": name,
            "values": {
                str(left.get("display_name") or left.get("company_name")): left.get(field, 0),
                str(right.get("display_name") or right.get("company_name")): right.get(field, 0),
            },
            "interpretation": interpretation,
        }

    @staticmethod
    def _comparison_distribution_dimension(
        name: str,
        left: dict[str, Any],
        right: dict[str, Any],
        field: str,
        interpretation: str,
    ) -> dict[str, Any]:
        return {
            "dimension": name,
            "values": {
                str(left.get("display_name") or left.get("company_name")): dict(left.get(field) or {}),
                str(right.get("display_name") or right.get("company_name")): dict(right.get(field) or {}),
            },
            "interpretation": interpretation,
        }

    @staticmethod
    def _comparison_trial_chain_dimension(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
        return {
            "dimension": "试验证据链完整性",
            "values": {
                str(left.get("display_name") or left.get("company_name")): {
                    "trial_chain_count": left.get("trial_chain_count", 0),
                    "multi_source_trial_chain_count": left.get("multi_source_trial_chain_count", 0),
                    "single_source_trial_chain_count": left.get("single_source_trial_chain_count", 0),
                },
                str(right.get("display_name") or right.get("company_name")): {
                    "trial_chain_count": right.get("trial_chain_count", 0),
                    "multi_source_trial_chain_count": right.get("multi_source_trial_chain_count", 0),
                    "single_source_trial_chain_count": right.get("single_source_trial_chain_count", 0),
                },
            },
            "interpretation": "多来源链只表示当前样本中登记、论文或公司资料已建立关联，不代表试验质量或企业实力。",
        }

    @staticmethod
    def _comparison_traceability_dimension(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
        return {
            "dimension": "未确认关系与可追溯性风险",
            "values": {
                str(left.get("display_name") or left.get("company_name")): {
                    "unresolved_link_count": left.get("unresolved_link_count", 0),
                    "unresolved_source_ids": [
                        item.get("source_id", "") for item in left.get("evidence_gaps") or [] if item.get("source_id")
                    ],
                },
                str(right.get("display_name") or right.get("company_name")): {
                    "unresolved_link_count": right.get("unresolved_link_count", 0),
                    "unresolved_source_ids": [
                        item.get("source_id", "") for item in right.get("evidence_gaps") or [] if item.get("source_id")
                    ],
                },
            },
            "interpretation": "待确认来源需要补充一对一关系证据；不能据此推断资料错误或企业表现。",
        }

    def _company_evidence_maturity(self, profile: dict[str, Any]) -> dict[str, Any]:
        return {
            "company": profile.get("display_name") or profile.get("company_name", ""),
            "source_diversity": {
                "source_type_count": len(profile.get("source_type_distribution") or {}),
                "source_type_distribution": dict(profile.get("source_type_distribution") or {}),
            },
            "trial_evidence_chain": {
                "trial_chain_count": profile.get("trial_chain_count", 0),
                "multi_source_trial_chain_count": profile.get("multi_source_trial_chain_count", 0),
                "single_source_trial_chain_count": profile.get("single_source_trial_chain_count", 0),
            },
            "version_composition": dict(profile.get("version_distribution") or {}),
            "regulatory_evidence_coverage": {
                "regulatory_chain_count": profile.get("regulatory_chain_count", 0),
                "regulatory_source_ids": [
                    source_id
                    for chain in profile.get("regulatory_chains") or []
                    for source_id in chain.get("source_ids") or []
                ],
            },
            "traceability_risk": {
                "unresolved_link_count": profile.get("unresolved_link_count", 0),
                "unresolved_source_ids": [
                    item.get("source_id", "") for item in profile.get("evidence_gaps") or [] if item.get("source_id")
                ],
            },
            "interpretation": "仅描述当前样本证据构成，不评价企业实力。",
        }

    def _gap_decision(self, chains: list[dict[str, Any]]) -> dict[str, Any]:
        decision = self._empty_decision()
        chain = chains[0]
        evidence_items = list(chain.get("evidence_items") or [])
        related = list(chain.get("related_regulatory_items") or [])
        roles = _unique([str(item.get("role") or item.get("source_type") or "资料") for item in evidence_items])
        primary_ids = [str(item.get("source_id")) for item in evidence_items if item.get("source_id")]
        related_ids = [str(item.get("source_id")) for item in related if item.get("source_id")]
        gaps = [self._sample_scoped_gap(gap) for gap in chain.get("evidence_gaps") or []]
        if not gaps:
            gaps = ["当前证据链内未记录明确缺口；仍需按研究更新节奏持续核验后续论文、监管资料和企业披露。"]
        decision["summary"] = (
            f"{chain.get('chain_name')}当前主证据包含{len(primary_ids)}条来源（{'、'.join(primary_ids)}），"
            f"覆盖{self._format_list(roles)}。"
            + (f"关联监管背景为{'、'.join(related_ids)}，不计入试验主证据数量。" if related_ids else "")
        )
        decision["key_findings"] = [
            f"主证据来源：{'、'.join(primary_ids)}。",
            f"已覆盖证据类型：{self._format_list(roles)}。",
        ]
        if related_ids:
            decision["key_findings"].append(f"关联监管背景：{'、'.join(related_ids)}，不计入该试验证据数量。")
        decision["risk_flags"] = ["关联监管背景不能误计入试验主证据数量。"]
        decision["evidence_gaps"] = gaps
        decision["next_evidence_actions"] = [
            "核验是否已有最终分析论文、长期随访论文或监管原始文件进入当前样本。",
            "补充公司正式披露、注册登记更新、PubMed论文或监管机构页面的可核验来源编号。",
        ]
        related_part = f"及关联监管背景{'、'.join(related_ids)}" if related_ids else ""
        decision["scope_statement"] = (
            f"本证据缺口分析仅限{chain.get('chain_name')}的当前试验链、主证据"
            f"{'、'.join(primary_ids) or '未命中'}{related_part}；缺口表示当前样本内尚未收录或尚未确认的证据。"
        )
        return decision

    def _regulatory_decision(self, qa_result: dict[str, Any], chain: dict[str, Any] | None) -> dict[str, Any]:
        decision = self._empty_decision()
        answer = str(qa_result.get("answer") or "")
        sources = {
            str(item.get("source_id") or ""): item
            for item in (chain or {}).get("evidence_items", []) or []
            if item.get("source_id")
        }
        if {"B015", "B016"} <= set(sources):
            b015 = sources["B015"]
            b016 = sources["B016"]
            b015_date = str(b015.get("publication_date") or "").strip()
            b015_updated = str(b015.get("source_last_updated") or "").strip()
            b016_date = str(b016.get("publication_date") or "").strip()
            decision["summary"] = (
                f"直接结论：B016是{b016_date} CHMP对Tevimbra II-18上市后变更的积极意见，"
                "不是最终法律授权决定；B015为Tevimbra EPAR页面，反映该药品欧盟集中授权后的公开评估和当前产品信息。"
            )
            decision["key_findings"] = [
                (
                    f"B016：CHMP对上市后变更的积极意见"
                    f"{'，文件日期为' + b016_date if b016_date else ''}，不能等同于最终法律授权决定。"
                ),
                (
                    "B015：EPAR页面反映Tevimbra在欧盟集中授权后的公开评估和当前产品信息"
                    f"{'，初始许可日期为' + b015_date if b015_date else ''}"
                    f"{'，页面更新时间为' + b015_updated if b015_updated else ''}。"
                ),
                "B015描述当前状态，B016保留2025-07-24历史意见；两者属于同一药物级监管事件链但文件性质不同。",
            ]
        else:
            direct = answer.splitlines()[0] if answer else "当前数据不足：未找到可核验监管状态。"
            decision["summary"] = direct
            decision["key_findings"] = [line[2:] for line in answer.splitlines() if line.startswith("- ")][:4]
            if not decision["key_findings"] and answer:
                decision["key_findings"] = [direct]
        if chain:
            ids = [item.get("source_id", "") for item in chain.get("evidence_items") or [] if item.get("source_id")]
            decision["key_findings"].append(f"监管链{chain.get('chain_id')}包含来源{'、'.join(ids)}。")
        if "B016" in answer or (chain and any(item.get("source_id") == "B016" for item in chain.get("evidence_items") or [])):
            decision["risk_flags"].append("B016为CHMP积极意见，不能表述为欧盟委员会最终法律授权决定。")
        if "B015" in answer:
            decision["risk_flags"].append("B015为EPAR页面，反映欧盟集中授权后的公开评估和当前产品信息；需与B016当时意见区分。")
        decision["evidence_gaps"] = ["监管判断仅限当前收录的B015/B016等已核验来源，不替代监管机构实时数据库检索。"]
        decision["next_evidence_actions"] = ["核验当前EPAR页面、CHMP opinion文件和欧盟委员会后续决定文件。"]
        source_ids = [item.get("source_id", "") for item in (chain or {}).get("evidence_items", []) if item.get("source_id")]
        if not source_ids:
            trace = qa_result.get("trace") or {}
            source_ids = list(trace.get("retrieved_source_ids") or [])
        decision["supported_conclusions"] = [
            "可以区分当前监管来源中EPAR页面与CHMP积极意见的文件性质、日期和状态边界。",
            "可以说明B016不能单独作为最终法律授权决定使用。",
        ]
        decision["unsupported_conclusions"] = [
            "不能把CHMP积极意见等同于欧盟委员会最终法律授权决定。",
            "不能把EPAR页面本身称为欧盟委员会批准决定文件。",
            "不能据此提供医疗个体建议、疗效判断或商业投资结论。",
        ]
        decision["scope_statement"] = (
            f"本监管辨析仅基于当前监管来源{'、'.join(self._sorted_source_ids(source_ids)) or '未命中来源'}"
            "和本地事实快照；不替代监管机构实时数据库或后续法律决定文件核验。"
        )
        return decision

    def _grounded_decision(self, qa_result: dict[str, Any], chains: list[dict[str, Any]] | None) -> dict[str, Any]:
        decision = self._empty_decision()
        answer = str(qa_result.get("answer") or "")
        trace = qa_result.get("trace") or {}
        source_count = len(trace.get("retrieved_source_ids") or [])
        first_line = answer.splitlines()[0] if answer else ""
        if first_line == "本地证据摘要：" and source_count:
            decision["summary"] = f"当前已检索到{source_count}条已核验来源。"
        else:
            decision["summary"] = first_line or "当前数据不足：未找到可支持该问题的证据。"
        findings = [line[2:] for line in answer.splitlines() if line.startswith("- ")][:5]
        decision["key_findings"] = findings or ([decision["summary"]] if decision["summary"] else [])
        gaps = []
        for chain in chains or []:
            gaps.extend(self._sample_scoped_gap(gap) for gap in chain.get("evidence_gaps") or [])
        if "当前数据不足" in answer:
            gaps.append("当前Source Registry中未找到可支持该问题的来源。")
        decision["evidence_gaps"] = gaps
        decision["next_evidence_actions"] = ["补充明确的来源编号、研究名称、NCT编号或药物别名后重新检索。"] if gaps else []
        source_ids = trace.get("retrieved_source_ids") or []
        if "当前数据不足" in answer:
            decision["scope_statement"] = (
                "当前系统总体覆盖本地已核验NSCLC样本中的恒瑞医药、百济神州、阿斯利康及已登记来源；"
                "本问题实体未在当前样本中命中。"
            )
        elif chains:
            chain = chains[0]
            decision["scope_statement"] = (
                f"本回答仅限{chain.get('chain_name') or chain.get('chain_id')}当前证据链及来源"
                f"{'、'.join(self._sorted_source_ids(source_ids)) or '未命中来源'}。"
            )
        else:
            decision["scope_statement"] = (
                f"本回答仅限当前问题命中的已核验来源{'、'.join(self._sorted_source_ids(source_ids)) or '未命中来源'}。"
            )
        return decision

    def _insufficient(self, response: dict[str, Any], message: str) -> None:
        decision = self._empty_decision()
        decision["summary"] = message
        decision["evidence_gaps"] = [message]
        decision["next_evidence_actions"] = ["补充明确实体或已核验来源后重新运行决策Agent。"]
        decision["scope_statement"] = self._insufficient_scope_statement(response)
        response["decision"] = decision
        response["answer"] = self._answer_from_decision(decision)
        response["limitations"].append(decision["scope_statement"])

    @staticmethod
    def _insufficient_scope_statement(response: dict[str, Any]) -> str:
        intent = response.get("intent")
        entities = response.get("entities") or {}
        if intent == "company_comparison":
            companies = entities.get("companies") or []
            compared = "、".join(companies) if companies else "未命中企业"
            return f"本企业比较仅限当前问题已识别企业（{compared}）和当前证据样本；当前不足以形成两家企业比较。"
        if intent in {"evidence_gap", "trial_status", "evidence_chain"}:
            labels = [*(entities.get("studies") or []), *(entities.get("trial_ids") or [])]
            return f"本证据问题仅限当前研究或试验实体（{'、'.join(labels) or '未命中实体'}）和当前证据样本。"
        if intent == "regulatory_status":
            source_ids = entities.get("source_ids") or []
            return f"本监管问题仅限当前监管来源编号（{'、'.join(source_ids) or '未命中来源'}）和本地事实快照。"
        return (
            "当前系统总体覆盖本地已核验NSCLC样本中的恒瑞医药、百济神州、阿斯利康及已登记来源；"
            "本问题实体未在当前样本中命中。"
        )

    def _matching_chains(self, entities: dict[str, list[str]]) -> list[dict[str, Any]]:
        chains = []
        for trial_id in entities.get("trial_ids") or []:
            chain = self.evidence_chain_service.get_trial_chain(trial_id)
            if chain:
                chains.append(chain)
        study_keys = {norm(study) for study in entities.get("studies") or []}
        if study_keys:
            for chain in self.evidence_chain_service.list_chains():
                if study_keys & {norm(study) for study in chain.get("study_names") or []}:
                    chains.append(chain)
        source_ids = set(entities.get("source_ids") or [])
        if source_ids:
            for chain in self.evidence_chain_service.list_chains():
                chain_source_ids = {
                    str(item.get("source_id") or "")
                    for item in [
                        *(chain.get("evidence_items") or []),
                        *(chain.get("related_regulatory_items") or []),
                    ]
                }
                if source_ids & chain_source_ids:
                    chains.append(chain)
        return self._dedupe_chains(chains)

    def _regulatory_chain(self, entities: dict[str, list[str]]) -> dict[str, Any]:
        if any(source_id in {"B015", "B016"} for source_id in entities.get("source_ids") or []):
            return self.evidence_chain_service.get_drug_regulatory_chain("Tevimbra")
        for drug in entities.get("drugs") or []:
            chain = self.evidence_chain_service.get_drug_regulatory_chain(drug)
            if chain:
                return chain
        return {}

    def _source_ids_from_comparison(self, comparison: dict[str, Any]) -> list[str]:
        source_ids = []
        for profile in comparison.get("companies") or []:
            source_ids.extend(profile.get("source_ids") or [])
            for chain in profile.get("trial_chains") or []:
                source_ids.extend(chain.get("source_ids") or [])
            for chain in profile.get("regulatory_chains") or []:
                source_ids.extend(chain.get("source_ids") or [])
            for gap in profile.get("evidence_gaps") or []:
                source_ids.append(gap.get("source_id", ""))
        return self._sorted_source_ids(source_ids)

    @staticmethod
    def _chain_ids_from_comparison(comparison: dict[str, Any]) -> list[str]:
        chain_ids = []
        for profile in comparison.get("companies") or []:
            for chain in [*(profile.get("trial_chains") or []), *(profile.get("regulatory_chains") or [])]:
                chain_ids.append(str(chain.get("chain_id") or ""))
        return _unique(chain_ids)

    def _citations_for_source_ids(
        self,
        source_ids: list[str],
        source_trace: dict[str, list[str]] | None = None,
    ) -> list[dict[str, Any]]:
        citations = []
        source_trace = source_trace or {}
        for source_id in self._sorted_source_ids(source_ids):
            row = self.source_registry_service.get_by_source_id(source_id)
            if not row:
                continue
            citations.append(
                {
                    "source_id": row.get("source_id", ""),
                    "produced_by_steps": list(source_trace.get(source_id, [])),
                    "title": row.get("description_zh") or row.get("title_original") or row.get("study_name") or row.get("source_id", ""),
                    "source_type": row.get("source_type", ""),
                    "organization": row.get("company_name", ""),
                    "url": row.get("source_url", ""),
                    "version_status": version_status(row.get("is_latest_evidence", "")),
                }
            )
        return citations

    def _featured_citations(self, response: dict[str, Any]) -> list[dict[str, Any]]:
        citations = list(response.get("citations") or [])
        if not citations:
            return []
        if response.get("intent") != "company_comparison":
            return citations[: min(len(citations), 6)]

        selected: list[dict[str, Any]] = []
        seen: set[str] = set()
        companies = response.get("entities", {}).get("companies") or []
        display_by_company = self._company_display_names(companies)

        for category in FEATURED_SOURCE_TYPE_PRIORITY:
            for company in companies:
                citation = self._first_citation_for_company_category(
                    citations,
                    display_by_company.get(company, company),
                    category,
                    seen,
                )
                if citation:
                    selected.append(citation)
                    seen.add(str(citation.get("source_id") or ""))
                if len(selected) >= 6:
                    return selected

        if len(selected) < 4:
            for citation in citations:
                source_id = str(citation.get("source_id") or "")
                if source_id and source_id not in seen:
                    selected.append(citation)
                    seen.add(source_id)
                if len(selected) >= min(6, len(citations)):
                    break
        return selected[:6]

    def _first_citation_for_company_category(
        self,
        citations: list[dict[str, Any]],
        company_display_name: str,
        category: str,
        seen: set[str],
    ) -> dict[str, Any] | None:
        company_key = self._citation_company_key(company_display_name)
        for citation in citations:
            source_id = str(citation.get("source_id") or "")
            if not source_id or source_id in seen:
                continue
            if self._citation_company_key(str(citation.get("organization") or "")) != company_key:
                continue
            if self._source_type_category(str(citation.get("source_type") or "")) == category:
                return citation
        return None

    def _company_display_names(self, companies: list[str]) -> dict[str, str]:
        names = {}
        for company in companies:
            normalized = self.company_comparison_service.normalize_company(company)
            names[company] = str(normalized.get("display_name") or company) if normalized else company
        return names

    @staticmethod
    def _citation_company_key(value: str) -> str:
        raw = str(value or "")
        if "阿斯利康" in raw or "AstraZeneca" in raw:
            return "阿斯利康"
        if "百济" in raw or "BeOne" in raw or "BeiGene" in raw:
            return "百济神州"
        if "恒瑞" in raw or "Hengrui" in raw:
            return "恒瑞医药"
        return norm(raw)

    @staticmethod
    def _source_type_category(source_type: str) -> str:
        key = norm(source_type)
        if "clinicaltrials" in key:
            return "trial_registry"
        if "pubmed" in key:
            return "publication"
        if "ema" in key or "chmp" in key or "监管" in source_type or "epar" in key:
            return "regulatory"
        if "公司" in source_type or "企业" in source_type or "年报" in source_type:
            return "company"
        return "other"

    @staticmethod
    def _source_trace_from_steps(steps: list[dict[str, Any]]) -> dict[str, list[str]]:
        trace: dict[str, list[str]] = {}
        for step in steps or []:
            if step.get("status") != "completed":
                continue
            step_id = str(step.get("step_id") or "")
            if not step_id:
                continue
            for source_id in step.get("source_ids") or []:
                sid = str(source_id or "").strip().upper()
                if not sid:
                    continue
                trace.setdefault(sid, [])
                if step_id not in trace[sid]:
                    trace[sid].append(step_id)
        return trace

    @staticmethod
    def _business_limitations(limitations: list[str]) -> list[str]:
        filtered = []
        for limitation in limitations or []:
            text = str(limitation or "").strip()
            if not text:
                continue
            if any(term in text for term in MODEL_EXECUTION_LIMITATION_TERMS):
                continue
            filtered.append(text)
        return _unique(filtered)

    def _run_step(
        self,
        response: dict[str, Any],
        *,
        name: str,
        tool: str,
        reason: str,
        input_summary: str,
        func: Callable[[], Any],
        summary_func: Callable[[Any], str],
        optional: bool = False,
        record_source_ids: bool = True,
    ) -> Any:
        started = perf_counter()
        step = {
            "step_id": f"S{len(response['steps']) + 1}",
            "name": name,
            "tool": tool,
            "status": "completed",
            "reason": reason,
            "input_summary": input_summary,
            "result_summary": "",
            "source_ids": [],
            "duration_ms": 0.0,
        }
        try:
            result = func()
            step["result_summary"] = summary_func(result)
            if record_source_ids:
                step["source_ids"] = self._extract_source_ids_from_value(result)
            return result
        except Exception as exc:
            step["status"] = "failed"
            step["result_summary"] = self._safe_error(exc)
            response["warnings"].append(f"{name}失败：{self._safe_error(exc)}")
            if not optional:
                raise
            return None
        finally:
            step["duration_ms"] = self._elapsed_ms(started)
            response["steps"].append(step)

    def _extract_source_ids_from_value(self, value: Any) -> list[str]:
        source_ids: list[str] = []
        if isinstance(value, dict):
            if value.get("source_id"):
                source_ids.append(str(value["source_id"]))
            for item in value.values():
                source_ids.extend(self._extract_source_ids_from_value(item))
        elif isinstance(value, list):
            for item in value:
                source_ids.extend(self._extract_source_ids_from_value(item))
        elif isinstance(value, str) and SOURCE_ID_RE.fullmatch(value.strip()):
            source_ids.append(value.strip().upper())
        return self._sorted_source_ids(source_ids)

    @staticmethod
    def _dedupe_chains(chains: list[dict[str, Any]]) -> list[dict[str, Any]]:
        seen = set()
        out = []
        for chain in chains:
            chain_id = str(chain.get("chain_id") or "")
            if chain_id and chain_id not in seen:
                seen.add(chain_id)
                out.append(chain)
        return out

    @staticmethod
    def _entity_summary(entities: dict[str, list[str]]) -> str:
        parts = []
        for key in ["companies", "studies", "trial_ids", "drugs", "source_ids"]:
            values = entities.get(key) or []
            if values:
                parts.append(f"{key}=" + "、".join(values))
        return "；".join(parts) if parts else "未识别到明确实体"

    @staticmethod
    def _format_distribution(distribution: dict[str, Any]) -> str:
        if not distribution:
            return "未统计"
        return "、".join(f"{key}{value}条" for key, value in sorted(distribution.items()))

    @staticmethod
    def _format_version_distribution(distribution: dict[str, Any]) -> str:
        if not distribution:
            return "未统计"
        labels = {"latest": "最新资料", "historical": "历史资料", "independent": "独立资料"}
        return "、".join(
            f"{labels.get(key, key)}{distribution.get(key, 0)}条"
            for key in ["latest", "historical", "independent"]
            if key in distribution
        )

    @staticmethod
    def _format_list(values: list[str]) -> str:
        return "、".join(values) if values else "未明确"

    @staticmethod
    def _sample_scoped_gap(text: Any) -> str:
        raw = str(text or "").strip()
        if not raw:
            return "当前收录样本中存在待补充证据。"
        if raw.startswith("当前收录样本"):
            return raw
        return f"当前收录样本中{raw}"

    @staticmethod
    def _answer_from_decision(decision: dict[str, Any]) -> str:
        lines = [decision.get("summary", "")]
        if decision.get("key_findings"):
            lines.append("核心发现：")
            lines.extend(f"- {item}" for item in decision["key_findings"])
        if decision.get("risk_flags"):
            lines.append("风险与边界：")
            lines.extend(f"- {item}" for item in decision["risk_flags"])
        if decision.get("evidence_gaps"):
            lines.append("证据缺口：")
            lines.extend(f"- {item}" for item in decision["evidence_gaps"])
        if decision.get("next_evidence_actions"):
            lines.append("下一步核验：")
            lines.extend(f"- {item}" for item in decision["next_evidence_actions"])
        lines.append(decision.get("scope_statement") or SCOPE_STATEMENT)
        return "\n".join(line for line in lines if line)

    @staticmethod
    def _safe_error(exc: Exception) -> str:
        if isinstance(exc, (FileNotFoundError, ValueError)):
            return str(exc)
        return "本地证据服务执行异常。"

    @staticmethod
    def _elapsed_ms(started: float) -> float:
        return round((perf_counter() - started) * 1000, 3)

    @staticmethod
    def _sorted_source_ids(source_ids: list[str]) -> list[str]:
        return sorted(_unique(source_ids), key=_source_sort_key)


def run(question: str, generation_mode: str = "local") -> dict[str, Any]:
    return RDDecisionAgentService().run(question, generation_mode=generation_mode)


def capabilities() -> dict[str, Any]:
    return RDDecisionAgentService().capabilities()
