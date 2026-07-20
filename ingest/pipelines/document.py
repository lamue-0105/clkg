"""Document pipeline — L1: register a long-form source and survey its passages.

What this does today: mints the ``doc`` entity from bibliographic metadata and
reports what the passage stream looks like. What it deliberately does NOT do:
write passage text into the database. For in-copyright sources the KG stores
extracted facts plus a page locator; the text stays in the local passage cache.

Fact extraction from passages (L2) and binding those facts to existing pl/clu
entities (L3) are separate stages. This one exists so that when they land, the
document they hang off is already in the graph with a stable PID.

    python -m ingest.cli document <path> --region mustang            # probe only
    python -m ingest.cli document <path> --region mustang --ingest   # + write doc
"""
from __future__ import annotations

import json
import logging
import uuid
from pathlib import Path
from typing import Any, Optional

from .. import db, staging
from ..connectors import document as doc_conn

log = logging.getLogger(__name__)


def load_sidecar(doc_path: Path) -> dict[str, Any]:
    """Read ``<stem>.meta.json`` beside the document, if present.

    Container metadata on scans is unreliable (CamScanner writes itself as the
    Author), so real bibliographic data has to come from somewhere else. A
    sidecar keeps it versioned next to the corpus instead of buried in a shell
    command that nobody can reproduce.
    """
    sidecar = doc_path.with_suffix(doc_path.suffix + ".meta.json")
    if not sidecar.exists():
        sidecar = doc_path.with_suffix(".meta.json")
    if not sidecar.exists():
        return {}
    try:
        data = json.loads(sidecar.read_text("utf-8"))
        log.info("loaded sidecar metadata: %s", sidecar.name)
        return data if isinstance(data, dict) else {}
    except json.JSONDecodeError as e:
        log.warning("ignoring malformed sidecar %s: %s", sidecar, e)
        return {}


def _passage_report(passages: list) -> dict[str, Any]:
    kinds: dict[str, int] = {}
    for p in passages:
        kinds[p.kind] = kinds.get(p.kind, 0) + 1
    body_chars = sum(len(p.text) for p in passages if p.kind == "body")
    return {
        "n_passages": len(passages),
        "kinds": kinds,
        "body_chars": body_chars,
        "needs_ocr_pages": len({p.pdf_page for p in passages
                                if p.kind == "needs_ocr"}),
    }


def run(
    *,
    doc_path: Path,
    region: str,
    doc_key: Optional[str] = None,
    meta: Optional[dict[str, Any]] = None,
    page_offset: int = 0,
    pages: Optional[tuple[int, int]] = None,
    ingest: bool = False,
    batch_id: Optional[uuid.UUID] = None,
) -> dict:
    """Probe a document; optionally register its ``doc`` entity.

    ``ingest=False`` (the default) touches no database. Probing is free and
    read-only, so it is the safe default for a stage whose main job is telling
    you whether the file even has a text layer.
    """
    doc_path = Path(doc_path)
    if not doc_path.exists():
        raise FileNotFoundError(doc_path)

    merged_meta = {**load_sidecar(doc_path), **(meta or {})}
    doc_key = doc_key or merged_meta.get("doc_key") or f"doc:{doc_path.stem}"
    page_offset = int(merged_meta.pop("page_offset", page_offset))
    merged_meta.pop("doc_key", None)

    print(f"[document] file       ={doc_path.name}")
    print(f"[document] region     ={region}")
    print(f"[document] doc_key    ={doc_key}")

    probe = doc_conn.describe(doc_path)
    print(f"[document] pages      ={probe['n_pages']} "
          f"text_layer={probe['text_pages']} coverage={probe['coverage']:.1%}")
    print(f"[document] route      ={probe['route']}"
          + ("  ← scan: L2 needs an OCR/VLM pass" if probe["route"] == "ocr" else ""))

    passages = doc_conn.read_passages(
        doc_path, doc_key=doc_key, page_offset=page_offset, pages=pages)
    rep = _passage_report(passages)
    print(f"[document] passages   ={rep['n_passages']} {rep['kinds']}")
    if rep["needs_ocr_pages"]:
        print(f"[document] needs OCR  ={rep['needs_ocr_pages']} pages "
              f"(no text layer — supply ocr_fn at L2)")

    result: dict[str, Any] = {"doc_key": doc_key, "probe": probe, "passages": rep}

    if not ingest:
        print("[document] probe only — nothing written (pass --ingest to register)")
        return result

    if not merged_meta.get("title"):
        print("[document] WARNING: no title in sidecar/--meta; "
              "container metadata on scans is often wrong")

    batch_id = batch_id or uuid.uuid4()
    rows = doc_conn.ingest_document(doc_path, region=region,
                                    doc_key=doc_key, meta=merged_meta)
    print(f"[document] batch_id   ={batch_id}")
    print(f"[document] parsed     → {len(rows)} bibliographic statements")

    with db.connect(region) as conn:
        written = staging.write_rows(conn, batch_id, rows)
        print(f"[document] staged    → {written} rows in staging.stg_ingest")
    with db.connect(region) as conn:
        rin, rok, rerr = staging.trigger_ingest_batch(conn, batch_id)
        print(f"[document] ingest_batch: rows_in={rin} rows_ok={rok} rows_err={rerr}")

    return result | {"batch_id": str(batch_id), "rows_staged": written,
                     "rows_in": rin, "rows_ok": rok, "rows_err": rerr}
