# Day6 研发证据工作台验证记录

## 目标

本阶段将原网站默认“工作台”重构为真实的研发证据决策工作台。页面保留原工作台的总览式布局，但业务指标全部来自当前已核验 NSCLC 来源登记表和证据链服务，不再展示旧 SQLite/Chroma 缺失时的固定企业数、年报数、财务事实、宏观指标、排名、趋势、雷达评分或模拟预警。

## 为什么不恢复空 SQLite 工作台

Day6 第一阶段审计确认 `data/enterprise_analysis.db` 为 0B 且无可用表，旧 Chroma 目录也不在当前可部署资产中。旧工作台依赖这些数据时无法证明业务数字来源，不能作为比赛主链路恢复。

因此当前默认工作台改为“研发决策工作台”，由以下服务组合计算：

- `SourceRegistryService`
- `EvidenceChainService`
- `CompanyEvidenceComparisonService`
- `GroundedQAService.data_version()`

旧网站功能代码继续保留在旧入口中，但不再决定默认首页，也不再用于比赛工作台指标。

## 指标计算规则

工作台包含 9 项核心指标：

| 指标 | 计算方式 | 当前结果 |
| --- | --- | --- |
| 总来源 | `source_registry.csv` 行数 | 31 |
| 已核验来源 | `verification_status=已人工核验` | 31 |
| 企业主体 | `CompanyEvidenceComparisonService.available_companies()` 归一主体 | 2 |
| 试验级证据链 | `EvidenceChainService.summary().trial_chains` | 10 |
| 药物级监管链 | `EvidenceChainService.summary().regulatory_chains` | 1 |
| 最新资料 | `is_latest_evidence=true` | 4 |
| 历史版本 | `is_latest_evidence=false` | 2 |
| 独立资料 | `is_latest_evidence` 空值或未填写 | 25 |
| 待确认关系 | `EvidenceChainService.get_unresolved_links()` | 7 |

说明：

- 百济神州、BeOne Medicines、BeiGene 归一为同一比较主体。
- 同一 `trial_id` 的证据链只计一项试验。
- B015/B016 属于药物级监管链或关联监管背景，不计入临床试验数量。
- `generated_at` 是接口响应生成时间，不代表证据事件日期。
- `latest_verified_at` 来自来源登记表中的真实核验日期。

## API

新增：

```text
GET /api/evidence/workbench
```

响应结构：

```json
{
  "workbench": {
    "summary": {},
    "companies": [],
    "source_type_distribution": [],
    "study_status_distribution": [],
    "evidence_gaps": [],
    "metadata": {},
    "limitations": []
  },
  "metadata": {
    "data_scope": "first_version_nsclc_hengrui_beone"
  }
}
```

`/api/runtime-capabilities` 新增 `evidence_workbench_available`，当证据工作台可用时 `default_page` 为 `today`。该 `today` 已代表真实证据工作台，不再调用旧 `/api/dashboard`。

## 前端

默认导航显示“研发决策工作台”。进入该页只请求：

```text
/api/evidence/workbench
```

页面展示 9 项核心指标和配套解释：

- 总来源、已核验来源、企业主体、试验级证据链、药物级监管链、最新资料、历史版本、独立资料、待确认关系。
- 恒瑞医药与百济神州/BeOne Medicines 的证据覆盖卡片。
- 来源类型构成、研究状态构成、当前数据缺口。
- 数据版本、最新核验日期、响应生成时间。
- 范围提示：“当前结果仅反映已收录并核验的NSCLC证据样本，不代表企业整体研发实力。”
- 到来源检索、证据链、企业对比、循证问答四个现有页签的快捷入口。

前端不展示企业综合评分、排名、领先方、成功率、疗效优劣、投资建议或没有时间数据支撑的趋势图。

## 测试结果

本阶段新增：

- `tests/test_evidence_workbench_service.py`：6 项。
- `tests/test_evidence_workbench_api.py`：5 项。
- `tests/test_evidence_workbench_frontend.py`：11 项。

受影响回归：

- `tests/test_runtime_capabilities.py`：5 项。
- `tests/test_legacy_frontend_degradation.py`：12 项。

已执行的阶段性检查：

- `webapp/frontend_src/build.py`：通过，`webapp/static/index.html` 已同步。
- `node --check webapp/frontend_src/component.js`：通过。
- 新增三组测试和能力/降级回归测试：通过。

完整 Day6 指定回归见最终执行记录。

## 本地人工验收

本地浏览器人工验收结论：

“研发决策工作台人工验收通过：9项指标正确，无旧固定数据，企业卡片、数据缺口和四个快捷入口正常，Network无旧API，Console无错误。”

验收范围：

- 9项核心指标正确。
- 未展示旧固定企业数、年报数、财务事实、宏观指标、排名、趋势、雷达评分或模拟预警。
- 恒瑞医药与百济神州/BeOne Medicines 企业卡片正常。
- 数据缺口正常。
- 来源检索、证据链、企业对比、循证问答四个快捷入口正常。
- Network 未请求 `/api/bootstrap`、`/api/dashboard`、`/api/profile`。
- Console 无错误。

该结论为本地浏览器人工验收，尚未部署 Day6 版本到 Render。

## 已知限制

- 当前工作台只覆盖第一版已人工核验的 NSCLC 样本，不代表两家企业所有研发活动。
- 研究人群、治疗场景、靶点、机制等字段仍存在结构化缺口，不能自动补全。
- 旧 SQLite/Chroma 工作台仍不可作为比赛主链路恢复。

## 下一步

下一阶段建议实施“企业证据画像”：复用当前工作台服务、来源检索和证据链，按企业组织背景、药物项目、临床试验、论文证据、监管事件和证据缺口。
