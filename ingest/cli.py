"""Command-line entry. Run from ~/clkg/:

    python -m ingest.cli init <region>           # bootstrap a new region DB
    python -m ingest.cli dump_schema <region>    # rewrite canonical 00_create_schema.sql
    python -m ingest.cli check <region>          # health-check an existing region DB
    python -m ingest.cli verify <region>         # compare columns vs canonical schema
    python -m ingest.cli mustang [--rows N]      # ingest Mustang heritage CSV
    python -m ingest.cli qiaopi [--rows N]       # ingest Qiaopi xlsx
    python -m ingest.cli xinjiang [--rows N]     # ingest Xinjiang heritage xlsx
    python -m ingest.cli template [xlsx_path]    # ingest standard CLKG_采集模板.xlsx
"""
from __future__ import annotations

import argparse
import logging
import sys
import uuid
from pathlib import Path
from typing import Optional

import psycopg

from . import config, db, schema as schema_mod
from .pipelines import mustang as mustang_pipeline
from .pipelines import qiaopi as qiaopi_pipeline
from .pipelines import xinjiang as xinjiang_pipeline
from .pipelines import template as template_pipeline


CLKG_ROOT = Path(__file__).resolve().parent.parent
SQL_DIR   = CLKG_ROOT / "01_sql"
SQL_FILES_IN_ORDER = [
    "00_create_schema.sql",   # business tables (canonical, generated from real DB)
    "01_staging.sql",          # staging schema + audit
    "02_pid_minter.sql",       # PID sequences + resolve_or_mint_pid
    "03_ingest_batch.sql",     # ingest_batch() stored procedure
    "04_grants.sql",           # mlsql_writer role + grants
]


# ---------------------------------------------------------------------------- init

def cmd_init(args) -> int:
    """Bootstrap a new region's database: CREATE DATABASE + apply 00..04 SQL."""
    region = args.region
    db_name = config.db_name(region)

    # 1. Create the database (connect to maintenance DB)
    print(f"[init] connecting to admin DB to ensure '{db_name}' exists...")
    admin = psycopg.connect(
        host=config.PG_HOST, port=config.PG_PORT,
        user=config.PG_USER, password=config.PG_PASSWORD,
        dbname="postgres", autocommit=True,
    )
    try:
        with admin.cursor() as cur:
            cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (db_name,))
            if cur.fetchone():
                print(f"[init] database '{db_name}' already exists — applying SQL idempotently")
            else:
                cur.execute(f'CREATE DATABASE "{db_name}"')
                print(f"[init] created database '{db_name}'")
    finally:
        admin.close()

    # 2. Apply each SQL file in order
    with db.connect(region) as conn:
        for fname in SQL_FILES_IN_ORDER:
            path = SQL_DIR / fname
            if not path.exists():
                print(f"[init] WARN: {fname} not found at {path}, skipping")
                continue
            sql = path.read_text(encoding="utf-8")
            with conn.cursor() as cur:
                cur.execute(sql)
            print(f"[init] applied {fname}")

    # 3. Health check
    print("[init] verifying...")
    with db.connect(region) as conn:
        report = db.check_prereqs(conn)
    print(f"--- {region} ({db_name}) ---")
    for k, v in report.items():
        print(f"  {k:18s}: {v}")
    return 0


# ---------------------------------------------------------------------------- dump_schema

def cmd_dump_schema(args) -> int:
    """Reverse-engineer canonical schema from a region's DB into 00_create_schema.sql."""
    out_path = Path(args.out) if args.out else SQL_DIR / "00_create_schema.sql"
    n = schema_mod.dump_schema(args.region, out_path)
    print(f"[dump_schema] wrote {out_path} ({n} tables from {args.region})")
    return 0


# ---------------------------------------------------------------------------- verify

def cmd_verify(args) -> int:
    """Compare a region's column inventory against `mustang_cl_kg` as the reference."""
    try:
        target  = schema_mod.list_tables(args.region)
        canonical = schema_mod.list_tables(args.reference)
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2

    diffs = 0
    print(f"--- {args.region} vs {args.reference} ---")
    all_tables = set(target) | set(canonical)
    for t in sorted(all_tables):
        tcols = set(target.get(t, []))
        ccols = set(canonical.get(t, []))
        if tcols == ccols:
            print(f"  {t:20s}: OK ({len(tcols)} cols)")
            continue
        diffs += 1
        missing = ccols - tcols
        extra   = tcols - ccols
        print(f"  {t:20s}: DRIFT")
        if missing: print(f"      missing: {sorted(missing)}")
        if extra:   print(f"      extra:   {sorted(extra)}")
    return 1 if diffs else 0


# ---------------------------------------------------------------------------- check

def cmd_check(args) -> int:
    try:
        with db.connect(args.region) as conn:
            report = db.check_prereqs(conn)
    except Exception as e:
        print(f"ERROR connecting to {args.region}: {e}", file=sys.stderr)
        return 2
    print(f"--- {args.region} ({config.db_name(args.region)}) ---")
    for k, v in report.items():
        print(f"  {k:18s}: {v}")
    return 0


# ---------------------------------------------------------------------------- pipelines

def cmd_mustang(args) -> int:
    csv_path: Path = args.csv or (config.project_root("mustang")
                                  / "tabular" / "mustang_fixed.csv")
    photos_root: Path = args.photos or (config.project_root("mustang") / "photos")
    if not csv_path.exists():
        print(f"ERROR: csv not found: {csv_path}", file=sys.stderr)
        return 2
    bid = uuid.UUID(args.batch_id) if args.batch_id else None
    mustang_pipeline.run(
        csv_path=csv_path,
        photos_root=photos_root if photos_root.exists() else None,
        photo_table_path=args.photo_table,
        polygon_gdb_path=args.polygon_gdb,
        polygon_layer=args.polygon_layer,
        max_rows=args.rows,
        photo_max_rows=args.photo_rows,
        polygon_max_rows=args.polygon_rows,
        enable_ner=(None if args.ner == "auto" else (args.ner == "on")),
        batch_id=bid,
        link_spatial=not args.no_spatial,
    )
    return 0


def cmd_xinjiang(args) -> int:
    xlsx_path: Optional[Path] = args.xlsx
    gdb_path:  Optional[Path] = args.gdb
    if not xlsx_path and not gdb_path:
        print("ERROR: pass at least one of --xlsx or --gdb", file=sys.stderr)
        return 2
    if xlsx_path and not xlsx_path.exists():
        print(f"ERROR: xlsx not found: {xlsx_path}", file=sys.stderr)
        return 2
    if gdb_path and not gdb_path.exists():
        print(f"ERROR: gdb not found: {gdb_path}", file=sys.stderr)
        return 2
    bid = uuid.UUID(args.batch_id) if args.batch_id else None
    xinjiang_pipeline.run(
        xlsx_path=xlsx_path,
        gdb_path=gdb_path,
        max_rows=args.rows,
        gdb_max_rows_per_layer=args.gdb_rows,
        enable_ner=(None if args.ner == "auto" else (args.ner == "on")),
        batch_id=bid,
    )
    return 0


def cmd_qiaopi(args) -> int:
    xlsx_path: Path = args.xlsx or (config.project_root("qiaopi")
                                    / "tabular" / "qiaopi_geocoded_hybrid.xlsx")
    if not xlsx_path.exists():
        print(f"ERROR: xlsx not found: {xlsx_path}", file=sys.stderr)
        return 2
    bid = uuid.UUID(args.batch_id) if args.batch_id else None
    qiaopi_pipeline.run(
        xlsx_path=xlsx_path, max_rows=args.rows,
        enable_ner=(None if args.ner == "auto" else (args.ner == "on")),
        batch_id=bid,
    )
    return 0


def cmd_template(args) -> int:
    xlsx_path: Path = args.xlsx or (CLKG_ROOT / "02_data_collection" / "CLKG_采集模板.xlsx")
    if not xlsx_path.exists():
        print(f"ERROR: template xlsx not found: {xlsx_path}", file=sys.stderr)
        return 2
    bid = uuid.UUID(args.batch_id) if args.batch_id else None
    template_pipeline.run(
        xlsx_path=xlsx_path,
        region=args.region,
        max_rows=args.rows,
        enable_ner=(None if args.ner == "auto" else (args.ner == "on")),
        batch_id=bid,
        skip_example_row=not args.no_skip_example,
        strict_crs=args.strict_crs,
    )
    return 0


# ---------------------------------------------------------------------------- main

def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    p = argparse.ArgumentParser(prog="clkg-ingest")
    sub = p.add_subparsers(dest="cmd", required=True)

    pi = sub.add_parser("init", help="Bootstrap a region DB: CREATE DATABASE + apply 00..04")
    pi.add_argument("region", help="region name (e.g. 'dunhuang', 'kashgar')")
    pi.set_defaults(func=cmd_init)

    pds = sub.add_parser("dump_schema",
        help="Reverse-engineer canonical schema from a known-good DB into 00_create_schema.sql")
    pds.add_argument("region")
    pds.add_argument("--out", default=None, help="output path (default: 01_sql/00_create_schema.sql)")
    pds.set_defaults(func=cmd_dump_schema)

    pv = sub.add_parser("verify",
        help="Compare a region's columns against a reference region (default: mustang)")
    pv.add_argument("region")
    pv.add_argument("--reference", default="mustang")
    pv.set_defaults(func=cmd_verify)

    pc = sub.add_parser("check", help="Health-check a region's PG database")
    pc.add_argument("region")
    pc.set_defaults(func=cmd_check)

    pm = sub.add_parser("mustang", help="Run Mustang ingest pipeline")
    pm.add_argument("--csv", type=Path, default=None,
                    help="heritage points CSV (default: NAS/mustang/tabular/mustang_fixed.csv)")
    pm.add_argument("--photos", type=Path, default=None,
                    help="photos folder organized as photos/{natural_key}/*.jpg")
    pm.add_argument("--photo-table", type=Path, default=None,
                    help="photo-metadata table (CSV with GPS columns, GBK-encoded OK)")
    pm.add_argument("--rows", type=int, default=None,
                    help="limit heritage CSV rows for testing")
    pm.add_argument("--photo-rows", type=int, default=None,
                    help="limit photo-table rows for testing")
    pm.add_argument("--polygon-gdb", type=Path, default=None,
                    help="path to ArcGIS GDB or shapefile holding polygon CLU features")
    pm.add_argument("--polygon-layer", type=str, default=None,
                    help="layer name inside the GDB (e.g. 'Heritage_Polygon202504')")
    pm.add_argument("--polygon-rows", type=int, default=None,
                    help="limit polygon rows for testing")
    pm.add_argument("--ner", choices=["auto", "on", "off"], default="auto")
    pm.add_argument("--batch-id", type=str, default=None)
    pm.add_argument("--no-spatial", action="store_true",
                    help="skip post-ingest containsPlace spatial inference")
    pm.set_defaults(func=cmd_mustang)

    px = sub.add_parser("xinjiang", help="Run Xinjiang ingest pipeline (xlsx + gdb)")
    px.add_argument("--xlsx", type=Path, default=None,
                    help="path to 《不可移动的文物》古遗址三普信息表 xlsx")
    px.add_argument("--gdb", type=Path, default=None,
                    help="path to 新疆文保数据 GDB folder")
    px.add_argument("--rows", type=int, default=None,
                    help="limit xlsx rows for testing")
    px.add_argument("--gdb-rows", type=int, default=None,
                    help="limit rows PER LAYER in the GDB (for testing)")
    px.add_argument("--ner", choices=["auto", "on", "off"], default="auto")
    px.add_argument("--batch-id", type=str, default=None)
    px.set_defaults(func=cmd_xinjiang)

    pq = sub.add_parser("qiaopi", help="Run Qiaopi ingest pipeline")
    pq.add_argument("--xlsx", type=Path, default=None)
    pq.add_argument("--rows", type=int, default=None)
    pq.add_argument("--ner", choices=["auto", "on", "off"], default="auto")
    pq.add_argument("--batch-id", type=str, default=None)
    pq.set_defaults(func=cmd_qiaopi)

    pt = sub.add_parser("template", help="Run standard template (CLKG_采集模板.xlsx) ingest")
    pt.add_argument("xlsx", type=Path, nargs="?", default=None,
                    help="path to template xlsx (default: 02_data_collection/CLKG_采集模板.xlsx)")
    pt.add_argument("--region", type=str, default=None,
                    help="override auto-detected region")
    pt.add_argument("--rows", type=int, default=None,
                    help="limit entity rows per sheet for testing")
    pt.add_argument("--ner", choices=["auto", "on", "off"], default="auto")
    pt.add_argument("--batch-id", type=str, default=None)
    pt.add_argument("--no-skip-example", action="store_true",
                    help="do NOT skip the gold-standard example row (for testing)")
    pt.add_argument("--strict-crs", action="store_true",
                    help="fail on GCJ-02/BD-09 coordinates (future: not yet enforced)")
    pt.set_defaults(func=cmd_template)

    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
