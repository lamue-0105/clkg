-- ============================================================================
-- CLKG · Staging schema for MLSQL → PostgreSQL batch ingest
--
-- Apply this file once per region database (kashgar_cl_kg / liangzhu_cl_kg /
-- mustang_cl_kg / qiaopi_cl_kg) AFTER create_schema.sql has provisioned the
-- three core semantic tables (evidence / conceptual_entity / entity_statement).
--
-- MLSQL writes here only. Business tables are written by ingest_batch() in a
-- single PG transaction. See 03_ingest_batch.sql.
-- ============================================================================

CREATE SCHEMA IF NOT EXISTS staging;

-- Each row = one (entity, predicate, value, valid_time, evidence) tuple,
-- already "flattened" from raw heterogeneous sources by MLSQL.
CREATE TABLE IF NOT EXISTS staging.stg_ingest (
  batch_id         UUID         NOT NULL,
  row_seq          BIGINT       NOT NULL,

  -- evidence (PROV-O provenance for this row)
  ev_source_uri    TEXT         NOT NULL,
  ev_source_type   TEXT         NOT NULL,   -- 'xlsx_row' | 'csv_row' | 'pdf_page' | 'image' ...
  ev_extracted_at  TIMESTAMPTZ  NOT NULL DEFAULT now(),
  ev_metadata      JSONB,                   -- surveyor, recorder, raw field map, etc.

  -- conceptual_entity (PID is assigned by ingest_batch() based on natural_key)
  ent_region       TEXT         NOT NULL,   -- 'kashgar' | 'liangzhu' | 'mustang' | 'qiaopi'
  ent_type_abbr    TEXT         NOT NULL,   -- 'pl' | 'ac' | 'ev' | 'img' | 'doc'
  ent_temporal     TEXT         NOT NULL,   -- '19c' | '1880' | 'unk' | ...
  ent_natural_key  TEXT         NOT NULL,   -- idempotency key within (region, type_abbr)

  -- entity_statement (4D-fluent triple)
  stmt_predicate   TEXT         NOT NULL,   -- 'hasName' | 'locatedAt' | 'sentTo' | ...
  stmt_value       JSONB        NOT NULL,   -- {"value": ...} or {"ref_pid": "clkg:..."} or {"wkt": "POINT(...)"}
  stmt_valid_from  DATE,
  stmt_valid_to    DATE,

  -- bookkeeping
  loaded_at        TIMESTAMPTZ  NOT NULL DEFAULT now(),
  processed_at     TIMESTAMPTZ,             -- set by ingest_batch() on success

  PRIMARY KEY (batch_id, row_seq)
);

CREATE INDEX IF NOT EXISTS idx_stg_ingest_natkey
  ON staging.stg_ingest (ent_region, ent_type_abbr, ent_natural_key);

CREATE INDEX IF NOT EXISTS idx_stg_ingest_unprocessed
  ON staging.stg_ingest (batch_id) WHERE processed_at IS NULL;


-- Per-row errors caught during ingest_batch(). One error row does not abort
-- the whole batch; ingest_batch() processes per-entity savepoints and writes
-- failures here for later inspection.
CREATE TABLE IF NOT EXISTS staging.stg_ingest_errors (
  batch_id      UUID         NOT NULL,
  row_seq       BIGINT       NOT NULL,
  error_code    TEXT         NOT NULL,      -- 'pid_conflict' | 'fk_missing' | 'value_invalid' | ...
  error_msg     TEXT         NOT NULL,
  failed_at     TIMESTAMPTZ  NOT NULL DEFAULT now(),
  PRIMARY KEY (batch_id, row_seq)
);


-- One audit row per batch. Drives the monitoring dashboard.
CREATE TABLE IF NOT EXISTS staging.ingest_audit (
  batch_id       UUID         PRIMARY KEY,
  region         TEXT         NOT NULL,
  source_label   TEXT,                       -- 'qiaopi_std.xlsx' | 'mustang_2024Q3' ...
  started_at     TIMESTAMPTZ  NOT NULL DEFAULT now(),
  finished_at    TIMESTAMPTZ,
  rows_in        BIGINT,
  rows_ok        BIGINT,
  rows_err       BIGINT,
  status         TEXT         NOT NULL DEFAULT 'running'  -- 'running' | 'success' | 'partial' | 'failed'
);
