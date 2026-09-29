# 医药研发规范化数据

`data/template/` 是仓库唯一的规范化数据入口。所有表直接位于本目录，不再使用 `mapped/`、`expanded_seed/` 或 `official_harvest/` 子目录。

- `sources.csv`：原始来源与核验状态。
- 实体表：`domains.csv`、`organizations.csv`、`assets.csv`、`indications.csv` 及别名表。
- 研究表：`studies.csv`、`study_identifiers.csv`、`publications.csv`。
- 证据与业务表：`facts.csv`、`relations.csv`、`regulatory_events.csv`、`market_events.csv`。

当前目录保存网站的根数据集：从原规范化语料中选出 1,370 条可展示来源和 225 家机构。入选来源必须有有效 URL、核验状态和明确已确认关系；无关系或含未解决关系的来源不进入网站展示。后续外部采集需先经过同一准入规则，才可加入这些表。

`website_data_contract.json` 是当前网站数据基线：固化表计数、来源核验状态构成、关系状态构成与每张 CSV 的 SHA-256 指纹。任何数据更新都必须同步更新该契约和 `data_manifest.json`，并重新通过离线校验；不能用来源数量推断机构实力、疗效、成功率或投资结论。

## 方向批量采集（direction_harvest_v1.0）

按 `config/direction_catalog.json` 定义的 **6 个研发阶段 / 20 个疾病方向**，通过官方接口批量采集：

| 接口 | 用途 | 官方地址 |
| --- | --- | --- |
| ClinicalTrials.gov API v2 | 临床试验注册记录 | <https://clinicaltrials.gov/api/v2/studies> |
| NCBI PubMed E-utilities | 期刊论文 | <https://eutils.ncbi.nlm.nih.gov/entrez/eutils> |

```bash
# 全部 20 个方向（默认每个方向 150 条记录）
python scripts/harvest_direction_data.py

# 只跑第 1 阶段 / 单个方向
python scripts/harvest_direction_data.py --stage 1
python scripts/harvest_direction_data.py --direction nsclc

# 只报告不写盘
python scripts/harvest_direction_data.py --dry-run
```

采集脚本幂等：以 `source_id` / `study_id` / `publication_id` 等主键合并，
采集表（`sources`、`studies`、`publications`、`facts`、`relations` 等）同 id 覆盖以反映上游状态变化；
参考表（`domains`、`indications`、`organizations`、`assets` 及别名表）为 **只写入不覆盖**，
不会改写人工维护的既有行。

### 核验口径

- 所有进入网站根数据集的来源统一使用 `verification_status=verified`，
  网站不区分来源的采集方式，均按人工核验口径展示。
- 每一行都保留上游标识（`NCT` 号或 `PMID`）和可直接打开的官方链接，
  可按 `source_locator` 与 `url` 回查。
- 来源仍保留上游标识和原始链接；任何来源都不得用于疗效排名、成功率预测或投资建议。

### 校验

```bash
python scripts/validate_direction_dataset.py
```

校验项包括：目录为 6 阶段 / 20 方向、全库来源数在 1200–1500、去重后机构数在 150–300、每个方向记录数落在 40–110 之间、来源 URL 与上游标识一致、主键唯一、以及跨表引用可解析。

### 数据字典补充

`domains.csv` 中新增两类 `domain_type`：

- `research_stage`：6 个研发阶段（`DOM_STAGE_1` … `DOM_STAGE_6`），`description` 记录该阶段目标。
- `disease_research_domain`：20 个疾病方向，`parent_domain_id` 指向所属阶段。

`facts.csv` 中批量采集行使用的谓词包括
`research_direction`、`official_title`、`study_status`、`study_phase`、`lead_sponsor`、
`enrollment_count`、`condition`、`intervention`、`start_date`、
`publication_title`、`journal`、`publication_type`、`publication_date`、`doi`。

`relations.csv` 中批量采集行使用
`source_describes_study`、`source_describes_publication`、`source_about_org`、
`source_about_indication`、`source_mentions_asset`。

### 机构中文名

ClinicalTrials.gov 的 `leadSponsor.name` 是自由文本，批量采集到的机构名以英文原样入库。
`config/organization_names_zh.json` 维护**权威中文名对照表**，由
`scripts/localize_organization_names.py` 应用：

- `organizations.csv` 的 `display_name` 改为 `中文名（English short name）`；
- `organization_aliases.csv` 增加一条 `language=zh`、`alias_type=display_name` 的别名；
- `canonical_name` **保持不变**，因为它仍是 `facts`/`relations` 的连接键。

只收录确实存在权威中文名的机构。**不做机器翻译，也不生成推测译名**：
未收录的机构（多为欧美医院、大学、小型生物科技公司和合作研究组织）继续保留英文原名。
当前 793 条批量采集机构中 **154 条**有中文名，包括跨国药企、中国生物科技公司、
中国医院与大学（如 北京协和医院、复旦大学、华中科技大学同济医学院附属同济医院、
中山大学附属第一医院、香港中文大学）。网站展示与筛选使用 `display_name`，
但中英文名都能检索（记录同时保留 `company_en`）。

```bash
python scripts/localize_organization_names.py                    # 应用对照表（幂等）
python scripts/localize_organization_names.py --report-unmatched # 查看未收录机构
```

### 个人研究者条目清理

`leadSponsor.name` 是自由文本，部分注册研究由**个人研究者**发起，其姓名被当成机构写入
`organizations.csv`，并出现在网站申办方筛选里。`config/individual_investigator_names.json`
逐条列出这类姓名，由 `scripts/drop_individual_investigators.py` 清理：

- 删除 `organizations.csv` 对应行及其别名；
- 删除 `relations.csv` 中指向它们的 `source_about_org` 关系；
- 清空 `studies.csv` 中受影响研究的 `sponsor_org_id`（研究记录本身保留）；
- `facts.csv` 中 `predicate=lead_sponsor` 的断言**保留**，因为它如实记录了注册库的说法。

使用**显式清单**而不是姓名形状启发式：启发式会把 `Kaiser Permanente`、
`Pierre Fabre Dermo Cosmetique`、`UMC Utrecht`、`Universidad Rey Juan Carlos`、
`Ziekenhuis Oost-Limburg` 等缺少英文机构后缀的真实机构误判为个人。
这些机构已单独登记在配置文件的 `reviewed_real_organizations_not_in_the_list` 中，
并有测试保证它们不会被删除。

```bash
python scripts/drop_individual_investigators.py --report  # 只列出将删除的条目
python scripts/drop_individual_investigators.py           # 执行清理（幂等）
```

## 与 `data/source_registry.csv` 的关系

`data/source_registry.csv` 是历史兼容资料，不是网站或 FastAPI 的运行时输入。证据中心、企业画像、对比、时间轴和循证问答均从本目录的规范化表投影数据；历史文件仅供追溯旧版本和兼容工具使用。
