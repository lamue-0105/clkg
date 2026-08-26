"""命令行：对任意来源表打印列映射建议，供人工确认。

    python -m ingest.matching <xlsx> [sheet]
"""
from __future__ import annotations
import sys
from . import suggest_for_xlsx

KIND_ICON = {"role": "⚙ 角色", "predicate": "▪ 谓词", "ref": "→ 引用",
             "relation_meta": "· 跳过", "": "?"}


def main(argv: list[str]) -> int:
    if not argv:
        print("用法: python -m ingest.matching <xlsx> [sheet]", file=sys.stderr)
        return 2
    path = argv[0]
    sheet = argv[1] if len(argv) > 1 else None
    props = suggest_for_xlsx(path, sheet)

    print(f"列映射建议 · {path}" + (f" [{sheet}]" if sheet else ""))
    print("（这是建议，需人工确认后再入库；低置信/未匹配项重点核对）\n")
    print(f"{'列':>3}  {'表头':<24}  {'建议目标':<16}  {'类型':<7} {'信心':>4}  原因")
    print("-" * 96)
    low = 0
    for p in props:
        tgt = p["target"] if p["target"] is not None else "—"
        sc = p["score"]
        flag = "⚠️" if (sc < 0.5 and p["kind"] != "relation_meta") else "  "
        if sc < 0.5 and p["kind"] != "relation_meta":
            low += 1
        hdr = (str(p["header"])[:22] + "…") if p["header"] and len(str(p["header"])) > 23 else str(p["header"])
        print(f"{p['col']:>3}  {hdr:<24}  {tgt:<16}  {KIND_ICON.get(p['kind'],'?'):<7} {sc:>4} {flag} {p['reason']}")
    print("-" * 96)
    matched = sum(1 for p in props if p["kind"] in ("role", "predicate", "ref") and p["score"] >= 0.5)
    print(f"共 {len(props)} 列：{matched} 列高信心建议，{low} 列需人工确认，"
          f"{sum(1 for p in props if p['kind']=='relation_meta')} 列关系标注(跳过)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
