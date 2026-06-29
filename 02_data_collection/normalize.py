"""按 mapping_dict.json 把别名归一到标准值（遗址类型/名称标准化）。

工作流（与 template_validator.py 配套）：
    validator 暴露变体 → 在 mapping_dict.json 登记 别名→标准 → 本脚本应用 → validator 复测

用法:
    python normalize.py <region>           # dry-run：只报告将改什么，不写库
    python normalize.py <region> --apply   # 实际 UPDATE

安全：--apply 前会删除"归一后会与既有标准值撞 unique_stmt_check"的别名行
（同主体+谓词+证据已存在标准值时），避免唯一索引冲突。
"""
from __future__ import annotations
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path.home() / "clkg"))
import psycopg
from ingest import config

DICT_PATH = Path(__file__).resolve().parent / "mapping_dict.json"


def load_dict() -> dict:
    d = json.loads(DICT_PATH.read_text(encoding="utf-8"))
    # 只保留 谓词→{别名:标准} 段（跳过 _ 开头的元数据）
    return {k: v for k, v in d.items() if not k.startswith("_") and isinstance(v, dict)}


def connect(region: str):
    return psycopg.connect(
        host=config.PG_HOST, port=config.PG_PORT, user=config.PG_USER,
        password=config.PG_PASSWORD, dbname=f"{region}_cl_kg", autocommit=True,
    )


def run(region: str, apply: bool) -> int:
    mapping = load_dict()
    total = 0
    with connect(region) as c, c.cursor() as cur:
        for pred, mp in mapping.items():
            for alias, canon in mp.items():
                if alias == canon:
                    continue
                cur.execute(
                    "SELECT count(*) FROM entity_statement WHERE predicate=%s AND object_value=%s",
                    (pred, alias))
                n = cur.fetchone()[0]
                if not n:
                    continue
                total += n
                mark = "→ 将改" if not apply else "→ 已改"
                print(f"  {pred}: `{alias}` → `{canon}`  ({n} 条) {mark}")
                if apply:
                    # 先删除归一后会与既有标准值冲突的别名行
                    cur.execute("""
                        DELETE FROM entity_statement a
                        WHERE a.predicate=%s AND a.object_value=%s
                          AND EXISTS (SELECT 1 FROM entity_statement b
                              WHERE b.subject_id=a.subject_id AND b.predicate=a.predicate
                                AND b.object_value=%s
                                AND b.evidence_id IS NOT DISTINCT FROM a.evidence_id
                                AND b.object_entity_id IS NOT DISTINCT FROM a.object_entity_id
                                AND b.valid_time_start IS NOT DISTINCT FROM a.valid_time_start)""",
                        (pred, alias, canon))
                    cur.execute(
                        "UPDATE entity_statement SET object_value=%s WHERE predicate=%s AND object_value=%s",
                        (canon, pred, alias))
    if total == 0:
        print("  （无可归一的别名——库里没有词典里登记的变体）")
    print(f"\n{'已应用' if apply else 'DRY-RUN'}：{region} 命中 {total} 条"
          f"{'（未写库，加 --apply 执行）' if not apply else ''}")
    return 0


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python normalize.py <region> [--apply]", file=sys.stderr)
        sys.exit(2)
    sys.exit(run(sys.argv[1], "--apply" in sys.argv))
