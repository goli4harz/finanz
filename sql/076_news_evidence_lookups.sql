-- ============================================================================
-- 076: Tabelle news_evidence_lookups - Protokoll der Historical-Evidence-Lookups
-- ============================================================================
-- Kap. 10 des Audit-Konzepts (2026-08-24): protokolliert jede Anfrage an den
-- neuen "Historical Evidence Lookup"-Subworkflow (Kap. 9/18, Schritt 5) - welche
-- Vergleichsfaelle wurden fuer welche News zu welchem Zeitpunkt herangezogen.
-- Dient der Nachvollziehbarkeit und einer spaeteren Kalibrierung des Matchings
-- selbst (V3-Thema, Kap. 17). Bewusst KEINE Fallzahl-Statistik hier gespeichert
-- (die wird laut Kap. 10 explizit zur Laufzeit aus v_news_evidence_cases
-- berechnet, nicht materialisiert) - stats_json ist nur ein Audit-Snapshot des
-- Lookup-Ergebnisses, keine zweite Quelle der Wahrheit.

CREATE TABLE IF NOT EXISTS trading.news_evidence_lookups (
  id                    BIGSERIAL PRIMARY KEY,
  news_id               BIGINT,
  ticker                TEXT,
  news_category         TEXT,
  sektor                TEXT,
  as_of_date            DATE,
  match_tier            INTEGER NOT NULL,
  sample_size           INTEGER NOT NULL,
  confounded_count      INTEGER NOT NULL DEFAULT 0,
  distinct_ticker_count INTEGER NOT NULL DEFAULT 0,
  evidence_sufficient   BOOLEAN NOT NULL,
  matched_case_ids      BIGINT[] NOT NULL DEFAULT '{}',
  confounded_case_ids   BIGINT[] NOT NULL DEFAULT '{}',
  stats_json            JSONB,
  computed_at           TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_news_evidence_lookups_news_id
  ON trading.news_evidence_lookups (news_id);
CREATE INDEX IF NOT EXISTS ix_news_evidence_lookups_ticker_computed
  ON trading.news_evidence_lookups (ticker, computed_at DESC);

COMMENT ON TABLE trading.news_evidence_lookups IS
  'Historical Evidence Engine (Audit-Konzept 2026-08-24, Kap. 9/10): Protokoll jeder Lookup-Anfrage an den Historical-Evidence-Lookup-Subworkflow. as_of_date ist NULL fuer Live-Aufrufe (kein Cutoff), gesetzt fuer Simulationsaufrufe aus Workflow 17 (Anti-Look-ahead, Kap. 19). match_tier 1-5 gemaess Matching-Hierarchie (Ticker+Kategorie -> Ticker -> Sektor+Kategorie -> Sektor -> Gesamtbestand); sample_size zaehlt nur nicht-konfundierte Faelle des gewaehlten Tiers.';

INSERT INTO trading.schema_migrations (version, description)
VALUES ('076', 'Tabelle news_evidence_lookups - Protokoll fuer den Historical-Evidence-Lookup-Subworkflow (Audit-Konzept 2026-08-24, Kap. 9/10/18)')
ON CONFLICT (version) DO NOTHING;
