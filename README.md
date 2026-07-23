# 药研制策（Pharma R&D Decision Agent）

> 面向医药研发情报分析的多源证据检索与管线决策支持系统

“药研制策”面向医药研发信息检索与比较场景，围绕特定疾病整合企业研发管线、临床试验、医学论文、监管信息和企业公开资料，帮助使用者快速了解研发进展、比较企业布局，并追溯分析结论所依据的公开证据。

本项目当前处于比赛初版开发阶段。第一版范围已冻结：初版聚焦 **1 个疾病/适应症、2 家医药企业和一条可稳定演示的分析闭环**，不追求大规模数据覆盖。

## 项目目标

- 统一整理药物、适应症、临床阶段、试验状态和来源信息。
- 对比两家企业在同一疾病方向上的研发管线布局。
- 组合结构化查询、字段过滤和向量检索定位相关证据。
- 基于真实检索结果生成带引用的分析摘要。
- 提示证据不足、信息过期、来源冲突和研发阶段风险。
- 在无数据或证据不足时返回明确提示，不生成虚构结论。

## 初版核心流程

```text
选择疾病与企业
      ↓
查看研发管线对比
      ↓
检索临床试验、论文、监管与企业资料
      ↓
生成基于证据的差异分析与风险提示
      ↓
查看证据编号、原始链接并导出报告
```

## 初版功能

| 模块 | 主要内容 | 当前状态 |
| --- | --- | --- |
| 研发管线对比 | 展示药物、适应症、临床阶段和试验状态 | 规划开发 |
| 证据中心 | 汇总试验、论文、公告和原始链接 | 规划开发 |
| 风险提示 | 标记证据缺失、时效性和来源冲突 | 规划开发 |
| 引用分析报告 | 根据检索证据生成带编号引用的比较结论 | 规划开发 |
| 数据与检索底座 | SQLite、Chroma、FastAPI及基础导入流程 | 已具备 |
| 研发证据查询 | Web 页面按关键词、企业、药物、临床试验、研究名称和来源ID检索31条人工核验证据 | 已完成 |
| 基础工程稳定性 | 空数据处理、延迟加载、缓存兼容和测试隔离 | 已完成 |

> 功能状态会随开发进度更新。README 中不会将规划功能描述为已经完成。

## 初版数据范围

- 疾病/适应症：非小细胞肺癌（NSCLC）。
- 比较企业：恒瑞医药、百济神州（BeOne Medicines，原BeiGene）；第一版数据可用性检查已经完成。
- 临床试验：计划整理 10–20 条。
- 医学论文：计划整理 10–20 篇。
- 监管信息：计划整理 5–10 条。
- 企业资料：每家计划整理 1–2 份年报、公告或官方管线资料。

每条事实至少记录：规范名称、内容类型、发布日期或更新时间、来源机构、原始链接、采集时间和证据编号。`source_count` 与 `source_types` 根据实际来源计算，不使用固定值。

当前恒瑞医药数据可用性检查结果：累计已人工核验资料 15 条，包含官方研发管线及肺癌研究资料 3 条、年度报告 1 份、ClinicalTrials.gov 试验 5 条、PubMed 相关论文 5 篇、公司药品注册批准正式公告 1 份。来源覆盖公司官网、年度报告、ClinicalTrials.gov 临床试验登记、PubMed 论文、投资者管线材料和公司正式公告。后续仍需补充 NMPA/CDE 等独立监管数据库原始记录。

当前百济神州数据可用性检查结果：累计来源记录 16 条，包含公司临床试验入口/页面 2 条、年度报告 1 份、ClinicalTrials.gov 登记 4 条、PubMed 论文 6 篇、公司当前管线材料 1 份、EMA 监管资料 2 条。百济神州当前涉及 4 项唯一 NSCLC 试验：RATIONALE-303、RATIONALE-304、RATIONALE-307、RATIONALE-315；来源记录数不等于唯一试验数。BeOne Medicines 为当前标准英文名称，BeiGene 为历史英文名称或部分早期试验中的原始申办方名称，两者统一归入百济神州。

第一版数据范围：恒瑞医药 15 条、百济神州 16 条，共 31 条人工核验来源。现有来源覆盖公司官网、年度报告、ClinicalTrials.gov、PubMed 论文、公司管线材料、公司正式公告及 EMA 独立监管资料，能够支持 NSCLC 研发管线、试验阶段、研究人群、证据版本和监管状态的初版比较。后续新增资料进入补充版本，不再影响初版开发主链路。

## 研发证据查询

Web 端已接入“研发证据查询”页面，用于查询第一版冻结的 31 条人工核验 NSCLC 资料。该页面包含四个内部页签：

- 来源检索
- 证据链
- 企业对比
- 循证问答

“来源检索”支持 6 种查询方式：

- 关键词查询
- 企业查询
- 药物查询
- 临床试验编号查询
- 研究名称查询
- 来源ID查询

页面中的“排除历史版本”表示：只排除同一研究中已经被后续资料替代的历史版本，保留最新版本和没有版本关系的独立资料。证据版本标签分为三类：

- 最新版本：`is_latest_evidence` 明确为 true、`"true"`、1 或 `"1"`。
- 历史版本：`is_latest_evidence` 明确为 false、`"false"`、0 或 `"0"`。
- 独立资料：`is_latest_evidence` 为空、未填写或不属于上述明确状态，表示该资料没有版本替代关系。

“证据链”用于把同一试验的登记、论文和监管背景关联展示，并区分最新版本、历史版本、独立资料和监管资料。监管背景不重复计入临床试验数量，页面同时展示证据缺口和待确认关系。

“企业对比”仅比较当前已核验 NSCLC 样本，展示来源覆盖、证据链、版本构成和待确认关系。该对比不代表企业整体研发实力，不提供疗效排名、成功率预测、综合评分或投资建议。

“循证问答”复用同一套本地证据服务，流程为：

```text
用户问题
  ↓
安全规则
  ↓
本地证据检索
  ↓
DeepSeek组织答案
  ↓
引用校验
  ↓
返回回答、引用、限制和白盒过程
```

循证问答支持两种模式：

- `auto`：DeepSeek 可用时智能生成，失败自动回退本地摘要。
- `local`：只使用本地结构化证据，不调用模型。

安全边界：不提供诊断、个体治疗建议、疗效保证、跨试验排名、成功率预测或投资建议。

上述证据查询、证据链、企业对比和循证问答功能均基于本地 CSV/JSON 配置和 FastAPI 只读服务；只有循证问答 `auto` 模式在本地配置 DeepSeek 后才会尝试调用模型。

## 研发决策工作台

默认首页已重构为“研发决策工作台”，用于展示当前核验证据样本的真实覆盖情况。该页只调用 `/api/evidence/workbench`，不再依赖旧 `/api/bootstrap`、`/api/dashboard` 或 `/api/profile` 初始化。

工作台动态展示 9 项核心指标：

- 总来源。
- 已核验来源、企业主体、试验级证据链、药物级监管链。
- 最新资料、历史版本、独立资料和待确认关系。
- 恒瑞医药与百济神州/BeOne Medicines 的证据覆盖卡片。
- 来源类型构成、研究状态构成、当前数据缺口。
- 数据版本、最新核验日期和响应生成时间。

旧 `data/enterprise_analysis.db` 当前为空，旧 Chroma 数据也不在轻量部署资产中，因此旧财务工作台不进入比赛主链路。新工作台仅反映已收录并核验的 NSCLC 证据样本，不代表企业整体研发实力，也不输出评分、排名、成功率、疗效优劣或投资建议。

Day6 本地浏览器人工验收已通过；该验收不是 Render 线上部署验收。

本地启动 FastAPI Web 服务：

```bash
.venv/bin/python -m uvicorn webapp.main:app --host 127.0.0.1 --port 8000
```

启用 DeepSeek 循证问答 `auto` 模式时使用本地 `.env`：

```bash
.venv/bin/python -m uvicorn webapp.main:app --host 127.0.0.1 --port 8000 --env-file .env
```

`.env` 不得提交，配置项参考 `.env.example`。

浏览器访问：

```text
http://127.0.0.1:8000
```

## 技术架构

```text
公开资料与人工核验数据
          ↓
数据清洗、规范化与来源记录
          ↓
SQLite 结构化数据 + Chroma 文档索引
          ↓
字段过滤、关键词与向量检索
          ↓
基于证据的分析、风险提示与引用报告
          ↓
FastAPI / Streamlit 展示
```

主要技术：Python、SQLite、Chroma、FastAPI、Streamlit、Pandas，以及可配置的大语言模型接口。

## 本地运行

推荐环境：Ubuntu/WSL2、Python 3.12。

```bash
git clone https://github.com/msy625/pharma-rd-decision-agent-v2.git
cd pharma-rd-decision-agent-v2

python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

初始化数据库：

```bash
python -m deepinsight.dataops.db_init
python -m deepinsight.dataops.db_expand
```

如需导入仓库内提供的宏观样例数据：

```bash
python -m deepinsight.dataops.macro_import
```

启动 FastAPI：

```bash
python -m uvicorn webapp.main:app --host 127.0.0.1 --port 8000
```

如果使用仓库内虚拟环境，也可以直接执行：

```bash
.venv/bin/python -m uvicorn webapp.main:app --host 127.0.0.1 --port 8000
```

如需启用 DeepSeek 循证问答 `auto` 模式，可使用本地 `.env` 启动：

```bash
.venv/bin/python -m uvicorn webapp.main:app --host 127.0.0.1 --port 8000 --env-file .env
```

`--env-file .env` 用于加载 DeepSeek 配置；不加该参数时，本地循证模式仍然可用。`.env` 不能提交，配置项参考 `.env.example`。

启动后在浏览器打开 `http://127.0.0.1:8000`。

## 比赛核心轻量部署

### 在线预览

Render Free Web Service 预览地址：

<https://pharma-rd-decision-agent.onrender.com>

当前部署分支为 `feature/day5-release-deploy`。线上已验收 `/health`、`/ready`、`/api/runtime-capabilities`、`/api/evidence/summary`、研发证据查询四个页签、`auto`/`local` 循证问答、安全拦截和本地 vendor 资源加载。Render Free 实例空闲后可能休眠，首次访问或长时间空闲后的访问可能需要等待冷启动。

完整开发环境继续使用：

```bash
python -m pip install -r requirements.txt
```

比赛核心线上演示可使用轻量依赖：

```bash
python -m pip install -r requirements-deploy.txt
```

轻量依赖只保障 FastAPI 静态页面、`/health`、`/ready`、`/api/evidence/*`、本地循证问答和可选 DeepSeek `auto` 模式，不包含旧 Streamlit、SQLite、Chroma、向量模型和数据导入功能依赖。

本地轻量启动：

```bash
PORT=8000 make web-deploy
```

等价命令：

```bash
python -m uvicorn webapp.main:app --host 0.0.0.0 --port ${PORT:-8000}
```

Render 使用 `render.yaml` 中的配置：

```text
buildCommand: pip install -r requirements-deploy.txt
startCommand: python -m uvicorn webapp.main:app --host 0.0.0.0 --port $PORT
healthCheckPath: /health
```

`/health` 是进程存活检查，不读取数据文件或密钥；`/ready` 是比赛核心链路就绪检查，会校验 CSV/JSON 证据数据并返回 `source_count` 和 `data_version`。

未配置 `DEEPSEEK_API_KEY` 时，循证问答仍可使用 `local` 模式，`auto` 模式会回退到本地结构化摘要。部署平台密钥只能放在平台环境变量中，不能提交 `.env`；Render 配置中 `DEEPSEEK_API_KEY` 使用手动配置，不写真实密钥。

公开预览环境默认关闭 DeepSeek 智能生成：

```text
GROUNDED_QA_LLM_ENABLED=false
GROUNDED_QA_LLM_PER_CLIENT_LIMIT=5
GROUNDED_QA_LLM_GLOBAL_LIMIT=30
GROUNDED_QA_LLM_WINDOW_SECONDS=600
GROUNDED_QA_LLM_MAX_CONCURRENCY=2
```

`local` 模式始终可用，不受 LLM 限流影响。只有在 Render 控制台手动配置 `DEEPSEEK_API_KEY`，并显式设置 `GROUNDED_QA_LLM_ENABLED=true` 后，`auto` 模式才会在问题通过安全检查、已检索到证据且未超过每客户端/全局/并发限制时尝试 DeepSeek。进程内限流适合当前 Render Free 单实例预览；实例重启会重置计数，多实例会分散计数，长期公网开放应使用平台级限流或集中式存储。

轻量部署不保证旧 Streamlit、SQLite、Chroma、向量检索、旧报告工作流和旧公司画像接口可用；这些旧功能需要完整 `requirements.txt` 和旧数据底座。

前端启动会先请求：

```text
GET /api/runtime-capabilities
```

该接口用于区分比赛核心轻量环境与旧功能能力状态。证据工作台可用时返回 `default_page=today`，首页默认进入真实“研发决策工作台”，只请求 `/api/evidence/workbench`，不会自动请求 `/api/bootstrap`、`/api/profile`、`/api/dashboard` 等旧接口，也不会展示旧工作台固定兜底统计。旧功能具备真实 SQLite 数据和可选依赖时仍可按能力保留，但不再决定默认工作台。

运行能力检查不使用 `.env` 判断旧功能是否可用，不读取或返回密钥，不创建 DeepSeek 客户端，不访问网络，也不加载 Chroma、sentence-transformers 或 Torch。

前端运行时资源已本地化到 `webapp/static/vendor/`：

- React 18.3.1
- ReactDOM 18.3.1
- Babel standalone 7.26.4

页面启动不再依赖 unpkg、jsDelivr、cdnjs 或 Google Fonts。字体文件和运行时 JS 均由 FastAPI 同源静态路由提供；证据中的 ClinicalTrials.gov、PubMed、EMA 和企业官网链接仍作为“打开原始来源”的外部链接保留，不属于页面启动依赖。页面同时提供本地 SVG favicon，`/favicon.ico` 和 `/static/favicon.svg` 均由 FastAPI 返回，避免浏览器默认 favicon 请求出现 404。

启动 Streamlit：

```bash
streamlit run scripts/streamlit/system_console.py
```

运行测试：

```bash
python -m pytest -q
```

基础工程最近一次验收结果为 `37 passed`（2026-07-21）。真实业务数据导入后还需重新执行数据质量、检索效果和完整演示测试。

校验与查询第一版来源登记表：

```bash
python3 scripts/validate_source_registry.py
python3 scripts/query_source_registry.py --summary
python3 scripts/query_source_registry.py --trial-id NCT04379635 --format table
python3 scripts/query_source_registry.py --drug SHR-1210 --format table
python3 -m unittest tests/test_source_registry_query.py
```

## 初版评价指标

- **事实准确率**：回答中的事实是否与原始资料一致。
- **引用支持率**：重要结论是否能够由引用证据支持。
- **检索有效率**：前 5 条检索结果中是否包含真正相关的资料。
- **稳定性**：连续操作、空数据、API 超时和断网情况下是否正确处理。
- **响应速度**：普通查询和报告生成是否满足现场演示需要。

## 项目边界

- 不训练或微调大模型，不自动补充缺失的医药事实。
- 不使用随机评分、虚构企业、虚构试验或无来源分析结论。
- 初版不建设覆盖全部疾病和药企的大型数据库。
- 知识图谱、多智能体和三维分子展示不属于初版必做范围。
- 数据不足时返回空结果或“暂无足够数据”，并保留可核验来源。
- 公司管线图不能单独作为历史研究状态依据，论文数量不能作为唯一试验数量。

## 数据与合规说明

项目仅使用允许公开访问和用于研究展示的资料。数据收集、整理和展示时保留来源、日期与链接，不上传包含隐私、商业秘密或使用许可不明确的内容。

本系统用于信息整理、技术研究和比赛展示，不构成医学诊断、治疗、用药建议、疗效保证或投资建议。使用者应以监管机构、临床试验注册平台、论文原文和企业正式公告为准。

## 项目来源与二次开发说明

本项目基于 [deafenken/DeepInsight-Agent](https://github.com/deafenken/DeepInsight-Agent) 进行二次开发，并已获得原作者授权。

原项目提供了企业分析、数据存储、检索、接口和报告等基础框架。本项目在此基础上重新定位为医药研发管线与证据分析场景，并计划重点新增真实研发数据体系、管线比较、证据追溯、风险提示、评测流程和比赛展示主线。原项目及其历史贡献归原作者和原贡献者所有；本项目团队对新增与修改部分负责。

## 当前进度

- [x] 完成基础依赖、跨平台路径和空数据接口修复。
- [x] 完成模型延迟加载、页面降级和缓存结构改进。
- [x] 隔离正式链路中的模拟数据，并建立可控测试 fixture。
- [x] 完成基础测试及 FastAPI、Streamlit 离线启动验证。
- [x] 初步确定初版疾病和企业范围：NSCLC、恒瑞医药、百济神州。
- [x] 完成第一版数据可用性检查并冻结数据范围。
- [x] 完成统一证据查询服务、FastAPI 证据接口和 Web 端研发证据查询页面。
- [ ] 建立可追溯的真实数据集导入流程。
- [ ] 完成管线比较、证据检索和引用分析闭环。
- [ ] 完成业务评测、演示缓存和展示材料。

## 团队协作

稳定开发分支为 `main`。成员从稳定分支创建独立功能分支，通过 Pull Request 合并，避免直接同时修改稳定分支。API 密钥、虚拟环境、本地数据库、大型原始资料和运行日志不得提交到仓库。
