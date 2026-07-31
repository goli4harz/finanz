-- ============================================================================
-- Welle 2, Arbeitspaket 1: normalisiertes, historisiertes Strategiesignal
-- ============================================================================
-- Ersetzt NICHT trading.technical_signals_history (Rohindikatoren/Punktesystem
-- bleiben dort, Rueckwaertskompatibilitaet). Diese neue Tabelle ist die
-- normalisierte Sicht je (Ticker, Handelstag, Strategie) mit Point-in-Time-
-- Semantik wie trading.fundamentals_history (sql/022): eine Neuberechnung
-- schliesst die vorherige Revision statt sie zu ueberschreiben.
--
-- Vier Strategien: mean_reversion/trend_following/breakout (bereits seit
-- Paket 18 als JSON-Spalten auf technical_signals_history berechnet, hier
-- zusaetzlich normalisiert UND historisiert) + neu news_event (aus "06"
-- berechnet, da dort News+technische Bestaetigung gemeinsam vorliegen).

CREATE TABLE IF NOT EXISTS trading.strategy_signals (
  id                     BIGSERIAL PRIMARY KEY,
  ticker                 TEXT NOT NULL,
  business_date          DATE NOT NULL,
  strategy               TEXT NOT NULL CHECK (strategy IN ('mean_reversion','trend_following','breakout','news_event')),
  direction              TEXT NOT NULL CHECK (direction IN ('long','short','neutral')),
  raw_score              NUMERIC(6,4),
  regime_fit             NUMERIC(6,4),
  data_quality_score     NUMERIC(6,4),
  entry_zone_low         NUMERIC(18,6),
  entry_zone_high        NUMERIC(18,6),
  stop_price             NUMERIC(18,6),
  target_price           NUMERIC(18,6),
  expected_horizon_days  INTEGER,
  time_stop_at           TIMESTAMPTZ,
  evidence_json          JSONB NOT NULL DEFAULT '[]'::jsonb,
  blockers_json          JSONB NOT NULL DEFAULT '[]'::jsonb,
  rule_version           TEXT NOT NULL,
  known_at               TIMESTAMPTZ NOT NULL DEFAULT now(),
  valid_from             TIMESTAMPTZ NOT NULL DEFAULT now(),
  valid_to               TIMESTAMPTZ,
  revision_number        INTEGER NOT NULL DEFAULT 1,
  CONSTRAINT uq_strategy_signals_ticker_date_strategy_rev
    UNIQUE (ticker, business_date, strategy, revision_number)
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_strategy_signals_current
  ON trading.strategy_signals (ticker, business_date, strategy)
  WHERE valid_to IS NULL;

CREATE INDEX IF NOT EXISTS ix_strategy_signals_ticker_date
  ON trading.strategy_signals (ticker, business_date DESC);
CREATE INDEX IF NOT EXISTS ix_strategy_signals_strategy_date
  ON trading.strategy_signals (strategy, business_date DESC);

COMMENT ON TABLE trading.strategy_signals IS
  'Welle 2, AP1: normalisiertes Strategiesignal je Ticker/Tag/Strategie, Point-in-Time '
  'revisioniert. Auch neutrale/blockierte Signale werden gespeichert (fuer spaetere '
  'Auswertung/Backtesting), nicht nur handelbare.';
COMMENT ON COLUMN trading.strategy_signals.raw_score IS 'Staerke des strategiespezifischen Rohsignals (0-1), NICHT die finale Opportunity (siehe AP4, trading.recommendations.opportunity_score).';
COMMENT ON COLUMN trading.strategy_signals.regime_fit IS 'Lokaler Proxy fuer mean_reversion/trend_following/breakout (aus 02, Bollinger-Breite-Heuristik seit Paket 18) BZW. bei news_event aus 06. Die AUTORITATIVE, regime-matrix-basierte Neubewertung erfolgt erst in 06 zum Entscheidungszeitpunkt (siehe docs/MARKTREGIME.md) - dieses Feld ist der unveraenderte Rohwert zum Zeitpunkt der Signalberechnung.';
COMMENT ON COLUMN trading.strategy_signals.rule_version IS 'Versionskennung der Signal-Berechnungsregeln je Strategie (aktuell "strategy-v1").';
