# 药研制策（Pharma R&D Decision Agent）

> 面向医药研发比赛展示的可追溯证据决策支持系统

“药研制策”聚焦非小细胞肺癌（NSCLC），将临床试验登记、医学论文、监管资料和企业公开信息组织为可检索、可关联、可回到原始来源的证据链，帮助使用者快速梳理企业研发进展、证据缺口与后续核验方向。

[在线体验：pharma-rd-decision-agent.onrender.com](https://pharma-rd-decision-agent.onrender.com/)

> Render Free 实例空闲后可能休眠，首次访问可能需要等待冷启动。

## 当前展示范围

当前代码、本地数据与线上只读 API 使用同一份 NSCLC 样本口径：

| 范围 | 当前值 |
| --- | ---: |
| 企业 | 3 家：恒瑞医药、百济神州 / BeOne Medicines、阿斯利康 / AstraZeneca |
| 人工核验证据来源 | 39 条 |
| 试验级证据链 | 14 条 |
| 药物级监管链 | 1 条 |

39 条来源由 `data/source_registry.csv` 管理；证据关系由 `config/evidence_chains.json` 明确配置。当前数据版本由文件内容动态计算，运行 `GET /ready` 或 `GET /api/evidence/workbench` 可查看，不在 README 中写死易过期的更新时间或响应生成时间。

来源数不等于唯一试验数：同一试验的登记、论文和版本资料会归入同一试验级证据链；药物级监管资料单独成链，不重复计入试验数量。

## 项目痛点与核心流程

医药研发信息分散在试验注册平台、论文、监管机构和企业网站中，常见问题包括名称不统一、同一试验多来源重复、资料版本关系不清、监管事件与临床试验混计，以及分析结论难以追溯。

```text
选择企业、药物、试验或研发问题
              ↓
检索人工核验来源并归一实体
              ↓
组织试验级证据链与药物级监管链
              ↓
识别版本、状态、来源差异和证据缺口
              ↓
输出带来源编号、原始链接与限制说明的决策支持结果
```

比赛展示价值在于把“查到资料”推进为“按明确口径组织证据并说明边界”：系统展示证据覆盖和缺口，不用分数、排名或模型猜测替代人工核验。

## 六个一级入口

| 一级入口 | 主要功能 |
| --- | --- |
| 研发决策总览 | 汇总来源、企业、证据链、版本构成、待确认关系和数据范围 |
| 企业证据画像 | 按归一企业主体展示来源类型、试验链、监管链、版本与证据缺口 |
| 研发事件时间轴 | 按资料中的真实结构化日期展示研发事件、版本演进和无日期资料 |
| 研发证据中心 | 提供来源检索、证据链和企业对比；支持关键词、企业、药物、试验、研究名称和来源 ID 查询 |
| 智能决策 Agent | 对问题执行安全检查、证据检索与规则化分析，返回引用、限制和工具轨迹；可选使用 DeepSeek 组织答案 |
| 证据决策简报 | 按企业生成结构化简报，汇总当前事实、核心试验、监管背景、证据充分性、风险缺口与下一步证据方向 |

企业画像和企业对比仅描述当前样本中的证据覆盖，不代表企业整体研发实力。旧 Streamlit、SQLite、Chroma 和历史企业分析接口仍属于兼容代码，不进入当前比赛导航和轻量部署主链路。

## 可信性设计

- **人工核验登记**：每条证据保留来源 ID、来源类型、原始链接、核验状态和相关日期。
- **实体归一**：统一企业别名，例如 BeOne Medicines、BeiGene 与百济神州归入同一主体。
- **链路分层**：严格区分试验级证据链与药物级监管链，避免共享试验或监管资料造成重复计数。
- **状态分离**：`verification_status` 表示资料核验状态，`study_status` 表示研究状态，两者不混用。
- **版本语义**：区分最新版本、历史版本和没有替代关系的独立资料；不根据相似标题自动推断关联。
- **可追溯输出**：检索、Agent 与简报均返回来源编号、引用和限制；证据不足时明确提示，不补写缺失事实。
- **只读主链路**：比赛核心 API 读取本地 CSV/JSON，不在页面操作中修改证据数据。
- **公开环境保护**：公开 Render 环境允许 `auto` 模式，但只有平台配置密钥、问题通过安全检查、检索到本地证据且未触发限流时才调用模型；其他情况自动回退本地分析。

## 技术架构

```text
浏览器（本地静态 React 页面）
              ↓ HTTP
FastAPI：健康检查、能力识别、证据查询、Agent、简报 API
              ↓
领域服务：来源登记、证据链、企业画像、时间轴、工作台、决策 Agent
              ↓
data/source_registry.csv + config/*.json
              ↓（auto 模式可选调用）
DeepSeek OpenAI-compatible API
```

- 后端：Python 3.12、FastAPI、Uvicorn、Pydantic。
- 前端：构建后的静态页面位于 `webapp/static/`，React、ReactDOM 和 Babel 运行时资源已随仓库提供。
- 轻量部署依赖：`requirements-deploy.txt`，不包含旧 Streamlit、Chroma、向量模型和完整数据管线依赖。
- 核心接口：`/health`、`/ready`、`/api/runtime-capabilities` 及 `/api/evidence/*`。

## 本地运行（Ubuntu Bash）

### 1. 准备环境

优先复用仓库已有虚拟环境。若尚未安装轻量部署依赖，可在已激活的项目环境中执行：

```bash
python -m pip install -r requirements-deploy.txt
```

### 2. 启动比赛 Web 应用

```bash
.venv/bin/python -m uvicorn webapp.main:app --host 127.0.0.1 --port 8000
```

如果已经激活虚拟环境，也可执行：

```bash
python -m uvicorn webapp.main:app --host 127.0.0.1 --port 8000
```

浏览器打开 <http://127.0.0.1:8000/>。停止服务时在终端按 `Ctrl+C`。

本地模式不依赖 API Key：不配置 DeepSeek 时，证据检索、工作台、企业画像、时间轴、Agent 本地分析和决策简报仍可使用。

## DeepSeek 可选配置

只有需要让智能决策 Agent 使用大模型组织答案时才配置 DeepSeek。复制示例配置并仅在本机填写：

```bash
cp .env.example .env
```

将真实密钥写入本地 `.env` 的 `DEEPSEEK_API_KEY`，同时把 `GROUNDED_QA_LLM_ENABLED` 显式设为 `true`，然后启动：

```bash
.venv/bin/python -m uvicorn webapp.main:app --host 127.0.0.1 --port 8000 --env-file .env
```

`.env.example` 只提供占位符和配置项。不得把真实密钥写入 README、代码、数据、部署配置或 Git；`.env` 不应提交。未配置密钥、开关关闭、调用失败或达到使用限制时，系统使用本地结构化证据路径，不伪造模型输出。

## Render 部署

仓库的 `render.yaml` 定义了当前轻量 Web Service：

```text
buildCommand: pip install -r requirements-deploy.txt
startCommand: python -m uvicorn webapp.main:app --host 0.0.0.0 --port $PORT
healthCheckPath: /health
```

部署前可在本地按相同方式启动：

```bash
PORT=8000 make web-deploy
```

`/health` 只检查进程存活；`/ready` 检查比赛核心数据是否可读，并返回数据版本和来源数。`render.yaml` 设置 `GROUNDED_QA_LLM_ENABLED=true`，但 `DEEPSEEK_API_KEY` 仍必须在 Render 控制台以环境变量手动配置。未配置密钥时 `auto` 自动回退本地分析；不得将真实密钥写入仓库。模型调用继续受每客户端、全局和并发限制保护。

## 测试与校验

比赛精简源码包可安装独立测试依赖并运行离线核心验证入口：

```bash
python -m pip install -r requirements-test.txt
python scripts/validate_competition_package.py
```

该入口使用 `tests/competition_core_tests.txt` 中的显式白名单，覆盖当前比赛数据、核心 API、local Agent、静态资源、部署配置和离线评测；不读取 `.env`，不调用 DeepSeek，也不要求源码包保留 `.git`。

仓库只保存 `RELEASE_METADATA.template.json`。正式创建白名单暂存目录时，必须在已提交且工作区干净的 Git 仓库中执行：

```bash
python scripts/build_competition_staging.py --output-dir /tmp/pharma-rd-source-stage
```

脚本会读取当前 `git rev-parse HEAD`，在暂存目录生成最终 `RELEASE_METADATA.json`；模板不会进入暂存包。若 Git 不可用或工作区不干净，正式模式会停止。仅在当前改动尚未提交的预打包验证阶段，可显式传入待验证 SHA：

```bash
python scripts/build_competition_staging.py \
  --output-dir /tmp/pharma-rd-source-stage-preview \
  --source-commit 3dcb2ae3a5fdd4ad25bc82013164f8d5911bcbd0
```

不需要启动服务即可执行当前数据完整性和相关轻量回归检查：

```bash
.venv/bin/python scripts/validate_source_registry.py
.venv/bin/python -m pytest -q \
  tests/test_competition_navigation_frontend.py \
  tests/test_evidence_workbench_api.py \
  tests/test_rd_decision_agent_api.py \
  tests/test_evidence_decision_brief_api.py \
  tests/test_deployment_config.py
```

查看本地只读就绪状态：

```bash
.venv/bin/python -c "from webapp.main import ready; print(ready())"
```

完整回归可按需执行：

```bash
.venv/bin/python -m pytest -q
```

测试结果以实际命令输出为准；README 不记录可能随代码变化而失效的历史通过数量。

## 项目边界

本系统用于公开资料整理、技术研究和比赛展示，不提供：

- 医学诊断或个体治疗、用药建议；
- 跨试验疗效排名、疗效保证或企业优劣排名；
- 临床成功率、研发成功率或审批结果预测；
- 投资、证券交易或财务建议。

系统不训练或微调医学大模型，不自动补充缺失事实，不从相似标题推断证据关系，也不把当前 3 家企业、39 条来源的样本外推为行业全貌。使用者应以监管机构、临床试验注册平台、论文原文和企业正式公告为准。

## 来源、授权与合规

证据样本来自允许公开访问的 ClinicalTrials.gov、PubMed、EMA/CHMP 页面及企业官网、年报、公告和公开管线资料。项目保留来源机构、日期、链接和核验信息，仅用于研究与比赛展示；不收录隐私、商业秘密或授权不明确的非公开内容。外部资料的版权和使用条款归各来源方所有。

本项目基于 [deafenken/DeepInsight-Agent](https://github.com/deafenken/DeepInsight-Agent) 二次开发，并已获得原作者授权。原项目及历史贡献归原作者和原贡献者所有，本项目团队对新增和修改部分负责。

## 当前进度

- [x] 建立 NSCLC 三企业、39 条人工核验来源的统一登记表。
- [x] 建立 14 条试验级证据链和 1 条药物级监管链的明确关系配置。
- [x] 完成六入口比赛 Web 主线及对应只读 FastAPI 服务。
- [x] 提供本地无密钥模式、可选 DeepSeek `auto` 模式和失败自动回退策略。
- [x] 提供 Render 轻量部署配置、健康检查与就绪检查。

上述进度只描述当前仓库中可见的代码、配置和数据，不代表覆盖全部 NSCLC 研发证据，也不替代上线后的持续可用性监控。

## 团队协作

- 从 `main` 创建独立功能分支，通过 Pull Request 评审后合并，避免多人直接同时修改稳定分支。
- 数据变更需保留来源、核验口径和证据链关系，并先运行登记表校验及相关测试。
- 提交前检查 `git status` 和 diff，不提交 `.env`、真实 API Key、虚拟环境、本地数据库、运行日志或大型原始资料。
- 功能、数据、README 和演示口径应同步更新；区分本地测试、浏览器验收和线上验证，不互相替代。
