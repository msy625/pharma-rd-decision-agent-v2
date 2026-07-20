import argparse
import sqlite3

from deepinsight.config import DB_PATH

DEFAULT_DB_PATH = DB_PATH
DEFAULT_DEPTH = 3


def get_connection(db_path):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def get_company_id(conn, company_name):
    row = conn.execute("SELECT company_id FROM dim_company WHERE company_name = ?", (company_name,)).fetchone()
    if not row:
        raise ValueError(f"未找到公司: {company_name}")
    return row["company_id"]


def query_downstream_holdings(conn, root_company_id, max_depth=2):
    sql = """
    WITH RECURSIVE equity_tree AS (
        SELECT
            fir.investee_company_id AS company_id,
            dc.company_name,
            1 AS depth,
            fir.equity_ratio AS direct_ratio,
            fir.equity_ratio AS cumulative_ratio,
            CAST(dc.company_name AS TEXT) AS path,
            fir.source_type,
            fir.source_note
        FROM fact_investment_relation fir
        JOIN dim_party dp ON fir.investor_party_id = dp.party_id
        JOIN dim_company dc ON fir.investee_company_id = dc.company_id
        WHERE dp.company_id = ?

        UNION ALL

        SELECT
            fir.investee_company_id AS company_id,
            dc.company_name,
            et.depth + 1 AS depth,
            fir.equity_ratio AS direct_ratio,
            ROUND(et.cumulative_ratio * fir.equity_ratio / 100.0, 4) AS cumulative_ratio,
            et.path || ' -> ' || dc.company_name AS path,
            fir.source_type,
            fir.source_note
        FROM equity_tree et
        JOIN dim_party dp ON dp.company_id = et.company_id
        JOIN fact_investment_relation fir ON fir.investor_party_id = dp.party_id
        JOIN dim_company dc ON fir.investee_company_id = dc.company_id
        WHERE et.depth < ?
    )
    SELECT company_id, company_name, depth, direct_ratio, cumulative_ratio, path, source_type, source_note
    FROM equity_tree
    ORDER BY depth, cumulative_ratio DESC, company_name
    """
    return [dict(row) for row in conn.execute(sql, (root_company_id, max_depth)).fetchall()]


def query_company_graph_snapshot(db_path, root_company, max_depth=DEFAULT_DEPTH):
    conn = get_connection(db_path)
    try:
        root_company_id = get_company_id(conn, root_company)
        rows = query_downstream_holdings(conn, root_company_id, max_depth=max_depth)
        return {
            "root_company": root_company,
            "max_depth": max_depth,
            "rows": rows,
            "summary": {
                "relation_count": len(rows),
                "source_count": len({(row.get("source_type"), row.get("source_note")) for row in rows}),
                "source_types": sorted({row.get("source_type") for row in rows if row.get("source_type")}),
            },
            "message": "暂无足够数据" if not rows else "已读取真实图谱数据",
        }
    finally:
        conn.close()


def parse_args():
    parser = argparse.ArgumentParser(description="查询企业图谱真实数据快照")
    parser.add_argument("--db-path", default=str(DEFAULT_DB_PATH), help="SQLite 数据库路径")
    parser.add_argument("--root-company", required=True, help="查询根节点公司名称")
    parser.add_argument("--depth", type=int, default=DEFAULT_DEPTH, help="股权层级深度")
    return parser.parse_args()


def main():
    args = parse_args()
    try:
        snapshot = query_company_graph_snapshot(args.db_path, args.root_company, args.depth)
    except Exception as exc:
        raise SystemExit(f"企业图谱查询失败: {exc}") from exc
    print(f"root_company={snapshot['root_company']} | relation_count={snapshot['summary']['relation_count']}")
    if not snapshot["rows"]:
        print(snapshot["message"])
        return
    for row in snapshot["rows"]:
        print(
            f"depth={row['depth']} | company={row['company_name']} | "
            f"direct={row['direct_ratio']} | cumulative={row['cumulative_ratio']} | path={row['path']}"
        )


if __name__ == "__main__":
    main()
