# Day 5 第四阶段补充：旧功能友好隔离与控制台清理

日期：2026-07-23
分支：`feature/day5-release-deploy`

本阶段处理轻量部署环境下旧企业分析功能的降级入口，不修改比赛核心证据 API、证据事实、证据链配置或 DeepSeek 调用规则。

## 问题根因

旧首页默认页是 `today`，`componentDidMount()` 会同时执行 `loadBootstrap()` 和 `loadPage()`。因此轻量环境打开首页时会自动请求 `/api/bootstrap` 和 `/api/dashboard`；进入旧公司画像、研报、数据库、时间轴和高级分析时还会按旧逻辑请求 `/api/profile`、`/api/compare`、`/api/timeline`、`/api/database/*`、`/api/advanced` 等接口。

轻量依赖不包含旧企业分析所需的完整 SQLite/Chroma 数据和可选依赖时，旧接口会返回友好 503。前端原先吞掉失败并保留固定兜底统计，所以用户容易看到 48、312、18642、1286 等前端旧兜底数字，并误以为是真实比赛数据。

SVG 控制台错误来自模板中直接写入动态 SVG 属性，例如 `path d="{{ ... }}"`、`polyline points="{{ ... }}"` 和 `line x1="{{ ... }}"`。浏览器在自定义模板运行时接管前会先解析这些原始属性，导致未解析的 `{{ ... }}` 进入 SVG 属性校验。

## 运行能力接口

新增：

```text
GET /api/runtime-capabilities
```

轻量环境预期响应：

```json
{
  "competition_core_available": true,
  "legacy_features_available": false,
  "default_page": "evidence",
  "legacy_unavailable_reason": "旧企业分析数据或可选依赖未配置"
}
```

判断方式：

- `competition_core_available`：只校验比赛核心 CSV/JSON 服务和证据链服务能读取本地数据。
- `legacy_features_available`：要求旧 SQLite 必要表存在且有真实行数，并且旧功能需要的可选依赖可被发现。
- 检查过程不加载 Chroma、sentence-transformers、Torch、Streamlit 或 Pandas 模块本体。
- 不创建 DeepSeek 客户端，不读取或返回密钥，不访问网络，不返回绝对路径或异常堆栈。
- 不使用 `.env` 是否存在作为判断条件。

完整旧环境满足旧 SQLite 数据和可选依赖时，`default_page` 保持 `today`；轻量环境为 `evidence`。

## 前端降级行为

页面启动先请求 `/api/runtime-capabilities`。

轻量环境：

- 默认进入“研发证据查询”；
- 不自动请求 `/api/bootstrap`、`/api/profile`、`/api/dashboard` 等旧接口；
- 旧导航保留但显示“旧数据未配置”；
- 点击旧功能时显示中文提示，不发送无意义旧接口请求；
- 不展示固定旧业务统计卡片；
- “来源检索 / 证据链 / 企业对比 / 循证问答”四个页签继续使用比赛核心接口。

完整旧环境：

- 保留原默认工作台；
- 保留旧导航和旧接口请求逻辑；
- 旧统计只来自 `/api/bootstrap` 等真实旧接口结果。

## SVG 与 favicon

SVG 修复采用与当前模板运行时兼容的最小方案：模板不再把动态绑定直接写入敏感 SVG 属性，而是在组件值中用 React 生成 `path`、`polyline` 和 `line` 元素。空数据或旧功能不可用时返回 `null`，不渲染对应 SVG 元素。

新增本地 `webapp/static/favicon.svg`，`template.html` 通过 `/static/favicon.svg` 引用，同时 FastAPI 提供 `/favicon.ico`，返回 `image/svg+xml`，避免浏览器默认请求 favicon 时出现 404。

## 自动测试

新增：

- `tests/test_runtime_capabilities.py`
- `tests/test_legacy_frontend_degradation.py`

覆盖能力接口轻量响应、重依赖未加载、DeepSeek 客户端未创建、路径和密钥不泄露、轻量启动不自动打旧接口、默认 evidence、旧功能友好提示、固定旧统计不在轻量分支展示、无无限重试、旧代码保留、SVG 原始绑定清理、未屏蔽 `console.error`、favicon ASGI 200、本地 vendor 资源仍在、四个循证页签仍在、构建产物与源码一致。

## 待人工验证

启动：

```bash
.venv/bin/python -m uvicorn webapp.main:app --host 127.0.0.1 --port 8767
```

浏览器打开：

```text
http://127.0.0.1:8767
```

预期：

- 首屏进入“研发证据查询”；
- Network 中不出现启动自动请求 `/api/bootstrap`、`/api/profile`、`/api/dashboard`；
- 旧导航显示“旧数据未配置”，点击后出现中文提示；
- 控制台不再出现未解析 `{{ ... }}` 的 SVG 属性错误；
- `/favicon.ico` 或 `/static/favicon.svg` 不再 404；
- 四个循证页签可正常切换和查询。

## 本地人工验收记录

人工验收结论：

> 轻量模式人工复验通过：默认进入研发证据查询，无旧API请求，无SVG和favicon错误，四个页签正常，旧功能降级正常。

该结论为本地浏览器人工验收，不是 Render 线上验收。

记录项：

- 本地 vendor React、ReactDOM、Babel 均能加载。
- 轻量模式默认进入研发证据查询。
- `/api/runtime-capabilities` 正确返回核心可用、旧功能不可用、默认 evidence。
- 启动阶段没有 bootstrap/profile/dashboard 请求。
- Console 无 SVG 属性错误。
- favicon 不再 404。
- 四个循证页签人工操作正常。
- 旧功能友好降级。
