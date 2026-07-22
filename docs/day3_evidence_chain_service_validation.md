# Day 3 证据链服务验证记录

日期：2026-07-22

## 验证范围

本阶段完成证据链配置、统一服务和自动测试，不接入 FastAPI，不修改 Web 前端，不修改 `data/source_registry.csv` 的事实内容。

新增能力：

- `config/evidence_chains.json`：人工确认的 10 条试验级证据链和 1 条药物级监管事件链。
- `deepinsight/core/evidence_chain_service.py`：基于配置和 `SourceRegistryService` 的只读证据链服务。
- `tests/test_evidence_chain_service.py`：证据链数量、版本、去重、监管边界、unresolved 和轻量导入测试。

## 统一口径

- 试验级证据链：10 条。
- 药物级监管事件链：1 条。
- 合计证据链：11 条。
- 药物级监管链不计入临床试验数量。
- B015/B016 属于 Tevimbra / tislelizumab 药物级监管事件链。
- B016 可作为 RATIONALE-315 相关监管背景，但不计入 NCT04379635 试验证据数量。
- H014 属于公司/药物级资料；当前无法确认的是 H014 与具体临床试验的一对一关系。

## 测试覆盖

`tests/test_evidence_chain_service.py` 覆盖：

- 试验链数量为 10，监管链数量为 1，总链数为 11。
- RATIONALE-304 包含 B003/B006/B007。
- B006 为历史版本，B007 为最新版本。
- RATIONALE-315 试验链只包含 B011/B012/B013。
- B016 不进入 RATIONALE-315 试验证据计数，但作为相关监管背景返回。
- 监管链包含 B015/B016；B015 为正式授权，B016 仅为 CHMP positive opinion。
- NCT04379635 只计一项试验。
- H003/H004/H005/H006/H007/H015 分别形成单来源试验链。
- H008-H012 和 H014 保持 unresolved。
- 不存在的 `chain_id`、`trial_id` 或药物监管链查询返回空结果。
- 服务导入不加载 Chroma、向量模型或大模型 SDK。
- 配置中的所有 `source_id` 均真实存在。
- 同一 `source_id` 不重复进入两条试验级证据链。

## 本地验证命令

```bash
.venv/bin/python -m json.tool config/evidence_chains.json > /dev/null
.venv/bin/python -m unittest tests/test_evidence_chain_service.py
.venv/bin/python scripts/validate_source_registry.py
.venv/bin/python -m unittest tests/test_source_registry_service.py
git diff --check
git status --short
git diff --stat
```

## 验证结果

| 命令 | 结果 |
|---|---|
| `.venv/bin/python -m json.tool config/evidence_chains.json > /dev/null` | 通过，无输出。 |
| `.venv/bin/python -m unittest tests/test_evidence_chain_service.py` | 通过，18 tests OK。 |
| `.venv/bin/python scripts/validate_source_registry.py` | 通过，31 sources，H001-H015 和 B001-B016 complete。 |
| `.venv/bin/python -m unittest tests/test_source_registry_service.py` | 通过，16 tests OK。 |
| `git diff --check` | 通过，无输出。 |
| `git status --short` | 显示本阶段新增配置、服务、测试和文档；未 commit。 |
| `git diff --stat` | 仅显示已跟踪文件 `docs/decision_log.md` 的 1 行新增；新增未跟踪文件不计入该命令输出。 |

导入检查未发现 `chromadb`、`sentence_transformers` 或 `openai` 被加载；本阶段未调用网络、未调用大模型、未调用 Chroma 或向量模型。
