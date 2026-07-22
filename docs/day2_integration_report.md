# Day 2 集成验收报告

日期：2026-07-22

## 完成功能

- 完成第一版统一证据查询服务，作为 CSV 来源登记表的只读查询入口。
- 完成 FastAPI 证据查询接口，向 Web 前端提供 7 类 `/api/evidence/*` 只读接口。
- 完成 Web 端“研发证据查询”页面，接入现有网站导航，支持列表查询、详情查看、证据版本标签和风险提示展示。
- 完成“排除历史版本”交互：勾选后立即重新查询，只排除明确历史版本，保留最新版本和独立资料。
- 完成浏览器人工验收，未发现异常。

## 调用关系

```text
data/source_registry.csv
        ↓
deepinsight.core.source_registry_service.SourceRegistryService
        ↓
webapp.main FastAPI /api/evidence/*
        ↓
webapp/frontend_src/component.js
        ↓
webapp/frontend_src/template.html
        ↓
webapp/static/index.html
```

Web 页面只调用证据查询接口，不调用大模型、Chroma、向量模型、chat、workflow 或 advanced 接口完成证据查询。

## 证据 API 接口

- `GET /api/evidence/summary`
- `GET /api/evidence/search`
- `GET /api/evidence/company/{name}`
- `GET /api/evidence/drug/{name}`
- `GET /api/evidence/trial/{trial_id}`
- `GET /api/evidence/study/{name}`
- `GET /api/evidence/source/{source_id}`

## 浏览器人工验收

| 项目 | 结果 |
| --- | --- |
| 导航新增“研发证据查询”且位置正确 | 通过 |
| 默认加载统计和 NSCLC 查询结果 | 通过 |
| 6 种查询模式可操作 | 通过 |
| 查询结果列表可点击并加载详情 | 通过 |
| 空结果、加载中、错误提示位置正常 | 通过 |
| 外链在新窗口打开并保留安全属性 | 通过 |
| 原有页面和导航未发现异常 | 通过 |

## 证据版本状态验证

| 来源ID | 预期状态 | 验证结果 |
| --- | --- | --- |
| B006 | 历史版本 | 通过 |
| B007 | 最新版本 | 通过 |
| H007 | 独立资料 | 通过 |
| H013 | 独立资料 | 通过 |

`RATIONALE-304` 未勾选“排除历史版本”时包含 B006 和 B007；勾选后隐藏 B006，保留 B007。`NSCLC` 勾选后仍保留 H007、H013，并显示为“独立资料”。

## 监管状态验证

| 来源ID | 预期状态 | 验证结果 |
| --- | --- | --- |
| B015 | EMA EPAR 当前授权页面，`authorisation_status=欧盟正式授权` | 通过 |
| B016 | CHMP positive opinion，不等于欧盟委员会最终批准 | 通过 |

B015 和 B016 属于同一监管事件链的不同阶段，不作为互相冲突的结论展示。

## 当前限制

- 第一版数据范围固定为 NSCLC、恒瑞医药、百济神州/BeOne Medicines 和 31 条人工核验来源。
- Web 页面目前是检索与详情展示闭环，尚未实现完整管线比较图和引用分析报告生成。
- 页面不提供治疗建议、投资判断、成功概率、随机评分或固定评分。
- 后续新增资料应进入补充版本，不直接改变第一版冻结数据口径。

## 后续计划

- 基于当前证据接口继续实现管线比较和问题集驱动的证据分析页面。
- 增加浏览器端自动化回归，覆盖主要查询路径和响应式布局。
- 在保持证据编号和来源链接可追溯的前提下，逐步接入报告生成链路。
