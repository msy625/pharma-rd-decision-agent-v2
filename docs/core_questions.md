# 初版核心问题

本文档基于已冻结的第一版数据范围设计。当前范围为非小细胞肺癌（NSCLC），比较企业为恒瑞医药和百济神州（BeOne Medicines，原BeiGene），已人工核验来源 31 条。

系统只回答研发管线梳理、多源证据检索、企业管线比较、证据追溯和风险提示相关问题。不提供疾病诊断、个体治疗建议、疗效保证或投资建议。

## 1. 核心问题执行表

### Q01

| 字段 | 内容 |
|---|---|
| question_id | Q01 |
| question | 恒瑞医药和百济神州分别有哪些已收录的 NSCLC 相关药物或研发项目？ |
| purpose | 建立初版管线总览，按企业列出已入库药物、研发代号、研究项目和监管项目。 |
| required_fields | `company_cn`、`company_display_name`、`drug_names`、`study_name`、`normalized_title_zh`、`source_type`、`source_id` |
| preferred_sources | ClinicalTrials.gov、PubMed、公司官网、公司管线材料、公司正式公告、EMA |
| answer_format | 按企业分组的项目清单；每个项目列出代表来源编号和来源类型。 |
| no_data_behavior | 若企业无匹配记录，返回“当前 31 条已核验来源中未收录”，并提示不代表真实世界无项目。 |
| risk_notes | 来源记录数不等于唯一项目数；B011、B012、B013 只对应 RATIONALE-315 一项试验。 |
| priority | P0：初版演示必须实现 |
| current_answerability | 可直接回答 |

### Q02

| 字段 | 内容 |
|---|---|
| question_id | Q02 |
| question | 每个药物或项目的标准名称、英文名称、研发代号和别名是什么？ |
| purpose | 支持别名识别，避免把同一药物或同一企业新旧名称拆成多个实体。 |
| required_fields | `drug_names`、`original_title`、`original_title_en`、`study_name`、`official_study_id`、`company_current_name`、`company_former_name` |
| preferred_sources | `data_dictionary.md` 名称映射、ClinicalTrials.gov、PubMed、公司年报、EMA |
| answer_format | 药物/项目别名表：中文名、英文名、研发代号、商品名、相关来源编号。 |
| no_data_behavior | 若别名未核验，标为“来源未明确”或“当前未收录”，不得自行补全。 |
| risk_notes | B002 年报未检索到 BGB-A317，不代表 BGB-A317 研发代号无效；BeiGene 和 BeOne Medicines 归为同一企业。 |
| priority | P0：初版演示必须实现 |
| current_answerability | 可直接回答 |

### Q03

| 字段 | 内容 |
|---|---|
| question_id | Q03 |
| question | 每个项目对应的靶点、作用机制和药物类型是什么？ |
| purpose | 支持按靶点、机制和药物类型理解管线结构。 |
| required_fields | `drug_names`、`normalized_title_zh`、`intervention`、`biomarker_requirements`、`notes` |
| preferred_sources | 公司管线材料、ClinicalTrials.gov、EMA、公司公告、PubMed |
| answer_format | 项目机制表：项目、已知靶点/机制/药物类型、证据来源、缺失项。 |
| no_data_behavior | 对未结构化核验的靶点、机制或类型，返回“当前字段未完整收录”，不得从药名外推。 |
| risk_notes | 当前没有完整的 `target`、`mechanism`、`drug_type` 字段；EGFR、ALK、HER2、PD-L1 多数属于生物标志物或人群限制，不应自动当作药物靶点。 |
| priority | P1：初版可实现但不是主链路 |
| current_answerability | 可部分回答 |

### Q04

| 字段 | 内容 |
|---|---|
| question_id | Q04 |
| question | 每个项目当前处于什么临床阶段、研究状态或监管状态？ |
| purpose | 展示项目阶段、试验状态和监管状态，支持研发管线进展判断。 |
| required_fields | `study_phase`、`study_status`、`authorisation_status`、`regulatory_event_type`、`source_last_updated`、`publication_date`、`notes` |
| preferred_sources | ClinicalTrials.gov、EMA、公司公告、公司研发进展公告、公司管线材料 |
| answer_format | 项目状态表：项目、阶段、研究状态、监管事件、来源编号、日期。 |
| no_data_behavior | 若状态来源未明确，返回“当前来源未明确”，不得猜测为进行中、完成或终止。 |
| risk_notes | `study_status` 与 `verification_status` 必须分开；H006 为 Terminated；B016 是 CHMP positive opinion，不是最终批准文件。 |
| priority | P0：初版演示必须实现 |
| current_answerability | 可直接回答 |

### Q05

| 字段 | 内容 |
|---|---|
| question_id | Q05 |
| question | 每个项目主要覆盖哪类 NSCLC 人群，包括鳞状、非鳞状、可切除、晚期或转移性等？ |
| purpose | 支持按研究人群检索和比较企业布局。 |
| required_fields | `histology`、`population`、`normalized_title_zh`、`biomarker_requirements`、`regimen_detail` |
| preferred_sources | ClinicalTrials.gov、PubMed、EMA、公司公告 |
| answer_format | 按企业和项目列出人群标签、原始描述摘要、证据编号。 |
| no_data_behavior | 若人群未明确，显示“来源未明确”，不泛化为全部 NSCLC。 |
| risk_notes | 不得把携带 EGFR/ALK 异常、脑转移、HER2 激活突变等特定人群写成全部 NSCLC。 |
| priority | P0：初版演示必须实现 |
| current_answerability | 可直接回答 |

### Q06

| 字段 | 内容 |
|---|---|
| question_id | Q06 |
| question | 每个项目覆盖一线、二线、三线还是围手术期治疗场景？ |
| purpose | 支持按治疗线次和治疗场景分析管线布局。 |
| required_fields | `treatment_line`、`population`、`intervention`、`regimen_detail`、`normalized_title_zh` |
| preferred_sources | ClinicalTrials.gov、PubMed、EMA、公司正式公告 |
| answer_format | 治疗场景矩阵：企业、项目、一线/经治/二线或三线/围手术期、来源编号。 |
| no_data_behavior | 若线次未核验，返回“来源未明确”，不根据方案外推。 |
| risk_notes | 既往治疗、二线或三线、围手术期不能混用；B015 的 EMA 适应症需分项展示。 |
| priority | P1：初版可实现但不是主链路 |
| current_answerability | 可直接回答 |

### Q07

| 字段 | 内容 |
|---|---|
| question_id | Q07 |
| question | 项目是否包含 EGFR、ALK、HER2、PD-L1 等生物标志物或人群限制？ |
| purpose | 提示关键入排标准和适应症限制，避免错误泛化。 |
| required_fields | `biomarker_requirements`、`population`、`histology`、`normalized_title_zh`、`notes` |
| preferred_sources | ClinicalTrials.gov、EMA、公司正式公告、PubMed |
| answer_format | 生物标志物限制表：项目、限制类型、具体描述、证据编号。 |
| no_data_behavior | 若字段为“来源未明确”或空值，显示“当前未核验到限制”，不得写成“无限制”。 |
| risk_notes | EGFR 和 ALK 是生物标志物或研究人群特征，不作为药物记录。 |
| priority | P1：初版可实现但不是主链路 |
| current_answerability | 可直接回答 |

### Q08

| 字段 | 内容 |
|---|---|
| question_id | Q08 |
| question | 同一项目有哪些 ClinicalTrials.gov 登记、PubMed 论文、公司公告和监管证据？ |
| purpose | 建立项目到多源证据的追溯链。 |
| required_fields | `source_id`、`source_type`、`registry_id`、`parent_trial_id`、`pmid`、`url`、`evidence_relation` |
| preferred_sources | ClinicalTrials.gov、PubMed、公司公告、公司试验页面、EMA |
| answer_format | 证据链表：项目、来源编号、来源类型、链接、关系说明。 |
| no_data_behavior | 若某类来源缺失，明确显示“当前未收录该类型来源”。 |
| risk_notes | 同一试验多来源不得重复计为多项试验；ClinicalTrials.gov 仍作为主要试验登记来源。 |
| priority | P0：初版演示必须实现 |
| current_answerability | 可直接回答 |

### Q09

| 字段 | 内容 |
|---|---|
| question_id | Q09 |
| question | 同一试验是否存在中期、最终或长期随访等不同证据版本，最新版本是哪一个？ |
| purpose | 支持证据版本识别，避免把中期和最终论文当成不同试验。 |
| required_fields | `parent_trial_id`、`study_name`、`analysis_stage`、`evidence_version`、`supersedes_source_id`、`is_latest_evidence`、`publication_date`、`online_publication_date` |
| preferred_sources | PubMed、ClinicalTrials.gov、公司试验页面 |
| answer_format | 版本链：试验编号、研究名称、来源版本顺序、最新证据标记。 |
| no_data_behavior | 若没有版本字段或父试验编号，返回“当前无法建立完整版本链”。 |
| risk_notes | B006/B007 和 B008/B009 是同一试验不同证据版本；H008 是长期随访但恒瑞论文与登记的父试验链尚未完全结构化。 |
| priority | P0：初版演示必须实现 |
| current_answerability | 可部分回答 |

### Q10

| 字段 | 内容 |
|---|---|
| question_id | Q10 |
| question | 两家公司在 NSCLC 适应症、人群、治疗线次、靶点和药物类型方面有哪些相同点和差异？ |
| purpose | 支持初版企业管线比较。 |
| required_fields | `company_cn`、`drug_names`、`histology`、`treatment_line`、`population`、`biomarker_requirements`、`intervention`、`study_phase` |
| preferred_sources | ClinicalTrials.gov、PubMed、EMA、公司公告、公司管线材料 |
| answer_format | 对比表：维度、恒瑞医药、百济神州、支持来源、限制说明。 |
| no_data_behavior | 对靶点和药物类型缺失处显示“当前字段不足”，不强行比较。 |
| risk_notes | 不比较未经统一口径处理的 PFS、OS、MPR 或 EFS 数值；不回答哪个公司或哪个药更好。 |
| priority | P0：初版演示必须实现 |
| current_answerability | 可部分回答 |

### Q11

| 字段 | 内容 |
|---|---|
| question_id | Q11 |
| question | 两家公司当前已收录项目的临床阶段和证据成熟度如何比较？ |
| purpose | 从证据层级说明当前资料成熟度，不做疗效优劣判断。 |
| required_fields | `study_phase`、`study_status`、`source_type`、`verification_status`、`regulatory_event_type`、`authorisation_status`、`is_latest_evidence` |
| preferred_sources | ClinicalTrials.gov、PubMed、EMA、公司正式公告 |
| answer_format | 分级摘要：临床登记、论文版本、监管证据、公司来源，附证据编号。 |
| no_data_behavior | 若缺少统一成熟度规则，返回“可描述证据类型，不能计算成熟度评分”。 |
| risk_notes | 不使用随机评分；证据成熟度只能基于来源类型和状态描述，不能转化为成功概率。 |
| priority | P1：初版可实现但不是主链路 |
| current_answerability | 可部分回答 |

### Q12

| 字段 | 内容 |
|---|---|
| question_id | Q12 |
| question | 哪些结论获得多个独立来源支持，哪些结论目前只有单一公司来源支持？ |
| purpose | 提供证据强弱和来源独立性提示。 |
| required_fields | `source_id`、`source_type`、`sponsor_original`、`regulatory_authority`、`evidence_relation`、`parent_trial_id`、`notes` |
| preferred_sources | ClinicalTrials.gov、PubMed、EMA、公司来源 |
| answer_format | 结论-证据矩阵：结论、支持来源、是否独立来源、风险提示。 |
| no_data_behavior | 若结论没有被结构化抽取，返回“当前只能列出来源组合，不能自动生成结论强度”。 |
| risk_notes | 公司来源、注册平台、论文和监管机构的独立性要分开；公司管线图不能单独证明历史状态。 |
| priority | P0：初版演示必须实现 |
| current_answerability | 可部分回答 |

### Q13

| 字段 | 内容 |
|---|---|
| question_id | Q13 |
| question | 不同来源之间是否存在阶段、状态、名称、时间或适应症描述冲突？ |
| purpose | 识别来源冲突和解释型风险。 |
| required_fields | `study_phase`、`study_status`、`authorisation_status`、`source_last_updated`、`data_cutoff_date`、`notes`、`scope_limitation`、`evidence_relation` |
| preferred_sources | ClinicalTrials.gov、公司管线材料、PubMed、EMA、公司公告 |
| answer_format | 冲突检查表：疑似差异、涉及来源、是否构成冲突、解释和处理建议。 |
| no_data_behavior | 若缺少可比字段，返回“当前不能自动判定冲突，只能列出差异”。 |
| risk_notes | B014 未列出 RATIONALE-315 不构成冲突；在线发表日期与卷期年份不同不构成冲突；研究状态和来源核验状态不得混用。 |
| priority | P1：初版可实现但不是主链路 |
| current_answerability | 可部分回答 |

### Q14

| 字段 | 内容 |
|---|---|
| question_id | Q14 |
| question | 当前数据还缺少哪些字段、监管记录或关键证据，可能影响比较结论？ |
| purpose | 生成数据缺口清单和最小补充计划。 |
| required_fields | 全部结构化字段、空值、`notes`、`scope_limitation`、`source_type`、`company_cn` |
| preferred_sources | `source_registry.csv`、`data_dictionary.md`、`data_availability.md` |
| answer_format | 缺失字段清单：影响问题、缺口、最小补充办法、优先级。 |
| no_data_behavior | 若字段不存在或空值较多，直接列为缺口，不用推断补齐。 |
| risk_notes | 不要为了提高可回答性而降低证据要求；恒瑞仍可补 NMPA/CDE 独立监管原始记录。 |
| priority | P0：初版演示必须实现 |
| current_answerability | 可直接回答 |

### Q15

| 字段 | 内容 |
|---|---|
| question_id | Q15 |
| question | 基于当前公开证据，可以形成哪些研发管线观察和风险提示，同时明确哪些结论不能得出？ |
| purpose | 形成带引用的初版报告骨架和边界声明。 |
| required_fields | `company_cn`、`source_id`、`source_type`、`study_phase`、`study_status`、`population`、`treatment_line`、`evidence_relation`、`notes`、`scope_limitation` |
| preferred_sources | 全部 31 条人工核验来源 |
| answer_format | 观察与风险提示：可支持观察、引用来源、限制、禁止结论。 |
| no_data_behavior | 若无法由来源支持，回答“当前证据不足，不能得出该结论”。 |
| risk_notes | 不生成疗效保证、跨试验疗效排名、公司投资价值判断或未来成功概率预测。 |
| priority | P0：初版演示必须实现 |
| current_answerability | 可部分回答 |

## 2. 可回答性检查

| 问题 | 优先级 | 当前可回答性 | 主要依赖字段 | 缺失或不足 | 最小补充办法 |
|---|---|---|---|---|---|
| Q01 | P0 | 可直接回答 | `company_cn`、`drug_names`、`study_name`、`source_id` | 缺少独立项目主表，需从来源记录聚合 | 建立轻量 `project_id` / `drug_project_name` 映射表 |
| Q02 | P0 | 可直接回答 | `drug_names`、`official_study_id`、`company_current_name` | 药物别名仍主要保存在分号文本中 | 后续拆分为药物别名表 |
| Q03 | P1 | 可部分回答 | `drug_names`、`intervention`、`notes` | 缺少完整 `target`、`mechanism`、`drug_type` 字段 | 补充靶点、机制、药物类型字段并逐条核验 |
| Q04 | P0 | 可直接回答 | `study_phase`、`study_status`、`regulatory_event_type`、`authorisation_status` | 部分 PubMed 论文没有研究状态 | 对论文保持空值，不强行填写研究状态 |
| Q05 | P0 | 可直接回答 | `histology`、`population`、`biomarker_requirements` | 少数来源为“来源未明确” | 保留未知状态，后续按原文补充 |
| Q06 | P1 | 可直接回答 | `treatment_line`、`regimen_detail`、`population` | 个别项目线次字段为“来源未明确” | 从原始登记或公告补齐线次 |
| Q07 | P1 | 可直接回答 | `biomarker_requirements`、`population` | 空值不能解释为无限制 | 输出“当前未核验到限制” |
| Q08 | P0 | 可直接回答 | `source_type`、`parent_trial_id`、`evidence_relation`、`url` | 恒瑞部分论文未建立父试验链 | 后续补充恒瑞论文与登记号映射 |
| Q09 | P0 | 可部分回答 | `analysis_stage`、`evidence_version`、`supersedes_source_id`、`is_latest_evidence` | 百济证据版本链较完整，恒瑞版本链不完整 | 增加恒瑞试验-论文关联和长期随访版本关系 |
| Q10 | P0 | 可部分回答 | `histology`、`treatment_line`、`study_phase`、`intervention` | 靶点和药物类型字段不完整 | 补充 `target`、`mechanism`、`drug_type` 后再比较 |
| Q11 | P1 | 可部分回答 | `study_phase`、`source_type`、`authorisation_status` | 没有统一证据成熟度规则 | 只描述来源层级，不计算评分 |
| Q12 | P0 | 可部分回答 | `source_type`、`sponsor_original`、`regulatory_authority`、`evidence_relation` | 缺少结构化“结论”表 | 先以项目-证据矩阵替代结论强度评分 |
| Q13 | P1 | 可部分回答 | `notes`、`scope_limitation`、`source_last_updated`、`data_cutoff_date` | 没有自动冲突检测规则 | 建立差异类型规则：名称、阶段、状态、时间、适应症 |
| Q14 | P0 | 可直接回答 | 全部字段、空值、备注 | 无 | 直接生成缺失字段和补充建议 |
| Q15 | P0 | 可部分回答 | 全部来源、状态、备注和限制字段 | 可观察，但不能给疗效排名或成功概率 | 输出“观察+风险+不能得出结论”三段式 |

当前统计：
- 可直接回答：8 个。
- 可部分回答：7 个。
- 当前不可可靠回答：0 个。

## 3. 初版演示问题集

| 演示序号 | 对应问题 | 自然语言示例 | 展示重点 |
|---|---|---|---|
| D01 | Q01 | 恒瑞医药目前收录了哪些 NSCLC 相关项目？ | 单企业管线查询 |
| D02 | Q02 | 卡瑞利珠单抗、SHR-1210 和 Camrelizumab 是不是同一个药？ | 药物别名识别 |
| D03 | Q04 | NCT04619433 当前是什么研究状态？ | 研究状态查询，区分 Terminated 与已人工核验 |
| D04 | Q05/Q06 | RATIONALE-315 覆盖什么人群和治疗场景？ | 人群及治疗线次查询 |
| D05 | Q08 | RATIONALE-315 有哪些试验登记、论文和监管证据？ | 试验与论文、监管证据关联 |
| D06 | Q09 | RATIONALE-304 有哪些不同版本的论文证据？ | 中期与最终分析版本识别 |
| D07 | Q10 | 恒瑞和百济在 NSCLC 研究人群覆盖方面有什么差异？ | 双企业管线比较 |
| D08 | Q14/Q15 | 当前数据还缺哪些关键证据，会带来什么风险？ | 数据缺失及风险提示 |

## 4. 文档结论

### 初版必须实现的 P0 问题

Q01、Q02、Q04、Q05、Q08、Q09、Q10、Q12、Q14、Q15。

### 当前只能部分回答的问题

Q03、Q09、Q10、Q11、Q12、Q13、Q15。

这些问题的共同原因是：靶点、机制和药物类型字段不完整；恒瑞部分论文尚未建立完整父试验链；证据成熟度和来源冲突还没有独立规则表；当前只适合做基于来源类型和备注的审慎说明。

### 需要补充的关键字段

- `project_id` 或 `drug_project_name`：用于把来源记录聚合为唯一项目。
- `target`：药物靶点。
- `mechanism`：作用机制。
- `drug_type`：药物类型，例如单抗、ADC、小分子、化疗药等。
- `claim_id` 或 `claim_text`：用于表达“结论”与证据的对应关系。
- `evidence_strength_rule`：用于定义多来源支持、单一公司来源支持和独立监管支持。
- `conflict_type`：用于结构化记录名称、阶段、状态、时间和适应症差异。
- 恒瑞论文与 ClinicalTrials.gov 登记之间的 `parent_trial_id` 关联。
- 恒瑞 NMPA/CDE 独立监管原始记录。

### 初版禁止回答的问题

- 个体治疗选择。
- 疾病诊断。
- 药物疗效保证。
- 跨试验直接疗效排名。
- 公司投资价值判断。
- 无来源支持的未来成功概率预测。

系统遇到上述问题时，应返回边界提示，并引导用户查看已核验来源、适应症范围、证据版本和数据缺口。
