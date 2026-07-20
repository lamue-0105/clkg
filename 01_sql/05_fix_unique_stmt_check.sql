-- ============================================================================
-- CLKG · Migration: make unique_stmt_check actually enforce statement dedup
--
-- WHY
-- ---
-- The original index was:
--
--   CREATE UNIQUE INDEX unique_stmt_check ON entity_statement
--     (subject_id, predicate, md5(object_value),
--      object_entity_id, valid_time_start, evidence_id);
--
-- PostgreSQL treats NULLs as DISTINCT in a unique index unless told otherwise.
-- object_entity_id is NULL on every literal-valued statement and
-- valid_time_start is NULL on most rows, so any pair of rows differing only in
-- those columns' NULL-ness never collided: the constraint was inert for ~99%
-- of all statements. Re-running an ingest therefore duplicated rows silently.
-- Measured 2026-07-20 before this migration:
--
--   mustang    78,443 statements   38,007 redundant  (48.45%)
--   xinjiang  184,335 statements      287 redundant  ( 0.16%)
--   qiaopi    245,579 statements        3 redundant  ( 0.00%)
--   liangzhu    3,591 statements        0 redundant  ( 0.00%)
--
-- 03_ingest_batch.sql documented this honestly ("LIMITATION (v1): no
-- statement-level dedup on retry"), but the technical manual §3.2 described the
-- constraint as "幂等重跑的基础". This migration makes the manual's claim true.
--
-- WHAT IT DOES
-- ------------
--   1. Copies every redundant row into entity_statement_dupes_backup
--      (reversible: re-INSERT from that table to undo).
--   2. Deletes redundant rows, keeping the lowest statement_id of each group.
--   3. Replaces the index with a COALESCE form that collapses NULLs.
--
-- Window PARTITION BY groups NULLs together (unlike a unique index), which is
-- exactly the grouping the fixed index will enforce.
--
-- Safe to re-run: step 1 appends nothing when there is nothing to delete, and
-- the index is dropped/recreated unconditionally.
--
-- Apply:  python -m ingest.cli dedup <region>        (see ingest/cli.py)
-- ============================================================================

BEGIN;

CREATE TABLE IF NOT EXISTS entity_statement_dupes_backup
  (LIKE entity_statement INCLUDING DEFAULTS);

COMMENT ON TABLE entity_statement_dupes_backup IS
  'Rows removed by 05_fix_unique_stmt_check.sql. Retain until the dedup is '
  'confirmed good; re-INSERT INTO entity_statement to roll back.';

-- ---- 1 + 2. quarantine, then delete -------------------------------------
WITH ranked AS (
  SELECT statement_id,
         row_number() OVER (
           PARTITION BY subject_id, predicate, md5(object_value),
                        object_entity_id, valid_time_start, evidence_id
           ORDER BY statement_id
         ) AS rn
  FROM entity_statement
),
doomed AS (
  SELECT statement_id FROM ranked WHERE rn > 1
),
saved AS (
  INSERT INTO entity_statement_dupes_backup
  SELECT es.* FROM entity_statement es
  JOIN doomed d ON d.statement_id = es.statement_id
  RETURNING 1
)
DELETE FROM entity_statement es
USING doomed d
WHERE es.statement_id = d.statement_id;

-- ---- 3. the real constraint ---------------------------------------------
-- COALESCE every nullable key column so NULL compares equal to NULL.
-- evidence_id is NOT NULL in practice across all regions, so it stays plain.
DROP INDEX IF EXISTS unique_stmt_check;

CREATE UNIQUE INDEX unique_stmt_check ON entity_statement (
  subject_id,
  predicate,
  COALESCE(md5(object_value), ''),
  COALESCE(object_entity_id, ''),
  COALESCE(valid_time_start, ''),
  evidence_id
);

COMMIT;
