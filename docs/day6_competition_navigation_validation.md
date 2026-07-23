# Day6 第五阶段：比赛模式导航与前半段业务闭环验证报告

日期：2026-07-23（2026-07-24 完成最终浏览器验收）
分支：`feature/day6-legacy-integration`
起点提交：`6af28cf827671473d6e389cd92ad2da8fac47a09 feat: add rd event timeline`

## 1. 阶段目标

本阶段把已经完成的研发决策工作台、企业证据画像、研发事件时间轴、研发证据中心和循证问答整理成比赛前半段业务闭环。旧智能问答、自动化研报、旧白盒溯源、数据库浏览和高级分析仍保留历史代码与 API，但不再进入比赛导航、启动初始化或默认渲染路径。

本阶段不修改 `data/source_registry.csv` 或 `config` 事实数据，不部署 Render，不合并 `main`，不读取 `.env`，不调用真实 DeepSeek，也不访问网络。

## 2. 五入口比赛导航

比赛主导航固定为：

1. `today`：研发决策总览。
2. `compare`：企业证据画像。
3. `timeline`：研发事件时间轴。
4. `evidence`：研发证据中心。
5. `groundedQa`：循证问答。

旧“工作流/数据与分析”分组、灰色不可用入口、全局企业与年份过滤、排名范围、向量 Top K、旧 DeepSeek 状态和演示动线均不进入比赛模板。

## 3. Grounded QA 一级入口

新增真实一级页面 `page=groundedQa`。页面继续复用原有：

- Grounded QA 状态。
- `loadGroundedCapabilities()`。
- `submitGroundedQA()`。
- local/auto 模式。
- 回答、引用、限制、安全提示和白盒过程。

请求接口仍仅为：

- `GET /api/evidence/grounded-qa/capabilities`
- `POST /api/evidence/grounded-qa`

不调用旧 `/api/chat`。capabilities 请求失败时，前端使用 `local_mode_available=true`、`llm_mode_available=false` 和 `groundedMode=local` 的本地回退状态，并明确提示本地循证摘要仍可使用。

## 4. 研发证据中心

“研发证据查询”统一更名为“研发证据中心”，内部只保留：

- 来源检索。
- 证据链。
- 企业对比。

原内部 Grounded QA 页签不再展示，但问答状态、组件和方法继续由一级页面复用。证据中心页头提供“进入循证问答”入口。

## 5. Legacy 隔离

- `componentDidMount()` 不再调用 `_initConvs()`。
- runtime capabilities 初始化不再调用 `/api/bootstrap`。
- `legacy_features_available=true` 不会触发比赛启动加载旧数据。
- `renderVals()` 默认只组合五个比赛页面需要的视图模型。
- `chatVals()`、`researchVals()`、`whiteboxVals()`、`databaseVals()` 和 `advancedVals()` 只在明确进入对应旧页面时计算。
- 旧页面代码、模板和 `/api/profile`、`/api/compare`、`/api/timeline`、`/api/chat` 等 API 路由继续保留。

## 6. 品牌

产品主品牌统一为：

- 药研制策。
- 可信医药研发证据智能分析。
- HTML title：`药研制策｜可信医药研发证据智能分析`。
- FastAPI title：`药研制策｜可信医药研发证据智能分析`。

README 和开发文档继续保留 DeepInsight 原项目来源、授权及历史贡献说明。

## 7. 业务闭环

- 工作台企业卡片设置 `companyProfileCompany` 后进入企业证据画像。
- 工作台提供明确的“查看研发事件时间轴”入口。
- 企业画像试验链进入研发证据中心并加载对应 `chain_id`。
- 时间轴事件支持查看来源、证据链、一级循证问答和原始来源。
- 研发证据中心可进入一级循证问答。
- 循证问答引用可进入来源检索并加载对应 `source_id`。
- 循证问答相关证据链可进入证据中心并加载对应 `chain_id`。

页面间只传递 `companyProfileCompany`、`source_id`、`chain_id` 或预填问题，没有新增复杂跨页面全局状态。

## 8. 浏览器人工验收

2026-07-24 本地浏览器验收通过：品牌、五个一级入口、页面高亮、证据中心三页签及各页面闭环跳转正常；比赛页面未请求旧 `/api/bootstrap`、`/api/profile`、`/api/chat` 或旧 `/api/timeline`。循证问答 local 模式对“B016是否代表替雷利珠单抗围手术期NSCLC已经获得欧盟最终批准？”明确回答“不代表最终批准”，引用仅含 B015、B016，来源类型、日期、监管口径和来源详情跳转正确。

五个页面最终往返切换时 Console 无稳定可复现错误。期间曾出现外部来源 HEAD/CORS 信息；静态审计确认仓库内不存在相应调用路径，且未修改代码后无法复现，因此不做猜测性业务修改。若再次出现，应以 Network Initiator 定位外部发起者。

## 9. 自动验证

按本阶段指定顺序完成本地离线验证：

- 前端构建：通过，`webapp/static/index.html` 已由 `build.py` 重新生成。
- `node --check webapp/frontend_src/component.js`：通过。
- 本阶段相关 Python 文件语法检查：通过。
- `frontend_src` 与 `webapp/static/index.html` 同步检查：通过。
- 比赛导航测试：14 项通过。
- 工作台、企业画像和研发事件时间轴测试：101 项通过。
- 来源检索、证据链和企业对比测试：193 项通过。
- Grounded QA 服务、API、前端、LLM 本地桩、限流和用量保护测试：142 项通过，包含中文紧邻 source_id、B016 锚点仅允许 B015/B016 及来源类型摘要回归。
- runtime capabilities、offline assets 和 legacy degradation 测试：31 项通过。
- 自动测试合计：481 项通过，0 项失败。
- 来源登记表验证：通过，31 条来源完整，`H001-H015` 与 `B001-B016` 连续且结构有效。
- `git diff --check`：通过。

以上自动验证未读取 `.env`，未调用真实 DeepSeek，未访问网络，也未加载比赛页面不需要的旧 SQLite/Chroma 主链路。

## 10. 下一步

浏览器人工验收已通过；完成本轮最终自动回归和安全检查后，可由用户手动提交。下一步整理比赛材料；当前不开始自动化证据研报，不部署 Render。
