"""Xinjiang 三普 pipeline: xlsx → Place statements → PG."""
from __future__ import annotations

import logging
import uuid
from pathlib import Path
from typing import Optional

from .. import config, db, staging
from ..connectors import shapefile, xinjiang as xinjiang_conn
from ..extractors import qwen_ner
from ..staging import StatementRow


# Per-layer config for the 新疆文保数据.gdb 3-tier heritage protection points.
# Columns differ slightly between tiers (e.g. 级别 vs 保护级); we list ALL
# variants in extra_predicates — columns absent in a given layer are silently
# skipped by the generic connector.
_HERITAGE_LAYERS = [
    "国家级文保CGCS_2000",
    "自治区级文保CGCS_2000",
    "县（市）级文保CGCS_2000",
]

_HERITAGE_EXTRA_PREDICATES = {
    # heritage classification fields (same semantic, different field names)
    "级别":   "hasHeritageLevel",   # 国家级/自治区级 layers
    "保护级": "hasHeritageLevel",   # 县（市）级 layer
    # gazetted batch / document
    "公布批": "hasGazettedBatch",   # higher tiers (e.g. '第五批')
    "批次":   "hasGazettedBatch",   # county tier ('第二批' etc.)
    "公布日": "hasGazettedDate",
    "公布时": "hasGazettedDate",
    # era and category
    "时代":   "hasEra",
    "类别":   "hasCategoryType",
    # admin hierarchy
    "所属地": "hasPrefecture",
    "地州":   "hasPrefecture",      # county tier
    "地州_市": "hasPrefecture",     # autonomous tier
    "所属县": "hasCounty",
    # address + official code
    "地址":   "hasAddress",
    "文物_1": "hasHeritageCode",    # 650102-0009 (county tier official code)
    # protection facilities (Y/N flags, mostly empty)
    "有保护": "hasProtectionFacility",
    "有标志": "hasSignage",
    "有记录": "hasRecord",
    "有专门": "hasSpecialUnit",
    "备注":   "hasNote",
}

log = logging.getLogger(__name__)


def _ner_rows(rows: list[StatementRow]) -> list[StatementRow]:
    """Run Qwen NER over 简介 / 环境状况 / 备注2 — the long-form descriptive fields."""
    targets = {"hasDescription", "hasEnvironment", "hasSurveyHistory"}
    out: list[StatementRow] = []
    for r in rows:
        if r.stmt_predicate not in targets:
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
    xlsx_path: Optional[Path] = None,
    gdb_path: Optional[Path] = None,
    region: str = "xinjiang",
    max_rows: Optional[int] = None,
    gdb_max_rows_per_layer: Optional[int] = None,
    enable_ner: Optional[bool] = None,
    batch_id: Optional[uuid.UUID] = None,
) -> dict:
    batch_id = batch_id or uuid.uuid4()
    if enable_ner is None:
        enable_ner = config.ENABLE_NER

    print(f"[xinjiang] batch_id={batch_id}")
    print(f"[xinjiang] xlsx    ={xlsx_path or '(skipped)'}")
    print(f"[xinjiang] gdb     ={gdb_path or '(skipped)'}")
    print(f"[xinjiang] ner     ={'on' if enable_ner else 'off'}")

    rows: list[StatementRow] = []

    if xlsx_path and Path(xlsx_path).exists():
        rows = xinjiang_conn.ingest_xinjiang_xlsx(xlsx_path, region=region, max_rows=max_rows)
        print(f"[xinjiang] xlsx    -> {len(rows)} statement rows")

    if gdb_path and Path(gdb_path).exists():
        for layer in _HERITAGE_LAYERS:
            layer_rows = shapefile.ingest_vector_layer(
                path=Path(gdb_path),
                layer=layer,
                region=region,
                type_abbr="pl",
                natural_key_cols=["级别", "保护级", "所属县", "文物保"],
                name_col="文物保",
                type_col="类别",
                extra_predicates=_HERITAGE_EXTRA_PREDICATES,
                max_rows=gdb_max_rows_per_layer,
            )
            print(f"[xinjiang] gdb {layer[:18]:<18s} -> {len(layer_rows):>6} statement rows")
            rows.extend(layer_rows)

    if enable_ner:
        ner = _ner_rows(rows)
        print(f"[xinjiang] ner     -> {len(ner)} statement rows")
        rows.extend(ner)

    with db.connect(region) as conn:
        written = staging.write_rows(conn, batch_id, rows)
        print(f"[xinjiang] staged  -> {written} rows in staging.stg_ingest")
    with db.connect(region) as conn:
        rin, rok, rerr = staging.trigger_ingest_batch(conn, batch_id)
        print(f"[xinjiang] ingest_batch: rows_in={rin} rows_ok={rok} rows_err={rerr}")

    return {"batch_id": str(batch_id), "rows_staged": written,
            "rows_in": rin, "rows_ok": rok, "rows_err": rerr}
