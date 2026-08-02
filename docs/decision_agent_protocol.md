# 药研罗盘轻量级研发决策 Agent 协议

## 目标

研发决策 Agent 面向比赛演示的闭环：

用户提出研发决策问题 -> 识别任务与实体 -> 生成工具计划 -> 调用本地证据服务 -> 汇总来源和证据链 -> 输出决策结论、风险、证据缺口、引用和执行轨迹。

本阶段是后端 MVP。它不引入 LangGraph、多 Agent 框架、新向量模型、新 LLM SDK，不依赖互联网、`.env` 或旧 SQLite demo 表。

## 任务类型

- `company_comparison`：企业研发证据样本比较。
- `evidence_gap`：研究或试验证据缺口分析。
- `regulatory_status`：监管状态辨析。
- `trial_status`：试验状态说明。
- `evidence_chain`：证据链说明。
- `source_search`：来源、药物、研究、来源编号检索。
- `prohibited_or_unsupported`：医疗个体建议、投资建议、疗效保证等安全拒答。

## 工具映射

- `company_comparison`
  - `CompanyEvidenceComparisonService.compare`
  - `CompanyEvidenceProfileService.build_profile`
  - 不默认调用 `RDEventTimelineService`；只有问题明确要求时间顺序时才应扩展。

- `evidence_gap`
  - `EvidenceChainService.get_trial_chain/list_chains`
  - `SourceRegistryService.get_by_source_id`

- `regulatory_status`
  - `GroundedQAService.answer_question`
  - `EvidenceChainService.get_drug_regulatory_chain/get_chain`

- `trial_status` / `evidence_chain`
  - `GroundedQAService.answer_question`
  - `EvidenceChainService.get_trial_chain/list_chains`

- `source_search`
  - `GroundedQAService.answer_question`

- `prohibited_or_unsupported`
  - `GroundedQAService.check_safety`
  - 不继续调用企业比较、时间轴、证据链等业务工具。

## 返回协议

`RDDecisionAgentService.run(question, generation_mode)` 返回固定 JSON 字典，核心字段：

- `question`：原始问题。
- `intent`：任务类型。
- `entities`：企业、药物、研究名、NCT编号、来源编号。
- `plan`：基于 intent 生成的结构化计划。
- `steps`：真实执行轨迹，不展示隐藏推理。
- `decision.summary`：直接回答。
- `decision.key_findings`：核心发现。
- `decision.comparison_dimensions`：企业比较维度。
- `decision.risk_flags`：风险和边界。
- `decision.evidence_gaps`：证据缺口。
- `decision.next_evidence_actions`：下一步核验资料。
- `decision.supported_conclusions`：当前样本可支持的结论类型。
- `decision.unsupported_conclusions`：当前样本不能支持的结论类型。
- `decision.evidence_maturity`：仅描述当前样本的来源构成、链条构成、版本构成、监管覆盖和可追溯性风险，不评价企业实力。
- `decision.scope_statement`：当前数据范围。
- `answer`：可读文本答案，由 `decision` 结构确定性生成。
- `citations`：完整真实 Source Registry 来源卡片，包含 `produced_by_steps`。
- `featured_citations`：确定性筛选的代表性来源卡片，供前端默认展示。
- `source_ids` / `chain_ids`：本次用到的来源和证据链。
- `source_trace`：来源编号到完成步骤编号的映射。
- `limitations` / `warnings`：限制和降级信息。
- `refused` / `safety_category`：安全拒答结果。
- `generation_mode` / `used_llm` / `execution_metadata`：生成模式、模型使用状态和执行元数据。
- `data_version` / `latency_ms` / `error`：版本、真实延迟和错误。

`steps` 字段只包含：

- `step_id`
- `name`
- `tool`
- `status`
- `reason`
- `input_summary`
- `result_summary`
- `source_ids`
- `duration_ms`

`source_ids` 只记录该步骤真实工具返回值中可提取的来源编号。最终 `citations[*].produced_by_steps` 必须引用至少一个 `completed` 步骤，且该步骤的 `source_ids` 中包含对应来源。

## 三条黄金演示路径

### A. 企业研发证据比较

示例：

- 阿斯利康与百济神州当前 NSCLC 证据样本有什么差异？
- 恒瑞医药和阿斯利康在 NSCLC 领域如何比较？

流程：

1. 安全检查。
2. 提取两个企业。
3. 调用企业比较服务。
4. 调用两家企业画像服务补充资料构成和待确认关系。
5. 输出样本范围、来源类型、试验链、监管链、待确认关系、限制和下一步核验。

边界：

来源数量和链数量只能描述当前样本覆盖，不得推断企业研发实力、优胜方、成功率或投资价值。

### B. 证据缺口分析

示例：

- RATIONALE-315 当前还存在哪些证据缺口？
- LAURA 当前证据链还缺少什么？

流程：

1. 安全检查。
2. 提取研究名或 NCT 编号。
3. 定位证据链。
4. 核验主证据来源和关联监管背景来源。
5. 单独展示关联监管背景，并明确不计入试验主证据数量。

边界：

缺口仅限当前收录样本，不等同于外部世界不存在相关证据。

### C. 监管状态辨析

示例：

- B016 是否代表替雷利珠单抗已经获得 EMA 正式批准？
- B015 和 B016 分别表示什么监管状态？

流程：

1. 安全检查。
2. 提取来源编号、药物或监管实体。
3. 调用 Grounded QA 生成监管状态本地答案。
4. 调用监管证据链，区分 CHMP 积极意见、EMA/EPAR 正式授权、历史状态和当前状态。

边界：

不得把 CHMP 积极意见写成欧盟委员会最终批准；不得用 B016 替代当前 EPAR 状态。

## 安全边界

以下问题必须拒答或限制：

- 个体诊断、用药、治疗方案推荐。
- 疗效保证。
- 跨试验疗效排名。
- 项目成功率、上市概率。
- 投资建议、企业实力排名。

安全拒答不执行业务工具，只返回拒答原因、适用范围和可改写方向。

## 当前数据范围

当前分析仅限本地 Source Registry 和 Evidence Chains 中已核验 NSCLC 样本，覆盖恒瑞医药、百济神州、阿斯利康三家公司及已登记来源。结果不代表完整研发管线、外部证据总量或实时监管数据库。

## 与普通检索和问答的区别

- 关键词检索只做文本包含匹配，不理解任务和证据链。
- 结构化检索只按字段返回来源，不综合决策结论。
- Grounded QA 负责本地循证问答和引用校验。
- 决策 Agent 在 Grounded QA 之外，还会按任务选择企业比较、企业画像、证据链和来源核验工具，输出可展示的计划、步骤、决策结构和证据卡片。

## 不展示隐藏推理

Agent 不返回 chain-of-thought。前端只展示真实工具轨迹：任务、工具、输入摘要、结果摘要、来源编号、耗时和状态。
