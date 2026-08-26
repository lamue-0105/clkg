"""StatementRow dataclass + bulk writers for staging.stg_ingest."""
from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Optional


@dataclass
class StatementRow:
    """One row destined for staging.stg_ingest — i.e. one 4D-fluent triple."""
    # evidence side
    ev_source_uri: str
    ev_source_type: str
    ev_metadata: dict
    # entity side
    ent_region: str
    ent_type_abbr: str
    ent_temporal: str
    ent_natural_key: str
    # statement side
    stmt_predicate: str
    stmt_value: dict
    stmt_valid_from: Optional[date] = None
    stmt_valid_to: Optional[date] = None
    ev_extracted_at: datetime = field(default_factory=datetime.now)


def assign_row_seqs(rows: list[StatementRow]) -> list[tuple[int, StatementRow]]:
    """Sort deterministically and number 1..N so re-running a batch produces the
    same (batch_id, row_seq) keys (PG PRIMARY KEY → idempotent re-insert)."""
    rows_sorted = sorted(rows, key=lambda r: (
        r.ev_source_uri, r.ent_natural_key, r.stmt_predicate,
        json.dumps(r.stmt_value, sort_keys=True, ensure_ascii=False),
    ))
    return list(enumerate(rows_sorted, start=1))


def write_rows(conn, batch_id: uuid.UUID, rows: list[StatementRow]) -> int:
    """Bulk insert into staging.stg_ingest. Idempotent via PK + ON CONFLICT."""
    if not rows:
        return 0
    numbered = assign_row_seqs(rows)
    params = [
        {
            "batch_id":         str(batch_id),
            "row_seq":          seq,
            "ev_source_uri":    r.ev_source_uri,
            "ev_source_type":   r.ev_source_type,
            "ev_extracted_at":  r.ev_extracted_at,
            "ev_metadata":      json.dumps(r.ev_metadata, ensure_ascii=False, default=str),
            "ent_region":       r.ent_region,
            "ent_type_abbr":    r.ent_type_abbr,
            "ent_temporal":     r.ent_temporal,
            "ent_natural_key":  r.ent_natural_key,
            "stmt_predicate":   r.stmt_predicate,
            "stmt_value":       json.dumps(r.stmt_value, ensure_ascii=False, default=str),
            "stmt_valid_from":  r.stmt_valid_from,
            "stmt_valid_to":    r.stmt_valid_to,
        }
        for seq, r in numbered
    ]
    with conn.cursor() as cur:
        cur.executemany("""
            INSERT INTO staging.stg_ingest (
              batch_id, row_seq,
              ev_source_uri, ev_source_type, ev_extracted_at, ev_metadata,
              ent_region, ent_type_abbr, ent_temporal, ent_natural_key,
              stmt_predicate, stmt_value,
              stmt_valid_from, stmt_valid_to
            ) VALUES (
              %(batch_id)s, %(row_seq)s,
              %(ev_source_uri)s, %(ev_source_type)s, %(ev_extracted_at)s, %(ev_metadata)s::jsonb,
              %(ent_region)s, %(ent_type_abbr)s, %(ent_temporal)s, %(ent_natural_key)s,
              %(stmt_predicate)s, %(stmt_value)s::jsonb,
              %(stmt_valid_from)s, %(stmt_valid_to)s
            )
            ON CONFLICT (batch_id, row_seq) DO NOTHING
        """, params)
    return len(params)


def trigger_ingest_batch(conn, batch_id: uuid.UUID) -> tuple[int, int, int]:
    with conn.cursor() as cur:
        cur.execute("SELECT rows_in, rows_ok, rows_err FROM ingest_batch(%s::uuid)",
                    (str(batch_id),))
        return cur.fetchone()
