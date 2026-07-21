# 第二天查询服务验证报告

## 基本信息

- 执行日期：2026-07-21
- 开发任务：封装统一资料查询服务
- 数据文件：`data/source_registry.csv`
- 药物别名配置：`config/entity_aliases.json`
- 证据规则配置：`config/evidence_rules.json`
- 服务文件：`deepinsight/core/source_registry_service.py`
- 命令行入口：`scripts/query_source_registry.py`

## 新增服务接口

`SourceRegistryService` 当前提供以下主要能力：

| 接口 | 用途 |
|---|---|
| `load_rows()` | 读取并校验来源登记CSV。 |
| `load_aliases()` | 读取药物别名配置。 |
| `load_evidence_rules()` | 读取证据规则配置。 |
| `summary()` | 返回总来源数、企业统计、来源类型统计和百济唯一NSCLC试验。 |
| `query(...)` | 支持企业、药物、试验编号、PMID、研究名称、source_id、来源类型、状态和全文关键词的组合查询。 |
| `get_by_source_id(source_id)` | 查询单条来源；不存在时返回 `None`。 |
| `related_evidence(trial_id)` | 查询同一临床试验关联证据。 |
| `normalize_row(row)` | 输出统一结果字段。 |

统一结果字段包括：`source_id`、`company_name`、`drug_name`、`trial_id`、`pmid`、`study_name`、`source_type`、`evidence_level`、`study_status`、`verification_status`、`title_original`、`description_zh`、`source_url`、`verified_at`、`is_latest_evidence`、`parent_trial_id`、`risk_notes`。

`evidence_level` 当前CSV未提供对应字段，服务保留为空值，不生成固定评分或伪精确证据分。

## 真实查询结果

| 查询 | 结果摘要 |
|---|---|
| `--summary` | 总来源31条；恒瑞医药15条；百济神州16条。 |
| `--company "恒瑞医药"` | 返回 H001-H015，共15条。 |
| `--drug "SHR-1210"` | 返回 H001、H002、H004、H005、H006、H008、H009、H010、H011、H012，共10条。 |
| `--trial-id NCT04379635` | 返回 B011、B012、B013，均关联 RATIONALE-315。 |
| `--text NCT04619433` | 返回 H006，`study_status=Terminated`，`verification_status=已人工核验`。 |
| `--study-name RATIONALE-304 --latest-only` | 返回 B003、B007；不返回 B006。 |

## 自动测试结果

| 测试命令 | 结果 |
|---|---|
| `python3 scripts/validate_source_registry.py` | 通过，31条来源完整。 |
| `python3 -m unittest tests/test_source_registry_query.py` | 通过，13项测试。 |
| `python3 -m unittest tests/test_source_registry_service.py` | 通过，15项测试。 |

新增服务测试覆盖：

1. 总计31条。
2. 恒瑞医药15条。
3. 百济神州16条。
4. BeOne Medicines 16条。
5. 企业别名查询一致。
6. SHR-1210匹配卡瑞利珠单抗相关来源。
7. NCT04379635返回B011、B012、B013。
8. NCT04619433返回H006且状态为Terminated。
9. RATIONALE-304 latest_only包含B007、不包含B006。
10. NCT03663205关联证据包含B003、B006、B007。
11. 不存在的企业返回空列表。
12. 不存在的source_id返回空结果。
13. 每条结果至少包含source_id和source_url。
14. 从非仓库根目录调用时仍能读取默认数据。
15. 导入服务时不会调用大模型、向量模型或外部网络依赖。

## 已知限制

- 本阶段只封装本地 CSV/JSON 查询服务，尚未接入 FastAPI、Web 页面或 Streamlit。
- `evidence_level` 暂无CSV字段支持，当前返回空值。
- 企业别名仅覆盖当前人工确认规则：恒瑞医药、百济神州、BeOne Medicines、BeiGene 等，不自动猜测新企业名。
- 药物别名来自 `config/entity_aliases.json`，不自动生成新别名。
- `latest_only` 使用 `is_latest_evidence=false` 排除旧证据版本；登记、监管和公司来源等非版本记录会保留。

## 下一步接入FastAPI

建议下一步在 `webapp/main.py` 中新增最小证据查询API，调用 `SourceRegistryService`：

```text
data/source_registry.csv
→ deepinsight/core/source_registry_service.py
→ webapp/main.py 中新增 /api/evidence/* 路由
→ webapp/frontend_src/component.js 增加证据查询视图
→ 返回来源、证据版本、状态和风险提示
```

接入FastAPI前不需要新增依赖，不需要连接Chroma，也不需要调用DeepSeek。
