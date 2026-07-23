# Day 5 第二阶段：部署入口轻量化与健康检查验证

日期：2026-07-23
分支：`feature/day5-release-deploy`

本阶段目标是让比赛核心循证链路在未安装旧网站重依赖时仍能导入并启动 FastAPI，同时增加健康检查接口。未修改证据 CSV、事实 JSON、requirements、部署配置或 `.env`。

## 健康检查接口

`GET /health` 是存活检查，只返回固定结构：

```json
{
  "status": "ok",
  "service": "pharma-rd-decision-agent"
}
```

它不读取 CSV、JSON、SQLite 或 Chroma，不创建 DeepSeek 客户端，不读取 API 密钥，不访问网络，也不加载模型。

`GET /ready` 是比赛核心链路就绪检查，会读取并校验当前核心 CSV/JSON 数据：

- `data/source_registry.csv`
- `config/entity_aliases.json`
- `config/evidence_rules.json`
- `config/evidence_chains.json`
- `config/grounded_qa_rules.json`

成功时返回：

```json
{
  "status": "ready",
  "service": "pharma-rd-decision-agent",
  "data_version": "sha256:<16 hex chars>",
  "source_count": 31,
  "local_grounded_qa_available": true
}
```

必需文件缺失或结构异常时返回 HTTP 503，错误文案为通用中文说明，不暴露绝对路径、堆栈或密钥名。

## 顶层导入轻量化

`webapp.main` 保留比赛主链路服务的直接导入：

- `SourceRegistryService`
- `EvidenceChainService`
- `CompanyEvidenceComparisonService`
- `GroundedQAService`
- `grounded_llm_settings`

旧功能相关导入已改为路由内延迟导入：

- `deepinsight.apps.app_whitebox`
- `deepinsight.apps.workflow_report`
- `deepinsight.core.agent_tools`
- `deepinsight.core.retriever` 中的旧问答、DeepSeek 客户端和 SQLite 辅助函数

旧 SQLite 数据库不可用或表结构缺失时，旧接口也会映射为同一个友好 503，不把 SQLite 表名错误、绝对路径或堆栈暴露给前端。

本地导入验证：

```text
import webapp.main -> import_ok
未加载 streamlit,pandas,chromadb,sentence_transformers,torch,openai,requests
```

## 缺少旧重依赖时仍可使用

在隔离子进程中模拟 `streamlit`、`pandas`、`chromadb`、`sentence_transformers`、`torch` 不可导入时，以下功能仍可用：

- `GET /health`
- `GET /ready`
- `GET /api/evidence/summary`
- `GET /api/evidence/search`
- `GET /api/evidence/company/{name}`
- `GET /api/evidence/drug/{name}`
- `GET /api/evidence/trial/{trial_id}`
- `GET /api/evidence/study/{name}`
- `GET /api/evidence/source/{source_id}`
- `GET /api/evidence/chain-summary`
- `GET /api/evidence/chains`
- `GET /api/evidence/company-comparison`
- `GET /api/evidence/grounded-qa/capabilities`
- `POST /api/evidence/grounded-qa` 的本地模式和无密钥 auto 回退

## 旧接口降级

旧网站功能路由保留，不删除。缺少旧功能依赖时返回 HTTP 503：

```json
{
  "detail": "旧网站功能当前不可用；比赛核心循证接口仍可使用。"
}
```

受影响路由包括：

- `/api/bootstrap`
- `/api/dashboard`
- `/api/profile`
- `/api/compare`
- `/api/timeline`
- `/api/database/*`
- `/api/data-room/*`
- `/api/chat`
- `/api/workflow`
- `/api/batch-workflow`
- `/api/advanced`
- `/api/whitebox`

该降级不伪造业务结果，不泄露绝对路径、堆栈或密钥。

## 已知限制

- 旧接口在依赖齐全但旧 SQLite/Chroma 数据缺失时仍可能按原逻辑报错或返回旧链路降级结果；本阶段只处理入口导入轻量化直接相关的问题。
- `/ready` 是比赛核心链路就绪检查，不代表旧 SQLite/Chroma 网站功能可用。
- 本阶段未新增 `requirements-deploy.txt`，最小部署依赖配置属于下一阶段。
- 本阶段未处理前端 React CDN 本地化风险。

## 测试结果

已执行：

```text
.venv/bin/python -m unittest tests/test_deployment_health.py
8 tests OK

.venv/bin/python -m unittest tests/test_evidence_api.py
18 tests OK

.venv/bin/python -m unittest tests/test_evidence_chain_api.py
21 tests OK

.venv/bin/python -m unittest tests/test_company_evidence_comparison_api.py
18 tests OK

.venv/bin/python -m unittest tests/test_grounded_qa_api.py
29 tests OK
```

已完成收尾验证：

```text
.venv/bin/python scripts/validate_source_registry.py
source_registry validation passed: 31 sources, H001-H015 and B001-B016 complete.

.venv/bin/python -m json.tool config/evidence_chains.json > /dev/null
OK

.venv/bin/python -m json.tool config/grounded_qa_rules.json > /dev/null
OK

git diff --check
OK
```
