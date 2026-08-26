-- ============================================================================
-- CLKG Demo Query Pack — 组会演示用 10 条"有故事"的 SQL
--   生成日期: 2026-05-18
--   覆盖项目: mustang_cl_kg / qiaopi_cl_kg / xinjiang_cl_kg
--   每条查询前面都有"故事"和"看点"说明，方便现场讲解
-- ============================================================================

-- ─────────────────────────────────────────────────────────────────────────────
-- Q1. 三库总规模 —— 一句话把 KG 体量讲清楚
-- 故事: "两天时间我们建成了三个区域的文化遗产知识图谱"
-- 看点: 每个库都达到了万级实体 + 十万级语句的规模
-- 在 psql 中跨库统计, 现场用三个连接分别跑即可
-- ─────────────────────────────────────────────────────────────────────────────

-- 在 mustang_cl_kg 中跑:
SELECT 'mustang' AS region,
       (SELECT count(*) FROM conceptual_entity) AS entities,
       (SELECT count(*) FROM entity_statement)  AS statements,
       (SELECT count(*) FROM evidence)          AS evidence_rows;

-- 在 qiaopi_cl_kg 中跑:
SELECT 'qiaopi' AS region,
       (SELECT count(*) FROM conceptual_entity) AS entities,
       (SELECT count(*) FROM entity_statement)  AS statements,
       (SELECT count(*) FROM evidence)          AS evidence_rows;

-- 在 xinjiang_cl_kg 中跑:
SELECT 'xinjiang' AS region,
       (SELECT count(*) FROM conceptual_entity) AS entities,
       (SELECT count(*) FROM entity_statement)  AS statements,
       (SELECT count(*) FROM evidence)          AS evidence_rows;


-- ─────────────────────────────────────────────────────────────────────────────
-- Q2. 实体类型分布 —— 看本体设计的成果
-- 故事: "CL-Onto 的 pl / clu / ac / ev / img / doc 六类体系在数据里活下来了"
-- 看点: mustang 同时有 pl (单体遗产)、clu (文化景观单元)、img (照片)
--        qiaopi 以 doc (侨批文档) + ac (人物) 为主
--        xinjiang 几乎全是 pl (考古点)
-- ─────────────────────────────────────────────────────────────────────────────
-- 在每个区域库跑同一条:
SELECT entity_type, count(*) AS n
  FROM conceptual_entity
 GROUP BY entity_type
 ORDER BY n DESC;


-- ─────────────────────────────────────────────────────────────────────────────
-- Q3. 木斯塘空间推理: Lomanthang 古城下辖 68 处遗产
-- 故事: "我们没有人工标注 Lomanthang 包含哪些点 — PostGIS 在 polygon-vs-point 的
--        ST_Contains 上自动跑出 646 条 containsPlace 关系"
-- 看点: 第一行 LOMANTHANG 包含 68 个子实体 → 真正的"文化景观单元"
-- 在 mustang_cl_kg 跑:
-- ─────────────────────────────────────────────────────────────────────────────
SELECT parent.label_zh                                AS parent_clu,
       count(*)                                       AS children,
       string_agg(child.label_zh, ', ' ORDER BY child.label_zh)
         FILTER (WHERE child.label_zh IS NOT NULL)    AS sample_children
  FROM entity_statement s
  JOIN conceptual_entity parent ON parent.pid = s.subject_id
  JOIN conceptual_entity child  ON child.pid  = s.object_entity_id
 WHERE s.predicate = 'containsPlace'
 GROUP BY parent.label_zh
 ORDER BY children DESC
 LIMIT 10;


-- ─────────────────────────────────────────────────────────────────────────────
-- Q4. 木斯塘照片时间线 —— "田野考察轨迹重建"
-- 故事: "6036 张田野照片按拍摄时间排序, 等于把一次田野考察的足迹重建出来"
-- 看点: 跨年度多次考察 + 单日内空间聚集说明这是同一个 site 的连续记录
-- 注: 过滤掉 EXIF 异常的 2099 年照片
-- 在 mustang_cl_kg 跑:
-- ─────────────────────────────────────────────────────────────────────────────
SELECT date_trunc('month', s_t.object_value::timestamp) AS month,
       count(DISTINCT s_t.subject_id)                    AS photos_taken,
       count(DISTINCT s_loc.subject_id)
         FILTER (WHERE s_loc.predicate = 'locatedAt')    AS with_gps
  FROM entity_statement s_t
  LEFT JOIN entity_statement s_loc
         ON s_loc.subject_id = s_t.subject_id
        AND s_loc.predicate  = 'locatedAt'
 WHERE s_t.predicate = 'capturedAt'
   AND s_t.object_value::timestamp < '2030-01-01'
 GROUP BY 1
 ORDER BY 1;


-- ─────────────────────────────────────────────────────────────────────────────
-- Q5. 侨批跨国汇款的"金流图"雏形
-- 故事: "每封侨批同时有寄出地、收件地、金额、币种 — 这是一份 19-20 世纪初
--        华南→东南亚的金融移民史料"
-- 看点: TOP10 寄出地→收件地的高频流向
-- 在 qiaopi_cl_kg 跑:
-- ─────────────────────────────────────────────────────────────────────────────
SELECT origin.object_value  AS from_place,
       dest.object_value    AS to_place,
       count(*)             AS letter_count
  FROM entity_statement origin
  JOIN entity_statement dest
    ON dest.subject_id = origin.subject_id
   AND dest.predicate  = 'hasDestination'
 WHERE origin.predicate = 'hasOrigin'
   AND origin.object_value IS NOT NULL
   AND dest.object_value   IS NOT NULL
 GROUP BY 1, 2
 ORDER BY letter_count DESC
 LIMIT 10;


-- ─────────────────────────────────────────────────────────────────────────────
-- Q6. 侨批寄信人活跃度 TOP15 —— "谁是这条家书纽带的高频联络人"
-- 故事: "把寄信人作为节点, 同一个名字反复出现 → 这是一个家庭/商号长期通信"
-- 看点: 前几名能直接对应到史学界关注的侨批主家族
-- 在 qiaopi_cl_kg 跑:
-- ─────────────────────────────────────────────────────────────────────────────
SELECT sender.object_value AS sender_name,
       count(*)            AS letters_sent,
       count(DISTINCT date_trunc('year', valid_from::date))
         AS active_years
  FROM entity_statement sender
  LEFT JOIN entity_statement vt
         ON vt.subject_id = sender.subject_id
        AND vt.predicate  = 'hasSendDate',
       LATERAL (SELECT vt.object_value::text AS valid_from) v
 WHERE sender.predicate = 'hasSender'
   AND sender.object_value IS NOT NULL
   AND length(sender.object_value) BETWEEN 2 AND 8
 GROUP BY 1
 ORDER BY letters_sent DESC
 LIMIT 15;


-- ─────────────────────────────────────────────────────────────────────────────
-- Q7. 新疆 3027 个三普考古点的年代分布 TOP15
-- 故事: "整个新疆考古点跨度从青铜时代到清代 — 一张年代直方图能看到丝路沿线
--        遗产的时代结构"
-- 看点: 高频年代里能直接读出"汉、唐、清"等丝路高峰期
-- 在 xinjiang_cl_kg 跑:
-- ─────────────────────────────────────────────────────────────────────────────
SELECT object_value AS era, count(*) AS site_count
  FROM entity_statement
 WHERE predicate = 'hasEra'
   AND object_value IS NOT NULL
   AND object_value <> ''
 GROUP BY 1
 ORDER BY 2 DESC
 LIMIT 15;


-- ─────────────────────────────────────────────────────────────────────────────
-- Q8. 新疆"世界级文保单位" —— KG 里只有 3 处 (UNESCO 关联)
-- 故事: "在 5409 个文保单位里挖出 3 个世界级 — 这是新疆作为丝路核心的最高
--        文化分级 (高昌故城、北庭故城、雅尔湖故城 — 全部在吐鲁番盆地)"
-- 看点: 现场可以直接念出这 3 个名字, 讲与丝绸之路廊道申遗的关系
-- 在 xinjiang_cl_kg 跑:
-- ─────────────────────────────────────────────────────────────────────────────
WITH world_level AS (
  SELECT subject_id FROM entity_statement
   WHERE predicate = 'hasHeritageLevel'
     AND object_value LIKE '%世界级%'
)
SELECT ce.pid,
       (SELECT object_value FROM entity_statement
         WHERE subject_id = ce.pid AND predicate = 'hasName' LIMIT 1) AS name,
       (SELECT object_value FROM entity_statement
         WHERE subject_id = ce.pid AND predicate = 'hasCounty' LIMIT 1) AS county,
       (SELECT object_value FROM entity_statement
         WHERE subject_id = ce.pid AND predicate = 'hasEra' LIMIT 1) AS era,
       (SELECT object_value FROM entity_statement
         WHERE subject_id = ce.pid AND predicate = 'hasGazettedBatch' LIMIT 1) AS batch
  FROM conceptual_entity ce
  JOIN world_level w ON w.subject_id = ce.pid;


-- ─────────────────────────────────────────────────────────────────────────────
-- Q9. 新疆各级文保单位金字塔
-- 故事: "县级→市级→自治区级→国家级→世界级 — KG 里的递进可被一条 GROUP BY
--        看出来, 完美对应国家文保分级体系"
-- 看点: 县级 1139 / 自治区级 625 / 国家级 135 / 市级 107 / 世界级 3
-- 在 xinjiang_cl_kg 跑:
-- ─────────────────────────────────────────────────────────────────────────────
SELECT object_value AS heritage_level, count(*) AS n
  FROM entity_statement
 WHERE predicate = 'hasHeritageLevel'
   AND object_value IS NOT NULL
 GROUP BY 1
 ORDER BY n DESC;


-- ─────────────────────────────────────────────────────────────────────────────
-- Q10. 跨区域空间覆盖 —— "我们的 KG 已经覆盖 X 平方公里"
-- 故事: "三库的 locatedAt 几何点用 ST_Extent 算出来的总覆盖范围, 横跨
--        喜马拉雅山南麓→华南侨乡→塔克拉玛干周边"
-- 看点: 三组 BBox 一字排开, 能直观体现项目的"全球文化景观"野心
-- 注: 现场依次在三个库跑同一条:
-- ─────────────────────────────────────────────────────────────────────────────
SELECT current_database()                                 AS db,
       count(*)                                           AS geo_points,
       round(min(ST_Y(object_geometry))::numeric, 2)      AS lat_min,
       round(max(ST_Y(object_geometry))::numeric, 2)      AS lat_max,
       round(min(ST_X(object_geometry))::numeric, 2)      AS lon_min,
       round(max(ST_X(object_geometry))::numeric, 2)      AS lon_max
  FROM entity_statement
 WHERE predicate = 'locatedAt'
   AND object_geometry IS NOT NULL;


-- ============================================================================
-- 演示顺序建议:
--   Q1  → 立规模          (开场震一下)
--   Q2  → 立本体          (说明 CL-Onto 落地)
--   Q3  → 木斯塘空间故事  (Lomanthang 68 子实体)
--   Q4  → 田野时间线      (照片轨迹)
--   Q5  → 侨批金流        (移民史视角)
--   Q6  → 侨批人物网络    (社会网络视角)
--   Q7  → 新疆年代分布    (丝路时代结构)
--   Q8  → 三个世界级遗产  (现场念名字, 收尾爆发)
--   Q9  → 文保金字塔      (制度对应)
--   Q10 → 跨区域 BBox     (收束: "三国一图")
-- ============================================================================
