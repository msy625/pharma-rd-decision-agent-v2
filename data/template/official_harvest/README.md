# official_harvest_v1

此目录是四个领域的官方批量采集落盘位置。它独立于 `expanded_seed/` 和当前运行中的 `data/source_registry.csv`，生成后需要先做审阅与二次筛选，不能直接用于临床或商业结论。

## 覆盖范围

- 乳腺癌
- 结直肠癌
- 胃癌/食管癌
- 肥胖/2型糖尿病

采集器只读取两个官方结构化来源：ClinicalTrials.gov v2（试验登记）和 NCBI PubMed E-utilities（论文元数据与摘要）。每条标准化记录都有 `source_id`，原始响应保存在 `raw/`，并以 `content_hash` 固化版本。

## 运行

在项目根目录执行：

```bash
python3 scripts/harvest_official_medical_data.py --per-domain 60
```

默认每个领域最多 60 条 ClinicalTrials.gov 登记研究、60 篇 PubMed 文献。胃癌/食管癌与肥胖/2 型糖尿病的多个登记检索式均分这 60 条配额，以保证两个子领域都有覆盖。四领域总计最多约 240 条研究登记和 240 篇论文；实际数量可能因重复记录而略少。

```bash
python3 scripts/harvest_official_medical_data.py --per-domain 10
```

## 生成物与边界

- 生成所有模板 CSV、`harvest_manifest.json`、以及 `raw/*.jsonl`。
- ClinicalTrials.gov 中的 condition 和 intervention 名称保持原文；不会推断靶点、药物类别、企业权属或竞争关系。
- PubMed 论文只有在标题或摘要明确出现 NCT 编号时才关联到研究；其他论文保留为未关联研究证据。
- 领域检索用于召回，不等价于精确疾病亚型。对外展示或分析前必须按 `registered_conditions` 或论文摘要做二次纳入排除。
