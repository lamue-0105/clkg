-- ============================================================================
-- CLKG · Role and grants for the MLSQL writer account
--
-- The MLSQL/Spark layer connects to PG as `mlsql_writer`. It has:
--   - INSERT on staging.stg_ingest (its only write target)
--   - EXECUTE on ingest_batch()    (the only path into business tables)
--   - SELECT on staging.ingest_audit (to read its own batch status)
--
-- It has NO direct write access to evidence / conceptual_entity /
-- entity_statement. The PG transaction boundary is enforced by privileges,
-- not just convention.
--
-- Apply once per region database. Run as a superuser.
-- ============================================================================

-- Role (idempotent). Password is set out-of-band via:
--   ALTER ROLE mlsql_writer WITH PASSWORD :'pw';
-- using a value from the deployer's secret store.
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'mlsql_writer') THEN
    CREATE ROLE mlsql_writer LOGIN;
  END IF;
END$$;

-- Database connect. GRANT ... ON DATABASE needs a static identifier, so we
-- resolve current_database() via dynamic SQL inside a DO block.
DO $$
BEGIN
  EXECUTE format('GRANT CONNECT ON DATABASE %I TO mlsql_writer', current_database());
END$$;

-- Staging schema: writer can insert into stg_ingest and read its own audit.
GRANT USAGE ON SCHEMA staging TO mlsql_writer;
GRANT INSERT, SELECT ON staging.stg_ingest         TO mlsql_writer;
GRANT SELECT          ON staging.stg_ingest_errors TO mlsql_writer;
GRANT SELECT          ON staging.ingest_audit      TO mlsql_writer;

-- The only path to business tables.
GRANT EXECUTE ON FUNCTION ingest_batch(UUID) TO mlsql_writer;

-- Read-only access to the PID registry so MLSQL can preview/debug PID
-- resolution. The actual minting still happens server-side.
GRANT SELECT ON pid_registry TO mlsql_writer;

-- Explicitly REVOKE business-table writes (defense in depth — default privs
-- usually don't grant these, but make it loud).
REVOKE INSERT, UPDATE, DELETE ON evidence          FROM mlsql_writer;
REVOKE INSERT, UPDATE, DELETE ON conceptual_entity FROM mlsql_writer;
REVOKE INSERT, UPDATE, DELETE ON entity_statement  FROM mlsql_writer;
