# 第一天查询验证报告

## 基本信息

- 执行日期：2026-07-21
- Python版本：Python 3.12.3
- 数据文件：`data/source_registry.csv`
- 别名配置：`config/entity_aliases.json`
- 总来源数：31条
- 企业来源数：恒瑞医药15条；百济神州16条

## 验证命令

| 命令 | 结果 | source_id摘要 |
|---|---|---|
| `python3 scripts/validate_source_registry.py` | 通过 | H001-H015、B001-B016完整，共31条 |
| `python3 scripts/query_source_registry.py --summary` | 通过 | 总数31；恒瑞医药15；百济神州16；百济唯一NSCLC试验4项 |
| `python3 scripts/query_source_registry.py --company "恒瑞医药" --format table` | 通过 | H001-H015 |
| `python3 scripts/query_source_registry.py --company "BeOne Medicines" --format table` | 通过 | B001-B016 |
| `python3 scripts/query_source_registry.py --trial-id NCT03663205 --format table` | 通过 | B003、B006、B007 |
| `python3 scripts/query_source_registry.py --trial-id NCT04379635 --format table` | 通过 | B011、B012、B013 |
| `python3 scripts/query_source_registry.py --text NCT04619433 --format table` | 通过 | H006 |
| `python3 scripts/query_source_registry.py --drug SHR-1210 --format table` | 通过 | H001、H002、H004、H005、H006、H008、H009、H010、H011、H012 |
| `python3 scripts/query_source_registry.py --study-name RATIONALE-304 --latest-only --format json` | 通过 | B003、B007 |
| `python3 -m unittest tests/test_source_registry_query.py` | 通过 | 13项测试通过 |

## 自动测试结果

- 测试命令：`python3 -m unittest tests/test_source_registry_query.py`
- 结果：13项测试通过
- 覆盖内容：来源数、编号唯一性、企业统计、关键试验关联、Terminated状态、药物别名、空结果、JSON合法性、latest-only、监管状态区分和SCLC管线范围限制。

## 已发现并处理的问题

| 问题 | 处理 |
|---|---|
| H008-H012为PubMed来源，但`pmid`字段为空。 | 从现有`registry_id`和PubMed链接中补齐对应PMID字段，未改变论文事实内容。 |
| H013字段错位，导致`url`列保存为核验日期。 | 补回缺失空列，使`verification_status`、`url`、`verified_at`、`source_pages`回到正确字段。 |
| B001字段错位，导致`url`列为空。 | 补回缺失空列，使公司临床试验官网链接和核验状态进入正确字段。 |
| 项目没有独立药物别名配置。 | 新建`config/entity_aliases.json`，保存已人工确认的药物中英文名、商品名和研发代号映射。 |

## 当前限制

- 查询工具直接读取CSV，不连接数据库、向量索引或Web主链路。
- `--latest-only`当前按`is_latest_evidence=false`排除旧论文版本；登记、监管和公司来源等非版本记录会保留。
- 药物别名仅覆盖当前已人工确认的名称，不自动推断新别名。
- B014为公司当前管线快照，含SCLC项目说明，但不进入NSCLC项目比较结果。
- 当前不进行PFS、OS、MPR或EFS数值比较，也不生成治疗建议、疗效排名或投资判断。

## 最终结论

31条人工核验资料已完成结构校验，能够支持按企业、药物、试验、论文、研究状态和证据版本进行最小查询。
