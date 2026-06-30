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


def main(argv: list[str]) -> int:
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
