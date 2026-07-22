# Day 3 证据链关系审计与最小设计

日期：2026-07-22

## 1. 证据链目标

本设计基于当前冻结的 31 条已人工核验 NSCLC 来源，目标是为后续证据链服务和页面开发提供最小、可追溯、不过度推断的关系规则。

证据链只回答“哪些来源可以可靠归到同一项临床研究或同一条监管事件链”。不生成证据评分、成功率、疗效排名、投资判断或治疗推荐。

当前统一口径：

- 试验级证据链共 10 条：百济神州 4 条，恒瑞医药 6 条。
- 药物级监管事件链共 1 条：Tevimbra / tislelizumab EMA NSCLC 监管事件链。
- 合计 11 条证据链。
- 药物级监管链不能计入临床试验数量。
- H014 属于公司/药物级资料；当前无法确认的是 H014 与具体临床试验的一对一关系。
- B016 可作为 RATIONALE-315 相关监管背景，但不计入 NCT04379635 试验证据数量。

关系分级：

- `confirmed`：由相同 NCT 编号、明确研究编号、相同 `parent_trial_id`、明确 `study_name` 或已核验关系说明确认。
- `drug_level`：只能关联到药物、适应症、企业管线或监管状态，不能认定属于某一项具体临床试验。
- `unresolved`：当前字段不足，不能可靠建立试验级或监管级关系。

## 2. 已确认关系表

### 2.1 百济神州 / BeOne Medicines

| chain_id | chain_name | 分级 | 确认依据 | source_id | 最新或主来源 | 处理规则 |
|---|---|---|---|---|---|---|
| trial:NCT03663205 | RATIONALE-304 / NCT03663205 | confirmed | B003 `registry_id=NCT03663205`；B006、B007 `parent_trial_id=NCT03663205`；三者 `study_name=RATIONALE-304` | B003, B006, B007 | B007 | B006 为中期/首次主要结果，B007 为最终分析；B003 为登记来源；只计为 1 项唯一试验。 |
| trial:NCT03594747 | RATIONALE-307 / NCT03594747 | confirmed | B004 `registry_id=NCT03594747`；B008、B009 `parent_trial_id=NCT03594747`；三者 `study_name=RATIONALE-307` | B004, B008, B009 | B009 | B008 为中期分析，B009 为最终分析；B004 为登记来源；只计为 1 项唯一试验。 |
| trial:NCT03358875 | RATIONALE-303 / NCT03358875 | confirmed | B005 `registry_id=NCT03358875`；B010 `parent_trial_id=NCT03358875`；二者 `study_name=RATIONALE-303` | B005, B010 | B010 | B010 为预设中期分析与最终分析合并报告；B005 为登记来源；只计为 1 项唯一试验。 |
| trial:NCT04379635 | RATIONALE-315 / NCT04379635 | confirmed | B011、B012、B013 均指向 `parent_trial_id=NCT04379635` 或 `registry_id=NCT04379635`；三者 `study_name=RATIONALE-315`；B012/B013 还含 `official_study_id=BGB-A317-315`、`china_trial_id=CTR20200821` | B011, B012, B013 | B011 | B012 为 ClinicalTrials.gov 主要登记，B013 为公司试验页面，B011 为中期分析论文；三者只计为 1 项唯一试验。 |
| regulatory:tevimbra-eu-nsclc | Tevimbra / tislelizumab EMA NSCLC 监管事件链 | confirmed | B015 为 EMA EPAR 当前正式授权状态；B016 为 CHMP positive opinion；两者 `evidence_relation` 明确构成监管事件链 | B015, B016 | B015 | 这是药物级/适应症级监管链，不等同于单一临床试验证据链。B016 可作为 RATIONALE-315 治疗流程相符的监管事件背景，但不并入 trial:NCT04379635 的试验级证据计数。 |

### 2.2 恒瑞医药

当前 H001-H015 中，可以确认以下来源代表具体试验或研究项目，但多数只有单一来源，暂不能与其他来源组成多来源试验链。

| chain_id | chain_name | 分级 | 确认依据 | source_id | 最新或主来源 | 处理规则 |
|---|---|---|---|---|---|---|
| trial:NCT04818333 | SHR-A1811 / NCT04818333 | confirmed | H003 `registry_id=NCT04818333` | H003 | H003 | 可作为单来源试验链；暂无可确认配对论文或监管来源。 |
| trial:NCT03083041 | SHR-1210 + apatinib / NCT03083041 | confirmed | H004 `registry_id=NCT03083041` | H004 | H004 | 可作为单来源试验链；不得仅因 H011 同含卡瑞利珠单抗和阿帕替尼而合并。 |
| trial:NCT03668496 | CameL-Sq / NCT03668496 | confirmed | H005 `registry_id=NCT03668496`；`study_name=CameL-Sq` | H005 | H005 | 可作为单来源试验链；不得与 H008 的 CameL 长期随访合并。 |
| trial:NCT04619433 | SHR-1210 + famitinib + chemotherapy / NCT04619433 | confirmed | H006 `registry_id=NCT04619433` | H006 | H006 | 可作为单来源试验链；不得仅因 H012 同含卡瑞利珠单抗和法米替尼而合并。 |
| trial:NCT02364362 | famitinib + docetaxel / NCT02364362 | confirmed | H007 `registry_id=NCT02364362` | H007 | H007 | 可作为单来源试验链；暂无可确认配对论文。 |
| trial:SHR-A2009-301 | SHR-A2009-301 | confirmed | H015 `registry_id=SHR-A2009-301`；`study_name=SHR-A2009-301` | H015 | H015 | 可作为公司研发进展来源支持的单来源研究链；达到主要终点不等于已申报或已获批。 |

## 3. 药物级关系

以下来源只能用于药物级、适应症级、企业级或监管级展示，不能作为某个具体试验的确认来源，除非后续补充 NCT、研究编号或明确来源关系。

| source_id | 分级 | 适用范围 | 说明 |
|---|---|---|---|
| H001 | drug_level | 恒瑞肺癌研究布局、相关药物信息 | 企业官网页面，不能代表单项临床研究。 |
| H002 | drug_level | 恒瑞研发投入、创新药管线背景 | 公司年报背景资料，不能代表单项临床研究。 |
| H013 | drug_level | 恒瑞 NSCLC、SHR-A1811、SHR-A2009 管线信息 | 投资者演示材料页码范围有限；文件未明确 SHR-A1811 在 NSCLC 的具体临床期数。 |
| H014 | drug_level | 瑞康曲妥珠单抗 NSCLC 药品注册获批事件 | 公司正式公告，可记录为药品注册获批事件；不是 NMPA 原始数据库页面，也不能自动并入 H003。 |
| B001 | drug_level | 百济神州公司临床试验入口和企业名称映射 | 公司试验入口，不代表单项临床研究。 |
| B002 | drug_level | BeOne 年报中的 NSCLC 和替雷利珠单抗信息 | 公司年度报告背景资料，不能代表单项临床研究。 |
| B014 | drug_level | BeOne 当前活跃管线快照 | 管线图未列出 RATIONALE-315 不构成冲突；SCLC 项目不计入 NSCLC 比较数据。 |
| B015 | drug_level | Tevimbra / tislelizumab EMA 当前正式授权状态 | 药物级/适应症级监管资料；可说明当前授权范围，不能单独作为某项试验论文结果。 |
| B016 | drug_level | Tevimbra 围手术期 NSCLC CHMP 积极意见 | 与 RATIONALE-315 治疗流程相符，可作为监管背景；不是欧盟委员会最终批准文件，且不并入试验级证据计数。 |

## 4. 暂不能确认的关系

| source_id | 暂不能确认的关系 | 当前原因 | 最小补充办法 |
|---|---|---|---|
| H008 | 与当前 H003-H007 任一登记记录的父试验关系 | H008 只有 `study_name=CameL` 和 PMID；当前无 NCT、`parent_trial_id` 或已核验关系说明。H005 是 `CameL-Sq`，名称和人群不同。 | 补充论文原文、PubMed/ClinicalTrials.gov 交叉字段或研究登记号。 |
| H009 | 与当前 H003-H007 任一登记记录的父试验关系 | H009 为 CAP-BRAIN 论文，当前无 NCT 或 `parent_trial_id`。 | 补充 CAP-BRAIN 登记号或公司/论文原文中的研究编号。 |
| H010 | 与当前 H003-H007 任一登记记录的父试验关系 | 当前无 `study_name`、NCT 或 `parent_trial_id`。 | 补充论文原文中的登记号或研究编号。 |
| H011 | 与 H004 或其他卡瑞利珠单抗+阿帕替尼研究的关系 | H011 与 H004 药物相同但人群、线次和标题不同；当前无共同 NCT 或已核验关系。 | 补充 H011 论文登记号，核对是否对应 NCT03083041 或另一项研究。 |
| H012 | 与 H006 或其他卡瑞利珠单抗+法米替尼研究的关系 | H012 与 H006 药物组合相近，但 H006 为一线非鳞 III 期、H012 为经治单臂 II 期；当前无共同 NCT 或已核验关系。 | 补充 H012 论文登记号，核对是否对应独立研究。 |
| H014 | 与 H003 / SHR-A1811 临床试验的关系 | H014 是药品注册获批公司公告，未提供 NCT 或直接试验编号关系。 | 补充 NMPA/CDE 原始监管记录或公告中明确的关键临床试验编号。 |
| B015 | 与 RATIONALE-304/307/303/315 中任一具体试验的一对一关系 | B015 汇总多个 NSCLC 正式授权适应症，适应症覆盖多项研究场景；不能把 EPAR 当前页面拆成某一项试验来源。 | 后续如需关联到具体试验，应引入 EPAR 评审报告中的 pivotal study 编号并逐项核验。 |

## 5. 最小数据结构

后续服务层建议统一返回：

```json
{
  "chain_id": "trial:NCT03663205",
  "chain_name": "RATIONALE-304 / NCT03663205",
  "relationship_level": "confirmed",
  "company_name": "百济神州",
  "drug_names": ["替雷利珠单抗", "Tislelizumab"],
  "trial_ids": {
    "nct": ["NCT03663205"],
    "official_study_id": [],
    "china_trial_id": []
  },
  "study_status": "Completed",
  "evidence_items": [],
  "latest_item": null,
  "historical_items": [],
  "independent_items": [],
  "regulatory_items": [],
  "evidence_gaps": [],
  "risk_notes": []
}
```

字段说明：

- `chain_id`：稳定 ID。试验级优先使用 `trial:{NCT}`；无 NCT 但有明确研究编号时使用 `trial:{study_id}`；药物级监管链使用 `regulatory:{drug-or-event}`。
- `chain_name`：面向页面展示的名称，优先 `study_name + trial_id`，药物级监管链使用药物名和监管事件。
- `relationship_level`：`confirmed`、`drug_level` 或 `unresolved`。
- `company_name`：使用标准化公司中文名。
- `drug_names`：由 `drug_names` 和别名配置拆分后去重展示；不得根据药物名自动合并试验。
- `trial_ids`：保留 NCT、正式研究编号和中国登记号，支持后续去重。
- `study_status`：只取试验登记或来源明确的研究状态；不得用 `verification_status` 替代。
- `evidence_items`：链内全部来源，保留 `source_id`、`source_type`、`pmid`、`registry_id`、`parent_trial_id`、`publication_date`、`analysis_stage`、`evidence_version`、`is_latest_evidence`、`url`。
- `latest_item`：同一试验内的最新论文或当前主来源。登记来源和监管来源可以作为主来源，但不能覆盖论文版本关系。
- `historical_items`：被 `supersedes_source_id` 或 `is_latest_evidence=false` 标记的历史版本。
- `independent_items`：暂无父链关系但可独立展示的来源，例如 H008-H012。
- `regulatory_items`：监管页面、积极意见、正式授权状态或公司监管公告。
- `evidence_gaps`：缺失 NCT、缺失父试验、缺少独立监管原始记录等。
- `risk_notes`：重复计数、版本差异、来源范围受限、监管状态不能混用等提示。

## 6. 去重和版本规则

1. 同一试验去重
   - 优先用 `parent_trial_id`；为空时用 `registry_id` 中的 NCT；再看 `official_study_id`、`china_trial_id` 和已核验 `evidence_relation`。
   - 多个来源共享同一试验 ID 时，只计为 1 项唯一试验。
   - B011、B012、B013 必须作为同一项 NCT04379635 / RATIONALE-315 试验展示，不重复计数。

2. 中期论文和最终论文排序
   - 同一试验内按 `evidence_version` 和 `supersedes_source_id` 建立版本链。
   - `final` 优先于 `interim`；`interim_and_final_combined` 作为合并报告单独展示；长期随访只作为长期信息补充，不自动覆盖所有最终分析字段。
   - 若 `is_latest_evidence=false`，默认进入 `historical_items`；若为空，不等同于历史版本。

3. 药物级监管资料区分
   - B015、B016 属于 Tevimbra / tislelizumab 药物级监管事件链。
   - B016 可标记为与 RATIONALE-315 治疗流程相符的监管背景，但不能作为 trial:NCT04379635 的论文、登记或公司试验页面重复计数。
   - H014 为公司公告中的药品注册获批事件，缺少独立监管原始页面时保持 `drug_level`，并提示需补 NMPA/CDE 原始记录。

4. 未解决关系展示
   - `unresolved` 不隐藏，应在页面中作为“待补充关系”或“独立资料”展示。
   - 展示时说明缺什么字段，例如 NCT、`parent_trial_id`、研究编号或监管原始记录。
   - 不得根据标题相似、药物名称相同或大模型推测强行关联。

## 7. 风险边界

- 当前数据范围只覆盖 31 条已人工核验来源，不代表两家公司 NSCLC 全量资料。
- 来源记录数不等于唯一临床试验数；同一试验多篇论文、多页面、多监管资料必须去重。
- `verification_status` 是来源核验状态，不是临床研究状态。
- `study_status`、`authorisation_status`、`regulatory_event_type` 必须分开展示。
- 公司年报、官网、投资者材料和管线图可作为背景或公司披露来源，不能替代 ClinicalTrials.gov、PubMed 或监管机构原始资料。
- CHMP positive opinion 不等于欧盟委员会最终批准；当前正式授权状态以 B015 这类监管机构当前授权页面为准。
- 管线快照未列出某项目不能证明项目不存在、终止或撤销。
- 不做跨试验疗效比较、疗效排序、成功概率、证据评分或治疗推荐。

## 8. 下一步建议新增的服务接口和 API

服务层建议新增只读能力：

- `SourceRegistryService.build_evidence_chains()`：返回全部证据链，包含 `confirmed`、`drug_level`、`unresolved` 三类。
- `SourceRegistryService.get_evidence_chain(chain_id)`：按 `chain_id` 返回单条链。
- `SourceRegistryService.get_trial_chain(trial_id)`：按 NCT、正式研究编号或中国登记号查询试验级链。
- `SourceRegistryService.get_drug_regulatory_chain(drug_name)`：按药物名查询药物级监管链。
- `SourceRegistryService.get_unresolved_links()`：返回待补充关系和缺口字段。

FastAPI 建议新增：

- `GET /api/evidence/chains`
- `GET /api/evidence/chains/{chain_id}`
- `GET /api/evidence/trial-chain/{trial_id}`
- `GET /api/evidence/drug/{name}/regulatory-chain`
- `GET /api/evidence/unresolved-links`

页面建议最小展示：

- 证据链列表：按企业、关系分级、试验级/药物级过滤。
- 证据链详情：主试验信息、登记来源、论文版本、监管来源、独立资料和风险提示。
- 未解决关系区：列出待补字段，不把未确认关系画成已确认链路。
