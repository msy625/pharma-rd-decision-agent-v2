# 启动脚本目录

这个目录只保留面向演示和本地运行的启动脚本，避免项目根目录堆满薄封装文件。

## Streamlit 页面入口

- `streamlit run scripts/streamlit/system_console.py`
- `streamlit run scripts/streamlit/chat_console.py`
- `streamlit run scripts/streamlit/analysis_studio.py`
- `streamlit run scripts/streamlit/stakeholder_console.py`
- `streamlit run scripts/streamlit/trace_console.py`
- `streamlit run scripts/streamlit/report_studio.py`

## 数据与缓存脚本

这类脚本统一改为模块方式运行：

- `python3 -m deepinsight.dataops.db_init`
- `python3 -m deepinsight.dataops.db_expand`
- `python3 -m deepinsight.dataops.data_pipeline`
- `python3 -m deepinsight.dataops.macro_import`
- `python3 -m deepinsight.dataops.graph_data_pipeline`
- `python3 -m deepinsight.demo.demo_cache`

## 研发阶段与疾病方向数据

按 `config/direction_catalog.json` 定义的 6 阶段 / 20 方向采集与维护 `data/template/` 规范化表：

- `python scripts/harvest_direction_data.py` —— 从 ClinicalTrials.gov v2 与 PubMed E-utilities 采集，幂等
- `python scripts/validate_direction_dataset.py` —— 离线校验方向记录数、上游标识与跨表引用
- `python scripts/localize_organization_names.py` —— 应用机构中文名对照表（幂等，`--report-unmatched` 可列出未收录机构）
- `python scripts/drop_individual_investigators.py` —— 清理被误当成机构的个人研究者条目（`--report` 只列不删）

采集脚本默认把 HTTP 响应缓存到 `.cache/direction_harvest/`（已 gitignore），
可用 `--cache-dir` 改路径、`--refresh` 忽略缓存。

## 证据校验与比赛打包

- `python scripts/validate_source_registry.py` —— 校验 39 条人工核验来源登记表
- `python scripts/query_source_registry.py --summary` —— 查询来源登记表（`--format json` 可机读）
- `python scripts/build_formal_evaluation_cases.py` —— 构建评测用例
- `python scripts/validate_competition_package.py` —— 比赛精简包离线验证入口
- `python scripts/build_competition_staging.py --output-dir <dir>` —— 按白名单生成比赛暂存目录
- `python scripts/add_astrazeneca_sources.py` —— 重建阿斯利康补充批次（幂等）
