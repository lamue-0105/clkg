-- ============================================================================
-- CLKG · Mustang smoke test  (auto-generated; do not edit by hand)
-- batch_id = 15263f14-d213-5da6-b7b5-7842cb63c7c2
-- source   = /Users/lamue/mustang_fixed.csv
-- rows     = 10 CSV rows -> 31 staging rows
-- ============================================================================
-- Run against mustang_cl_kg AFTER sql/01..04 have been applied.
-- ============================================================================

BEGIN;
DELETE FROM staging.stg_ingest_errors WHERE batch_id = '15263f14-d213-5da6-b7b5-7842cb63c7c2'::uuid;
DELETE FROM staging.stg_ingest        WHERE batch_id = '15263f14-d213-5da6-b7b5-7842cb63c7c2'::uuid;
DELETE FROM staging.ingest_audit      WHERE batch_id = '15263f14-d213-5da6-b7b5-7842cb63c7c2'::uuid;

INSERT INTO staging.stg_ingest (
  batch_id, row_seq,
  ev_source_uri, ev_source_type, ev_extracted_at, ev_metadata,
  ent_region, ent_type_abbr, ent_temporal, ent_natural_key,
  stmt_predicate, stmt_value,
  stmt_valid_from, stmt_valid_to
) VALUES
  ('15263f14-d213-5da6-b7b5-7842cb63c7c2', 101, 'csv:///Users/lamue/mustang_fixed.csv#OBJECTID=1', 'csv_row', now(), '{"data_source": "GPS20190504+i调查202409", "surveyor": "lhp", "recorder": "hxh,xl", "literature": " ", "note": "Sakya，16th"}'::jsonb, 'mustang', 'pl', 'unk', 'HXH2025030301', 'hasName', '{"value": "Lowo Nyiphug Namdrol Norbuling Monestery&School"}'::jsonb, NULL, NULL),
  ('15263f14-d213-5da6-b7b5-7842cb63c7c2', 102, 'csv:///Users/lamue/mustang_fixed.csv#OBJECTID=1', 'csv_row', now(), '{"data_source": "GPS20190504+i调查202409", "surveyor": "lhp", "recorder": "hxh,xl", "literature": " ", "note": "Sakya，16th"}'::jsonb, 'mustang', 'pl', 'unk', 'HXH2025030301', 'hasType', '{"value": "洞穴寺院"}'::jsonb, NULL, NULL),
  ('15263f14-d213-5da6-b7b5-7842cb63c7c2', 103, 'csv:///Users/lamue/mustang_fixed.csv#OBJECTID=1', 'csv_row', now(), '{"data_source": "GPS20190504+i调查202409", "surveyor": "lhp", "recorder": "hxh,xl", "literature": " ", "note": "Sakya，16th"}'::jsonb, 'mustang', 'pl', 'unk', 'HXH2025030301', 'locatedAt', '{"wkt": "POINT(789484.6848 3237680.528)", "z": 0.0, "srid": 32645}'::jsonb, NULL, NULL),
  ('15263f14-d213-5da6-b7b5-7842cb63c7c2', 201, 'csv:///Users/lamue/mustang_fixed.csv#OBJECTID=2', 'csv_row', now(), '{"data_source": "i调查202409", "surveyor": "lhp", "recorder": "hxh,xl", "literature": " ", "note": " "}'::jsonb, 'mustang', 'pl', 'unk', 'HXH2025030303', 'hasName', '{"value": "Nyiphug寺院对面山崖洞穴"}'::jsonb, NULL, NULL),
  ('15263f14-d213-5da6-b7b5-7842cb63c7c2', 202, 'csv:///Users/lamue/mustang_fixed.csv#OBJECTID=2', 'csv_row', now(), '{"data_source": "i调查202409", "surveyor": "lhp", "recorder": "hxh,xl", "literature": " ", "note": " "}'::jsonb, 'mustang', 'pl', 'unk', 'HXH2025030303', 'hasType', '{"value": "洞穴"}'::jsonb, NULL, NULL),
  ('15263f14-d213-5da6-b7b5-7842cb63c7c2', 203, 'csv:///Users/lamue/mustang_fixed.csv#OBJECTID=2', 'csv_row', now(), '{"data_source": "i调查202409", "surveyor": "lhp", "recorder": "hxh,xl", "literature": " ", "note": " "}'::jsonb, 'mustang', 'pl', 'unk', 'HXH2025030303', 'locatedAt', '{"wkt": "POINT(789498.2856 3237145.185)", "z": 0.0, "srid": 32645}'::jsonb, NULL, NULL),
  ('15263f14-d213-5da6-b7b5-7842cb63c7c2', 301, 'csv:///Users/lamue/mustang_fixed.csv#OBJECTID=3', 'csv_row', now(), '{"data_source": "i调查202409+Google20240515", "surveyor": "lhp", "recorder": "hxh,xl", "literature": "[1]高原秘境木斯塘207", "note": null}'::jsonb, 'mustang', 'pl', 'unk', 'HXH2025030304', 'hasName', '{"value": "Jhong Cave入口"}'::jsonb, NULL, NULL),
  ('15263f14-d213-5da6-b7b5-7842cb63c7c2', 302, 'csv:///Users/lamue/mustang_fixed.csv#OBJECTID=3', 'csv_row', now(), '{"data_source": "i调查202409+Google20240515", "surveyor": "lhp", "recorder": "hxh,xl", "literature": "[1]高原秘境木斯塘207", "note": null}'::jsonb, 'mustang', 'pl', 'unk', 'HXH2025030304', 'hasType', '{"value": "洞穴"}'::jsonb, NULL, NULL),
  ('15263f14-d213-5da6-b7b5-7842cb63c7c2', 303, 'csv:///Users/lamue/mustang_fixed.csv#OBJECTID=3', 'csv_row', now(), '{"data_source": "i调查202409+Google20240515", "surveyor": "lhp", "recorder": "hxh,xl", "literature": "[1]高原秘境木斯塘207", "note": null}'::jsonb, 'mustang', 'pl', 'unk', 'HXH2025030304', 'locatedAt', '{"wkt": "POINT(789919.815 3237826.223)", "z": 0.0, "srid": 32645}'::jsonb, NULL, NULL),
  ('15263f14-d213-5da6-b7b5-7842cb63c7c2', 304, 'csv:///Users/lamue/mustang_fixed.csv#OBJECTID=3', 'csv_row', now(), '{"data_source": "i调查202409+Google20240515", "surveyor": "lhp", "recorder": "hxh,xl", "literature": "[1]高原秘境木斯塘207", "note": null}'::jsonb, 'mustang', 'pl', 'unk', 'HXH2025030304', 'hasDescription', '{"value": "[1]一个庞大的洞穴群落，错落为5层，共108个小洞窟。又名isija Jong Cave/Chhoser Cave。"}'::jsonb, NULL, NULL),
  ('15263f14-d213-5da6-b7b5-7842cb63c7c2', 401, 'csv:///Users/lamue/mustang_fixed.csv#OBJECTID=4', 'csv_row', now(), '{"data_source": "i调查202409", "surveyor": "hj", "recorder": "hxh,xl", "literature": " ", "note": " "}'::jsonb, 'mustang', 'pl', 'unk', 'HXH2025030305', 'hasName', '{"value": "洞穴入口"}'::jsonb, NULL, NULL),
  ('15263f14-d213-5da6-b7b5-7842cb63c7c2', 402, 'csv:///Users/lamue/mustang_fixed.csv#OBJECTID=4', 'csv_row', now(), '{"data_source": "i调查202409", "surveyor": "hj", "recorder": "hxh,xl", "literature": " ", "note": " "}'::jsonb, 'mustang', 'pl', 'unk', 'HXH2025030305', 'hasType', '{"value": "洞穴"}'::jsonb, NULL, NULL),
  ('15263f14-d213-5da6-b7b5-7842cb63c7c2', 403, 'csv:///Users/lamue/mustang_fixed.csv#OBJECTID=4', 'csv_row', now(), '{"data_source": "i调查202409", "surveyor": "hj", "recorder": "hxh,xl", "literature": " ", "note": " "}'::jsonb, 'mustang', 'pl', 'unk', 'HXH2025030305', 'locatedAt', '{"wkt": "POINT(791315.2877 3238460.611)", "z": 0.0, "srid": 32645}'::jsonb, NULL, NULL),
  ('15263f14-d213-5da6-b7b5-7842cb63c7c2', 501, 'csv:///Users/lamue/mustang_fixed.csv#OBJECTID=5', 'csv_row', now(), '{"data_source": "i调查202409", "surveyor": "lhp", "recorder": "hxh", "literature": " ", "note": " "}'::jsonb, 'mustang', 'pl', 'unk', 'HXH2025030306', 'hasName', '{"value": "Dzong制高点"}'::jsonb, NULL, NULL),
  ('15263f14-d213-5da6-b7b5-7842cb63c7c2', 502, 'csv:///Users/lamue/mustang_fixed.csv#OBJECTID=5', 'csv_row', now(), '{"data_source": "i调查202409", "surveyor": "lhp", "recorder": "hxh", "literature": " ", "note": " "}'::jsonb, 'mustang', 'pl', 'unk', 'HXH2025030306', 'hasType', '{"value": "疑点"}'::jsonb, NULL, NULL),
  ('15263f14-d213-5da6-b7b5-7842cb63c7c2', 503, 'csv:///Users/lamue/mustang_fixed.csv#OBJECTID=5', 'csv_row', now(), '{"data_source": "i调查202409", "surveyor": "lhp", "recorder": "hxh", "literature": " ", "note": " "}'::jsonb, 'mustang', 'pl', 'unk', 'HXH2025030306', 'locatedAt', '{"wkt": "POINT(787472.1068 3233459.951)", "z": 0.0, "srid": 32645}'::jsonb, NULL, NULL),
  ('15263f14-d213-5da6-b7b5-7842cb63c7c2', 601, 'csv:///Users/lamue/mustang_fixed.csv#OBJECTID=6', 'csv_row', now(), '{"data_source": "i调查202409", "surveyor": "lhp", "recorder": "hxh", "literature": " ", "note": " "}'::jsonb, 'mustang', 'pl', 'unk', 'HXH2025030307', 'hasName', '{"value": "土方"}'::jsonb, NULL, NULL),
  ('15263f14-d213-5da6-b7b5-7842cb63c7c2', 602, 'csv:///Users/lamue/mustang_fixed.csv#OBJECTID=6', 'csv_row', now(), '{"data_source": "i调查202409", "surveyor": "lhp", "recorder": "hxh", "literature": " ", "note": " "}'::jsonb, 'mustang', 'pl', 'unk', 'HXH2025030307', 'hasType', '{"value": "疑点"}'::jsonb, NULL, NULL),
  ('15263f14-d213-5da6-b7b5-7842cb63c7c2', 603, 'csv:///Users/lamue/mustang_fixed.csv#OBJECTID=6', 'csv_row', now(), '{"data_source": "i调查202409", "surveyor": "lhp", "recorder": "hxh", "literature": " ", "note": " "}'::jsonb, 'mustang', 'pl', 'unk', 'HXH2025030307', 'locatedAt', '{"wkt": "POINT(787225.3158 3233018.531)", "z": 0.0, "srid": 32645}'::jsonb, NULL, NULL),
  ('15263f14-d213-5da6-b7b5-7842cb63c7c2', 701, 'csv:///Users/lamue/mustang_fixed.csv#OBJECTID=7', 'csv_row', now(), '{"data_source": "i调查202409", "surveyor": "lhp", "recorder": "hxh", "literature": " ", "note": " "}'::jsonb, 'mustang', 'pl', 'unk', 'HXH2025030308', 'hasName', '{"value": "土方带红漆，应该是宗教类"}'::jsonb, NULL, NULL),
  ('15263f14-d213-5da6-b7b5-7842cb63c7c2', 702, 'csv:///Users/lamue/mustang_fixed.csv#OBJECTID=7', 'csv_row', now(), '{"data_source": "i调查202409", "surveyor": "lhp", "recorder": "hxh", "literature": " ", "note": " "}'::jsonb, 'mustang', 'pl', 'unk', 'HXH2025030308', 'hasType', '{"value": "疑点"}'::jsonb, NULL, NULL),
  ('15263f14-d213-5da6-b7b5-7842cb63c7c2', 703, 'csv:///Users/lamue/mustang_fixed.csv#OBJECTID=7', 'csv_row', now(), '{"data_source": "i调查202409", "surveyor": "lhp", "recorder": "hxh", "literature": " ", "note": " "}'::jsonb, 'mustang', 'pl', 'unk', 'HXH2025030308', 'locatedAt', '{"wkt": "POINT(787221.5339 3232981.131)", "z": 0.0, "srid": 32645}'::jsonb, NULL, NULL),
  ('15263f14-d213-5da6-b7b5-7842cb63c7c2', 801, 'csv:///Users/lamue/mustang_fixed.csv#OBJECTID=8', 'csv_row', now(), '{"data_source": "i调查202409", "surveyor": "lhp", "recorder": "hxh", "literature": " ", "note": " "}'::jsonb, 'mustang', 'pl', 'unk', 'HXH2025030309', 'hasName', '{"value": "泥墙组1"}'::jsonb, NULL, NULL),
  ('15263f14-d213-5da6-b7b5-7842cb63c7c2', 802, 'csv:///Users/lamue/mustang_fixed.csv#OBJECTID=8', 'csv_row', now(), '{"data_source": "i调查202409", "surveyor": "lhp", "recorder": "hxh", "literature": " ", "note": " "}'::jsonb, 'mustang', 'pl', 'unk', 'HXH2025030309', 'hasType', '{"value": "疑点"}'::jsonb, NULL, NULL),
  ('15263f14-d213-5da6-b7b5-7842cb63c7c2', 803, 'csv:///Users/lamue/mustang_fixed.csv#OBJECTID=8', 'csv_row', now(), '{"data_source": "i调查202409", "surveyor": "lhp", "recorder": "hxh", "literature": " ", "note": " "}'::jsonb, 'mustang', 'pl', 'unk', 'HXH2025030309', 'locatedAt', '{"wkt": "POINT(787269.4677 3232898.697)", "z": 0.0, "srid": 32645}'::jsonb, NULL, NULL),
  ('15263f14-d213-5da6-b7b5-7842cb63c7c2', 901, 'csv:///Users/lamue/mustang_fixed.csv#OBJECTID=9', 'csv_row', now(), '{"data_source": "i调查202409", "surveyor": "lhp", "recorder": "hxh", "literature": " ", "note": " "}'::jsonb, 'mustang', 'pl', 'unk', 'HXH2025030310', 'hasName', '{"value": "泥墙组1"}'::jsonb, NULL, NULL),
  ('15263f14-d213-5da6-b7b5-7842cb63c7c2', 902, 'csv:///Users/lamue/mustang_fixed.csv#OBJECTID=9', 'csv_row', now(), '{"data_source": "i调查202409", "surveyor": "lhp", "recorder": "hxh", "literature": " ", "note": " "}'::jsonb, 'mustang', 'pl', 'unk', 'HXH2025030310', 'hasType', '{"value": "疑点"}'::jsonb, NULL, NULL),
  ('15263f14-d213-5da6-b7b5-7842cb63c7c2', 903, 'csv:///Users/lamue/mustang_fixed.csv#OBJECTID=9', 'csv_row', now(), '{"data_source": "i调查202409", "surveyor": "lhp", "recorder": "hxh", "literature": " ", "note": " "}'::jsonb, 'mustang', 'pl', 'unk', 'HXH2025030310', 'locatedAt', '{"wkt": "POINT(787297.2294 3232898.999)", "z": 0.0, "srid": 32645}'::jsonb, NULL, NULL),
  ('15263f14-d213-5da6-b7b5-7842cb63c7c2', 1001, 'csv:///Users/lamue/mustang_fixed.csv#OBJECTID=10', 'csv_row', now(), '{"data_source": "i调查202409", "surveyor": "lhp", "recorder": "hxh", "literature": " ", "note": " "}'::jsonb, 'mustang', 'pl', 'unk', 'HXH2025030311', 'hasName', '{"value": "佛塔"}'::jsonb, NULL, NULL),
  ('15263f14-d213-5da6-b7b5-7842cb63c7c2', 1002, 'csv:///Users/lamue/mustang_fixed.csv#OBJECTID=10', 'csv_row', now(), '{"data_source": "i调查202409", "surveyor": "lhp", "recorder": "hxh", "literature": " ", "note": " "}'::jsonb, 'mustang', 'pl', 'unk', 'HXH2025030311', 'hasType', '{"value": "佛塔"}'::jsonb, NULL, NULL),
  ('15263f14-d213-5da6-b7b5-7842cb63c7c2', 1003, 'csv:///Users/lamue/mustang_fixed.csv#OBJECTID=10', 'csv_row', now(), '{"data_source": "i调查202409", "surveyor": "lhp", "recorder": "hxh", "literature": " ", "note": " "}'::jsonb, 'mustang', 'pl', 'unk', 'HXH2025030311', 'locatedAt', '{"wkt": "POINT(787335.8992 3232809.27)", "z": 0.0, "srid": 32645}'::jsonb, NULL, NULL);

COMMIT;

-- ---- Promote to business tables -------------------------------------------
SELECT * FROM ingest_batch('15263f14-d213-5da6-b7b5-7842cb63c7c2'::uuid);

-- ---- Verification queries -------------------------------------------------
\echo '--- audit row ---'
SELECT * FROM staging.ingest_audit WHERE batch_id = '15263f14-d213-5da6-b7b5-7842cb63c7c2'::uuid;

\echo '--- per-row errors (should be empty) ---'
SELECT * FROM staging.stg_ingest_errors WHERE batch_id = '15263f14-d213-5da6-b7b5-7842cb63c7c2'::uuid;

\echo '--- minted PIDs for this batch ---'
SELECT pid, type_abbr, natural_key
FROM   conceptual_entity
WHERE  region = 'mustang'
ORDER  BY pid;

\echo '--- statements written ---'
SELECT ce.pid, es.predicate, es.value, ev.source_uri
FROM   entity_statement es
JOIN   conceptual_entity ce ON ce.pid = es.entity_pid
JOIN   evidence          ev ON ev.evidence_id = es.evidence_id
WHERE  ev.source_uri LIKE 'csv://%mustang_fixed.csv%'
ORDER  BY ce.pid, es.predicate;

\echo '--- staging rows after promotion (all should be processed) ---'
SELECT batch_id, row_seq, processed_at IS NOT NULL AS processed
FROM   staging.stg_ingest
WHERE  batch_id = '15263f14-d213-5da6-b7b5-7842cb63c7c2'::uuid
ORDER  BY row_seq;
