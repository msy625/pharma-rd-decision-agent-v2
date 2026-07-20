import json
from datetime import datetime, timezone
from pathlib import Path

from deepinsight.config import DEMO_CACHE_DIR
from deepinsight.core.agent_tools import run_advanced_analysis
from deepinsight.apps.app_whitebox import WHITEBOX_DEMO_ANSWER, WHITEBOX_DEMO_CHUNKS, WHITEBOX_DEMO_REASONING, WHITEBOX_DEMO_SQL
from deepinsight.core.retriever import answer_query, create_optional_client
from deepinsight.apps.workflow_report import run_workflow

CHAT_PRESETS = [
    {
        "slug": "starter_latest_enterprise_diagnosis",
        "question": "请总结 ST生物 最新年度的经营质量、风险点和关注指标",
        "filters": {"company_name": "ST生物"},
        "top_k": 5,
    },
    {
        "slug": "starter_recent_company_compare",
        "question": "对比 华兰生物 和 乐普医疗 近年的经营表现差异",
        "filters": {},
        "top_k": 5,
    },
    {
        "slug": "starter_regulatory_risk",
        "question": "从监管机构视角梳理一家公司的潜在合规风险",
        "filters": {"company_name": "ST生物"},
        "top_k": 5,
    },
    {
        "slug": "starter_traceable_investment_summary",
        "question": "基于年报与研报，生成一份可追溯的投资分析摘要",
        "filters": {"company_name": "ST生物"},
        "top_k": 6,
    },
    {
        "slug": "enterprise_diagnosis",
        "question": "请总结ST生物2023年的经营质量、风险点和关注指标",
        "filters": {},
        "top_k": 5,
    },
    {
        "slug": "company_compare",
        "question": "对比华兰生物和乐普医疗2023年的经营差异",
        "filters": {},
        "top_k": 5,
    },
    {
        "slug": "macro_linkage",
        "question": "结合2022到2024年医疗卫生机构变化，分析ST生物的经营环境",
        "filters": {},
        "top_k": 5,
    },
]

WORKFLOW_PRESETS = [
    {
        "slug": "workflow_report",
        "topic": "请为 ST生物 生成经营质量与风险诊断报告",
        "filters": {},
        "top_k": 5,
    }
]

ADVANCED_PRESETS = [
    {
        "slug": "advanced_st_bio",
        "question": "请分析该公司的股权结构、司法风险与创新能力",
        "company_name": "ST生物",
    }
]


def ensure_cache_dir():
    DEMO_CACHE_DIR.mkdir(parents=True, exist_ok=True)


def _write_json(path: Path, payload):
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _read_json(path: Path):
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _cache_data_version() -> str:
    versions = []
    data_dir = DEMO_CACHE_DIR.parent / "data"
    for path in [data_dir / "enterprise_analysis.db", data_dir / "chroma" / "chroma.sqlite3"]:
        if path.exists():
            versions.append(f"{path.name}:{int(path.stat().st_mtime)}:{path.stat().st_size}")
    return "|".join(versions) or "unknown"


def _extract_source_types(result) -> list[str]:
    source_types = set()
    if result.get("sql_rows"):
        source_types.add("sql")
    if result.get("macro_rows"):
        source_types.add("macro")
    if result.get("chunks") or result.get("rag_chunks"):
        source_types.add("vector")
    if result.get("tool_results"):
        source_types.add("tool")
    for source in result.get("sources") or []:
        source_type = source.get("type")
        if source_type:
            source_types.add(str(source_type))
    return sorted(source_types)


def _count_sources(result) -> int:
    source_count = len(result.get("sources") or [])
    source_count += len(result.get("chunks") or [])
    source_count += len(result.get("rag_chunks") or [])
    if result.get("sql_rows"):
        source_count += 1
    if result.get("macro_rows"):
        source_count += 1
    if result.get("tool_results"):
        source_count += len(result.get("tool_results") or {})
    return source_count


def build_cache_payload(cache_type, slug, result, **metadata):
    return {
        "schema_version": 2,
        "data_version": _cache_data_version(),
        "generated_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        "source_count": _count_sources(result),
        "source_types": _extract_source_types(result),
        "is_cached": True,
        "type": cache_type,
        "slug": slug,
        **metadata,
        "result": result,
    }


def build_chat_cache():
    client = create_optional_client()
    ensure_cache_dir()
    for item in CHAT_PRESETS:
        result = answer_query(item["question"], filters=item["filters"], top_k=item["top_k"], client=client)
        payload = build_cache_payload("chat", item["slug"], result, question=item["question"], filters=item["filters"], top_k=item["top_k"])
        _write_json(DEMO_CACHE_DIR / f"{item['slug']}.json", payload)


def build_workflow_cache():
    client = create_optional_client()
    ensure_cache_dir()
    for item in WORKFLOW_PRESETS:
        result = run_workflow(item["topic"], filters=item["filters"], top_k=item["top_k"], client=client)
        payload = build_cache_payload("workflow", item["slug"], result, topic=item["topic"], filters=item["filters"], top_k=item["top_k"])
        _write_json(DEMO_CACHE_DIR / f"{item['slug']}.json", payload)


def build_advanced_cache():
    client = create_optional_client()
    ensure_cache_dir()
    for item in ADVANCED_PRESETS:
        result = run_advanced_analysis(item["question"], company_name=item["company_name"], client=client)
        payload = build_cache_payload("advanced", item["slug"], result, question=item["question"], company_name=item["company_name"])
        _write_json(DEMO_CACHE_DIR / f"{item['slug']}.json", payload)


def build_whitebox_cache():
    ensure_cache_dir()
    payload = {
        "type": "whitebox",
        "slug": "whitebox_demo",
        "result": {
            "answer_markdown": WHITEBOX_DEMO_ANSWER,
            "sql": WHITEBOX_DEMO_SQL,
            "chunks": WHITEBOX_DEMO_CHUNKS,
            "reasoning_markdown": WHITEBOX_DEMO_REASONING,
        },
    }
    _write_json(DEMO_CACHE_DIR / "whitebox_demo.json", build_cache_payload("whitebox", "whitebox_demo", payload["result"]))


def build_all_demo_cache():
    build_chat_cache()
    build_workflow_cache()
    build_advanced_cache()
    build_whitebox_cache()


def normalize_text(value):
    return (value or "").strip().replace(" ", "")


def get_chat_cache(question):
    normalized = normalize_text(question)
    for item in CHAT_PRESETS:
        if normalize_text(item["question"]) == normalized:
            payload = _read_json(DEMO_CACHE_DIR / f"{item['slug']}.json")
            return payload["result"] if payload else None
    return None


def get_workflow_cache(topic):
    normalized = normalize_text(topic)
    for item in WORKFLOW_PRESETS:
        if normalize_text(item["topic"]) == normalized:
            payload = _read_json(DEMO_CACHE_DIR / f"{item['slug']}.json")
            return payload["result"] if payload else None
    return None


def get_advanced_cache(company_name, question):
    normalized_question = normalize_text(question)
    normalized_company = normalize_text(company_name)
    for item in ADVANCED_PRESETS:
        if normalize_text(item["company_name"]) == normalized_company and normalize_text(item["question"]) == normalized_question:
            payload = _read_json(DEMO_CACHE_DIR / f"{item['slug']}.json")
            return payload["result"] if payload else None
    return None


if __name__ == "__main__":
    build_all_demo_cache()
