-- ============================================================================
-- CLKG · qiaopi_cl_kg cleanup + schema alignment to mustang's evidence shape
--
-- Safe to run multiple times. Wipes ALL business + staging data and renames
-- evidence columns only if they're still under their old names. Won't touch
-- columns already aligned.
-- ============================================================================

BEGIN;

-- ---- 1. Wipe everything ----------------------------------------------------
TRUNCATE TABLE entity_statement, evidence, conceptual_entity RESTART IDENTITY CASCADE;
TRUNCATE TABLE pid_registry;
TRUNCATE TABLE staging.stg_ingest, staging.stg_ingest_errors, staging.ingest_audit;

DO $$
DECLARE seq_name TEXT;
BEGIN
  FOR seq_name IN
    SELECT relname FROM pg_class WHERE relkind = 'S' AND relname LIKE 'seq_pid_qiaopi_%'
  LOOP
    EXECUTE format('ALTER SEQUENCE %I RESTART WITH 1', seq_name);
  END LOOP;
END$$;

-- ---- 2. Align evidence column names (idempotent: only rename if needed) ----
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM information_schema.columns
             WHERE table_schema='public' AND table_name='evidence'
               AND column_name='evidence_id') THEN
    ALTER TABLE evidence RENAME COLUMN evidence_id TO id;
  END IF;

  IF EXISTS (SELECT 1 FROM information_schema.columns
             WHERE table_schema='public' AND table_name='evidence'
               AND column_name='source_ref') THEN
    ALTER TABLE evidence RENAME COLUMN source_ref TO source_name;
  END IF;

  IF EXISTS (SELECT 1 FROM information_schema.columns
             WHERE table_schema='public' AND table_name='evidence'
               AND column_name='creator') THEN
    ALTER TABLE evidence RENAME COLUMN creator TO collector;
  END IF;

  IF EXISTS (SELECT 1 FROM information_schema.columns
             WHERE table_schema='public' AND table_name='evidence'
               AND column_name='raw_data_snapshot') THEN
    ALTER TABLE evidence RENAME COLUMN raw_data_snapshot TO metadata;
  END IF;

  IF EXISTS (SELECT 1 FROM information_schema.columns
             WHERE table_schema='public' AND table_name='evidence'
               AND column_name='created_at') THEN
    ALTER TABLE evidence RENAME COLUMN created_at TO recording_date;
  END IF;

  IF EXISTS (SELECT 1 FROM information_schema.columns
             WHERE table_schema='public' AND table_name='evidence'
               AND column_name='recording_date'
               AND data_type='timestamp without time zone') THEN
    ALTER TABLE evidence ALTER COLUMN recording_date TYPE date USING recording_date::date;
  END IF;

  IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                 WHERE table_schema='public' AND table_name='evidence'
                   AND column_name='description') THEN
    ALTER TABLE evidence ADD COLUMN description text;
  END IF;
END$$;

COMMIT;

-- ---- 3. Verify -------------------------------------------------------------
SELECT 'evidence'          AS t, count(*) FROM evidence
UNION ALL SELECT 'entity_statement',   count(*) FROM entity_statement
UNION ALL SELECT 'conceptual_entity',  count(*) FROM conceptual_entity
UNION ALL SELECT 'pid_registry',       count(*) FROM pid_registry
UNION ALL SELECT 'staging.stg_ingest', count(*) FROM staging.stg_ingest;

SELECT column_name, data_type FROM information_schema.columns
WHERE table_schema='public' AND table_name='evidence'
ORDER BY ordinal_position;
