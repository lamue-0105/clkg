-- ============================================================================
-- CLKG · ingest_batch(batch_id) — promotes staging.stg_ingest rows to the
-- three CL-Onto business tables in a single transaction.
--
-- Maps to the ACTUAL business-table shape observed in mustang_cl_kg
-- (2026-05-17, captured from information_schema.columns):
--
--   evidence (
--     id              integer       -- serial / identity (we INSERT...RETURNING)
--     source_type     text
--     source_name     text
--     collector       text
--     recording_date  date
--     description     text
--     metadata        jsonb
--   )
--
--   conceptual_entity (
--     pid             varchar       PK
--     entity_type     varchar
--     label_zh        varchar
--     label_en        varchar
--     created_at      timestamp
--   )
--
--   entity_statement (
--     statement_id      bigint        -- serial / identity
--     subject_id        varchar       -- FK → conceptual_entity.pid
--     predicate         varchar
--     object_value      text          -- string literals / fallback JSON
--     object_entity_id  varchar       -- FK → conceptual_entity.pid (cross-ref)
--     object_geometry   geometry      -- PostGIS native geometry
--     valid_time_start  text
--     valid_time_end    text
--     evidence_id       integer       -- FK → evidence.id
--     confidence        double precision
--   )
--
-- staging.stg_ingest.stmt_value JSONB dispatches by shape:
--   {"value":"..."}                        → object_value
--   {"ref_natural_key":"...", "ref_type_abbr":"pl", "ref_region":"..."} → object_entity_id
--   {"wkt":"POINT(...)", "srid":32645}     → object_geometry
--   anything else                          → object_value (full JSON dumped)
--
-- LIMITATION (v1): no statement-level dedup on retry. Re-running a batch will
-- duplicate entity_statement rows. conceptual_entity and evidence are
-- deduplicated via PID and source_name respectively. To re-run cleanly,
-- DELETE FROM entity_statement WHERE evidence_id IN (...) first.
-- ============================================================================

CREATE OR REPLACE FUNCTION ingest_batch(p_batch_id UUID)
RETURNS TABLE (rows_in BIGINT, rows_ok BIGINT, rows_err BIGINT)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
DECLARE
  v_rows_in  BIGINT := 0;
  v_rows_ok  BIGINT := 0;
  v_rows_err BIGINT := 0;
BEGIN
  -- ---- Audit: start (idempotent on retry) ----------------------------------
  INSERT INTO staging.ingest_audit (batch_id, region, started_at, status)
  SELECT p_batch_id, MIN(ent_region), now(), 'running'
  FROM   staging.stg_ingest
  WHERE  batch_id = p_batch_id
  ON CONFLICT (batch_id) DO UPDATE
    SET started_at = EXCLUDED.started_at, status = 'running',
        finished_at = NULL, rows_in = NULL, rows_ok = NULL, rows_err = NULL;

  DELETE FROM staging.stg_ingest_errors WHERE batch_id = p_batch_id;

  SELECT COUNT(*) INTO v_rows_in
  FROM   staging.stg_ingest WHERE batch_id = p_batch_id;

  IF v_rows_in = 0 THEN
    UPDATE staging.ingest_audit
       SET finished_at = now(), rows_in = 0, rows_ok = 0, rows_err = 0, status = 'success'
     WHERE batch_id = p_batch_id;
    RETURN QUERY SELECT 0::bigint, 0::bigint, 0::bigint;
    RETURN;
  END IF;

  -- ---- 1. PID resolution for every distinct entity in this batch ----------
  DROP TABLE IF EXISTS _ent_map;
  CREATE TEMP TABLE _ent_map ON COMMIT DROP AS
  SELECT DISTINCT
    ent_region, ent_type_abbr, ent_temporal, ent_natural_key,
    resolve_or_mint_pid(ent_region, ent_type_abbr, ent_temporal, ent_natural_key) AS pid
  FROM staging.stg_ingest
  WHERE batch_id = p_batch_id;

  CREATE INDEX ON _ent_map (ent_region, ent_type_abbr, ent_natural_key);

  -- ---- 2a. UPSERT conceptual_entity for every entity in _ent_map ----------
  --        label_zh: populated from the first hasName statement we see.
  INSERT INTO conceptual_entity (pid, entity_type, label_zh, created_at)
  SELECT
    em.pid,
    em.ent_type_abbr,
    (SELECT s2.stmt_value->>'value'
       FROM staging.stg_ingest s2
       WHERE s2.batch_id = p_batch_id
         AND s2.ent_region    = em.ent_region
         AND s2.ent_type_abbr = em.ent_type_abbr
         AND s2.ent_natural_key = em.ent_natural_key
         AND s2.stmt_predicate = 'hasName'
         AND jsonb_typeof(s2.stmt_value->'value') = 'string'
       LIMIT 1),
    now()
  FROM _ent_map em
  ON CONFLICT (pid) DO UPDATE
    SET label_zh = COALESCE(conceptual_entity.label_zh, EXCLUDED.label_zh);

  -- ---- 2b. Ensure cross-referenced entities also exist (for FK integrity) -
  INSERT INTO conceptual_entity (pid, entity_type, label_zh, created_at)
  SELECT DISTINCT
    resolve_or_mint_pid(
      COALESCE(s.stmt_value->>'ref_region', s.ent_region),
      COALESCE(s.stmt_value->>'ref_type_abbr', 'pl'),
      'unk',
      s.stmt_value->>'ref_natural_key'
    ),
    COALESCE(s.stmt_value->>'ref_type_abbr', 'pl'),
    s.stmt_value->>'ref_natural_key',
    now()
  FROM staging.stg_ingest s
  WHERE s.batch_id = p_batch_id
    AND s.stmt_value ? 'ref_natural_key'
  ON CONFLICT (pid) DO NOTHING;

  -- ---- 3. Evidence: reuse by source_name or insert new -------------------
  DROP TABLE IF EXISTS _ev_map;
  CREATE TEMP TABLE _ev_map (
    ev_source_uri TEXT PRIMARY KEY,
    evidence_id   INTEGER NOT NULL
  ) ON COMMIT DROP;

  INSERT INTO _ev_map (ev_source_uri, evidence_id)
  SELECT DISTINCT s.ev_source_uri, e.id
  FROM staging.stg_ingest s
  JOIN evidence e ON e.source_name = s.ev_source_uri
  WHERE s.batch_id = p_batch_id;

  WITH new_ev AS (
    INSERT INTO evidence (source_type, source_name, recording_date,
                          collector, description, metadata)
    SELECT DISTINCT ON (s.ev_source_uri)
      s.ev_source_type,
      s.ev_source_uri,
      s.ev_extracted_at::date,
      COALESCE(s.ev_metadata->>'surveyor',
               s.ev_metadata->>'recorder',
               s.ev_metadata->>'collector'),
      s.ev_metadata->>'description',
      s.ev_metadata
    FROM staging.stg_ingest s
    WHERE s.batch_id = p_batch_id
      AND NOT EXISTS (SELECT 1 FROM _ev_map m WHERE m.ev_source_uri = s.ev_source_uri)
    ORDER BY s.ev_source_uri, s.row_seq
    RETURNING id, source_name
  )
  INSERT INTO _ev_map (ev_source_uri, evidence_id)
  SELECT source_name, id FROM new_ev;

  -- ---- 4. entity_statement: dispatch stmt_value to the right column -------
  INSERT INTO entity_statement (
    subject_id, predicate,
    object_value, object_entity_id, object_geometry,
    valid_time_start, valid_time_end,
    evidence_id, confidence
  )
  SELECT
    em.pid AS subject_id,
    s.stmt_predicate AS predicate,

    -- object_value
    CASE
      WHEN s.stmt_value ? 'wkt'              THEN NULL
      WHEN s.stmt_value ? 'ref_natural_key'  THEN NULL
      WHEN s.stmt_value ? 'value'
           AND jsonb_typeof(s.stmt_value->'value') = 'string'
        THEN s.stmt_value->>'value'
      ELSE s.stmt_value::text
    END AS object_value,

    -- object_entity_id (cross-reference)
    CASE
      WHEN s.stmt_value ? 'ref_natural_key' THEN
        resolve_or_mint_pid(
          COALESCE(s.stmt_value->>'ref_region', s.ent_region),
          COALESCE(s.stmt_value->>'ref_type_abbr', 'pl'),
          'unk',
          s.stmt_value->>'ref_natural_key'
        )
      ELSE NULL
    END AS object_entity_id,

    -- object_geometry (PostGIS native, always stored as SRID 4326 WGS84).
    -- ST_Transform reprojects from the source SRID; a 4326→4326 call is a no-op.
    CASE
      WHEN s.stmt_value ? 'wkt' THEN
        ST_Transform(
          ST_GeomFromText(
            s.stmt_value->>'wkt',
            COALESCE(NULLIF(s.stmt_value->>'srid','')::int, 4326)
          ),
          4326
        )
      ELSE NULL
    END AS object_geometry,

    s.stmt_valid_from::text AS valid_time_start,
    s.stmt_valid_to::text   AS valid_time_end,
    m.evidence_id,
    COALESCE(NULLIF(s.stmt_value->>'confidence','')::double precision, 1.0) AS confidence
  FROM staging.stg_ingest s
  JOIN _ent_map em ON em.ent_region    = s.ent_region
                  AND em.ent_type_abbr = s.ent_type_abbr
                  AND em.ent_natural_key = s.ent_natural_key
  JOIN _ev_map  m  ON m.ev_source_uri  = s.ev_source_uri
  WHERE s.batch_id = p_batch_id
  -- Idempotent re-run: skip rows that already exist (matches the schema's
  -- unique_stmt_check on subject+predicate+value+ref+vts+evidence).
  ON CONFLICT ON CONSTRAINT unique_stmt_check DO NOTHING;

  GET DIAGNOSTICS v_rows_ok = ROW_COUNT;

  -- ---- 5. Mark staging rows processed ------------------------------------
  UPDATE staging.stg_ingest SET processed_at = now()
   WHERE batch_id = p_batch_id;

  -- ---- 6. Audit: finish --------------------------------------------------
  UPDATE staging.ingest_audit
     SET finished_at = now(),
         rows_in     = v_rows_in,
         rows_ok     = v_rows_ok,
         rows_err    = v_rows_err,
         status      = CASE WHEN v_rows_err = 0 THEN 'success' ELSE 'partial' END
   WHERE batch_id = p_batch_id;

  RETURN QUERY SELECT v_rows_in, v_rows_ok, v_rows_err;
END;
$$;


-- ----------------------------------------------------------------------------
-- Grants: callers (mlsql_writer or the future clkg_writer role) need EXECUTE
-- on this function. See sql/04_grants.sql for the comprehensive grant block.
-- ----------------------------------------------------------------------------
