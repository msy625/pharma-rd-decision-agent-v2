# 医药研发规范化数据

`data/template/` 是仓库唯一的规范化数据入口。所有表直接位于本目录，不再使用 `mapped/`、`expanded_seed/` 或 `official_harvest/` 子目录。

- `sources.csv`：原始来源与核验状态。
- 实体表：`domains.csv`、`organizations.csv`、`assets.csv`、`indications.csv` 及别名表。
- 研究表：`studies.csv`、`study_identifiers.csv`、`publications.csv`。
- 证据与业务表：`facts.csv`、`relations.csv`、`regulatory_events.csv`、`market_events.csv`。

旧 NSCLC 数据已规范化写入这些表；四领域种子数据已合并。后续外部采集必须向同一套表追加，并保留 `source_id` 和核验状态。
