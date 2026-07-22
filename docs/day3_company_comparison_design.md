# 第三天企业证据对比数据可行性审计

## 1. 对比目标

本阶段目标是在当前已人工核验的 31 条 NSCLC 资料样本内，判断恒瑞医药与百济神州/BeOne Medicines 能否进行结构化证据样本对比，并为后续企业证据对比服务、API 和页面开发确定最小口径。

该对比只回答“当前收录证据样本覆盖了什么、缺什么、能如何分组”，不回答企业研发实力、项目成功概率、疗效优劣、投资价值或综合排名。

所有数量均必须标注为“当前收录样本内”。15 条与 16 条来源不能代表企业研发实力，6 条与 4 条试验级证据链也不能直接得出谁的研发能力更强。

## 2. 可直接比较维度

| 维度 | 结论 | 数据来源 | 当前收录样本内结果 |
| --- | --- | --- | --- |
| 当前样本来源数量 | 可直接比较 | `data/source_registry.csv.company` | 恒瑞医药 15 条；百济神州/BeOne Medicines 16 条 |
| 已核验来源数量 | 可直接比较 | `verification_status=已人工核验` | 恒瑞医药 15 条；百济神州/BeOne Medicines 16 条 |
| 试验级证据链数量 | 可直接比较 | `config/evidence_chains.json.chain_type=trial` | 恒瑞医药 6 条；百济神州 4 条；合计 10 条 |
| 药物级监管链数量 | 可直接比较 | `chain_type=regulatory` | 恒瑞医药 0 条；百济神州 1 条；合计 1 条 |
| 来源类型构成 | 可直接比较 | `source_type` | 可按企业统计 ClinicalTrials.gov、PubMed、公司公告、监管资料等类别 |
| 最新、历史、独立资料构成 | 可直接比较 | `is_latest_evidence` | `true` 为最新，`false` 为历史，空值为独立资料 |
| 单来源链与多来源链数量 | 可直接比较 | 每条链 `source_ids` 数量 | 恒瑞医药 6 条单来源试验链、0 条多来源试验链；百济神州 0 条单来源试验链、4 条多来源试验链 |
| 未解决关联数量 | 可直接比较 | `unresolved_links` | 恒瑞医药 6 条；百济神州 1 条 |

当前收录样本内来源类型构成：

| 企业 | 来源类型构成 |
| --- | --- |
| 恒瑞医药 | ClinicalTrials.gov 5；PubMed 5；企业官网 1；公司年报 1；投资者演示材料 1；公司正式公告 1；公司研发进展公告 1 |
| 百济神州/BeOne Medicines | PubMed 6；ClinicalTrials.gov 4；公司临床试验官网 1；公司年度报告 1；公司官方试验页面 1；公司全球临床研发管线 1；独立监管机构当前授权页面 1；EMA/CHMP上市后变更积极意见 1 |

当前收录样本内版本构成：

| 企业 | 最新版本 | 历史版本 | 独立资料 |
| --- | ---: | ---: | ---: |
| 恒瑞医药 | 0 | 0 | 15 |
| 百济神州/BeOne Medicines | 4 | 2 | 10 |

## 3. 部分可比较维度

| 维度 | 结论 | 可用口径 | 风险边界 |
| --- | --- | --- | --- |
| 临床研究状态分布 | 只能部分比较 | 可统计 `study_status` 原始值，例如 Completed、Active, not recruiting、Unknown、Terminated | 不同来源类型混有临床登记状态、公告事件状态和监管不适用状态，不能直接解释为研发进度优劣 |
| 临床阶段分布 | 只能部分比较 | 可统计 `study_phase` 原始值 | 字段存在空值、`不适用`、`文件未明确`，且 III 期公告与 ClinicalTrials.gov Phase 3 需要保留原始口径 |
| 药物/项目数量 | 只能部分比较 | 可使用证据链、`drug_names` 和明确研究编号作为样本内项目覆盖提示 | 缺少统一 `project_id`、`target`、`mechanism`、`drug_type`，不能输出企业真实药物或项目总数 |
| 研究人群覆盖 | 只能部分比较 | 可展示 `population`、`histology`、`biomarker_requirements` 的已填写内容 | 字段粒度不一致，不能自动推断完整适应症覆盖 |
| 治疗场景覆盖 | 只能部分比较 | 可展示 `treatment_line`、`regimen_detail`、`comparator` 的已填写内容 | 不能从标题或药物名称推断未结构化治疗线、联合方案或对照方案 |

当前收录样本内研究状态分布：

| 企业 | 研究状态分布 |
| --- | --- |
| 恒瑞医药 | 未填写 8；Unknown 2；Completed 2；Terminated 1；药品注册获批事件 1；III期研究期中分析达到主要终点 1 |
| 百济神州/BeOne Medicines | 未填写 8；Completed 3；Active, not recruiting 2；不适用 2；当前活跃管线快照 1 |

当前收录样本内临床阶段分布：

| 企业 | 临床阶段分布 |
| --- | --- |
| 恒瑞医药 | Phase 2 4；Phase 3 3；Phase 1/2 1；Phase 1 1；Phase 1b/2 1；III期 1；文件未明确 1；未填写 3 |
| 百济神州/BeOne Medicines | Phase 3 11；不适用 3；未填写 2 |

## 4. 禁止比较维度

| 维度 | 当前结论 |
| --- | --- |
| 靶点、机制和药物类型 | 当前不能可靠比较。当前结构化字段缺少统一 `target`、`mechanism`、`drug_type`，不得从标题、药物名称或大模型推断。 |
| 疗效、安全性和成功概率 | 当前不能可靠比较。不得做跨试验疗效排名，不得输出成功率预测、投资建议、企业综合评分或疗效优劣结论。 |
| 企业研发实力 | 禁止由来源数量、链数量、多来源链数量或样本覆盖推断。多来源链可能代表证据关联更完整，也可能只是当前采集覆盖不同。 |
| 旧 `/api/compare` 财务或雷达评分 | 禁止复用到循证对比。旧公司画像对比包含财务、风险、专利和评分语义，不适合作为当前证据样本比较口径。 |

## 5. 指标计算规则

| 字段 | 计算规则 | 数据来源 |
| --- | --- | --- |
| `source_counts` | 按公司统计当前 CSV 来源条数 | `source_registry.csv.company` |
| `verified_source_counts` | 按公司统计 `verification_status=已人工核验` 的来源条数 | `source_registry.csv.verification_status` |
| `trial_chain_counts` | 按公司统计 `chain_type=trial` 的链数量 | `evidence_chains.json.chains` |
| `regulatory_chain_counts` | 按公司统计 `chain_type=regulatory` 的链数量 | `evidence_chains.json.chains` |
| `source_type_distribution` | 按公司和 `source_type` 分组计数 | `source_registry.csv.source_type` |
| `study_status_distribution` | 按公司和原始 `study_status` 分组计数，空值显示为“未填写” | `source_registry.csv.study_status` |
| `version_distribution` | `is_latest_evidence=true` 计为最新版本，`false` 计为历史版本，空值计为独立资料 | `source_registry.csv.is_latest_evidence` |
| `single_source_chain_counts` | `chain_type=trial` 且 `source_ids` 数量为 1 的链数量 | `evidence_chains.json.chains[].source_ids` |
| `multi_source_chain_counts` | `chain_type=trial` 且 `source_ids` 数量大于 1 的链数量 | `evidence_chains.json.chains[].source_ids` |
| `unresolved_link_counts` | 按 unresolved source 的公司归属计数 | `evidence_chains.json.unresolved_links` 与 `source_registry.csv.source_id` |
| `representative_chains` | 返回每家公司若干试验链摘要，用于说明样本结构 | `evidence_chains.json.chains` 与 EvidenceChainService 标准化来源 |

临床试验数量只按试验级证据链或唯一 `trial_id` 计数。同一试验下的登记、论文、公司页面和监管背景不能分别计为多项试验。药物级监管链不能计入临床试验数量。

## 6. 最小响应结构

建议新增服务层返回结构：

```json
{
  "companies": ["恒瑞医药", "百济神州/BeOne Medicines"],
  "data_scope": "current_verified_nsclc_31_source_sample",
  "source_counts": {},
  "verified_source_counts": {},
  "trial_chain_counts": {},
  "regulatory_chain_counts": {},
  "source_type_distribution": {},
  "study_status_distribution": {},
  "version_distribution": {},
  "single_source_chain_counts": {},
  "multi_source_chain_counts": {},
  "unresolved_link_counts": {},
  "representative_chains": [],
  "evidence_gaps": [],
  "comparison_notes": [],
  "prohibited_conclusions": []
}
```

字段说明：

| 字段 | 含义 |
| --- | --- |
| `companies` | 本次对比企业，使用别名配置统一展示名 |
| `data_scope` | 固定说明本结果仅基于当前 31 条已核验 NSCLC 样本 |
| `source_counts` / `verified_source_counts` | 当前样本内来源数量与已核验来源数量 |
| `trial_chain_counts` / `regulatory_chain_counts` | 当前样本内试验级链和药物级监管链数量 |
| `source_type_distribution` | 当前样本内来源类型构成 |
| `study_status_distribution` | 当前样本内原始研究状态构成 |
| `version_distribution` | 最新、历史、独立资料构成 |
| `single_source_chain_counts` / `multi_source_chain_counts` | 当前样本内试验链证据来源完整度提示 |
| `unresolved_link_counts` | 当前样本内待确认关系数量 |
| `representative_chains` | 代表性链条摘要，不用于排名 |
| `evidence_gaps` | 缺失字段、未解决关系和不能推断的内容 |
| `comparison_notes` | 对比解释边界，例如“多来源链不等于研发更强” |
| `prohibited_conclusions` | 明确禁止输出的结论类型 |

## 7. 页面位置建议

建议选择 A：在“研发证据查询”内增加“企业对比”第三个页签。

原因：

- 当前功能本质是“证据样本对比”，应与来源检索、证据链放在同一研发证据语境下。
- 旧“公司画像·对比”页面已经承载财务、风险、专利、雷达或评分类信息，容易让用户误解为企业综合实力比较。
- 新页签可以明确展示“当前收录样本内”的限制，避免把 15 条与 16 条来源、6 条与 4 条试验链解释为企业研发能力强弱。

不建议直接复用旧“公司画像·对比”页面，除非后续将其证据对比模块与财务评分模块进行明显视觉和文案隔离。

## 8. 风险提示文案

建议页面固定展示以下边界提示：

- 本页仅比较当前收录的 31 条已核验 NSCLC 资料样本，不代表企业完整研发管线。
- 来源数量、试验链数量和多来源链数量只能反映当前样本覆盖，不代表研发实力、项目质量或成功概率。
- 药物级监管链不计入临床试验数量。
- 多来源链可能表示登记、论文和公司资料关联更完整，也可能只是当前采集覆盖不同。
- 当前缺少统一的靶点、机制、药物类型和结构化疗效字段，因此不做跨试验疗效排名。
- 当前数据不足时应显示“当前数据不足”，不得从标题或药物名称自动推断。
- 本页不提供投资建议、企业综合评分、成功率预测或治疗选择建议。

## 9. 后续服务、API和测试建议

已按本设计新增服务：

- `deepinsight/core/company_evidence_comparison_service.py`
- 复用 `SourceRegistryService` 与 `EvidenceChainService`，不重复实现 CSV 筛选和证据链去重逻辑。
- 服务方法包括：
  - `company_profile(company_name)`
  - `compare(company_a, company_b)`
  - `metric_rules()`
  - `available_companies()`

实际落地接口命名为：

- `GET /api/evidence/company-comparison`
  - 查询参数：`companies` 可选，默认恒瑞医药与百济神州/BeOne Medicines。
  - 返回最小响应结构。
- `GET /api/evidence/company-comparison/metric-rules`
  - 返回指标来源、计算规则和禁止结论，供前端展示说明。

API 使用 `company_a` 与 `company_b` 两个查询参数，默认分别为恒瑞医药与 BeOne Medicines。

建议测试：

- 当前样本内来源数量为恒瑞医药 15、百济神州/BeOne Medicines 16。
- 已核验来源数量与来源数量一致。
- 试验级证据链数量为恒瑞医药 6、百济神州 4。
- 药物级监管链数量为恒瑞医药 0、百济神州 1。
- 百济神州药物级监管链不计入临床试验数量。
- 单来源试验链与多来源试验链数量符合配置。
- H008-H012、H014 和 B015 的具体试验关系保持待确认。
- 响应不包含评分、成功率、疗效排名、投资建议或企业综合排名字段。
- 服务导入不加载大模型、Chroma 或向量模型。
