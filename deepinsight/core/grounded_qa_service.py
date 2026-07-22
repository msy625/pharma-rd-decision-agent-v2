"""Local grounded QA service for verified NSCLC evidence.

This module composes existing CSV/JSON-backed evidence services. It does not
import LLM SDKs, vector stores, or model-loading libraries.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from deepinsight.core.company_evidence_comparison_service import (
    SCOPE_WARNING,
    CompanyEvidenceComparisonService,
)
from deepinsight.core.evidence_chain_service import DEFAULT_CHAIN_CONFIG_PATH, EvidenceChainService
from deepinsight.core.source_registry_service import (
    DEFAULT_CSV_PATH,
    DEFAULT_EVIDENCE_RULES_PATH,
    PROJECT_ROOT,
    SourceRegistryService,
    norm,
)

DEFAULT_GROUNDED_QA_RULES_PATH = PROJECT_ROOT / "config" / "grounded_qa_rules.json"
QUESTION_TYPES = {
    "source_search",
    "trial_status",
    "evidence_chain",
    "regulatory_status",
    "company_comparison",
    "evidence_gap",
    "prohibited_or_unsupported",
}
NCT_RE = re.compile(r"(?<![A-Za-z0-9])NCT\d{8}(?![A-Za-z0-9])", re.IGNORECASE)
SOURCE_ID_RE = re.compile(r"\b[HB]\d{3}\b", re.IGNORECASE)


def _load_rules(path: str | Path | None = None) -> dict[str, Any]:
    rules_path = Path(path) if path else DEFAULT_GROUNDED_QA_RULES_PATH
    return json.loads(rules_path.read_text(encoding="utf-8"))


def _unique_values(values: list[str]) -> list[str]:
    seen = set()
    out = []
    for value in values:
        key = norm(value)
        if value and key not in seen:
            seen.add(key)
            out.append(value)
    return out


def _contains_any(text: str, terms: list[str]) -> bool:
    text_key = norm(text)
    return any(norm(term) in text_key for term in terms if term)


def _version_label(item: dict[str, Any]) -> str:
    status = item.get("version_status")
    if status == "latest":
        return "最新版本"
    if status == "historical":
        return "历史版本"
    raw = norm(item.get("is_latest_evidence"))
    if raw == "true":
        return "最新版本"
    if raw == "false":
        return "历史版本"
    return "独立资料"


def _item_title(item: dict[str, Any]) -> str:
    return (
        item.get("title")
        or item.get("title_original")
        or item.get("description_zh")
        or item.get("study_name")
        or item.get("trial_id")
        or item.get("source_id")
        or ""
    )


class GroundedQAService:
    """Rule-based local QA over verified source registry and evidence chains."""

    def __init__(
        self,
        *,
        source_registry_service: SourceRegistryService | None = None,
        evidence_chain_service: EvidenceChainService | None = None,
        company_comparison_service: CompanyEvidenceComparisonService | None = None,
        rules_path: str | Path | None = None,
    ) -> None:
        self.source_registry_service = source_registry_service or SourceRegistryService()
        self.evidence_chain_service = evidence_chain_service or EvidenceChainService(
            source_registry_service=self.source_registry_service
        )
        self.company_comparison_service = company_comparison_service or CompanyEvidenceComparisonService(
            source_registry_service=self.source_registry_service,
            evidence_chain_service=self.evidence_chain_service,
        )
        self.rules_path = Path(rules_path) if rules_path else DEFAULT_GROUNDED_QA_RULES_PATH
        self._rules: dict[str, Any] | None = None

    @property
    def rules(self) -> dict[str, Any]:
        if self._rules is None:
            self._rules = _load_rules(self.rules_path)
        return self._rules

    def check_safety(self, question: str) -> dict[str, Any]:
        text = str(question or "").strip()
        matches = []
        for category, patterns in (self.rules.get("prohibited_patterns") or {}).items():
            matched = [pattern for pattern in patterns if pattern and pattern in text]
            if matched:
                matches.append({"category": category, "patterns": matched})
        return {
            "allowed": not matches,
            "question_type": "prohibited_or_unsupported" if matches else None,
            "matches": matches,
            "notice": "该问题超出当前循证问答安全边界，不能基于本系统资料回答。",
        }

    def classify_question(self, question: str) -> str:
        text = str(question or "").strip()
        if not text:
            return "prohibited_or_unsupported"
        if not self.check_safety(text)["allowed"]:
            return "prohibited_or_unsupported"

        kws = self.rules.get("classification_keywords") or {}
        source_ids = [sid.upper() for sid in SOURCE_ID_RE.findall(text)]
        nct_ids = [trial_id.upper() for trial_id in NCT_RE.findall(text)]
        has_hengrui = self._mentions_company(text, "hengrui")
        has_beone = self._mentions_company(text, "beone")
        has_rationale = bool(self._extract_study_names(text))

        if nct_ids and _contains_any(text, kws.get("trial_status", [])):
            return "trial_status"
        if has_rationale and _contains_any(text, kws.get("trial_status", [])):
            return "trial_status"
        if "试验" in text and _contains_any(text, kws.get("trial_status", [])):
            return "trial_status"
        if any(source_id in {"B015", "B016"} for source_id in source_ids):
            return "regulatory_status"
        if _contains_any(text, kws.get("regulatory_status", [])):
            return "regulatory_status"
        if has_rationale or _contains_any(text, kws.get("evidence_chain", [])):
            return "evidence_chain"
        if has_hengrui and has_beone and _contains_any(text, kws.get("company_comparison", [])):
            return "company_comparison"
        if _contains_any(text, kws.get("evidence_gap", [])):
            return "evidence_gap"
        return "source_search"

    def retrieve_evidence(self, question: str, question_type: str | None = None) -> dict[str, Any]:
        qtype = question_type or self.classify_question(question)
        if qtype not in QUESTION_TYPES:
            qtype = "source_search"
        if qtype == "prohibited_or_unsupported":
            return self._empty_retrieval(qtype)

        if qtype == "company_comparison":
            comparison = self.company_comparison_service.compare("恒瑞医药", "百济神州")
            sources = self._sources_from_comparison(comparison)
            return {
                "question_type": qtype,
                "sources": sources,
                "chains": [],
                "related_regulatory_items": [],
                "comparison": comparison,
                "evidence_gaps": [],
                "retrieval_service": ["CompanyEvidenceComparisonService", "SourceRegistryService", "EvidenceChainService"],
            }

        if qtype == "evidence_gap":
            gaps = self.evidence_chain_service.get_unresolved_links()
            sources = [item.get("source") for item in gaps if isinstance(item.get("source"), dict)]
            return {
                "question_type": qtype,
                "sources": [source for source in sources if source],
                "chains": [],
                "related_regulatory_items": [],
                "comparison": None,
                "evidence_gaps": gaps,
                "retrieval_service": ["EvidenceChainService", "SourceRegistryService"],
            }

        chains = self._matching_chains(question)
        related_regulatory_items = []
        sources = []
        for chain in chains:
            sources.extend(chain.get("evidence_items") or [])
            related_regulatory_items.extend(chain.get("related_regulatory_items") or [])

        direct_sources = [] if qtype == "evidence_chain" and chains else self._matching_sources(question, qtype)
        sources.extend(direct_sources)

        if qtype == "regulatory_status":
            regulatory_chain = self._regulatory_chain_for_question(question)
            if regulatory_chain:
                chains = self._append_unique_chains(chains, [regulatory_chain])
                sources.extend(regulatory_chain.get("evidence_items") or [])

        return {
            "question_type": qtype,
            "sources": self._dedupe_sources(sources),
            "chains": self._dedupe_chains(chains),
            "related_regulatory_items": self._dedupe_sources(related_regulatory_items),
            "comparison": None,
            "evidence_gaps": self._gaps_from_chains(chains),
            "retrieval_service": self._retrieval_services(qtype),
        }

    def build_evidence_packet(self, question: str, question_type: str | None = None) -> dict[str, Any]:
        qtype = question_type or self.classify_question(question)
        retrieval = self.retrieve_evidence(question, qtype)
        sources = retrieval.get("sources") or []
        related = retrieval.get("related_regulatory_items") or []
        all_sources = self._dedupe_sources([*sources, *related])
        source_ids = [item["source_id"] for item in all_sources if item.get("source_id")]
        chain_ids = [chain["chain_id"] for chain in retrieval.get("chains") or [] if chain.get("chain_id")]
        return {
            "question": question,
            "question_type": qtype,
            "sources": sources,
            "related_regulatory_items": related,
            "all_sources": all_sources,
            "chains": retrieval.get("chains") or [],
            "comparison": retrieval.get("comparison"),
            "evidence_gaps": retrieval.get("evidence_gaps") or [],
            "retrieval_service": retrieval.get("retrieval_service") or [],
            "allowed_source_ids": source_ids,
            "primary_source_ids": [item["source_id"] for item in sources if item.get("source_id")],
            "chain_ids": chain_ids,
            "data_version": self.data_version(),
        }

    def validate_citations(
        self,
        citations: list[dict[str, Any]],
        evidence_packet: dict[str, Any],
    ) -> tuple[list[dict[str, Any]], list[str]]:
        allowed = set(evidence_packet.get("allowed_source_ids") or [])
        seen = set()
        valid = []
        limitations = []
        for citation in citations or []:
            source_id = str(citation.get("source_id") or "").strip()
            if not source_id or source_id in seen:
                if source_id in seen:
                    limitations.append(f"已去除重复引用：{source_id}。")
                continue
            if source_id not in allowed:
                limitations.append(f"已移除不在本次检索证据包中的引用：{source_id}。")
                continue
            row = self.source_registry_service.get_by_source_id(source_id)
            if not row:
                limitations.append(f"已移除登记表不存在的引用：{source_id}。")
                continue
            expected_url = row.get("source_url") or ""
            provided_url = str(citation.get("source_url") or "")
            if provided_url and provided_url != expected_url:
                limitations.append(f"已按登记表校正引用URL：{source_id}。")
            valid.append(
                {
                    "source_id": source_id,
                    "title": _item_title(row),
                    "source_url": expected_url,
                    "source_type": row.get("source_type", ""),
                    "verified_at": row.get("verified_at", ""),
                    "support_summary": citation.get("support_summary") or self._support_summary(row),
                }
            )
            seen.add(source_id)
        return valid, limitations

    def build_local_response(self, question: str, evidence_packet: dict[str, Any]) -> dict[str, Any]:
        qtype = evidence_packet.get("question_type") or "source_search"
        answer, raw_citations, evidence_used, limitations = self._local_answer_parts(question, evidence_packet)
        citations, citation_limitations = self.validate_citations(raw_citations, evidence_packet)
        limitations.extend(citation_limitations)
        if not citations and qtype != "prohibited_or_unsupported":
            answer = "当前数据不足：未在当前已核验资料中找到可支持该问题的证据。"
            evidence_used = []
        return self._response(
            question,
            qtype,
            answer,
            citations,
            evidence_used,
            limitations,
            evidence_packet,
            used_llm=False,
            model_name="local-structured-summary",
        )

    def answer_question(
        self,
        question: str,
        llm_client: Any = None,
        model_name: str | None = None,
        *,
        use_configured_llm: bool = False,
    ) -> dict[str, Any]:
        text = str(question or "").strip()
        if not text:
            packet = self.build_evidence_packet("", "prohibited_or_unsupported")
            return self._response(
                "",
                "prohibited_or_unsupported",
                "请输入需要查询的问题。",
                [],
                [],
                ["空问题未执行检索。"],
                packet,
                used_llm=False,
                model_name=model_name or "",
                safety_notice="空问题未执行检索。",
            )

        safety = self.check_safety(text)
        if not safety["allowed"]:
            packet = self.build_evidence_packet(text, "prohibited_or_unsupported")
            categories = "、".join(item["category"] for item in safety["matches"])
            return self._response(
                text,
                "prohibited_or_unsupported",
                "该问题超出当前循证问答安全边界，不能基于本系统资料回答。",
                [],
                [],
                [f"命中安全边界：{categories}。", "禁止问题不会执行检索，也不会调用语言模型。"],
                packet,
                used_llm=False,
                model_name=model_name or "",
                safety_notice=safety["notice"],
            )

        qtype = self.classify_question(text)
        packet = self.build_evidence_packet(text, qtype)
        if not packet.get("allowed_source_ids"):
            return self.build_local_response(text, packet)
        if llm_client is None and use_configured_llm:
            try:
                from deepinsight.core.grounded_qa_llm import (
                    create_grounded_llm_client,
                    grounded_llm_settings,
                    is_grounded_llm_configured,
                )

                if is_grounded_llm_configured():
                    settings = grounded_llm_settings()
                    model_name = model_name or settings["model"]
                    llm_client = create_grounded_llm_client()
            except Exception as exc:
                return self._local_fallback(text, packet, self._llm_fallback_reason(exc))
        if llm_client is None:
            return self.build_local_response(text, packet)

        try:
            llm_payload = self._call_injected_llm(llm_client, text, packet, model_name)
            citations, citation_limitations = self.validate_citations(llm_payload.get("citations") or [], packet)
            limitations = list(llm_payload.get("limitations") or [])
            limitations.extend(citation_limitations)
            answer = str(llm_payload.get("answer") or "").strip()
            if not answer:
                return self._local_fallback(text, packet, "模型未返回可用答案，已回退本地证据摘要。")
            if not citations:
                return self._local_fallback(text, packet, "模型输出未通过引用校验，已回退本地证据摘要。")
        except Exception as exc:
            return self._local_fallback(text, packet, self._llm_fallback_reason(exc))
        return self._response(
            text,
            qtype,
            answer,
            citations,
            llm_payload.get("evidence_used") or self._evidence_used(packet),
            limitations,
            packet,
            used_llm=True,
            model_name=model_name or "injected-llm-client",
        )

    def data_version(self) -> str:
        digest = hashlib.sha256()
        for path in [
            DEFAULT_CSV_PATH,
            DEFAULT_CHAIN_CONFIG_PATH,
            DEFAULT_EVIDENCE_RULES_PATH,
            self.rules_path,
        ]:
            try:
                path_label = str(path.resolve().relative_to(PROJECT_ROOT))
            except ValueError:
                path_label = path.name
            digest.update(path_label.encode("utf-8"))
            digest.update(b"\0")
            digest.update(path.read_bytes())
            digest.update(b"\0")
        return "sha256:" + digest.hexdigest()[:16]

    def _empty_retrieval(self, qtype: str) -> dict[str, Any]:
        return {
            "question_type": qtype,
            "sources": [],
            "chains": [],
            "related_regulatory_items": [],
            "comparison": None,
            "evidence_gaps": [],
            "retrieval_service": [],
        }

    def _mentions_company(self, question: str, company_key: str) -> bool:
        aliases = ((self.rules.get("confirmed_terms") or {}).get("companies") or {}).get(company_key, [])
        return _contains_any(question, aliases)

    def _extract_study_names(self, question: str) -> list[str]:
        studies = ((self.rules.get("confirmed_terms") or {}).get("studies") or [])
        return [study for study in studies if norm(study) in norm(question)]

    def _extract_source_ids(self, question: str) -> list[str]:
        return _unique_values([item.upper() for item in SOURCE_ID_RE.findall(question or "")])

    def _extract_trial_ids(self, question: str) -> list[str]:
        return _unique_values([item.upper() for item in NCT_RE.findall(question or "")])

    def _extract_drug_terms(self, question: str) -> list[str]:
        out = []
        for aliases in ((self.rules.get("confirmed_terms") or {}).get("drugs") or {}).values():
            if _contains_any(question, aliases):
                out.append(aliases[0])
        return _unique_values(out)

    def _matching_chains(self, question: str) -> list[dict[str, Any]]:
        chains = []
        for trial_id in self._extract_trial_ids(question):
            chain = self.evidence_chain_service.get_trial_chain(trial_id)
            if chain:
                chains.append(chain)
        study_names = self._extract_study_names(question)
        if study_names:
            for chain in self.evidence_chain_service.list_chains():
                chain_studies = [norm(item) for item in chain.get("study_names") or []]
                if any(norm(study) in chain_studies for study in study_names):
                    chains.append(chain)
        for drug in self._extract_drug_terms(question):
            chain = self.evidence_chain_service.get_drug_regulatory_chain(drug)
            if chain:
                chains.append(chain)
        return self._dedupe_chains(chains)

    def _regulatory_chain_for_question(self, question: str) -> dict[str, Any]:
        if _contains_any(question, ["Tevimbra", "替雷利珠单抗", "tislelizumab", "B015", "B016", "EMA", "CHMP"]):
            return self.evidence_chain_service.get_drug_regulatory_chain("Tevimbra")
        return {}

    def _matching_sources(self, question: str, qtype: str) -> list[dict[str, Any]]:
        sources = []
        for source_id in self._extract_source_ids(question):
            row = self.source_registry_service.get_by_source_id(source_id)
            if row:
                sources.append(row)
        for trial_id in self._extract_trial_ids(question):
            sources.extend(self.source_registry_service.query(trial_id=trial_id))
        for study in self._extract_study_names(question):
            sources.extend(self.source_registry_service.query(study_name=study))
        for drug in self._extract_drug_terms(question):
            sources.extend(self.source_registry_service.query(drug=drug))
        if qtype == "source_search" and not sources:
            sources.extend(self.source_registry_service.query(text=question))
        return self._dedupe_sources(sources)

    def _sources_from_comparison(self, comparison: dict[str, Any]) -> list[dict[str, Any]]:
        source_ids = []
        for profile in comparison.get("companies") or []:
            for chain in profile.get("trial_chains") or []:
                source_ids.extend(chain.get("source_ids") or [])
            for chain in profile.get("regulatory_chains") or []:
                source_ids.extend(chain.get("source_ids") or [])
            for gap in profile.get("evidence_gaps") or []:
                if gap.get("source_id"):
                    source_ids.append(gap["source_id"])
        return self._sources_by_ids(source_ids)

    def _sources_by_ids(self, source_ids: list[str]) -> list[dict[str, Any]]:
        rows = []
        for source_id in _unique_values(source_ids):
            row = self.source_registry_service.get_by_source_id(source_id)
            if row:
                rows.append(row)
        return rows

    def _dedupe_sources(self, sources: list[dict[str, Any]]) -> list[dict[str, Any]]:
        seen = set()
        out = []
        for source in sources:
            if not isinstance(source, dict):
                continue
            source_id = source.get("source_id")
            if not source_id or source_id in seen:
                continue
            seen.add(source_id)
            out.append(source)
        return out

    def _dedupe_chains(self, chains: list[dict[str, Any]]) -> list[dict[str, Any]]:
        seen = set()
        out = []
        for chain in chains:
            if not isinstance(chain, dict):
                continue
            chain_id = chain.get("chain_id")
            if not chain_id or chain_id in seen:
                continue
            seen.add(chain_id)
            out.append(chain)
        return out

    def _append_unique_chains(self, left: list[dict[str, Any]], right: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return self._dedupe_chains([*left, *right])

    def _gaps_from_chains(self, chains: list[dict[str, Any]]) -> list[dict[str, Any]]:
        gaps = []
        for chain in chains:
            for gap in chain.get("evidence_gaps") or []:
                gaps.append({"chain_id": chain.get("chain_id", ""), "description": gap})
        return gaps

    def _retrieval_services(self, qtype: str) -> list[str]:
        if qtype in {"evidence_chain", "trial_status", "regulatory_status"}:
            return ["EvidenceChainService", "SourceRegistryService"]
        return ["SourceRegistryService"]

    def _citation_for_source(self, source: dict[str, Any], summary: str | None = None) -> dict[str, Any]:
        return {
            "source_id": source.get("source_id", ""),
            "title": _item_title(source),
            "source_url": source.get("source_url", ""),
            "source_type": source.get("source_type", ""),
            "verified_at": source.get("verified_at", ""),
            "support_summary": summary or self._support_summary(source),
        }

    def _support_summary(self, source: dict[str, Any]) -> str:
        parts = []
        if source.get("study_name"):
            parts.append(str(source["study_name"]))
        if source.get("trial_id"):
            parts.append(str(source["trial_id"]))
        if source.get("study_status"):
            parts.append(f"study_status={source['study_status']}")
        if source.get("authorisation_status"):
            parts.append(str(source["authorisation_status"]))
        if source.get("regulatory_event_type"):
            parts.append(str(source["regulatory_event_type"]))
        return "；".join(parts) or _item_title(source)

    def _local_answer_parts(
        self,
        question: str,
        packet: dict[str, Any],
    ) -> tuple[str, list[dict[str, Any]], list[dict[str, Any]], list[str]]:
        qtype = packet.get("question_type")
        sources = packet.get("sources") or []
        chains = packet.get("chains") or []
        related = packet.get("related_regulatory_items") or []
        limitations = ["未调用大模型，仅展示当前已检索到的结构化证据。"]
        evidence_used = self._evidence_used(packet)
        citations = []

        if qtype == "trial_status":
            if not sources:
                return "当前数据不足：未在当前已核验资料中找到该试验状态。", [], [], limitations
            lines = ["本地证据摘要："]
            for source in sources[:5]:
                status = source.get("study_status") or "未填写"
                lines.append(f"- {source['source_id']} 显示研究状态为 {status}。")
                citations.append(self._citation_for_source(source, f"研究状态：{status}"))
            return "\n".join(lines), citations, evidence_used, limitations

        if qtype == "regulatory_status":
            if not sources:
                return "当前数据不足：未找到可核验的监管资料。", [], [], limitations
            lines = ["本地证据摘要："]
            for source in sources:
                if source.get("source_id") == "B015":
                    summary = "EMA/欧盟正式授权"
                elif source.get("source_id") == "B016":
                    summary = "CHMP积极意见，非最终批准"
                else:
                    summary = source.get("authorisation_status") or source.get("regulatory_event_type") or "监管资料"
                lines.append(f"- {source['source_id']}：{summary}。")
                citations.append(self._citation_for_source(source, summary))
            return "\n".join(lines), citations, evidence_used, limitations

        if qtype == "evidence_chain":
            if not chains:
                return "当前数据不足：未找到可确认的证据链。", [], [], limitations
            lines = ["本地证据摘要："]
            for chain in chains:
                lines.append(f"- {chain.get('chain_name')}：试验证据包含 " + "、".join(item["source_id"] for item in chain.get("evidence_items") or []) + "。")
                for item in chain.get("evidence_items") or []:
                    lines.append(f"  - {item['source_id']}：{item.get('role', '')}，{_version_label(item)}。")
                    citations.append(self._citation_for_source(item))
                if chain.get("related_regulatory_items"):
                    ids = "、".join(item["source_id"] for item in chain["related_regulatory_items"])
                    lines.append(f"  - 关联监管背景：{ids}，不计入该试验证据数量。")
                    for item in chain["related_regulatory_items"]:
                        citations.append(self._citation_for_source(item, "关联监管背景，不计入试验证据数量"))
                for gap in chain.get("evidence_gaps") or []:
                    lines.append(f"  - 证据缺口：{gap}")
            return "\n".join(lines), citations, evidence_used, limitations

        if qtype == "company_comparison":
            comparison = packet.get("comparison") or {}
            profiles = comparison.get("companies") or []
            if len(profiles) < 2:
                return "当前数据不足：无法形成企业证据样本对比。", [], [], limitations
            lines = ["本地证据摘要：", SCOPE_WARNING]
            for profile in profiles:
                lines.append(
                    f"- {profile.get('display_name') or profile.get('company_name')}：来源 {profile.get('source_count', 0)} 条，"
                    f"试验链 {profile.get('trial_chain_count', 0)} 条，监管链 {profile.get('regulatory_chain_count', 0)} 条，"
                    f"待确认关系 {profile.get('unresolved_link_count', 0)} 条。"
                )
            citations = [self._citation_for_source(source) for source in sources[:12]]
            limitations.append(SCOPE_WARNING)
            return "\n".join(lines), citations, evidence_used, limitations

        if qtype == "evidence_gap":
            gaps = packet.get("evidence_gaps") or []
            if not gaps:
                return "当前数据不足：未找到待确认关系或证据缺口记录。", [], [], limitations
            lines = ["本地证据摘要："]
            for gap in gaps:
                source_id = gap.get("source_id", "")
                desc = gap.get("description") or "存在待确认关系。"
                lines.append(f"- {source_id}：{desc}")
            citations = [self._citation_for_source(source, "待确认关系或证据缺口") for source in sources]
            return "\n".join(lines), citations, evidence_used, limitations

        if not sources:
            return "当前数据不足：未在当前已核验资料中找到可支持该问题的证据。", [], [], limitations
        lines = ["本地证据摘要："]
        for source in sources[:10]:
            bits = [source["source_id"], source.get("source_type", "资料")]
            if source.get("study_name"):
                bits.append(source["study_name"])
            if source.get("trial_id"):
                bits.append(source["trial_id"])
            lines.append("- " + " / ".join(bits))
            citations.append(self._citation_for_source(source))
        return "\n".join(lines), citations, evidence_used, limitations

    def _evidence_used(self, packet: dict[str, Any]) -> list[dict[str, Any]]:
        items = []
        for source in packet.get("sources") or []:
            items.append(
                {
                    "kind": "source",
                    "source_id": source.get("source_id", ""),
                    "source_type": source.get("source_type", ""),
                    "study_name": source.get("study_name", ""),
                    "trial_id": source.get("trial_id", ""),
                    "study_status": source.get("study_status", ""),
                    "version_status": source.get("version_status") or _version_label(source),
                }
            )
        for source in packet.get("related_regulatory_items") or []:
            items.append(
                {
                    "kind": "related_regulatory",
                    "source_id": source.get("source_id", ""),
                    "source_type": source.get("source_type", ""),
                    "study_name": source.get("study_name", ""),
                    "trial_id": source.get("trial_id", ""),
                    "version_status": source.get("version_status") or _version_label(source),
                }
            )
        for chain in packet.get("chains") or []:
            items.append(
                {
                    "kind": "chain",
                    "chain_id": chain.get("chain_id", ""),
                    "chain_type": chain.get("chain_type", ""),
                    "source_ids": [item.get("source_id", "") for item in chain.get("evidence_items") or []],
                    "related_regulatory_source_ids": [
                        item.get("source_id", "") for item in chain.get("related_regulatory_items") or []
                    ],
                }
            )
        if packet.get("comparison"):
            items.append(
                {
                    "kind": "company_comparison",
                    "data_scope": packet["comparison"].get("data_scope", ""),
                    "interpretation_scope": packet["comparison"].get("interpretation_scope", ""),
                }
            )
        return items

    def _call_injected_llm(
        self,
        llm_client: Any,
        question: str,
        packet: dict[str, Any],
        model_name: str | None,
    ) -> dict[str, Any]:
        from deepinsight.core.grounded_qa_llm import generate_grounded_answer, parse_grounded_llm_output

        if hasattr(llm_client, "chat"):
            result = generate_grounded_answer(question, packet, client=llm_client)
        elif callable(llm_client):
            result = llm_client(question=question, evidence_packet=packet, model_name=model_name)
        elif hasattr(llm_client, "answer"):
            result = llm_client.answer(question=question, evidence_packet=packet, model_name=model_name)
        else:
            raise TypeError("llm_client must be callable or expose answer().")
        if isinstance(result, dict):
            return result
        return parse_grounded_llm_output(result)

    def _local_fallback(self, question: str, packet: dict[str, Any], reason: str) -> dict[str, Any]:
        response = self.build_local_response(question, packet)
        response["limitations"].append(reason)
        response["trace"]["fallback_used"] = True
        response["trace"]["llm_attempted"] = True
        return response

    @staticmethod
    def _llm_fallback_reason(exc: Exception) -> str:
        text = str(exc or "").lower()
        if "timeout" in text or "timed out" in text:
            return "模型调用超时，已回退本地证据摘要。"
        if "401" in text or "auth" in text or "unauthorized" in text:
            return "模型鉴权失败，已回退本地证据摘要。"
        if "402" in text or "balance" in text or "quota" in text:
            return "模型账户余额或额度不可用，已回退本地证据摘要。"
        if "503" in text or "service unavailable" in text or "unavailable" in text:
            return "模型服务暂时不可用，已回退本地证据摘要。"
        return "模型输出或调用不可用，已回退本地证据摘要。"

    def _response(
        self,
        question: str,
        qtype: str,
        answer: str,
        citations: list[dict[str, Any]],
        evidence_used: list[dict[str, Any]],
        limitations: list[str],
        packet: dict[str, Any],
        *,
        used_llm: bool,
        model_name: str,
        safety_notice: str = "",
    ) -> dict[str, Any]:
        return {
            "question": question,
            "question_type": qtype,
            "answer": answer,
            "citations": citations,
            "evidence_used": evidence_used,
            "limitations": _unique_values([item for item in limitations if item]),
            "safety_notice": safety_notice or "仅基于当前本地已核验证据回答，不提供医疗、疗效、商业或资本市场决策意见。",
            "trace": {
                "retrieval_service": packet.get("retrieval_service") or [],
                "retrieved_source_ids": packet.get("allowed_source_ids") or [],
                "retrieved_chain_ids": packet.get("chain_ids") or [],
                "source_count": len(packet.get("allowed_source_ids") or []),
                "data_version": packet.get("data_version") or self.data_version(),
                "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "model_name": model_name,
                "used_llm": used_llm,
                "cache_hit": False,
                "fallback_used": False,
            },
        }


_DEFAULT_SERVICE: GroundedQAService | None = None


def get_default_service() -> GroundedQAService:
    global _DEFAULT_SERVICE
    if _DEFAULT_SERVICE is None:
        _DEFAULT_SERVICE = GroundedQAService()
    return _DEFAULT_SERVICE


def classify_question(question: str) -> str:
    return get_default_service().classify_question(question)


def check_safety(question: str) -> dict[str, Any]:
    return get_default_service().check_safety(question)


def retrieve_evidence(question: str, question_type: str | None = None) -> dict[str, Any]:
    return get_default_service().retrieve_evidence(question, question_type)


def build_evidence_packet(question: str, question_type: str | None = None) -> dict[str, Any]:
    return get_default_service().build_evidence_packet(question, question_type)


def validate_citations(
    citations: list[dict[str, Any]],
    evidence_packet: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[str]]:
    return get_default_service().validate_citations(citations, evidence_packet)


def build_local_response(question: str, evidence_packet: dict[str, Any]) -> dict[str, Any]:
    return get_default_service().build_local_response(question, evidence_packet)


def answer_question(question: str, llm_client: Any = None, model_name: str | None = None) -> dict[str, Any]:
    return get_default_service().answer_question(question, llm_client=llm_client, model_name=model_name)


def data_version() -> str:
    return get_default_service().data_version()
