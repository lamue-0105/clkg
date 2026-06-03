# CLKG 数据采集标准作业流程（SOP）

> 版本 v1 · 2026-06-01 · 适用于文化景观知识图谱（CLKG）多人协作数据采集
> 配套文件：`CLKG_采集模板.xlsx`（采集用）、`会议速览_招募.md`（招募会用）

---

## 0. 这份 SOP 想解决什么

我们要把**很多人采集的数据**汇入**同一张知识图谱**。多人协作最大的风险不是采得慢，而是**采得不一致**——每个人对"名字怎么写、坐标记哪个系、来源怎么标"各有一套，事后再统一会指数级地痛。

所以本 SOP 的核心原则只有一句：

> **把约束放在采集那一刻**——用受控词表、固定格式、强制来源，让数据"进来时就是对的"。

你只需要照 `CLKG_采集模板.xlsx` 填表，规则都内置在下拉和批注里。本文档解释**为什么**这么填，以及负责人如何审核入库。

---

## 1. 跨项目结构总览（先看这张图）

CLKG 同时跑多个项目（mustang / qiaopi / xinjiang …），但**只用一套 SOP + 一份模板**。架构按三层组织：

```
┌─────────────────────────────────────────────────────────────────┐
│  🔵 共享层（一套服务所有项目）                                 │
│  · 规范文档：SOP_数据采集.md · 会议速览_招募.md                │
│  · 采集工具：CLKG_采集模板.xlsx（4 张采集表 + 词表 + 填写说明）│
│  · 本体词表：词表 sheet 的 11 类下拉（dv_<key> 动态绑定）      │
│  · 维护脚本：build_template.py / export_authority.py           │
│  · 实体类型：pl / clu / ac / doc / img / ev（统一语义）        │
│  · 通用谓词：hasName / hasType / locatedAt / hasNotes …        │
└────────────────────────────┬────────────────────────────────────┘
                             │ region 字段路由
        ┌────────────────────┼────────────────────┐
        ▼                    ▼                    ▼
┌───────────────┐    ┌───────────────┐    ┌───────────────┐
│ 🟢 Mustang   │    │ 🟠 Qiaopi    │    │ 🟣 Xinjiang  │ … kashgar / liangzhu / 新项目
├───────────────┤    ├───────────────┤    ├───────────────┤
│ 权威清单_     │    │ 权威清单_     │    │ 权威清单_     │
│ mustang.csv   │    │ qiaopi.csv    │    │ xinjiang.csv  │
│               │    │               │    │               │
│ NAS:          │    │ NAS:          │    │ NAS:          │
│ /Volumes/     │    │ /Volumes/     │    │ /Volumes/     │
│ clkg_data/    │    │ clkg_data/    │    │ clkg_data/    │
│ mustang/      │    │ qiaopi/       │    │ xinjiang/     │
│               │    │               │    │               │
│ PG:           │    │ PG:           │    │ PG:           │
│ mustang_cl_kg │    │ qiaopi_cl_kg  │    │ xinjiang_cl_kg│
│               │    │               │    │               │
│ 紫色扩展：    │    │ 紫色扩展：    │    │ 紫色扩展：    │
│ ❌ 不用       │    │ ✅ 全用       │    │ ❌ 不用       │
└──────────────┘    └──────────────┘    └──────────────┘
```

### 1.1 设计决策（为什么是这个结构）

| 决策 | 含义 | 好处 |
|---|---|---|
| **一份 SOP + 一份模板** 服务所有项目 | 不为每个项目造一套 | 新人只学一次；交接成本低 |
| **`region` 字段做路由** | 同一份 xlsx 可混采多项目 | 跨项目协作不切换工具 |
| **本体共享，扩展项目化** | pl/clu/ac/doc/img 语义对齐；紫色扩展按项目自治 | 跨项目可比性 + 项目灵活性 |
| **权威清单分项目** | 每项目一份 CSV | 去重在项目内部，不跨项目误归并 |
| **PG 一项目一库** | mustang_cl_kg / qiaopi_cl_kg 互不干涉 | 大改不影响其他项目；性能独立 |
| **NAS 一项目一目录** | `/Volumes/clkg_data/{region}/` | 物理隔离 + 路径可预测 |

### 1.2 各项目差异速查

| 维度 | Mustang | Qiaopi | Xinjiang |
|---|---|---|---|
| 主用表 | Place（多 clu）+ Asset | Document + Actor + Place | Place（多 pl/clu） |
| 紫色扩展（侨批 9 列） | ❌ | ✅ | ❌ |
| 主要 source_type | field_survey + gis_dataset | archive + literature | field_survey + literature |
| 主要 CRS | EPSG:32644（UTM 44N） | GCJ-02（高德） | WGS84 / CGCS2000 |
| 关键空间推断 | ST_Contains 自动建 containsPlace | 暂无 | 暂无 |
| 关键审计点 | hasType 12 值的归一 | hasCurrency 与 hasPaidAmount 双币种校验 | 待定 |

### 1.3 新项目加入流程（仅负责人执行）

完全不需要改 SOP 或模板，三步即可：

```bash
# Step 1: 词表加 region
#   在 build_template.py 的 VOCAB['region'] 末尾追加，或直接在 词表 sheet 底部追加后重生成

# Step 2: 创建 PG 库（mint_pid 序列懒加载，无需建表迁移）
createdb {new_region}_cl_kg
psql -d {new_region}_cl_kg \
     -f ~/clkg/sql/01_staging.sql \
     -f ~/clkg/sql/02_pid_minter.sql \
     -f ~/clkg/sql/03_ingest_batch.sql

# Step 3: 创建 NAS 子目录
mkdir -p /Volumes/clkg_data/{new_region}/{tabular,photos,gis}
```

之后采集者把模板的 `region` 列填 `{new_region}` 即可——本体、词表、SOP、审核流程**完全复用**。

---

## 2. 数据模型速览（采集者必读，3 分钟）

CLKG 不是宽表，是**三元组（SPO）模型**：一切事实都是「主语 → 谓词 → 宾语」。底层三张表：

| 表 | 作用 | 你不用直接碰 |
|---|---|---|
| `conceptual_entity` | 实体登记册（每个地点/人/文档一行，自动发 PID） | ✅ 系统自动 |
| `entity_statement` | 三元组事实（名称、坐标、关系……） | ✅ 由模板自动展开 |
| `evidence` | 来源/证据（谁、何时、从哪采的） | ✅ 由模板自动展开 |

**你只需要填宽表（一行 = 一个实体），我在 ingest 阶段把它"融化"成三元组。** 这样你填得轻松，进库又干净。

### 2.1 实体类型（entity_type）——共 6 种

| 代码 | 全称 | 含义 | 填哪张表 |
|---|---|---|---|
| `pl` | Place | 单体地点（一座庙、一个村、一处遗址） | Place_地点 |
| `clu` | CulturalLandscapeUnit | 文化景观单元（**群体/区域**，多个地点的聚合） | Place_地点 |
| `ac` | Actor | 人物 / 家族 / 机构 | Actor_人物 |
| `doc` | Document | 文档（侨批、档案、口述史转写） | Document_文档 |
| `img` | Image/Asset | 图像、录音、录像等多模态资产 | Asset_资产 |
| `ev` | Event | 事件（暂未启用） | — |

> **clu vs pl 判定规则**：如果它是"一群同类东西"或"一片区域"（如 Mustang 的"群体""区域"图层）→ 记 `clu`；如果是可以单独定位的一处 → 记 `pl`。拿不准时记 `pl` 并在备注里说明，审核时再定。

---

## 3. 八块标准流程

### ① 采集单元定义：一行填什么

- **一行 = 一个实体**（一个地点、一个人、一份文档、一个资产）。
- 不要把两个地点塞进一行，也不要把一个地点拆成多行。
- 跨表引用要靠 **natural_key**（见 ③）：比如一封侨批的寄件人，要在 `Document_文档` 里填 `hasSender = 那个人的 natural_key`，同时去 `Actor_人物` 表给那个人单独建一行。

### ② 来源 / 证据（**不可省**）

研究型知识图谱里，**没有来源的数据等于没有数据**。每一行都必须填：

| 列 | 填什么 |
|---|---|
| `记录人*` | 你的名字 |
| `采集日期*` | YYYY-MM-DD |
| `source_name_来源*` | 出处的唯一标识：文献→Zotero 引用键或「题名, 页码」；档案→馆藏号；网络→URL；田野→调查表编号 |
| `source_type_来源类型*` | 下拉选：literature / archive / field_survey / oral_history / gis_dataset / web / image_file / other |
| `confidence_可信度` | 把握程度：亲见/原档=1.0，二手可靠=0.9，推断=0.7，存疑=0.5 |

> 接 Zotero：文献类来源**优先填 Zotero 的 citation key**（如 `chen2019qiaopi`），这样能直接对回你的文献库。

### ③ natural_key：身份与去重的命根子

系统靠 `natural_key` 判断"这是不是同一个实体"。规则：

1. **同一个实体，永远用同一个 key。** 两个人采到同一座庙，必须填同一个 key，否则会被当成两座庙。
2. **优先复用已有的稳定编号**：遗产保护编码、侨批馆藏号、照片文件夹名。
3. 没有现成编号时，用结构化短码：`{region}-{type}-{有意义的英文/拼音短码}`，如 `mustang-pl-lomanthang`、`qiaopi-ac-chenmiaoqing`。
4. **采集前先查权威清单**（见 ⑥），别新建已存在的实体。

> 为什么这么重要：`natural_key` 是去重锚点。它对了，重复入库也不会产生重复实体（幂等）；它乱了，图谱里就会有一堆"双胞胎"。

### ④ 空间数据标准（**最大的坑，重点看**）

我们被坐标系坑过两次（Mustang 把 UTM 44N 当 45N；侨批把高德 GCJ-02 当 WGS84，偏移 50–500 米）。铁律：

> **如实记录原始坐标 + 声明它的坐标系来源（CRS），永远不要自己换算。** 换算由 ingest 阶段统一用 `ST_Transform` 做。

| 坐标来源 | CRS 应填 |
|---|---|
| 高德地图截的 | `GCJ-02` |
| 百度地图截的 | `BD-09` |
| 手机/相机 GPS、谷歌地球、天地图经纬度 | `WGS84` |
| 国内官方测绘成果 | `CGCS2000` |
| 国外 UTM 44 带（Mustang 等） | `EPSG:32644` |
| 实在不知道 | `unk`（并在备注说明，审核时定） |

- 经纬度一律填**十进制度**（如 `83.9567`），不要度分秒。
- 同时在 `坐标来源` 列写清楚（如"高德地图""实测 GPS""文献附图量取"）。

### ⑤ 多模态资产（照片 / 录音 / 录像 / 扫描件）

- **文件命名 & 存放**：资产放到 NAS 约定目录 `/Volumes/clkg_data/{region}/{photos|scans|audio}/`。
- **关联到实体**：把资产对应的地点/文档的 `natural_key` 填进资产行的 `depicts_关联实体`。
  - 便捷约定：照片放进**以地点 natural_key 命名的文件夹**，系统会自动关联（如 `photos/mustang-pl-lomanthang/`）。
- PG 里只存路径，不存文件本身。
- 注意版权/许可：非自己拍摄的，在备注注明来源与可用范围。

### ⑥ 去重 / 实体认领（权威清单）

- 负责人维护一份**权威实体清单**（已存在的 `natural_key` + 名称）。
- 采集前先认领任务、查清单：**已存在的实体不要重建**，补充信息时复用其 `natural_key`。
- 典型坑：同一座寺的两个名字（"白塔寺"/"妙应寺"）。约定**用一个主名作 `hasName`，其余写进备注**，由审核归并。

### ⑦ 采集模板（你天天用的东西）

`CLKG_采集模板.xlsx`，4 张采集表 + 1 张词表：

- **红色表头 = 必填**，蓝色表头 = 选填。
- 关键列有**下拉菜单**（entity_type / region / CRS / source_type 等），直接选，别手敲。
- 每张表第 2 行是**金标准示例行**（浅黄色），照着填，填完删掉。
- 鼠标悬停表头有**批注说明**怎么填。
- 拿不准的格子留空 + 在 `hasNotes_备注` 里写明，不要瞎猜填。

### ⑧ 质量闸门（提交 → 审核 → 入库 → 审计）

**采集者自查清单**（提交前逐条核对）：
- [ ] 所有红色必填列都填了
- [ ] `natural_key` 查过权威清单、没重复
- [ ] 凡填了坐标的，`CRS_坐标系` 一定填了
- [ ] `source_name` 能让别人找到原始出处
- [ ] 删掉了黄色示例行
- [ ] 下拉列没有手敲的错别字（如 `mustang` 不要写成 `Mustang`）

**负责人流程**：互查/抽查 → ingest 入 staging → 跑 `ingest_batch` → **predicate distinct-value 审计**（每个谓词的取值分布 vs 本体，发现异常用 `UPDATE` 归一化）→ 更新权威清单。

---

## 4. 角色与工作流

```
认领任务 → 采集(填模板) → 自查 → 提交 → 互查/抽查 → ingest → 审计 → 更新权威清单
   │           采集者              │        负责人/审核        负责人
   └────────────── 权威清单贯穿全程 ──────────────────┘
```

| 角色 | 职责 |
|---|---|
| 采集者 | 认领、查清单、按模板采集、自查、提交 |
| 审核员 | 互查/抽查、退回问题、确认可入库 |
| 负责人（你） | 维护权威清单与词表、ingest、审计归一化、扩展本体 |

---

## 5. 各数据类型的采集要点

| 数据类型 | 主表 | 要点 |
|---|---|---|
| 文献/档案抽取 | Document / Place / Actor | source_type 选 archive/literature；来源填 Zotero key 或馆藏号；提到的人和地各自建实体并互相引用 |
| 田野/实地记录 | Place / Asset | source_type=field_survey；坐标多为实测 GPS（WGS84）；照片放进以地点 key 命名的文件夹 |
| 现成 GIS/数据集 | Place（多为 clu） | source_type=gis_dataset；**务必声明原始 CRS**；面状要素记 clu |
| 网络/公开资料 | Place / Document | source_type=web；来源填 URL；**地图截图警惕 GCJ-02/BD-09** |
| 口述史 | Document + Actor + Asset | doc 存转写全文，受访者建 ac，录音建 img 资产；source_type=oral_history |
| 半结构化文本 | Document | 先按字段拆进对应列，拆不动的整段放 hasInnerLetter/hasDescription，备注说明 |

---

## 6. 本体参考（现有谓词，便于审核对照）

实体属性以谓词形式存储。常用谓词节选（完整清单见代码库 connectors，约 69 个）：

- **通用**：`hasName` `hasType` `hasDescription` `locatedAt`(坐标) `hasNotes`
- **行政层级**：`hasPrefecture` `hasCounty` `hasTown` `hasVillage` `hasAddress`
- **时间**：`hasEra` `hasSurveyDate` `valid_time_start/end`
- **聚合/空间**：`hasLayer` `containsPlace`(clu→pl，由 ST_Contains 自动推断)
- **侨批**：`hasCollectionNumber` `hasSender` `hasRecipient` `hasOriginPlace` `hasDestinationPlace` `hasShownDate` `hasFormalDate` `hasCurrency` `hasAmount` `hasInnerLetter`
- **资产**：`hasFileName` `hasFilePath` `depicts` `capturedAt` `hasAltitude`

> 模板列名已对齐这些谓词（如 `hasName_名称` → 谓词 `hasName`），ingest 时按列名映射。新增谓词请先与负责人确认，避免本体膨胀。

---

## 7. 常见错误（Do / Don't）

| ❌ 不要 | ✅ 要 |
|---|---|
| 自己把高德坐标转成 WGS84 | 原样填 + CRS 选 GCJ-02 |
| 同一地点不同人填不同 key | 查权威清单，复用同一 natural_key |
| 来源留空或写"网上看到的" | 填可定位的 URL / 馆藏号 / Zotero key |
| 手敲 region/类型 | 用下拉选 |
| 一行塞多个实体 | 一行一个实体，跨表用 key 关联 |
| 拿不准就瞎填 | 留空 + 备注说明 |
| 把示例行留在表里提交 | 提交前删掉黄色示例行 |

---

## 8. 数据质量评估标准（项目什么时候算采集完成）

"采集完成" 不是"所有列都填满"，而是**6 个维度**都达标。前 3 个是底线（覆盖+关联+来源），后 3 个是研究质量门槛（精度+一致性+多模态）。**所有维度都能用 SQL 自检**——这是知识图谱比 Excel 强的核心。

### 8.1 六维度评估

#### 维度 1 · 实体覆盖度（不漏）

| 表 | 应有的最小覆盖 | 量化目标 |
|---|---|---|
| Place（pl） | 项目内每一处可识别地点 1 行 | 比对官方权威清单，覆盖率 ≥ 95% |
| Place（clu） | 每个聚落群/区域 1 行 | 全集 |
| Document | 文献/档案/口述史 | 至少 1:1 配对 Place 的核心来源 |
| Actor | 重要人物 / 家族 / 机构 | 文献中可考者全录 |
| Asset | 现状照片 / 测绘 / 扫描件 | 每个 pl 至少 1 张 depicts 照片 |

#### 维度 2 · 跨表关联完整性（不悬空）

所有跨表引用都能在目标表找到对应行。

```sql
-- 悬空引用检测（理想 = 0 条）
SELECT s.subject_id, s.predicate, s.object_value
FROM entity_statement s
WHERE s.object_entity_id IS NULL
  AND s.predicate IN ('hasSender','hasRecipient','depicts','relatedPlace','relatedActor',
                      'hasOriginPlace','hasDestinationPlace');
```

**理想标准**：悬空引用率 < 1%。

#### 维度 3 · 来源链完整性（不无源）

```sql
-- 无证据的实体（理想 = 0）
SELECT ce.pid, ce.entity_type, ce.label_zh
FROM conceptual_entity ce
WHERE NOT EXISTS (
  SELECT 1 FROM entity_statement es
  WHERE es.subject_id = ce.pid AND es.evidence_id IS NOT NULL
);
```

**理想标准**：每个实体至少 1 条带 evidence 的 statement。

#### 维度 4 · 空间精度（CRS 声明 + 落入合理范围）

```sql
-- 坐标合理性检查（例：福建项目应在 23.5-28.5°N, 115.5-120.5°E）
SELECT pid, ST_Y(object_geometry) AS lat, ST_X(object_geometry) AS lon
FROM entity_statement s
JOIN conceptual_entity c ON s.subject_id = c.pid
WHERE predicate='locatedAt' AND c.entity_type IN ('pl','clu')
  AND NOT (ST_Y(object_geometry) BETWEEN <lat_min> AND <lat_max>
       AND ST_X(object_geometry) BETWEEN <lon_min> AND <lon_max>);
```

**理想标准**：100% 坐标落在项目地理边界内。**> 0 条意味着 SRID 又被坑了**（参考 Mustang UTM 44N → 45N 偏移 6° 事故）。

#### 维度 5 · 本体一致性（控制词表归一）

```sql
-- 关键谓词取值分布 vs 本体定义
SELECT object_value, count(*) FROM entity_statement
WHERE predicate='hasType' AND subject_id LIKE 'clkg:<region>:%'
GROUP BY 1 ORDER BY 2 DESC;
```

**理想标准**：
- distinct 值数 ≤ 本体定义类数 × 1.2（容忍 20% 漂移）
- 漂移项已通过 `UPDATE entity_statement` 归一化（如 Mustang "寺院" → "寺庙"）

#### 维度 6 · 多模态对齐（Asset depicts 命中率）

```sql
-- 有照片的 Place 比例
WITH pl_with_asset AS (
  SELECT DISTINCT s.object_entity_id AS pid
  FROM entity_statement s
  JOIN conceptual_entity c ON s.subject_id=c.pid
  WHERE c.entity_type='img' AND s.predicate='depicts'
)
SELECT
  count(*) FILTER (WHERE entity_type='pl') AS total_pl,
  count(*) FILTER (WHERE entity_type='pl' AND pid IN (SELECT pid FROM pl_with_asset)) AS pl_with_photo
FROM conceptual_entity;
```

**理想标准**：≥ 80% 的 pl 有至少 1 张 depicts 照片（视项目，文献类项目可放宽）。

### 8.2 三级"采集完成"分级

| 阶段 | 标准 | 适合场景 |
|---|---|---|
| 🟡 **MVP（最小可用）** | 维度 1 ≥ 50% + 维度 3 = 100% + 维度 4 = 100% | 可以演示与试用，**不能下论断** |
| 🟢 **研究就绪** | 维度 1 ≥ 90% + 维度 2 < 1% 悬空 + 维度 5 已归一 | **可基于此图谱写论文** |
| 🔵 **公开发布** | 维度 6 ≥ 80% + 全部 distinct-value 审计通过 + 权威清单导出可分享 | 可对外发布，对接 UNESCO / 文物局等系统 |

### 8.3 实操建议

新项目**不要追求 🔵 一步到位**：

1. 先冲 🟡——让图谱能跑起来、能演示
2. 再用具体研究需求驱动补 🟢——缺什么补什么，避免无的放矢
3. 最后才考虑 🔵——只在确实要对外发布时再投入

**每次 ingest 之后**，建议负责人按维度 1-6 跑一遍自检 SQL，把结果归档到 `~/clkg/data_collection/quality-audit/{region}-{date}.md`，作为项目进度追踪。

---
