# 第二天 FastAPI 证据接口验证报告

## 新增接口

本阶段在现有 `webapp/main.py` 中新增只读证据查询接口：

| 接口 | 用途 |
|---|---|
| `GET /api/evidence/summary` | 返回第一版资料统计、企业来源数、数据范围和核验日期。 |
| `GET /api/evidence/search?q=...` | 按任意关键词检索资料，支持 `latest_only` 和 `limit`。 |
| `GET /api/evidence/company/{name}` | 按企业名称或企业别名查询。 |
| `GET /api/evidence/drug/{name}` | 按药物名称、英文名或研发代号查询。 |
| `GET /api/evidence/trial/{trial_id}` | 按 NCT 编号查询同一试验的关联证据。 |
| `GET /api/evidence/study/{name}` | 按研究名称查询，支持 `latest_only`。 |
| `GET /api/evidence/source/{source_id}` | 按 `source_id` 查询单条资料。 |

所有筛选逻辑均调用 `deepinsight.core.source_registry_service.SourceRegistryService`，API 层不重新实现 CSV 筛选。

## 响应格式

列表类接口统一返回：

```json
{
  "query": {},
  "count": 0,
  "items": [],
  "metadata": {
    "data_scope": "first_version_nsclc_hengrui_beone",
    "data_source": "source_registry.csv"
  }
}
```

单条来源接口返回：

```json
{
  "item": {}
}
```

单条资料保留 `source_id`、`company_name`、`drug_name`、`trial_id`、`pmid`、`study_name`、`source_type`、`study_status`、`verification_status`、`title_original`、`description_zh`、`source_url`、`verified_at`、`is_latest_evidence`、`parent_trial_id` 等字段。`evidence_level` 当前保持为空，不生成评分。

## 错误处理

| 场景 | 行为 |
|---|---|
| `q` 为空 | 返回 400。 |
| `limit` 小于1或大于100 | 返回 400；有完整 FastAPI 参数校验时也可能为 422。 |
| `source_id` 不存在 | 返回 404。 |
| 企业、药物、试验或研究无结果 | 返回 200，`items=[]`。 |
| 数据文件缺失 | 返回 503，提示证据资料文件不可用。 |
| CSV或JSON结构异常 | 返回 503，提示证据资料结构异常。 |
| 未知异常 | 返回 500，使用友好错误信息，不返回堆栈或本地绝对路径。 |

## 接口查询场景

| 查询 | 结果摘要 |
|---|---|
| `/api/evidence/summary` | `total_sources=31`。 |
| `/api/evidence/company/恒瑞医药` | 返回15条。 |
| `/api/evidence/company/百济神州` | 返回16条。 |
| `/api/evidence/company/BeOne Medicines` | 返回16条。 |
| `/api/evidence/drug/SHR-1210` | 返回卡瑞利珠单抗相关资料，包含 H004。 |
| `/api/evidence/trial/NCT04379635` | 返回 B011、B012、B013。 |
| `/api/evidence/trial/NCT04619433` | 返回 H006，`study_status=Terminated`。 |
| `/api/evidence/study/RATIONALE-304?latest_only=true` | 包含 B007，不包含 B006。 |
| `/api/evidence/source/B015` | 返回 EMA 当前正式授权信息，`authorisation_status=欧盟正式授权`。 |
| `/api/evidence/source/B016` | 返回 CHMP positive opinion，不标记为欧盟正式授权。 |

以上场景由 `tests/test_evidence_api.py` 覆盖；在安装 FastAPI 依赖的环境中会通过 ASGI 客户端发起真实 HTTP 请求。当前基础解释器缺少 FastAPI，无法在本机完成该测试分支。

## 自动测试结果

已新增 `tests/test_evidence_api.py`，覆盖17项真实 ASGI 请求场景：

1. summary返回31条。
2. company/恒瑞医药返回15条。
3. company/百济神州返回16条。
4. company/BeOne Medicines返回16条。
5. drug/SHR-1210返回卡瑞利珠单抗资料。
6. trial/NCT04379635返回B011、B012、B013。
7. trial/NCT04619433返回H006且状态为Terminated。
8. study/RATIONALE-304 latest_only包含B007、不包含B006。
9. source/B015返回EMA正式授权资料。
10. source/B016不显示为最终批准。
11. 不存在的source_id返回404。
12. 不存在的企业不返回500。
13. 空search参数返回400。
14. 非法limit返回400或422。
15. 每条结果包含source_id和source_url。
16. API导入和请求过程不加载Chroma或sentence-transformers。
17. 旧的 `/api/whitebox` 路由仍可通过 HTTP 访问。

## 真实环境问题修复记录

真实 FastAPI 环境测试发现，早期测试直接调用路由函数，遗漏了 FastAPI `Query` 默认值对象进入业务逻辑的问题。例如直接调用 `evidence_by_company("恒瑞医药")` 时，未显式传入 `limit` 会导致 `limit` 接收到 `Query` 对象，进而在 `_validate_evidence_limit()` 中触发类型错误。

本次修复采用 `typing.Annotated` 搭配 `Query` 约束，并将 Python 默认值保持为普通值：

```python
limit: Annotated[int, Query(ge=1, le=100)] = 100
latest_only: Annotated[bool, Query()] = False
```

这样通过 HTTP 调用时仍由 FastAPI 校验参数范围，直接调用路由函数时默认值也是普通 `int` 或 `bool`。API 测试已改为优先使用 `FastAPI TestClient` 发起真实 ASGI 请求；若当前依赖组合导致 `TestClient` 不可用，则回退到当前 `httpx` 支持的 `ASGITransport`。直接调用只保留一个回归测试，用于确认 `limit` 默认值不再是 `Query` 对象。

当前基础解释器没有 `python` 命令，也未发现仓库内 `.venv/bin/python`；`python3` 可用但未安装 FastAPI，因此本地执行 `python3 -m unittest tests/test_evidence_api.py` 时 18 项测试按依赖缺失跳过。未安装 `httpx2`，未修改 `requirements.txt`。本环境未观察到 `StarletteDeprecationWarning`；在具备 FastAPI 的真实环境中若 `TestClient` 仍输出该警告，它不影响当前功能验证。

## 提交前一致性修正

提交前发现 B011 的备注仍包含“RATIONALE-315 的 ClinicalTrials.gov 登记将在后续批次补充”的过时表述。当前 B012 已收录 NCT04379635 的 ClinicalTrials.gov 登记，B013 已收录公司官方试验页面，因此已将 B011 备注修正为：

- B011 是 RATIONALE-315 中期分析论文；
- B012 是同一试验的 ClinicalTrials.gov 登记；
- B013 是同一试验的公司官方试验页面；
- B011、B012、B013 均对应同一项 NCT04379635/RATIONALE-315 试验，不重复计数。

已增加回归检查，确认 B011 的 `risk_notes` 不再包含“后续批次补充”，并确认 B011、B012、B013 的关联试验仍为 NCT04379635。

## Uvicorn 与 curl 验证

本次尝试在当前 shell 中按要求使用 `python -m uvicorn ...` 启动服务，但 `python` 命令不存在；使用 `python3` 时当前环境缺少 FastAPI 依赖，无法完成 Uvicorn 启动和 curl 实测。该项需要在已激活且安装项目依赖的虚拟环境中补跑。

## 已知限制

- 本阶段没有修改 Web 前端，因此浏览器页面尚未暴露这些接口。
- 当前基础解释器缺少 FastAPI，真实 ASGI 请求测试在本环境被跳过；测试文件已取消 stub 路由测试，具备依赖时会请求真实 `app`。
- 证据接口当前只读取 CSV/JSON，不连接 SQLite、Chroma 或大模型。
- `evidence_level` 暂无来源字段支持，当前不返回评分。

## 下一步前端接入

下一步建议在 `webapp/frontend_src/component.js` 中增加证据查询视图，调用 `/api/evidence/summary`、`/api/evidence/search`、`/api/evidence/company/{name}`、`/api/evidence/drug/{name}` 和 `/api/evidence/trial/{trial_id}`。完成后再同步生成 `webapp/static/index.html` 并更新 README。
