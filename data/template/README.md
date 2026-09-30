# 规范化数据目录

`data/template/` 是当前网站读取的规范化数据入口。核心表直接放在本目录：

- `sources.csv`：来源记录、来源类型、核验状态和原始链接。
- `organizations.csv`、`assets.csv`、`indications.csv`、`domains.csv`：机构、药物、适应症和研究领域实体；对应 `*_aliases.csv` 保存别名。
- `studies.csv`、`study_identifiers.csv`、`publications.csv`：研究、注册编号和论文。
- `facts.csv`、`relations.csv`：结构化事实与实体/来源关系。
- `regulatory_events.csv`、`market_events.csv`：监管及市场事件。
- `data_manifest.json`：数据集版本、表记录数和整理信息。
- `website_data_contract.json`：网站数据基线，包括表计数、来源/关系状态及 CSV 文件指纹。

## 当前网站数据

数据清单 `data_manifest.json` 的日期为 2026-09-28。当前记录数如下；修改数据后应同步更新数据清单和网站数据契约，并运行相应校验。

| 表 | 记录数 |
| --- | ---: |
| `sources` | 1,047 |
| `organizations` | 43 |
| `studies` / `study_identifiers` | 643 / 643 |
| `publications` | 402 |
| `relations` | 3,692 |
| `facts` | 7,694 |
| `assets` / `indications` / `domains` | 465 / 27 / 27 |
| `regulatory_events` / `market_events` | 3 / 0 |

该目录是从较大的规范化语料整理出的当前网站子集，不等于所有上游数据。进入网站的来源满足有效链接、核验状态及明确关系等准入条件；网站统一按已确认来源口径展示，不区分机器采集或人工整理。数量只说明当前数据集规模，不能用来推断疗效、机构实力、研发成功率或投资价值。

## 研究方向数据维护

`config/direction_catalog.json` 定义 6 个研发阶段和 20 个疾病研究方向；方向记录来自 ClinicalTrials.gov API v2 与 NCBI PubMed E-utilities。目录生成/采集脚本为 `scripts/harvest_direction_data.py`，支持按阶段或方向限定范围：

```bash
python scripts/harvest_direction_data.py --dry-run
python scripts/harvest_direction_data.py --stage 1
python scripts/harvest_direction_data.py --direction nsclc
```

采集会写入规范化表，执行前应先检查脚本选项和工作区状态，并在数据变更后审阅差异。不要把采集结果未经准入、关系检查和数据契约更新就直接发布到网站。

当前方向校验入口：

```bash
python scripts/validate_direction_dataset.py
```

校验脚本的默认参数为每个方向 30–110 条记录、来源数不超过 1,200 条、机构数不少于 40 家，并检查目录、标识、链接和跨表引用。它们是校验阈值，不是当前网站数据必须达到的精确记录数；如要更改阈值，先核对脚本参数和当前数据准入目标。

## 名称整理与历史数据

`scripts/localize_organization_names.py` 使用 `config/organization_names_zh.json` 中的明确对照维护机构中文展示名；`scripts/drop_individual_investigators.py` 根据显式名单清理被误录为机构的个人研究者。运行此类写入脚本前应阅读脚本说明、确认目标数据并检查 Git 差异。

`data/source_registry.csv` 是历史兼容资料，不是当前网站主链路的运行时输入。网站的来源检索、机构画像、时间轴、证据链和问答读取规范化数据表生成的服务数据。
