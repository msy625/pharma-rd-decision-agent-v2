# 药研制策离线量化评测协议（Pilot v1）

## 目的与边界

本协议用于离线、可复现地评估当前人工核验NSCLC证据工作流。第一阶段只有12题pilot，用于验证评测工具并暴露生产能力缺口，不属于最终开发集或锁定验收集，也不能作为最终业务成绩。

评测不调用真实DeepSeek、OpenAI或其他模型，不访问外部业务网络，不修改来源登记表、企业别名或证据链配置。自由文本监管语义仍需人工复核，服务层延迟也不等同于浏览器端到端延迟。

## 事实快照

- `expected_data_version`: `sha256:330ac862f52db200`
- `facts_snapshot_commit`: `656626b8756a01e4f6280f4451be503a92439e71`
- `benchmark_stage`: `pilot`
- `case_count`: `12`

runner必须校验`data_version`，不一致时在创建输出目录前中止。事实快照提交只表示题集依据的起点；后续评测代码提交不会因为HEAD变化而被拒绝。

## Pilot题型分布

| 题型 | 数量 |
|---|---:|
| 来源检索 | 2 |
| 试验状态 | 2 |
| 证据链 | 2 |
| 监管状态 | 2 |
| 企业比较 | 1 |
| 证据缺口 | 1 |
| 禁止或不支持 | 2 |
| 合计 | 12 |

每个用例使用同一schema。空集合统一写为`[]`，不得按题型建立不兼容结构。金标准由人工编写，runner不得从被测服务输出反向生成期望source_id、chain_id或事实结论。

## 三种离线基线

### `keyword_contains`

调用`SourceRegistryService.query(text=...)`执行普通关键词包含查询，不扩展证据链，不生成业务回答。

### `structured_no_chain`

按照用例`request.query_mode`调用`SourceRegistryService`现有结构化查询。企业对比只合并两个现有企业查询结果；多source_id只逐个调用现有source_id查询。该基线不调用`EvidenceChainService`扩展关系。

### `grounded_qa_local`

调用现有`GroundedQAService.answer_question()`，不传LLM客户端，也不启用配置模型。该流程保留现有安全分类、source_id锚点、证据链扩展、本地摘要、引用校验和限制说明。

三种基线统一输出：

```text
source_ids, chain_ids, citations, answer, question_type,
safety_category, refused, used_llm, limitations,
latency_ms, error
```

适配器只调用生产服务并归一响应，不复制来源筛选、企业别名、证据链、版本或监管规则。

## 指标

设`P_K`为实际返回结果的前K项，`R`为人工金标准来源集合。

- Retrieval Precision@K：若`P_K`非空，为`|P_K ∩ R| / |P_K|`；否则为0。
- Retrieval Recall@K：`|P_K ∩ R| / |R|`；金标准为空时，无返回记1，有返回记0。
- source集合Precision、Recall、F1：按完整返回集合计算。
- chain完全匹配率：实际chain_id集合与期望集合相等记1，否则记0。
- chain F1：按chain_id集合Precision和Recall计算。
- 引用白名单合规率：白名单内引用数/全部引用数；无引用时记1，但不代替必要事实和来源覆盖检查。
- 零越界引用：不存在白名单外引用记1。
- 必要事实覆盖率：自动匹配且至少有一个声明的支持来源出现在引用中的事实数/必要事实数。
- 禁止结论触发率：命中的禁止结论规则数/禁止规则数，越低越好。
- 监管题硬条件通过率：来源、链、引用、必要事实、禁止结论、分类、拒答状态和延迟全部通过。
- 证据不足正确提示率：需要缺口或数据不足说明的用例中，限制提示正确且未产生越界来源或结论。
- 安全分类准确率：安全类别与金标准完全相同。
- 禁止问题拒答率：应拒答用例中正确拒答、零检索、零引用、零模型调用。
- 总体通过率：用例全部硬条件通过的比例。
- 按题型宏平均：先计算各题型通过率，再对题型等权平均。
- 延迟：分别报告Mean、Median和nearest-rank P95。

人工复核标记不阻止自动指标计算，但自动通过不能替代人工结论。B015/B016监管口径、企业比较中的暗含排名，以及“当前样本未收录”与“事实不存在”的区别必须人工复核。

## 运行方式

Ubuntu Bash：

```bash
.venv/bin/python -m evaluation.runner \
  --output-dir /tmp/yy-evaluation-pilot
```

可以通过`--baselines`选择逗号分隔的基线。输出目录由调用者指定；runner拒绝将动态结果写入`data/`或`config/`事实目录。测试使用临时目录，不向仓库写入运行结果。

## 输出文件

- `case_results.jsonl`：逐题、逐基线结果和指标。
- `metric_details.csv`：扁平化指标明细。
- `category_summary.csv`：按题型汇总。
- `baseline_comparison.csv`：三种基线对比。
- `latency_percentiles.csv`：Mean、Median和P95延迟。
- `failures.json`：失败原因和实际来源/链/引用。
- `report.md`：面向人工审阅的汇总报告。
- `run_manifest.json`：数据版本、Git SHA、dirty状态、Python版本、时间和参数。

## Pilot解释规则

评测工具自动测试通过只表示schema、runner、指标和报告实现符合协议，不能写成业务准确率。pilot中出现的自然语言别名、公司组合分类或证据缺口分类失败，应记录为当前生产能力缺口；本阶段不得为了提高分数修改生产服务或硬编码答案。
## 结果状态与分母

每条结果只取一个状态：`passed`、`failed`、`not_applicable`、`unsupported`、`manual_review`。不支持的基线能力标记为`unsupported`，不进入适用题通过率分母，也绝不记为通过。

- 覆盖率 = `passed + failed + manual_review` / 全部题目。
- 适用题通过率 = `passed` / `passed + failed`；没有适用题时为`N/A`，不能显示100%。
- 端到端通过率 = `passed` / 全部题目。

Pilot人工复核记录位于`evaluation/reviews/pilot_manual_reviews.json`。其中明确披露当前为非人工签字的辅助证据复核，项目负责人签字前不得对外表述为已完成人工验收。

## 60题正式集

正式集冻结于`formal_manifest.json`和`formal_cases.jsonl`，共60题：来源检索10、试验状态8、证据链10、监管状态8、企业比较8、证据缺口6、禁止或不支持10。拆分为42题开发集与18题锁定验收集。生成脚本只从人工Pilot金标准合同复制预期来源、链、事实与安全边界并改写问法，不调用被测服务；锁定验收集不得用于针对性修复或调参。
