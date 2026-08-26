"""从活库 + collection_schema 自动生成 CL-Onto 的 OWL/RDFS（Turtle）。

把"隐式 T-Box"（散在三表+连接器+schema）形式化为显式本体：声明 6 个类、
所有对象属性(边)与数据属性(字面值)的 rdfs:domain / rdfs:range，并对 CIDOC-CRM /
PROV-O / GeoSPARQL 做轻量对齐。是规划里 G1 缺口的第一步。

本体随数据增长——重跑即可刷新。

用法:
    python -m ingest.ontology                       # 写 03_docs/ontology/clkg.ttl
    python -m ingest.ontology --print                # 打印到 stdout
"""
from __future__ import annotations

import sys
from pathlib import Path

import psycopg

from . import config
from .collection_schema import ALL_SHEETS, EXTENSION_SHEETS

REGIONS = ["mustang", "qiaopi", "xinjiang", "liangzhu"]

# entity_type -> (类名, 中文, CIDOC-CRM closeMatch)
CLASSES = {
    "pl":  ("Place", "地点", "E53_Place"),
    "clu": ("CulturalLandscapeUnit", "文化景观单元", "E27_Site"),
    "ac":  ("Actor", "行动者", "E39_Actor"),
    "doc": ("Document", "文档", "E31_Document"),
    "ev":  ("Event", "事件", "E5_Event"),
    "img": ("DigitalImage", "图像", "E36_Visual_Item"),
}
# 对象属性 -> CIDOC-CRM closeMatch（其余 (c) 步细化）
PROP_CRM = {
    "tookPlaceIn": "P7_took_place_at",
    "carriedOutBy": "P14_carried_out_by",
    "containsPlace": "P89_falls_within",
    "locatedAt": "P168_place_is_defined_by",
}
# range = xsd:decimal 的数据属性
NUMERIC = {"hasEmotionScore", "hasAmount", "hasPaidAmount", "hasConvertedAmount",
           "hasArea", "hasShapeArea", "hasShapeLength"}

PREFIXES = """@prefix clkg: <https://w3id.org/clkg/ontology#> .
@prefix owl:  <http://www.w3.org/2002/07/owl#> .
@prefix rdf:  <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix xsd:  <http://www.w3.org/2001/XMLSchema#> .
@prefix prov: <http://www.w3.org/ns/prov#> .
@prefix geo:  <http://www.opengis.net/ont/geosparql#> .
@prefix skos: <http://www.w3.org/2004/02/skos/core#> .
@prefix crm:  <http://www.cidoc-crm.org/cidoc-crm/> .
"""


def _zh_labels() -> dict[str, str]:
    m = {}
    for sd in ALL_SHEETS + EXTENSION_SHEETS:
        for c in sd.columns:
            if c.predicate and c.predicate not in m and c.chinese_label:
                m[c.predicate] = c.chinese_label
    return m


def inventory() -> dict[str, dict]:
    """活库谓词清单：predicate -> {subj:set, objt:set, val, ref, geo, n}。"""
    agg: dict[str, dict] = {}
    for r in REGIONS:
        try:
            conn = psycopg.connect(host=config.PG_HOST, port=config.PG_PORT,
                user=config.PG_USER, password=config.PG_PASSWORD, dbname=f"{r}_cl_kg")
        except Exception:
            continue
        with conn, conn.cursor() as cur:
            cur.execute("""
              SELECT s.predicate, sub.entity_type, obj.entity_type,
                     bool_or(s.object_value IS NOT NULL),
                     bool_or(s.object_entity_id IS NOT NULL),
                     bool_or(s.object_geometry IS NOT NULL), count(*)
              FROM entity_statement s
              JOIN conceptual_entity sub ON s.subject_id = sub.pid
              LEFT JOIN conceptual_entity obj ON s.object_entity_id = obj.pid
              GROUP BY 1,2,3""")
            for pred, st, ot, hv, he, hg, n in cur.fetchall():
                a = agg.setdefault(pred, {"subj": set(), "objt": set(),
                                          "val": False, "ref": False, "geo": False, "n": 0})
                a["subj"].add(st)
                if ot:
                    a["objt"].add(ot)
                a["val"] |= hv; a["ref"] |= he; a["geo"] |= hg; a["n"] += n
    return agg


def _domain(types: set[str]) -> str:
    cls = sorted(CLASSES[t][0] for t in types if t in CLASSES)
    if not cls:
        return ""
    if len(cls) == 1:
        return f"    rdfs:domain clkg:{cls[0]} ;\n"
    union = " ".join(f"clkg:{c}" for c in cls)
    return f"    rdfs:domain [ a owl:Class ; owl:unionOf ( {union} ) ] ;\n"


def build_turtle(version: str = "0.1") -> str:
    zh = _zh_labels()
    inv = inventory()
    out = [PREFIXES, ""]
    out.append("<https://w3id.org/clkg/ontology> a owl:Ontology ;")
    out.append(f'    rdfs:label "CL-Onto · 文化景观知识图谱本体"@zh ;')
    out.append(f'    owl:versionInfo "{version}" ;')
    out.append('    rdfs:comment "CIDOC-CRM 精简对齐 + PROV-O 溯源 + 4D-fluent 时态 + RDF-star。由 ingest.ontology 从活库自动生成。"@zh .')
    out.append("")

    out.append("# ── 类（Classes）──")
    for t, (cn, czh, crm) in CLASSES.items():
        out.append(f"clkg:{cn} a owl:Class ;")
        out.append(f'    rdfs:label "{czh}"@zh, "{cn}"@en ;')
        if crm:
            out.append(f"    skos:closeMatch crm:{crm} ;")
        out.append(f'    rdfs:comment "entity_type={t}"@zh .')
        out.append("")
    out.append("clkg:Evidence a owl:Class ; rdfs:subClassOf prov:Entity ;")
    out.append('    rdfs:label "证据/溯源"@zh, "Evidence"@en .')
    out.append("")

    edges = sorted((p, a) for p, a in inv.items() if a["ref"])
    geos = sorted((p, a) for p, a in inv.items() if a["geo"] and not a["ref"])
    attrs = sorted((p, a) for p, a in inv.items() if not a["ref"] and not a["geo"])

    out.append(f"# ── 对象属性 / 关系边（{len(edges)}）──")
    for p, a in edges:
        out.append(f"clkg:{p} a owl:ObjectProperty ;")
        if p in zh:
            out.append(f'    rdfs:label "{zh[p]}"@zh ;')
        out.append(_domain(a["subj"]).rstrip("\n") or "")
        rng = sorted(CLASSES[t][0] for t in a["objt"] if t in CLASSES)
        if rng:
            r = f"clkg:{rng[0]}" if len(rng) == 1 else "[ a owl:Class ; owl:unionOf ( " + " ".join(f"clkg:{c}" for c in rng) + " ) ]"
            out.append(f"    rdfs:range {r} ;")
        if p in PROP_CRM:
            out.append(f"    skos:closeMatch crm:{PROP_CRM[p]} ;")
        out.append(f'    rdfs:comment "{a["n"]} statements"@en .')
        out.append("")

    out.append(f"# ── 空间属性（{len(geos)}）──")
    for p, a in geos:
        out.append(f"clkg:{p} a owl:ObjectProperty ;")
        out.append(_domain(a["subj"]).rstrip("\n") or "")
        out.append("    rdfs:range geo:Geometry ;")
        if p in PROP_CRM:
            out.append(f"    skos:closeMatch crm:{PROP_CRM[p]} ;")
        out.append('    rdfs:comment "object_geometry, SRID 4326 (WGS84)"@en .')
        out.append("")

    out.append(f"# ── 数据属性 / 字面值（{len(attrs)}）──")
    for p, a in attrs:
        out.append(f"clkg:{p} a owl:DatatypeProperty ;")
        if p in zh:
            out.append(f'    rdfs:label "{zh[p]}"@zh ;')
        dom = _domain(a["subj"]).rstrip("\n")
        if dom:
            out.append(dom)
        rng = "xsd:decimal" if p in NUMERIC else "xsd:string"
        out.append(f"    rdfs:range {rng} .")
        out.append("")
    return "\n".join(out)


CLASS_COLOR = {"pl": "#2E75B6", "clu": "#17a2b8", "ac": "#7030A0",
               "doc": "#C55A11", "ev": "#c0392b", "img": "#6c757d"}


def build_dot() -> str:
    """类级本体结构图（Methods F4）的 Graphviz DOT。"""
    inv = inventory()
    attr_count = {t: 0 for t in CLASSES}
    for p, a in inv.items():
        if not a["ref"] and not a["geo"]:
            for t in a["subj"]:
                if t in attr_count:
                    attr_count[t] += 1
    L = ['digraph CLOnto {',
         '  rankdir=LR; bgcolor="white"; graph[fontname="PingFang SC",fontsize=11];',
         '  node[shape=box,style="rounded,filled",fontname="PingFang SC",fontcolor=white,fontsize=12,margin="0.22,0.13"];',
         '  edge[fontname="PingFang SC",fontsize=9,color="#9aa4b2",fontcolor="#374151"];']
    for t, (cn, czh, _) in CLASSES.items():
        L.append(f'  {cn}[fillcolor="{CLASS_COLOR[t]}",label="{cn}\\n{czh} ({t})\\n{attr_count[t]} 属性"];')
    L.append('  Geometry[shape=ellipse,fillcolor="#374151",fontcolor=white,label="Geometry\\nWGS84"];')
    pairs: dict[tuple[str, str], list[str]] = {}
    for p, a in inv.items():
        if a["ref"]:
            for st in a["subj"]:
                for ot in a["objt"]:
                    if st in CLASSES and ot in CLASSES:
                        pairs.setdefault((st, ot), []).append(p)
    for (st, ot), preds in pairs.items():
        lbl = "\\n".join(sorted(set(preds)))
        L.append(f'  {CLASSES[st][0]} -> {CLASSES[ot][0]} [label="{lbl}"];')
    geo_src = set()
    for p, a in inv.items():
        if a["geo"]:
            geo_src |= {t for t in a["subj"] if t in CLASSES}
    for t in sorted(geo_src):
        L.append(f'  {CLASSES[t][0]} -> Geometry [label="locatedAt",style=dashed,color="#3a8a55"];')
    L.append("}")
    return "\n".join(L)


# ── CIDOC-CRM 映射（curated 已知项；其余走模式规则，标 broad/none 供专家细化）──
_CRM_CURATED = {
    # 对象属性
    "tookPlaceIn":        ("P7_took_place_at", "exact", ""),
    "carriedOutBy":       ("P14_carried_out_by", "exact", ""),
    "containsPlace":      ("P89_falls_within", "close", "空间包含"),
    "locatedAt":          ("P168_place_is_defined_by", "close", "→ Geometry"),
    "mentionsPlaceEntity": ("P67_refers_to", "broad", "诗→提及地"),
    "mentionsGroup":      ("P67_refers_to", "broad", ""),
    "hasSender":          ("—", "none", "信件寄件人；CRM 需经 E7+P14 间接表达"),
    "hasRecipient":       ("—", "none", "收件人；同上"),
    "hasOriginPlace":     ("P27_moved_from", "broad", "若建模为 E9 Move"),
    "hasDestinationPlace": ("P26_moved_to", "broad", "若建模为 E9 Move"),
    # 数据属性·常用
    "hasName":   ("P1_is_identified_by", "close", "→ E41 Appellation"),
    "hasTitle":  ("P102_has_title", "close", "→ E35 Title"),
    "hasAuthor": ("P14_carried_out_by", "broad", "创建活动 E65"),
}


def _crm_for(pred: str) -> tuple[str, str, str]:
    if pred in _CRM_CURATED:
        return _CRM_CURATED[pred]
    if any(k in pred for k in ("Date", "Time", "Era", "Span", "captured")):
        return ("P4_has_time-span", "broad", "时间 → E52")
    if any(k in pred for k in ("Type", "Layer", "Category", "EventType")):
        return ("P2_has_type", "close", "→ E55 Type")
    if any(k in pred for k in ("Code", "Number", "Reference", "Batch", "Identifier")):
        return ("P1_is_identified_by", "close", "→ E42 Identifier")
    if any(k in pred for k in ("Description", "Note", "FullText", "Abstract",
                               "Record", "SurveyHistory", "CulturalValue", "Concept")):
        return ("P3_has_note / P190", "close", "文本内容")
    if any(k in pred for k in ("Address", "Prefecture", "County", "Town",
                               "Village", "District", "Country")):
        return ("P87_is_identified_by", "broad", "地名/地址 → E45/E48")
    return ("—", "none", "项目扩展，无直接 CRM")


def build_crm_table() -> tuple[str, str]:
    """返回 (markdown, csv) 的 CRM 映射表。"""
    inv = inventory()
    zh = _zh_labels()
    rows = []  # (clkg, kind, crm, level, note)
    # 类
    for t, (cn, czh, crm) in CLASSES.items():
        rows.append((f"clkg:{cn}", "Class", f"crm:{crm}" if crm else "—",
                     "close" if crm else "none", czh))
    rows.append(("clkg:Evidence", "Class", "prov:Entity", "exact", "PROV-O，非 CRM"))
    # 属性
    edges = sorted(p for p, a in inv.items() if a["ref"] or a["geo"])
    attrs = sorted(p for p, a in inv.items() if not a["ref"] and not a["geo"])
    for p in edges:
        crm, lvl, note = _crm_for(p)
        rows.append((f"clkg:{p}", "ObjectProp", crm if crm == "—" else f"crm:{crm}", lvl,
                     (zh.get(p, "") + " " + note).strip()))
    for p in attrs:
        crm, lvl, note = _crm_for(p)
        rows.append((f"clkg:{p}", "DataProp", crm if crm == "—" else f"crm:{crm}", lvl,
                     (zh.get(p, "") + " " + note).strip()))

    LV = {"exact": "✅ exact", "close": "🟢 close", "broad": "🟡 broad", "none": "⚪ none"}
    md = ["# CL-Onto ↔ CIDOC-CRM 映射表",
          "",
          "match: ✅exact 等价 · 🟢close 近义 · 🟡broad 上位/需建模 · ⚪none 项目扩展无直接对应",
          "", "| CLKG 术语 | 种类 | CIDOC-CRM | match | 说明 |",
          "|---|---|---|---|---|"]
    cnt = {"exact": 0, "close": 0, "broad": 0, "none": 0}
    for clkg, kind, crm, lvl, note in rows:
        cnt[lvl] += 1
        md.append(f"| `{clkg}` | {kind} | {crm} | {LV[lvl]} | {note} |")
    md.insert(3, f"覆盖：✅{cnt['exact']} 🟢{cnt['close']} 🟡{cnt['broad']} ⚪{cnt['none']}（共 {len(rows)} 项）\n")
    csv = ["clkg,kind,cidoc_crm,match,note"]
    for clkg, kind, crm, lvl, note in rows:
        csv.append(f'"{clkg}",{kind},"{crm}",{lvl},"{note}"')
    return "\n".join(md), "\n".join(csv)


def _class_attr_counts() -> dict[str, list[tuple[str, int]]]:
    """{entity_type: [(datatype_predicate, count)...] 降序}。"""
    agg: dict[str, dict[str, int]] = {}
    for r in REGIONS:
        try:
            conn = psycopg.connect(host=config.PG_HOST, port=config.PG_PORT,
                user=config.PG_USER, password=config.PG_PASSWORD, dbname=f"{r}_cl_kg")
        except Exception:
            continue
        with conn, conn.cursor() as cur:
            cur.execute("""SELECT sub.entity_type, s.predicate, count(*)
              FROM entity_statement s JOIN conceptual_entity sub ON s.subject_id=sub.pid
              WHERE s.object_value IS NOT NULL AND s.object_entity_id IS NULL
                AND s.object_geometry IS NULL
              GROUP BY 1,2""")
            for t, p, n in cur.fetchall():
                agg.setdefault(t, {}).setdefault(p, 0)
                agg[t][p] += n
    return {t: sorted(d.items(), key=lambda x: -x[1]) for t, d in agg.items()}


def _esc(s: str) -> str:
    return str(s).replace('"', "'")


def build_vowl_dot(top_k: int = 3) -> str:
    """VOWL 风格：类=蓝圆 · 对象属性=蓝标签节点 · 数据属性=绿标签→黄类型框。力导向(neato)。"""
    inv = inventory()
    zh = _zh_labels()
    L = ['digraph VOWL {',
         '  layout=neato; overlap=false; splines=true; bgcolor="white"; sep="+8";',
         '  node[fontname="PingFang SC",fontsize=11,penwidth=0.8];',
         '  edge[color="#555555",arrowsize=0.7];']
    # 类（蓝圆，全英文）
    for t, (cn, czh, _) in CLASSES.items():
        L.append(f'  {cn}[shape=circle,style=filled,fillcolor="#AFCBEC",width=1.25,'
                 f'fixedsize=true,fontsize=10,label="{cn}"];')
    for extra in ("Geometry", "Evidence"):
        L.append(f'  {extra}[shape=circle,style=filled,fillcolor="#AFCBEC",width=1.0,'
                 f'fixedsize=true,label="{extra}"];')
    i = 0
    # 对象属性（蓝标签节点，class→prop→class）
    for p, a in inv.items():
        if not a["ref"]:
            continue
        for st in a["subj"]:
            for ot in a["objt"]:
                if st in CLASSES and ot in CLASSES:
                    op = f"op{i}"; i += 1
                    L.append(f'  {op}[shape=box,style=filled,fillcolor="#A9C7F0",'
                             f'label="{_esc(p)}",fontsize=9,height=0.22];')
                    L.append(f'  {CLASSES[st][0]} -> {op}[arrowhead=none];')
                    L.append(f'  {op} -> {CLASSES[ot][0]};')
    # locatedAt → Geometry
    for p, a in inv.items():
        if a["geo"]:
            for t in a["subj"]:
                if t in CLASSES:
                    op = f"op{i}"; i += 1
                    L.append(f'  {op}[shape=box,style=filled,fillcolor="#A9C7F0",'
                             f'label="locatedAt",fontsize=9,height=0.22];')
                    L.append(f'  {CLASSES[t][0]} -> {op}[arrowhead=none]; {op} -> Geometry;')
            break
    # 每类 → Evidence（hasEvidence，溯源边）
    for t, (cn, _czh, _) in CLASSES.items():
        op = f"op{i}"; i += 1
        L.append(f'  {op}[shape=box,style=filled,fillcolor="#A9C7F0",'
                 f'label="hasEvidence",fontsize=9,height=0.22];')
        L.append(f'  {cn} -> {op}[arrowhead=none]; {op} -> Evidence;')
    # 数据属性（每类 top_k，绿标签→黄类型框）
    attrs = _class_attr_counts()
    j = 0
    for t, lst in attrs.items():
        if t not in CLASSES:
            continue
        for pred, _cnt in lst[:top_k]:
            dp, yb = f"dp{j}", f"yb{j}"; j += 1
            rng = "decimal" if pred in NUMERIC else "string"
            L.append(f'  {dp}[shape=box,style=filled,fillcolor="#9BCB6A",'
                     f'label="{_esc(pred)}",fontsize=9,height=0.22];')
            L.append(f'  {yb}[shape=box,style=filled,fillcolor="#FFCC33",'
                     f'label="{rng}",fontsize=9,height=0.22,width=0.5];')
            L.append(f'  {CLASSES[t][0]} -> {dp}[arrowhead=none]; {dp} -> {yb};')
    L.append("}")
    return "\n".join(L)


def main(argv: list[str]) -> int:
    if "--vowl" in argv:
        import subprocess
        d = Path(__file__).resolve().parent.parent / "03_docs" / "ontology"
        d.mkdir(parents=True, exist_ok=True)
        (d / "clkg-vowl.dot").write_text(build_vowl_dot(), encoding="utf-8")
        for fmt in ("svg", "png"):
            try:
                subprocess.run(["neato", f"-T{fmt}", str(d / "clkg-vowl.dot"),
                                "-o", str(d / f"clkg-vowl.{fmt}")], check=True)
            except Exception as e:
                print(f"渲染 {fmt} 失败: {e}")
        print(f"✅ {d}/clkg-vowl.svg / .png（VOWL 风格）")
        return 0
    if "--crm" in argv:
        md, csv = build_crm_table()
        d = Path(__file__).resolve().parent.parent / "03_docs" / "ontology"
        d.mkdir(parents=True, exist_ok=True)
        (d / "crm-mapping.md").write_text(md, encoding="utf-8")
        (d / "crm-mapping.csv").write_text(csv, encoding="utf-8")
        print(f"✅ {d}/crm-mapping.md / .csv")
        return 0
    if "--dot" in argv:
        import subprocess
        dot = build_dot()
        d = Path(__file__).resolve().parent.parent / "03_docs" / "ontology"
        d.mkdir(parents=True, exist_ok=True)
        (d / "clkg-schema.dot").write_text(dot, encoding="utf-8")
        for fmt in ("svg", "png"):
            try:
                subprocess.run(["dot", f"-T{fmt}", str(d / "clkg-schema.dot"),
                                "-o", str(d / f"clkg-schema.{fmt}")], check=True)
            except Exception as e:
                print(f"渲染 {fmt} 失败: {e}")
        print(f"✅ {d}/clkg-schema.dot / .svg / .png")
        return 0
    ttl = build_turtle()
    if "--print" in argv:
        print(ttl)
        return 0
    out = Path(__file__).resolve().parent.parent / "03_docs" / "ontology" / "clkg.ttl"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(ttl, encoding="utf-8")
    n_cls = sum(1 for ln in ttl.splitlines() if ln.startswith("clkg:") and "owl:Class" in ln)
    n_obj = ttl.count("a owl:ObjectProperty")
    n_dat = ttl.count("a owl:DatatypeProperty")
    print(f"✅ {out}")
    print(f"   {n_cls} 命名类 · {n_obj} 对象属性 · {n_dat} 数据属性")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
