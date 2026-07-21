# 数据字典

## 1. 标题字段

| 字段 | 含义 | 填写规则 |
|---|---|---|
| `original_title_en` | 来源页面中的原始英文标题 | 仅保存 ClinicalTrials.gov 或 PubMed 页面提供的英文原题，不使用机器翻译结果冒充原题。企业中文官网或中文报告没有英文原题时可留空。 |
| `original_title` | 来源页面或文件封面显示的原始标题 | 用于兼容中英文来源，按来源原文保存，不翻译、不改写。 |
| `original_language` | 原始标题语言 | 使用 `zh`、`en` 等语言代码。按来源实际显示语言填写。 |
| `normalized_title_zh` | 便于项目内统一检索和展示的规范中文描述 | 使用简洁中文概括研究药物、研究人群和研究类型；这是人工规范化描述，不等同于来源原题。 |

## 2. 状态字段

| 字段 | 含义 | 填写规则 |
|---|---|---|
| `verification_status` | 数据来源核验状态 | 表示来源链接和记录是否已经人工打开核验。例如“已人工核验”。 |
| `study_status` | 临床研究状态 | 表示 ClinicalTrials.gov 等来源显示的研究状态。例如 `Terminated`、`Completed`、`Unknown`。该字段不得与 `verification_status` 混用。 |

## 3. 研究描述字段

| 字段 | 含义 | 填写规则 |
|---|---|---|
| `study_name` | 研究简称或试验名称 | 例如 CameL、CAP-BRAIN。来源或论文未明确名称时可留空。 |
| `population` | 研究对象 | 记录疾病分型、治疗线数、基因状态、脑转移等关键入组人群信息。不得把特定人群泛化为全部 NSCLC 患者。 |
| `intervention` | 干预或治疗方案 | 记录具体药物组合或研究干预，避免只写“联合化疗”等过于笼统的描述。 |
| `drug_names` | 药物名称集合 | 中文名、英文名和研发代号用分号分隔，便于后续检索和别名合并。 |
| `study_phase` | 研究分期 | 按来源记录填写，例如 Phase 1、Phase 2、Phase 3。无法确认时留空。 |
| `source_pages` | 来源文件中的相关页码 | 适用于 PDF、演示材料、年报等多页文件。多个页码用分号分隔，例如 `20;28;29;30`。 |
| `publication_date` | 来源发布日期或公告日期 | 按来源显示格式记录。无法确认时留空，不从其他材料推断。 |
| `announcement_number` | 公告编号 | 适用于公司公告、交易所公告等正式公告来源。无公告编号时留空。 |
| `company_current_name` | 企业当前标准英文名称 | 用于企业归一化。例如百济神州统一使用 `BeOne Medicines`。 |
| `company_former_name` | 企业历史英文名称 | 用于保留新旧名称映射。例如 `BeiGene`。 |
| `company_display_name` | 展示用企业名称 | 用于页面或报告展示，例如“百济神州（BeOne Medicines，原BeiGene）”。 |
| `sponsor_original` | 来源页面显示的原始申办方名称 | 按来源原文保存。例如早期 ClinicalTrials.gov 试验可显示为 `BeiGene`，但标准企业名称仍归一到 `BeOne Medicines`。 |
| `histology` | NSCLC 组织学分型 | 记录鳞状、非鳞状、鳞状和非鳞状、来源未明确等。 |
| `treatment_line` | 治疗线数 | 记录一线、二线或三线、经治等，不从来源外推断。 |
| `comparator` | 对照组 | 记录对照治疗方案；无对照组或来源未明确时留空或写“来源未明确”。 |
| `regimen_detail` | 方案细节 | 记录剂量、给药频率、周期和试验组/对照组差异，避免把不同化疗方案混为一种。 |
| `biomarker_requirements` | 生物标志物或分子人群限制 | 记录 EGFR、ALK、HER2、PD-L1 等入排标准或人群特征；这些不作为药物名称记录。 |
| `parent_trial_id` | 论文或资料关联的父级临床试验登记号 | 用于把 PubMed 论文与 ClinicalTrials.gov 试验连接起来，例如 `NCT03663205`。同一试验的中期和最终分析应使用相同 `parent_trial_id`。 |
| `pmid` | PubMed 论文编号 | 仅适用于 PubMed 来源，填写数字编号，不包含 URL。 |
| `publication_type` | PubMed 页面显示的出版类型 | 按 PubMed 元数据保存，多个类型用分号分隔。 |
| `analysis_stage` | 论文报告的分析阶段 | 记录中期分析、最终分析、预设中期分析与最终分析合并报告等。不得把论文分析阶段等同于临床研究状态。 |
| `evidence_version` | 证据版本标识 | 用于程序检索，例如 `interim`、`final`、`interim_and_final_combined`。 |
| `supersedes_source_id` | 当前证据替代或延续的早期来源编号 | 例如 B007 是 B006 的后续最终分析版本时填写 `B006`。无明确替代关系时留空。 |
| `is_latest_evidence` | 是否为当前试验已入库来源中的最新证据版本 | 使用 `true` 或 `false`。该字段只表示入库证据版本关系，不代表研究结论优劣。 |
| `primary_endpoints` | 主要终点 | 按来源或人工核验结果记录 PFS、OS、MPR、EFS 等主要终点，可用分号分隔。 |
| `secondary_endpoints` | 次要终点 | 按来源或人工核验结果记录次要终点；来源未明确或本轮未核验时留空。 |
| `online_publication_date` | 论文在线发表日期 | 适用于 PubMed 或期刊页面显示的在线发表日期，使用 `YYYY-MM-DD`。该字段与期刊卷期年份可能不同。 |
| `issue_year` | 论文所属期刊卷期年份 | 记录期刊卷期对应年份，例如 B011 在线发表于 2024-11-21，但卷期年份为 2025。 |
| `journal` | 期刊名称 | 按 PubMed 元数据中的期刊名称保存，不自行改写。 |
| `doi` | 数字对象标识符（Digital Object Identifier） | 按 PubMed 元数据保存 DOI；缺失时留空，不编造。 |
| `official_study_id` | 来源显示的正式研究编号 | 例如 ClinicalTrials.gov 的 `BGB-A317-315`。不得用内部编号替代来源正式编号。 |
| `china_trial_id` | 中国临床试验登记号 | 例如 `CTR20200821`。仅在来源明确显示时填写。 |
| `enrollment_actual` | 实际入组人数 | 按 ClinicalTrials.gov 等来源显示填写，只保存已核验数值。 |
| `regulatory_authority` | 监管机构 | 例如 `European Medicines Agency（EMA）` 或 `EMA/CHMP`。 |
| `regulatory_event_type` | 监管事件类型 | 例如 `EPAR current authorisation status`、`CHMP positive opinion`。事件类型不得与最终批准状态混用。 |
| `authorisation_status` | 授权状态 | 记录来源显示的当前授权状态，例如“欧盟正式授权”。 |
| `marketing_authorisation_holder` | 上市许可持有人 | 按监管来源原文保存，例如 `BeOne Medicines Ireland Limited`。 |
| `source_last_updated` | 来源页面最后更新日期 | 适用于监管页面、数据库页面等会更新的来源。 |
| `data_cutoff_date` | 数据截止日期 | 适用于公司管线快照、报告或演示材料。该日期不等于核验日期。 |
| `evidence_relation` | 与其他证据的关系 | 记录同一试验多来源、论文版本链或监管事件链，例如“B011/B012/B013 对应同一项 RATIONALE-315 试验”。 |
| `scope_limitation` | 来源使用范围限制 | 记录管线图展示范围、疾病分类方式、不得外推的边界等。 |

## 4. 药物名称规则

| 规范名称 | 英文名或类别 | 研发代号 |
|---|---|---|
| 卡瑞利珠单抗 | Camrelizumab | SHR-1210 |
| 阿帕替尼 | Apatinib | 无 |
| 法米替尼 | Famitinib | 无 |
| 瑞康曲妥珠单抗 | Trastuzumab rezetecan | SHR-A1811 |
| SHR-A2009 | HER3 ADC | SHR-A2009 |
| 多西他赛 | Docetaxel | 无 |
| 培美曲塞 | Pemetrexed | 无 |
| 卡铂 | Carboplatin | 无 |
| 替雷利珠单抗 | Tislelizumab | BGB-A317 |
| TEVIMBRA | Tislelizumab | BGB-A317 |
| 顺铂 | Cisplatin | 无 |
| 紫杉醇 | Paclitaxel | 无 |
| 白蛋白结合型紫杉醇 | Nab-paclitaxel | 无 |

EGFR 和 ALK 不作为药物名称记录；它们属于生物标志物或研究人群特征，应放入 `population`、`normalized_title_zh` 或备注字段中。

## 5. 进展状态规则

- “达到主要终点”表示研究在指定分析中达到预设主要终点，不等于“提交上市申请”。
- “提交上市申请”表示企业或监管系统显示已递交上市申请，不等于“获批上市”。
- “获批上市”表示监管批准或公司正式公告确认获批。
- 三个状态必须分开记录，不得互相替代。
- 来源没有明确给出的临床阶段不得推断；例如 H013 没有明确 SHR-A1811 在 NSCLC 适应症上的具体临床期数时，`study_phase` 应留空或写“文件未明确”。
- NCT04619433 的研究状态为已终止（Terminated），但其来源资料已经人工核验；`study_status` 与 `verification_status` 不得混用。
- SHR-A2009-301 仅确认 III 期研究期中分析达到主要终点，不能据此认定已经申报或获批上市。
- `Completed` 是 ClinicalTrials.gov 等来源显示的临床研究状态；“已人工核验”是人工打开来源并确认记录可用的核验状态。两者不得互相替代。
- 论文来源记录数不等于唯一临床试验数。比如同一项 RATIONALE-304 试验可以同时有中期分析论文和最终分析论文，来源记录为 2 条，但唯一临床试验仍为 1 项。
- PubMed 论文的 `analysis_stage`、`evidence_version` 和 `is_latest_evidence` 用于表达证据版本关系，不得改写成治疗建议、疗效排名或药物优劣判断。
- 同一临床试验可以有论文、ClinicalTrials.gov 登记和公司试验页面三类来源。B011、B012、B013 均关联 `NCT04379635`，只计为一项 RATIONALE-315 唯一试验。
- 监管事件链需要按时间和状态分开记录。CHMP positive opinion 是积极意见，不等同于欧盟委员会最终批准；EMA EPAR 当前授权页面可记录为当前正式授权状态。
- 公司当前管线图是特定截止日期的快照，不能单独作为历史研究不存在、撤销或来源冲突的依据。

## 6. 缺失值规则

- 未从来源页面确认的字段不得猜测。
- 无法确认的字段留空或写“待确认”。
- PubMed 论文没有明确临床研究状态时，`study_status` 可留空。
- 结构化字段后续可以补充，但必须保留来源、核验日期和证据编号。
