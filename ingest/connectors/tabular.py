"""Tabular connectors — read CSV/XLSX and emit StatementRow lists."""
from __future__ import annotations

from pathlib import Path
from typing import Optional

import geopandas as gpd
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


# Historical clu-vs-pl base rates by `Type`, computed from the 399 existing
# point-geometry Mustang entities ingested via ingest_mustang_csv() above
# (222 clu / 177 pl, as of 2026-08-22 — see ingest audit in project notes).
# Used as a fallback ONLY when `Layer` is missing or non-standard. Rates near
# 0.5 reflect genuine historical inconsistency in how that Type was labeled
# (寺庙/疑点), not a gap in this lookup — those rows get flagged low-confidence
# rather than silently guessed.
_TYPE_CLU_RATE: dict[str, float] = {
    "聚落": 1.00, "农田": 1.00, "洞穴": 1.00, "佛塔群": 1.00,
    "洞穴寺庙": 0.33,
    "寺庙": 0.53, "寺院": 0.53,  # 寺院 treated as a synonym of 寺庙
    "疑点": 0.52,
    "玛尼墙": 0.15, "佛塔": 0.16,
    "堡垒": 0.04, "高程点": 0.00, "高程": 0.00, "王宫": 0.00,
}
_LOW_CONFIDENCE_BAND = (0.4, 0.6)

# Data-entry errors found specifically in point2026.shp's Layer column,
# resolved by reading each row's Name/Describe text (see conversation
# record 2026-08-22):
#   '建准' -> Describe "寺院对面的一大片洞穴" (a large cave area)      -> clu
#   '佛塔' -> Describe "两个佛塔底座" (two pagoda bases)               -> pl
#   '聚落' -> Name "...Chorten Group"                                 -> clu
#   '0'    -> Describe "建筑单体..." (explicitly "single unit")       -> pl
_POINT2026_LAYER_TYPO_OVERRIDE: dict[str, str] = {
    "建准": "clu", "佛塔": "pl", "聚落": "clu", "0": "pl",
}


def ingest_mustang_point2026_shp(
    shp_path: Path,
    *,
    region: str = "mustang",
    max_rows: Optional[int] = None,
) -> list[StatementRow]:
    """Parse the 2026-07-21 Mustang point survey (point2026.shp, 420 features).

    All features are Point geometry (no polygons) — this batch cannot supply
    the clu side of ST_Contains spatial inference on its own; its pl-side
    points can still produce NEW containsPlace statements against the
    already-ingested clu polygons once spatial.link_contains_place() re-runs.

    Type dispatch, in priority order:
      1. Layer='单体' -> pl; Layer in ('区域','群体','建筑群') -> clu.
         (建筑群 is a value not in the original 3-way schema doc; treated as
         an aggregation like 群体 under the same single-vs-multi logic.)
      2. Layer='高程' -> pl (Type is uniformly '高程' for these rows, matching
         the historical '高程点' category, which was 100% pl).
      3. Layer='质心' -> pl (these are real field-recorded features with
         actual content, not GIS-computed polygon centroids, despite the
         label — see conversation record).
      4. A few rows have a Layer value that's a data-entry error, not one of
         the above — resolved individually via _POINT2026_LAYER_TYPO_OVERRIDE.
      5. Otherwise (Layer missing/blank): look up Type in _TYPE_CLU_RATE and
         take the historical majority class. Rates inside _LOW_CONFIDENCE_BAND,
         or Types absent from the table entirely, default to pl (the safer,
         atomic assumption) and get an extra hasQualityFlag statement so they
         surface in the validation dashboard for manual review.
    """
    gdf = gpd.read_file(shp_path, rows=max_rows)
    if gdf.crs and gdf.crs.to_epsg() != 4326:
        gdf = gdf.to_crs(epsg=4326)

    import math

    rows: list[StatementRow] = []
    skipped: list[str] = []
    ev_uri_base = f"file://{shp_path}"
    meta_cols = ["DataSource", "Surveyor", "Recorder", "Literature", "UNIT_NAME", "Note"]

    for idx, r in gdf.iterrows():
        final_id = str(r["final_ID"]).strip() if pd.notna(r.get("final_ID")) else ""
        id_val = str(r["ID"]).strip() if pd.notna(r.get("ID")) else ""
        nk = final_id or id_val or f"point2026-row{idx}"

        geom = r.geometry
        if geom is None or geom.is_empty or not (math.isfinite(geom.x) and math.isfinite(geom.y)):
            skipped.append(nk)
            continue

        layer_val = str(r["Layer"]).strip() if pd.notna(r.get("Layer")) else ""
        type_val = str(r["Type"]).strip() if pd.notna(r.get("Type")) else ""

        low_confidence = False
        if layer_val == "单体":
            type_abbr = "pl"
        elif layer_val in ("区域", "群体", "建筑群"):
            type_abbr = "clu"
        elif layer_val == "高程":
            type_abbr = "pl"
        elif layer_val == "质心":
            type_abbr = "pl"
        elif layer_val in _POINT2026_LAYER_TYPO_OVERRIDE:
            type_abbr = _POINT2026_LAYER_TYPO_OVERRIDE[layer_val]
        elif type_val in _TYPE_CLU_RATE:
            rate = _TYPE_CLU_RATE[type_val]
            type_abbr = "clu" if rate > 0.5 else "pl"
            if _LOW_CONFIDENCE_BAND[0] <= rate <= _LOW_CONFIDENCE_BAND[1]:
                low_confidence = True
        else:
            type_abbr = "pl"
            low_confidence = True  # no Layer signal, no Type precedent either

        common = dict(
            ev_source_uri=f"{ev_uri_base}#row={idx}",
            ev_source_type="vector_feature",
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
        if type_val:
            rows.append(StatementRow(**common,
                stmt_predicate="hasType", stmt_value={"value": type_val}))
        if layer_val:
            rows.append(StatementRow(**common,
                stmt_predicate="hasLayer", stmt_value={"value": layer_val}))
        if pd.notna(r.get("Describe")) and str(r["Describe"]).strip():
            rows.append(StatementRow(**common,
                stmt_predicate="hasDescription",
                stmt_value={"value": str(r["Describe"]).strip()}))
        if pd.notna(r.get("Date")) and str(r["Date"]).strip():
            rows.append(StatementRow(**common,
                stmt_predicate="hasSurveyDate",
                stmt_value={"value": str(r["Date"]).strip()}))

        # Real field-measured elevation lives in the `height` attribute column
        # (metres a.s.l., e.g. ~3700-3800 for the 高程 points) — NOT in the
        # geometry's Z coordinate, which is a meaningless constant 0 across
        # the whole file (confirmed by inspection; the two rows with a non-zero
        # Z are the two corrupt/coordinate-less rows skipped above, not real
        # elevation readings). height==0 means "not recorded", not sea level.
        if pd.notna(r.get("height")) and float(r["height"]) != 0:
            rows.append(StatementRow(**common,
                stmt_predicate="hasElevation",
                stmt_value={"value": float(r["height"])}))

        # entity_statement.object_geometry is a 2D column, so the geometry
        # itself is stored without Z (which is a meaningless constant 0 here
        # anyway) — real elevation is captured above via hasElevation instead.
        wkt = f"POINT ({geom.x} {geom.y})"
        rows.append(StatementRow(**common,
            stmt_predicate="locatedAt",
            stmt_value={"wkt": wkt, "srid": 4326, "source": "vector_feature"}))

        if low_confidence:
            rows.append(StatementRow(**common,
                stmt_predicate="hasQualityFlag",
                stmt_value={"value": "clu/pl分类置信度低(历史同类Type分布接近五五开或无先例)，建议人工复核"}))

    return rows
