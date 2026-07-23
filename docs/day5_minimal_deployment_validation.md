# Day 5 第三阶段：最小部署依赖、Render 配置与干净环境验证

日期：2026-07-23
分支：`feature/day5-release-deploy`

本阶段新增比赛核心轻量部署配置，不修改证据事实数据，不提交 `.env`，不调用真实 DeepSeek。

## 最小依赖

`requirements-deploy.txt` 只包含当前 `.venv` 已验证兼容的直接依赖：

```text
fastapi==0.139.2
uvicorn==0.51.0
pydantic==2.13.4
openai==2.46.0
```

选择原因：

- `fastapi`：提供 `webapp.main:app`、路由、静态文件挂载和 HTTP 错误响应。
- `uvicorn`：线上运行 ASGI Web 服务。
- `pydantic`：`webapp.main` 直接使用 `BaseModel` 和 `Field` 定义请求模型。
- `openai`：DeepSeek OpenAI-compatible `auto` 模式延迟创建客户端时需要；无密钥或 local 模式不会创建客户端。

未纳入旧重依赖：

- `streamlit`
- `pandas`
- `chromadb`
- `sentence-transformers`
- `torch`
- `langchain-text-splitters`
- `pdfplumber`
- `openpyxl`
- `streamlit-echarts`

## Python 版本

`.python-version` 固定为：

```text
3.12.3
```

原因：当前项目 `.venv` 使用 Python 3.12.3，并已在该版本下完成 FastAPI 入口、健康检查、证据 API、证据链、企业对比和 Grounded QA 回归测试。

## Render 配置

`render.yaml` 配置一个 Python Web Service：

```text
buildCommand: pip install -r requirements-deploy.txt
startCommand: python -m uvicorn webapp.main:app --host 0.0.0.0 --port $PORT
healthCheckPath: /health
```

环境变量：

- `DEEPSEEK_API_KEY`: `sync: false`，由平台手动配置，不写真实密钥。
- `DEEPSEEK_BASE_URL`: `https://api.deepseek.com`
- `DEEPSEEK_MODEL`: `deepseek-v4-flash`

未配置持久磁盘，不引用旧 SQLite/Chroma 数据，不包含个人绝对路径。

## Makefile

新增 `web-deploy`，不影响原 `web` 和 Streamlit 目标：

```bash
PORT=8000 make web-deploy
```

实际命令：

```bash
python3 -m uvicorn webapp.main:app --host 0.0.0.0 --port ${PORT:-8000}
```

## 配置测试

新增 `tests/test_deployment_config.py`，覆盖：

- `requirements-deploy.txt` 存在；
- 不包含旧重依赖；
- 只包含比赛核心直接依赖；
- `.python-version` 是完整补丁版本；
- `render.yaml` 可解析或具备合法结构；
- Render build/start/health 配置正确；
- 不包含真实密钥；
- `.env` 仍被 Git 忽略；
- 不引用旧 SQLite/Chroma 数据；
- 不包含个人绝对路径。

## 干净环境验证

临时环境路径：

```text
/tmp/pharma-rd-deploy-venv
```

验证策略：

1. 只安装 `requirements-deploy.txt`。
2. 不安装完整 `requirements.txt`。
3. 不读取 `.env`。
4. 不调用真实 DeepSeek。
5. 只做本地 HTTP smoke。

验证命令和结果见本轮最终报告。若 pip 网络下载失败，则该部分应记录为未完成，不写成通过。

实际结果：

```text
python3 --version
Python 3.12.3

/tmp/pharma-rd-deploy-venv/bin/python -m pip install -r requirements-deploy.txt
Successfully installed fastapi==0.139.2 uvicorn==0.51.0 pydantic==2.13.4 openai==2.46.0 and transitive dependencies.

import webapp.main
app_is_fastapi True
missing_routes []
loaded_blocked []

/tmp/pharma-rd-deploy-venv/bin/python -m unittest tests/test_deployment_health.py
8 tests OK

/tmp/pharma-rd-deploy-venv/bin/python -m unittest tests/test_deployment_config.py
12 tests OK
```

本地 Uvicorn smoke 使用端口 `8766`，未读取 `.env`，未设置 `DEEPSEEK_API_KEY`：

```text
GET /health
HTTP 200
{"status":"ok","service":"pharma-rd-decision-agent"}

GET /ready
HTTP 200
source_count=31
local_grounded_qa_available=true

GET /api/evidence/summary
HTTP 200
total_sources=31

POST /api/evidence/grounded-qa
question=RATIONALE-304有哪些证据版本？
generation_mode=local
HTTP 200
generation_mode_used=local
llm_used=false
citations=B003,B006,B007
```

临时环境已删除：

```text
/tmp/pharma-rd-deploy-venv
```

## 已知边界

- 轻量部署保证比赛核心循证功能，不保证旧 Streamlit、SQLite、Chroma、向量检索、旧报告工作流或旧公司画像接口可用。
- `/health` 不读数据，只代表进程存活。
- `/ready` 只代表比赛核心 CSV/JSON 链路就绪，不代表旧数据库链路就绪。
- 前端 React、ReactDOM、Babel 已在后续阶段本地化到 vendor 资源，并已完成线上加载验收。

## Render 实际部署结果

Render Free Web Service 已部署成功：

```text
https://pharma-rd-decision-agent.onrender.com
```

部署信息：

- 部署分支：`feature/day5-release-deploy`
- 安全补丁提交：`2ef08b1`

线上验收结果：

- `/health`：通过
- `/ready`：通过，`source_count=31`
- `/api/runtime-capabilities`：比赛核心可用，旧功能不可用，默认 `evidence`
- `/api/evidence/summary`：31 条来源
- 本地 vendor React、ReactDOM、Babel 在线正常加载
- 页面默认进入“研发证据查询”
- 四个循证页签线上正常

Render Free 实例空闲后可能休眠和冷启动。未进行高频线上 429 压力测试；429 逻辑由自动测试覆盖。
