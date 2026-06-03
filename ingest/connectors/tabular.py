"""Tabular connectors — read CSV/XLSX and emit StatementRow lists."""
from __future__ import annotations

from pathlib import Path
from typing import Optional

import pandas as pd

from ..staging import StatementRow


_MUSTANG_GIS_SRID = 32644  # UTM zone 44N — covers 78°E-84°E, central meridian 81°E.
                           # Mustang (Nepal, ~83.5°E) sits in zone 44, not 45.


def _meta_from_row(row: pd.Series, cols: list[str]) -> dict:
    return {
        col: (str(row[col]).strip() if pd.notna(row[col]) else None)
        for col in cols if col in row.index
    }


def ingest_mustang_csv(
    csv_path: Path,
    *,
    region: str = "mustang",
    max_rows: Optional[int] = None,
) -> list[StatementRow]:
    """Parse a Mustang heritage-survey CSV into Place statements."""
    df = pd.read_csv(csv_path, nrows=max_rows)
    rows: list[StatementRow] = []
    ev_uri_base = f"file://{csv_path}"
    meta_cols = ["DataSource", "Surveyor", "Recorder", "Literature", "Note"]

    for _, r in df.iterrows():
        obj_id = int(r["OBJECTID"]) if pd.notna(r["OBJECTID"]) else None
        nk = str(r["ID"]).strip() if pd.notna(r["ID"]) else ""
        if not nk or obj_id is None:
            continue

        # CL-Onto type dispatch: Layer = 群体/区域 → CulturalLandscapeUnit (clu).
        # Layer = 单体 (or missing) → atomic Place (pl). Per the Mustang schema doc:
        #   单体 = single point, 群体 = multi-same-type, 区域 = multi-different-types
        layer_val = str(r["Layer"]).strip() if pd.notna(r.get("Layer")) else ""
        type_abbr = "clu" if layer_val in ("群体", "区域") else "pl"

        common = dict(
            ev_source_uri=f"{ev_uri_base}#OBJECTID={obj_id}",
            ev_source_type="csv_row",
            ev_metadata=_meta_from_row(r, meta_cols),
            ent_region=region,
            ent_type_abbr=type_abbr,
            ent_temporal="unk",
            ent_natural_key=nk,
        )

        if pd.notna(r.get("Name")) and str(r["Name"]).strip():
            rows.append(StatementRow(**common,
                stmt_predicate="hasName",
                stmt_value={"value": str(r["Name"]).strip()}))
        if pd.notna(r.get("Type")) and str(r["Type"]).strip():
            rows.append(StatementRow(**common,
                stmt_predicate="hasType",
                stmt_value={"value": str(r["Type"]).strip()}))
        if pd.notna(r.get("POINT_X")) and pd.notna(r.get("POINT_Y")):
            rows.append(StatementRow(**common,
                stmt_predicate="locatedAt",
                stmt_value={
                    "wkt":  f"POINT({float(r['POINT_X'])} {float(r['POINT_Y'])})",
                    "z":    float(r["POINT_Z"]) if pd.notna(r.get("POINT_Z")) else None,
                    "srid": _MUSTANG_GIS_SRID,
                }))
        if pd.notna(r.get("Describe")) and str(r["Describe"]).strip():
            rows.append(StatementRow(**common,
                stmt_predicate="hasDescription",
                stmt_value={"value": str(r["Describe"]).strip()}))

        # Layer — encodes spatial-grouping kind per the Mustang schema doc:
        # 单体 (single) / 群体 (multi-of-same-type) / 区域 (multi-of-different-types).
        if pd.notna(r.get("Layer")) and str(r["Layer"]).strip():
            rows.append(StatementRow(**common,
                stmt_predicate="hasLayer",
                stmt_value={"value": str(r["Layer"]).strip()}))

        # Date — survey/recording date of this heritage point (per schema doc).
        if pd.notna(r.get("Date")) and str(r["Date"]).strip():
            rows.append(StatementRow(**common,
                stmt_predicate="hasSurveyDate",
                stmt_value={"value": str(r["Date"]).strip()}))

    return rows
