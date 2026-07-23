import json
import gc
import sqlite3
import sys
import tempfile
from pathlib import Path

import pytest

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from deepinsight.core.retriever import LocalEmbeddingClient
from deepinsight.dataops.db_expand import create_extended_tables, seed_company_parties
from deepinsight.dataops.db_init import create_tables, seed_indicators


TEST_COMPANY = "ST生物"
TEST_PEER = "同业样本"
TEST_YEAR = 2023
COLLECTION_NAME = "enterprise_documents"


def _insert_financial_fact(conn, document_id, indicator_name, period_label, value_role, value_num, unit=None, source_page=7):
    indicator_id = conn.execute(
        "SELECT indicator_id FROM dict_financial_indicator WHERE indicator_name = ?",
        (indicator_name,),
    ).fetchone()["indicator_id"]
    conn.execute(
        """
        INSERT INTO fact_financial_report (
            document_id, indicator_id, period_label, value_role, unit, value_num, source_page, source_row_label
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (document_id, indicator_id, period_label, value_role, unit, value_num, source_page, f"{indicator_name}-{period_label}-{value_role}"),
    )


def _create_test_sqlite(db_path):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        create_tables(conn)
        seed_indicators(conn)
        create_extended_tables(conn)

        conn.execute(
            "INSERT INTO dim_industry (industry_code, industry_name, industry_level) VALUES (?, ?, ?)",
            ("BIO", "生物制品", 2),
        )
        industry_id = conn.execute("SELECT industry_id FROM dim_industry WHERE industry_name = ?", ("生物制品",)).fetchone()["industry_id"]
        companies = [
            ("688001", TEST_COMPANY, "ST生物"),
            ("688002", TEST_PEER, "同业样本"),
        ]
        for stock_code, company_name, short_name in companies:
            conn.execute(
                """
                INSERT INTO dim_company (stock_code, company_name, company_short_name, exchange, primary_industry_id)
                VALUES (?, ?, ?, ?, ?)
                """,
                (stock_code, company_name, short_name, "SSE", industry_id),
            )
        seed_company_parties(conn)

        document_ids = {}
        for company_name in (TEST_COMPANY, TEST_PEER):
            company_id = conn.execute("SELECT company_id FROM dim_company WHERE company_name = ?", (company_name,)).fetchone()["company_id"]
            cursor = conn.execute(
                """
                INSERT INTO dim_document (
                    company_id, doc_type, report_year, title, file_name, file_path,
                    version_label, is_latest, publish_date, pages_total, parser_type, metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?, ?)
                """,
                (
                    company_id,
                    "annual_report",
                    TEST_YEAR,
                    f"{company_name}2023年度报告",
                    f"{company_name}-2023年度报告.md",
                    f"/tmp/test-fixture/{company_name}-2023年度报告.md",
                    "fixture",
                    "2024-04-30",
                    120,
                    "pytest_fixture",
                    json.dumps({"has_meaningful_text": True, "meaningful_line_count": 10}, ensure_ascii=False),
                ),
            )
            document_ids[company_name] = cursor.lastrowid

        metric_values = {
            TEST_COMPANY: {
                "营业收入": (136_790_924.0, 120_000_000.0, "元"),
                "归属于上市公司股东的净利润": (28_172_625.5, -6_997_109.89, "元"),
                "经营活动产生的现金流量净额": (36_276_713.5, 40_100_000.0, "元"),
                "研发费用": (9_985_226.68, 8_600_000.0, "元"),
                "净资产收益率": (-12.33, -19.65, "%"),
                "总资产": (771_382_516.0, 553_064_727.0, "元"),
            },
            TEST_PEER: {
                "营业收入": (88_000_000.0, 80_000_000.0, "元"),
                "归属于上市公司股东的净利润": (12_000_000.0, 10_000_000.0, "元"),
                "经营活动产生的现金流量净额": (20_000_000.0, 18_000_000.0, "元"),
                "研发费用": (7_000_000.0, 6_500_000.0, "元"),
                "净资产收益率": (6.5, 5.8, "%"),
                "总资产": (410_000_000.0, 390_000_000.0, "元"),
            },
        }
        for company_name, values in metric_values.items():
            document_id = document_ids[company_name]
            for indicator_name, (current, historical, unit) in values.items():
                _insert_financial_fact(conn, document_id, indicator_name, f"{TEST_YEAR}FY", "current", current, unit)
                _insert_financial_fact(conn, document_id, indicator_name, f"{TEST_YEAR - 1}FY", "historical", historical, unit, source_page=8)

        for name, values in {
            "卫生总费用-卫生总费用": [70_000.0, 78_000.0],
            "医疗卫生机构-医院数": [37_000.0, 38_500.0],
            "医疗卫生机构-医疗卫生机构数": [1_030_000.0, 1_070_000.0],
            "医疗卫生机构门诊服务情况-医疗卫生机构诊疗人次": [8_400_000.0, 9_200_000.0],
        }.items():
            cursor = conn.execute(
                """
                INSERT INTO dict_macro_indicator (indicator_code, indicator_name, frequency, default_unit, source_name)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(indicator_code) DO UPDATE SET indicator_name = excluded.indicator_name
                """,
                (f"fixture_{abs(hash(name))}", name, "annual", "亿元", "pytest_fixture"),
            )
            macro_id = cursor.lastrowid or conn.execute(
                "SELECT macro_indicator_id FROM dict_macro_indicator WHERE indicator_name = ?",
                (name,),
            ).fetchone()["macro_indicator_id"]
            for year, value in zip((2022, 2023), values):
                conn.execute(
                    """
                    INSERT INTO fact_macro_data (macro_indicator_id, period_date, region_name, value_num, unit, source_file)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (macro_id, f"{year}-12-31", "全国", value, "亿元", "pytest_fixture.xlsx"),
                )

        company_id = conn.execute("SELECT company_id FROM dim_company WHERE company_name = ?", (TEST_COMPANY,)).fetchone()["company_id"]
        peer_id = conn.execute("SELECT company_id FROM dim_company WHERE company_name = ?", (TEST_PEER,)).fetchone()["company_id"]
        conn.execute(
            """
            INSERT INTO fact_legal_risk (
                company_id, case_no, risk_type, role_in_case, filing_date, amount_involved,
                status, severity_score, detail_text, source_type, batch_tag
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (company_id, "fixture-risk-001", "合同纠纷", "被告", "2025-01-10", 1_200_000.0, "审理中", 82, "测试用临时风险事件。", "pytest", "pytest"),
        )
        for index, patent_type in enumerate(("发明", "实用新型"), start=1):
            conn.execute(
                """
                INSERT INTO fact_ip_patent (
                    company_id, patent_no, patent_name, patent_type, legal_status,
                    application_year, patent_score, source_type, batch_tag
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (company_id, f"fixture-patent-{index}", f"测试专利{index}", patent_type, "有效", 2023 - index + 1, 75 + index, "pytest", "pytest"),
            )
        peer_party_id = conn.execute("SELECT party_id FROM dim_party WHERE company_id = ?", (peer_id,)).fetchone()["party_id"]
        conn.execute(
            """
            INSERT INTO fact_investment_relation (
                investor_party_id, investee_company_id, equity_ratio, control_type,
                effective_date, source_type, batch_tag
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (peer_party_id, company_id, 12.5, "direct", "2023-01-01", "pytest", "pytest"),
        )

        vector_id = f"fixture-{document_ids[TEST_COMPANY]}-0"
        conn.execute(
            """
            INSERT INTO map_vector_chunk (
                vector_id, document_id, chunk_index, page_start, page_end, chunk_hash, chunk_text_preview
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (vector_id, document_ids[TEST_COMPANY], 0, 12, 12, "fixture-hash-0", "经营情况与风险提示"),
        )
        conn.commit()
    finally:
        conn.close()


def _create_test_chroma(chroma_path):
    import chromadb

    client = chromadb.PersistentClient(path=str(chroma_path))
    collection = client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"description": "pytest isolated enterprise documents"},
    )
    documents = [
        "ST生物 主营业务保持稳定，经营情况显示营业收入和现金流改善，但仍需关注市场竞争风险与研发投入节奏。",
        "ST生物 风险提示显示公司需要关注合规事项、渠道竞争和成本波动，管理层讨论强调核心产品放量。",
    ]
    embeddings = LocalEmbeddingClient().embed(documents)
    collection.add(
        ids=["fixture-st-bio-0", "fixture-st-bio-1"],
        documents=documents,
        embeddings=embeddings,
        metadatas=[
            {
                "source": "ST生物-2023年度报告.md",
                "page": 12,
                "doc_type": "annual_report",
                "company_name": TEST_COMPANY,
                "industry_name": "生物制品",
                "report_year": TEST_YEAR,
                "document_id": 1,
                "chunk_index": 0,
            },
            {
                "source": "ST生物-2023年度报告.md",
                "page": 35,
                "doc_type": "annual_report",
                "company_name": TEST_COMPANY,
                "industry_name": "生物制品",
                "report_year": TEST_YEAR,
                "document_id": 1,
                "chunk_index": 1,
            },
        ],
    )
    return client, collection


@pytest.fixture(scope="session")
def isolated_enterprise_store():
    with tempfile.TemporaryDirectory(prefix="deepinsight-enterprise-tests-") as tmpdir:
        base_dir = Path(tmpdir)
        db_path = base_dir / "enterprise_analysis_test.db"
        chroma_path = base_dir / "chroma"
        _create_test_sqlite(db_path)
        client, collection = _create_test_chroma(chroma_path)
        try:
            yield db_path, chroma_path
        finally:
            client._system.stop()
            del collection
            del client
            gc.collect()
            from chromadb.api.client import SharedSystemClient

            SharedSystemClient.clear_system_cache()


@pytest.fixture(autouse=True)
def use_isolated_enterprise_store(monkeypatch, isolated_enterprise_store):
    db_path, chroma_path = isolated_enterprise_store

    from deepinsight.apps import workflow_report
    from deepinsight.core import agent_tools, retriever
    import webapp.main as web_main

    retriever._FIN_IND_HINT.clear()
    monkeypatch.setattr(retriever, "DEFAULT_DB_PATH", db_path)
    monkeypatch.setattr(retriever, "DEFAULT_CHROMA_PATH", chroma_path)
    monkeypatch.setattr(agent_tools, "DEFAULT_DB_PATH", db_path)
    monkeypatch.setattr(workflow_report, "DEFAULT_DB_PATH", db_path)
    monkeypatch.setattr(web_main, "DEFAULT_DB_PATH", db_path)

    monkeypatch.setattr(retriever.get_connection, "__defaults__", (db_path,))
    monkeypatch.setattr(retriever.get_collection, "__defaults__", (chroma_path, COLLECTION_NAME))
    monkeypatch.setattr(retriever.get_financial_indicators_hint, "__defaults__", (db_path,))
    monkeypatch.setattr(retriever.build_sql_prompt, "__defaults__", (None, db_path))
    monkeypatch.setattr(retriever.find_company_names_in_question, "__defaults__", (db_path, 3))
    monkeypatch.setattr(retriever.resolve_company_industry_name, "__defaults__", (db_path,))
    monkeypatch.setattr(retriever.resolve_local_query_filters, "__defaults__", (None, db_path))
    monkeypatch.setattr(retriever.find_macro_indicator_names, "__defaults__", (db_path, 5))
    monkeypatch.setattr(retriever.generate_local_macro_sql, "__defaults__", (db_path,))
    monkeypatch.setattr(retriever.generate_sql, "__defaults__", (None, None, db_path))
    monkeypatch.setattr(retriever.execute_sql, "__defaults__", (db_path,))
    monkeypatch.setattr(retriever.retrieve_chunks, "__defaults__", (None, 5, None, chroma_path, COLLECTION_NAME))
    monkeypatch.setattr(retriever.answer_query, "__defaults__", (None, 5, db_path, chroma_path, COLLECTION_NAME, None, None, None))

    monkeypatch.setattr(agent_tools.tool_get_equity_penetration, "__defaults__", (2, db_path))
    monkeypatch.setattr(agent_tools.tool_get_risk_radar, "__defaults__", (False, db_path))
    monkeypatch.setattr(agent_tools.tool_get_innovation_index, "__defaults__", (db_path,))
    monkeypatch.setattr(agent_tools.run_advanced_analysis, "__defaults__", (db_path, None))
