# Day6 第四阶段：研发事件时间轴验证报告

日期：2026-07-23
分支：`feature/day6-legacy-integration`
起点提交：`1fd1507c1bc5695eed476802942f95bea3348f92 feat: add company evidence profiles`

## 1. 阶段结论

旧公司事件时间轴已从比赛主链路隔离，新主导航为“研发事件时间轴”。新实现只读取当前本地人工核验的 NSCLC 来源登记表和证据链配置，不依赖旧 SQLite、Chroma、模型、环境密钥或网络。

本阶段未修改 `data/source_registry.csv` 或 `config` 事实数据，未部署 Render，未合并 `main`，未读取 `.env`，未调用 DeepSeek，也未访问业务网络。开发完成后按收尾流程执行本地验证、提交和指定分支推送。

## 2. 为什么旧时间轴不能恢复

旧 `/api/timeline` 调用 `fetch_company_timeline_dashboard()`，数据来自旧 SQLite 的财务、法律风险和专利表，语义是公司经营动态而不是研发证据事件。当前 `data/enterprise_analysis.db` 为空，旧链路无法提供可核验的真实记录。

旧实现还会把只有年份的财务或专利记录补成固定的 `YYYY-12-31` 或 `YYYY-06-30`，旧前端在接口无数据时显示 7 条固定兜底事件。这些日期和事件不能追溯到当前 31 条人工核验来源，因此旧接口继续作为 legacy 路由保留，但不进入新导航、状态、加载或渲染路径。

## 3. 服务与复用关系

新增 `deepinsight/core/rd_event_timeline_service.py`，公开类为 `RDEventTimelineService`，接口包括：

- `normalize_company(company_name)`
- `available_companies()`
- `build_events(include_auxiliary=False)`
- `events_by_company(company_name, include_auxiliary=False)`
- `events_by_trial(trial_id)`
- `events_by_drug(drug_name)`
- `event_type_distribution(events=None)`
- `year_distribution(events=None)`
- `undated_sources(company_name=None, trial_id=None, drug_name=None)`
- `build_timeline(company_name=None, trial_id=None, drug_name=None, event_type=None, year=None, include_auxiliary=False, include_undated=True)`

服务组合现有能力：

- `SourceRegistryService.load_rows()`：读取真实结构化日期和来源字段；查询筛选继续复用现有企业、试验和药物逻辑。
- `EvidenceChainService`：读取 `chain_id`、试验去重、来源角色和版本关系。
- `CompanyEvidenceProfileService`：复用企业别名归一和可用企业列表。
- `EvidenceWorkbenchService`：复用 `data_version`、核验日期和响应生成时间元信息。

未重新实现 CSV 读取、企业别名、药物别名、证据链配置或版本三态规则。

## 4. 日期字段和语义

| 字段 | 时间轴用途 | 语义 |
| --- | --- | --- |
| `online_publication_date` | PubMed 论文首选 | 在线发表日期 |
| `publication_date` | 其他核心事件 | 资料发布日期、公司公告披露日期或监管事件日期 |
| `data_cutoff_date` | 仅辅助事件 | 辅助证据截点 |
| `source_last_updated` | 不生成事件 | 来源页面更新时间元信息 |
| `verified_at` | 不生成事件 | 人工核验日期 |
| `generated_at` | 不生成事件 | API 响应生成时间 |
| `issue_year` | 不覆盖在线日期 | 期刊卷期年份元信息 |

服务不从标题、URL、PMID、试验编号或当前年份猜测缺失日期。月精度值保持 `YYYY-MM`；例如 H013 的 `2026年1月` 规范为 `2026-01`，不会补成 `2026-01-01`。每个事件的 `date` 保留 `value`、`original_value`、`field`、`precision` 和 `semantic`。

## 5. 事件、去重和动态基线

每个来源最多生成一条事件，事件 ID 为 `source:{source_id}`。同一试验的中期、最终或其他论文可以形成多个时间事件，但 `unique_trial_count` 按试验证据链去重。药物级监管事件不计入唯一试验数。

当前动态结果：

| 指标 | 数量 |
| --- | ---: |
| 人工核验来源 | 31 |
| 有可用非核验日期的来源 | 12 |
| 核心事件 | 11 |
| 辅助事件 | 1 |
| 无日期资料 | 19 |
| 恒瑞医药核心事件 | 2 |
| 百济神州 / BeOne Medicines 核心事件 | 9 |
| 百济神州 / BeOne Medicines 辅助事件 | 1 |

B014 是唯一辅助事件，默认隐藏，只在 `include_auxiliary=true` 时显示。当前不生成试验登记、试验开始、试验完成或试验终止事件；相关来源在缺少可用事件日期时进入无日期资料。

核心事件类型分布：

| event_type | 中文标签 | 数量 |
| --- | --- | ---: |
| `company_disclosure` | 公司正式披露 | 2 |
| `registration_authorisation` | 公司公告披露注册获批 | 1 |
| `interim_analysis` | 中期分析 | 3 |
| `final_analysis` | 最终分析 | 2 |
| `combined_analysis_publication` | 中期与最终合并论文 | 1 |
| `formal_authorisation` | 正式授权 | 1 |
| `regulatory_opinion` | 监管意见 | 1 |

辅助类型 `evidence_update` 为 1 条。B010 只生成一条“中期与最终合并论文”事件，不拆成中期和最终两条。

## 6. 版本演进

RATIONALE-304：

- B006：2021-05-23，中期分析，`historical`，`superseded_by_source_id=B007`。
- B007：2024-09-25，最终分析，`latest`，`supersedes_source_id=B006`。
- 两条时间事件，一个唯一试验 `trial:NCT03663205`。

RATIONALE-307：

- B008：2021-05-01，中期分析，`historical`，`superseded_by_source_id=B009`。
- B009：2024-09-25，最终分析，`latest`，`supersedes_source_id=B008`。
- 两条时间事件，一个唯一试验 `trial:NCT03594747`。

服务和前端同时展示正向与反向版本关系。

## 7. 监管事件口径

- B015：事件日期为 2023-09-15，标题为“Tevimbra欧盟初始许可”。`source_last_updated=2026-05-27` 仅作为页面更新时间，不作为批准日期；该事件不表述为围手术期 NSCLC 在 2023-09-15 获得最终批准。
- B016：事件日期为 2025-07-24，标题明确“CHMP积极意见，非最终批准”，不显示为正式批准。
- B015/B016 均属于 `regulatory:tevimbra-eu-nsclc`，不是普通历史版和最新版替代关系。
- `NCT04379635` 只作为 B016 的关联试验背景；B016 不增加试验证据数量，B015 不进入 `NCT04379635` 时间轴筛选结果。
- H014 显示为公司公告披露注册获批，并明确来源不是 NMPA/CDE 原始监管记录。

## 8. API 与错误处理

新增：

- `GET /api/evidence/timeline`
- `GET /api/evidence/timeline/{company}`

支持 `company`、`trial_id`、`drug`、`event_type`、`year`、`include_auxiliary` 和 `include_undated`。中文、英文和历史英文企业别名归一到相同主体；未知企业返回 HTTP 200、空时间轴和“当前数据不足”。

文件缺失或结构异常返回脱敏 503，未知异常返回脱敏 500，不暴露路径、堆栈或密钥。新接口不调用旧 `/api/timeline`，不创建 DeepSeek 客户端，也不加载 OpenAI、Chroma、sentence-transformers 或 Torch。

`/api/runtime-capabilities` 新增 `rd_event_timeline_available`。该能力只检查新的本地证据时间轴服务，不依赖旧 SQLite、Chroma 或 `legacy_features_available`。

## 9. 前端结构

新页面包括：

- 独立的企业、试验、药物、事件类型和年份筛选。
- 默认关闭的辅助事件开关。
- 核心事件、唯一试验、监管相关事件、无日期资料、辅助更新和有日期来源动态指标。
- 事件日期语义、日期字段、原始日期值和精度。
- `source_id`、药物、`trial_id`、`chain_id`、版本、来源类型、核验状态和来源链接。
- B006→B007、B008→B009 版本演进。
- 无日期资料及“未进入时间轴，不代表事件不存在”提示。
- 查看来源、查看证据链、进入循证问答和打开原始链接入口。
- 加载、空结果、错误和窄屏状态。

`timeline` 已从 `_legacyPages()` 移除。页面不读取旧 `state.company` 作为时间轴企业筛选，不请求旧 `/api/timeline`，也不包含旧 7 条固定事件。

## 10. 浏览器人工验收

研发事件时间轴已完成本地浏览器人工验收：

- 主导航和页面加载正常。
- 默认显示 11 条核心事件、19 条无日期资料；有日期来源为 12 条，核心事件仍为 11 条。
- 恒瑞医药与百济神州 / BeOne Medicines 企业筛选及动态指标正确。
- B015 显示 Tevimbra 欧盟初始许可；B016 显示 CHMP 积极意见且非最终批准。
- B006→B007、B008→B009 双向版本演进正确。
- 辅助事件开关默认关闭，开启后显示 B014。
- 企业、试验、药物、事件类型、年份和重置筛选正常。
- 查看来源、查看证据链、进入循证问答和打开原始链接正常。
- Network 只请求新的 `/api/evidence/timeline*` 接口，未请求旧 `/api/timeline`。
- Console 无错误，窄屏响应式布局正常。

该结果是本地浏览器验收，不代表 Render 线上部署验收。

## 11. 自动验证

最终执行结果：

| 验证组 | 模块数 | 测试数 | 结果 |
| --- | ---: | ---: | --- |
| 新研发事件时间轴服务、API、前端 | 3 | 42 | 全部通过 |
| 研发决策工作台回归 | 3 | 22 | 全部通过 |
| 企业证据画像回归 | 3 | 36 | 全部通过 |
| 来源登记服务、查询、API、前端 | 4 | 71 | 全部通过 |
| 证据链服务、API、前端 | 3 | 64 | 全部通过 |
| 企业对比服务、API、前端 | 3 | 58 | 全部通过 |
| runtime capabilities、离线资源、legacy degradation | 3 | 31 | 全部通过 |
| 合计 | 22 | 324 | 全部通过 |

其他验证：

- `.venv/bin/python webapp/frontend_src/build.py`：通过，静态产物已同步。
- `node --check webapp/frontend_src/component.js`：通过。
- `node --check webapp/static/dc-runtime.js`：通过。
- `.venv/bin/python scripts/validate_source_registry.py`：通过，31 条来源完整。
- `git diff --check`：通过。

## 12. 数据限制

- 当前事件只来自第一版 31 条人工核验 NSCLC 来源，不代表企业完整研发历史。
- 19 条无日期资料不能进入排序时间轴，但不代表对应事件、试验或研究不存在。
- 当前不从试验登记状态推导试验开始、完成或终止日期。
- B014 是公司当前活跃管线快照，包含范围差异，只作为可选辅助更新。
- 来源数量、事件数量和年份分布不能解释为企业研发实力或研发活跃度。
- 不输出排名、领先、成功率、疗效或安全性优劣及投资建议。

## 13. 阶段收尾

本阶段自动验证和本地浏览器人工验收均已通过，可以完成提交和指定分支推送。按当前指令暂不继续开发其他功能，不恢复旧 SQLite/Chroma 时间轴，不部署 Render，也不合并 `main`。
