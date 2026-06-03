-- ============================================================================
-- CLKG · PID minter
--
-- Generates persistent identifiers in the form:
--   clkg:{region_code}:{type_abbr}-{temporal_info}-{serial_num(7-digit)}
--
-- Sequences are lazily created the first time a new (region, type_abbr) is
-- minted, so adding a new heritage project requires NO schema migration —
-- just call mint_pid('new_region', ...) and the sequence appears.
--
-- mint_pid() runs SECURITY DEFINER so the low-priv mlsql_writer / python
-- ingest role can call it without holding CREATE-SEQUENCE privilege.
--
-- Apply once per region database.
-- ============================================================================

CREATE TABLE IF NOT EXISTS pid_registry (
  region        TEXT NOT NULL,
  type_abbr     TEXT NOT NULL,
  natural_key   TEXT NOT NULL,
  pid           TEXT NOT NULL UNIQUE,
  minted_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (region, type_abbr, natural_key)
);


CREATE OR REPLACE FUNCTION mint_pid(
  p_region    TEXT,
  p_type_abbr TEXT,
  p_temporal  TEXT
) RETURNS TEXT
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
DECLARE
  v_seq_name TEXT;
  v_serial   BIGINT;
BEGIN
  -- Validate inputs to keep dynamic SQL safe.
  IF p_region    !~ '^[a-z][a-z0-9_]*$' THEN RAISE EXCEPTION 'invalid region: %', p_region; END IF;
  IF p_type_abbr !~ '^[a-z]{2,4}$'      THEN RAISE EXCEPTION 'invalid type_abbr: %', p_type_abbr; END IF;

  v_seq_name := format('seq_pid_%s_%s', p_region, p_type_abbr);

  -- Lazy creation. First mint for a new (region,type) auto-provisions the seq.
  IF NOT EXISTS (
    SELECT 1 FROM pg_class
    WHERE relname = v_seq_name AND relkind = 'S'
  ) THEN
    EXECUTE format('CREATE SEQUENCE IF NOT EXISTS %I START 1 INCREMENT 1', v_seq_name);
  END IF;

  EXECUTE format('SELECT nextval(%L)', v_seq_name) INTO v_serial;

  RETURN format(
    'clkg:%s:%s-%s-%s',
    p_region, p_type_abbr,
    COALESCE(NULLIF(p_temporal, ''), 'unk'),
    lpad(v_serial::text, 7, '0')
  );
END;
$$;


CREATE OR REPLACE FUNCTION resolve_or_mint_pid(
  p_region      TEXT,
  p_type_abbr   TEXT,
  p_temporal    TEXT,
  p_natural_key TEXT
) RETURNS TEXT
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
DECLARE
  v_pid TEXT;
BEGIN
  SELECT pid INTO v_pid FROM pid_registry
  WHERE region = p_region AND type_abbr = p_type_abbr AND natural_key = p_natural_key;
  IF v_pid IS NOT NULL THEN RETURN v_pid; END IF;

  v_pid := mint_pid(p_region, p_type_abbr, p_temporal);

  INSERT INTO pid_registry(region, type_abbr, natural_key, pid)
  VALUES (p_region, p_type_abbr, p_natural_key, v_pid)
  ON CONFLICT (region, type_abbr, natural_key) DO NOTHING;

  SELECT pid INTO v_pid FROM pid_registry
  WHERE region = p_region AND type_abbr = p_type_abbr AND natural_key = p_natural_key;
  RETURN v_pid;
END;
$$;
