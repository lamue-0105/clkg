"""CLKG 入库对齐校验器（采集即校验 / pre-ingest quality gate 的库端实现）。

检测"入库数据是否与目标表头(collection_schema)对齐"，并产出 H3 实验指标：
  M1 谓词值域离散度  —— 受控词表谓词的 distinct 取值数（越高 = 漂移风险越大）
  M2 事后归一化率    —— 取值落在词表外、需要 UPDATE 归一的 statement 占比

与 audit_quality.py 互补：audit 看 6 维数据质量；本脚本看 schema/表头一致性。
单一真相源 = ingest.collection_schema（与模板生成、连接器共用，防漂移）。

用法:
    python template_validator.py mustang
    python template_validator.py qiaopi
    python template_validator.py xinjiang

输出:
    ~/clkg/02_data_collection/quality-audit/{region}-validation-{YYYY-MM-DD}.md
"""
from __future__ import annotations
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path.home() / "clkg"))
import psycopg
from ingest import config
from ingest.collection_schema import ALL_SHEETS, EXTENSION_SHEETS, VOCAB

# 谓词 -> 允许取值集合（从 schema 的受控词表列提取）
PRED_VOCAB: dict[str, set[str]] = {}
for _sd in ALL_SHEETS + EXTENSION_SHEETS:
    for _c in _sd.columns:
        if _c.predicate and _c.vocab_key and _c.vocab_key in VOCAB:
            PRED_VOCAB.setdefault(_c.predicate, set()).update(VOCAB[_c.vocab_key])

VALID_ET = set(VOCAB["entity_type"])
# 数值型谓词 -> (下限, 上限)；用于类型合理性检查
NUMERIC_RANGE = {"hasEmotionScore": (0.0, 1.0)}


def connect(region: str):
    return psycopg.connect(
        host=config.PG_HOST, port=config.PG_PORT, user=config.PG_USER,
        password=config.PG_PASSWORD, dbname=f"{region}_cl_kg", autocommit=True,
    )


def validate(region: str) -> dict:
    res = {"region": region, "entity_type": {}, "vocab": [], "numeric": [], "geom": {}}
    with connect(region) as c, c.cursor() as cur:
        # C1 entity_type 域
        cur.execute("SELECT DISTINCT entity_type FROM conceptual_entity")
        ets = {r[0] for r in cur.fetchall()}
        res["entity_type"] = {"actual": sorted(ets), "illegal": sorted(ets - VALID_ET)}

        # C2 受控词表谓词 + M1/M2
        m2_total = m2_bad = 0
        for pred, allowed in sorted(PRED_VOCAB.items()):
            cur.execute(
                "SELECT object_value, count(*) FROM entity_statement "
                "WHERE predicate=%s AND object_value IS NOT NULL GROUP BY 1", (pred,))
            vals = cur.fetchall()
            if not vals:
                continue
            n_stmt = sum(n for _, n in vals)
            bad = [(v, n) for v, n in vals if v not in allowed]
            m2_total += n_stmt
            m2_bad += sum(n for _, n in bad)
            res["vocab"].append({
                "predicate": pred, "distinct": len(vals), "stmts": n_stmt,
                "out_of_vocab": [{"value": v, "n": n} for v, n in bad],
            })
        res["m1_distinct_total"] = sum(v["distinct"] for v in res["vocab"])
        res["m2_total"], res["m2_bad"] = m2_total, m2_bad
        res["m2_rate_pct"] = (m2_bad / m2_total * 100) if m2_total else 0.0

        # C3 数值型谓词合理性
        for pred, (lo, hi) in NUMERIC_RANGE.items():
            cur.execute("SELECT object_value FROM entity_statement "
                        "WHERE predicate=%s AND object_value IS NOT NULL", (pred,))
            vals = [r[0] for r in cur.fetchall()]
            if not vals:
                continue
            bad = 0
            for v in vals:
                try:
                    f = float(v)
                    if not (lo <= f <= hi):
                        bad += 1
                except (TypeError, ValueError):
                    bad += 1
            res["numeric"].append({"predicate": pred, "n": len(vals), "bad": bad,
                                   "range": [lo, hi]})

        # C4 坐标全局范围（抓 lon/lat 互换、垃圾值）
        cur.execute("SELECT count(*) FROM entity_statement WHERE object_geometry IS NOT NULL")
        gtot = cur.fetchone()[0]
        cur.execute("""SELECT count(*) FROM entity_statement WHERE object_geometry IS NOT NULL
                       AND NOT (ST_X(ST_Centroid(object_geometry)) BETWEEN -180 AND 180
                            AND ST_Y(ST_Centroid(object_geometry)) BETWEEN -90 AND 90)""")
        res["geom"] = {"total": gtot, "out_of_range": cur.fetchone()[0]}
    return res


def render(res: dict) -> str:
    r = res
    et_ok = not r["entity_type"]["illegal"]
    vocab_bad = sum(1 for v in r["vocab"] if v["out_of_vocab"])
    num_bad = sum(x["bad"] for x in r["numeric"])
    geom_ok = r["geom"].get("out_of_range", 0) == 0
    aligned = et_ok and vocab_bad == 0 and num_bad == 0 and geom_ok
    L = [
        f"# 入库对齐校验 · {r['region']}_cl_kg",
        f"**校验日期**: {date.today().isoformat()}　**对齐结论**: "
        f"{'✅ 完全对齐' if aligned else '⚠️ 存在未对齐项'}",
        "",
        "## 指标（供 H3 实验 B/T 对照）",
        f"- **M1 谓词值域离散度**: 受控谓词 distinct 取值合计 = **{r['m1_distinct_total']}**",
        f"- **M2 事后归一化率**: {r['m2_bad']} / {r['m2_total']} = **{r['m2_rate_pct']:.2f}%**"
        f"（落在词表外、需 UPDATE 归一的占比；前置式应趋近 0）",
        "",
        "## C1 · entity_type 域一致性",
        f"- 实际: {r['entity_type']['actual']}",
        f"- 判定: {'✅ 全部合法' if et_ok else '❌ 越界: ' + str(r['entity_type']['illegal'])}",
        "",
        "## C2 · 受控词表谓词一致性",
    ]
    if not r["vocab"]:
        L.append("- （无受控词表谓词数据）")
    for v in r["vocab"]:
        if v["out_of_vocab"]:
            oo = ", ".join(f"`{x['value']}`×{x['n']}" for x in v["out_of_vocab"][:8])
            L.append(f"- `{v['predicate']}`: {v['distinct']} 种取值　⚠️ 词表外: {oo}")
        else:
            L.append(f"- `{v['predicate']}`: {v['distinct']} 种取值　✅")
    L += ["", "## C3 · 数值型谓词合理性"]
    if not r["numeric"]:
        L.append("- （无数值型谓词数据）")
    for x in r["numeric"]:
        tag = "✅" if x["bad"] == 0 else f"❌ {x['bad']} 条非法"
        L.append(f"- `{x['predicate']}` ∈ {x['range']}: {x['n']} 条　{tag}")
    L += ["", "## C4 · 坐标全局范围",
          f"- 带几何 {r['geom'].get('total',0)} 条，越界 {r['geom'].get('out_of_range',0)} 条　"
          f"{'✅' if geom_ok else '❌ 疑似经纬度互换/垃圾值'}",
          "", "_由 template_validator.py 自动生成_"]
    return "\n".join(L)


def main(region: str) -> int:
    res = validate(region)
    out_dir = Path(__file__).resolve().parent / "quality-audit"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / f"{region}-validation-{date.today().isoformat()}.md"
    out_file.write_text(render(res), encoding="utf-8")
    aligned = (not res["entity_type"]["illegal"]
               and not any(v["out_of_vocab"] for v in res["vocab"])
               and not any(x["bad"] for x in res["numeric"])
               and res["geom"].get("out_of_range", 0) == 0)
    print(f"✅ {out_file}")
    print(f"   对齐: {'✅ 完全对齐' if aligned else '⚠️ 有未对齐项'} | "
          f"M1 离散度={res['m1_distinct_total']} | M2 归一化率={res['m2_rate_pct']:.2f}%")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("用法: python template_validator.py <region>", file=sys.stderr)
        sys.exit(2)
    sys.exit(main(sys.argv[1]))
