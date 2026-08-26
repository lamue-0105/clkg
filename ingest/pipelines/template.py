"""Template pipeline — reads a filled CLKG_采集模板.xlsx end-to-end."""
from __future__ import annotations

import logging
import uuid
from pathlib import Path
from typing import Optional

from .. import config, db, staging
from ..connectors import template as template_conn
from ..extractors import qwen_ner
from ..staging import StatementRow

log = logging.getLogger(__name__)


def _ner_rows_from_descriptions(rows: list[StatementRow]) -> list[StatementRow]:
    """For hasDescription, hasFullText, hasAbstract → run Qwen NER and emit
    mentions* statements on the same source entity."""
    NER_TEXT_PREDICATES = {"hasDescription", "hasFullText", "hasAbstract"}
    out: list[StatementRow] = []
    for r in rows:
        if r.stmt_predicate not in NER_TEXT_PREDICATES:
            continue
        text = r.stmt_value.get("value", "")
        for ent in qwen_ner.extract_entities(text):
            etype = (ent.get("type") or "").strip()
            if etype not in {"Place", "Person", "Period", "Event"}:
                continue
            out.append(StatementRow(
                ev_source_uri=r.ev_source_uri,
                ev_source_type=r.ev_source_type,
                ev_metadata={**r.ev_metadata, "extractor": f"qwen:{config.QWEN_MODEL}"},
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
    region: Optional[str] = None,
    max_rows: Optional[int] = None,
    enable_ner: Optional[bool] = None,
    batch_id: Optional[uuid.UUID] = None,
    skip_example_row: bool = True,
    strict_crs: bool = False,
    sheet_names: Optional[list[str]] = None,
) -> dict:
    """Orchestrate template ingest end-to-end.

    Parameters
    ----------
    xlsx_path : Path
        Path to the filled CLKG_采集模板.xlsx.
    region : str or None
        Region override. Auto-detected from xlsx if None.
    max_rows : int or None
        Per-sheet row limit for testing.
    enable_ner : bool or None
        Enable Qwen NER on long-text fields.  Default: config.ENABLE_NER.
    batch_id : UUID or None
        Reuse an existing batch_id for idempotent re-run.
    skip_example_row : bool
        Skip the gold-standard example row. Default True.
    strict_crs : bool
        Fail on unconvertible CRS.  (Not yet enforced.)
    sheet_names : list[str] or None
        Which sheets to ingest.  Default: all four.

    Returns
    -------
    dict with keys: batch_id, rows_staged, rows_in, rows_ok, rows_err
    """
    batch_id = batch_id or uuid.uuid4()
    if enable_ner is None:
        enable_ner = config.ENABLE_NER

    from ..connectors.template import ingest_template_xlsx

    # When region is not set explicitly, auto-detect from the sheet data.
    if region is None:
        _probe = ingest_template_xlsx(
            xlsx_path, region=None, max_rows=1,
            skip_example_row=skip_example_row,
            sheet_names=sheet_names,
        )

    print(f"[template] batch_id={batch_id}")
    print(f"[template] xlsx       ={xlsx_path}")
    print(f"[template] region     ={region or '(auto-detect)'}")
    print(f"[template] ner        ={'on' if enable_ner else 'off'}")

    # 1. Parse template → StatementRows
    #    region=None means "auto-detect from sheet data".
    #    region="mustang" overrides the sheet data — the connector respects it.
    rows = ingest_template_xlsx(
        xlsx_path,
        region=region,
        max_rows=max_rows,
        skip_example_row=skip_example_row,
        strict_crs=strict_crs,
        sheet_names=sheet_names,
    )
    # Always use the user-supplied region for DB targeting;
    # if auto-detected, use what the connector found.
    db_region = region or (rows[0].ent_region if rows else None)
    if not db_region:
        raise ValueError("Cannot determine region: pass --region or ensure "
                         "the template has at least one data row.")

    print(f"[template] parsed     → {len(rows)} statements "
          f"({len({r.ent_natural_key for r in rows})} entities) "
          f"region={db_region}")

    if not rows:
        print("[template] no rows — nothing to ingest")
        return {
            "batch_id": str(batch_id), "rows_staged": 0,
            "rows_in": 0, "rows_ok": 0, "rows_err": 0,
        }

    # 2. Optional NER
    if enable_ner:
        ner_rows = _ner_rows_from_descriptions(rows)
        print(f"[template] ner       → {len(ner_rows)} statement rows")
        rows.extend(ner_rows)

    # 3. Write staging (first transaction)
    with db.connect(db_region) as conn:
        written = staging.write_rows(conn, batch_id, rows)
        print(f"[template] staged    → {written} rows in staging.stg_ingest")

    # 4. Trigger ingest_batch (second transaction)
    with db.connect(db_region) as conn:
        rin, rok, rerr = staging.trigger_ingest_batch(conn, batch_id)
        print(f"[template] ingest_batch: rows_in={rin} rows_ok={rok} rows_err={rerr}")

    return {
        "batch_id":      str(batch_id),
        "rows_staged":   written,
        "rows_in":       rin,
        "rows_ok":       rok,
        "rows_err":      rerr,
    }
