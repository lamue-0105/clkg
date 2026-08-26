"""Qiaopi (overseas Chinese remittance letter) xlsx connector.

Expected source: qiaopi_geocoded_hybrid.xlsx (36 cols incl. lat/lon).
Each row → up to 5 entities (Document + Sender + Recipient + Origin + Dest)
and a fan of statements linking them.

CAVEAT — coordinate system: the lat/lon columns appear to come from Gaode
(Amap) geocoding which uses GCJ-02, not WGS-84. This adds 50-500m offset for
points inside China. v1 stores them as if they were WGS84; downstream
high-precision spatial work should add a GCJ-02 → WGS-84 conversion step.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

import pandas as pd

from ..staging import StatementRow

REGION_DEFAULT = "qiaopi"


def _clean(v: Any) -> Optional[str]:
    if v is None: return None
    if isinstance(v, float) and pd.isna(v): return None
    s = str(v).strip()
    return s if s and s.lower() != "nan" else None


def _first_non_empty(*vals) -> Optional[str]:
    for v in vals:
        c = _clean(v)
        if c:
            return c
    return None


def _meta(r: pd.Series) -> dict:
    keep = {
        "uploader":         _clean(r.get("uploader")),
        "upload_time":      _clean(r.get("uploadTime")),
        "uploader_mobile":  _clean(r.get("uploaderMobile")),
        "uploader_email":   _clean(r.get("uploaderEmail")),
        "progress":         _clean(r.get("progress")),
        "office":           _clean(r.get("office")),
        "letter_number":    _clean(r.get("letterNumber")),
        "collect_location": _clean(r.get("collectLocation")),
    }
    return {k: v for k, v in keep.items() if v is not None}


def ingest_qiaopi_xlsx(
    xlsx_path: Path,
    *,
    region: str = REGION_DEFAULT,
    max_rows: Optional[int] = None,
) -> list[StatementRow]:
    df = pd.read_excel(xlsx_path, nrows=max_rows)
    out: list[StatementRow] = []
    ev_uri_base = f"file://{xlsx_path}"

    for _, r in df.iterrows():
        rid  = int(r["id"]) if pd.notna(r["id"]) else None
        coll = _clean(r.get("collectNumber"))
        if rid is None or not coll:
            continue

        ev_uri = f"{ev_uri_base}#id={rid}"
        ev_meta = _meta(r)

        # ====================================================================
        # 1. Document entity (the qiaopi letter itself)
        # Invariant: every StatementRow with the same ev_source_uri uses the
        # IDENTICAL ev_metadata dict — evidence describes the source, not the
        # entity, so per-entity metadata variations break dedup in ingest_batch.
        # ====================================================================
        doc = dict(
            ev_source_uri=ev_uri, ev_source_type="xlsx_row",
            ev_metadata=ev_meta,
            ent_region=region, ent_type_abbr="doc",
            ent_temporal="modern",   # qiaopi span late-19c through 20c
            ent_natural_key=coll,    # collectNumber is globally unique
        )

        # Title (Chinese: e.g. "陈妙清寄广东潮安张光昭侨批")
        if (v := _clean(r.get("title"))):
            out.append(StatementRow(**doc, stmt_predicate="hasTitle",
                                    stmt_value={"value": v}))

        out.append(StatementRow(**doc, stmt_predicate="hasCollectionNumber",
                                stmt_value={"value": coll}))

        # Dates — stored as text (formats vary, e.g. era dates like 民国28年).
        for col, pred in [("shownDate", "hasShownDate"),
                          ("formalDate", "hasFormalDate"),
                          ("replyDate",  "hasReplyDate")]:
            if (v := _clean(r.get(col))):
                out.append(StatementRow(**doc, stmt_predicate=pred,
                                        stmt_value={"value": v}))

        # Amount + currency
        if (v := _clean(r.get("currencyType"))):
            out.append(StatementRow(**doc, stmt_predicate="hasCurrency",
                                    stmt_value={"value": v}))
        for col, pred in [("moneyAmount", "hasAmount"),
                          ("paidAmount",  "hasPaidAmount"),
                          ("convertedAmount", "hasConvertedAmount")]:
            if (v := _clean(r.get(col))):
                out.append(StatementRow(**doc, stmt_predicate=pred,
                                        stmt_value={"value": v}))

        # Inner letter — IF actually digitized as text. The qiaopi_geocoded_hybrid
        # dataset uses a 1/0 flag here (not the actual letter body), so we skip
        # short values to avoid filling staging with meaningless flags.
        if (v := _clean(r.get("innerLetter"))) and len(v) > 3:
            out.append(StatementRow(**doc, stmt_predicate="hasInnerLetter",
                                    stmt_value={"value": v}))

        # Notes
        if (v := _clean(r.get("notes"))):
            out.append(StatementRow(**doc, stmt_predicate="hasNotes",
                                    stmt_value={"value": v}))

        # ====================================================================
        # 2. Sender (Actor) — natural key = name
        # ====================================================================
        if (sender_nk := _clean(r.get("sender"))):
            sender = dict(
                ev_source_uri=ev_uri, ev_source_type="xlsx_row",
                ev_metadata=ev_meta,
                ent_region=region, ent_type_abbr="ac",
                ent_temporal="modern",
                ent_natural_key=sender_nk,
            )
            out.append(StatementRow(**sender, stmt_predicate="hasName",
                                    stmt_value={"value": sender_nk}))
            # Document → Sender
            out.append(StatementRow(**doc, stmt_predicate="hasSender",
                stmt_value={"ref_natural_key": sender_nk,
                            "ref_type_abbr": "ac", "ref_region": region}))

        # ====================================================================
        # 3. Recipient (Actor)
        # ====================================================================
        if (rec_nk := _clean(r.get("recver"))):
            rec = dict(
                ev_source_uri=ev_uri, ev_source_type="xlsx_row",
                ev_metadata=ev_meta,
                ent_region=region, ent_type_abbr="ac",
                ent_temporal="modern",
                ent_natural_key=rec_nk,
            )
            out.append(StatementRow(**rec, stmt_predicate="hasName",
                                    stmt_value={"value": rec_nk}))
            out.append(StatementRow(**doc, stmt_predicate="hasRecipient",
                stmt_value={"ref_natural_key": rec_nk,
                            "ref_type_abbr": "ac", "ref_region": region}))

        # ====================================================================
        # 4. Origin Place — overseas sending location (usually no lat/lon)
        # ====================================================================
        origin_name = _first_non_empty(
            r.get("sendLocation"), r.get("sendArea"), r.get("sendCountry"))
        if origin_name:
            origin = dict(
                ev_source_uri=ev_uri, ev_source_type="xlsx_row",
                ev_metadata=ev_meta,
                ent_region=region, ent_type_abbr="pl",
                ent_temporal="unk",
                ent_natural_key=origin_name,
            )
            out.append(StatementRow(**origin, stmt_predicate="hasName",
                                    stmt_value={"value": origin_name}))
            # Hierarchical context if available
            for col, pred in [("sendCountry", "hasCountry"),
                              ("sendArea", "hasArea"),
                              ("sendLocation", "hasLocation")]:
                if (v := _clean(r.get(col))) and v != origin_name:
                    out.append(StatementRow(**origin, stmt_predicate=pred,
                                            stmt_value={"value": v}))
            out.append(StatementRow(**doc, stmt_predicate="hasOriginPlace",
                stmt_value={"ref_natural_key": origin_name,
                            "ref_type_abbr": "pl", "ref_region": region}))

        # ====================================================================
        # 5. Destination Place — recipient's location (has lat/lon!)
        # ====================================================================
        dest_name = _first_non_empty(
            r.get("recvTown_std"), r.get("recvTown"),
            r.get("recvVillage"), r.get("recvDistrict"),
            r.get("recvLocation"))
        if dest_name:
            dest = dict(
                ev_source_uri=ev_uri, ev_source_type="xlsx_row",
                ev_metadata=ev_meta,
                ent_region=region, ent_type_abbr="pl",
                ent_temporal="unk",
                ent_natural_key=dest_name,
            )
            out.append(StatementRow(**dest, stmt_predicate="hasName",
                                    stmt_value={"value": dest_name}))
            # Hierarchical decomposition
            for col, pred in [("recvDistrict", "hasDistrict"),
                              ("recvTown",     "hasTown"),
                              ("recvVillage",  "hasVillage")]:
                if (v := _clean(r.get(col))) and v != dest_name:
                    out.append(StatementRow(**dest, stmt_predicate=pred,
                                            stmt_value={"value": v}))
            # Geographic coordinates (Gaode geocoded — see CAVEAT at top of file)
            lat = r.get("lat"); lon = r.get("lon")
            if pd.notna(lat) and pd.notna(lon):
                try:
                    flat, flon = float(lat), float(lon)
                    if -90 <= flat <= 90 and -180 <= flon <= 180:
                        out.append(StatementRow(**dest, stmt_predicate="locatedAt",
                            stmt_value={
                                "wkt":    f"POINT({flon} {flat})",
                                "srid":   4326,
                                "source": "gaode_geocoded",
                            }))
                except (ValueError, TypeError):
                    pass
            out.append(StatementRow(**doc, stmt_predicate="hasDestinationPlace",
                stmt_value={"ref_natural_key": dest_name,
                            "ref_type_abbr": "pl", "ref_region": region}))

    return out
