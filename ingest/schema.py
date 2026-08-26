"""Schema extraction + canonical DDL generation.

`dump_schema(region)` connects to an existing CLKG region database and
reverse-engineers a clean `CREATE TABLE` / `CREATE INDEX` / `ALTER TABLE` SQL
file for the three business tables (evidence / conceptual_entity /
entity_statement). This is the canonical schema baseline that `init` then
applies to NEW regions.

This file is deliberately minimal — it generates portable SQL that uses
`CREATE TABLE IF NOT EXISTS` so re-running on an existing DB is safe.
"""
from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

from . import config, db


_TABLES = ("evidence", "conceptual_entity", "entity_statement")


def _fetch_schema(conn) -> dict[str, Any]:
    """Pull columns, constraints, indexes, and owned sequences from pg_catalog."""
    out: dict[str, Any] = {"columns": {}, "constraints": {}, "indexes": {}, "sequences": []}

    with conn.cursor() as cur:
        # Columns
        cur.execute("""
            SELECT c.relname, a.attname,
                   pg_catalog.format_type(a.atttypid, a.atttypmod),
                   a.attnotnull,
                   pg_get_expr(ad.adbin, ad.adrelid)
            FROM pg_class c
            JOIN pg_namespace n ON n.oid = c.relnamespace
            JOIN pg_attribute a ON a.attrelid = c.oid
            LEFT JOIN pg_attrdef ad ON ad.adrelid = c.oid AND ad.adnum = a.attnum
            WHERE n.nspname = 'public'
              AND c.relname = ANY(%s)
              AND a.attnum > 0 AND NOT a.attisdropped
            ORDER BY c.relname, a.attnum
        """, (list(_TABLES),))
        for tn, cn, dt, nn, dv in cur.fetchall():
            out["columns"].setdefault(tn, []).append({
                "name": cn, "type": dt, "not_null": nn, "default": dv,
            })

        # Constraints (PK / UNIQUE / FK / CHECK)
        cur.execute("""
            SELECT c.relname, con.contype, con.conname, pg_get_constraintdef(con.oid)
            FROM pg_constraint con
            JOIN pg_class c ON c.oid = con.conrelid
            JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE n.nspname = 'public'
              AND c.relname = ANY(%s)
            ORDER BY c.relname, con.contype, con.conname
        """, (list(_TABLES),))
        for tn, ct, cn, df in cur.fetchall():
            out["constraints"].setdefault(tn, []).append({
                "type": ct, "name": cn, "def": df,
            })

        # Indexes (skip those backing PK/UNIQUE — already covered by constraints)
        cur.execute("""
            SELECT tablename, indexname, indexdef
            FROM pg_indexes
            WHERE schemaname = 'public'
              AND tablename = ANY(%s)
              AND indexname NOT IN (
                SELECT conname FROM pg_constraint WHERE contype IN ('p','u')
              )
            ORDER BY tablename, indexname
        """, (list(_TABLES),))
        for tn, ix, df in cur.fetchall():
            out["indexes"].setdefault(tn, []).append({"name": ix, "def": df})

        # Sequences owned by these tables (SERIAL columns)
        cur.execute("""
            SELECT s.relname
            FROM pg_class s
            JOIN pg_depend d ON d.objid = s.oid
            JOIN pg_class t ON t.oid = d.refobjid
            JOIN pg_namespace n ON n.oid = t.relnamespace
            WHERE s.relkind = 'S'
              AND n.nspname = 'public'
              AND t.relname = ANY(%s)
            ORDER BY s.relname
        """, (list(_TABLES),))
        out["sequences"] = [r[0] for r in cur.fetchall()]

    return out


def _render(schema: dict[str, Any], source_region: str) -> str:
    L: list[str] = []
    L.append("-- ============================================================================")
    L.append("-- CLKG · Canonical CL-Onto schema (3 business tables)")
    L.append(f"-- Auto-extracted from {config.db_name(source_region)} on {date.today().isoformat()}")
    L.append("--")
    L.append("-- This is the SINGLE SOURCE OF TRUTH for evidence / conceptual_entity /")
    L.append("-- entity_statement across all CLKG region databases. Any divergence found")
    L.append("-- by `python -m ingest.cli verify <region>` is a bug to fix.")
    L.append("--")
    L.append("-- This file is applied by `python -m ingest.cli init <region>` BEFORE")
    L.append("-- 01_staging.sql .. 04_grants.sql.")
    L.append("-- ============================================================================")
    L.append("")
    L.append("CREATE EXTENSION IF NOT EXISTS postgis;")
    L.append("")

    if schema["sequences"]:
        L.append("-- Sequences for SERIAL-style primary keys")
        for seq in schema["sequences"]:
            L.append(f"CREATE SEQUENCE IF NOT EXISTS {seq};")
        L.append("")

    for tbl in _TABLES:
        cols = schema["columns"].get(tbl, [])
        cons = schema["constraints"].get(tbl, [])
        idxs = schema["indexes"].get(tbl, [])
        if not cols:
            continue

        L.append(f"CREATE TABLE IF NOT EXISTS {tbl} (")
        col_lines = []
        for c in cols:
            line = f"  {c['name']} {c['type']}"
            if c["not_null"]:
                line += " NOT NULL"
            if c["default"]:
                line += f" DEFAULT {c['default']}"
            col_lines.append(line)
        # PRIMARY KEY inline (one allowed per table)
        pk = next((c for c in cons if c["type"] == "p"), None)
        if pk:
            col_lines.append(f"  CONSTRAINT {pk['name']} {pk['def']}")
        L.append(",\n".join(col_lines))
        L.append(");")
        L.append("")

        # Sequences ownership (for SERIAL-like behaviour on re-create)
        for c in cols:
            if c.get("default") and c["default"].startswith("nextval("):
                # extract sequence name from nextval('foo'::regclass)
                inner = c["default"][len("nextval("):].rsplit(")", 1)[0]
                seq_name = inner.split("::")[0].strip().strip("'\"")
                L.append(f"ALTER SEQUENCE {seq_name} OWNED BY {tbl}.{c['name']};")
        L.append("")

        # Non-PK constraints (UNIQUE / FK / CHECK / EXCLUSION)
        non_pk = [c for c in cons if c["type"] != "p"]
        if non_pk:
            for c in non_pk:
                L.append(f"ALTER TABLE {tbl} ADD CONSTRAINT {c['name']} {c['def']};")
            L.append("")

        # Indexes
        if idxs:
            for i in idxs:
                ddl = i["def"]
                # Make idempotent
                ddl = ddl.replace("CREATE INDEX ",        "CREATE INDEX IF NOT EXISTS ", 1)
                ddl = ddl.replace("CREATE UNIQUE INDEX ", "CREATE UNIQUE INDEX IF NOT EXISTS ", 1)
                L.append(f"{ddl};")
            L.append("")

    return "\n".join(L)


def dump_schema(region: str, out_path: Path) -> int:
    """Extract canonical schema from `region`'s DB; write SQL to `out_path`.
    Returns number of tables captured."""
    with db.connect(region) as conn:
        schema = _fetch_schema(conn)

    sql = _render(schema, source_region=region)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(sql, encoding="utf-8")
    return len(schema["columns"])


def list_tables(region: str) -> dict[str, list[str]]:
    """Return {table_name: [column_name, ...]} for the three business tables.
    Used by `verify` to compare actual vs canonical."""
    with db.connect(region) as conn:
        schema = _fetch_schema(conn)
    return {t: [c["name"] for c in cols] for t, cols in schema["columns"].items()}
