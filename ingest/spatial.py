"""Post-ingest spatial inference: derive `containsPlace` from geometric within().

After polygon-shaped CulturalLandscapeUnit (clu) entities are ingested, this
module computes spatial containment against atomic Place (pl) entities and
materializes the implicit hierarchy as explicit `containsPlace` statements.

The inference itself is the "source" of these statements — they are NOT in any
file. We record a synthetic evidence row (`spatial://<region>/inference`) so
provenance stays honest.

Usage:
    from .spatial import link_contains_place
    n = link_contains_place(region='mustang')
"""
from __future__ import annotations

import logging
from typing import Optional

from . import db

log = logging.getLogger(__name__)


_ENSURE_EVIDENCE = """
INSERT INTO evidence (source_type, source_name, recording_date,
                      collector, description, metadata)
SELECT 'spatial_inference', %(uri)s::text, CURRENT_DATE,
       'spatial_within_join',
       'Auto-derived containsPlace statements via ST_Contains(clu.poly, pl.point).',
       jsonb_build_object('region', %(region)s::text)
WHERE NOT EXISTS (SELECT 1 FROM evidence WHERE source_name = %(uri)s::text)
RETURNING id;
"""

_FETCH_EVIDENCE_ID = """
SELECT id FROM evidence WHERE source_name = %(uri)s;
"""

_LINK_QUERY = """
WITH clu AS (
  SELECT ce.pid, es.object_geometry AS geom
  FROM   conceptual_entity ce
  JOIN   entity_statement es ON es.subject_id = ce.pid AND es.predicate = 'locatedAt'
  WHERE  ce.entity_type = 'clu'
    AND  ce.pid LIKE %(pid_prefix)s
    AND  GeometryType(es.object_geometry) IN ('POLYGON','MULTIPOLYGON')
),
pl AS (
  SELECT ce.pid, es.object_geometry AS geom
  FROM   conceptual_entity ce
  JOIN   entity_statement es ON es.subject_id = ce.pid AND es.predicate = 'locatedAt'
  WHERE  ce.entity_type = 'pl'
    AND  ce.pid LIKE %(pid_prefix)s
    AND  GeometryType(es.object_geometry) = 'POINT'
)
INSERT INTO entity_statement (
  subject_id, predicate, object_value, object_entity_id, object_geometry,
  valid_time_start, valid_time_end, evidence_id, confidence
)
SELECT clu.pid, 'containsPlace', NULL, pl.pid, NULL,
       NULL, NULL, %(evidence_id)s, 1.0
FROM   clu, pl
WHERE  ST_Contains(clu.geom, pl.geom)
ON CONFLICT ON CONSTRAINT unique_stmt_check DO NOTHING;
"""


def link_contains_place(region: str) -> int:
    """Generate `containsPlace` statements for all clu→pl spatial containments
    in the named region. Returns count of NEW statements inserted (existing
    ones are skipped by the unique constraint).
    """
    inference_uri = f"spatial://{region}/inference/contains_place"
    pid_prefix = f"clkg:{region}:%"

    with db.connect(region) as conn:
        with conn.cursor() as cur:
            # 1. Ensure the synthetic evidence row exists
            cur.execute(_ENSURE_EVIDENCE, {"uri": inference_uri, "region": region})
            cur.execute(_FETCH_EVIDENCE_ID, {"uri": inference_uri})
            evidence_id = cur.fetchone()[0]

            # 2. Run the spatial-containment INSERT
            cur.execute(_LINK_QUERY, {
                "pid_prefix": pid_prefix,
                "evidence_id": evidence_id,
            })
            n_inserted = cur.rowcount

    log.info("[spatial] %s: %d new containsPlace statements", region, n_inserted)
    return n_inserted
