"""Photo-metadata-table connector.

Input: a CSV (GBK-encoded ArcGIS export) with one row per photo and pre-extracted
GPS / capture time. Used when the user has already done EXIF extraction +
geocoding in ArcGIS Pro and exported a tidy table — no need to read EXIF
from JPG/HEIC files ourselves.

Expected columns (from 木斯塘 重命名1.csv):
  OBJECTID, FileName, FileType, FileSize, CaptureTime,
  Latitude (text like "29.23 N"),  Longitude (text),
  Latitude_D (decimal),             Longitude_D (decimal),
  Altitude, SourcePath, ProcessingStatus

The actual image files may live anywhere (or nowhere yet on this machine).
We store SourcePath as-is; the PG row reflects metadata only. When you later
migrate the files, just update SourcePath; PIDs / linkage stay stable.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Optional

import pandas as pd

from ..staging import StatementRow


def _try_csv(path: Path, **kw) -> pd.DataFrame:
    """Open the CSV with the right encoding (these ArcGIS exports are GBK)."""
    for enc in ("gbk", "gb18030", "utf-8-sig", "utf-8"):
        try:
            return pd.read_csv(path, encoding=enc, **kw)
        except UnicodeDecodeError:
            continue
    raise RuntimeError(f"could not decode {path}; tried gbk/gb18030/utf-8")


def _parse_capture_time(v) -> Optional[datetime]:
    if pd.isna(v): return None
    for fmt in ("%Y/%m/%d %H:%M:%S", "%Y/%m/%d %H:%M", "%Y-%m-%d %H:%M:%S",
                "%Y-%m-%d %H:%M", "%Y/%m/%d", "%Y-%m-%d"):
        try:
            return datetime.strptime(str(v).strip(), fmt)
        except ValueError:
            continue
    return None


def ingest_photo_table(
    csv_path: Path,
    *,
    region: str = "mustang",
    max_rows: Optional[int] = None,
) -> list[StatementRow]:
    df = _try_csv(csv_path, nrows=max_rows)
    rows: list[StatementRow] = []

    for _, r in df.iterrows():
        try:
            obj_id = int(r["OBJECTID"])
        except (ValueError, TypeError):
            continue

        filename = str(r.get("FileName", "")).strip() or f"unknown_{obj_id}"
        nk = f"photo:{obj_id:05d}"   # stable id from the photo table
        ev_uri = f"file://{csv_path}#OBJECTID={obj_id}"

        ev_meta = {
            "objectid":          obj_id,
            "filename":          filename,
            "source_path":       str(r.get("SourcePath", "")).strip() or None,
            "file_size":         str(r.get("FileSize", "")).strip() or None,
            "processing_status": str(r.get("ProcessingStatus", "")).strip() or None,
        }

        common = dict(
            ev_source_uri=ev_uri,
            ev_source_type="photo_metadata_row",
            ev_metadata=ev_meta,
            ent_region=region,
            ent_type_abbr="img",
            ent_temporal="2024",   # this CSV is from the 2024 field expedition
            ent_natural_key=nk,
        )

        # ---- basic file attributes
        rows.append(StatementRow(**common, stmt_predicate="hasFileName",
                                 stmt_value={"value": filename}))

        if pd.notna(r.get("FileType")):
            rows.append(StatementRow(**common, stmt_predicate="hasFileType",
                                     stmt_value={"value": str(r["FileType"]).strip()}))

        if pd.notna(r.get("SourcePath")):
            rows.append(StatementRow(**common, stmt_predicate="hasFilePath",
                                     stmt_value={"value": str(r["SourcePath"]).strip()}))

        if pd.notna(r.get("FileSize")):
            rows.append(StatementRow(**common, stmt_predicate="hasFileSize",
                                     stmt_value={"value": str(r["FileSize"]).strip()}))

        # ---- capture time
        dt = _parse_capture_time(r.get("CaptureTime"))
        if dt:
            rows.append(StatementRow(**common, stmt_predicate="capturedAt",
                                     stmt_value={"iso": dt.isoformat()},
                                     stmt_valid_from=dt.date(),
                                     stmt_valid_to=dt.date()))

        # ---- location (POINT in WGS84 — already decimal in this dataset)
        lat = r.get("Latitude_D"); lon = r.get("Longitude_D")
        if pd.notna(lat) and pd.notna(lon):
            try:
                flat, flon = float(lat), float(lon)
                if -90 <= flat <= 90 and -180 <= flon <= 180:
                    rows.append(StatementRow(**common, stmt_predicate="locatedAt",
                        stmt_value={
                            "wkt":    f"POINT({flon} {flat})",
                            "srid":   4326,
                            "source": "photo_metadata_gps",
                        }))
            except (ValueError, TypeError):
                pass

        # ---- altitude (often NaN in this dataset, but capture if present)
        alt = r.get("Altitude")
        if pd.notna(alt):
            try:
                rows.append(StatementRow(**common, stmt_predicate="hasAltitude",
                                         stmt_value={"meters": float(alt)}))
            except (ValueError, TypeError):
                pass

    return rows
