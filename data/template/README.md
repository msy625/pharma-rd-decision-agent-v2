# 医药研发规范化数据

`data/template/` 是仓库唯一的规范化数据入口。所有表直接位于本目录，不再使用 `mapped/`、`expanded_seed/` 或 `official_harvest/` 子目录。

- `sources.csv`：原始来源与核验状态。
- 实体表：`domains.csv`、`organizations.csv`、`assets.csv`、`indications.csv` 及别名表。
- 研究表：`studies.csv`、`study_identifiers.csv`、`publications.csv`。
- 证据与业务表：`facts.csv`、`relations.csv`、`regulatory_events.csv`、`market_events.csv`。

旧 NSCLC 数据已规范化写入这些表；四领域种子数据已合并。后续外部采集必须向同一套表追加，并保留 `source_id` 和核验状态。

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

- 批量采集行的 `verification_status` 统一为 `api_harvested`，
  与人工核验样本的 `verified` 严格区分。
- 每一行都保留上游标识（`NCT` 号或 `PMID`）和可直接打开的官方链接，
  可按 `source_locator` 与 `url` 回查。
- 批量采集行 **未经人工逐条复核**，不得用于疗效排名、成功率预测或投资建议。

### 校验

```bash
python scripts/validate_direction_dataset.py
```

校验项包括：目录为 6 阶段 / 20 方向、每个方向记录数落在 100–200 之间、
来源 URL 与上游标识一致、主键唯一、以及跨表引用可解析。

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
当前 793 条批量采集机构中 86 条有中文名。网站展示与筛选使用 `display_name`，
但中英文名都能检索（记录同时保留 `company_en`）。

```bash
python scripts/localize_organization_names.py                    # 应用对照表（幂等）
python scripts/localize_organization_names.py --report-unmatched # 查看未收录机构
```

## 与 `data/source_registry.csv` 的关系

`data/source_registry.csv`（39 条人工核验 NSCLC 来源）是早期 `SourceRegistryService`
的输入格式，保留在仓库中作为兼容输入，供证据中心、证据链、企业画像、事件时间轴和循证问答使用。
它对应的规范化记录同样存在于 `data/template/` 中。方向批量采集数据 **不写入** 该文件，
因此人工核验的 39 条样本口径保持不变。
