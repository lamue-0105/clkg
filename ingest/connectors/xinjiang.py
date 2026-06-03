"""Xinjiang Third National Heritage Survey (三普) xlsx connector.

Expected source: `《不可移动的文物》古遗址三普信息表_新疆全部地区_已编码.xlsx`
3027 rows × 17 columns, all-text Chinese; no coordinates (geocoding is future
work). The 简介 / 备注 / 环境状况 fields are NER-rich — point Qwen at them
when API key arrives.

Each row → 1 Place entity (type_abbr='pl') with rich descriptive statements.

Field mapping:
    site_id      → ent_natural_key (e.g. 'GY652825001')
    名称          → hasName
    位置 / 地址及位置 → hasAddress
    年代          → hasEra (text — many era ranges; parsing left for future)
    区域          → hasPrefecture
    县市          → hasCounty
    数字码        → hasAdminCode (GB/T 2260 6-digit code)
    备注1         → hasSurveyType ('新发现' or '复查')
    环境状况      → hasEnvironment
    简介          → hasDescription
    保存状况      → hasPreservationState
    备注2         → hasSurveyHistory
    参考书目      → hasReference
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

import pandas as pd

from ..staging import StatementRow


REGION_DEFAULT = "xinjiang"


_FIELD_TO_PREDICATE = {
    # text predicates → free-form value
    "名称":        "hasName",
    "年代":        "hasEra",
    "区域":        "hasPrefecture",
    "县市":        "hasCounty",
    "数字码":      "hasAdminCode",
    "备注1":       "hasSurveyType",
    "环境状况":    "hasEnvironment",
    "简介":        "hasDescription",
    "保存状况":    "hasPreservationState",
    "备注2":       "hasSurveyHistory",
    "参考书目":    "hasReference",
}


def _clean(v: Any) -> Optional[str]:
    if v is None: return None
    if isinstance(v, float) and pd.isna(v): return None
    s = str(v).strip()
    return s if s and s.lower() != "nan" else None


def ingest_xinjiang_xlsx(
    xlsx_path: Path,
    *,
    region: str = REGION_DEFAULT,
    max_rows: Optional[int] = None,
) -> list[StatementRow]:
    df = pd.read_excel(xlsx_path, nrows=max_rows)
    rows: list[StatementRow] = []
    ev_uri_base = f"file://{xlsx_path}"

    for idx, r in df.iterrows():
        nk = _clean(r.get("site_id"))
        if not nk:
            continue

        ev_meta = {
            "id":           _clean(r.get("id")),
            "序号":          _clean(r.get("序号")),
            "序号_无重复":   _clean(r.get("序号_无重复")),
            "数字码":        _clean(r.get("数字码")),
        }
        ev_meta = {k: v for k, v in ev_meta.items() if v is not None}

        common = dict(
            ev_source_uri=f"{ev_uri_base}#site_id={nk}",
            ev_source_type="xlsx_row",
            ev_metadata=ev_meta,
            ent_region=region,
            ent_type_abbr="pl",
            ent_temporal="unk",
            ent_natural_key=nk,
        )

        # Address: prefer the more detailed '地址及位置' over short '位置'.
        addr = _clean(r.get("地址及位置")) or _clean(r.get("位置"))
        if addr:
            rows.append(StatementRow(**common, stmt_predicate="hasAddress",
                                     stmt_value={"value": addr}))

        # Generic field mapping
        for col, pred in _FIELD_TO_PREDICATE.items():
            v = _clean(r.get(col))
            if v is not None:
                rows.append(StatementRow(**common, stmt_predicate=pred,
                                         stmt_value={"value": v}))

    return rows
