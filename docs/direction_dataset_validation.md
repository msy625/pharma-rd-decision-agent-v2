# 研发阶段与疾病方向数据接入验证

## 目标

在保持人工核验 NSCLC 样本口径不变的前提下，按 6 个研发阶段 / 20 个疾病方向补充公开数据，
并在网站上提供“疾病方向 / 研发阶段”筛选视图。

## 背景：规范化数据表迁移遗留问题

提交 `a429d5b`（migrate legacy source data to normalized template）删除了 `data/source_registry.csv`，
并把内容迁入 `data/template/` 的规范化表，但当时没有同步修改应用代码：
`deepinsight/core/source_registry_service.py` 仍在读取该文件，
`scripts/query_source_registry.py`、`scripts/build_competition_staging.py` 以及大部分测试同样依赖它。

结果：`main` 分支上证据中心、证据链、企业画像、事件时间轴、循证问答和决策 Agent 全部无法初始化，
测试基线为 **326 failed / 73 errors**，均为 `SourceRegistryFileNotFound: data\source_registry.csv`。

本次处理方式：保留 `data/template/` 作为规范化唯一入口，同时把 `data/source_registry.csv`
（39 条人工核验来源）恢复为**兼容输入**并在 `.gitignore` 中放行。
方向批量采集数据 **不写入** 该文件，因此人工核验样本口径不变。

恢复后测试基线为 **665 passed / 76 subtests passed**；加入方向数据测试后为 **740 passed / 5906 subtests passed**。

### 为什么不从规范化表反向生成该文件

已尝试用 `data/template/` 反向重建 39 行 56 列，结论是**不可行**：

- 39 行的 `source_id` 全部可重建，但逐格比对仍有 **273 处差异**；
- 部分字段在规范化表中没有承载位置，属于不可恢复（`__LOST__`）：
  `evidence_relation`（9 行）、`marketing_authorisation_holder`（2 行）、`data_cutoff_date`（1 行）；
- 另有字段只能部分恢复，例如 `china_trial_id`（B013 `CTR20200821`）、
  `regulatory_authority`（B016 的 `EMA/CHMP` 与规范化值不一致）、
  `comparator` / `biomarker_requirements` / `study_phase` / `study_status` 存在占位丢失。

这些字段被证据版本关系、监管链和事件时间轴直接依赖，丢失后无法通过测试断言。
因此选择把 `data/source_registry.csv` 作为**兼容输入**保留，而不是生成一个内容更弱的替代文件。
后续若要彻底完成迁移，需要先扩展规范化表的字段，再让应用改读 `data/template/`。

## 数据接入

### 目录与配置

| 路径 | 作用 |
| --- | --- |
| `config/direction_catalog.json` | 6 阶段 / 20 方向的目录，含每个方向的 ClinicalTrials.gov 条件检索式与 PubMed MeSH 检索式 |
| `scripts/harvest_direction_data.py` | 采集脚本，写入 `data/template/` 规范化表 |
| `scripts/validate_direction_dataset.py` | 校验脚本，纯离线 |
| `data/template/*.csv` | 规范化数据表（沿用既有表结构，未新增表） |

### 采集来源

- ClinicalTrials.gov API v2：<https://clinicaltrials.gov/api/v2/studies>
- NCBI PubMed E-utilities：esearch + esummary

只读取公开元数据，不抓取论文全文，不绕过访问控制。

### 幂等与写入策略

- 采集表（`sources`、`studies`、`study_identifiers`、`publications`、`facts`、`relations`）
  按主键合并，同 id 覆盖，以便重复执行时反映上游状态与日期变化。
- 参考表（`domains`、`indications`、`organizations`、`assets` 及两张别名表）
  **只写入不覆盖**，不会改写人工维护的既有行。
- `domains` 表的 `parent_domain_id` 通过独立步骤单独更新，不影响其他字段。

### 核验口径

批量采集行的 `verification_status` 为 `api_harvested`，与人工核验样本的 `verified` 严格区分：

- 每一行保留上游标识（`source_locator` 为 `NCT` 号或 `PMID`）与可直接打开的官方链接；
- 脚本按标识规整记录 URL：试验记录使用 `https://clinicaltrials.gov/study/{NCT}`，
  论文记录使用 `https://pubmed.ncbi.nlm.nih.gov/{PMID}/`；
- 无任何可用公开链接的记录被排除，数量记录在
  `GET /api/directions/roadmap` 的 `metadata.excluded_unverifiable_records`。

## 数据规模

`python scripts/validate_direction_dataset.py` 输出（每个方向 100–200 条，全部落在区间内）：

| 阶段 | 目标 | 方向数 | 记录数 |
| --- | --- | ---: | ---: |
| 第 1 阶段（肿瘤） | 建立肿瘤研发竞争分析闭环 | 5 | 701 |
| 第 2 阶段（代谢） | 加入代谢、长期疗效和支付价值 | 3 | 400 |
| 第 3 阶段（心血管） | 加入临床结局和真实世界长期随访 | 3 | 424 |
| 第 4 阶段（免疫与呼吸） | 加入免疫靶点和同类竞品分析 | 4 | 576 |
| 第 5 阶段（罕见与遗传） | 加入自然史、孤儿药和特殊监管路径 | 2 | 293 |
| 第 6 阶段（神经与感染） | 加入复杂终点、患者负担和公共卫生模块 | 3 | 438 |
| **合计** | | **20** | **2832** |

说明：方向记录数包含少量既有的规范化种子数据（例如 NSCLC 方向含原 39 条人工核验样本对应的研究记录），
因此单个方向的记录数高于该方向本次新采集的条数。检索式中的 PubMed 结果按日期倒序，
因此重复执行采集时最新记录会随时间小幅变化（仍在 100–200 区间内）。

## 校验结果

```bash
python scripts/validate_direction_dataset.py
python scripts/validate_source_registry.py
```

校验项与结果：

- 目录为 6 阶段 / 20 方向，方向 key 唯一；
- 每个方向记录数在 100–200 区间内；
- 每条来源 URL 以 `http(s)://` 开头、`verification_status` 与 `verified_at` 非空；
- ClinicalTrials.gov 来源的 `source_locator` 匹配 `^NCT\d{8}$` 且出现在 URL 中；
- PubMed 来源的 `source_locator` 为纯数字 PMID 且出现在 URL 中；
- 所有表主键唯一且非空；
- `studies.domain_id`、`study_identifiers.study_id`、`publications.source_id`、
  `facts.source_id`、`relations.source_id`、`relations.object_id`（资产）均可解析。

结果：**validation passed**，无错误。

### 上游抽样复核

除结构校验外，另随机抽取 8 条试验与 8 篇论文，直接回查上游官方接口确认标识真实存在：

| 核对方式 | 抽样数 | 结果 |
| --- | ---: | --- |
| `GET https://clinicaltrials.gov/api/v2/studies/{NCT}` 返回的 `nctId` 与记录一致 | 8 | 8/8 |
| PubMed `esummary.fcgi` 返回的 `result` 包含对应 `PMID` | 8 | 8/8 |

合计 **16/16 通过，0 失败**。

### 采集可重复性

对单个方向（银屑病）重复执行采集脚本，14 张表的行数变化全部为 `+0`，
同时重新拉取了该方向的 150 条记录：

```text
wrote sources.csv: 2850 -> 2850 rows (+0)
wrote studies.csv: 1664 -> 1664 rows (+0)
wrote publications.csv: 1176 -> 1176 rows (+0)
... 全部 14 张表均为 +0
```

说明脚本幂等：重复执行不会产生重复行，也不会改写参考表中人工维护的既有内容。

## 网站接入

### 新增只读接口

| 接口 | 说明 |
| --- | --- |
| `GET /api/directions/roadmap` | 6 阶段 + 每个方向的记录数、申办方数、分期构成；含 `metadata.excluded_unverifiable_records` |
| `GET /api/directions/summary` | 总记录数、试验数、论文数、方向数、阶段数 |
| `GET /api/directions/filters` | 由真实记录派生的筛选值（来源类型 / 分期 / 状态 / 申办方 / 阶段 / 方向） |
| `GET /api/directions/records` | 按方向、阶段、记录类型、来源类型、分期、状态、申办方、关键词筛选并分页 |

- `direction_id` 同时接受方向 ID（`DOM_X`）与方向 key（`x`）。
- `limit` 上限为 500，越界值会被收敛。
- `GET /api/runtime-capabilities` 新增 `direction_dataset_available`，
  该能力不可用时前端降级且不影响其余入口。

### 错误处理

数据文件缺失返回 503，结构异常返回 503，未知方向返回空结果而非报错，避免把数据问题暴露为 500。

## 边界与限制

- 方向批量采集数据只说明“某方向上有哪些公开注册研究和公开论文”，
  **不表示研发实力、研发活跃度、疗效优劣或成功率**。
- 申办方、干预措施、靶点与权属字段未经核实，不得据此推断企业管线规模或竞争格局。
- 记录数受检索式与 `target` 参数影响，不是穷举计数。
- 批量采集行未经人工逐条复核，不能替代人工核验样本。

## 前端接入

“研发证据中心”新增第 4 个页签「疾病方向」（`evidenceTab='directions'`），包含：

- **阶段路线图**：6 个阶段卡片，展示阶段名、阶段标题、目标、方向数与收录记录数，
  每个方向以 chip 形式展示 方向名 + 试验数 / 论文数；点击方向即筛选该方向的记录。
- **记录列表**：支持按 记录类型 / 分期 / 状态 / 来源类型 / 申办方 / 关键词 筛选，并支持分页。
- **核验口径区分**：每行展示核验状态徽标（`机器采集` / `人工核验`），
  并显示当页 人工核验（verified）与 机器采集（api_harvested）构成。
- **范围声明**：明确说明机器采集记录未经人工逐条复核，与人工核验资料属于两套口径，
  不用于企业研发实力排名，不支持跨试验疗效 / 安全性 / 成功率推断。
- **降级**：`direction_dataset_available` 为 false 时隐藏页签并给出说明，不影响其余入口。

构建方式（`INDEX_HTML_CONTENT` 在 `webapp/main.py` 导入时绑定，改完前端需重启服务）：

```bash
python webapp/frontend_src/build.py
```

## 本机环境注意事项

宿主机默认区域设置为 GBK 时，`tests/test_source_registry_query.py::test_json_output_is_valid`
与 `tests/test_deployment_health.py::test_07_...` 这两个“子进程捕获输出”用例会失败：
子进程按 UTF-8 写出中文，父进程按 GBK 解码，`UnicodeDecodeError` 使 `stdout` 保持为 `None`。
这与本次改动无关，在改动前的 `main` 上同样复现。启用 Python UTF-8 模式即可全部通过：

```bash
PYTHONUTF8=1 python -m pytest -q     # 740 passed, 5906 subtests passed
```

## 验收结论

启动 `uvicorn webapp.main:app --host 127.0.0.1 --port <port>` 后逐项实测，全部通过：

| 检查项 | 结果 |
| --- | --- |
| `GET /health`、`GET /ready` | 通过（`source_count=39`，人工核验口径未变） |
| `direction_dataset_available` | `true`；其余 4 项既有能力位保持 `true` |
| `GET /api/directions/roadmap` | 6 阶段 / 20 方向；**每个方向记录数均落在 100–200**；阶段合计与总数一致 |
| 6 个阶段目标 | 与需求给出的 6 条目标逐字一致 |
| `GET /api/directions/records` | 方向筛选、阶段筛选、记录类型筛选、分页均正确；所有记录带 http(s) 链接 |
| `GET /api/directions/filters` | 由真实记录派生（20 方向 / 6 阶段 / 9 分期 / 797 申办方） |
| `GET /` 与 `/static/index.html` | 均含全部疾病方向页签标记与 3 条 `/api/directions/*` 路径，两者内容一致 |
| 既有入口 | `data-evidence-center-tabs`、`data-evidence-page` 等标记仍在，未破坏原有页签 |
| 全量测试 | **740 passed / 5906 subtests passed / 0 failed** |

### 真实浏览器渲染验收

用 headless Edge 通过 DevTools Protocol 实际打开页面、点击页签并截图（非仅标记级断言）：

| 操作 | 观察结果 |
| --- | --- |
| 打开 `/` | 应用正常启动，标题「药研罗盘｜医药研发可信证据决策系统」 |
| 点击「研发证据中心」→「疾病方向」 | 页签切换成功，第 4 个页签高亮 |
| 路线图渲染 | **6 个阶段卡片、20 个方向 chip**，与需求给出的 6 条阶段目标逐字一致 |
| 路线图汇总 | 阶段 6 · 方向 20 · 收录记录 2832 |
| 范围声明 | 「数据口径与使用边界」提示框正常展示机器采集口径 |
| 核验构成 | 人工核验（verified）41 条 · 机器采集（api_harvested）2791 条 |
| 记录列表 | 每行展示标题、核验状态徽标、研究名称、方向/阶段、申办方或期刊、药物、NCT/PMID、日期、分期与「打开原始来源」 |
| 点击「乳腺癌」chip | 范围切换为「乳腺癌（DOM_BREAST_CANCER）」· 当前收录记录 **130 条**，与接口 `total` 一致 |
| 选择「分期 = Phase 3」 | 列表收敛为 **12 行**，且每行分期均为 Phase 3 |
| 控制台 | **0 条 console error、0 条 page exception** |

截图仅用于本次验收，未纳入仓库。
