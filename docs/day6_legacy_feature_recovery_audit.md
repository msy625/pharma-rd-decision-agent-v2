# Day6 第一阶段：旧功能和旧数据恢复审计

日期：2026-07-23
分支：`feature/day6-legacy-integration`

## 1. 审计范围

本阶段只做只读审计和恢复设计，不修改业务代码、前端、数据、依赖或部署配置。审计对象包括旧 SQLite、旧 Chroma、本地演示缓存、旧 Streamlit 入口、FastAPI 旧接口、当前前端导航入口、数据导入脚本、部署说明和 Git 跟踪/忽略状态。

本阶段未读取 `.env`，未调用 DeepSeek，未访问业务网络。

## 2. 旧数据资产清单

| 资产 | 当前是否存在 | Git 状态 | 大小 | 来源说明 | 敏感信息初筛 | 干净克隆可获得 | Render 可获得 | 结论 |
|---|---:|---|---:|---|---|---:|---:|---|
| `data/enterprise_analysis.db` | 是 | 被 `.gitignore` 忽略，未跟踪 | 0 B | `deploy/README.md` 要求本地补齐或从原始文档重建 | 空文件，未发现可读内容 | 否 | 否 | 当前不可恢复旧功能 |
| `data/chroma/` | 否 | 被 `.gitignore` 忽略，未跟踪 | 不适用 | `db_init.py`/`data_pipeline.py` 可初始化，需原始文档和 Chroma 依赖 | 未审计到实际库内容 | 否 | 否 | 不建议进入比赛主链路 |
| `data/raw_macro/国家统计局_卫生_2022_2024.xlsx` | 是 | 已跟踪 | 28 KB | 文件名与 `macro_import.py` 指向国家统计局卫生数据 | 未展开正文，仅做文件级检查 | 是 | 是 | 可作为宏观辅助数据，需二次核验字段口径 |
| `demo_cache/` | 是 | 已跟踪 | 480 KB | `deepinsight/demo/demo_cache.py` 生成的演示缓存 | 未发现密钥；包含旧企业经营样例和演示结论 | 是 | 是 | 仅可作历史样例，不进比赛主链路 |
| `audit_md/` | 是 | 已跟踪 | 20 KB | 早期审计报告 | 未发现密钥；记录了旧 mock 风险 | 是 | 是 | 可作为风险依据 |
| `deepinsight/dataops/` | 是 | 已跟踪 | 200 KB | SQLite/Chroma/宏观导入脚本 | 代码中存在调用环境变量的 embedding 客户端，但未读取密钥 | 是 | 是 | 可复用 schema 和导入框架 |
| `scripts/` | 是 | 已跟踪 | 80 KB | Streamlit 启动脚本和证据查询脚本 | 未发现密钥；有本地演示入口 | 是 | 是 | 可作为本地后台入口 |
| `deploy/` | 是 | 已跟踪 | 36 KB | 旧长期服务器部署说明 | 有通用服务器绝对路径示例，不是个人工作站路径；不含密钥值 | 是 | 是 | 仅作旧部署参考 |

Git 历史检查结论：`data/enterprise_analysis.db` 和 `data/chroma/` 未在当前仓库历史中作为跟踪文件出现；干净克隆和 Render 轻量部署均不能获得这两项旧数据底座。

## 3. SQLite 审计

`data/enterprise_analysis.db` 当前存在但为空文件。使用 Python 标准库 `sqlite3` 以只读方式连接后，`sqlite_master` 中没有表或视图。

因此当前无法审计真实 SQLite 表行数、企业覆盖、年份覆盖、来源 URL、来源名称、发布日期或核验日期。根据代码和 schema 脚本，旧 SQLite 预期包含：

- 基础表：`dim_industry`、`dim_company`、`dict_financial_indicator`、`dim_document`、`fact_financial_report`、`dict_macro_indicator`、`fact_macro_data`、`map_vector_chunk`
- 扩展表：`dim_person`、`dim_party`、`fact_investment_relation`、`fact_legal_risk`、`fact_ip_patent`

schema 中具备部分可追溯字段：

- `dim_document.publish_date`
- `dim_document.source_url`
- `fact_financial_report.source_page`
- `dict_macro_indicator.source_name`
- `fact_macro_data.release_date`
- `fact_macro_data.source_file`
- `fact_investment_relation.source_type/source_note`
- `fact_legal_risk.source_type/source_note`
- `fact_ip_patent.source_type/source_note`

但当前仓库没有旧数据库内容，不能证明这些字段已经被真实填充。

风险：

- `fact_legal_risk.severity_score`、`fact_ip_patent.patent_score` 和 `agent_tools.build_radar_scores()` 会形成 0-100 评分或雷达图口径。
- `fetch_industry_ranking_dashboard()` 和旧 `/api/compare` 会输出排名、赢家或领先项，这与当前循证主链路“不输出企业综合评分、成功率、疗效排名或投资建议”的口径冲突。
- `macro_import.py` 写入 `source_file` 时会使用本地绝对路径，若恢复该链路，需要改成相对来源标签或文件名，避免暴露本地路径。

重建可能性：

- 仅靠当前仓库不能完整重建旧 SQLite，因为原始年报/研报目录 `Final_md/`、`reports_md/`、`report_md/` 当前不存在且未在 Git 历史中跟踪。
- 可以复用 `db_init.py`、`db_expand.py` 和 `macro_import.py` 建空 schema 并导入当前宏观 Excel。
- 若后续提供真实年报/研报原文和可核验来源清单，可用 `data_pipeline.py` 重建部分旧表，但仍需人工核验字段抽取质量。

## 4. Chroma 审计

`data/chroma/` 当前不存在；Git 历史未显示曾跟踪该目录。不能读取 collection 名称、文档数量或 metadata 实际内容。

代码层预期：

- 默认目录：`data/chroma`
- 默认 collection：`enterprise_documents`
- 预期 metadata：`source`、`page`、`doc_type`、`company_name`、`industry_name`、`report_year`
- 初始化依赖：`chromadb`
- 导入依赖：Chroma、文本切分组件，旧 embedding 写入流程可使用本地哈希 embedding；历史代码中还保留智谱 embedding 客户端，但默认 `get_embedding_client()` 返回本地实现。

结论：当前不建议把旧 Chroma RAG 放入比赛主链路。原因是实际向量库缺失、原始文档缺失、部署依赖重、可解释性弱于现有 31 条人工核验证据登记表。若未来恢复，应先重新核验原文、metadata、source URL、页码和 chunk 到 source_id 的映射。

## 5. 旧功能恢复矩阵

| 功能 | 前端入口 | 后端 API | 服务函数 | 数据依赖 | 第三方依赖 | 当前是否可运行 | 真实数据状态 | 风险 | 比赛价值 | 难度 | Render Free 可行性 | 建议 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 工作台 | `today` | `/api/bootstrap`、`/api/dashboard` | `fetch_bootstrap_data`、`fetch_import_dashboard`、`fetch_company_trend_dashboard`、`fetch_industry_ranking_dashboard`、`fetch_alert_center`、`fetch_macro_linkage_dashboard` | SQLite 基础/扩展表 | pandas/chromadb 作为 legacy capability 检查项 | 否，SQLite 为空 | 当前无真实旧 DB | 排名、宏观相关性容易被误读 | 高，可改成证据总览 | 中 | 可行，若改接证据服务 | 改接当前证据服务 |
| 公司画像 | `compare` 页画像区 | `/api/profile` | `fetch_company_profile_dashboard`、`agent_tools` | SQLite 财务、风险、专利、股权 | 旧 DB、agent tools | 否 | 当前无真实旧 DB | 雷达评分和专利/风险评分口径未核验 | 高，可变成企业证据画像 | 中 | 可行，若基于 CSV/JSON | 改接当前证据服务 |
| 公司对比 | `compare` 页对比区 | `/api/compare` | `fetch_compare_matrix_dashboard` | SQLite 财务、风险、专利 | 旧 DB、agent tools | 否 | 当前无真实旧 DB | 输出 winner/领先项，和循证对比冲突 | 中 | 中 | 可行但需改口径 | 与循证功能合并 |
| 自动化研报 | `research` | `/api/workflow`、`/api/batch-workflow` | `run_workflow` | SQLite + Chroma 或 demo_cache | 旧 RAG、可选 LLM | 否 | 当前无真实旧 DB/Chroma | 早期审计指出历史 workflow 曾使用固定 mock | 高，若每段带 source_id | 高 | 轻量版可行，旧 RAG 不可行 | 改接当前证据服务 |
| 白盒溯源 | `whitebox` | `/api/whitebox` | `app_whitebox` 常量 | 静态常量 | Streamlit/OpenAI 仅在旧页面中 | 可返回静态演示 | 非实时真实链路 | 硬编码 SQL/RAG/思考链 | 高，若复用 GroundedQA trace | 低到中 | 可行，若重构为 trace 展示 | 与循证功能合并 |
| 数据库浏览 | `database` | `/api/database/catalog`、`/api/database/table` | `fetch_database_catalog`、`fetch_database_table_preview` | SQLite 任意表 | 旧 DB | 否 | 当前无真实旧 DB | 可能暴露内部表和路径字段 | 中，适合本地审查 | 低 | 不建议公开 | 仅本地后台保留 |
| 事件时间轴 | `timeline` | `/api/timeline` | `fetch_company_timeline_dashboard` | SQLite 财务、风险、专利 | 旧 DB | 否 | 当前无真实旧 DB | 混合财务/风险/创新，不是研发事件 | 高，若改为试验/论文/监管时间轴 | 中 | 可行 | 改接当前证据服务 |
| 高级分析 | `advanced` | `/api/advanced` | `run_advanced_analysis`、`tool_get_*` | SQLite 扩展表 | 旧 DB、可选 LLM | 否 | 当前无真实旧 DB | 雷达评分、综合分析、无证据引用 | 低到中 | 中 | 不建议公开 | 从比赛主链路隔离 |
| 旧智能问答 | `chat` | `/api/chat` | `answer_query` | SQLite + Chroma | Chroma、旧 RAG、可选 LLM | 否 | 当前无真实旧 DB/Chroma | 与 GroundedQA 重复，检索来源不可按 source_id 校验 | 低 | 高 | 不建议 | 从比赛主链路隔离 |

## 6. 固定/模拟结果风险

按类型区分：

- 测试代码：`unittest.mock`、测试中的 forbidden 关键词属于测试工具或断言，不是运行路径风险。
- 历史审计文档：`audit_md/03-workflow-behavior-mismatch.md` 明确记录旧 `workflow_report.py` 曾把固定 mock 数据展示成 SQL/Chroma 结果。
- 非主链路实验：`deepinsight/experiments/mock_llm.py` 和 `agent_loop.py` 是实验代码，不应接入比赛页面。
- 当前页面真实运行路径：`/api/whitebox` 返回 `app_whitebox` 中硬编码 SQL、RAG chunk 和结论；`/api/advanced` 使用评分/雷达口径；旧 `/api/compare` 输出 winner/领先项。
- 当前 Render 轻量路径：Day5 已通过 runtime capabilities 隔离旧功能，轻量模式默认 `evidence`，不会自动请求旧 `/api/bootstrap`、`/api/profile`、`/api/dashboard`，也不会展示旧固定统计。

发现的具体风险：

- `demo_cache/advanced_st_bio.json` 含“模拟”和“评分”痕迹。
- `demo_cache/*.json` 多数含旧 SQLite/Chroma 上下文，但当前旧 DB/Chroma 不存在，不能作为可核验事实来源。
- `app_whitebox.py` 存在硬编码 ST生物 SQL、RAG chunk、白盒推理和结论。
- `agent_tools.build_radar_scores()` 使用 0-100 雷达评分口径。
- 旧公司对比使用 winner/领先项，不适合比赛循证口径。

不得恢复：

- MOCK、固定演示响应或无来源结论。
- 雷达评分、综合评分、企业排名、疗效排名、成功率、投资建议。
- 无 source_id、source_url 或核验日期的“结论型”展示。

## 7. P0/P1/P2 优先级

P0，必须优先恢复或重构：

- 真实数据决策工作台：基于 `SourceRegistryService`、`EvidenceChainService`、`CompanyEvidenceComparisonService`，展示总来源、已核验来源、企业数、试验链、监管链、最新/历史/独立资料、待确认关系、数据版本和核验日期。
- 企业证据画像：从当前核验证据生成企业背景、药物项目、临床试验、论文证据、监管事件和证据缺口。
- 研发事件时间轴：基于 source registry 和 evidence chains，明确区分事件日期、发布日期和核验日期。
- 带引用的自动研报：使用当前已核验证据，每段结论绑定 `source_id` 和 URL，列出数据限制。

P1，可作为辅助恢复：

- 数据库浏览：只建议本地后台保留，线上隐藏或按 capability 禁用。
- 白盒溯源：不恢复旧静态演示，改为 GroundedQA trace、证据来源、证据链、引用校验和安全规则展示。
- 企业背景对比：仅使用当前企业证据对比服务，不恢复财务 winner/雷达评分。

P2，暂不进入比赛主链路：

- 旧智能问答。
- 重型 Chroma RAG。
- 无来源高级分析。
- 固定评分与排名。
- demo_cache 演示缓存。

## 8. 统一产品结构

建议把旧网站框架收敛为一个统一产品，而不是把旧功能并列恢复。

1. 决策工作台
   - 当前已核验来源数。
   - 企业数。
   - 试验链数。
   - 监管链数。
   - 最新/历史/独立资料。
   - 待确认关系。
   - 数据版本和核验日期。

2. 企业证据画像
   - 企业背景。
   - 药物项目。
   - 临床试验。
   - 论文证据。
   - 监管事件。
   - 证据缺口。

3. 研发事件时间轴
   - 试验登记。
   - 中期论文。
   - 最终论文。
   - CHMP 意见。
   - 正式授权。
   - 明确区分事件日期、发布日期、核验日期。

4. 自动化研报
   - 使用当前已核验证据。
   - 每段结论带 `source_id`。
   - 列出引用 URL。
   - 列出数据限制。
   - 不输出疗效排名、成功率或投资建议。

5. 循证问答与白盒
   - 复用 `GroundedQAService`。
   - 展示问题分类、证据来源、证据链、引用校验、安全规则。
   - 不恢复旧模拟回答。

## 9. 能力分级设计

当前 `runtime-capabilities` 只有 `legacy_features_available` 布尔值。建议升级为独立能力结构：

```json
{
  "evidence_core_available": true,
  "enterprise_context_available": true,
  "company_profile_available": true,
  "timeline_available": true,
  "report_available": true,
  "legacy_database_browser_available": false,
  "legacy_chroma_available": false,
  "legacy_sqlite_available": false,
  "default_page": "dashboard",
  "capability_reasons": {
    "legacy_sqlite_available": "旧 SQLite 数据库未配置或为空",
    "legacy_chroma_available": "旧 Chroma 向量库未配置"
  }
}
```

判断原则：

- `evidence_core_available`：当前 31 条核验证据和证据链配置可加载。
- `enterprise_context_available`：当前证据服务能按企业聚合来源、药物、试验、论文、监管事件。
- `company_profile_available`：企业证据画像 API 可从当前证据服务生成，不依赖旧 SQLite。
- `timeline_available`：source registry 或 evidence chains 具备可解释日期字段。
- `report_available`：本地模板化研报能为每段输出 source_id、URL 和限制说明。
- `legacy_database_browser_available`：旧 SQLite 存在、非空、schema 合格，且允许本地后台访问。
- `legacy_chroma_available`：Chroma 目录存在、collection 可读、metadata 可追溯，且依赖已安装。

这样可以避免“一项旧依赖缺失导致全部旧功能关闭”。

## 10. 部署方案比较

| 方案 | 原创性 | 真实性 | 答辩效果 | Render Free 资源 | 稳定性 | 数据体积 | 维护成本 | 5 天内可实现性 |
|---|---|---|---|---|---|---|---|---|
| A. 所有功能恢复到当前 Render 单体 | 中 | 低到中，因旧 DB/Chroma 缺失 | 容易显得功能多但口径混乱 | 差 | 差 | 高 | 高 | 低 |
| B. Render 部署轻量融合版，重型功能只在本地 | 高 | 高，线上只展示可核验证据 | 好 | 好 | 好 | 低 | 中 | 高 |
| C. 两个独立服务 | 中 | 中 | 中 | 差，需要更多运维 | 中 | 中到高 | 高 | 低 |
| D. 使用新证据数据重构旧页面，不部署旧 Chroma | 高 | 高 | 好 | 好 | 好 | 低 | 中 | 高 |

唯一推荐方案：B 与 D 的组合，即 Render 部署轻量融合版，使用当前核验证据数据重构旧页面；重型 Chroma 和旧 SQLite 浏览仅本地后台保留，不进入比赛主链路。

理由：

- 能保留原网站成熟框架和交互形态。
- 所有线上结论都能回到 `source_id`、URL、证据链和核验日期。
- 不依赖当前缺失的 SQLite/Chroma。
- Render Free 资源可承受。
- 5 天内可以优先完成工作台、企业画像、时间轴和本地研报。

## 11. 推荐实施顺序

1. P0-1：重构决策工作台为“证据工作台”。
   - 复用当前首页布局。
   - 数据来自 `/api/evidence/summary`、`/api/evidence/chain-summary`、`/api/evidence/unresolved-links` 和数据版本。
   - 去掉旧财务事实、宏观事实、排名和固定统计。

2. P0-2：新增企业证据画像。
   - 后端按企业聚合 source registry 和 evidence chains。
   - 前端复用旧公司画像布局，但字段改为药物、试验、论文、监管、证据缺口。

3. P0-3：新增研发事件时间轴。
   - 从 source registry 和 evidence chains 派生事件。
   - 明确标注日期类型和来源。

4. P0-4：新增带引用自动研报。
   - 先做本地模板，不接大模型。
   - 每段都带 source_id 和 URL。

5. P1：把白盒页改为 GroundedQA trace 可视化。

## 12. 阻塞问题

- Day6 第二阶段已完成 P0-1：默认工作台已重构为“研发决策工作台”，使用 `SourceRegistryService`、`EvidenceChainService`、`CompanyEvidenceComparisonService` 和现有 `data_version` 逻辑动态计算。旧空 SQLite 工作台不再作为默认工作台恢复。
- 新增 `/api/evidence/workbench` 和 `runtime-capabilities.evidence_workbench_available`。轻量与完整环境的可靠默认工作台均为真实证据工作台；旧 SQLite/Chroma 功能继续按能力隔离。
- 当前工作台 9 项核心指标实际为：31 条来源、31 条已核验、2 个归一企业主体、10 条试验级证据链、1 条药物级监管链、4 条最新资料、2 条历史版本、25 条独立资料、7 条待确认关系。
- 前端 `today` 页面不再请求旧 `/api/dashboard`，也不再渲染旧固定企业数、年报数、财务事实、宏观指标、排名、趋势、雷达评分或模拟预警。
- Day6 第三阶段已完成 P0-2：主导航“公司画像 · 对比”已替换为“企业证据画像”，新增 `CompanyEvidenceProfileService` 和两个只读 FastAPI 接口。
- 企业画像复用 `SourceRegistryService`、`EvidenceChainService`、`EvidenceWorkbenchService`、`CompanyEvidenceComparisonService` 的企业归一能力和现有 `data_version` 逻辑，没有重写 CSV 筛选、别名、版本或证据链规则。
- 当前实际画像指标：恒瑞医药 15 条来源、6 条试验链、0 条监管链、6 条待确认关系；百济神州 / BeOne Medicines 16 条来源、4 条试验链、1 条监管链、1 条待确认关系。
- B015/B016 只进入药物级监管链；B015 显示正式授权，B016 显示 CHMP 积极意见且非最终批准，B016 不增加 RATIONALE-315 试验证据数量。
- `runtime-capabilities` 新增 `company_evidence_profile_available`，只检查当前本地证据服务，不依赖旧 SQLite 是否为空。
- 旧财务画像模板和代码作为历史内容保留，但从主导航、`loadPage()` 和自动请求中隔离；当前画像页不调用旧 `/api/profile`、`/api/compare` 或 `/api/dashboard`。

- 当前旧 SQLite 是空文件，且被忽略，不在干净克隆和 Render 中。
- 当前旧 Chroma 目录不存在，且被忽略，不在干净克隆和 Render 中。
- 原始年报/研报目录缺失，不能完整重建旧 SQLite/Chroma。
- demo_cache 有旧企业经营样例，但不是当前比赛核验证据，不可直接作为事实主链路。
- 旧自动研报和白盒曾有固定 mock 或硬编码演示内容，必须重构后才可公开展示。

## 13. 预计修改文件

后续实施阶段预计会涉及：

- `webapp/main.py`
- `webapp/frontend_src/component.js`
- `webapp/frontend_src/template.html`
- `webapp/static/index.html`
- `deepinsight/core/evidence_workbench_service.py`
- 已新增 `deepinsight/core/company_evidence_profile_service.py`
- 可能新增 `deepinsight/core/evidence_timeline_service.py`
- 可能新增 `deepinsight/core/evidence_report_service.py`
- 对应测试文件和 Day6 文档

P0-1 工作台阶段已新增 `deepinsight/core/evidence_workbench_service.py`、`tests/test_evidence_workbench_service.py`、`tests/test_evidence_workbench_api.py`、`tests/test_evidence_workbench_frontend.py` 和 `docs/day6_evidence_workbench_validation.md`，并更新 FastAPI、前端源码和构建产物。

P0-2 企业证据画像阶段已新增 `deepinsight/core/company_evidence_profile_service.py`、`tests/test_company_evidence_profile_service.py`、`tests/test_company_evidence_profile_api.py`、`tests/test_company_evidence_profile_frontend.py` 和 `docs/day6_company_evidence_profile_validation.md`。下一步 P0-3 计划新增研发事件时间轴，优先区分证据事件日期、发布日期、核验日期和响应生成时间，不从标题推断缺失事件。

## 14. 验收标准

下一阶段恢复功能必须满足：

- 不使用 MOCK、Faker、random、固定评分或无来源结论。
- 页面默认展示的所有业务数字均来自当前核验证据服务或明确标注为不可用。
- 每个结论可以追溯到 `source_id`、URL、证据链或核验日期。
- 禁止输出疗效排名、成功率、企业综合评分或投资建议。
- 轻量 Render 环境不依赖旧 SQLite、Chroma、sentence-transformers 或 Torch。
- `runtime-capabilities` 能按功能独立标记可用性。
- local 循证问答继续可用，DeepSeek 开关和限流不被绕过。
- 自动测试覆盖能力判断、旧功能隔离、来源引用、无固定结果和前端四页签不回归。
