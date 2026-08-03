-- ============================================================================
-- 058 - Workflow 16 (historischer Nachrichtenimport, GDELT): Ergaenzungen zu
-- trading.historical_news + neue trading.historical_news_assessments.
--
-- Kontext: sql/057 hat trading.historical_news bereits angelegt, aber ohne die
-- Felder, die die konkrete GDELT-Spezifikation des Auftrags verlangt:
--   - "mehrdeutige Treffer als unklar kennzeichnen" -> ticker_match_status/
--     ambiguous_candidates_json (statt nur linked_tickers_json zu befuellen
--     oder leer zu lassen, was mehrdeutig mit "kein Treffer" waere).
--   - "fehlenden Volltext als Datenqualitaetseinschraenkung dokumentieren" ->
--     has_full_text auf historical_news, based_on_full_text auf der Bewertung
--     (GDELT liefert nur Titel+Kurzbeschreibung, nie den Artikeltext).
--   - "Titel und Beschreibung durch den bestehenden News-Analyseprozess
--     schicken" -> trading.historical_news_assessments, strukturell analog zu
--     trading.news_assessments (Punkt 8 in 001_agenten_architektur.sql), aber
--     getrennt von der Live-Tabelle (gleiche Begruendung wie bei allen anderen
--     historical_*-Tabellen aus sql/057: die Live-Pipeline liest
--     news_assessments ohne Kategorie-Filter).
--
-- Idempotent (ADD COLUMN IF NOT EXISTS / CREATE TABLE IF NOT EXISTS / ON
-- CONFLICT DO NOTHING) und wird NICHT automatisch ausgefuehrt - manueller Lauf
-- ueber "97 - Einmalig - Beliebige Query ausfuehren" wie alle bisherigen
-- Migrationen.
-- ============================================================================

BEGIN;

-- ============================================================================
-- 1. trading.historical_news: Unternehmenszuordnungs-Status + Datenqualitaet
-- ============================================================================

ALTER TABLE trading.historical_news
  ADD COLUMN IF NOT EXISTS ticker_match_status TEXT NOT NULL DEFAULT 'none',
  ADD COLUMN IF NOT EXISTS ambiguous_candidates_json JSONB NOT NULL DEFAULT '[]'::jsonb,
  ADD COLUMN IF NOT EXISTS has_full_text BOOLEAN NOT NULL DEFAULT FALSE;

DO $$
BEGIN
  ALTER TABLE trading.historical_news DROP CONSTRAINT IF EXISTS chk_historical_news_match_status;
  ALTER TABLE trading.historical_news ADD CONSTRAINT chk_historical_news_match_status
    CHECK (ticker_match_status IN ('matched', 'ambiguous', 'none'));
END $$;

COMMENT ON COLUMN trading.historical_news.ticker_match_status IS
  'matched = genau ein Instrument eindeutig erkannt (siehe linked_tickers_json), '
  'ambiguous = mehrere Instrumente gleichzeitig plausibel (siehe ambiguous_candidates_json, '
  'NICHT geraten), none = kein Instrumentenbezug (ggf. is_general_market=true).';
COMMENT ON COLUMN trading.historical_news.ambiguous_candidates_json IS
  'Nur befuellt wenn ticker_match_status=ambiguous - Liste der gleichzeitig plausiblen '
  'Ticker-Kandidaten, fuer spaetere manuelle Pruefung/Verfeinerung der Matching-Regeln.';
COMMENT ON COLUMN trading.historical_news.has_full_text IS
  'IMMER FALSE fuer den GDELT-Importpfad (Article List liefert nur Titel+Kurzbeschreibung, '
  'nie den Artikeltext) - vorgesehen fuer einen spaeteren Anbieter/Fallback mit Volltext.';

-- ============================================================================
-- 2. trading.historical_news_assessments (analog trading.news_assessments)
-- ============================================================================

CREATE TABLE IF NOT EXISTS trading.historical_news_assessments (
  id                       BIGSERIAL PRIMARY KEY,
  news_id                  BIGINT NOT NULL REFERENCES trading.historical_news (id),
  relevant                 BOOLEAN NOT NULL,
  wirkungsebene             TEXT,
  betroffene_ticker_json    JSONB NOT NULL DEFAULT '[]'::jsonb,
  betroffene_sektoren_json  JSONB NOT NULL DEFAULT '[]'::jsonb,
  wirkungsrichtung          TEXT,
  wirkung_staerke           TEXT,
  sentiment                 TEXT,
  konfidenz                 SMALLINT CHECK (konfidenz BETWEEN 0 AND 100),
  news_kategorie            TEXT,
  ticker_begruendung        TEXT,
  wirkungs_begruendung      TEXT,
  ist_wiederholung          BOOLEAN NOT NULL DEFAULT FALSE,
  referenz_news_ids_json    JSONB NOT NULL DEFAULT '[]'::jsonb,
  unsicherheiten_json       JSONB NOT NULL DEFAULT '[]'::jsonb,
  based_on_full_text        BOOLEAN NOT NULL DEFAULT FALSE,
  modell_version             TEXT,
  prompt_version              TEXT,
  created_at                   TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT chk_historical_news_assessments_wirkungsrichtung
    CHECK (wirkungsrichtung IN ('positiv','negativ','neutral','unklar') OR wirkungsrichtung IS NULL),
  CONSTRAINT chk_historical_news_assessments_staerke
    CHECK (wirkung_staerke IN ('niedrig','mittel','hoch','unklar') OR wirkung_staerke IS NULL)
);

CREATE INDEX IF NOT EXISTS ix_historical_news_assessments_news_id
  ON trading.historical_news_assessments (news_id);
CREATE INDEX IF NOT EXISTS ix_historical_news_assessments_relevant
  ON trading.historical_news_assessments (relevant);

COMMENT ON TABLE trading.historical_news_assessments IS
  'Strukturell identisch zu trading.news_assessments, aber getrennt gefuehrt fuer '
  'historisch importierte Nachrichten (Workflow 16) - referenziert historical_news statt '
  'news_items, damit die Live-Pipeline (liest news_assessments ohne Kategorie-Filter) nicht '
  'mit Simulationsdaten vermischt wird.';
COMMENT ON COLUMN trading.historical_news_assessments.based_on_full_text IS
  'Gespiegelt aus historical_news.has_full_text zum Bewertungszeitpunkt - macht sichtbar, '
  'dass eine Bewertung auf Titel+Kurzbeschreibung statt Volltext beruht, auch wenn sich '
  'has_full_text auf der Quellzeile spaeter aendern sollte.';

-- ============================================================================
-- 3. Konfigurationswerte fuer den GDELT-Importpfad
-- ============================================================================

INSERT INTO trading.pipeline_config (config_key, value_numeric, description) VALUES
  ('GDELT_PROBE_WINDOW_MINUTES', 5, 'Wie viele Minuten nach jeder Viertelstunden-Marke Workflow 16 auf eine GDELT-Datei probiert (Dateien erscheinen empirisch 1-4 Minuten danach, kein fixer Versatz).'),
  ('GDELT_REQUEST_DELAY_MS', 1500, 'Konservative Wartezeit zwischen aufeinanderfolgenden GDELT-Anfragen (unauthentifizierter oeffentlicher Dienst ohne bekanntes Rate-Limit).'),
  ('GDELT_MARKS_PER_WORKER_RUN', 12, 'Wie viele 15-Minuten-Marken Workflow 16 je Worker-Tick innerhalb EINES Tages-Pakets abarbeitet (ein ganzer Tag = 96 Marken waere bei 1-6 Anfragen je Marke + Delay zu lang fuer einen einzelnen, alle 2 Minuten feuernden Trigger-Lauf) - Fortschritt innerhalb des Tages steht in import_job_items.checkpoint_json, der naechste Tick macht bei der naechsten unbearbeiteten Marke weiter.')
ON CONFLICT (config_key) DO NOTHING;

INSERT INTO trading.pipeline_config (config_key, value_text, description) VALUES
  ('GDELT_EARLIEST_DATE', '2020-01-01', 'Fruehestes von der GDELT Article List Historical Backfile abgedecktes Datum - Jobs mit fruaehrem period_from werden von Workflow 16 abgelehnt statt endlos 404 zu probieren.')
ON CONFLICT (config_key) DO NOTHING;

INSERT INTO trading.schema_migrations (version, description)
VALUES ('058', 'Workflow 16 (GDELT-Nachrichtenimport): historical_news um Matching-Status/Datenqualitaet erweitert, historical_news_assessments neu, GDELT-Konfigurationswerte')
ON CONFLICT (version) DO NOTHING;

COMMIT;
