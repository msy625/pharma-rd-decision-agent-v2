# Day6 第三阶段：企业证据画像验证报告

日期：2026-07-23
分支：`feature/day6-legacy-integration`
起点提交：`70d7b14 feat: add verified evidence workbench`

## 1. 阶段结论

原主导航“公司画像 · 对比”已重构为“企业证据画像”。新页面只展示当前人工核验的 NSCLC 证据样本，不恢复旧财务画像、雷达评分、风险分、企业排名、winner 或投资建议逻辑。

本阶段未修改 `data/source_registry.csv` 或 `config` 事实数据，未部署 Render，未合并 `main`，未读取 `.env`，未调用 DeepSeek，未访问网络。

## 2. 为什么不恢复旧财务画像

旧画像依赖 `data/enterprise_analysis.db`、旧财务表、专利/风险字段和评分工具。Day6 审计确认当前 SQLite 为空，旧 Chroma 不在可部署资产中，固定财务值、雷达评分和 winner 口径无法由当前比赛证据证明。

因此本阶段保留旧历史代码，但将其从主导航、`loadPage()` 和自动请求中隔离。新画像不调用 `/api/profile`、`/api/compare` 或 `/api/dashboard`；双企业证据对比继续保留在“研发证据查询—企业对比”内部页签。

## 3. 数据来源与复用关系

`CompanyEvidenceProfileService` 只组合现有本地服务：

- `SourceRegistryService`：企业来源查询、真实 `source_type`、核验状态和来源字段。
- `EvidenceChainService`：试验级证据链、药物级监管链、版本关系和待确认关系。
- `EvidenceWorkbenchService`：数据范围、核验日期、响应生成时间和现有 `data_version`。
- `CompanyEvidenceComparisonService`：企业别名归一。

服务不访问数据库、模型、向量库、环境密钥或网络。

## 4. 企业归一

当前返回两个归一主体：

1. `恒瑞医药`，别名包括江苏恒瑞医药股份有限公司和英文名称。
2. `百济神州`，展示名称为“百济神州 / BeOne Medicines”；`百济神州`、`BeOne Medicines`、`BeiGene` 和当前登记的中英文组合名称归一为同一主体。

不存在企业返回 HTTP 200 和空画像，限制说明包含“当前数据不足”，不返回 500。

## 5. 指标与证据链计算规则

- `source_count`：按归一企业查询当前来源登记表的记录数。
- `verified_source_count`：只统计 `verification_status=已人工核验`。
- `trial_chain_count`：只统计 `chain_type=trial`，论文、登记和公司页面在同一链内不重复算作多项试验。
- `regulatory_chain_count`：只统计 `chain_type=regulatory`，不计入试验链数量。
- 单来源/多来源试验链：按试验链的 `source_count` 动态分类。
- 论文和试验登记来源：分别依据真实 `source_type=PubMed` 与 `source_type=ClinicalTrials.gov` 统计，不根据标题推测。
- 最新/历史/独立资料：复用 `EvidenceChainService.version_status()` 对 `is_latest_evidence` 的三态解释。
- 待确认关系：复用 `evidence_chains.json` 的 `unresolved_links`，按来源所属企业过滤。
- `latest_verified_at`：取当前企业来源的真实最大核验日期。
- `generated_at`：响应生成时间，不解释为证据事件日期。

当前实际指标：

| 企业 | 来源 | 已核验 | 试验链 | 监管链 | 多来源试验链 | 单来源试验链 | PubMed | ClinicalTrials.gov | 最新/历史/独立 | 待确认 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | ---: |
| 恒瑞医药 | 15 | 15 | 6 | 0 | 0 | 6 | 5 | 5 | 0 / 0 / 15 | 6 |
| 百济神州 / BeOne Medicines | 16 | 16 | 4 | 1 | 4 | 0 | 6 | 4 | 4 / 2 / 10 | 1 |

## 6. B015/B016 口径

- B015：EMA 当前授权页面，画像显示“正式授权”。
- B016：CHMP 积极意见，画像明确“非最终批准”。
- B015/B016 共同组成 `regulatory:tevimbra-eu-nsclc` 药物级监管链。
- 该监管链可显示 `NCT04379635` 作为关联试验背景，但不计入试验链数量。
- B016 不进入 RATIONALE-315 试验链的 `source_ids`，不增加该试验证据数量。

## 7. API

新增：

- `GET /api/evidence/company-profile/{name}`
- `GET /api/evidence/company-profile-companies`

单企业响应包含 `profile` 和顶层 `metadata.data_scope`；画像内部包含企业信息、摘要、试验链、监管链、独立资料、三类分布、待确认关系、数据元信息和限制说明。

错误行为：中文、英文和空格路径正常；不存在企业返回 200；文件缺失和结构错误返回脱敏 503；未知异常返回脱敏 500，不暴露路径、堆栈或密钥。

`/api/runtime-capabilities` 新增 `company_evidence_profile_available`。该能力只依赖当前 CSV/JSON 证据服务，不因空 SQLite 而关闭。

## 8. 前端结构

企业证据画像页面包括：

- 醒目范围提示和企业选择器。
- 企业名称、归一主体和别名。
- 12 项动态核心指标。
- 来源类型和研究状态构成。
- 试验证据链卡片及“查看证据链”跳转。
- 药物级监管链及 B015/B016 状态说明。
- 独立资料和待确认关系列表。
- 数据版本、核验日期、生成时间和限制说明。
- “查看全部来源”“打开企业对比”“进入循证问答”快捷入口。

恒瑞没有独立监管链时显示“当前样本未收录独立监管链；该表述不代表企业没有监管进展”。空值统一通过安全文本函数显示“暂无”，不显示 `undefined` 或 `null`。

## 9. 浏览器人工验收

企业证据画像已完成本地浏览器人工验收，结果如下：

- 主导航显示“企业证据画像”，默认加载恒瑞医药。
- 可正常切换“百济神州 / BeOne Medicines”，两家企业指标与当前事实数据一致。
- B015 显示“正式授权”；B016 显示“CHMP 积极意见，非最终批准”。
- 试验链、监管链、独立资料和待确认关系展示正确；恒瑞无监管链时使用谨慎的样本范围表述。
- “查看证据链”可跳转到证据链页签并加载对应 `chain_id`。
- “查看全部来源”“打开企业对比”“进入循证问答”三个入口均正常。
- Network 仅请求新的 company-profile 接口，未请求旧 `/api/profile`、`/api/compare`、`/api/dashboard`。
- Console 无错误，窄屏响应式布局正常。

该结论是 Day6 本地浏览器验收结果，不代表 Render 线上部署验收。

## 10. 自动验证

按本阶段清单执行的最终结果：

| 命令 | 结果 |
| --- | --- |
| `.venv/bin/python webapp/frontend_src/build.py` | 通过，生成 `webapp/static/index.html` |
| `node --check webapp/frontend_src/component.js` | 通过 |
| `node --check webapp/static/dc-runtime.js` | 通过 |
| 企业画像服务、API、前端 3 个测试模块 | 36 项通过 |
| 研发工作台服务、API、前端 3 个测试模块 | 22 项通过 |
| 证据链服务、API、前端 3 个测试模块 | 64 项通过 |
| 企业对比、共享前端、离线资源、旧功能降级和 runtime capabilities 7 个测试模块 | 113 项通过 |
| `.venv/bin/python scripts/validate_source_registry.py` | 通过，31 条来源完整 |
| `git diff --check` | 通过 |

本阶段共执行 16 个 unittest 模块，235 项测试全部通过。

## 11. 范围限制

- 当前画像不是企业完整研发管线。
- 当前缺少统一的 `project_id`、`target`、`mechanism` 和 `drug_type`。
- 不从 `drug_name` 字符串推断项目数量。
- 来源数量不能解释为企业研发实力。
- 不输出评分、排名、领先、成功率、疗效或安全性优劣、投资建议。
- “当前样本未收录”不等同于企业没有相关试验、论文或监管进展。

## 12. 下一步计划

下一阶段计划实现“研发事件时间轴”：复用来源登记表和证据链，明确区分证据事件日期、发布日期、核验日期和响应生成时间；不从标题推断缺失事件，不把 B016 的 CHMP 积极意见写成最终批准。
