"""Generic vector-layer connector (Shapefile / GDB / GeoJSON / GeoPackage).

Reads ANY vector format that geopandas/pyogrio supports, reprojects geometry
to WGS84 (SRID 4326) to match the `entity_statement.object_geometry` column
constraint, and emits StatementRow instances per feature.

Configurable for any project — the caller specifies which column is the
natural key, which is the name, etc. No project-specific assumptions.

Examples:
    # Mustang heritage polygons (from GDB)
    ingest_vector_layer(
        path="/Volumes/.../1-1MusthangBase.gdb",
        layer="Heritage_Polygon202504",
        region="mustang",
        type_abbr="clu",
        natural_key_col="ID",
        extra_predicates={"Recorder": "hasRecorder", "Date": "hasSurveyDate"},
    )

    # Standalone shapefile with name + type columns
    ingest_vector_layer(
        path="/path/to/sites.shp",
        region="dunhuang",
        type_abbr="pl",
        natural_key_col="site_id",
        name_col="name_zh",
        type_col="category",
    )
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

import geopandas as gpd
import pandas as pd

from ..staging import StatementRow


def _clean(v) -> Optional[str]:
    if v is None: return None
    if isinstance(v, float) and pd.isna(v): return None
    s = str(v).strip()
    return s if s and s.lower() != "nan" else None


def ingest_vector_layer(
    path: str | Path,
    *,
    region: str,
    type_abbr: str,
    natural_key_col: Optional[str] = None,
    natural_key_cols: Optional[list[str]] = None,
    natural_key_separator: str = "|",
    layer: Optional[str] = None,
    name_col: Optional[str] = None,
    type_col: Optional[str] = None,
    temporal: str = "unk",
    extra_predicates: Optional[dict[str, str]] = None,
    max_rows: Optional[int] = None,
) -> list[StatementRow]:
    """Read a vector layer and emit StatementRow list.

    Args:
        path: shapefile path, GDB folder path, or any OGR-readable source.
        layer: layer name when reading from a GDB or multi-layer file.
        region: CLKG region (e.g. 'mustang').
        type_abbr: CL-Onto type to assign each feature (e.g. 'clu' or 'pl').
        natural_key_col: single column whose value becomes ent_natural_key.
        natural_key_cols: list of columns joined by `natural_key_separator`
            to form a composite ent_natural_key (use when no single column is
            unique). Mutually exclusive with natural_key_col.
        natural_key_separator: separator joining natural_key_cols (default '|').
        name_col: optional column whose value becomes a hasName statement.
        type_col: optional column whose value becomes a hasType statement.
        temporal: ent_temporal segment for the PID (default 'unk').
        extra_predicates: {column_name: predicate_name} for additional
            attribute → statement mappings. Columns absent in this layer are
            silently skipped (lets one config serve multiple similar layers).
        max_rows: limit rows for testing.

    Returns:
        list[StatementRow]
    """
    if not natural_key_col and not natural_key_cols:
        raise ValueError("must supply natural_key_col or natural_key_cols")
    gdf = gpd.read_file(path, layer=layer, rows=max_rows)
    if gdf.crs is None:
        # Without a CRS we can't reproject. Assume WGS84 already.
        pass
    elif gdf.crs.to_epsg() != 4326:
        gdf = gdf.to_crs(epsg=4326)

    extra_predicates = extra_predicates or {}
    path_str = str(path)
    ev_uri_base = f"file://{path_str}" + (f"#layer={layer}" if layer else "")

    rows: list[StatementRow] = []

    for idx, r in gdf.iterrows():
        if natural_key_cols:
            parts = [_clean(r.get(c)) or "" for c in natural_key_cols]
            nk = natural_key_separator.join(parts).strip(natural_key_separator)
            if not any(parts):
                continue
        else:
            nk = _clean(r.get(natural_key_col))
            if not nk:
                continue

        geom = r.geometry
        wkt = geom.wkt if (geom is not None and not geom.is_empty) else None

        # Build evidence metadata from all non-geometry columns
        ev_meta = {}
        for c in gdf.columns:
            if c == gdf.geometry.name:
                continue
            v = _clean(r[c])
            if v is not None:
                ev_meta[c] = v

        common = dict(
            ev_source_uri=f"{ev_uri_base}&row={idx}",
            ev_source_type="vector_feature",
            ev_metadata=ev_meta,
            ent_region=region,
            ent_type_abbr=type_abbr,
            ent_temporal=temporal,
            ent_natural_key=nk,
        )

        if name_col and (v := _clean(r.get(name_col))):
            rows.append(StatementRow(**common, stmt_predicate="hasName",
                                     stmt_value={"value": v}))

        if type_col and (v := _clean(r.get(type_col))):
            rows.append(StatementRow(**common, stmt_predicate="hasType",
                                     stmt_value={"value": v}))

        if wkt:
            rows.append(StatementRow(**common, stmt_predicate="locatedAt",
                                     stmt_value={"wkt": wkt, "srid": 4326,
                                                 "source": "vector_feature"}))

        for col, pred in extra_predicates.items():
            if (v := _clean(r.get(col))):
                rows.append(StatementRow(**common, stmt_predicate=pred,
                                         stmt_value={"value": v}))

    return rows


def list_layers(path: str | Path) -> list[str]:
    """List all layer names in a multi-layer source (e.g. GDB)."""
    import fiona
    return fiona.listlayers(str(path))
