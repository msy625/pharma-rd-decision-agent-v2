# Day 5 第一阶段：发布与部署可行性审计

审计日期：2026-07-23
分支：`feature/day5-release-deploy`
范围：只读检查与部署设计；未修改业务代码，未安装依赖，未访问网络，未读取 `.env` 内容。

## 1. 线上主链路

比赛线上演示真正需要的主链路是：

```text
浏览器
  -> FastAPI: webapp.main:app
  -> 静态前端: webapp/static/index.html
  -> /api/evidence/*
  -> SourceRegistryService
  -> EvidenceChainService
  -> CompanyEvidenceComparisonService
  -> GroundedQAService
  -> 可选 DeepSeek
```

主链路的数据来源是只读 CSV/JSON：

- `data/source_registry.csv`
- `config/entity_aliases.json`
- `config/evidence_rules.json`
- `config/evidence_chains.json`
- `config/grounded_qa_rules.json`

主链路服务本身不需要 SQLite、Chroma、sentence-transformers、torch、Streamlit、demo_cache 或本地绝对路径。`SourceRegistryService`、`EvidenceChainService`、`CompanyEvidenceComparisonService`、`GroundedQAService` 都是 CSV/JSON 读路径，不导入模型、向量库、数据库或 Web 框架。

当前阻碍最小部署的是 `webapp/main.py` 的顶层导入链。虽然 `/api/evidence/*` 不使用旧网站能力，但 `webapp.main` 导入时仍会导入：

- `deepinsight.core.agent_tools`
- `deepinsight.apps.app_whitebox`
- `deepinsight.apps.workflow_report`
- `deepinsight.core.retriever`

本地导入检查显示：

```text
import webapp.main -> streamlit,pandas,openai 已进入 sys.modules
import deepinsight.core.grounded_qa_service -> 未加载 streamlit/pandas/chromadb/sentence_transformers/torch/openai/requests/fastapi
```

因此，按当前入口直接部署 `webapp.main:app` 时，线上至少仍需要安装旧网站顶层导入所需的 `streamlit`、`pandas`、`openai` 等包；如果后续拆分或延迟导入旧功能，比赛主链路可以降到更小依赖集合。

## 2. Git 数据完整性

已确认 Git 跟踪：

- `data/source_registry.csv`
- `config/evidence_chains.json`
- `config/grounded_qa_rules.json`
- `config/entity_aliases.json`
- `config/evidence_rules.json`
- `webapp/static/index.html`
- `webapp/static/dc-runtime.js`
- `webapp/static/LineChart.dc.html`
- `webapp/static/BarChart.dc.html`
- `webapp/static/fonts/*.woff2`
- `demo_cache/*.json`

未跟踪或不存在于 Git 跟踪清单：

- `.env`：被 `.gitignore` 规则 `.env` 忽略，未读取内容。
- `data/enterprise_analysis.db`：本机存在，但因 `data/*` 规则被忽略，未被 Git 跟踪。
- `data/chroma/`：未发现 Git 跟踪。
- Dockerfile、Procfile、runtime.txt、render.yaml、Railway 配置、GitHub Actions、Netlify/Vercel 配置：未发现。

干净克隆下，比赛主链路所需 CSV/JSON 和静态入口文件完整；旧 SQLite/Chroma 网站功能所需数据库和向量索引不完整。

`data/source_registry.csv` 当前为 31 行，所有 `url` 字段 scheme 均为 `https`。

## 3. 启动方式

当前 FastAPI 应用入口：

```bash
python -m uvicorn webapp.main:app --host 0.0.0.0 --port 8000
```

推荐线上平台启动命令应支持平台注入的 `PORT`：

```bash
python -m uvicorn webapp.main:app --host 0.0.0.0 --port ${PORT:-8000}
```

现状：

- `Makefile web` 支持 `0.0.0.0`，但端口固定为 `8000`。
- README 本地示例使用 `127.0.0.1:8000`。
- `deploy/systemd/deepinsight-web.service` 使用 `127.0.0.1:8000`，适合 Nginx 反代，不适合多数 PaaS 直接暴露端口。
- 未发现 `/health`、`/ready` 或类似健康检查接口。
- 可以临时用 `/api/evidence/summary` 作为业务健康检查，但它会读取 CSV/JSON，不会加载 DeepSeek、Chroma 或向量模型。
- `GET /api/evidence/grounded-qa/capabilities` 也不会创建 DeepSeek 客户端，但会读取规则文件并计算数据版本。
- 无 `DEEPSEEK_API_KEY` 时，`grounded_llm_settings()` 返回 `configured=False`，应用可启动；循证问答 `auto` 会回退本地摘要。
- DeepSeek 调用失败时，`GroundedQAService` 会捕获异常并回退本地摘要，返回泛化失败原因，不暴露原始异常。
- 启动期间未发现主动网络访问或模型下载；但当前 `webapp.main` 导入会加载旧功能依赖。

## 4. 必需依赖

按比赛主链路的最小运行需求，理论上需要：

- `fastapi`
- `uvicorn`
- `pydantic`，由 FastAPI 依赖引入
- Python 标准库：`csv`、`json`、`pathlib`、`collections`、`hashlib`、`datetime`、`re`
- 可选 DeepSeek：`openai`

按当前 `webapp.main:app` 入口的实际导入需求，还需要：

- `streamlit`
- `pandas`
- `openai`
- 旧功能运行时按路径可能需要 `requests`、`chromadb`、`sqlite3` 标准库和本地数据库。

`requirements.txt` 当前包含：

```text
streamlit
pandas
openpyxl
openai
requests
chromadb
streamlit-echarts
pdfplumber
langchain-text-splitters
faker
sentence-transformers
fastapi
uvicorn
```

依赖分类：

| 分类 | 依赖 |
| --- | --- |
| 循证比赛主链路必需 | `fastapi`, `uvicorn`; 当前入口实际还需 `streamlit`, `pandas`, `openai` |
| 可选 DeepSeek | `openai` |
| 旧网站功能依赖 | `streamlit`, `pandas`, `requests`, `chromadb`, `openpyxl`, `pdfplumber`, `streamlit-echarts`, `langchain-text-splitters` |
| 开发/测试依赖 | 当前 `requirements.txt` 未单列；测试使用标准库 `unittest` 和本地轻量 ASGI 客户端，部分测试依赖 FastAPI 可导入 |
| 当前完全不需要的主链路依赖 | `faker`, `sentence-transformers`, `chromadb`, `openpyxl`, `pdfplumber`, `streamlit-echarts`, `langchain-text-splitters`；`torch` 未在 requirements 中直接列出，但通常会由 `sentence-transformers` 间接拉入 |

## 5. 重依赖风险

显著部署风险：

- `sentence-transformers` 通常会间接安装 `torch`、`transformers` 等大包，显著增加构建时间和磁盘占用。
- `chromadb` 依赖链较长，且持久化向量库对文件系统有要求。
- `streamlit`、`pandas`、`openpyxl`、`pdfplumber` 对比赛主链路不是必要依赖，但当前 `webapp.main` 顶层导入使其中部分依赖变成启动依赖。
- `.venv` 本机体积约 `5.8G`，说明完整依赖集合不适合轻量 PaaS 快速构建。
- requirements 未固定版本，Python 3.12 下存在上游版本漂移风险。

本地版本检查：

```text
Python 3.12.3
FastAPI 0.139.2
Starlette 1.3.1
httpx 0.28.1
Pydantic 2.13.4
```

当前测试已采用自定义轻量 ASGI 客户端，避免依赖 `TestClient` 与 `httpx` 组合细节；历史文档记录过 `Annotated[..., Query(...)] = 普通默认值` 的修复，以兼容真实 HTTP 参数校验和直接调用默认值。

适合下一阶段新增 `requirements-deploy.txt`，但需要同时处理 `webapp.main` 顶层导入。否则只新增最小依赖文件会导致应用 import 阶段缺包。

如果使用最小依赖并延迟导入旧功能，旧网站的这些 API 可能不可用或降级：

- `/api/bootstrap`
- `/api/dashboard`
- `/api/profile`
- `/api/compare`
- `/api/timeline`
- `/api/database/*`
- `/api/data-room/*`
- `/api/chat`
- `/api/workflow`
- `/api/batch-workflow`
- `/api/advanced`
- `/api/whitebox`

## 6. 文件系统与缓存

比赛主链路数据只读，读取 Git 中的 CSV/JSON，不依赖持久化磁盘写入。

`GroundedQAService.data_version()` 会根据 CSV/JSON 文件内容计算短哈希，可作为线上数据版本一致性标识。部署时只要 Git 提交一致，多实例之间数据版本一致。

`demo_cache/` 已被 Git 跟踪，但比赛主链路不依赖它。旧网站演示缓存可能读写 `demo_cache/`，多实例部署下不适合作为共享状态。

当前静态前端无需 Node/npm 构建，`webapp/static/index.html` 已生成并被 Git 跟踪，可以直接提交产物。若修改 `webapp/frontend_src/component.js`，才需要运行：

```bash
python3 webapp/frontend_src/build.py
```

前端运行时风险：`webapp/static/dc-runtime.js` 会从 `unpkg.com` 加载 React/ReactDOM，静态 HTML 也包含 Google Fonts 预连接。部署本身不需要 Node/npm，但浏览器访问时依赖外部 CDN 可达；比赛现场网络受限时可能影响首屏。

## 7. 安全风险

已确认：

- `.env` 被 `.gitignore` 忽略，未读取内容。
- `.env.example` 和 `deploy/env/webapp.env.example` 只包含占位符或空值。
- 未发现形如真实 `sk-...` 的密钥。
- DeepSeek key 只在后端环境变量读取，前端 API 能看到 `llm_mode_available` 和模型名，但不会收到 key。
- `/api/evidence/grounded-qa` 限制问题长度为 1000 字符。
- Grounded QA 的错误处理会返回通用错误，不返回原始异常、绝对路径或密钥名；测试覆盖过异常脱敏。
- `source_registry.csv` 的 `url` 当前全部为 `https`。

仍需处理或确认：

- 未设置 CORS；同源静态前端不需要 CORS。若未来前后端分域，需要显式白名单，而不是开放 `*`。
- 未设置允许的 Host（Trusted Host）。PaaS 和自有服务器上线时建议限制域名。
- 未发现专门健康检查接口；用业务接口代替健康检查会把数据文件异常等同于进程异常。
- API 当前没有请求频率限制；比赛演示可接受，公网长期开放需要加限流。
- DeepSeek 调用已有超时配置，但旧 `retriever.DeepSeekClient` 使用 90 秒 timeout，旧 API 可能导致请求占用时间较长。
- 旧功能的 warning 可能包含数据库/向量检索异常文本，需上线前检查是否会暴露绝对路径或内部结构。
- 前端请求错误只显示通用中文提示，不显示后端异常正文。

## 8. 平台适配比较

未联网查询实时价格、套餐限制或当前平台规则；以下仅按当前项目结构做技术适配判断。

| 平台 | FastAPI 常驻支持 | 环境变量 | GitHub 自动部署 | 依赖/磁盘风险 | 冷启动 | 自定义域名 | 改造量 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Render | 原生适合 Web Service | 支持 | 支持 | 完整 requirements 风险较高；最小依赖更适合 | 免费/低配可能冷启动 | 支持 | 中 |
| Railway | 原生适合常驻服务 | 支持 | 支持 | 完整依赖和磁盘限制需确认 | 取决于套餐 | 支持 | 中 |
| Fly.io | 适合容器化 FastAPI | 支持 | 可接 GitHub/CI | 需要 Dockerfile；重依赖镜像较大 | 可控但需配置 | 支持 | 中到高 |
| 自有云服务器 | 完全支持 systemd + Nginx | 自行管理 | 可手动或 CI | 磁盘和内存可控；运维成本高 | 无典型 PaaS 冷启动 | 支持 | 低到中，已有 deploy/ 可复用 |
| Netlify/Vercel | 静态前端原生，FastAPI 常驻不匹配 | 支持 | 支持 | Python 后端需改 serverless 或分离部署 | serverless 冷启动和超时风险 | 支持 | 高 |

首选：Render 或 Railway，用 GitHub 自动部署一个 FastAPI Web Service；下一步联网确认价格、Python 版本、磁盘、构建时长、休眠规则。

备选：自有云服务器。已有 `deploy/` 适配 systemd + Nginx，适合稳定公网演示，但需要手动运维和服务器安全配置。

不推荐作为单体后端首选：Netlify/Vercel。可以托管静态前端，但当前项目是持续运行的 FastAPI 单体服务，拆成 serverless 改造量较大。

## 9. 阻塞问题清单

### 阻塞部署

1. `webapp/main.py` 顶层导入旧功能依赖，最小依赖部署会 import 失败。
   - 原因：比赛主链路虽轻量，但应用入口导入 `streamlit/pandas/openai` 相关模块。
   - 最小解决方案：把旧网站模块改为路由内延迟导入，或新增比赛专用入口，例如 `webapp/evidence_app.py`，只挂载静态前端和 `/api/evidence/*`。
   - 验证方式：在只安装最小依赖的干净虚拟环境执行 `python -c "import webapp.evidence_app"` 或等价入口导入检查，再请求 `/api/evidence/summary` 和 `/api/evidence/grounded-qa`。

2. 启动命令未统一支持平台 `PORT`。
   - 原因：README 和 Makefile 固定 `8000`；PaaS 通常要求监听平台提供的 `PORT`。
   - 最小解决方案：在部署文档或平台配置中使用 `python -m uvicorn webapp.main:app --host 0.0.0.0 --port ${PORT:-8000}`。
   - 验证方式：本地设置 `PORT=8010` 启动并访问对应端口；PaaS 部署后查看健康检查。

3. 缺少健康检查接口。
   - 原因：未发现 `/health`、`/ready` 或类似接口。
   - 最小解决方案：新增不加载 DeepSeek、Chroma、向量模型的轻量 `/health`，只返回进程和版本状态；另可新增 `/ready` 校验 CSV/JSON。
   - 验证方式：请求 `/health` 不触发重依赖导入和网络访问，返回 200。

### 影响核心演示

1. 前端运行时依赖外部 CDN 加载 React。
   - 原因：`webapp/static/dc-runtime.js` 包含 `https://unpkg.com/react...` 和 `react-dom...`。
   - 最小解决方案：将 React/ReactDOM UMD 文件纳入 `webapp/static/` 并改为本地引用，或确认比赛现场公网可访问 CDN。
   - 验证方式：浏览器禁用外网或拦截 CDN 后检查首屏是否可用；正常网络下检查控制台无加载失败。

2. 线上平台完整安装 requirements 可能超时或磁盘不足。
   - 原因：`sentence-transformers`、间接 `torch`、`chromadb` 等依赖链较重。
   - 最小解决方案：新增 `requirements-deploy.txt` 并拆分/延迟导入旧功能。
   - 验证方式：干净环境按部署依赖安装，记录构建时间和磁盘占用，导入 FastAPI 入口并跑 evidence API smoke test。

3. 无正式健康检查时，平台健康探针可能误判。
   - 原因：可用替代接口 `/api/evidence/summary` 依赖数据文件。
   - 最小解决方案：同阻塞项 3。
   - 验证方式：健康探针持续返回 200；删除数据文件时 `/health` 仍可区分进程存活和业务数据不可用。

### 可以上线后优化

1. CORS、Trusted Host、限流未配置。
   - 原因：当前同源演示不必需，但公网长期开放需要。
   - 最小解决方案：上线域名确定后配置 Host 白名单；如分域再配置 CORS 白名单；为问答 POST 增加简单限流。
   - 验证方式：非白名单 Host/CORS 请求被拒绝，正常域名可访问。

2. 旧网站部署说明与当前比赛主链路不一致。
   - 原因：`deploy/README.md` 仍以 SQLite + Chroma 长期服务器部署为默认。
   - 最小解决方案：新增比赛部署说明，明确 CSV/JSON 主链路和旧功能差异。
   - 验证方式：干净克隆按新文档能启动主链路。

3. requirements 未固定版本。
   - 原因：当前 `requirements.txt` 只有包名，没有版本锁定。
   - 最小解决方案：比赛部署依赖固定已验证版本，或记录构建镜像/lock 文件。
   - 验证方式：新环境重复安装后版本一致，测试通过。

## 10. 推荐部署方案

第一选择：Render 或 Railway 部署 FastAPI Web Service。

建议策略：

1. 先保留单体 FastAPI 入口用于本地完整功能。
2. 新增比赛专用轻量入口或延迟导入旧功能。
3. 新增 `requirements-deploy.txt`，只包含 `fastapi`、`uvicorn` 和可选 `openai`。
4. 使用 `python -m uvicorn <入口>:app --host 0.0.0.0 --port ${PORT:-8000}`。
5. 将 `DEEPSEEK_API_KEY` 作为平台环境变量，可不配置；不配置时默认本地模式。

备选方案：自有云服务器复用 `deploy/systemd` + `deploy/nginx`，但需同步更新部署文档，避免要求不存在或不需要的 SQLite/Chroma 数据。

## 11. 下一步实施顺序

1. 新增轻量健康检查：`/health` 只验证进程存活，`/ready` 可验证 CSV/JSON。
2. 拆分或延迟导入旧网站模块，保证 `/api/evidence/*` 入口不依赖 Streamlit、Pandas、Chroma、sentence-transformers。
3. 新增 `requirements-deploy.txt` 并固定最小版本，保留 `requirements.txt` 给完整本地旧功能。
4. 更新部署文档和启动命令，明确 `PORT`、`0.0.0.0`、无 DeepSeek key 的降级行为。
5. 处理前端 CDN 风险：要么本地化 React/ReactDOM，要么在比赛前确认现场网络和平台 CSP。
6. 选择 Render/Railway 做一次真实联网部署验证；实时价格、休眠规则、磁盘限制和 Python 版本需下一步联网确认。
7. 跑干净环境 smoke test：导入入口、请求 `/`、`/api/evidence/summary`、`/api/evidence/search?q=NSCLC`、`/api/evidence/grounded-qa/capabilities`、`POST /api/evidence/grounded-qa`。
