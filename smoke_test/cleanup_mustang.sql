-- ============================================================================
-- CLKG · Mustang test data cleanup
--
-- Wipes ALL CLKG data from mustang_cl_kg so a re-ingest can start fresh.
-- Use during early testing when you want a clean slate. NEVER run this in
-- production — there is no undo.
-- ============================================================================

BEGIN;

-- Business tables (CASCADE handles FK fan-out).
TRUNCATE TABLE entity_statement, evidence, conceptual_entity RESTART IDENTITY CASCADE;

-- PID registry (so the next mint starts from 0000001 again).
TRUNCATE TABLE pid_registry;

-- Staging.
TRUNCATE TABLE staging.stg_ingest, staging.stg_ingest_errors, staging.ingest_audit;

-- Reset all per-(region,type) PID sequences.
DO $$
DECLARE seq_name TEXT;
BEGIN
  FOR seq_name IN
    SELECT relname FROM pg_class WHERE relkind = 'S' AND relname LIKE 'seq_pid_%'
  LOOP
    EXECUTE format('ALTER SEQUENCE %I RESTART WITH 1', seq_name);
  END LOOP;
END$$;

COMMIT;

-- Verify everything is empty.
SELECT 'entity_statement'  AS table_name, count(*) FROM entity_statement
UNION ALL SELECT 'evidence',                 count(*) FROM evidence
UNION ALL SELECT 'conceptual_entity',        count(*) FROM conceptual_entity
UNION ALL SELECT 'pid_registry',             count(*) FROM pid_registry
UNION ALL SELECT 'staging.stg_ingest',       count(*) FROM staging.stg_ingest;
