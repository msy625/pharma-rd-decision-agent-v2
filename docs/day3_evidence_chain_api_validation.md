# Day 3 证据链 API 验证记录

日期：2026-07-22

## 新增接口

本阶段将 `EvidenceChainService` 接入现有 FastAPI，仅新增只读接口，不修改 Web 前端。

- `GET /api/evidence/chain-summary`
- `GET /api/evidence/chains`
- `GET /api/evidence/chains/{chain_id}`
- `GET /api/evidence/trial-chain/{trial_id}`
- `GET /api/evidence/drug/{name}/regulatory-chain`
- `GET /api/evidence/unresolved-links`

## 响应格式

列表接口统一返回：

```json
{
  "query": {},
  "count": 0,
  "items": [],
  "metadata": {
    "data_scope": "first_version_nsclc_hengrui_beone",
    "relationship_source": "evidence_chains.json"
  }
}
```

单条接口统一返回：

```json
{
  "item": {}
}
```

证据链详情保留 `chain_id`、`chain_name`、`chain_type`、`company_name`、`drug_names`、`trial_ids`、`study_names`、`study_status`、`evidence_items`、`latest_items`、`historical_items`、`independent_items`、`regulatory_items`、`related_regulatory_items`、`evidence_gaps`、`risk_notes` 和 `source_count`。

## 错误处理

- 非法 `chain_type`：400。
- 非法 `limit`：FastAPI 参数校验 422，或手动校验 400。
- 不存在 `chain_id`：404。
- 不存在 `trial_id`：404。
- 不存在药物监管链：200，`item={}`。
- 列表无结果：200，`items=[]`。
- 配置或数据文件缺失：503。
- JSON/CSV 结构异常：503。
- 未知错误：500，返回友好提示，不暴露绝对路径、堆栈或密钥。

## 关键关系验证

- `trial:NCT04379635` 只把 B011、B012、B013 放入 `evidence_items`，`source_count=3`。
- B016 通过 `related_regulatory_items` 返回，作为 RATIONALE-315 相关监管背景。
- B016 不增加 NCT04379635 的试验证据数量。
- B015/B016 进入 `regulatory:tevimbra-eu-nsclc` 药物级监管链。

## 自动测试

`tests/test_evidence_chain_api.py` 使用轻量 ASGI 请求，不调用真实网络，覆盖：

- summary 总链数 11、试验链 10、监管链 1。
- RATIONALE-304 证据版本：B006 历史、B007 最新。
- RATIONALE-315 与 B016 的试验级/监管背景边界。
- tislelizumab 药物级监管链。
- 恒瑞医药 6 条试验链。
- 非法参数、404、空监管链、unresolved 列表。
- 响应不包含评分、成功率或疗效排名字段。
- API 请求不加载 Chroma、向量模型或大模型 SDK。
- 原有 `/api/evidence/*` 查询接口仍可用。

## 本地验证命令

```bash
.venv/bin/python -m unittest tests/test_evidence_chain_service.py
.venv/bin/python -m unittest tests/test_evidence_chain_api.py
.venv/bin/python -m unittest tests/test_evidence_api.py
.venv/bin/python -m unittest tests/test_source_registry_service.py
.venv/bin/python -m json.tool config/evidence_chains.json > /dev/null
.venv/bin/python scripts/validate_source_registry.py
git diff --check
git status --short
git diff --stat
```

## 验证结果

| 命令 | 结果 |
|---|---|
| `.venv/bin/python -m unittest tests/test_evidence_chain_service.py` | 通过，18 tests OK。 |
| `.venv/bin/python -m unittest tests/test_evidence_chain_api.py` | 通过，21 tests OK。 |
| `.venv/bin/python -m unittest tests/test_evidence_api.py` | 通过，18 tests OK。 |
| `.venv/bin/python -m unittest tests/test_source_registry_service.py` | 通过，16 tests OK。 |
| `.venv/bin/python -m json.tool config/evidence_chains.json > /dev/null` | 通过，无输出。 |
| `.venv/bin/python scripts/validate_source_registry.py` | 通过，31 sources，H001-H015 和 B001-B016 complete。 |
| `git diff --check` | 通过，无输出。 |
| `git status --short` | 显示本阶段新增配置、服务、API测试和文档；未 commit。 |
| `git diff --stat` | 显示已跟踪文件 `docs/decision_log.md` 和 `webapp/main.py` 共 103 行新增；未跟踪新增文件不计入该命令输出。 |

本阶段未安装或更换依赖，未调用网络，未接入大模型、Chroma 或向量模型。
