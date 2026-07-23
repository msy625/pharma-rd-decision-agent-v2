# Day 5 第四阶段：前端运行时依赖审计与 CDN 资源本地化

日期：2026-07-23
分支：`feature/day5-release-deploy`

本阶段只处理页面启动所需前端运行时资源，不修改业务 API、证据数据、证据链配置或 DeepSeek 调用逻辑。

## 外部资源审计

页面运行所需 CDN：

| 资源 | 原 URL | 版本 | 用途 | 不可访问时影响 | 处理 |
| --- | --- | --- | --- | --- | --- |
| React UMD | `https://unpkg.com/react@18.3.1/umd/react.production.min.js` | 18.3.1 | `dc-runtime.js` 启动 React 组件树 | 页面无法完成 React 渲染 | 已本地化 |
| ReactDOM UMD | `https://unpkg.com/react-dom@18.3.1/umd/react-dom.production.min.js` | 18.3.1 | 挂载根组件 | 页面无法挂载到 `#dc-root` | 已本地化 |
| Babel standalone | `https://unpkg.com/@babel/standalone@7.26.4/babel.min.js` | 7.26.4 | `x-import` 加载 JSX 外部组件时备用 | 当前页面无 `x-import`，但该分支触发时会失败 | 已本地化 |
| Google Fonts preconnect | `https://fonts.googleapis.com`、`https://fonts.gstatic.com` | 不适用 | 仅预连接 | 字体文件已是 `/static/fonts/*.woff2`，启动不依赖 | 已移除 |

不处理的外部网址：

- `data/source_registry.csv` 中的 ClinicalTrials.gov、PubMed、EMA、企业官网和公司 PDF 链接；
- API 返回字段 `source_url`；
- 前端“打开原始来源”链接；
- README 和文档中的普通说明网址。

这些链接属于证据来源或文档引用，不是页面启动运行时资源。

## 本地化资源

资源保存到 `webapp/static/vendor/`，由现有 FastAPI 静态路由 `/static/*` 提供。

| 资源 | 本地路径 | SHA-256 | 许可证 |
| --- | --- | --- | --- |
| React 18.3.1 | `webapp/static/vendor/react/react.production.min-18.3.1.js` | `d949f1c3687aedadcedac85261865f29b17cd273997e7f6b2bfc53b2f9d4c4dd` | `webapp/static/vendor/react/LICENSE-18.3.1` |
| ReactDOM 18.3.1 | `webapp/static/vendor/react-dom/react-dom.production.min-18.3.1.js` | `35f4f974f4b2bcd44da73963347f8952e341f83909e4498227d4e26b98f66f0d` | `webapp/static/vendor/react-dom/LICENSE-18.3.1` |
| Babel standalone 7.26.4 | `webapp/static/vendor/babel/babel.min-7.26.4.js` | `a12872ea8da3d29b2a296c51bfac7c482e81419c755f2207a49ad9b77200f4ea` | `webapp/static/vendor/babel/LICENSE-7.26.4` |

清单文件：`webapp/static/vendor/manifest.json`。

下载来源均为当前页面原先使用的 unpkg 固定版本 URL。未升级 React、ReactDOM 或 Babel 版本。

## 加载逻辑

- `webapp/static/dc-runtime.js` 中的 React、ReactDOM 和 Babel URL 改为 `/static/vendor/...`。
- `webapp/frontend_src/template.html` 移除 Google Fonts preconnect。
- 已运行 `webapp/frontend_src/build.py` 重新生成 `webapp/static/index.html`。
- `webapp/frontend_src/component.js` 未修改，页面业务功能和 API 调用不变。

文件关系：

- `component.js` 注入 `template.html` 的 `/*__COMPONENT__*/` 占位；
- `build.py` 生成 `webapp/static/index.html`；
- `dc-runtime.js` 独立作为静态运行时文件加载；
- `vendor/` 文件通过 `/static/vendor/...` 直接访问。

## 当前启动依赖

页面启动不再依赖公共 CDN：

- 不依赖 unpkg；
- 不依赖 jsDelivr；
- 不依赖 cdnjs；
- 不依赖 Google Fonts。

用户点击原始证据来源链接时仍会打开外部网站，这是证据追溯功能，不属于启动依赖。

## 自动测试

新增 `tests/test_frontend_offline_assets.py`，覆盖：

- 关键运行时不再引用公共 CDN；
- 本地 script/link 静态资源真实存在；
- React 和 ReactDOM 版本固定为 18.3.1；
- vendor JS 文件非空且不是 HTML 错误页；
- LICENSE 文件存在；
- SHA-256 清单与文件一致；
- FastAPI 能返回 vendor 静态资源；
- 首页导航和“研发证据查询”四个页签仍存在；
- 原始证据 `source_url` 未被改成本地路径；
- `static/index.html` 与 `template.html`、`component.js` 构建结果保持同步。

本轮回归测试：

```text
.venv/bin/python webapp/frontend_src/build.py
static/index.html written: 688695 bytes

node --check webapp/frontend_src/component.js
OK

node --check webapp/static/dc-runtime.js
OK

.venv/bin/python -m unittest tests/test_frontend_offline_assets.py
14 tests OK

.venv/bin/python -m unittest tests/test_evidence_frontend.py
24 tests OK

.venv/bin/python -m unittest tests/test_evidence_chain_frontend.py
25 tests OK

.venv/bin/python -m unittest tests/test_company_evidence_comparison_frontend.py
23 tests OK

.venv/bin/python -m unittest tests/test_grounded_qa_frontend.py
37 tests OK

.venv/bin/python -m unittest tests/test_deployment_health.py
8 tests OK

.venv/bin/python -m unittest tests/test_deployment_config.py
12 tests OK

git diff --check
OK
```

## 浏览器断网验证

本阶段完成了本地 HTTP 语义、静态资源、源码和构建一致性检查。当前环境没有可用的浏览器自动化工具，因此未伪造真实断网浏览器验收结果。

尝试启动轻量 Uvicorn：

```text
.venv/bin/python -m uvicorn webapp.main:app --host 127.0.0.1 --port 8767
Application startup complete.
```

当前沙箱中 `curl http://127.0.0.1:8767/...` 被环境代理或本地网络命名空间限制阻断：不加 `--noproxy` 时返回代理层 503；加 `--noproxy '*'` 后请求未到达 Uvicorn 日志并超时。因此未记录为真实 curl smoke 通过。

使用同一 FastAPI app 的进程内 ASGI 请求验证：

```text
GET /                                         200 text/html
GET /health                                  200 application/json
GET /ready                                   200 application/json, source_count=31
GET /static/vendor/react/...18.3.1.js        200 text/javascript
GET /static/vendor/react-dom/...18.3.1.js    200 text/javascript
GET /static/vendor/babel/...7.26.4.js        200 text/javascript
GET /api/evidence/summary                    200 application/json, total_sources=31
```

建议人工验证步骤：

```bash
.venv/bin/python -m uvicorn webapp.main:app --host 127.0.0.1 --port 8767
```

在浏览器打开：

```text
http://127.0.0.1:8767
```

预期：

- 页面成功渲染；
- 侧边栏可见；
- “研发证据查询”可见；
- “来源检索 / 证据链 / 企业对比 / 循证问答”四个页签可见；
- 浏览器控制台没有 React、ReactDOM 或 Babel 加载失败错误。

## 尚未解决的外部资源风险

- 原始证据链接仍依赖外部网站可访问性，但这只影响用户点击后查看原始来源，不影响页面启动。
- 若未来新增 `x-import` 外部组件并使用远程 `from` URL，需要单独审计并本地化对应组件资源。

## 补充修复记录

同日补充了轻量部署下的旧功能隔离和控制台清理：

- 新增 `/api/runtime-capabilities`，页面启动先判断比赛核心和旧功能可用性。
- 轻量环境默认进入“研发证据查询”，不自动请求 `/api/bootstrap`、`/api/profile`、`/api/dashboard`。
- 旧功能导航保留但显示“旧数据未配置”；点击不可用旧功能只显示中文提示，不发送无意义旧接口请求。
- 旧工作台固定兜底统计不在轻量模式分支展示，避免被误解为真实比赛数据。
- 模板中的动态 SVG `path d`、`polyline points`、`line x1/y1/x2/y2` 改为组件值中安全生成 React SVG 元素，空数据时不渲染。
- 新增本地 `webapp/static/favicon.svg`，`template.html` 引用 `/static/favicon.svg`，FastAPI `/favicon.ico` 返回同一 SVG。
- 新增 `tests/test_runtime_capabilities.py` 和 `tests/test_legacy_frontend_degradation.py` 覆盖上述行为。

详细记录见 `docs/day5_legacy_degradation_validation.md`。

本地人工验收结论：

> 轻量模式人工复验通过：默认进入研发证据查询，无旧API请求，无SVG和favicon错误，四个页签正常，旧功能降级正常。

该结论为本地浏览器人工验收，不是 Render 线上验收。验收确认本地 vendor React、ReactDOM、Babel 均能加载，favicon 不再 404，四个循证页签人工操作正常。
