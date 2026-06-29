"""CLKG collection schema — single source of truth for the standard template.

This module defines the authoritative column definitions, sheet descriptors,
and controlled vocabularies for the four data-collection sheets.  It is consumed
by three components so they never drift apart:

  • build_template.py   → generates CLKG_采集模板.xlsx
  • connectors/template.py → reads filled templates and emits StatementRows
  • (future) template_validator.py → pre-ingest quality gate

Design principle (技术手册 §6.5):
  "单一事实源同时供模板生成、验证器、连接器使用，防三者漂移。"
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


# ═══════════════════════════════════════════════════════════════════════════
# Column role — tells the connector how to dispatch each cell
# ═══════════════════════════════════════════════════════════════════════════

class ColumnRole(str, Enum):
    """Semantic role of a column in the collection template.

    The connector reads each row cell-by-cell and dispatches based on role:
      • META columns  → go into ev_metadata, no SPO statement emitted
      • KEY columns   → feed the StatementRow common dict (ent_*)
      • VALUE columns → emit StatementRow(predicate, {"value": cell})
      • REF_* columns → emit cross-entity reference statements
      • GEOMETRY cols → accumulated per row; one locatedAt statement at end
      • CONFIDENCE    → row-level default confidence for all statements
    """
    META            = "meta"             # ev_metadata only (recorder, date)
    NATURAL_KEY     = "natural_key"      # ent_natural_key
    REGION          = "region"           # ent_region
    ENTITY_TYPE     = "entity_type"      # ent_type_abbr
    SOURCE_NAME     = "source_name"      # evidence source_name
    SOURCE_TYPE     = "source_type"      # ev_source_type
    VALUE           = "value"            # → stmt_value={"value": cell}
    REF_PL          = "ref_pl"           # → {"ref_natural_key": cell, "ref_type_abbr": "pl", ...}
    REF_AC          = "ref_ac"           # → {"ref_natural_key": cell, "ref_type_abbr": "ac", ...}
    REF_DOC         = "ref_doc"          # → {"ref_natural_key": cell, "ref_type_abbr": "doc", ...}
    REF_ANY         = "ref_any"          # → heuristic type guess (depicts)
    LON             = "lon"              # longitude, accumulated for geometry
    LAT             = "lat"              # latitude, accumulated for geometry
    CRS             = "crs"              # coordinate reference system
    CONFIDENCE      = "confidence"       # row-level default confidence
    ASSET_PATH      = "asset_path"       # path string (weak reference)
    STATUS          = "status"           # doc_status in ev_metadata
    ACTOR_ROLE      = "actor_role"       # role in ev_metadata


# ═══════════════════════════════════════════════════════════════════════════
# Column definition
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class ColumnDef:
    """One column in a collection sheet."""
    index: int                          # 1-based column position in xlsx
    header: str                         # Full header, e.g. "hasName_名称*"
    predicate: str                      # CL-Onto predicate, e.g. "hasName"
    chinese_label: str                  # e.g. "名称"
    role: ColumnRole                    # Dispatch role
    required: bool = False              # Parsed from trailing "*"
    vocab_key: Optional[str] = None     # Key into VOCAB (for dropdowns)
    note: str = ""                      # Comment / help text
    width: int = 14                     # Excel column width
    ext: bool = False                   # Purple project-extension column


@dataclass
class SheetDescriptor:
    """Describes one collection sheet (generic or project-extension)."""
    sheet_name: str                     # e.g. "Place_地点"
    sheet_order: int                    # Tab order (0-based)
    tab_color: str                      # Hex color for sheet tab
    entity_types: list[str] = field(default_factory=list)  # Allowed entity_type values
    columns: list[ColumnDef] = field(default_factory=list)
    example_row: list[Optional[str]] = field(default_factory=list)
    example_natural_key: str = ""       # For example-row content detection
    # -- extension-sheet support (flat event tables without identity columns) --
    default_region: Optional[str] = None        # used when no REGION column exists
    default_entity_type: Optional[str] = None   # used when no ENTITY_TYPE column exists
    synthetic_key_prefix: Optional[str] = None  # synthesize natural_key per data row
                                                # when no NATURAL_KEY column exists
                                                # (e.g. "junken-evt" → junken-evt-0001)


# ═══════════════════════════════════════════════════════════════════════════
# Controlled vocabularies (shared with build_template.py)
# ═══════════════════════════════════════════════════════════════════════════

VOCAB: dict[str, list[str]] = {
    "entity_type": ["pl", "clu", "ac", "img", "doc", "ev"],
    "region":      ["mustang", "qiaopi", "xinjiang", "kashgar", "liangzhu"],
    "source_type": ["literature", "archive", "field_survey", "oral_history",
                    "gis_dataset", "web", "image_file", "other"],
    "CRS":         ["WGS84", "GCJ-02", "BD-09", "CGCS2000",
                    "EPSG:32644", "EPSG:32645", "unk"],
    "layer":       ["单体", "群体", "区域"],
    "heritage_lv": ["国家级", "自治区级", "省级", "市级", "县市级"],
    "confidence":  ["1.0", "0.9", "0.7", "0.5"],
    "actor_role":  ["person", "family", "organization"],
    "doc_type":    ["专著", "期刊论文", "档案", "方志", "碑刻铭文", "契约文书",
                    "信札(侨批)", "谱牒", "舆图", "报刊", "口述史转写", "图像图说", "其他"],
    "lang":        ["zh", "en", "zh-en双语", "其他"],
    "doc_status":  ["待验证", "已验证", "存疑", "废弃"],
}

VOCAB_NOTES: dict[str, str] = {
    "entity_type": "pl=单体地点 / clu=文化景观单元(群体·区域) / ac=人物机构 / img=图像音视频 / doc=文档(侨批·档案·口述史) / ev=事件",
    "region": "项目/区域代号，对应一个区域库。现有三库: mustang/qiaopi/xinjiang; kashgar/liangzhu 为规划。新项目可在本列底部新增。",
    "source_type": "literature=文献 archive=档案 field_survey=田野 oral_history=口述史 gis_dataset=GIS数据集 web=网络公开 image_file=图像 other=其他",
    "CRS": "坐标来源的坐标系！高德=GCJ-02，百度=BD-09，国外UTM-44N=EPSG:32644。绝不自己换算，ingest 统一转 WGS84。",
    "layer": "仅 Mustang 等需要时填。群体/区域→entity_type 记 clu；单体→pl。",
    "heritage_lv": "文物保护级别（如适用）。",
    "confidence": "对该条记录正确性的把握。亲见/原档=1.0，二手可靠=0.9，推断=0.7，存疑=0.5。",
    "actor_role": "person=个人 family=家族 organization=机构/商号。",
    "doc_type": "文献体裁：专著/期刊论文/档案/方志/碑刻铭文/契约文书/信札(侨批)/谱牒/舆图/报刊/口述史转写/图像图说/其他。",
    "lang": "文献主要语言：zh=中文 en=英文 zh-en双语 其他。",
    "doc_status": "数据状态(可选)：待验证/已验证/存疑/废弃。对应早期 design_legacy 的 Status 字段。",
}


# ═══════════════════════════════════════════════════════════════════════════
# Known example natural_keys (for example-row content detection)
# ═══════════════════════════════════════════════════════════════════════════

_EXAMPLE_NATURAL_KEYS = {
    "Place_地点":    "mustang-pl-lomanthang",
    "Document_文档": "Q12345",
    "Actor_人物":    "qiaopi-ac-chenmiaoqing",
    "Asset_资产":    "IMG_1234",
}


# ═══════════════════════════════════════════════════════════════════════════
# Place_地点  (27 columns)
# ═══════════════════════════════════════════════════════════════════════════

_SHEET_PLACE = SheetDescriptor(
    sheet_name="Place_地点",
    sheet_order=1,
    tab_color="2E75B6",
    entity_types=["pl", "clu"],
    example_natural_key=_EXAMPLE_NATURAL_KEYS["Place_地点"],
    columns=[
        # -- 通用基础 --
        ColumnDef(1,  "记录人*",               "",                "记录人",       ColumnRole.META,        required=True,  note="你的名字，便于追溯。"),
        ColumnDef(2,  "采集日期*",             "",                "采集日期",     ColumnRole.META,        required=True,  note="YYYY-MM-DD，记录当天日期。"),
        ColumnDef(3,  "region*",              "",                "region",       ColumnRole.REGION,      required=True,  vocab_key="region",     note="项目/区域代号。"),
        ColumnDef(4,  "entity_type*",          "",                "entity_type",  ColumnRole.ENTITY_TYPE, required=True,  vocab_key="entity_type", note="单体→pl；群体/区域→clu。"),
        ColumnDef(5,  "natural_key*",          "",                "natural_key",  ColumnRole.NATURAL_KEY, required=True,  note="稳定唯一标识！同一地点永远用同一个 key（去重靠它）。优先用已有编号(遗产编码/照片文件夹名)，否则用 region-pl-有意义短码。"),
        # -- 地点核心 --
        ColumnDef(6,  "hasName_名称*",          "hasName",         "名称",         ColumnRole.VALUE,       required=True,  width=16),
        ColumnDef(7,  "hasType_类型",           "hasType",         "类型",         ColumnRole.VALUE,                      note="如 庙宇/村落/墓葬。"),
        ColumnDef(8,  "hasCategoryType_遗产类别","hasCategoryType", "遗产类别",     ColumnRole.VALUE,                      note="如 古遗址/古建筑。",          width=14),
        ColumnDef(9,  "hasEra_年代",            "hasEra",          "年代",         ColumnRole.VALUE,                      note="如 汉代/19c/清。"),
        ColumnDef(10, "hasLayer_层级",          "hasLayer",        "层级",         ColumnRole.VALUE,       vocab_key="layer",      note="Mustang 等：单体/群体/区域。"),
        ColumnDef(11, "hasHeritageLevel_保护级别","hasHeritageLevel","保护级别",    ColumnRole.VALUE,       vocab_key="heritage_lv", note="如适用。"),
        # -- 空间 --
        ColumnDef(12, "lon_经度",               "",                "经度",         ColumnRole.LON,                        note="十进制度。务必同时填 CRS_坐标系。"),
        ColumnDef(13, "lat_纬度",               "",                "纬度",         ColumnRole.LAT,                        note="十进制度。"),
        ColumnDef(14, "CRS_坐标系",             "",                "坐标系",       ColumnRole.CRS,          vocab_key="CRS",        note="坐标来源的坐标系，必须如实声明！绝不自己换算。", width=13),
        ColumnDef(15, "坐标来源",               "hasCoordinateSource","坐标来源",  ColumnRole.VALUE,                      note="如 高德地图/实测GPS/文献附图。", width=14),
        # -- 行政 --
        ColumnDef(16, "hasPrefecture_省州",     "hasPrefecture",   "省州",         ColumnRole.VALUE),
        ColumnDef(17, "hasCounty_县区",         "hasCounty",       "县区",         ColumnRole.VALUE),
        ColumnDef(18, "hasTown_乡镇",           "hasTown",         "乡镇",         ColumnRole.VALUE),
        ColumnDef(19, "hasVillage_村",          "hasVillage",      "村",           ColumnRole.VALUE),
        ColumnDef(20, "hasAddress_地址",        "hasAddress",      "地址",         ColumnRole.VALUE,       width=18,               note="完整地址。"),
        # -- 其他 --
        ColumnDef(21, "hasDescription_描述",    "hasDescription",  "描述",         ColumnRole.VALUE,       width=24,               note="自由文本描述。"),
        ColumnDef(22, "hasSurveyDate_调查日期", "hasSurveyDate",   "调查日期",     ColumnRole.VALUE,                      note="实地调查/资料对应日期。"),
        # -- 来源 --
        ColumnDef(23, "source_name_来源*",      "",                "来源",         ColumnRole.SOURCE_NAME, required=True,  width=22,               note="出处！文献=Zotero引用键或题名页码；档案=馆藏号；网址=URL；田野=调查表编号。"),
        ColumnDef(24, "source_type_来源类型*",   "",                "来源类型",     ColumnRole.SOURCE_TYPE, required=True,  vocab_key="source_type", width=13),
        ColumnDef(25, "confidence_可信度",       "",                "可信度",       ColumnRole.CONFIDENCE,  vocab_key="confidence"),
        ColumnDef(26, "asset_path_关联资产",     "hasAssetPath",    "关联资产",     ColumnRole.ASSET_PATH,  width=18,               note="照片/扫描件的 NAS 路径或文件夹名。"),
        ColumnDef(27, "hasNotes_备注",           "hasNotes",        "备注",         ColumnRole.VALUE,       width=18),
    ],
    example_row=[
        "张三", "2026-06-01", "mustang", "pl", "mustang-pl-lomanthang", "洛满堂",
        "庙宇", "古建筑", "19c", "单体", "", "83.9567", "29.1845", "WGS84", "实测GPS",
        "甘达基省", "木斯塘县", "", "Lo Manthang", "古城北侧", "三层夯土建筑，保存完好。",
        "2024-05-18", "Mustang2024_field#012", "field_survey", "1.0",
        "/Volumes/clkg_data/mustang/photos/mustang-pl-lomanthang/", "需复查屋顶年代",
    ],
)


# ═══════════════════════════════════════════════════════════════════════════
# Document_文档  (34 columns)
# ═══════════════════════════════════════════════════════════════════════════

_SHEET_DOCUMENT = SheetDescriptor(
    sheet_name="Document_文档",
    sheet_order=2,
    tab_color="C55A11",
    entity_types=["doc"],
    example_natural_key=_EXAMPLE_NATURAL_KEYS["Document_文档"],
    columns=[
        # -- 通用基础 --
        ColumnDef(1,  "记录人*",                     "",                  "记录人",         ColumnRole.META,        required=True),
        ColumnDef(2,  "采集日期*",                   "",                  "采集日期",       ColumnRole.META,        required=True, note="YYYY-MM-DD"),
        ColumnDef(3,  "region*",                    "",                  "region",         ColumnRole.REGION,      required=True, vocab_key="region"),
        ColumnDef(4,  "entity_type*",                "",                  "entity_type",    ColumnRole.ENTITY_TYPE, required=True, vocab_key="entity_type",
                      note="各类文本材料统一填 doc（文献/档案/方志/碑刻/契约/信札/口述史转写均可）。"),
        ColumnDef(5,  "natural_key*",                "",                  "natural_key",    ColumnRole.NATURAL_KEY, required=True, width=18,
                      note="稳定唯一标识。优先用已有编号(馆藏号/档号)；口述史用 受访者-日期 编号。"),
        # -- 文档核心(通用) --
        ColumnDef(6,  "hasTitle_标题*",              "hasTitle",          "标题",           ColumnRole.VALUE,       required=True,  width=22,
                      note="标题/题名；无题者据内容拟题；口述史可用 受访者口述(日期)。"),
        ColumnDef(7,  "hasDocType_文献类型",          "hasDocType",        "文献类型",       ColumnRole.VALUE,       vocab_key="doc_type", width=13,
                      note="文献体裁，见词表(专著/档案/方志/碑刻/契约/信札…)。"),
        ColumnDef(8,  "hasAuthor_作者创建者",          "hasAuthor",         "作者创建者",     ColumnRole.VALUE,       width=14,
                      note="作者/编者/创建者；多个用、分隔。"),
        ColumnDef(9,  "hasLanguage_语言",            "hasLanguage",       "语言",           ColumnRole.VALUE,       vocab_key="lang"),
        ColumnDef(10, "hasHoldingInstitution_收藏机构","hasHoldingInstitution","收藏机构",    ColumnRole.VALUE,       width=16, note="收藏/提供机构全称。"),
        ColumnDef(11, "hasCollectionNumber_馆藏号",   "hasCollectionNumber","馆藏号",        ColumnRole.VALUE,       width=13, note="馆藏号/索书号/档号等。"),
        ColumnDef(12, "hasFormalDate_标准化日期",      "hasFormalDate",     "标准化日期",     ColumnRole.VALUE,       width=14, note="成文/出版日期，公历，如 1929 或 1929-XX-XX。"),
        ColumnDef(13, "hasShownDate_原件题署日期",     "hasShownDate",      "原件题署日期",   ColumnRole.VALUE,       width=14, note="原件上写的日期，如 民国18年/光绪三十年。"),
        ColumnDef(14, "hasFullText_全文转写",          "hasFullText",       "全文转写",       ColumnRole.VALUE,       width=30, note="正文/信文/口述全文转写（如已数字化）。"),
        ColumnDef(15, "hasAbstract_内容摘要",          "hasAbstract",       "内容摘要",       ColumnRole.VALUE,       width=24, note="一两句话的内容提要。"),
        ColumnDef(16, "relatedPlace_关联地点",         "relatedPlace",      "关联地点",       ColumnRole.REF_PL,      width=16,
                      note="相关地点的 natural_key 或地名；并去 Place 表登记。"),
        ColumnDef(17, "relatedActor_关联人物",         "relatedActor",      "关联人物",       ColumnRole.REF_AC,      width=16,
                      note="相关人物/机构的 natural_key 或名；并去 Actor 表登记。"),
        ColumnDef(18, "hasReference_著录参考",         "hasReference",      "著录参考",       ColumnRole.VALUE,       width=16, note="著录出处/参考文献/Zotero 键。"),
        ColumnDef(19, "hasRights_版权许可",            "hasRights",         "版权许可",       ColumnRole.VALUE,       width=14, note="版权/使用许可范围。"),
        # -- 来源(通用基础尾) --
        ColumnDef(20, "source_name_来源*",            "",                  "来源",           ColumnRole.SOURCE_NAME, required=True,  width=22,
                      note="出处：馆藏号/Zotero键/档号/录音文件名。"),
        ColumnDef(21, "source_type_来源类型*",         "",                  "来源类型",       ColumnRole.SOURCE_TYPE, required=True,  vocab_key="source_type", width=13,
                      note="文献=literature；档案=archive；口述史=oral_history。"),
        ColumnDef(22, "confidence_可信度",             "",                  "可信度",         ColumnRole.CONFIDENCE,  vocab_key="confidence"),
        ColumnDef(23, "状态",                          "hasStatus",         "状态",           ColumnRole.VALUE,       vocab_key="doc_status", note="数据状态(可选)：待验证/已验证/存疑/废弃。"),
        ColumnDef(24, "asset_path_资产路径",           "hasAssetPath",      "资产路径",       ColumnRole.ASSET_PATH,  width=20, note="扫描件/录音/录像的 NAS 路径。"),
        ColumnDef(25, "hasNotes_备注",                 "hasNotes",          "备注",           ColumnRole.VALUE,       width=18),
        # -- 项目专属扩展(侨批等批信类专用，紫色) --
        ColumnDef(26, "hasSender_寄件人(侨批)",         "hasSender",         "寄件人(侨批)",   ColumnRole.REF_AC,      width=14, ext=True,
                      note="批信寄件人 natural_key/姓名；并去 Actor 表登记。"),
        ColumnDef(27, "hasRecipient_收件人(侨批)",      "hasRecipient",      "收件人(侨批)",   ColumnRole.REF_AC,      width=14, ext=True, note="批信收件人。"),
        ColumnDef(28, "hasOriginPlace_寄出地(侨批)",    "hasOriginPlace",    "寄出地(侨批)",   ColumnRole.REF_PL,      width=14, ext=True, note="寄出地 natural_key/地名。"),
        ColumnDef(29, "hasDestinationPlace_寄达地(侨批)","hasDestinationPlace","寄达地(侨批)", ColumnRole.REF_PL,      width=14, ext=True, note="寄达地。"),
        ColumnDef(30, "hasReplyDate_回批日期(侨批)",     "hasReplyDate",      "回批日期(侨批)", ColumnRole.VALUE,       ext=True),
        ColumnDef(31, "hasCurrency_币种(侨批)",          "hasCurrency",       "币种(侨批)",     ColumnRole.VALUE,       ext=True, note="如 墨西哥银元。"),
        ColumnDef(32, "hasAmount_金额(侨批)",            "hasAmount",         "金额(侨批)",     ColumnRole.VALUE,       ext=True),
        ColumnDef(33, "hasPaidAmount_实付(侨批)",        "hasPaidAmount",     "实付(侨批)",     ColumnRole.VALUE,       ext=True),
        ColumnDef(34, "hasConvertedAmount_折算(侨批)",   "hasConvertedAmount","折算(侨批)",     ColumnRole.VALUE,       width=12, ext=True, note="标准化折算金额。"),
    ],
    example_row=[
        "李四", "2026-06-01", "qiaopi", "doc", "Q12345",
        "陈妙清寄潮安家书", "信札(侨批)", "陈妙清", "zh", "潮汕侨批馆", "Q12345",
        "1929-XX-XX", "民国18年", "父亲大人膝下敬禀者……", "寄银百元并报平安",
        "qiaopi-pl-chaoan", "qiaopi-ac-chenmiaoqing", "《潮汕侨批集成》第3辑", "馆藏，研究用途",
        "Q12345 / 潮汕侨批馆", "archive", "0.9", "待验证",
        "/Volumes/clkg_data/qiaopi/scans/Q12345.jpg", "字迹部分模糊",
        "qiaopi-ac-chenmiaoqing", "qiaopi-ac-chenmu", "qiaopi-pl-saigon", "qiaopi-pl-chaoan",
        "", "墨西哥银元", "100", "98", "550",
    ],
)


# ═══════════════════════════════════════════════════════════════════════════
# Actor_人物  (12 columns)
# ═══════════════════════════════════════════════════════════════════════════

_SHEET_ACTOR = SheetDescriptor(
    sheet_name="Actor_人物",
    sheet_order=3,
    tab_color="7030A0",
    entity_types=["ac"],
    example_natural_key=_EXAMPLE_NATURAL_KEYS["Actor_人物"],
    columns=[
        ColumnDef(1,  "记录人*",            "",            "记录人",       ColumnRole.META,        required=True),
        ColumnDef(2,  "采集日期*",          "",            "采集日期",     ColumnRole.META,        required=True,  note="YYYY-MM-DD"),
        ColumnDef(3,  "region*",           "",            "region",       ColumnRole.REGION,      required=True,  vocab_key="region"),
        ColumnDef(4,  "entity_type*",       "",            "entity_type",  ColumnRole.ENTITY_TYPE, required=True,  vocab_key="entity_type"),
        ColumnDef(5,  "natural_key*",       "",            "natural_key",  ColumnRole.NATURAL_KEY, required=True,  width=18,
                     note="稳定唯一标识。被 Document 表的寄/收件人引用，必须一致！"),
        ColumnDef(6,  "hasName_姓名*",      "hasName",     "姓名",         ColumnRole.VALUE,       required=True,  width=16, note="姓名/家族名/机构名。"),
        ColumnDef(7,  "角色类型",            "hasRole",     "角色类型",     ColumnRole.VALUE,       vocab_key="actor_role",
                     note="person/family/organization。"),
        ColumnDef(8,  "hasDescription_说明","hasDescription","说明",       ColumnRole.VALUE,       width=26,       note="身份、关系、生平等。"),
        ColumnDef(9,  "source_name_来源*",   "",            "来源",         ColumnRole.SOURCE_NAME, required=True,  width=20, note="出处。"),
        ColumnDef(10, "source_type_来源类型*","",            "来源类型",     ColumnRole.SOURCE_TYPE, required=True,  vocab_key="source_type", width=13),
        ColumnDef(11, "confidence_可信度",    "",            "可信度",       ColumnRole.CONFIDENCE,  vocab_key="confidence"),
        ColumnDef(12, "hasNotes_备注",        "hasNotes",    "备注",         ColumnRole.VALUE,       width=18),
    ],
    example_row=[
        "李四", "2026-06-01", "qiaopi", "ac", "qiaopi-ac-chenmiaoqing", "陈妙清",
        "person", "潮安籍南洋华侨，1920s 寄批人。", "Q12345", "archive", "0.9", "",
    ],
)


# ═══════════════════════════════════════════════════════════════════════════
# Asset_资产  (17 columns)
# ═══════════════════════════════════════════════════════════════════════════

_SHEET_ASSET = SheetDescriptor(
    sheet_name="Asset_资产",
    sheet_order=4,
    tab_color="BF8F00",
    entity_types=["img"],
    example_natural_key=_EXAMPLE_NATURAL_KEYS["Asset_资产"],
    columns=[
        ColumnDef(1,  "记录人*",                "",              "记录人",       ColumnRole.META,        required=True),
        ColumnDef(2,  "采集日期*",              "",              "采集日期",     ColumnRole.META,        required=True,  note="YYYY-MM-DD"),
        ColumnDef(3,  "region*",               "",              "region",       ColumnRole.REGION,      required=True,  vocab_key="region"),
        ColumnDef(4,  "entity_type*",           "",              "entity_type",  ColumnRole.ENTITY_TYPE, required=True,  vocab_key="entity_type",
                     note="照片/录音/录像统一填 img。"),
        ColumnDef(5,  "natural_key*",           "",              "natural_key",  ColumnRole.NATURAL_KEY, required=True,  width=18,
                     note="稳定唯一标识（可用文件名去扩展名）。"),
        ColumnDef(6,  "hasFileName_文件名*",     "hasFileName",   "文件名",       ColumnRole.VALUE,       required=True,  width=16, note="含扩展名，如 IMG_1234.jpg。"),
        ColumnDef(7,  "hasFilePath_路径*",       "hasFilePath",   "路径",         ColumnRole.VALUE,       required=True,  width=24, note="NAS 完整路径 file://… 或相对 NAS_ROOT 的路径。"),
        ColumnDef(8,  "hasFileType_类型",        "hasFileType",   "类型",         ColumnRole.VALUE,                      note="JPEG/WAV/MP4 等。"),
        ColumnDef(9,  "depicts_关联实体",        "depicts",       "关联实体",     ColumnRole.REF_ANY,     width=18,       note="该资产描绘/对应的 Place 或 Document 的 natural_key。"),
        ColumnDef(10, "capturedAt_拍摄时间",     "capturedAt",    "拍摄时间",     ColumnRole.VALUE,       width=16,       note="ISO 时间，如 2024-05-18T14:30。"),
        ColumnDef(11, "lon_经度",                "",              "经度",         ColumnRole.LON,                        note="EXIF GPS（通常 WGS84）。"),
        ColumnDef(12, "lat_纬度",                "",              "纬度",         ColumnRole.LAT),
        ColumnDef(13, "CRS_坐标系",              "",              "坐标系",       ColumnRole.CRS,         vocab_key="CRS", note="EXIF 一般是 WGS84。"),
        ColumnDef(14, "hasAltitude_海拔",        "hasAltitude",   "海拔",         ColumnRole.VALUE,                      note="米。"),
        ColumnDef(15, "source_name_来源*",       "",              "来源",         ColumnRole.SOURCE_NAME, required=True,  width=20, note="出处。"),
        ColumnDef(16, "source_type_来源类型*",    "",              "来源类型",     ColumnRole.SOURCE_TYPE, required=True,  vocab_key="source_type", width=13,
                     note="照片填 image_file。"),
        ColumnDef(17, "hasNotes_备注",           "hasNotes",      "备注",         ColumnRole.VALUE,       width=18),
    ],
    example_row=[
        "张三", "2026-06-01", "mustang", "img", "IMG_1234", "IMG_1234.jpg",
        "/Volumes/clkg_data/mustang/photos/mustang-pl-lomanthang/IMG_1234.jpg",
        "JPEG", "mustang-pl-lomanthang", "2024-05-18T14:30", "83.9567", "29.1845",
        "WGS84", "3840", "相机原片", "image_file", "正立面",
    ],
)


# ═══════════════════════════════════════════════════════════════════════════
# Project-extension sheets — 新疆军垦 (Xinjiang military reclamation)
#
# These are flat one-row-per-event tables. Unlike the four generic sheets they
# carry NO 记录人/region/entity_type/natural_key identity columns, so the
# descriptor supplies them as sheet-level defaults:
#   • default_region       → ent_region for every row
#   • default_entity_type  → ent_type_abbr for every row
#   • synthetic_key_prefix → natural_key = "{prefix}-{NNNN}" by data-row order
# 诗歌 is the exception: it already has the standard identity columns.
# ═══════════════════════════════════════════════════════════════════════════

# ---- 军垦_事件 (517 events from a 4-book compilation) ----------------------
_SHEET_JUNKEN_EVENT = SheetDescriptor(
    sheet_name="军垦_事件",
    sheet_order=5,
    tab_color="880000",
    entity_types=["ev"],
    default_region="xinjiang",
    default_entity_type="ev",
    synthetic_key_prefix="junken-evt",
    columns=[
        ColumnDef(1,  "时代_历史时期",   "hasEra",           "历史时期",   ColumnRole.VALUE,       required=True,  note="如 战国/西汉/奠基时期"),
        ColumnDef(2,  "时间_具体年份",   "hasShownDate",     "具体年份",   ColumnRole.VALUE,                       note="如 前169年/1949年"),
        ColumnDef(3,  "发起人",          "hasInitiator",     "发起人",     ColumnRole.VALUE,                       note="发起人或行动主体（字面文本，非实体引用）"),
        ColumnDef(4,  "承受人",          "hasBeneficiary",   "承受人",     ColumnRole.VALUE,                       note="承受人（字面文本，非实体引用；避免与 hasRecipient 跨表引用语义撞车）"),
        ColumnDef(5,  "事件描述",        "hasDescription",   "事件描述",   ColumnRole.VALUE,       required=True,  note="简要描述事件内容", width=30),
        ColumnDef(6,  "地点",            "hasAddress",       "地点",       ColumnRole.VALUE,                       note="具体区域或垦区名称"),
        ColumnDef(7,  "物",              "hasObject",        "物",         ColumnRole.VALUE,                       note="文物、概念、物质实体"),
        ColumnDef(8,  "文化价值",        "hasCulturalValue", "文化价值",   ColumnRole.VALUE,                       note="精神内涵、象征意义等"),
        ColumnDef(9,  "屯垦制度",        "hasInstitution",   "屯垦制度",   ColumnRole.VALUE,                       note="政策、组织形式等"),
        ColumnDef(10, "source_name_来源", "",                "来源",       ColumnRole.SOURCE_NAME, required=True,  note="书名、页码、作者等"),
        ColumnDef(11, "著录人",          "",                 "著录人",     ColumnRole.META,        required=True,  note="数据录入者"),
        ColumnDef(12, "出处",            "hasReference",     "出处",       ColumnRole.VALUE,                       note="资料来源出处"),
    ],
    example_row=[
        "战国", "", "商鞅", "秦国军民", "商鞅系统阐述农战思想", "秦国", "农战概念", "",
        "战国农战政策", "《商君书·农战》", "辛佳丽", "《新疆兵团屯垦戍边史》",
    ],
)

# ---- 军垦_口述史 (2931 oral-history events) --------------------------------
_SHEET_JUNKEN_ORAL = SheetDescriptor(
    sheet_name="军垦_口述史",
    sheet_order=6,
    tab_color="884400",
    entity_types=["ev"],
    default_region="xinjiang",
    default_entity_type="ev",
    synthetic_key_prefix="junken-oral",
    columns=[
        ColumnDef(1,  "章",       "hasChapter",     "章",         ColumnRole.VALUE,                      note="章节信息"),
        ColumnDef(2,  "节",       "hasSection",     "节",         ColumnRole.VALUE,                      note="节信息"),
        ColumnDef(3,  "小节",     "hasSubsection",  "小节",       ColumnRole.VALUE,                      note="小节信息"),
        ColumnDef(4,  "口述者",   "hasSpeaker",     "口述者",     ColumnRole.VALUE,      required=True,  note="口述者姓名"),
        ColumnDef(5,  "口述者身份", "hasSpeakerRole", "口述者身份", ColumnRole.VALUE,                    note="口述者身份描述"),
        ColumnDef(6,  "采访人",   "hasInterviewer", "采访人",     ColumnRole.VALUE,                      note="采访人姓名"),
        ColumnDef(7,  "时间",     "hasShownDate",   "时间",       ColumnRole.VALUE,                      note="事件发生时间"),
        ColumnDef(8,  "时代",     "hasEra",         "时代",       ColumnRole.VALUE,      required=True,  note="时代分期"),
        ColumnDef(9,  "地点",     "hasAddress",     "地点",       ColumnRole.VALUE,                      note="事件发生地点"),
        ColumnDef(10, "人物",     "hasParticipantName", "人物",   ColumnRole.VALUE,                      note="事件涉及人物（字面文本，非实体引用）"),
        ColumnDef(11, "物品",     "hasObject",      "物品",       ColumnRole.VALUE,                      note="涉及物品"),
        ColumnDef(12, "概念",     "hasConcept",     "概念",       ColumnRole.VALUE,                      note="涉及概念"),
        ColumnDef(13, "触发词",   "hasTrigger",     "触发词",     ColumnRole.VALUE,                      note="触发词"),
        ColumnDef(14, "行动主体", "hasAgent",       "行动主体",   ColumnRole.VALUE,                      note="行动主体"),
        ColumnDef(15, "事件类型", "hasEventType",   "事件类型",   ColumnRole.VALUE,                      note="事件类型代码"),
        ColumnDef(16, "事件描述", "hasDescription", "事件描述",   ColumnRole.VALUE,      required=True,  note="事件详细描述", width=30),
    ],
    example_row=[
        "奠基(1949-1954)", "向西开拔", "（一）", "刘双全", "司令员", "李霞等",
        "1949年下半年", "奠基时期", "青海；西宁", "", "", "", "绕道青海", "部队",
        "MigrationEvent", "部队从青海西宁绕道前进",
    ],
)

# ---- 军垦_诗歌 (poems; standard identity columns present) -------------------
_SHEET_JUNKEN_POEM = SheetDescriptor(
    sheet_name="军垦_诗歌",
    sheet_order=7,
    tab_color="886600",
    entity_types=["doc"],
    example_natural_key="poem-001",
    columns=[
        ColumnDef(1,  "记录人*",              "",                "记录人",     ColumnRole.META,        required=True,  note="校对人/记录人"),
        ColumnDef(2,  "采集日期*",            "",                "采集日期",   ColumnRole.META,        required=True,  note="YYYY-MM-DD"),
        ColumnDef(3,  "region*",             "",                "region",     ColumnRole.REGION,      required=True,  vocab_key="region",      note="填 xinjiang"),
        ColumnDef(4,  "entity_type*",         "",                "entity_type", ColumnRole.ENTITY_TYPE, required=True, vocab_key="entity_type", note="统一填 doc"),
        ColumnDef(5,  "natural_key*",         "",                "natural_key", ColumnRole.NATURAL_KEY, required=True, note="填原始数据 id，如 poem-001"),
        ColumnDef(6,  "hasTitle_题名*",        "hasTitle",        "题名",       ColumnRole.VALUE,       required=True,  note="诗歌标题"),
        ColumnDef(7,  "hasAuthor_作者",        "hasAuthor",       "作者",       ColumnRole.VALUE,                       note="诗歌作者"),
        ColumnDef(8,  "hasEra_时代",           "hasEra",          "时代",       ColumnRole.VALUE,                       note="如 汉/唐/清"),
        ColumnDef(9,  "hasFullText_正文",      "hasFullText",     "正文",       ColumnRole.VALUE,       width=30,        note="诗歌全文"),
        ColumnDef(10, "hasAbstract_例证",      "hasAbstract",     "例证",       ColumnRole.VALUE,       width=24,        note="例证/简要说明"),
        ColumnDef(11, "hasPlace_地名",         "mentionsPlace",   "地名",       ColumnRole.VALUE,                       note="诗句中提及的地名"),
        ColumnDef(12, "lon_经度",              "",                "经度",       ColumnRole.LON,                         note="古地名对应今经纬度"),
        ColumnDef(13, "lat_纬度",              "",                "纬度",       ColumnRole.LAT,                         note="古地名对应今经纬度"),
        ColumnDef(14, "CRS_坐标系",            "",                "坐标系",     ColumnRole.CRS,         vocab_key="CRS", note="填 WGS84"),
        ColumnDef(15, "hasReference_出处",     "hasReference",    "出处",       ColumnRole.VALUE,                       note="诗歌来源文献"),
        ColumnDef(16, "hasEmotion_情感极性",   "hasEmotion",      "情感极性",   ColumnRole.VALUE,                       note="正向/负向"),
        ColumnDef(17, "hasEmotionScore_极性得分", "hasEmotionScore", "极性得分", ColumnRole.VALUE,                     note="情感得分"),
        ColumnDef(18, "hasEmotionType_情绪类别", "hasEmotionType", "情绪类别",  ColumnRole.VALUE,                       note="豪迈雄浑/苍凉悲悼等"),
        ColumnDef(19, "hasIdentity_身份",      "hasIdentity",     "身份",       ColumnRole.VALUE,                       note="作者身份判断"),
        ColumnDef(20, "hasNotes_备注",         "hasNotes",        "备注",       ColumnRole.VALUE,       width=18),
    ],
    example_row=[
        "陈东豪", "2026-07-01", "xinjiang", "doc", "poem-001", "西极天马歌", "刘彻", "汉",
        "天马徕兮从西极...", "汉武虽通西域，本人未至", "西极", "", "", "", "《全汉三国晋南北朝诗》",
        "正向", "0.95", "豪迈雄浑", "想象", "汉武虽通西域，本人未至",
    ],
)


# ═══════════════════════════════════════════════════════════════════════════
# Registry of all sheets (ordered by tab order)
# ═══════════════════════════════════════════════════════════════════════════

ALL_SHEETS: list[SheetDescriptor] = [
    _SHEET_PLACE,
    _SHEET_DOCUMENT,
    _SHEET_ACTOR,
    _SHEET_ASSET,
]

# Project-specific extension sheets. Generated into the template and recognised
# by the connector, but NOT part of the default ingest target — only ingested
# when present in the workbook (see connectors/template.py).
EXTENSION_SHEETS: list[SheetDescriptor] = [
    _SHEET_JUNKEN_EVENT,
    _SHEET_JUNKEN_ORAL,
    _SHEET_JUNKEN_POEM,
]

SHEETS_BY_NAME: dict[str, SheetDescriptor] = {
    s.sheet_name: s for s in (ALL_SHEETS + EXTENSION_SHEETS)
}


# ═══════════════════════════════════════════════════════════════════════════
# Helper: build a fast lookup {header: ColumnDef} for each sheet
# ═══════════════════════════════════════════════════════════════════════════

def column_map(sheet: SheetDescriptor) -> dict[str, ColumnDef]:
    """Return {header: ColumnDef} for the sheet, used by the connector."""
    return {col.header: col for col in sheet.columns}
