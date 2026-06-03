"""Qiaopi pipeline: xlsx → Document/Actor/Place entities + statements → PG."""
from __future__ import annotations

import logging
import uuid
from pathlib import Path
from typing import Optional

from .. import config, db, staging
from ..connectors import qiaopi as qiaopi_conn
from ..extractors import qwen_ner
from ..staging import StatementRow

log = logging.getLogger(__name__)


def _ner_rows_from_inner_letters(rows: list[StatementRow]) -> list[StatementRow]:
    """NER over title / inner letter / notes text. Emits `mentions*` statements
    on the source Document entity. The qiaopi_geocoded_hybrid dataset stores
    innerLetter as a flag so most NER value comes from title and notes today;
    if a richer dataset (with actual letter bodies) lands, hasInnerLetter
    statements >3 chars will also be picked up automatically."""
    out: list[StatementRow] = []
    for r in rows:
        if r.stmt_predicate not in ("hasTitle", "hasInnerLetter", "hasNotes"):
            continue
        text = r.stmt_value.get("value", "")
        for ent in qwen_ner.extract_entities(text):
            etype = (ent.get("type") or "").strip()
            if etype not in {"Place", "Person", "Period", "Event"}:
                continue
            out.append(StatementRow(
                ev_source_uri=r.ev_source_uri,
                ev_source_type=r.ev_source_type,
                ev_metadata={**r.ev_metadata,
                             "extractor": f"qwen:{config.QWEN_MODEL}",
                             "ner_source_predicate": r.stmt_predicate},
                ent_region=r.ent_region,
                ent_type_abbr=r.ent_type_abbr,
                ent_temporal=r.ent_temporal,
                ent_natural_key=r.ent_natural_key,
                stmt_predicate=f"mentions{etype}",
                stmt_value={
                    "surface":    ent.get("surface"),
                    "canonical":  ent.get("canonical"),
                    "confidence": ent.get("confidence"),
                },
            ))
    return out


def run(
    *,
    xlsx_path: Path,
    region: str = "qiaopi",
    max_rows: Optional[int] = None,
    enable_ner: Optional[bool] = None,
    batch_id: Optional[uuid.UUID] = None,
) -> dict:
    batch_id = batch_id or uuid.uuid4()
    if enable_ner is None:
        enable_ner = config.ENABLE_NER

    print(f"[qiaopi] batch_id={batch_id}")
    print(f"[qiaopi] xlsx    ={xlsx_path}")
    print(f"[qiaopi] ner     ={'on' if enable_ner else 'off'}")

    rows = qiaopi_conn.ingest_qiaopi_xlsx(xlsx_path, region=region, max_rows=max_rows)
    print(f"[qiaopi] xlsx    -> {len(rows)} statement rows")

    if enable_ner:
        ner_rows = _ner_rows_from_inner_letters(rows)
        print(f"[qiaopi] ner     -> {len(ner_rows)} statement rows")
        rows.extend(ner_rows)

    with db.connect(region) as conn:
        written = staging.write_rows(conn, batch_id, rows)
        print(f"[qiaopi] staged  -> {written} rows in staging.stg_ingest")
    with db.connect(region) as conn:
        rin, rok, rerr = staging.trigger_ingest_batch(conn, batch_id)
        print(f"[qiaopi] ingest_batch: rows_in={rin} rows_ok={rok} rows_err={rerr}")

    return {"batch_id": str(batch_id), "rows_staged": written,
            "rows_in": rin, "rows_ok": rok, "rows_err": rerr}
