"""PostgreSQL connection helpers."""
from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

import psycopg

from . import config


@contextmanager
def connect(region: str) -> Iterator[psycopg.Connection]:
    conn = psycopg.connect(
        host=config.PG_HOST,
        port=config.PG_PORT,
        user=config.PG_USER,
        password=config.PG_PASSWORD,
        dbname=config.db_name(region),
        autocommit=False,
    )
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def check_prereqs(conn: psycopg.Connection) -> dict:
    """Return a quick health report on what's deployed in the connected DB."""
    out = {}
    with conn.cursor() as cur:
        cur.execute("""
            SELECT EXISTS(
              SELECT 1 FROM information_schema.schemata WHERE schema_name='staging'
            )""")
        out["staging_schema"] = cur.fetchone()[0]

        cur.execute("""
            SELECT array_agg(table_name ORDER BY table_name)
            FROM information_schema.tables
            WHERE table_schema='public'
              AND table_name IN ('evidence','conceptual_entity','entity_statement')
        """)
        out["business_tables"] = cur.fetchone()[0] or []

        cur.execute("""
            SELECT array_agg(routine_name ORDER BY routine_name)
            FROM information_schema.routines
            WHERE routine_schema='public'
              AND routine_name IN ('mint_pid','resolve_or_mint_pid','ingest_batch')
        """)
        out["functions"] = cur.fetchone()[0] or []

        cur.execute("SELECT extname FROM pg_extension WHERE extname IN ('postgis','pgcrypto')")
        out["extensions"] = [r[0] for r in cur.fetchall()]
    return out
