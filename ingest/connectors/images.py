"""Image connector — reads a folder of photos, extracts EXIF (incl. GPS), emits
both DigitalImage entity statements and a back-reference to the depicted Place.

Expected NAS layout:
    {NAS_ROOT}/{region}/photos/{place_natural_key}/*.jpg
                                                    *.jpeg
                                                    *.png
                                                    *.tif

The folder name under photos/ IS the natural_key of the Place the photos depict.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Iterator, Optional

from PIL import Image, UnidentifiedImageError

from ..staging import StatementRow


_IMG_EXTS = {".jpg", ".jpeg", ".png", ".tif", ".tiff"}

# EXIF tag IDs we care about (avoids importing the full ExifTags namespace).
_DATETIME_ORIG = 0x9003
_DATETIME      = 0x0132
_MAKE          = 0x010F
_MODEL         = 0x0110
_GPS_IFD       = 0x8825


def _gps_to_decimal(gps_ifd: dict) -> Optional[tuple[float, float]]:
    try:
        lat = gps_ifd[2]; lat_ref = gps_ifd[1]
        lon = gps_ifd[4]; lon_ref = gps_ifd[3]
        lat_dec = float(lat[0]) + float(lat[1])/60 + float(lat[2])/3600
        lon_dec = float(lon[0]) + float(lon[1])/60 + float(lon[2])/3600
        if str(lat_ref).upper() == "S": lat_dec = -lat_dec
        if str(lon_ref).upper() == "W": lon_dec = -lon_dec
        return lat_dec, lon_dec
    except (KeyError, IndexError, TypeError, ValueError, ZeroDivisionError):
        return None


def _parse_exif_dt(s) -> Optional[datetime]:
    if not s: return None
    try:
        return datetime.strptime(str(s).strip(), "%Y:%m:%d %H:%M:%S")
    except (ValueError, TypeError):
        return None


def _walk_photos(photos_root: Path, place_natural_key: str) -> Iterator[Path]:
    base = photos_root / place_natural_key
    if not base.is_dir(): return
    for p in sorted(base.iterdir()):
        if p.is_file() and p.suffix.lower() in _IMG_EXTS:
            yield p


def ingest_photos_for(
    photos_root: Path,
    place_natural_key: str,
    *,
    region: str,
) -> list[StatementRow]:
    rows: list[StatementRow] = []

    for img_path in _walk_photos(photos_root, place_natural_key):
        # natural_key for the DigitalImage entity is its path relative to the
        # region's photo root — stable across re-runs, unique per photo.
        rel = img_path.relative_to(photos_root).as_posix()
        img_nk = f"img:{rel}"
        ev_uri = f"file://{img_path}"

        # Common evidence/entity fields for every statement about this photo.
        common = dict(
            ev_source_uri=ev_uri,
            ev_source_type="image_file",
            ev_metadata={
                "size_bytes":     img_path.stat().st_size,
                "place_natural_key": place_natural_key,
            },
            ent_region=region,
            ent_type_abbr="img",
            ent_temporal="unk",
            ent_natural_key=img_nk,
        )

        rows.append(StatementRow(**common,
            stmt_predicate="hasFileName",
            stmt_value={"value": img_path.name}))
        rows.append(StatementRow(**common,
            stmt_predicate="depicts",
            stmt_value={"ref_natural_key": place_natural_key,
                        "ref_type_abbr": "pl", "ref_region": region}))

        try:
            with Image.open(img_path) as im:
                exif = im.getexif()
        except (UnidentifiedImageError, OSError):
            continue

        dt = _parse_exif_dt(exif.get(_DATETIME_ORIG) or exif.get(_DATETIME))
        if dt:
            rows.append(StatementRow(**common,
                stmt_predicate="capturedAt",
                stmt_value={"iso": dt.isoformat()},
                stmt_valid_from=dt.date(),
                stmt_valid_to=dt.date()))

        make = exif.get(_MAKE); model = exif.get(_MODEL)
        if make or model:
            rows.append(StatementRow(**common,
                stmt_predicate="capturedBy",
                stmt_value={"make": str(make or "").strip() or None,
                            "model": str(model or "").strip() or None}))

        gps_ifd = exif.get_ifd(_GPS_IFD) if hasattr(exif, "get_ifd") else None
        if gps_ifd:
            ll = _gps_to_decimal(gps_ifd)
            if ll:
                lat, lon = ll
                rows.append(StatementRow(**common,
                    stmt_predicate="locatedAt",
                    stmt_value={"wkt": f"POINT({lon} {lat})", "srid": 4326,
                                "source": "exif_gps"}))

    return rows


def discover_place_keys(photos_root: Path) -> list[str]:
    """List all subfolders of photos/, each treated as a Place natural_key."""
    if not photos_root.is_dir(): return []
    return sorted(d.name for d in photos_root.iterdir() if d.is_dir())
