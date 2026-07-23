# Day5 线上循证问答安全补丁验证

## 背景

Render 预览部署已完成核心接口验收。公开 `POST /api/evidence/grounded-qa` 如果直接开放 `auto` 模式，可能被重复调用并消耗 DeepSeek 余额。因此线上默认关闭 DeepSeek 智能生成，`local` 本地循证摘要始终可用。

本补丁不读取 `.env`，不把真实密钥写入 Git，不在自动测试中调用真实 DeepSeek。

## 默认配置

新增非敏感配置：

```text
GROUNDED_QA_LLM_ENABLED=false
GROUNDED_QA_LLM_PER_CLIENT_LIMIT=5
GROUNDED_QA_LLM_GLOBAL_LIMIT=30
GROUNDED_QA_LLM_WINDOW_SECONDS=600
GROUNDED_QA_LLM_MAX_CONCURRENCY=2
```

`GROUNDED_QA_LLM_ENABLED` 只有明确设置为 `true`、`1`、`yes` 或 `on` 时才开启；其他值均视为关闭。数值配置非法、越界或缺失时回退安全默认值。

Render Blueprint 中显式设置：

```text
GROUNDED_QA_LLM_ENABLED=false
```

`DEEPSEEK_API_KEY` 继续使用 `sync:false`，只允许在 Render 控制台手动配置，不能写入仓库。

## API 执行顺序

`POST /api/evidence/grounded-qa` 的执行顺序为：

1. 校验请求格式、空问题和 1000 字符长度。
2. 分类问题并执行安全边界检查。
3. 禁止问题在检索前返回安全拦截结果，不占 LLM 配额。
4. 检索本地已核验证据。
5. 无证据问题返回“当前数据不足”，不占 LLM 配额。
6. `local` 模式直接返回本地循证摘要。
7. `auto` 模式检查 `GROUNDED_QA_LLM_ENABLED` 和 `DEEPSEEK_API_KEY`。
8. 只有开关开启、密钥存在、问题安全且已有证据时，才申请限流和并发许可。
9. 获得许可后才尝试 DeepSeek。
10. 模型输出仍需通过引用校验，失败时回退本地摘要。
11. 并发许可在 `finally` 中释放。

## 限流和并发

新增 `deepinsight/core/grounded_qa_usage_guard.py`：

- 进程内固定窗口计数，使用 `time.monotonic()`。
- 每客户端窗口限额默认 5 次。
- 全局窗口限额默认 30 次。
- 全局并发上限默认 2。
- 线程锁保护计数和并发状态。
- 清理过期客户端窗口，避免内存无限增长。
- 不保存完整问题，不导入 OpenAI、Chroma、sentence-transformers、Torch 或旧功能模块。

客户端标识使用 ASGI `request.client.host`。如果无法可靠获得客户端地址，例如测试客户端，则退化为共享匿名客户端限额。应用不盲目信任任意转发 Header，也不会把客户端地址返回前端。

限制：当前实现是 Render Free 单实例适用的进程内保护。实例重启会重置计数；多实例部署会分散计数；它不是边缘网关、WAF 或认证系统的替代品。若后续开放长期公网访问，应迁移到平台级限流或集中式存储。

## 响应行为

- `local`：200，不占 LLM 配额。
- `auto` 且开关关闭：200，回退本地摘要，并说明“DeepSeek智能生成当前未启用，本地循证摘要仍可使用。”
- `auto` 且无密钥：200，回退本地摘要。
- 禁止问题：200，安全规则拦截，不占 LLM 配额。
- 无证据问题：200，当前数据不足，不占 LLM 配额。
- 每客户端、全局或并发限额命中：429，返回 `Retry-After` 响应头。
- DeepSeek 调用异常：200，按现有规则回退本地摘要，不返回异常堆栈。

429 响应只包含友好中文说明、`retry_after` 和 `local_mode_available=true`，不返回内部计数表、客户端地址、密钥、路径或异常堆栈。

## Capabilities

`GET /api/evidence/grounded-qa/capabilities` 返回：

- `local_mode_available=true`
- `llm_mode_available`：仅当 `GROUNDED_QA_LLM_ENABLED=true` 且 `DEEPSEEK_API_KEY` 已配置时为 true
- `llm_rate_limit_enabled=true`
- `per_client_limit`
- `global_limit`
- `window_seconds`
- `max_concurrency`

接口不返回密钥、不返回当前客户端已用次数、不返回全局内部计数。

## 前端处理

循证问答页在开关关闭或无密钥时显示：

```text
DeepSeek智能生成当前未启用，本地循证摘要仍可使用。
```

收到 429 时，页面显示中文限流提示；如果响应带有 `Retry-After`，提示等待秒数；不自动重试。用户仍可切换 `local` 模式继续使用本地循证摘要。

## 验证

自动测试覆盖：

- 默认开关关闭。
- 开关关闭时即使测试密钥存在也不创建客户端。
- 开关开启且有测试密钥时 capabilities 才显示 LLM 可用。
- `local`、禁止问题、无证据问题不占 LLM 配额。
- 合法 `auto` 调用才计数。
- 每客户端、全局和并发限额返回 429。
- 429 包含 `Retry-After`。
- 窗口结束后恢复。
- 过期记录清理。
- 非法配置回退安全默认值。
- 异常后并发许可释放。
- DeepSeek 异常回退本地摘要。
- 响应不暴露客户端地址、密钥、路径或堆栈。
- 导入保护模块不加载 OpenAI、Chroma、sentence-transformers 或 Torch。
- 前端 429 只提示，不自动重试。

待人工复验：

1. Render 中保持 `GROUNDED_QA_LLM_ENABLED=false` 且不配置 `DEEPSEEK_API_KEY` 时，`auto` 回退本地摘要。
2. 页面显示“DeepSeek智能生成当前未启用，本地循证摘要仍可使用。”
3. 后续如需演示 LLM，先在 Render 手动配置密钥，再显式设置 `GROUNDED_QA_LLM_ENABLED=true`，并在演示后关闭或删除密钥。
