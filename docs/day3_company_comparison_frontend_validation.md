# 第三天企业证据对比前端验证

## 页面结构

企业证据对比已接入“研发证据查询”内部第三个页签。当前内部页签为：

- 来源检索
- 证据链
- 企业对比

未新增侧边栏主导航，未修改旧“公司画像·对比”页面。

## 数据接口

切换到“企业对比”页签时调用：

- `GET /api/evidence/company-comparison`
- `GET /api/evidence/company-comparison/metric-rules`

默认比较对象为：

- 恒瑞医药
- BeOne Medicines

前端展示企业名称为：

- 恒瑞医药
- 百济神州 / BeOne Medicines

选择归一后相同的企业时，前端显示“请选择两个不同企业后再比较”，不发送无意义比较请求。

## 展示内容

顶部醒目显示：

> 以下结果仅反映当前收录并核验的NSCLC证据样本，不代表企业整体研发实力。

同时展示：

- 数据范围：当前31条已核验NSCLC资料
- 对比对象：恒瑞医药、百济神州/BeOne Medicines
- 不包含疗效排名、成功率预测或投资建议

核心对比区展示：

- 当前样本来源数
- 已核验来源数
- 试验级证据链数
- 药物级监管链数
- 单来源试验链数
- 多来源试验链数
- 最新版本、历史版本、独立资料
- 待确认关系数量和证据缺口
- 来源类型构成

所有数字区域标注“当前样本内”。

## 证据链入口

企业对比页中的试验链和监管链列表提供“查看证据链”按钮。点击后切换到“证据链”页签，并复用现有 `loadChainDetail()` 加载对应 `chain_id` 详情。

证据链详情接口仍由现有逻辑使用 `encodeURIComponent` 编码 `chain_id`，支持 `trial:NCT03663205` 这类包含冒号的编号。

## 风险边界

页面不使用红绿胜负色、冠军标识、排名箭头或“领先”等词。不显示评分、胜负、成功率或投资建议。

“如何理解这些数字”折叠区读取 metric-rules 接口，展示每个指标的：

- 指标名称
- 计算方法
- 正确解释
- 禁止解释

“当前数据不足”区域列出临床阶段、研究人群、治疗场景、靶点、机制、药物类型、疗效与安全性，并说明本版缺少统一结构化字段，不输出强结论。

## 验证

已执行：

```bash
.venv/bin/python webapp/frontend_src/build.py
node --check webapp/frontend_src/component.js
.venv/bin/python -m unittest tests/test_company_evidence_comparison_frontend.py
.venv/bin/python -m unittest tests/test_evidence_chain_frontend.py
.venv/bin/python -m unittest tests/test_evidence_frontend.py
.venv/bin/python -m unittest tests/test_company_evidence_comparison_api.py
```

结果：

- 构建通过，`webapp/static/index.html` 已与源码同步。
- JS 语法检查通过。
- 企业证据对比前端测试 23 个通过。
- 证据链前端回归测试 25 个通过。
- 研发证据查询前端回归测试 24 个通过。
- 企业证据对比 API 回归测试 18 个通过。

本阶段未调用 chat、workflow、advanced、大模型、Chroma 或向量模型接口。
