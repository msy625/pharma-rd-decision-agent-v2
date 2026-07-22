# 第三天企业证据对比服务层验证

## 范围

本阶段新增 `deepinsight/core/company_evidence_comparison_service.py`，用于基于当前已核验 NSCLC 证据样本比较恒瑞医药与百济神州/BeOne Medicines 的结构化证据覆盖。

服务只复用：

- `SourceRegistryService`
- `EvidenceChainService`

未重复实现 CSV 读取、企业别名配置解析或证据链关系逻辑。

## 公开接口

| 方法 | 用途 |
| --- | --- |
| `company_profile(company_name)` | 返回单个企业在当前收录样本内的证据覆盖画像 |
| `compare(company_a, company_b)` | 返回两个企业的结构化证据样本对比 |
| `metric_rules()` | 返回指标计算方法、正确解释和禁止解释 |
| `available_companies()` | 返回当前支持的归一化比较主体 |

## 企业归一化

当前支持两个比较主体：

- 恒瑞医药
- 百济神州/BeOne Medicines

`百济神州`、`BeOne Medicines`、`BeiGene` 归一为同一比较主体，不重复计数。

## 当前计算结果

所有数量均为当前收录样本内动态计算结果：

| 企业 | 来源 | 已核验来源 | 试验链 | 监管链 | 单来源试验链 | 多来源试验链 | 待确认关系 | 版本构成 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 恒瑞医药 | 15 | 15 | 6 | 0 | 6 | 0 | 6 | 最新 0；历史 0；独立 15 |
| 百济神州/BeOne Medicines | 16 | 16 | 4 | 1 | 0 | 4 | 1 | 最新 4；历史 2；独立 10 |

## 边界

服务返回固定解释边界：

> 以下结果仅反映当前收录并核验的NSCLC证据样本，不代表企业整体研发实力。

服务不生成综合评分、排名、优胜方、成功率、疗效/安全性优劣或投资建议，也不自动推断研究人群、治疗场景、靶点或机制。

## 验证

已执行：

```bash
.venv/bin/python -m unittest tests/test_company_evidence_comparison_service.py
```

结果：17 个测试通过。
