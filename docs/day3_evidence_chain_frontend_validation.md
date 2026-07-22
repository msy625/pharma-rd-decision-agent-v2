# Day 3 证据链前端接入验证记录

日期：2026-07-22

## 修改范围

本阶段只在现有“研发证据查询”页面内部增加证据链页签，不新增侧边栏主导航，不修改后端 API、CSV、JSON 或证据链服务。

修改内容：

- `webapp/frontend_src/component.js`：增加证据链页签状态、API 调用、列表和详情数据适配。
- `webapp/frontend_src/template.html`：在“研发证据查询”页面内增加“来源检索 / 证据链”两个页签。
- `webapp/static/index.html`：由构建脚本生成。
- `tests/test_evidence_chain_frontend.py`：新增前端静态回归测试。
- `docs/decision_log.md`：记录证据链前端接入决策。

## 页面结构

- 来源检索：保留原有来源查询、版本筛选、结果列表和来源详情。
- 证据链：展示统计卡片、企业/类型筛选、证据链列表、证据链详情和待确认关系折叠区。

证据链统计调用 `GET /api/evidence/chain-summary`，列表调用 `GET /api/evidence/chains`，详情调用 `GET /api/evidence/chains/{chain_id}`，待确认关系调用 `GET /api/evidence/unresolved-links`。

## 关键展示规则

- `chain_id` 详情请求使用 `encodeURIComponent`，支持 `trial:NCT03663205` 这类包含冒号的 ID。
- 外部来源链接只允许 `http/https`，并保留 `target="_blank"` 与 `rel="noopener noreferrer"`。
- 版本标签统一为“最新版本 / 历史版本 / 独立资料”。
- 监管资料优先显示主标签“监管资料”，不再用“独立资料”覆盖监管性质。
- `regulatory_authorisation` 显示为“EMA正式授权信息”，`regulatory_opinion` 显示为“CHMP积极意见”。
- 监管资料的“角色”和“授权状态”分开展示；CHMP 积极意见显示为“积极意见，非最终批准”。
- `study_status` 为空、N/A、不适用或 not applicable 时，不展示“状态”行。
- 不显示评分、成功率、疗效排名或投资建议。
- 不调用 chat、workflow、advanced、大模型、Chroma 或向量模型接口。

## RATIONALE-315 与 B016

- B011、B012、B013 显示在试验证据区域。
- B016 显示在“关联监管背景”区域。
- 页面明确展示“关联监管背景不计入该试验的证据数量”。
- B016 的角色展示为 CHMP 积极意见，授权状态展示为“积极意见，非最终批准”，不写成正式授权或最终批准。

## 加载、空状态和错误

- 切换到证据链页签时自动加载统计、列表和待确认关系。
- 切换企业或类型筛选后自动刷新列表。
- 请求期间展示统计加载、证据链加载、详情加载或待确认关系加载状态。
- 无列表结果时展示“空结果：未找到符合条件的证据链”。
- 请求失败时展示简洁错误提示。

## 验证命令

```bash
.venv/bin/python webapp/frontend_src/build.py
node --check webapp/frontend_src/component.js
.venv/bin/python -m unittest tests/test_evidence_chain_frontend.py
.venv/bin/python -m unittest tests/test_evidence_frontend.py
.venv/bin/python -m unittest tests/test_evidence_chain_api.py
git diff --check
git status --short
git diff --stat
```

## 验证结果

| 命令 | 结果 |
|---|---|
| `.venv/bin/python webapp/frontend_src/build.py` | 通过，生成 `webapp/static/index.html`。 |
| `node --check webapp/frontend_src/component.js` | 通过，无输出。 |
| `.venv/bin/python -m unittest tests/test_evidence_chain_frontend.py` | 通过，25 tests OK。 |
| `.venv/bin/python -m unittest tests/test_evidence_frontend.py` | 通过，24 tests OK。 |
| `.venv/bin/python -m unittest tests/test_evidence_chain_api.py` | 通过，21 tests OK。 |
| `git diff --check` | 通过，无输出。 |
| `git status --short` | 显示本阶段前端、文档和测试改动；未 commit。 |
| `git diff --stat` | 显示已跟踪文件 `docs/decision_log.md`、`webapp/frontend_src/component.js`、`webapp/frontend_src/template.html`、`webapp/main.py` 和 `webapp/static/index.html` 的差异；未跟踪新增文件不计入该命令输出。 |

本阶段未调用网络，未调用 chat、workflow、advanced、大模型、Chroma 或向量模型接口，未安装或更换依赖。
