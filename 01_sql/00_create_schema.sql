-- ============================================================================
-- CLKG · Canonical CL-Onto schema (3 business tables)
-- Auto-extracted from mustang_cl_kg on 2026-05-17
--
-- This is the SINGLE SOURCE OF TRUTH for evidence / conceptual_entity /
-- entity_statement across all CLKG region databases. Any divergence found
-- by `python -m ingest.cli verify <region>` is a bug to fix.
--
-- This file is applied by `python -m ingest.cli init <region>` BEFORE
-- 01_staging.sql .. 04_grants.sql.
-- ============================================================================

CREATE EXTENSION IF NOT EXISTS postgis;

-- Sequences for SERIAL-style primary keys
CREATE SEQUENCE IF NOT EXISTS entity_statement_statement_id_seq;
CREATE SEQUENCE IF NOT EXISTS evidence_id_seq;

CREATE TABLE IF NOT EXISTS evidence (
  id integer NOT NULL DEFAULT nextval('evidence_id_seq'::regclass),
  source_type text,
  source_name text,
  collector text,
  recording_date date,
  description text,
  metadata jsonb,
  CONSTRAINT evidence_pkey PRIMARY KEY (id)
);

ALTER SEQUENCE evidence_id_seq OWNED BY evidence.id;

CREATE TABLE IF NOT EXISTS conceptual_entity (
  pid character varying(100) NOT NULL,
  entity_type character varying(50) NOT NULL,
  label_zh character varying(255),
  label_en character varying(255),
  created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT conceptual_entity_pkey PRIMARY KEY (pid)
);


CREATE INDEX IF NOT EXISTS idx_entity_type ON public.conceptual_entity USING btree (entity_type);

CREATE TABLE IF NOT EXISTS entity_statement (
  statement_id bigint NOT NULL DEFAULT nextval('entity_statement_statement_id_seq'::regclass),
  subject_id character varying(100) NOT NULL,
  predicate character varying(255) NOT NULL,
  object_value text,
  object_entity_id character varying(100),
  object_geometry geometry(Geometry,4326),
  valid_time_start text,
  valid_time_end text,
  evidence_id integer,
  confidence double precision DEFAULT 1.0,
  CONSTRAINT entity_statement_pkey PRIMARY KEY (statement_id)
);

ALTER SEQUENCE entity_statement_statement_id_seq OWNED BY entity_statement.statement_id;

ALTER TABLE entity_statement ADD CONSTRAINT entity_statement_object_entity_id_fkey FOREIGN KEY (object_entity_id) REFERENCES conceptual_entity(pid);
ALTER TABLE entity_statement ADD CONSTRAINT entity_statement_subject_id_fkey FOREIGN KEY (subject_id) REFERENCES conceptual_entity(pid) ON DELETE CASCADE;
ALTER TABLE entity_statement ADD CONSTRAINT unique_stmt_check UNIQUE (subject_id, predicate, object_value, object_entity_id, valid_time_start, evidence_id);

CREATE INDEX IF NOT EXISTS idx_statement_predicate ON public.entity_statement USING btree (predicate);
CREATE INDEX IF NOT EXISTS idx_statement_subject ON public.entity_statement USING btree (subject_id);
