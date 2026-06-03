-- ============================================================================
-- CLKG · Mustang CulturalLandscapeUnit (CLU) Type Upgrade
--
-- Reclassifies aggregation entities (Layer = 群体 or 区域) from atomic
-- Place (type_abbr='pl') to CulturalLandscapeUnit (type_abbr='clu').
-- The Mustang schema doc defines:
--   单体 = single point  → stays 'pl'
--   群体 = multi-same-type aggregation → 'clu'
--   区域 = multi-different-type aggregation → 'clu'
--
-- This script changes TWO tables consistently:
--   conceptual_entity.entity_type — "current truth"
--   pid_registry.type_abbr        — lookup key used by resolve_or_mint_pid
--
-- The PID string itself is left unchanged (still has 'pl-' segment for the
-- 220 legacy entities). PIDs are persistent identifiers — changing them
-- would cascade into entity_statement.subject_id, .object_entity_id, etc.
-- Cosmetic mismatch is acceptable; semantic correctness on entity_type is not.
--
-- Idempotent: re-running has no effect after first run.
-- ============================================================================

BEGIN;

-- Snapshot the upgrade scope so we can verify.
WITH clu_targets AS (
  SELECT DISTINCT subject_id
  FROM entity_statement
  WHERE subject_id LIKE 'clkg:mustang:%'
    AND predicate = 'hasLayer'
    AND object_value IN ('群体', '区域')
)
SELECT
  'before upgrade'                AS phase,
  count(*)                         AS clu_target_count,
  count(*) FILTER (WHERE ce.entity_type = 'pl')  AS still_pl,
  count(*) FILTER (WHERE ce.entity_type = 'clu') AS already_clu
FROM clu_targets t
JOIN conceptual_entity ce ON ce.pid = t.subject_id;

-- 1) Update conceptual_entity.entity_type
UPDATE conceptual_entity ce
SET entity_type = 'clu'
WHERE ce.pid IN (
  SELECT DISTINCT subject_id
  FROM entity_statement
  WHERE subject_id LIKE 'clkg:mustang:%'
    AND predicate = 'hasLayer'
    AND object_value IN ('群体', '区域')
)
AND ce.entity_type = 'pl';

-- 2) Sync pid_registry.type_abbr so future ingests resolve to the same PIDs
UPDATE pid_registry pr
SET type_abbr = 'clu'
WHERE pr.region = 'mustang'
  AND pr.type_abbr = 'pl'
  AND pr.pid IN (
    SELECT DISTINCT subject_id
    FROM entity_statement
    WHERE subject_id LIKE 'clkg:mustang:%'
      AND predicate = 'hasLayer'
      AND object_value IN ('群体', '区域')
  );

COMMIT;

-- ---- Verification ----------------------------------------------------------

-- After: entity_type breakdown for Mustang
SELECT entity_type, count(*) AS n
FROM conceptual_entity
WHERE pid LIKE 'clkg:mustang:%'
GROUP BY entity_type
ORDER BY entity_type;

-- After: pid_registry alignment
SELECT type_abbr, count(*) AS n
FROM pid_registry
WHERE region = 'mustang'
GROUP BY type_abbr
ORDER BY type_abbr;

-- Cross-check: CLU entities should all have hasLayer in (群体, 区域)
SELECT 'CLU has wrong Layer' AS check_name, count(*) AS bad_rows
FROM conceptual_entity ce
LEFT JOIN entity_statement es
  ON es.subject_id = ce.pid AND es.predicate = 'hasLayer'
WHERE ce.entity_type = 'clu'
  AND ce.pid LIKE 'clkg:mustang:%'
  AND (es.object_value IS NULL OR es.object_value NOT IN ('群体', '区域'));

-- Cross-check: Place entities should NOT have Layer in (群体, 区域)
SELECT 'PL has aggregation Layer' AS check_name, count(*) AS bad_rows
FROM conceptual_entity ce
JOIN entity_statement es
  ON es.subject_id = ce.pid AND es.predicate = 'hasLayer'
WHERE ce.entity_type = 'pl'
  AND ce.pid LIKE 'clkg:mustang:%'
  AND es.object_value IN ('群体', '区域');
