-- ============================================================================
-- Welle 2, Arbeitspaket 6: zweistufiger Markt-Screener
-- ============================================================================

CREATE TABLE IF NOT EXISTS trading.scan_runs (
  id                     BIGSERIAL PRIMARY KEY,
  run_id                 TEXT NOT NULL,
  business_date          DATE NOT NULL,
  started_at             TIMESTAMPTZ NOT NULL DEFAULT now(),
  finished_at            TIMESTAMPTZ,
  universe_size          INTEGER,
  stage_a_survivors      INTEGER,
  stage_b_analyzed       INTEGER,
  config_snapshot_json   JSONB,
  status                 TEXT,
  CONSTRAINT uq_scan_runs_run_id UNIQUE (run_id)
);

CREATE TABLE IF NOT EXISTS trading.scan_candidates (
  id             BIGSERIAL PRIMARY KEY,
  scan_run_id    BIGINT NOT NULL REFERENCES trading.scan_runs(id),
  ticker         TEXT NOT NULL,
  stage          TEXT NOT NULL CHECK (stage IN ('A','B')),
  included       BOOLEAN NOT NULL,
  reason         TEXT NOT NULL,
  scan_score     NUMERIC(10,4),
  strategy_hint  TEXT,
  metrics_json   JSONB,
  created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_scan_candidates_run ON trading.scan_candidates (scan_run_id);
CREATE INDEX IF NOT EXISTS ix_scan_candidates_ticker ON trading.scan_candidates (ticker, created_at DESC);
CREATE INDEX IF NOT EXISTS ix_scan_runs_date ON trading.scan_runs (business_date DESC);

COMMENT ON TABLE trading.scan_runs IS 'Welle 2, AP6: ein Lauf des neuen Workflows "13 - Markt-Screener taeglich".';
COMMENT ON TABLE trading.scan_candidates IS 'Jeder geprüfte Ticker je Lauf/Stufe, MIT Grund bei Ausschluss (included=FALSE) - keine stillen Ablehnungen.';

-- Scanner-Konfiguration (Default konservativ, verhindert teure KI-Massenaufrufe).
INSERT INTO trading.pipeline_config (config_key, value_numeric, description) VALUES
  ('SCANNER_MAX_CANDIDATES_TOTAL',        15,   'Maximale Anzahl Kandidaten insgesamt, die Stufe B (vertiefte Analyse) erreichen.'),
  ('SCANNER_MAX_CANDIDATES_PER_STRATEGY',  5,   'Maximale Stufe-B-Kandidaten je Strategie (mean_reversion/trend_following/breakout).'),
  ('SCANNER_MAX_CANDIDATES_PER_SEKTOR',    3,   'Maximale Stufe-B-Kandidaten je Sektor (Konzentrationsbegrenzung).'),
  ('SCANNER_MAX_AI_CALLS',                15,   'Harte Obergrenze an KI-Aufrufen je Scanner-Lauf (=SCANNER_MAX_CANDIDATES_TOTAL als Sicherheitsnetz, unabhaengig konfigurierbar).'),
  ('SCANNER_MIN_SCORE_FOR_STAGE_B',        0.5, 'Mindest-Scan-Score (0-1) fuer den Aufstieg von Stufe A nach Stufe B.'),
  ('SCANNER_MIN_VOLUME_EUR',          500000,   'Mindest-Tagesumsatz (Kurs x Volumen, naeherungsweise in Kontowaehrung) fuer ausreichende Liquiditaet in Stufe A.'),
  ('SCANNER_MIN_PRICE',                    2.0, 'Mindestkurs (vermeidet Penny-Stock-Rauschen).')
ON CONFLICT (config_key) DO NOTHING;
