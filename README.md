# CLKG · Cultural Landscape Knowledge Graph

> **多项目、多模态文化遗产知识图谱基础设施**
> *A multi-project, multimodal knowledge graph infrastructure for cultural heritage research.*

[![License: MIT](https://img.shields.io/badge/Code-MIT-blue.svg)](LICENSE)
[![Docs: CC BY 4.0](https://img.shields.io/badge/Docs-CC%20BY%204.0-lightgrey.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.10+-3776AB.svg?logo=python&logoColor=white)](https://www.python.org/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16+-336791.svg?logo=postgresql&logoColor=white)](https://www.postgresql.org/)
[![PostGIS](https://img.shields.io/badge/PostGIS-3.4+-336791.svg)](https://postgis.net/)

---

## What is CLKG?

CLKG provides a PostgreSQL + PostGIS backend, a CIDOC-CRM-aligned ontology (CL-Onto), and a Python ingest pipeline for cultural heritage knowledge graphs. It currently supports three research projects: **Mustang** (Nepal/Tibet trans-Himalayan cultural landscape), **Qiaopi** (Chaoshan overseas Chinese remittance letters, UNESCO Memory of the World), and **Xinjiang** (Silk Road immovable cultural heritage). The architecture is region-agnostic — new projects can be added without schema migration.

## 中文概述

CLKG 是一个**跨项目、跨模态**的文化遗产知识图谱基础设施，包含三层：

1. **本体层（CL-Onto）**：基于 CIDOC CRM 的实体-关系建模，含 6 类核心实体（地点 / 文化景观单元 / 人物 / 文档 / 资产 / 事件）
2. **存储层（PostgreSQL + PostGIS）**：每个研究项目一个独立数据库（`{region}_cl_kg`），4D-fluent 三元组 + PROV-O 溯源
3. **采集层（Python ingest + Excel 模板）**：多人协作 SOP + 受控词表 + 自动幂等入库

目前覆盖**木斯塘 / 潮汕侨批 / 新疆**三个研究项目，架构支持任意新项目无缝加入。

---

## Repository Layout · 仓库结构

```
clkg/
├── ingest/                Python ingest package (imported as `ingest`, unnumbered)
│   ├── config.py          env-driven configuration
│   ├── db.py              PG connection + health probe
│   ├── staging.py         StatementRow + bulk staging writes
│   ├── collection_schema.py  single source of truth for the template
│   ├── connectors/        tabular / shapefile / images / qiaopi / template / xinjiang
│   ├── extractors/        LLM-augmented NER (Qwen, off by default)
│   ├── pipelines/         per-project orchestrators
│   ├── cli.py             python -m ingest.cli ...
│   └── watchfolder.py     inbox/ daemon
│
├── 01_sql/                PostgreSQL DDL
│   ├── 00_create_schema.sql three-table CL-Onto schema
│   ├── 01_staging.sql     staging schema
│   ├── 02_pid_minter.sql  region-agnostic PID minter (SECURITY DEFINER)
│   ├── 03_ingest_batch.sql single-transaction promotion to business tables
│   ├── 04_grants.sql      role permissions
│   └── smoke_test/        standalone PG-side smoke / maintenance SQL
│
├── 02_data_collection/    Multi-collaborator collection toolkit
│   ├── SOP_数据采集.md     8-section standard operating procedure (Chinese)
│   ├── CLKG_采集模板.xlsx  collection sheets + 军垦 extension + vocab
│   ├── build_template.py  template generator (from ingest.collection_schema)
│   ├── audit_quality.py   6-dimension data quality self-check
│   ├── export_authority.py authority-list exporter
│   ├── 会议速览_招募.md     1-page recruitment briefing
│   └── quality-audit/     per-project audit reports (local only)
│
├── 03_docs/               design documents
│   ├── 技术说明与实验设计手册.md  main planning manual
│   └── inventory.md       data-asset inventory
│
├── 04_reports/            run reports (REPORT_*.md / .html)
├── 05_viz/                demo visualizations + presentation + demo_queries.sql
├── 06_design_legacy/      early schema design (archived CSVs)
├── data/                  raw / intermediate research data (gitignored, local only)
└── requirements.txt
```

> **📦 关于研究产出**：本仓库**只包含基础设施代码 + 文档**。具体研究产出（论文草稿、研究叙述、综述、qiaopi-geofinance 实证发现等）保存在私有研究仓库中。论文发表后将逐步迁移至公开仓库并附 DOI 链接。

---

## Quick Start · 快速开始

### 1. Prerequisites

- Python 3.10+ (Anaconda recommended)
- PostgreSQL 16+ with PostGIS 3.4+ extension
- Optional: DashScope (Qwen LLM) API key for NER

### 2. Install

```bash
git clone https://github.com/lamue-0105/clkg.git
cd clkg
pip install -r requirements.txt
cp .env.example .env
# 编辑 .env：填入 PG_PASSWORD / NAS_ROOT / (optional) DASHSCOPE_API_KEY
```

### 3. PG-side setup (per project database)

```bash
createdb mustang_cl_kg
psql -d mustang_cl_kg -c "CREATE EXTENSION postgis;"
for f in sql/01_staging.sql sql/02_pid_minter.sql sql/03_ingest_batch.sql sql/04_grants.sql; do
  psql -d mustang_cl_kg -f "$f"
done
```

### 4. Verify

```bash
python -m ingest.cli check mustang
```

### 5. Run first ingest

```bash
python -m ingest.cli mustang --rows 10
```

---

## For Collaborators · 招募协作者用法

If you are joining the data collection effort:

1. **Read first**: `data_collection/SOP_数据采集.md` (~10 min) and `data_collection/会议速览_招募.md` (5 min)
2. **Get the template**: `data_collection/CLKG_采集模板.xlsx` —— 打开"填写说明" sheet
3. **Three red lines**:
   - 坐标系不自己换算（高德填 GCJ-02、GPS 填 WGS84）
   - 同一对象永远同一 `natural_key`
   - 每行都要有来源（Zotero key / 馆藏号 / URL / 田野编号）
4. **Submit**: 填好的 xlsx 提交给负责人，由负责人执行 `python -m ingest.cli` 入库

You do **not** need to know the database internals to contribute.

---

## Data Quality · 数据质量自检

CLKG 的核心 selling point 之一是**质量可查询**。SOP §8 定义了 6 个维度评估标准：

```bash
python data_collection/audit_quality.py mustang
# → quality-audit/mustang-YYYY-MM-DD.md
```

输出 Markdown 报告含：实体覆盖度、跨表关联完整性、来源链完整性、空间精度、本体一致性、多模态对齐。

---

## Project Region Onboarding · 新项目接入

完全不需要修改 SOP 或模板，三步：

```bash
# 1. 词表加 region（在 CLKG_采集模板.xlsx 的「词表」sheet 底部追加，或修改 build_template.py 重生成）

# 2. 创建 PG 库（mint_pid 序列懒加载，无需 schema migration）
createdb {new_region}_cl_kg
psql -d {new_region}_cl_kg -c "CREATE EXTENSION postgis;"
for f in sql/0{1..4}_*.sql; do psql -d {new_region}_cl_kg -f "$f"; done

# 3. 创建 NAS 子目录
mkdir -p /Volumes/clkg_data/{new_region}/{tabular,photos,gis}
```

---

## Citation · 学术引用

If you use CLKG in your research, please cite as:

```bibtex
@software{clkg2026,
  author = {lamue},
  title  = {{CLKG}: Cultural Landscape Knowledge Graph},
  year   = {2026},
  url    = {https://github.com/lamue-0105/clkg},
  note   = {Version 0.1.0}
}
```

See [`CITATION.cff`](CITATION.cff) for machine-readable citation metadata.

---

## License · 许可

- **Code** (`*.py`, `*.sql`, `*.sh`): [MIT License](LICENSE)
- **Documentation** (`*.md`, SOP, design docs): [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/)
- **Data** (authority lists, manuscripts): NOT included; see private research repository.

---

## Status · 当前状态

| 模块 | 状态 |
|---|---|
| PG 三表（staging / business / evidence）| ✅ Production |
| PID 发号器（region-agnostic）| ✅ Production |
| ingest_batch 单事务存储过程 | ✅ Production |
| Tabular / Image / Shapefile connectors | ✅ Production |
| Qiaopi-specific connector | ✅ Production |
| Mustang pipeline end-to-end | ✅ Production |
| Qwen NER（默认关）| 🟡 Available |
| 数据采集 SOP + 模板 | ✅ v1（招募会用）|
| 6 维度质量自检 | ✅ v1 |
| Watchfolder daemon | ✅ Production |
| RDF/Turtle 导出 | 🚧 Roadmap |
| PDF / Audio connectors | 🚧 Roadmap |
| Federated cross-region querying | 🚧 Roadmap |

---

## Acknowledgments

This work is part of an ongoing doctoral research project on **Spatio-Temporal Semantic Alignment for Multimodal Cultural Heritage Knowledge Graphs**. The author thanks all collaborators in the Mustang, Qiaopi, and Xinjiang sub-projects.

---

## Contact

Issues and questions: please use [GitHub Issues](https://github.com/lamue-0105/clkg/issues).
