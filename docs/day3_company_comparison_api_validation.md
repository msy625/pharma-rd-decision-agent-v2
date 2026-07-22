# 第三天企业证据对比 API 验证

## 新增接口

| 接口 | 用途 |
| --- | --- |
| `GET /api/evidence/company-comparison` | 返回两个企业在当前收录样本内的证据覆盖对比 |
| `GET /api/evidence/company-comparison/metric-rules` | 返回指标计算规则、正确解释和禁止解释 |

`metric-rules` 使用静态路径，并位于现有证据查询动态路由之前，避免被其他动态路由误匹配。

## 响应结构

`GET /api/evidence/company-comparison` 返回：

```json
{
  "comparison": {},
  "metadata": {
    "data_scope": "first_version_nsclc_hengrui_beone",
    "interpretation_scope": "current_verified_sample_only"
  }
}
```

`GET /api/evidence/company-comparison/metric-rules` 返回：

```json
{
  "items": [],
  "count": 0
}
```

## 错误处理

| 场景 | 返回 |
| --- | --- |
| 企业名称为空 | 400 |
| 两个企业名称归一后相同 | 400 |
| 不存在企业 | 200，返回空企业画像和“当前数据不足”提示 |
| 数据或配置缺失 | 503 |
| CSV/JSON 结构异常 | 503 |
| 未知异常 | 友好 500，不暴露绝对路径、堆栈或密钥 |

## 解释边界

API 只返回当前已核验 NSCLC 样本内的结构化覆盖，不输出综合评分、排名、优胜方、成功率、疗效/安全性优劣或投资建议。

旧 `/api/compare` 的财务、风险、专利和雷达类结果未复用于本接口。

## 验证

已执行：

```bash
.venv/bin/python -m unittest tests/test_company_evidence_comparison_api.py
```

结果：18 个测试通过，使用真实 ASGI 层轻量客户端，不调用真实网络。
