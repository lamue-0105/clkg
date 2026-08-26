"""CLKG 数据质量自检（SOP §8 六维度评估），输出 markdown 归档。

用法：
    python audit_quality.py mustang
    python audit_quality.py qiaopi
    python audit_quality.py xinjiang

输出：
    ~/clkg/02_data_collection/quality-audit/{region}-{YYYY-MM-DD}.md
"""
from __future__ import annotations
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path.home() / "clkg"))
import psycopg
from ingest import config

# 项目地理边界（lat_min, lat_max, lon_min, lon_max）
BBOX = {
    "mustang":  (28.0, 30.0, 83.0, 84.5),
    "qiaopi":   (0.0, 30.0, 100.0, 120.0),   # 含东南亚寄出地 + 潮汕收件地
    "xinjiang": (34.0, 49.0, 73.0, 96.0),
    "kashgar":  (37.0, 41.0, 73.0, 80.0),
    "liangzhu": (30.0, 31.5, 119.5, 121.0),
}

# 各项目预期主要 entity_type
EXPECTED_TYPES = {
    "mustang":  ["pl", "clu", "img"],
    "qiaopi":   ["pl", "ac", "doc"],
    "xinjiang": ["pl", "clu"],
    "kashgar":  ["pl", "clu"],
    "liangzhu": ["pl", "clu"],
}


def connect(region):
    return psycopg.connect(
        host=config.PG_HOST, port=config.PG_PORT,
        user=config.PG_USER, password=config.PG_PASSWORD,
        dbname=f"{region}_cl_kg", autocommit=True,
    )


def d1_coverage(cur, region):
    """维度 1 · 实体覆盖度"""
    cur.execute("SELECT entity_type, count(*) FROM conceptual_entity GROUP BY 1 ORDER BY 1")
    rows = cur.fetchall()
    actual = {r[0]: r[1] for r in rows}
    expected = EXPECTED_TYPES.get(region, [])
    missing = [t for t in expected if actual.get(t, 0) == 0]
    return {
        "by_type": actual,
        "expected_types": expected,
        "missing_types": missing,
        "total_entities": sum(actual.values()),
    }


def d2_crossref(cur):
    """维度 2 · 跨表关联完整性（悬空引用率）"""
    cur.execute("""
        SELECT count(*) FROM entity_statement
        WHERE predicate IN ('hasSender','hasRecipient','depicts','relatedPlace',
                            'relatedActor','hasOriginPlace','hasDestinationPlace')
    """)
    total_refs = cur.fetchone()[0]
    cur.execute("""
        SELECT count(*) FROM entity_statement
        WHERE object_entity_id IS NULL
          AND predicate IN ('hasSender','hasRecipient','depicts','relatedPlace',
                            'relatedActor','hasOriginPlace','hasDestinationPlace')
    """)
    dangling = cur.fetchone()[0]
    rate = (dangling / total_refs * 100) if total_refs else 0.0
    return {"total_refs": total_refs, "dangling": dangling, "dangling_rate_pct": rate}


def d3_evidence(cur):
    """维度 3 · 来源链完整性"""
    cur.execute("SELECT count(*) FROM conceptual_entity")
    n_total = cur.fetchone()[0]
    cur.execute("""
        SELECT count(*) FROM conceptual_entity ce
        WHERE NOT EXISTS (
          SELECT 1 FROM entity_statement es
          WHERE es.subject_id = ce.pid AND es.evidence_id IS NOT NULL
        )
    """)
    no_ev = cur.fetchone()[0]
    rate = (no_ev / n_total * 100) if n_total else 0.0
    return {"total_entities": n_total, "no_evidence": no_ev, "no_evidence_rate_pct": rate}


def d4_spatial(cur, region):
    """维度 4 · 空间精度"""
    bbox = BBOX.get(region)
    if not bbox:
        return {"bbox": None, "msg": "无项目边界定义，跳过"}
    lat_min, lat_max, lon_min, lon_max = bbox
    cur.execute("""
        SELECT count(*) FROM entity_statement
        WHERE predicate='locatedAt' AND object_geometry IS NOT NULL
    """)
    total = cur.fetchone()[0]
    cur.execute(f"""
        SELECT count(*) FROM entity_statement s
        JOIN conceptual_entity c ON s.subject_id = c.pid
        WHERE predicate='locatedAt' AND object_geometry IS NOT NULL
          AND c.entity_type IN ('pl','clu')
          AND NOT (ST_Y(ST_Centroid(object_geometry)) BETWEEN {lat_min} AND {lat_max}
               AND ST_X(ST_Centroid(object_geometry)) BETWEEN {lon_min} AND {lon_max})
    """)
    outliers = cur.fetchone()[0]
    rate = (outliers / total * 100) if total else 0.0
    return {
        "bbox": bbox, "total_geom": total,
        "outliers": outliers, "outlier_rate_pct": rate,
    }


def d5_ontology(cur, region):
    """维度 5 · 本体一致性（hasType distinct 值）"""
    cur.execute(f"""
        SELECT object_value, count(*) FROM entity_statement
        WHERE predicate='hasType' AND subject_id LIKE 'clkg:{region}:%'
        GROUP BY 1 ORDER BY 2 DESC
    """)
    rows = cur.fetchall()
    return {"distinct_values": len(rows), "top_values": rows[:15]}


def d6_assets(cur):
    """维度 6 · 多模态对齐"""
    cur.execute("""
        WITH pl_with_asset AS (
          SELECT DISTINCT s.object_entity_id AS pid
          FROM entity_statement s
          JOIN conceptual_entity c ON s.subject_id=c.pid
          WHERE c.entity_type='img' AND s.predicate='depicts'
        )
        SELECT
          count(*) FILTER (WHERE entity_type='pl') AS total_pl,
          count(*) FILTER (WHERE entity_type='pl' AND pid IN (SELECT pid FROM pl_with_asset)) AS pl_photo
        FROM conceptual_entity
    """)
    r = cur.fetchone()
    total_pl, pl_photo = r[0] or 0, r[1] or 0
    rate = (pl_photo / total_pl * 100) if total_pl else 0.0
    return {"total_pl": total_pl, "pl_with_photo": pl_photo, "coverage_pct": rate}


def grade(d1, d2, d3, d4, d6):
    """三级采集完成度分级"""
    # 简化判断：MVP 看 d3/d4 是否 100%；研究就绪看 d1 实体数 + d2 悬空率；公开发布看 d6 + d5
    mvp = d3["no_evidence_rate_pct"] == 0 and d4["outlier_rate_pct"] == 0
    research = mvp and d2["dangling_rate_pct"] < 1 and d1["total_entities"] >= 100
    publish = research and d6["coverage_pct"] >= 80
    if publish: return "🔵 公开发布"
    if research: return "🟢 研究就绪"
    if mvp: return "🟡 MVP（最小可用）"
    return "⚪ 未达底线"


def render_markdown(region, results):
    today = date.today().isoformat()
    d1, d2, d3, d4, d5, d6 = (results[k] for k in "d1 d2 d3 d4 d5 d6".split())
    g = grade(d1, d2, d3, d4, d6)
    lines = [
        f"# 数据质量自检 · {region}_cl_kg",
        f"**审计日期**: {today}　**审计依据**: SOP §8 六维度评估　**综合分级**: {g}",
        "",
        "---",
        "",
        "## 维度 1 · 实体覆盖度",
        f"- 总实体数: **{d1['total_entities']}**",
        f"- 预期主要类型: {d1['expected_types']}",
        f"- 实际分布: {d1['by_type']}",
        f"- 缺失类型: {d1['missing_types'] or '✅ 无'}",
        "",
        "## 维度 2 · 跨表关联完整性",
        f"- 跨表引用总数: {d2['total_refs']}",
        f"- 悬空引用: {d2['dangling']}（{d2['dangling_rate_pct']:.2f}%）",
        f"- 判定: {'✅ < 1% 达标' if d2['dangling_rate_pct'] < 1 else '⚠️ 超标'}",
        "",
        "## 维度 3 · 来源链完整性",
        f"- 无证据实体: {d3['no_evidence']} / {d3['total_entities']}（{d3['no_evidence_rate_pct']:.2f}%）",
        f"- 判定: {'✅ 全部有证据' if d3['no_evidence'] == 0 else '⚠️ 存在无源实体'}",
        "",
        "## 维度 4 · 空间精度",
    ]
    if d4.get("bbox"):
        lines += [
            f"- 项目边界 (lat × lon): {d4['bbox']}",
            f"- 带几何 statement 总数: {d4['total_geom']}",
            f"- 越界点: {d4['outliers']}（{d4['outlier_rate_pct']:.2f}%）",
            f"- 判定: {'✅ 全部落在边界内' if d4['outliers'] == 0 else '⚠️ 越界（疑似 SRID 错误）'}",
        ]
    else:
        lines.append(f"- {d4.get('msg', 'N/A')}")
    lines += [
        "",
        "## 维度 5 · 本体一致性（hasType 取值）",
        f"- distinct 值数: {d5['distinct_values']}",
    ]
    if d5["top_values"]:
        lines.append("- Top 15:")
        for v, n in d5["top_values"]:
            lines.append(f"  - `{v}` × {n}")
    else:
        lines.append("- （无 hasType 数据）")
    lines += [
        "",
        "## 维度 6 · 多模态对齐",
        f"- Place(pl) 总数: {d6['total_pl']}",
        f"- 有 depicts 照片的 pl: {d6['pl_with_photo']}（{d6['coverage_pct']:.2f}%）",
        f"- 判定: {'✅ ≥ 80% 达标' if d6['coverage_pct'] >= 80 else '⚠️ 不足 80%（视项目可放宽）'}",
        "",
        "---",
        "",
        "## 行动建议",
    ]
    actions = []
    if d3["no_evidence"]:
        actions.append("- 🔴 维度 3: 补全无证据实体的 source（关系到底线）")
    if d4.get("outliers", 0):
        actions.append("- 🔴 维度 4: 检查越界坐标的 SRID（可能是坐标系错填）")
    if d2["dangling_rate_pct"] >= 1:
        actions.append("- 🟡 维度 2: 修复悬空跨表引用（多半是 natural_key 拼写不一致）")
    if d1["missing_types"]:
        actions.append(f"- 🟡 维度 1: 补采缺失类型 {d1['missing_types']}")
    if d6["coverage_pct"] < 80 and d6["total_pl"] > 0:
        actions.append("- 🟢 维度 6: 推进资产采集（如做田野/出版需求）")
    if not actions:
        actions.append("- ✨ 当前未发现需立即处置的问题")
    lines += actions + ["", f"_由 audit_quality.py 自动生成于 {today}_"]
    return "\n".join(lines)


def main(region):
    out_dir = Path(__file__).resolve().parent / "quality-audit"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / f"{region}-{date.today().isoformat()}.md"

    with connect(region) as conn:
        cur = conn.cursor()
        results = {
            "d1": d1_coverage(cur, region),
            "d2": d2_crossref(cur),
            "d3": d3_evidence(cur),
            "d4": d4_spatial(cur, region),
            "d5": d5_ontology(cur, region),
            "d6": d6_assets(cur),
        }
    md = render_markdown(region, results)
    out_file.write_text(md, encoding="utf-8")
    print(f"✅ {out_file}")
    print(f"   分级: {grade(results['d1'], results['d2'], results['d3'], results['d4'], results['d6'])}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("usage: python audit_quality.py <region>")
        sys.exit(1)
    main(sys.argv[1])
