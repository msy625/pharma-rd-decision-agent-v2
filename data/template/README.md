# 多领域医药研发数据模板 v0.1

本目录是后续扩充数据时使用的初版模板，不替换当前的 `data/source_registry.csv`，也不直接参与当前运行链路。

目标是把“来源、实体、事实、关系、商业事件”分开，形成可持续扩展的医药研发决策数据层。

## 一、推荐业务主线

```text
研究领域
  -> 企业/机构
  -> 研发资产
  -> 疾病/适应症
  -> 研究项目
  -> 论文/登记/监管来源
  -> 监管事件
  -> 市场事件
  -> 证据缺口与决策问题
```

每条新增数据都应该能够回答：

1. 这个对象属于哪个领域？
2. 它和哪个企业、资产、适应症或研究项目有关？
3. 事实来自哪个可核验来源？
4. 关系是已确认、推测还是待确认？
5. 这个事实对研发、注册、竞争或商业决策有什么意义？

## 二、文件分层

| 文件 | 层级 | 作用 |
|---|---|---|
| `domains.csv` | 领域层 | 肿瘤、免疫、代谢等研究领域和主题边界 |
| `organizations.csv` | 实体层 | 企业、监管机构、医院、研究机构 |
| `organization_aliases.csv` | 实体层 | 企业历史名称、中文名、英文名和简称 |
| `assets.csv` | 实体层 | 药物、抗体、ADC、平台或研发项目 |
| `asset_aliases.csv` | 实体层 | 通用名、商品名、研发代号 |
| `indications.csv` | 实体层 | 疾病、亚型、生物标志物和治疗线 |
| `studies.csv` | 研究层 | 临床、临床前、转化、真实世界研究 |
| `study_identifiers.csv` | 研究层 | NCT、CTR、内部研究编号等 |
| `publications.csv` | 研究层 | 论文、会议摘要、海报和报告 |
| `regulatory_events.csv` | 监管层 | 申报、审评、批准、标签变化等 |
| `market_events.csv` | 商业层 | 授权、合作、上市、支付、竞争事件 |
| `sources.csv` | 来源层 | 原始页面、文件、核验状态和时间 |
| `facts.csv` | 事实层 | 来源明确支持的原子事实 |
| `relations.csv` | 关系层 | 实体之间的可追溯关系 |

## 三、填写规则

- 每个实体使用稳定 ID，不使用名称作为主键。
- 多个名称、编号或关系不要放在一个单元格中，分别写入别名表、编号表或关系表。
- `source_id` 只表示资料来源；`fact_id` 表示从来源中抽取的一个事实；`relation_id` 表示两个实体之间的一条关系。
- `confirmed`、`probable`、`unresolved`、`rejected` 必须区分，不能把待确认关系当成事实。
- 研究状态、来源核验状态、监管授权状态分别记录，不能混用。
- 没有来源支持的结论不进入 `facts.csv`，只可以作为待研究问题记录在业务任务系统中。
- 日期全部使用 `YYYY-MM-DD`；只有年份时使用 `YYYY`，不要补造月份和日期。
- 同一项临床研究的 NCT、CTR、公司编号分别记录在 `study_identifiers.csv`，不要重复创建多个研究对象。

## 四、核心关系示例

```text
ORG_BEONE --sponsors--> STUDY_NCT04379635
ASSET_TISLELIZUMAB --tested_in--> STUDY_NCT04379635
STUDY_NCT04379635 --targets--> IND_NSCLC_1L
STUDY_NCT04379635 --reported_by--> PUB_B011
ASSET_TISLELIZUMAB --has_regulatory_event--> REG_B015
SOURCE_B012 --supports--> FACT_STUDY_STATUS_001
```

## 五、当前数据迁移原则

当前 `data/source_registry.csv` 和 `config/evidence_chains.json` 继续作为旧格式输入保留。后续应先生成本目录的规范化数据，再让服务层通过适配器读取，确认结果一致后再逐步替换旧读取逻辑。

