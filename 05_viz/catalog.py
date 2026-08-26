"""静态登记表 — 版本组合 / 数据与权威资源目录 / 专题案例内容。

这些内容不是从库里现算的（版本标签、数据来源的版权/模态描述、专题叙事文字
本身就是需要人工登记的元数据，不是可推导量），但凡是可以核验的数字（实体数/
陈述数/containsPlace 数等）都在页面渲染时用 /api/regions、/api/validation 等
接口的实时结果替换，不在这里硬编码，避免和活库脱节。
"""
from __future__ import annotations

VERSION_COMBO = {
    "data_version": "2026.08.22-01",
    "ontology_version": "2026.08.22-01",
    "rule_set_version": "2026.08.22-01",
    "authority_version": "2026.08.22-01",
    "status": "演示数据 · draft",
    "note": (
        "这是本原型的第一个标注版本组合，用于论文/答辩演示，不是 PRD 中定义的"
        "完整 draft→validated→published 发布流程的产物——没有实现发布门禁，"
        "标签本身也不随每次 ingest 自动递增，需要手动维护。"
    ),
    "changelog": [
        {"date": "2026-08-22", "summary": "首个版本组合标注；接入规则库、CL-Onto概念页、三案例专题页。"},
    ],
}

SOURCES = [
    {
        "source_id": "src.mustang.gdb",
        "region": "mustang",
        "name": "木斯塘 SHP/GDB 矢量图层（聚落多边形 + 单体点位）",
        "modalities": ["geospatial"],
        "crs_note": "原始 UTM 44N，入库时统一 ST_Transform 至 WGS84(4326)",
        "rights": "课题组内部",
        "status": "已接入",
    },
    {
        "source_id": "src.mustang.csv",
        "region": "mustang",
        "name": "木斯塘属性表 CSV",
        "modalities": ["tabular"],
        "crs_note": "同上",
        "rights": "课题组内部",
        "status": "已接入",
    },
    {
        "source_id": "src.mustang.photo",
        "region": "mustang",
        "name": "木斯塘田野照片（EXIF 地理标记）",
        "modalities": ["image", "geospatial"],
        "crs_note": "WGS84（EXIF GPS 原生）",
        "rights": "课题组内部",
        "status": "已接入",
    },
    {
        "source_id": "src.qiaopi.xlsx",
        "region": "qiaopi",
        "name": "侨批地理编码语料（qiaopi_geocoded_hybrid.xlsx）",
        "modalities": ["text", "geospatial"],
        "crs_note": "高德 GCJ-02（国测局加密坐标），非国际标准 WGS84，展示前需留意",
        "rights": "课题组内部/侨批文物馆授权",
        "status": "已接入",
    },
    {
        "source_id": "src.qiaopi.chaoshan",
        "region": "qiaopi",
        "name": "潮汕侨批整合语料（新一轮，约 8.7 万条候选记录）",
        "modalities": ["text"],
        "crs_note": "无地理编码，仅寄批地/收批地文本",
        "rights": "课题组内部",
        "status": "连接器已开发，小样本试点，全量接入未执行",
    },
    {
        "source_id": "src.xinjiang.mixed",
        "region": "xinjiang",
        "name": "新疆文物保护点位数据（矢量图层 + 属性表模板 + 名录）",
        "modalities": ["tabular", "geospatial"],
        "crs_note": "已转换至 WGS84(4326)",
        "rights": "课题组内部",
        "status": "已接入",
    },
    {
        "source_id": "src.xinjiang.new_gdb",
        "region": "xinjiang",
        "name": "新疆文保数据（新）.gdb — 814 处已登记文保点 + 行政边界",
        "modalities": ["geospatial"],
        "crs_note": "待入库时确认",
        "rights": "课题组内部",
        "status": "已识别，尚未接入（三案例中进度最落后的一项）",
    },
    {
        "source_id": "src.kashgar.caa",
        "region": "kashgar",
        "name": "喀什塔里木土遗址 MLLM 探测结果（导师课题组 CAA 论文数据层）",
        "modalities": ["geospatial"],
        "crs_note": "待确认",
        "rights": "课题组内部（导师课题组共享）",
        "status": "已识别为潜在数据源，尚未接入",
    },
]

AUTHORITIES = [
    {
        "authority_id": "auth.cidoc-crm",
        "name": "CIDOC CRM",
        "resource_type": "reference_ontology",
        "usage": "CL-Onto 的 6 个核心类与主要谓词均对齐/标注 closeMatch 到 CIDOC-CRM（见 ingest/ontology.py 的 CRM 映射表生成逻辑）。",
    },
    {
        "authority_id": "auth.prov-o",
        "name": "W3C PROV-O",
        "resource_type": "reference_ontology",
        "usage": "Evidence 类声明为 prov:Entity 子类，承担陈述溯源语义。",
    },
    {
        "authority_id": "auth.geosparql",
        "name": "OGC GeoSPARQL",
        "resource_type": "standard",
        "usage": "空间属性（locatedAt 等）的 range 对齐 geo:Geometry；几何统一存为 PostGIS geometry(Geometry,4326)。",
    },
]

TOPICS = {
    "mustang": {
        "label": "木斯塘 · 文化景观",
        "region": "mustang",
        "problem": (
            "田野记录里的聚落层级关系（哪些单体建筑/遗迹从属于哪个聚落或区域）"
            "只隐含在图层组织和文字描述里，没有被显式建模为可查询的关系。"
        ),
        "data_standard": (
            "SHP/GDB 矢量图层（聚落多边形 + 单体点位）+ 属性表 CSV + 带 EXIF 地理"
            "标记的田野照片。原始坐标系为 UTM 44N，入库时统一 ST_Transform 到 "
            "WGS84(4326)；类结构对齐 CIDOC-CRM 的 E27_Site（clu）与 E53_Place（pl）。"
        ),
        "modeling_rule": (
            "clu（文化景观单元，聚落/区域级）与 pl（原子地点，单体建筑/点位）两级"
            "实体 + containsPlace 空间推理规则：对 clu 的多边形几何与 pl 的点几何"
            "跑 ST_Contains，把隐含的层级关系显式化为陈述（见 ingest/spatial.py）。"
        ),
        "findings_query": "mustang",  # 页面渲染时用这个 key 拉活库实时数字
        "limitations": (
            "推理只做了空间维度，没有时间维度校验（同一地点跨时期的层级变化未"
            "区分）；containsPlace 的统计口径此前因唯一约束的 NULL 语义 bug 出现过"
            "膨胀（682 存量→300 复算后核实），已修复，但提醒了一个方法论教训："
            "任何论文数字都应先查 git log 追溯计算脚本再引用。H3（原生溯源采集"
            "质量增益）的基线对照实验（B 组）仍然缺失。"
        ),
    },
    "qiaopi": {
        "label": "侨批 · 文献/记忆遗产",
        "region": "qiaopi",
        "problem": (
            "纸质书信档案的地理语义关联弱（寄批地/收批地是自由文本，没有锚定到"
            "统一的地点实体），且时间表达非标准化（民国纪年、干支等混用）。"
        ),
        "data_standard": (
            "侨批扫描件 OCR/整理文本 + 高德（GCJ-02）地理编码；新一轮潮汕侨批"
            "整合语料约 8.7 万条候选记录，仅含寄批地/收批地文本，无地理编码。"
            "GCJ-02 是国测局加密坐标，非国际标准 WGS84，跨库空间分析前需转换。"
        ),
        "modeling_rule": (
            "doc（书信文档）/ ac（寄件人、收件人）/ pl（寄批地、收批地）三类实体，"
            "hasSender / hasRecipient / hasOriginPlace / hasDestinationPlace 等谓词；"
            "日期解析分级字段（解析等级/候选公历年/年份来源/干支提示）只放在"
            "证据元数据（ev_metadata）里，不建模为独立陈述——避免把解析过程的"
            "中间产物和陈述本身混在一起。"
        ),
        "findings_query": "qiaopi",
        "limitations": (
            "潮汕整合语料仅完成连接器开发和小样本试点，全量入库尚未执行；"
            "复合键匹配显示新语料约 99.7% 不与现有语料重复，但这是精确字符串"
            "匹配的结果，模糊重复（同一封信不同誊抄版本）尚未排查。"
        ),
    },
    "xinjiang": {
        "label": "新疆 · 考古遗产",
        "region": "xinjiang",
        "problem": (
            "考古遗产点位与行政边界、保护等级之间的空间归属关系尚未显式关联，"
            "木斯塘验证过的 containsPlace 推理还没有在这个区域跑过。"
        ),
        "data_standard": (
            "已接入：文物保护点位矢量图层 + 属性表模板 + 名录（已转 WGS84）。"
            "待接入：新疆文保数据（新）.gdb 中 814 处已登记文保点和行政边界，"
            "以及导师课题组 CAA 论文里 MLLM 探测塔里木土遗址的结果，可作为"
            "喀什子项目 containsPlace 推理的补充地理数据层。"
        ),
        "modeling_rule": (
            "沿用木斯塘验证过的通用 SHP/GDB 连接器和 containsPlace 空间推理"
            "规则，理论上不需要为新疆重新开发管线，只需要新数据接入即可复用。"
        ),
        "findings_query": "xinjiang",
        "limitations": (
            "新一批 814 点 GDB 尚未接入，containsPlace 推理在这个区域还没有跑过"
            "（当前 containsPlace=0）。这是三个案例里进度最落后的一个，也直接"
            "说明跨遗产类型可迁移性假设（H1）目前还缺一个完整走通的第三案例。"
        ),
    },
}
