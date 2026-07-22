# Day 4 第三阶段：循证问答 FastAPI 接入验证

## 新增接口

本阶段将 `GroundedQAService` 接入 FastAPI，只启用本地循证模式，不接入 DeepSeek，不创建 LLM 客户端，不访问网络。

新增接口：

- `GET /api/evidence/grounded-qa/capabilities`
- `POST /api/evidence/grounded-qa`

`capabilities` 路由放在其他 `/api/evidence/...` 动态参数路由之前，避免静态路径被误匹配。

## 请求结构

```json
{
  "question": "RATIONALE-304有哪些证据版本？",
  "generation_mode": "auto"
}
```

`generation_mode` 支持：

- `auto`：为后续 LLM 接入预留；当前没有 LLM 客户端，因此自动使用本地结构化摘要。
- `local`：强制使用本地结构化摘要。

本阶段两种模式都不会访问网络或调用 DeepSeek。

## 响应结构

```json
{
  "result": {
    "question": "",
    "question_type": "",
    "answer": "",
    "citations": [],
    "evidence_used": [],
    "safety_category": "",
    "limitations": [],
    "safety_notice": "",
    "trace": {}
  },
  "metadata": {
    "data_scope": "first_version_nsclc_hengrui_beone",
    "generation_mode_requested": "",
    "generation_mode_used": "local",
    "llm_used": false,
    "fallback_used": false,
    "model_name": "local-structured-summary"
  }
}
```

## API层边界

API 层只负责：

- 请求字段校验。
- 调用 `GroundedQAService.answer_question()`。
- 包装 `metadata`。
- 将数据/配置异常映射为友好 HTTP 错误。

API 层不做：

- 不重新分类问题。
- 不重新检索 CSV。
- 不生成答案。
- 不创建 DeepSeek 客户端。
- 不访问 Chroma、SQLite 或向量模型。
- 不读取或输出 API 密钥。

## 错误处理

- `question` 缺失或空白：400。
- `question` 超过 1000 字符：400。
- `generation_mode` 非法：400。
- 禁止问题：200，返回 `prohibited_or_unsupported` 和安全说明，不检索、不调用 LLM。
- 安全拦截问题：`metadata.generation_mode_used=safety_block`、`llm_used=false`、`fallback_used=false`，本次实际 `model_name` 为空或 `safe-policy`，不使用 capabilities 中的配置模型冒充实际调用模型。
- API 用户可见文案使用中文安全类别；内部 `safety_category` 字段保留机器代码，但 `answer`、`limitations` 和 `safety_notice` 不直接显示 snake_case。
- 没有证据：200，回答“当前数据不足”。
- 没有 API 密钥：本地模式正常返回，不返回 500。
- 数据或配置文件缺失：503。
- JSON/CSV 结构异常：503。
- 未知异常：友好 500，不暴露绝对路径、堆栈或密钥。

## Capabilities

`GET /api/evidence/grounded-qa/capabilities` 返回：

- `local_mode_available=true`
- `llm_mode_available=false`
- `supported_question_types`
- `prohibited_categories`
- `data_version`
- `requires_api_key_for_llm=true`
- `description=本地循证模式可用，DeepSeek尚未启用。`

## 关键问题验证

已通过 API 覆盖：

- RATIONALE-304 返回 B003/B006/B007，B006 为历史版本，B007 为最新版本。
- RATIONALE-315 返回 B011/B012/B013，B016 只作为关联监管背景。
- RATIONALE-315 trace 返回 `source_count=4`、`trial_evidence_count=3`、`related_regulatory_count=1`，B016 不进入试验证据数量。
- NCT04619433 返回 `Terminated`。
- B015 为 EMA/欧盟正式授权。
- B016 为 CHMP 积极意见，非最终批准。
- 企业对比包含“当前收录并核验的NSCLC证据样本”限制。
- 证据缺口返回 H008、H009、H010、H011、H012、H014 等待确认关系。
- SHR-1210 别名查询有效。
- 不存在试验返回“当前数据不足”。
- 个体治疗建议问题返回 `safety_category=individual_medication_or_treatment`。
- 禁止问题不返回引用、证据、检索来源或证据链，`source_count=0`。
- 禁止问题的 API metadata 返回 `generation_mode_used=safety_block`，不显示 `deepseek-v4-flash` 为本次实际模型。
- 禁止问题的用户可见文案显示中文类别，例如“个体治疗或用药建议”，并说明未检索证据、未调用语言模型、未生成引用。
- 主回答、限制说明和安全提示分区去重，不重复完整相同句子。
- 证据链缺口表述包含“当前收录样本中”，不把未收录写成全球不存在。

## 测试结果

新增 API 测试：

```bash
.venv/bin/python -m unittest tests/test_grounded_qa_api.py
```

结果：

```text
Ran 29 tests
OK
```

完整收尾验证已执行：

- `tests/test_grounded_qa_service.py`：23 tests OK。
- `tests/test_grounded_qa_api.py`：29 tests OK。
- `tests/test_evidence_api.py`：18 tests OK。
- `tests/test_evidence_chain_api.py`：21 tests OK。
- `tests/test_company_evidence_comparison_api.py`：18 tests OK。
- `scripts/validate_source_registry.py`：31 sources，H001-H015 和 B001-B016 complete。
- `git diff --check`：通过。

## 后续接入DeepSeek前提

可以开始下一阶段 DeepSeek 接入，但应保持：

- 检索先于生成。
- `GroundedQAService` 继续负责证据包和引用校验。
- LLM 客户端通过注入方式传入，不在 API 层自由创建。
- 模型输出的引用必须通过 `validate_citations()`。
