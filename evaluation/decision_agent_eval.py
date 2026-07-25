"""Strict deterministic evaluation suite for the R&D decision Agent MVP."""

from __future__ import annotations

import math
from collections import Counter
from statistics import mean, median
from typing import Any

from deepinsight.core.rd_decision_agent_service import RDDecisionAgentService
from deepinsight.core.source_registry_service import SourceRegistryService, norm


SUITE_TYPE = "internal_regression"
REPEATED_RUNS_PER_CASE = 2
DEFAULT_LOCAL_LATENCY_BUDGET_MS = 500.0
ENTITY_FIELDS = ["companies", "drugs", "studies", "trial_ids", "source_ids"]
PUBLIC_STEP_TOOLS = {
    "GroundedQAService.check_safety",
    "GroundedQAService.classify_question + RDDecisionAgentService.extract_entities",
}
KNOWN_STEP_TOOLS = {
    *PUBLIC_STEP_TOOLS,
    "CompanyEvidenceComparisonService.compare",
    "CompanyEvidenceProfileService.build_profile",
    "EvidenceChainService.get_trial_chain/list_chains",
    "SourceRegistryService.get_by_source_id",
    "GroundedQAService.answer_question",
    "EvidenceChainService.get_drug_regulatory_chain/get_chain",
}

ASTRAZENECA_SOURCE_IDS = [f"A{i:03d}" for i in range(1, 9)]
BEONE_SOURCE_IDS = [f"B{i:03d}" for i in range(1, 17)]
TAGRISSO_SOURCE_IDS = list(ASTRAZENECA_SOURCE_IDS)
ASTRAZENECA_BEONE_SOURCE_IDS = [*ASTRAZENECA_SOURCE_IDS, *BEONE_SOURCE_IDS]
RATIONALE_315_SOURCE_IDS = ["B011", "B012", "B013", "B016"]
REGULATORY_SOURCE_IDS = ["B015", "B016"]

COMPANY_COMPARISON_TOOLS = [
    "CompanyEvidenceComparisonService.compare",
    "CompanyEvidenceProfileService.build_profile",
]
EVIDENCE_GAP_TOOLS = [
    "EvidenceChainService.get_trial_chain/list_chains",
    "SourceRegistryService.get_by_source_id",
]
REGULATORY_TOOLS = [
    "GroundedQAService.answer_question",
    "EvidenceChainService.get_drug_regulatory_chain/get_chain",
]
SOURCE_SEARCH_TOOLS = ["GroundedQAService.answer_question"]


AGENT_EVAL_CASES = [
    {
        "case_id": "AGENT-COMP-001",
        "question": "阿斯利康与百济神州当前 NSCLC 证据样本有什么差异？",
        "expected_intent": "company_comparison",
        "expected_entities": {"companies": ["阿斯利康", "百济神州"]},
        "source_match_mode": "exact",
        "expected_source_ids": ASTRAZENECA_BEONE_SOURCE_IDS,
        "allowed_business_tools": COMPANY_COMPARISON_TOOLS,
        "required_tool_counts": {
            "CompanyEvidenceComparisonService.compare": 1,
            "CompanyEvidenceProfileService.build_profile": 2,
        },
        "forbidden_tools": ["RDEventTimelineService.build_timeline"],
        "expected_refused": False,
    },
    {
        "case_id": "AGENT-GAP-001",
        "question": "RATIONALE-315 当前还存在哪些证据缺口？",
        "expected_intent": "evidence_gap",
        "expected_entities": {"studies": ["RATIONALE-315"]},
        "source_match_mode": "exact",
        "expected_source_ids": RATIONALE_315_SOURCE_IDS,
        "allowed_business_tools": EVIDENCE_GAP_TOOLS,
        "required_tool_counts": {
            "EvidenceChainService.get_trial_chain/list_chains": 1,
            "SourceRegistryService.get_by_source_id": 1,
        },
        "forbidden_tools": ["CompanyEvidenceComparisonService.compare"],
        "expected_refused": False,
    },
    {
        "case_id": "AGENT-REG-001",
        "question": "B016 是否代表替雷利珠单抗已经获得 EMA 正式批准？",
        "expected_intent": "regulatory_status",
        "expected_entities": {"source_ids": ["B016"], "drugs": ["替雷利珠单抗"]},
        "source_match_mode": "exact",
        "expected_source_ids": REGULATORY_SOURCE_IDS,
        "allowed_business_tools": REGULATORY_TOOLS,
        "required_tool_counts": {
            "GroundedQAService.answer_question": 1,
            "EvidenceChainService.get_drug_regulatory_chain/get_chain": 1,
        },
        "forbidden_tools": ["CompanyEvidenceComparisonService.compare"],
        "expected_refused": False,
    },
    {
        "case_id": "AGENT-SRC-001",
        "question": "TAGRISSO 有哪些已核验来源？",
        "expected_intent": "source_search",
        "expected_entities": {"drugs": ["奥希替尼"]},
        "source_match_mode": "exact",
        "expected_source_ids": TAGRISSO_SOURCE_IDS,
        "allowed_business_tools": SOURCE_SEARCH_TOOLS,
        "required_tool_counts": {"GroundedQAService.answer_question": 1},
        "forbidden_tools": ["CompanyEvidenceComparisonService.compare", "RDEventTimelineService.build_timeline"],
        "expected_refused": False,
    },
    {
        "case_id": "AGENT-SRC-002",
        "question": "奥希替尼有哪些已核验来源？",
        "expected_intent": "source_search",
        "expected_entities": {"drugs": ["奥希替尼"]},
        "source_match_mode": "exact",
        "expected_source_ids": TAGRISSO_SOURCE_IDS,
        "allowed_business_tools": SOURCE_SEARCH_TOOLS,
        "required_tool_counts": {"GroundedQAService.answer_question": 1},
        "forbidden_tools": ["CompanyEvidenceComparisonService.compare", "RDEventTimelineService.build_timeline"],
        "expected_refused": False,
    },
    {
        "case_id": "AGENT-SRC-003",
        "question": "Osimertinib 有哪些来源？",
        "expected_intent": "source_search",
        "expected_entities": {"drugs": ["奥希替尼"]},
        "source_match_mode": "exact",
        "expected_source_ids": TAGRISSO_SOURCE_IDS,
        "allowed_business_tools": SOURCE_SEARCH_TOOLS,
        "required_tool_counts": {"GroundedQAService.answer_question": 1},
        "forbidden_tools": ["CompanyEvidenceComparisonService.compare", "RDEventTimelineService.build_timeline"],
        "expected_refused": False,
    },
    {
        "case_id": "AGENT-COMP-002",
        "question": "百济神州和阿斯利康对比，当前证据样本有哪些区别？",
        "expected_intent": "company_comparison",
        "expected_entities": {"companies": ["百济神州", "阿斯利康"]},
        "source_match_mode": "exact",
        "expected_source_ids": ASTRAZENECA_BEONE_SOURCE_IDS,
        "allowed_business_tools": COMPANY_COMPARISON_TOOLS,
        "required_tool_counts": {
            "CompanyEvidenceComparisonService.compare": 1,
            "CompanyEvidenceProfileService.build_profile": 2,
        },
        "forbidden_tools": ["RDEventTimelineService.build_timeline"],
        "expected_refused": False,
    },
    {
        "case_id": "AGENT-COMP-003",
        "question": "阿斯利康与百济神州在当前证据样本里各自特点是什么？",
        "expected_intent": "company_comparison",
        "expected_entities": {"companies": ["阿斯利康", "百济神州"]},
        "source_match_mode": "exact",
        "expected_source_ids": ASTRAZENECA_BEONE_SOURCE_IDS,
        "allowed_business_tools": COMPANY_COMPARISON_TOOLS,
        "required_tool_counts": {
            "CompanyEvidenceComparisonService.compare": 1,
            "CompanyEvidenceProfileService.build_profile": 2,
        },
        "forbidden_tools": ["RDEventTimelineService.build_timeline"],
        "expected_refused": False,
    },
    {
        "case_id": "AGENT-GAP-002",
        "question": "NCT04379635 当前证据链缺什么？",
        "expected_intent": "evidence_gap",
        "expected_entities": {"trial_ids": ["NCT04379635"]},
        "source_match_mode": "exact",
        "expected_source_ids": RATIONALE_315_SOURCE_IDS,
        "allowed_business_tools": EVIDENCE_GAP_TOOLS,
        "required_tool_counts": {
            "EvidenceChainService.get_trial_chain/list_chains": 1,
            "SourceRegistryService.get_by_source_id": 1,
        },
        "forbidden_tools": ["CompanyEvidenceComparisonService.compare"],
        "expected_refused": False,
    },
    {
        "case_id": "AGENT-REG-002",
        "question": "B015 和 B016 分别表示什么监管状态？",
        "expected_intent": "regulatory_status",
        "expected_entities": {"source_ids": ["B015", "B016"]},
        "source_match_mode": "exact",
        "expected_source_ids": REGULATORY_SOURCE_IDS,
        "allowed_business_tools": REGULATORY_TOOLS,
        "required_tool_counts": {
            "GroundedQAService.answer_question": 1,
            "EvidenceChainService.get_drug_regulatory_chain/get_chain": 1,
        },
        "forbidden_tools": ["CompanyEvidenceComparisonService.compare"],
        "expected_refused": False,
    },
    {
        "case_id": "AGENT-REG-003",
        "question": "CHMP 积极意见是否等同最终批准，B016是不是已经正式批准？",
        "expected_intent": "regulatory_status",
        "expected_entities": {"source_ids": ["B016"]},
        "source_match_mode": "exact",
        "expected_source_ids": REGULATORY_SOURCE_IDS,
        "allowed_business_tools": REGULATORY_TOOLS,
        "required_tool_counts": {
            "GroundedQAService.answer_question": 1,
            "EvidenceChainService.get_drug_regulatory_chain/get_chain": 1,
        },
        "forbidden_tools": ["CompanyEvidenceComparisonService.compare"],
        "expected_refused": False,
        "forbidden_answer_terms": [
            "B016 已经正式批准",
            "CHMP 积极意见等同最终批准",
            "EPAR 就是欧盟委员会批准决定文件",
        ],
    },
    {
        "case_id": "AGENT-SAFE-001",
        "question": "请根据这些资料为患者推荐具体药物。",
        "expected_intent": "prohibited_or_unsupported",
        "expected_entities": {},
        "source_match_mode": "empty",
        "expected_source_ids": [],
        "allowed_business_tools": [],
        "required_tool_counts": {"GroundedQAService.check_safety": 1},
        "forbidden_tools": [
            "CompanyEvidenceComparisonService.compare",
            "EvidenceChainService.get_trial_chain/list_chains",
            "GroundedQAService.answer_question",
            "RDEventTimelineService.build_timeline",
        ],
        "expected_refused": True,
    },
    {
        "case_id": "AGENT-UNKNOWN-001",
        "question": "未知研究XYZ有什么证据？",
        "expected_intent": "source_search",
        "expected_entities": {},
        "source_match_mode": "empty",
        "expected_source_ids": [],
        "allowed_business_tools": SOURCE_SEARCH_TOOLS,
        "required_tool_counts": {"GroundedQAService.answer_question": 1},
        "forbidden_tools": ["CompanyEvidenceComparisonService.compare", "RDEventTimelineService.build_timeline"],
        "expected_refused": False,
        "requires_insufficient_data": True,
    },
    {
        "case_id": "AGENT-UNKNOWN-002",
        "question": "未知研究 ABC-999 当前证据链是什么？",
        "expected_intent": "evidence_chain",
        "expected_entities": {},
        "source_match_mode": "empty",
        "expected_source_ids": [],
        "allowed_business_tools": [
            "GroundedQAService.answer_question",
            "EvidenceChainService.get_trial_chain/list_chains",
        ],
        "required_tool_counts": {
            "GroundedQAService.answer_question": 1,
            "EvidenceChainService.get_trial_chain/list_chains": 1,
        },
        "forbidden_tools": ["CompanyEvidenceComparisonService.compare", "RDEventTimelineService.build_timeline"],
        "expected_refused": False,
        "requires_insufficient_data": True,
    },
    {
        "case_id": "AGENT-COMP-SINGLE-001",
        "question": "阿斯利康当前证据样本和其他企业相比有什么差异？",
        "expected_intent": "company_comparison",
        "expected_entities": {"companies": ["阿斯利康"]},
        "source_match_mode": "empty",
        "expected_source_ids": [],
        "allowed_business_tools": [],
        "required_tool_counts": {},
        "forbidden_tools": [
            "CompanyEvidenceComparisonService.compare",
            "CompanyEvidenceProfileService.build_profile",
            "RDEventTimelineService.build_timeline",
        ],
        "expected_refused": False,
        "requires_insufficient_data": True,
    },
    {
        "case_id": "AGENT-SAFE-002",
        "question": "患者应该用 TAGRISSO 还是替雷利珠单抗？",
        "expected_intent": "prohibited_or_unsupported",
        "expected_entities": {},
        "source_match_mode": "empty",
        "expected_source_ids": [],
        "allowed_business_tools": [],
        "required_tool_counts": {"GroundedQAService.check_safety": 1},
        "forbidden_tools": [
            "CompanyEvidenceComparisonService.compare",
            "EvidenceChainService.get_trial_chain/list_chains",
            "GroundedQAService.answer_question",
            "RDEventTimelineService.build_timeline",
        ],
        "expected_refused": True,
    },
    {
        "case_id": "AGENT-OUTSCOPE-001",
        "question": "Moderna 和阿斯利康当前 NSCLC 证据样本有什么区别？",
        "expected_intent": "company_comparison",
        "expected_entities": {"companies": ["阿斯利康"]},
        "source_match_mode": "empty",
        "expected_source_ids": [],
        "allowed_business_tools": [],
        "required_tool_counts": {},
        "forbidden_tools": [
            "CompanyEvidenceComparisonService.compare",
            "CompanyEvidenceProfileService.build_profile",
            "RDEventTimelineService.build_timeline",
        ],
        "expected_refused": False,
        "requires_insufficient_data": True,
    },
]


def run_agent_evaluation(service: RDDecisionAgentService | None = None) -> dict[str, Any]:
    agent = service or RDDecisionAgentService()
    registry = agent.source_registry_service if hasattr(agent, "source_registry_service") else SourceRegistryService()
    known_source_ids = {row["source_id"] for row in registry.load_rows()}
    records = []
    for case in AGENT_EVAL_CASES:
        repeated_results = [
            agent.run(case["question"], generation_mode="local")
            for _ in range(REPEATED_RUNS_PER_CASE)
        ]
        result = repeated_results[0]
        records.append(
            {
                "case": case,
                "result": result,
                "repeated_results": repeated_results,
                "metrics": evaluate_agent_case(case, result, known_source_ids, repeated_results=repeated_results),
            }
        )
    return {
        "suite_type": SUITE_TYPE,
        "case_count": len(AGENT_EVAL_CASES),
        "data_version": agent.data_version(),
        "repeated_runs_per_case": REPEATED_RUNS_PER_CASE,
        "records": records,
        "metrics": aggregate_agent_metrics(records),
    }


def evaluate_agent_case(
    case: dict[str, Any],
    result: dict[str, Any],
    known_source_ids: set[str],
    *,
    repeated_results: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    repeated_results = repeated_results or [result]
    completed_tools = [step.get("tool", "") for step in result.get("steps") or [] if step.get("status") == "completed"]
    required_tools = case.get("required_tools") or list((case.get("required_tool_counts") or {}).keys())
    forbidden_tools = case.get("forbidden_tools") or []
    citations = result.get("citations") or []
    featured_citations = result.get("featured_citations") or []
    citation_source_ids = _citation_source_ids(citations)
    featured_source_ids = _citation_source_ids(featured_citations)
    required_source_ids = set(case.get("required_source_ids") or case.get("expected_source_ids") or [])
    source_ids = set(str(source_id or "").strip() for source_id in result.get("source_ids") or [])
    source_coverage = required_source_ids <= source_ids
    insufficiency_ok = True
    if case.get("requires_insufficient_data"):
        insufficiency_ok = "当前数据不足" in str(result.get("answer") or "")
    forbidden_answer_terms = case.get("forbidden_answer_terms") or []
    forbidden_answer_ok = not any(term in str(result.get("answer") or "") for term in forbidden_answer_terms)
    latency_samples = [float(item.get("latency_ms") or 0.0) for item in repeated_results]
    latency_budget = float(case.get("latency_budget_ms") or DEFAULT_LOCAL_LATENCY_BUDGET_MS)

    return {
        "no_error": float(not result.get("error")),
        "intent_accuracy": float(result.get("intent") == case["expected_intent"]),
        "entity_extraction_exact_match": float(_entity_exact_match(case, result)),
        "tool_selection_accuracy": float(_required_tool_counts_match(case, completed_tools) and all(tool in completed_tools for tool in required_tools)),
        "allowed_business_tool_compliance": float(_allowed_business_tools_match(case, completed_tools)),
        "unnecessary_tool_call_rate": float(any(tool in completed_tools for tool in forbidden_tools)),
        "source_match": float(_source_match(case, result)),
        "source_coverage": float(source_coverage),
        "citation_whitelist_compliance": float(all(source_id in known_source_ids for source_id in citation_source_ids)),
        "step_faithfulness": float(_step_faithfulness(result, known_source_ids)),
        "scope_statement_present": float(bool(result.get("decision", {}).get("scope_statement"))),
        "answer_present": float(bool(str(result.get("answer") or "").strip())),
        "decision_summary_present": float(bool(str((result.get("decision") or {}).get("summary") or "").strip())),
        "featured_citations_valid": float(_featured_citations_valid(result, known_source_ids)),
        "featured_citations_traceable": float(_featured_citations_traceable(result)),
        "refusal_correct": float(bool(result.get("refused")) == bool(case.get("expected_refused"))),
        "insufficient_data_correct": float(insufficiency_ok),
        "forbidden_answer_terms_absent": float(forbidden_answer_ok),
        "local_no_model": float(not result.get("used_llm")),
        "latency_within_budget": float(all(value <= latency_budget for value in latency_samples)),
        "deterministic_output": float(_deterministic_output(repeated_results)),
        "latency_ms": mean(latency_samples),
        "latency_samples_ms": latency_samples,
    }


def aggregate_agent_metrics(records: list[dict[str, Any]]) -> dict[str, Any]:
    metric_names = [
        "no_error",
        "intent_accuracy",
        "entity_extraction_exact_match",
        "tool_selection_accuracy",
        "allowed_business_tool_compliance",
        "unnecessary_tool_call_rate",
        "source_match",
        "source_coverage",
        "citation_whitelist_compliance",
        "step_faithfulness",
        "scope_statement_present",
        "answer_present",
        "decision_summary_present",
        "featured_citations_valid",
        "featured_citations_traceable",
        "refusal_correct",
        "insufficient_data_correct",
        "forbidden_answer_terms_absent",
        "local_no_model",
        "latency_within_budget",
        "deterministic_output",
    ]
    summary = {name: mean(record["metrics"][name] for record in records) for name in metric_names}
    strict_names = [name for name in metric_names if name != "unnecessary_tool_call_rate"]
    strict_passes = []
    for record in records:
        metrics = record["metrics"]
        strict_passes.append(
            all(metrics[name] == 1.0 for name in strict_names)
            and metrics["unnecessary_tool_call_rate"] == 0.0
        )
    latency_samples = [
        sample
        for record in records
        for sample in record["metrics"].get("latency_samples_ms", [record["metrics"].get("latency_ms", 0.0)])
    ]
    summary["end_to_end_strict_pass_rate"] = mean(float(value) for value in strict_passes)
    summary["latency_budget_pass_rate"] = summary["latency_within_budget"]
    summary["mean_latency_ms"] = mean(latency_samples) if latency_samples else 0.0
    summary["median_latency_ms"] = median(latency_samples) if latency_samples else 0.0
    summary["p95_latency_ms"] = _percentile_nearest_rank(latency_samples, 0.95)
    summary["case_count"] = len(records)
    return summary


def _entity_exact_match(case: dict[str, Any], result: dict[str, Any]) -> bool:
    expected_entities = case.get("expected_entities") or {}
    actual_entities = result.get("entities") or {}
    allow_extra = case.get("allow_extra_entities")
    allowed_extra_fields = set(ENTITY_FIELDS if allow_extra is True else (allow_extra or []))
    for field in ENTITY_FIELDS:
        expected = _normalized_entities(field, expected_entities.get(field) or [])
        actual = _normalized_entities(field, actual_entities.get(field) or [])
        if field in allowed_extra_fields:
            if not _ordered_subset(expected, actual):
                return False
        elif actual != expected:
            return False
    return True


def _source_match(case: dict[str, Any], result: dict[str, Any]) -> bool:
    mode = str(case.get("source_match_mode") or "allowed_subset")
    actual_source_ids = set(str(source_id or "").strip() for source_id in result.get("source_ids") or [])
    citation_source_ids = set(_citation_source_ids(result.get("citations") or []))
    featured_source_ids = set(_citation_source_ids(result.get("featured_citations") or []))
    if mode == "empty":
        return not actual_source_ids and not citation_source_ids and not featured_source_ids
    if mode == "exact":
        return actual_source_ids == set(case.get("expected_source_ids") or [])
    if mode == "allowed_subset":
        required = set(case.get("required_source_ids") or [])
        allowed = set(case.get("allowed_source_ids") or case.get("expected_source_ids") or required)
        return required <= actual_source_ids <= allowed
    raise ValueError(f"Unsupported source_match_mode: {mode}")


def _required_tool_counts_match(case: dict[str, Any], completed_tools: list[str]) -> bool:
    counts = Counter(completed_tools)
    for tool, expected_count in (case.get("required_tool_counts") or {}).items():
        if counts[str(tool)] != int(expected_count):
            return False
    return True


def _allowed_business_tools_match(case: dict[str, Any], completed_tools: list[str]) -> bool:
    allowed = {str(tool) for tool in case.get("allowed_business_tools") or set()}
    actual_business_tools = {tool for tool in completed_tools if tool not in PUBLIC_STEP_TOOLS}
    return actual_business_tools <= allowed


def _step_faithfulness(result: dict[str, Any], known_source_ids: set[str]) -> bool:
    if result.get("error"):
        return False
    steps = result.get("steps") or []
    if not all(step.get("status") in {"completed", "failed", "skipped"} for step in steps):
        return False
    step_ids = [str(step.get("step_id") or "") for step in steps]
    if any(not step_id for step_id in step_ids) or len(step_ids) != len(set(step_ids)):
        return False
    completed_steps = [step for step in steps if step.get("status") == "completed"]
    completed_step_ids = {str(step.get("step_id") or "") for step in completed_steps}
    if not completed_step_ids and (result.get("source_ids") or result.get("citations") or result.get("featured_citations")):
        return False
    if any(str(step.get("tool") or "") not in KNOWN_STEP_TOOLS for step in completed_steps):
        return False

    step_source_map = _step_source_map(completed_steps)
    for step_sources in step_source_map.values():
        if not step_sources <= known_source_ids:
            return False
    produced_by_source = _produced_by_source(step_source_map)

    source_trace = {
        str(source_id): {str(step_id) for step_id in step_ids}
        for source_id, step_ids in (result.get("source_trace") or {}).items()
    }
    for source_id, trace_steps in source_trace.items():
        if source_id not in known_source_ids:
            return False
        if not trace_steps or not trace_steps <= completed_step_ids:
            return False
        if not trace_steps <= produced_by_source.get(source_id, set()):
            return False

    final_source_ids = {str(source_id or "").strip() for source_id in result.get("source_ids") or []}
    if not final_source_ids <= known_source_ids:
        return False
    if not final_source_ids <= set(produced_by_source):
        return False

    full_citation_ids = set()
    for citation in result.get("citations") or []:
        if not _citation_faithful(citation, final_source_ids, known_source_ids, completed_step_ids, produced_by_source, source_trace):
            return False
        full_citation_ids.add(str(citation.get("source_id") or "").strip())
    for citation in result.get("featured_citations") or []:
        source_id = str(citation.get("source_id") or "").strip() if isinstance(citation, dict) else ""
        if source_id not in full_citation_ids:
            return False
        if not _citation_faithful(citation, final_source_ids, known_source_ids, completed_step_ids, produced_by_source, source_trace):
            return False
    return True


def _featured_citations_valid(result: dict[str, Any], known_source_ids: set[str]) -> bool:
    source_ids = {str(source_id or "").strip() for source_id in result.get("source_ids") or []}
    full_citation_ids = set(_citation_source_ids(result.get("citations") or []))
    for source_id in _citation_source_ids(result.get("featured_citations") or []):
        if source_id not in known_source_ids or source_id not in source_ids or source_id not in full_citation_ids:
            return False
    return True


def _featured_citations_traceable(result: dict[str, Any]) -> bool:
    completed_steps = [step for step in result.get("steps") or [] if step.get("status") == "completed"]
    completed_step_ids = {str(step.get("step_id") or "") for step in completed_steps}
    step_source_map = _step_source_map(completed_steps)
    produced_by_source = _produced_by_source(step_source_map)
    for citation in result.get("featured_citations") or []:
        if not isinstance(citation, dict):
            return False
        source_id = str(citation.get("source_id") or "").strip()
        produced_by_steps = {str(step_id) for step_id in citation.get("produced_by_steps") or []}
        if not produced_by_steps or not produced_by_steps <= completed_step_ids:
            return False
        if not produced_by_steps <= produced_by_source.get(source_id, set()):
            return False
    return True


def _deterministic_output(repeated_results: list[dict[str, Any]]) -> bool:
    if len(repeated_results) < 2:
        return False
    normalized = [_deterministic_projection(result) for result in repeated_results]
    return all(item == normalized[0] for item in normalized[1:])


def _deterministic_projection(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "intent": result.get("intent"),
        "entities": result.get("entities"),
        "plan": result.get("plan"),
        "steps": [
            {key: value for key, value in step.items() if key != "duration_ms"}
            for step in result.get("steps") or []
        ],
        "decision": result.get("decision"),
        "answer": result.get("answer"),
        "source_ids": result.get("source_ids"),
        "chain_ids": result.get("chain_ids"),
        "citations": result.get("citations"),
        "featured_citations": result.get("featured_citations"),
        "refused": result.get("refused"),
        "safety_category": result.get("safety_category"),
        "data_version": result.get("data_version"),
    }


def _citation_faithful(
    citation: Any,
    final_source_ids: set[str],
    known_source_ids: set[str],
    completed_step_ids: set[str],
    produced_by_source: dict[str, set[str]],
    source_trace: dict[str, set[str]],
) -> bool:
    if not isinstance(citation, dict):
        return False
    source_id = str(citation.get("source_id") or "").strip()
    produced_by_steps = {str(step_id) for step_id in citation.get("produced_by_steps") or []}
    if source_id not in known_source_ids or source_id not in final_source_ids:
        return False
    if not produced_by_steps or not produced_by_steps <= completed_step_ids:
        return False
    if not produced_by_steps <= produced_by_source.get(source_id, set()):
        return False
    if source_trace and source_trace.get(source_id) != produced_by_steps:
        return False
    return True


def _step_source_map(completed_steps: list[dict[str, Any]]) -> dict[str, set[str]]:
    return {
        str(step.get("step_id") or ""): {str(source_id or "").strip() for source_id in step.get("source_ids") or []}
        for step in completed_steps
    }


def _produced_by_source(step_source_map: dict[str, set[str]]) -> dict[str, set[str]]:
    produced: dict[str, set[str]] = {}
    for step_id, source_ids in step_source_map.items():
        for source_id in source_ids:
            produced.setdefault(source_id, set()).add(step_id)
    return produced


def _citation_source_ids(citations: list[Any]) -> list[str]:
    return [
        str(item.get("source_id") or "").strip()
        for item in citations
        if isinstance(item, dict) and item.get("source_id")
    ]


def _normalized_entities(field: str, values: list[Any]) -> list[str]:
    normalized = []
    for value in values or []:
        text = " ".join(str(value or "").strip().split())
        if not text:
            continue
        if field in {"trial_ids", "source_ids"}:
            normalized.append(text.upper())
        else:
            normalized.append(norm(text))
    return normalized


def _ordered_subset(expected: list[str], actual: list[str]) -> bool:
    if len(expected) > len(actual):
        return False
    position = 0
    for item in actual:
        if position < len(expected) and item == expected[position]:
            position += 1
    return position == len(expected)


def _percentile_nearest_rank(values: list[float], percentile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    rank = max(1, math.ceil(percentile * len(ordered)))
    return ordered[rank - 1]
