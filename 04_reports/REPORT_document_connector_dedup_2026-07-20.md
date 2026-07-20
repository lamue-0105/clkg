# CLKG 阶段报告：文档连接器（L1）与去重约束修复

**日期**：2026-07-20
**范围**：`ingest/connectors/document.py`、`ingest/pipelines/document.py`、`01_sql/00`/`03`/`05`、`ingest/spatial.py`、`ingest/cli.py`
**触发**：以 Harrison《Mustang Building》(2019) 为示范书目，搭建图书/长文档信息抽取链路

---

## 摘要

两件事，第二件比第一件重要。

1. **建成文档抽取链路的 L1 层**：长文档 → 带页码定位的段落流 + doc 实体著录。补上了 `03_docs/inventory.md` 里列为待建的 `pdf.py` / `docx.py`。

2. **发现并修复了一个使唯一约束长期失效的缺陷**。`unique_stmt_check` 因 PostgreSQL 的 NULL 语义，对约 99% 的语句从未生效，导致重跑即静默重复。**mustang 库 48.45% 的语句是冗余行**，且该冗余经 `locatedAt` 传播进了 ST_Contains 派生的 `containsPlace`。已修复、清理、并对四个库全部验证。

**规模变化**：四库语句总数 511,939 → **473,651**（-38,288）。凡此前报告过的语句规模数字均需以新值为准。

---

## 一、缺陷：唯一约束对 99% 的语句从未生效

### 现象

同一份文档重复入库时，`evidence` 行正确复用（仅一条），但 `entity_statement` 出现完全相同的重复行：同 subject、同 predicate、同 object_value、**同 evidence_id**。

### 根因

原索引定义：

```sql
CREATE UNIQUE INDEX unique_stmt_check ON entity_statement
  (subject_id, predicate, md5(object_value),
   object_entity_id, valid_time_start, evidence_id);
```

PostgreSQL 唯一索引默认视 NULL 互不相等。而：

| 列 | 四库合计 NULL 占比 |
|---|---|
| `object_entity_id` | 全部字面值语句均为 NULL |
| `valid_time_start` | qiaopi / xinjiang / liangzhu 为 100% NULL |

因此任意两行只要在这些列上同为 NULL，索引就判定它们不同，约束不触发。

### 验证

临时表对照实验（不触碰真实数据）：

| 索引形式 | 插入两条完全相同的行 |
|---|---|
| 现行（裸列） | **允许**，rows = 2 |
| COALESCE 包装 | **UniqueViolation**，拦截 |

### 影响面

| 库 | 语句总数 | 冗余行 | 占比 |
|---|---|---|---|
| **mustang** | 78,434 | **37,998** | **48.45%** |
| xinjiang | 184,335 | 287 | 0.16% |
| qiaopi | 245,579 | 3 | 0.00% |
| liangzhu | 3,591 | 0 | 0.00% |

mustang 占比畸高是因为它是开发区，反复重跑过；其余三库基本只入过一两次。

### 文档表述不一致

- `01_sql/03_ingest_batch.sql` 文件头是**诚实**的，明确写有 "LIMITATION (v1): no statement-level dedup on retry"。
- 《技术说明与实验设计手册》§3.2 则称该约束为「**幂等重跑的基础**」，属过度声明。

修复后手册的说法才成立，§3.2 已改写并补入 COALESCE 不可省的原因。

---

## 二、冗余传播进派生结果（对论文数字的直接影响）

冗余不止于存储浪费。空间推理 `link_contains_place()` 的写法是 clu 多边形与 pl 点做交叉连接：

```sql
FROM clu, pl WHERE ST_Contains(clu.geom, pl.geom)
```

两侧的 CTE 都基于 `locatedAt` 取几何，而 `locatedAt` 本身被复制过（mustang：13,275 → 6,800），交叉连接因此把结果对数放大。

去重后重算 ST_Contains：

| 口径 | 值 |
|---|---|
| 去重前库中存储 | 682 |
| 既往记录/报告引用 | 646 |
| **去重后重算（365 多边形 × 177 点）** | **300** |
| **去重后库中存储** | **300** |

只有 300 是可验证且自洽的（存储值与重算值完全吻合）。

**行动项：投稿前复查所有引用 646 或旧语句规模的文本。** 已知 `04_reports/REPORT_2026-05-17_to_18.md` 摘要中的「~480,000 条三元组」需按新值复核。

去重正确性的旁证——若干谓词计数在去重后精确回归到实体数：

| 谓词 | 去重前 | 去重后 | 应等于 |
|---|---|---|---|
| `hasFileName` / `hasFilePath` / `hasFileType` / `hasFileSize` | 12,082 | **6,037** | img 实体数 6,037 |
| `hasShapeArea` / `hasShapeLength` | 388 | **368** | clu 实体数 368 |

---

## 三、修复

### 3.1 索引

`01_sql/00_create_schema.sql` 中 canonical 定义改为：

```sql
CREATE UNIQUE INDEX unique_stmt_check ON entity_statement (
  subject_id, predicate,
  COALESCE(md5(object_value), ''),
  COALESCE(object_entity_id, ''),
  COALESCE(valid_time_start, ''),
  evidence_id
);
```

`evidence_id` 四库均无 NULL，保持裸列。

**过度合并风险已排除**：COALESCE 到 `''` 会把空字符串与 NULL 视为相同。实测四库中 `object_value`、`object_entity_id`、`valid_time_start` 的空字符串计数**全部为 0**，故不存在误合并。

### 3.2 迁移与命令

- 新增 `01_sql/05_fix_unique_stmt_check.sql`：隔离重复行 → 删除 → 重建索引，单事务。
- 新增 `python -m ingest.cli dedup <region>`：**默认只报告**，`--yes` 才执行。

**双份备份**：
- 库内 `entity_statement_dupes_backup` 表（回滚即 INSERT 回去）
- 库外 `~/clkg-backups/{region}_entity_statement_dupes.csv`

### 3.3 连带修复的两处

**`ingest_batch()` 的 ON CONFLICT**。它原本就有 `DO NOTHING`，但列清单写的是旧索引的列。表达式索引要求 ON CONFLICT 逐字重复同样的表达式，不匹配是硬错误而非静默降级。已同步并重新部署到四个库。

**`ingest/spatial.py` 的 `ON CONFLICT ON CONSTRAINT unique_stmt_check`**。`unique_stmt_check` 是唯一**索引**，`pg_constraint` 中并无同名条目，该写法直接报错。这是**先前既有**的缺陷，自该索引取代旧 UNIQUE 约束起即已失效。已改为表达式列表。

### 3.4 验证

| 检查 | 结果 |
|---|---|
| 四库残留重复 | 0 / 0 / 0 / 0 |
| 四库索引已换为 COALESCE 版 | 是 |
| 文档入库连续重跑 3 次 | 语句数稳定 14，`rows_ok=0`（全部正确跳过） |
| `link_contains_place('mustang')` 连跑 2 次 | 均返回 0 新增，`containsPlace` 稳定 300 |
| `ingest.cli verify mustang` | 三表列结构 OK |

---

## 四、文档连接器（L1）

### 定位

L1 刻意**不含语义**：把文件变成带定位的段落流，并只产出关于文档自身的著录语句。从段落抽取事实是 L2，把事实绑定到既有实体是 L3。

### 接口

```python
describe(path)        # 廉价探测：页数、文字层覆盖率、路由建议
read_passages(path)   # → list[Passage]，磁盘缓存
ingest_document(path) # → list[StatementRow]，仅著录语句
```

```bash
python -m ingest.cli document <path> --region mustang            # 只探测，不写库
python -m ingest.cli document <path> --region mustang --ingest   # 写入 doc 实体
```

默认只读是刻意的：这一层的主要职责就是告诉你文件到底有没有文字层。

### 版权处理

`hasFullText` **不入库**。在版权期内的资料，库中只存抽取出的事实加页码定位；段落文本留在本地缓存（`~/.cache/clkg/doc_passages/`），既保证重跑免费，又不再分发原文。

### Passage 数据结构要点

- `page`（印刷页码）与 `pdf_page`（物理页）分离，差值即 `page_offset`。前置页无页码时二者不同，必须实地核验。
- `locator` 为可引用字符串，如 `p.116` / `p.116 fig.4.130`。
- `kind` ∈ body / caption / heading / needs_ocr。
- 无文字层的页返回 `kind="needs_ocr"` 且文本为空；传入 `ocr_fn` 即可填充。**不在 L1 内部调用视觉模型**——那要花钱，必须是显式、可续跑的决定，而不是打开文件的副作用。

### 实测

| 文件 | 页数 | 文字层覆盖 | 路由 | 段落 |
|---|---|---|---|---|
| Mustang Building.pdf（CamScanner 扫描） | 398 | **0.0%** | ocr | 398 全为 needs_ocr |
| 某技术书（有文字层） | 851 | 97.9% | text_layer | 3,731 |
| 某 .docx | — | — | text_layer | 78（按 Word 样式识别出 11 个标题） |

### 建设过程中修掉的两个缺陷

**切片污染缓存**。缓存键不含页码范围，`--pages 110-120` 的一次运行会把 11 段写入缓存，之后整本读取只返回这 11 段。改为缓存只保存整本，切片作为视图。

**页眉页脚被当作正文**。改用重复频率检测，不依赖出版社版式。此处踩过一个坑：初版阈值取 20% 页数，结果一条未检出——书的页脚**按章、按奇偶交替**，851 页中每种仅出现约 30 次。改为低比例加绝对下限后检出 17 种模式，垃圾段落随之消失。

另加了记忆化：小切片上反复迭代由 3.6 秒降至 0.03 秒。

### 示范书目就位

- 书置于 `data/mustang/documents/`（该目录整体 gitignore，注释即写明供「原始/版权/个人数据」）
- 配套 `Mustang Building.pdf.meta.json` 边车文件，记录书目信息、已核验的 `page_offset=0`、版权状态、以及该书的四条覆盖度限制
- doc 实体 `clkg:mustang:doc-unk-0000002`，14 条著录语句

**溯源修正**：最初入库时 `hasFilePath` 指向微信缓存目录，属坏溯源，已重新入库为稳定路径。

---

## 五、待办

1. **复查论文数字**：646、480,000 及其他基于旧语句规模的表述。
2. **L2 抽取器**：段落 → 面向 CL-Onto 谓词集的受约束抽取。以本次阅读产出的 1.2 万字结构化笔记作输入与金标准，避免重复消耗 398 页视觉 token。
3. **新谓词待定**：`partOfUnit`（文本断言的聚落层级，几何推不出来，如 Shöyul 村落联盟无多边形）、`hasDateBasis`（树轮/碳十四/文献/传说/推测，直接驱动 confidence）、`surveyedBy`、以及「作者推测 vs 断言」的表达方式。
4. **确认后清理**：`entity_statement_dupes_backup` 表在去重结果确认无误后可删。
5. **观察项**：doc 实体的英文标题落入了 `label_zh`（`ingest_batch()` 取 `hasName` 填充该列）。非本次改动引入，但对非中文资料是数据质量瑕疵。
