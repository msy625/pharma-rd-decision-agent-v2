# Day 4 第二阶段：循证问答本地核心服务验证

## 服务范围

本阶段新增本地循证问答核心服务，暂不接 FastAPI，暂不接 DeepSeek，不调用网络，不读取真实 API 密钥，不加载 Chroma 或向量模型。

新增服务：

- `config/grounded_qa_rules.json`
- `deepinsight/core/grounded_qa_service.py`
- `tests/test_grounded_qa_service.py`

服务公开接口：

- `classify_question(question)`
- `check_safety(question)`
- `retrieve_evidence(question, question_type=None)`
- `build_evidence_packet(question, question_type=None)`
- `validate_citations(citations, evidence_packet)`
- `build_local_response(question, evidence_packet)`
- `answer_question(question, llm_client=None, model_name=None)`
- `data_version()`

## 执行流程

严格顺序：

```text
问题文本
→ 空问题检查
→ 安全边界检查
→ 问题分类
→ 调用已有服务检索
→ 构造结构化证据包
→ 生成本地可验证摘要或调用注入的LLM客户端
→ 引用校验
→ 返回结构化结果
```

禁止先让大模型自由回答再补引用。禁止问题不会执行检索，也不会调用注入的 LLM 客户端。

## 问题分类

本阶段使用规则分类，不使用大模型分类。

支持类型：

- `source_search`
- `trial_status`
- `evidence_chain`
- `regulatory_status`
- `company_comparison`
- `evidence_gap`
- `prohibited_or_unsupported`

关键规则：

- NCT 编号使用正则识别。
- RATIONALE-304/307/303/315 可匹配对应证据链。
- B015/B016 进入监管状态类。
- 同时提到恒瑞与百济，并包含比较、差异或对比含义时进入企业样本对比。
- 缺口、证据不足、待确认等问题进入证据缺口类。
- 无法明确分类时进入来源检索。

## 检索与证据包

服务复用已有实现：

- `SourceRegistryService`
- `EvidenceChainService`
- `CompanyEvidenceComparisonService`

不重新读取 CSV，不重新实现证据链或企业对比规则。

证据包包含：

- `sources`
- `related_regulatory_items`
- `all_sources`
- `chains`
- `comparison`
- `evidence_gaps`
- `allowed_source_ids`
- `primary_source_ids`
- `chain_ids`
- `data_version`

`data_version()` 基于以下文件内容哈希生成稳定标识：

- `data/source_registry.csv`
- `config/evidence_chains.json`
- `config/evidence_rules.json`
- `config/grounded_qa_rules.json`

不使用当前时间，不写死版本号，不使用个人绝对路径。

## 引用校验

`validate_citations()` 保证：

- citation 的 `source_id` 必须在本次 `evidence_packet.allowed_source_ids` 中。
- `source_id` 必须能通过 `SourceRegistryService.get_by_source_id()` 找到。
- `source_url` 必须与登记表一致；如输入 URL 错误，则按登记表校正。
- 重复引用去重。
- 无效引用移除并记录到 `limitations`。
- LLM 注入客户端不能新增不存在或未检索到的 `source_id`。

## 无密钥行为

本阶段不读取密钥，也不依赖密钥。

没有 `llm_client` 时：

- `trace.used_llm=false`
- `trace.model_name=local-structured-summary`
- 返回本地结构化证据摘要。
- 没有证据时返回“当前数据不足”。
- `limitations` 说明未调用大模型，仅展示结构化证据。

## 安全拦截修复

浏览器验收发现问题：

- “请根据这些资料告诉一位肺癌患者具体应该选择什么药？”被误判为 `source_search`。
- 系统继续返回“当前数据不足”和本地证据摘要，未明确说明属于禁止回答的个体治疗或用药建议。

修复规则：

- `individual_medication_or_treatment` 增加直接禁止表达，例如“推荐具体药物”“推荐治疗方案”“请为患者制定治疗方案”。
- 新增语义组合规则：个体对象（患者、病人、本人、我、家人、具体病例）同时命中建议意图（应该选择、应该使用、推荐、用药建议、治疗方案、怎么治疗、适合什么药等）时拦截。
- 安全拦截在证据检索前返回，不调用 `retrieve_evidence()`，不调用 LLM。
- 安全结果返回 `safety_category=individual_medication_or_treatment`、空引用、空证据、`source_count=0`、`used_llm=false`、`cache_hit=false`。

二次修复：

- 新增 `safety_category_labels` 统一映射，服务端用户可见文案使用中文安全类别。
- `safety_category` 结构化字段继续保留内部代码，便于 API 和白盒排查。
- 主回答、`limitations` 和 `safety_notice` 不直接显示 snake_case 内部类别代码。
- 安全拦截限制说明固定为两类信息：命中的中文安全类别，以及“未检索证据、未调用语言模型、未生成引用”。
- 安全提示去重为统一边界：“本系统仅提供已核验研发证据的查询、关联和状态说明，不能替代医生判断。”

第三次展示修复：

- `trace.source_count` 保持检索来源总数。
- 证据链问题额外返回 `trial_evidence_count` 和 `related_regulatory_count`。
- RATIONALE-315 返回 `source_count=4`、`trial_evidence_count=3`、`related_regulatory_count=1`；B016 只计入关联监管背景，不计入试验证据数量。
- 非证据链问题不返回无意义的 0 值拆分字段。
- 本地证据缺口使用“当前收录样本中”限定，例如“当前收录样本中包含中期分析论文，尚未收录最终分析论文。”

防误伤规则：

- 不把单独的“治疗方案”“用什么药”作为无条件禁止词。
- 研发证据问题如“RATIONALE-304使用了哪些药物？”、“B003试验组采用什么治疗方案？”、“恒瑞目前有哪些相关药物资料？”和“NCT04619433当前是什么状态？”不进入安全拦截。

## 关键事实验证

已覆盖：

- NCT04619433 返回 `Terminated`。
- B015 返回 EMA/欧盟正式授权。
- B016 返回 CHMP 积极意见，非最终批准。
- RATIONALE-304 返回 B003/B006/B007，其中 B006 为历史版本，B007 为最新版本。
- RATIONALE-315 试验证据为 B011/B012/B013，B016 只作为关联监管背景。
- RATIONALE-315 白盒统计拆分为检索来源总数 4、试验证据数量 3、关联监管背景 1。
- 证据缺口说明使用当前收录样本范围限定，不推断全球范围不存在。
- 企业对比带“当前收录并核验的NSCLC证据样本”限制。
- 不存在试验返回当前数据不足，不返回异常。
- 禁止问题不检索、不调用 LLM。
- 个体治疗或用药建议问题返回 `prohibited_or_unsupported` 和 `individual_medication_or_treatment`。
- 个体诊断建议、个体治疗或用药建议、疗效保证、跨试验疗效排名、成功率预测、投资建议、企业综合排名均有中文类别展示回归。
- 未知安全类别展示为“其他不支持的问题类型”。
- 正常研发证据查询不因“药物”或“治疗方案”字样被误拦截。

## 测试结果

新增测试：

```bash
.venv/bin/python -m unittest tests/test_grounded_qa_service.py
```

结果：

```text
Ran 27 tests
OK
```

收尾验证已运行：

```bash
.venv/bin/python -m json.tool config/grounded_qa_rules.json > /dev/null
.venv/bin/python -m unittest tests/test_evidence_chain_service.py
.venv/bin/python -m unittest tests/test_company_evidence_comparison_service.py
.venv/bin/python scripts/validate_source_registry.py
git diff --check
```

结果：

- `config/grounded_qa_rules.json`：JSON 校验通过。
- `tests/test_grounded_qa_service.py`：27 tests OK。
- `tests/test_evidence_chain_service.py`：18 tests OK。
- `tests/test_company_evidence_comparison_service.py`：17 tests OK。
- `scripts/validate_source_registry.py`：31 sources，H001-H015 和 B001-B016 complete。
- `git diff --check`：通过。
