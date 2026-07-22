# Day 4 第五阶段：循证问答 Web 页面验证

## 页面位置

循证问答已接入“研发证据查询”内部第四个页签：

- 来源检索
- 证据链
- 企业对比
- 循证问答

本阶段未新增侧边栏主导航，未修改旧“智能问答”和旧“白盒溯源”页面。

## 能力加载

进入“循证问答”页签时调用：

```text
GET /api/evidence/grounded-qa/capabilities
```

页面展示：

- 本地循证模式是否可用。
- DeepSeek 是否可用。
- 当前模型名称。
- 数据版本。
- 支持的问题类型。

前端不读取、保存或显示任何密钥值。

## 交互规则

生成模式：

- DeepSeek 可用时默认 `auto`。
- DeepSeek 不可用时默认 `local`，并提示使用本地证据摘要。
- 页面说明 `auto` 失败时会自动回退本地摘要。

问题输入：

- 最多 1000 字符。
- 显示当前字符数。
- 空问题不能提交。
- 提交期间禁用按钮，防止重复请求。
- 支持点击按钮提交。
- 支持 Ctrl+Enter 提交。

示例问题共 6 个，点击只填入输入框，不自动提交：

- RATIONALE-304有哪些证据版本？
- RATIONALE-315形成了怎样的证据链？
- NCT04619433当前是什么状态？
- B015和B016有什么区别？
- 恒瑞与百济当前证据样本有什么差异？
- 当前数据还存在哪些缺口？

## API边界

提交问答只调用：

```text
POST /api/evidence/grounded-qa
```

不调用旧接口：

- `/api/chat`
- `/api/whitebox`
- `/api/workflow`
- `/api/advanced`

提交使用请求序号和 `AbortController`，避免前一次请求覆盖后一次问题结果。页面刷新不会自动发起 POST。

## 展示结构

结果区展示：

- 回答：纯文本绑定，保留换行，不使用 HTML 解析模型输出。
- 状态标签：问题类型、实际执行方式、回退提示、模型名称。
- 引用资料：`source_id`、`title`、`source_type`、`verified_at`、`support_summary` 和原始来源链接。
- 限制说明：仅在存在 `limitations` 时展示。
- 安全提示：展示 `safety_notice`，禁止问题不会伪装成正常回答。
- 白盒过程：折叠展示检索服务、来源ID、证据链ID、检索来源总数、可用时展示试验证据数量和关联监管背景、执行方式、安全类别、数据版本、生成时间、模型名称、是否使用 DeepSeek、是否命中缓存。

来源数量拆分：

- `source_count` → 检索来源总数。
- `trial_evidence_count` → 试验证据数量。
- `related_regulatory_count` → 关联监管背景。
- 非证据链问题不显示无意义的 0 值拆分。

执行方式展示规则：

- `used_llm=true`：显示实际 DeepSeek 模型。
- `used_llm=false` 且 `generation_mode_used=local`：显示本地循证摘要。
- `generation_mode_used=safety_block`：显示“安全规则拦截”和“未调用模型”，不显示 DeepSeek V4 Flash 为本次实际模型。
- `fallback_used=true`：显示“DeepSeek暂不可用，已回退本地证据摘要”。

引用展示规则：

- 普通无引用结果显示“当前回答没有可展示引用”。
- 安全拦截结果显示“当前回答不需要引用”。

外链只接受 http/https，使用 `target="_blank"` 和 `rel="noopener noreferrer"`。

trace 中存在 `chain_id` 时提供“查看证据链”，点击后切换到证据链页签并调用现有 `loadChainDetail()`；`chain_id` 继续通过 `encodeURIComponent` 编码。

## 展示层中文化

本阶段追加了前端展示映射，避免普通结果区直接暴露技术字段。API 原始字段、事实数据、证据关系和 `source_id`/`source_url` 均不改变。

角色映射：

- `trial_registry` → 临床试验登记
- `interim_publication` → 中期分析论文
- `final_publication` → 最终分析论文
- `company_document` → 企业官方资料
- `regulatory_authorisation` → EMA正式授权信息
- `regulatory_opinion` → CHMP积极意见
- `independent_evidence` → 独立证据资料
- 未知角色 → 其他证据资料

模型名称映射：

- `local-structured-summary` → 本地循证摘要
- `deepseek-v4-flash` → DeepSeek V4 Flash
- `safe-policy` → 未调用模型
- 其他模型名做空格化友好显示

安全类别映射：

- `individual_diagnosis` → 个体诊断建议
- `individual_medication_or_treatment` → 个体治疗或用药建议
- `efficacy_guarantee` → 疗效保证
- `cross_trial_efficacy_ranking` → 跨试验疗效排名
- `success_probability_prediction` → 成功率预测
- `investment_advice` → 投资建议
- `company_overall_ranking` → 企业综合排名
- 未知类别 → 其他不支持的问题类型

前端只对 `trace.safety_category` 字段做兜底映射，不对任意回答或限制文本做全局替换。

白盒服务名和执行方式映射：

- `EvidenceChainService` → 证据链服务
- `SourceRegistryService` → 来源登记服务
- `CompanyEvidenceComparisonService` → 企业证据对比服务
- `GroundedQAService` → 循证问答服务
- `llm` → DeepSeek智能生成
- `local` → 本地循证摘要
- `safety_block` → 安全规则拦截

前端在白盒过程中展示中文主标签，并在括号内保留内部标识。

研究状态映射：

- `Completed` → 已完成（Completed）
- `Terminated` → 已终止（Terminated）
- `Active, not recruiting` → 活跃、停止招募（Active, not recruiting）
- `Recruiting` → 招募中（Recruiting）
- `Not yet recruiting` → 尚未招募（Not yet recruiting）
- `Unknown`、空值、`N/A`、不适用 → 暂无明确状态

本地摘要和引用支持摘要中的 `study_status=...` 会显示为“研究状态：...”。引用支持摘要中的原始状态值也会中文化，例如 `Active, not recruiting` 显示为“活跃、停止招募（Active, not recruiting）”。白盒过程保留原始 `model_name`，标签为“内部模型标识”。

## 安全边界

页面固定展示：

```text
系统仅根据当前已核验的NSCLC证据样本回答，不提供诊断、个体治疗建议、疗效保证、跨试验排名、成功率预测或投资建议。
```

页面不提供固定回答、前端模拟结果、MOCK、随机评分或无来源结论。

## 安全拦截验收发现

浏览器验收发现个体治疗建议问题曾被展示为来源检索结果，并同时显示本地摘要和 DeepSeek V4 Flash。修复后页面只根据单次回答 metadata/trace 展示实际执行情况，不再使用 capabilities 中的配置模型冒充本次模型。

当前安全拦截结果显示：

- 问题类型：安全边界。
- 执行方式：安全规则拦截。
- 模型：未调用模型。
- 回答：明确说明不能提供个体治疗或用药建议。
- 限制说明：使用中文安全类别，并说明未检索证据、未调用语言模型、未生成引用。
- 引用区域：当前回答不需要引用。
- 安全提示：统一显示“本系统仅提供已核验研发证据的查询、关联和状态说明，不能替代医生判断。”

## 测试结果

本阶段执行：

```bash
.venv/bin/python webapp/frontend_src/build.py
node --check webapp/frontend_src/component.js
.venv/bin/python -m unittest tests/test_grounded_qa_frontend.py
.venv/bin/python -m unittest tests/test_evidence_frontend.py
.venv/bin/python -m unittest tests/test_evidence_chain_frontend.py
.venv/bin/python -m unittest tests/test_company_evidence_comparison_frontend.py
.venv/bin/python -m unittest tests/test_grounded_qa_api.py
```

结果：

- 构建成功，`webapp/static/index.html` 已由源码生成。
- `node --check` 通过。
- `tests/test_grounded_qa_frontend.py`：37 tests OK。
- `tests/test_evidence_frontend.py`：24 tests OK。
- `tests/test_evidence_chain_frontend.py`：25 tests OK。
- `tests/test_company_evidence_comparison_frontend.py`：23 tests OK。
- `tests/test_grounded_qa_api.py`：28 tests OK。

自动测试未调用真实 DeepSeek，未读取 `.env`，未访问网络。
