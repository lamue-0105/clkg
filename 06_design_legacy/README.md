# 设计演进史 · CL-Onto 早期框架

本目录保存了 CLKG 项目 **早期设计草案**（2026 年 4 月前后），以 8 张 CSV 表的形式记录了最初的本体设想。

> **它们已经不再是实施层的"权威定义"**——当前权威是 `~/clkg/sql/00_create_schema.sql` 和实际部署的 PG schema。
> 这些 CSV 保留下来是 **设计演进的历史快照**，未来写论文 / 整理本体时是宝贵的"思路演化"素材。

---

## 文件清单（8 张表）

| 文件 | 内容 |
|---|---|
| `遗产核心类标准化总表.csv` | 7 个 Class 定义（CLU/PeriodizedPlace/Event/Actor/Evidence/Geometry/TimeSpan） |
| `通用基础字段.csv` | 6 个跨实体共有字段（EntityID/StandardName/Lang/DataSource/CreateTime/Status） |
| `地名专项字段.csv` | 5 个地名字段（CHGIS_Code/AdminLevel/GeoType/CoordSystem/HistoryAlias） |
| `图像专项字段.csv` | 5 个图像字段（IIIF_ImageURI/ImageFormat/ImageRights/ImageDesc/ImageResolution） |
| `跨库关联关系表.csv` | 5 种关联类型（空间/时间/语义/主体/层级） |
| `PID 唯一编码表.csv` | 早期 PID 格式 `LAB-XJ-PLC-00000001`（机构-项目-类型-序号） |
| `项目基础信息.csv` | 项目元数据模板 |
| `项目专属扩展字段表.csv` | 新疆文保 / 木斯塘的专项扩展字段 |

---

## 这套设计 → 当前实现的演进

### ✅ 已落地（直接对应）

| 早期设计 | 当前实现 |
|---|---|
| 7 个 Class | 3 张表（evidence / conceptual_entity / entity_statement）+ 多种 `entity_type` 缩写 |
| TimeSpan 独立实体 | `valid_time_start/end` 直接挂在 statement 上（扁平化） |
| Geometry 独立实体 | `entity_statement.object_geometry` 是 PostGIS 几何 |
| **CulturalLandscapeUnit** 概念 | **2026-05-18 实现**：Mustang 220 个聚合实体升级为 `entity_type='clu'` |
| Lang 多语言字段 | `conceptual_entity.label_zh` + `label_en` |
| DataSource 字段 | `evidence.source_name` + `evidence.metadata` |
| 5 种关联类型 | 谓词驱动（`hasSender`/`depicts`/`locatedAt`/`containsPlace` 等）|
| PID 格式 `LAB-XJ-PLC-00000001` | 演进为 `clkg:{region}:{type}-{temporal}-{serial}`，按区域 + 类型独立序列 |

### 🔓 已规划、待落地

| 早期设计 | 当前状态 | 备注 |
|---|---|---|
| CHGIS_Code 历史地名标准编码 | 尚未对齐 | 需要写"CHGIS 对齐工作流" |
| AdminLevel 行政层级 | 谓词未加 | 接新疆三普数据时会用上 `hasAdminLevel` |
| HistoryAlias 历史别称 | 谓词未加 | 4D-fluents 天然支持（不同时段不同名） |
| IIIF_ImageURI 标准化图像 URL | 仅存文件路径 | 需要部署 IIIF 服务器后补充 |
| ImageRights 版权声明 | 谓词未加 | 接新图像数据时直接加 `hasImageRights` |
| Status 数据有效性 | 谓词未加 | 加 `hasStatus` 谓词即可 |
| CIDOC-CRM 标准对齐 | 未对齐 | 写谓词命名规范时一并完成 |

### ⚠️ 被替换 / 简化

| 早期设计 | 演进决定 | 原因 |
|---|---|---|
| 7 个独立 Class | 3 张表 + entity_type 枚举 | RDF schema-less 思想；实际查询性能更好；新增类型不改 schema |
| PID 加机构前缀（LAB） | 暂不加 | 现阶段单机构；跨机构合并时再加 |
| TimeSpan 独立实体 | 扁平到 statement 上 | 简化查询；导出 RDF 时再展开 |
| Geometry 独立实体 | 内嵌到 statement 上 | PostGIS 直接支持 |
| 必选字段强约束（如 StandardName 必填） | 通过 ingest_batch 的 hasName 抽取 | 让数据进入后再渐进式补全 |

---

## 这份遗产对未来工作的价值

1. **谓词命名规范**：当我们整理 CL-Onto predicates 时，参考这里的字段名命名风格
2. **CIDOC-CRM 对齐**：这里明确引用了 CIDOC-CRM/IIIF/CHGIS 三大标准，给未来对齐提供锚点
3. **学术论文素材**：从"7-Class 框架"到"3-Table CL-Onto"的演进过程，是一个完整的"研究决策"叙事
4. **新项目本体设计参考**：当某个新遗产项目需要扩展字段时，先看 `项目专属扩展字段表.csv` 里有没有类似的（如 Heritage_Level、Risk_Level、Eco_Index）

---

## 维护原则

**不修改本目录**——这是历史快照，应保持原貌。

新的本体演进决策应该：
- 记在 `~/clkg/REPORT_*.md` 阶段报告里
- 落实到 `~/clkg/sql/00_create_schema.sql` 真实 schema
- 或者写到 `~/clkg/predicates.md`（待建）的谓词命名规范里

如果未来真有重大本体重写，**复制一份新快照到 `design_legacy/v2_2027xx/`**，保持每次"代际跃迁"都有归档。
