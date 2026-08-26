"""Mustang multimodal pipeline: tabular CSV + photo folders + (optional) NER."""
from __future__ import annotations

import logging
import uuid
from pathlib import Path
from typing import Optional

from .. import config, db, spatial, staging
from ..connectors import images, photo_table, shapefile, tabular
from ..extractors import qwen_ner
from ..staging import StatementRow

log = logging.getLogger(__name__)


def _ner_rows_from_descriptions(rows: list[StatementRow]) -> list[StatementRow]:
    """For each hasDescription statement, run Qwen NER and emit `mentions*`
    statements on the SAME source entity. NER hits are not promoted to new
    entities here — that's a curation step for a later pipeline."""
    out: list[StatementRow] = []
    for r in rows:
        if r.stmt_predicate != "hasDescription":
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
    csv_path: Path,
    photos_root: Optional[Path] = None,
    photo_table_path: Optional[Path] = None,
    polygon_gdb_path: Optional[Path] = None,
    polygon_layer: Optional[str] = None,
    region: str = "mustang",
    max_rows: Optional[int] = None,
    photo_max_rows: Optional[int] = None,
    polygon_max_rows: Optional[int] = None,
    enable_ner: Optional[bool] = None,
    batch_id: Optional[uuid.UUID] = None,
    link_spatial: bool = True,
) -> dict:
    batch_id = batch_id or uuid.uuid4()
    if enable_ner is None:
        enable_ner = config.ENABLE_NER

    print(f"[mustang] batch_id={batch_id}")
    print(f"[mustang] csv         ={csv_path}")
    print(f"[mustang] photos_root ={photos_root or '(skipped)'}")
    print(f"[mustang] photo_table ={photo_table_path or '(skipped)'}")
    print(f"[mustang] ner         ={'on' if enable_ner else 'off'}")

    # 1. Tabular (heritage points CSV) -----------------------------------------
    rows = tabular.ingest_mustang_csv(csv_path, region=region, max_rows=max_rows)
    print(f"[mustang] tabular     -> {len(rows)} statement rows")

    # 2a. Photos via EXIF folder layout -----------------------------------------
    if photos_root and photos_root.is_dir():
        place_keys = sorted({r.ent_natural_key for r in rows if r.ent_type_abbr == "pl"})
        photo_rows: list[StatementRow] = []
        for nk in place_keys:
            photo_rows.extend(images.ingest_photos_for(photos_root, nk, region=region))
        csv_keys = set(place_keys)
        for nk in images.discover_place_keys(photos_root):
            if nk not in csv_keys:
                photo_rows.extend(images.ingest_photos_for(photos_root, nk, region=region))
        print(f"[mustang] photos_exif -> {len(photo_rows)} statement rows")
        rows.extend(photo_rows)

    # 2b. Photos via metadata table (preferred when GPS/EXIF already extracted)
    if photo_table_path and Path(photo_table_path).is_file():
        ptable_rows = photo_table.ingest_photo_table(
            Path(photo_table_path), region=region, max_rows=photo_max_rows,
        )
        print(f"[mustang] photo_table -> {len(ptable_rows)} statement rows")
        rows.extend(ptable_rows)

    # 2c. Polygon CLU entities (from a GDB layer or shapefile) -----------------
    if polygon_gdb_path:
        poly_rows = shapefile.ingest_vector_layer(
            path=Path(polygon_gdb_path),
            layer=polygon_layer,
            region=region,
            type_abbr="clu",
            natural_key_col="ID",
            max_rows=polygon_max_rows,
            extra_predicates={
                "Recorder":     "hasRecorder",
                "Date":         "hasSurveyDate",
                "Q":            "hasQualityFlag",
                "Note":         "hasNote",
                "Shape_Area":   "hasShapeArea",
                "Shape_Length": "hasShapeLength",
            },
        )
        print(f"[mustang] polygons    -> {len(poly_rows)} statement rows "
              f"(layer={polygon_layer or 'default'})")
        rows.extend(poly_rows)

    # 3. NER on free-text descriptions -----------------------------------------
    if enable_ner:
        ner_rows = _ner_rows_from_descriptions(rows)
        print(f"[mustang] ner     -> {len(ner_rows)} statement rows")
        rows.extend(ner_rows)

    # 4. Write staging (commit) THEN promote to business tables ---------------
    # Two transactions so staging data survives for inspection if ingest_batch fails.
    with db.connect(region) as conn:
        written = staging.write_rows(conn, batch_id, rows)
        print(f"[mustang] staged      -> {written} rows in staging.stg_ingest")
    with db.connect(region) as conn:
        rin, rok, rerr = staging.trigger_ingest_batch(conn, batch_id)
        print(f"[mustang] ingest_batch: rows_in={rin} rows_ok={rok} rows_err={rerr}")

    # 5. Spatial inference: derive containsPlace from polygon→point geometry --
    if link_spatial:
        n_contains = spatial.link_contains_place(region)
        print(f"[mustang] containsPlace -> {n_contains} new statements (clu→pl)")

    return {
        "batch_id":      str(batch_id),
        "rows_staged":   written,
        "rows_in":       rin,
        "rows_ok":       rok,
        "rows_err":      rerr,
        "contains_new":  n_contains if link_spatial else None,
    }
