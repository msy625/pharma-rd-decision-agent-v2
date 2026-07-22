# Day 4 第一阶段：循证问答架构审计

## 1. 当前大模型链路

本阶段只做代码审计，未调用外部网络、DeepSeek 或其他大模型 API，未读取或回显任何真实密钥值。

检查范围包括：

- `webapp/main.py`
- `deepinsight/core/retriever.py`
- `deepinsight/core/agent_tools.py`
- `deepinsight/apps/app_system.py`
- `deepinsight/apps/app_whitebox.py`
- `deepinsight/apps/workflow_report.py`
- `deepinsight/demo/demo_cache.py`
- `deepinsight/core/cache_tools.py`
- `deepinsight/config.py`
- `requirements.txt`
- `README.md`
- `.gitignore`
- `deploy/README.md`
- `deploy/env/webapp.env.example`
- `config/`
- `docs/`
- `tests/`
- `webapp/frontend_src/component.js`
- `webapp/static/index.html`

现有 DeepSeek 客户端有三类创建方式：

1. `deepinsight/core/retriever.py`
   - `DeepSeekClient` 读取 `DEEPSEEK_API_KEY`、`DEEPSEEK_MODEL`、`DEEPSEEK_BASE_URL`。
   - `create_optional_client()` 在没有 `DEEPSEEK_API_KEY` 时返回 `None`。
   - `/api/chat`、`/api/workflow`、`/api/batch-workflow`、`/api/advanced` 会在请求处理时调用 `create_optional_client()`。
2. `deepinsight/apps/workflow_report.py`、`deepinsight/apps/app_whitebox.py`、`deepinsight/apps/app_system.py`
   - 使用 `openai.OpenAI(api_key=..., base_url="https://api.deepseek.com")`。
   - 这些路径通过 OpenAI 兼容 SDK 调用 DeepSeek。
3. `deepinsight/apps/app_system.py`
   - `get_openai_client()` 使用 `st.cache_resource` 缓存客户端。
   - `call_openai_deepseek()` 用于多角色分析和白盒 Reasoner 示例。

当前配置位置：

- `deploy/env/webapp.env.example` 声明 `DEEPSEEK_API_KEY`、`DEEPSEEK_MODEL`、`DEEPSEEK_BASE_URL`。
- `.gitignore` 忽略 `deploy/env/webapp.env`，只保留 example。
- `deploy/README.md` 说明 `DEEPSEEK_API_KEY` 可选，未配置时进入本地降级模式。
- `requirements.txt` 包含 `openai` 和 `requests`，支持 OpenAI 兼容接口与手写 HTTP 请求两种调用方式。

模块导入时没有直接创建 DeepSeek 客户端；但不同入口在页面或请求启动后行为不同：

- FastAPI `/api/bootstrap` 会调用 `create_optional_client()` 判断 `deepseek_enabled`，没有密钥时返回 `False`，不抛错。
- FastAPI `/api/chat`、`/api/workflow`、`/api/batch-workflow`、`/api/advanced` 在请求时创建可选客户端。
- Streamlit `app_system.py` 在用户触发聊天、研报、图谱或白盒按钮时尝试创建客户端；无密钥时多数路径降级为 `client=None`，多角色和 Reasoner 示例会显示调用失败。
- `/api/whitebox` 不创建客户端，只返回静态演示 SQL、RAG chunk、reasoning 和答案。

现有 `/api/chat` 当前读取：

- SQLite：`data/enterprise_analysis.db`，路径来自 `deepinsight/config.py` 的 `DB_PATH`。
- Chroma：`data/chroma`，路径来自 `CHROMA_DIR`。
- 宏观数据表、财务事实表、年报文档表等旧企业经营分析表。

现有 `/api/chat` 不读取 `data/source_registry.csv`，不调用 `SourceRegistryService`、`EvidenceChainService` 或 `CompanyEvidenceComparisonService`，因此当前问答不能保证每个结论都有真实 `source_id` 和 `source_url`。

当前前端调用关系：

- “智能问答”调用 `POST /api/chat`。
- “自动化研报”调用 `POST /api/workflow` 或 `POST /api/batch-workflow`。
- “高级分析”调用 `POST /api/advanced`。
- “白盒溯源”调用 `GET /api/whitebox`。
- “研发证据查询”调用 `/api/evidence/*` 系列接口，不调用旧 chat/workflow/advanced。

## 2. 可复用部分

可以安全复用：

- `SourceRegistryService`：CSV 查询、别名扩展、来源字段规范化、`source_id` 查询。
- `EvidenceChainService`：证据链、监管链、待确认关系、`chain_id` 与 `source_id` 组合。
- `CompanyEvidenceComparisonService`：企业当前核验样本对比、指标定义、禁止解释规则。
- `webapp/main.py` 中现有 `/api/evidence/*` 的错误处理和只读响应模式。
- `deepinsight/core/retriever.py` 的 `create_optional_client()` 思路：无密钥返回 `None`，避免 500。
- 前端“研发证据查询”页面的入口和接口隔离方式。

## 3. 需要隔离部分

应与新的循证问答隔离：

- `/api/chat`、`answer_query()`：耦合 SQLite、Chroma、SQL 生成、RAG、旧企业经营分析和投资研判提示。
- `retrieve_chunks()`：会创建 Chroma client，第四天初版不应依赖。
- `SemanticCache`：导入 `chromadb`，首次查询会加载 `sentence-transformers` 模型。
- `demo_cache/*.json` 与 `deepinsight/demo/demo_cache.py`：面向旧企业经营演示缓存，不具备新证据引用校验字段。
- `/api/whitebox` 当前静态演示内容：可复用“trace 展示形态”，不能复用为真实循证问答结果。
- `deepinsight/experiments/mock_llm.py` 等实验代码：不在主链路，但不得接入循证问答。
- 前端 `answerFor()`、`reportFor()`、`whiteboxVals()` 中的固定展示兜底内容：不得作为新问答真实结果。

## 4. 安全和密钥风险

风险结论：

- 配置文件只暴露环境变量名称，未发现 example 中写入密钥值。
- 当前 `DeepSeekClient` 使用 `requests` 手写 `Authorization` header；日志层未发现主动打印密钥。
- `DEEPSEEK_BASE_URL` 在 `retriever.py` 默认值是 `https://api.deepseek.com/chat/completions`，而 OpenAI SDK 路径使用 `https://api.deepseek.com`。新服务建议统一使用 OpenAI 兼容 SDK，减少 base_url 口径差异。
- 无 API 密钥时，旧 FastAPI chat/workflow/advanced 可降级，不应返回 500；但若有密钥且外部调用失败，当前接口可能抛异常并返回 500。
- 新循证问答必须把“无密钥”和“模型调用失败”都转为结构化降级响应，不能伪造 LLM 答案。

## 5. 新循证问答调用流程

建议新增独立服务和独立 API，不直接改写旧 `/api/chat`：

```text
用户问题
→ 安全边界判断
→ 问题类型分类
→ 从 SourceRegistryService / EvidenceChainService / CompanyEvidenceComparisonService 检索
→ 形成结构化证据包
→ 如有 API 密钥，调用 DeepSeek 只做答案组织
→ 校验模型输出引用的 source_id
→ 返回 answer、citations、evidence_used、limitations、safety_notice、trace
```

建议新增：

- 服务：`deepinsight/core/grounded_qa_service.py`
- 可选缓存：`deepinsight/core/grounded_qa_cache.py`
- API：`POST /api/evidence/grounded-qa`
- 请求体：`question`、可选 `company`、`drug`、`trial_id`、`top_k`、`use_cache`

## 6. 问题分类

初版至少支持：

- `source_search`：查找资料来源、source_id、论文、登记号、监管页面。
- `trial_status`：回答试验登记状态、研究状态、是否 Terminated 等。
- `evidence_chain`：解释同一试验证据链、历史版本、独立资料和监管背景。
- `regulatory_status`：解释正式授权、积极意见、监管事件类型。
- `company_comparison`：比较恒瑞医药与百济神州/BeOne Medicines 当前已核验 NSCLC 样本。
- `evidence_gap`：回答当前缺哪些证据、哪些关系待确认。
- `prohibited_or_unsupported`：拦截诊断、个体治疗建议、疗效保证、跨试验疗效排名、成功率预测、投资建议，或当前样本无法支持的问题。

分类可先用规则实现，避免第四天初版把分类依赖大模型。

## 7. 响应结构

最小响应结构：

```json
{
  "question": "",
  "question_type": "source_search",
  "answer": "",
  "citations": [
    {
      "source_id": "",
      "title": "",
      "source_url": "",
      "source_type": "",
      "verified_at": "",
      "support_summary": ""
    }
  ],
  "evidence_used": [],
  "limitations": [],
  "safety_notice": "",
  "trace": {
    "retrieval_service": "",
    "retrieved_source_ids": [],
    "retrieved_chain_ids": [],
    "source_count": 0,
    "data_version": "",
    "generated_at": "",
    "model_name": "",
    "used_llm": false,
    "cache_hit": false
  }
}
```

`evidence_used` 建议保存内部结构化证据包摘要，不保存模型自由发挥内容。`citations` 只来自已校验的 registry row。

## 8. 引用校验

必须实现以下规则：

- 检索先于大模型生成。
- 大模型只能基于结构化证据包组织语言，不能新增检索结果之外的 `source_id`。
- 返回前用 `SourceRegistryService.get_by_source_id()` 校验所有引用真实存在。
- `source_url` 必须来自 registry 的 `url` 字段。
- 若模型输出引用不在检索集合内，删除该引用并降级答案；严重不一致时返回“当前数据不足”。
- 没有证据时明确回答“当前数据不足”，并返回空 `citations`。
- B015/B016 必须继续区分：B015 是 EMA 当前正式授权状态，B016 是 CHMP 积极意见，不等于最终批准。
- NCT04619433 必须保持 `Terminated`，不得把 `verification_status=已人工核验` 写成研究正在进行。
- 企业对比只代表当前已核验 NSCLC 样本，不代表整体研发实力。

## 9. 无密钥降级

无 `DEEPSEEK_API_KEY` 时：

- `used_llm=false`。
- 不返回 500。
- 不返回伪造的模型答案。
- 如果检索有证据，返回本地模板化、引用可校验的简短答案。
- 如果检索无证据，返回“当前数据不足”。
- `safety_notice` 明确说明当前为本地证据整理，未调用大模型。

模型调用失败时采用同样降级策略，并在 `limitations` 中记录“模型组织答案不可用，已返回本地证据摘要”。

第四阶段接入后，DeepSeek 适配器独立放在 `deepinsight/core/grounded_qa_llm.py`。模块导入时不创建客户端，`generation_mode=local` 不创建客户端；`generation_mode=auto` 只有在密钥已配置、问题通过安全边界、且本次检索有证据时，才由 `GroundedQAService` 延迟创建 OpenAI 兼容客户端并尝试调用 DeepSeek。模型失败、输出非法或引用无效时自动回退本地摘要。

DeepSeek 配置只使用：

- `DEEPSEEK_API_KEY`
- `DEEPSEEK_BASE_URL`
- `DEEPSEEK_MODEL`
- `DEEPSEEK_TIMEOUT_SECONDS`
- `DEEPSEEK_MAX_TOKENS`

默认模型为 `deepseek-v4-flash`。API capability 只返回是否已配置和模型名，不返回密钥或密钥字段。

## 10. 缓存规则

可选演示缓存只能保存真实生成且通过引用校验的答案。每条缓存必须包含：

- `cache_schema_version`
- `data_version`
- `generated_at`
- `model_name`
- `question`
- `question_type`
- `source_count`
- `source_ids`
- `chain_ids`
- `answer`
- `citations`
- `limitations`

失效规则：

- 当前 `data_version` 与缓存不一致时失效。
- 当前检索得到的 `source_ids` 或 `chain_ids` 与缓存不一致时失效。
- 任一缓存 citation 的 `source_id` 已不存在或 `source_url` 为空时失效。
- 缓存不能作为伪造实时结果；命中时 `trace.cache_hit=true`，并保留原始 `generated_at`。
- 不接入 `SemanticCache`，不使用向量模型作为第四天初版必要依赖。

`data_version` 当前由 `data/source_registry.csv`、`config/evidence_chains.json`、`config/evidence_rules.json` 和 `config/grounded_qa_rules.json` 的文件内容哈希生成；后续可升级为显式数据版本号。

## 11. 前端位置建议

推荐方案：B，在“研发证据查询”中增加“循证问答”第四个页签。

理由：

- 不破坏旧“智能问答”的企业经营分析体验。
- 避免旧 SQLite/Chroma 结论与新 `source_registry.csv` 证据口径混用。
- 用户会把它理解为研发证据体系的一部分，而不是泛化聊天机器人。
- 五天初版内实现范围可控：新增一个 API、一个服务、一个页签即可。

不建议第一阶段直接改造 A，因为旧 `/api/chat` 入口已经绑定企业经营、财务 SQL、Chroma、投资研判提示和旧前端会话逻辑。方案 C 可作为过渡叙事：保留旧智能问答，同时新增独立循证问答。

## 12. 分阶段实施顺序

建议顺序：

1. 新增 `GroundedQAService`：规则分类、安全边界、检索证据包、本地降级答案、引用校验。
2. 新增 `POST /api/evidence/grounded-qa`：只读、无密钥不 500、返回最小响应结构。
3. 增加单元测试和真实 ASGI 请求测试：覆盖无密钥、无证据、B015/B016、NCT04619433、企业对比边界、禁止问题。
4. 在“研发证据查询”增加“循证问答”页签：调用新 API，不调用 `/api/chat`、`/api/workflow`、`/api/advanced`。
5. 可选加入严格缓存：只缓存通过引用校验的真实结果，数据版本或来源集合变化即失效。

第四天初版禁止使用：

- 固定评分、`random`、`Faker` 或 `MOCK` 生成结论。
- 无来源结论。
- Chroma、`sentence-transformers` 或语义缓存作为必要依赖。
- 个体诊断、个体治疗建议、疗效保证、跨试验疗效排名、成功率预测、投资建议。
