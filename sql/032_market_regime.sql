-- ============================================================================
-- Welle 2, Arbeitspaket 3: Marktregime-Modell
-- ============================================================================
-- Berechnet in "02b" aus den bereits vorhandenen 8 Referenzsymbolen (DAX,
-- MDAX, Euro Stoxx 50, Nasdaq, S&P 500, EUR/USD, Oel, Gold - siehe
-- "Markt-Watchlist laden"). KEIN VIX/VSTOXX, KEINE Marktbreite (Advance/
-- Decline) im aktuellen Datenuniversum vorhanden - beide Merkmale werden
-- NICHT erfunden, sondern als 'not_available' markiert (siehe
-- docs/MARKTREGIME.md). stress_regime wird stattdessen aus realisierter
-- Volatilitaet der Hauptindizes abgeleitet (verfuegbarer Proxy).

CREATE TABLE IF NOT EXISTS trading.market_regime (
  id                  BIGSERIAL PRIMARY KEY,
  region              TEXT NOT NULL,
  business_date       DATE NOT NULL,
  trend_regime        TEXT,
  volatility_regime   TEXT,
  breadth_regime      TEXT,
  stress_regime       TEXT,
  liquidity_regime    TEXT,
  combined_regime     TEXT,
  regime_confidence   NUMERIC(5,4),
  data_quality        TEXT,
  session_status       TEXT,
  inputs_json          JSONB,
  rule_version         TEXT NOT NULL,
  known_at             TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT uq_market_regime_region_date UNIQUE (region, business_date)
);

CREATE INDEX IF NOT EXISTS ix_market_regime_region_date
  ON trading.market_regime (region, business_date DESC);

COMMENT ON TABLE trading.market_regime IS
  'Welle 2, AP3: differenziertes Marktregime je Region/Tag. Kein Point-in-Time-'
  'Revisionsschema wie strategy_signals - ein Tag hat genau einen Regime-Snapshot, '
  'ON CONFLICT DO UPDATE bei erneuter Berechnung (wie technical_signals_history).';
COMMENT ON COLUMN trading.market_regime.region IS 'Europa, USA oder global (Cross-Asset-Kontext aus EUR/USD, Oel, Gold - kein eigenes Regime, nur Modifikator).';
COMMENT ON COLUMN trading.market_regime.breadth_regime IS 'Immer NULL/''not_available'' - keine Marktbreiten-Datenquelle im aktuellen System. Schema vorbereitet fuer Welle 3.';
COMMENT ON COLUMN trading.market_regime.liquidity_regime IS 'Immer NULL/''not_available'' - keine aggregierte Liquiditaetsdatenquelle (Bid/Ask, Marktbreite-Volumen) im aktuellen System. Schema vorbereitet fuer Welle 3.';
COMMENT ON COLUMN trading.market_regime.stress_regime IS 'Proxy aus realisierter 20-Tage-Volatilitaet der Hauptindizes, NICHT aus VIX/VSTOXX (nicht im Datenuniversum vorhanden).';
COMMENT ON COLUMN trading.market_regime.combined_regime IS 'z.B. bull_trend_low_vol/bull_trend_high_vol/sideways_low_vol/sideways_high_vol/bear_trend/stress/unknown - siehe docs/MARKTREGIME.md fuer die Ableitungsregeln.';
COMMENT ON COLUMN trading.market_regime.rule_version IS 'Versionskennung der Regime-Ableitungsregeln (aktuell "regime-v1").';

-- ============================================================================
-- Strategie-Regime-Matrix (deterministisch, versioniert)
-- ============================================================================
CREATE TABLE IF NOT EXISTS trading.strategy_regime_matrix (
  id               BIGSERIAL PRIMARY KEY,
  rule_version     TEXT NOT NULL,
  strategy         TEXT NOT NULL,
  combined_regime  TEXT NOT NULL,
  fit_multiplier   NUMERIC(4,3) NOT NULL,
  blocked          BOOLEAN NOT NULL DEFAULT FALSE,
  notes            TEXT,
  CONSTRAINT uq_strategy_regime_matrix UNIQUE (rule_version, strategy, combined_regime)
);

COMMENT ON TABLE trading.strategy_regime_matrix IS
  'Welle 2, AP3: deterministische Zuordnung Strategie->Regime->Eignung. fit_multiplier '
  'skaliert regime_fit (0=vollstaendig blockiert bei blocked=TRUE, 1=volle Eignung, '
  'dazwischen=eingeschraenkt). 06 liest diese Tabelle statt die Logik im JS zu duplizieren.';

INSERT INTO trading.strategy_regime_matrix (rule_version, strategy, combined_regime, fit_multiplier, blocked, notes) VALUES
  ('regime-matrix-v1', 'mean_reversion', 'sideways_low_vol',  1.00, FALSE, 'Idealbedingung: Seitwaerts, ruhige Volatilitaet'),
  ('regime-matrix-v1', 'mean_reversion', 'sideways_high_vol', 0.60, FALSE, 'Eingeschraenkt: Seitwaerts, aber unruhig'),
  ('regime-matrix-v1', 'mean_reversion', 'bull_trend_low_vol',0.40, FALSE, 'Eingeschraenkt: Rueckkehr zum Mittel gegen einen Trend ist riskanter'),
  ('regime-matrix-v1', 'mean_reversion', 'bull_trend_high_vol',0.25, FALSE, 'Stark eingeschraenkt'),
  ('regime-matrix-v1', 'mean_reversion', 'bear_trend',         0.00, TRUE,  'Blockiert: dominanter Gegentrend'),
  ('regime-matrix-v1', 'mean_reversion', 'stress',             0.00, TRUE,  'Blockiert: Stressregime'),
  ('regime-matrix-v1', 'mean_reversion', 'unknown',            0.30, FALSE, 'Unklares Regime: konservativ eingeschraenkt, nicht blockiert'),

  ('regime-matrix-v1', 'trend_following', 'bull_trend_low_vol', 1.00, FALSE, 'Idealbedingung'),
  ('regime-matrix-v1', 'trend_following', 'bull_trend_high_vol',0.60, FALSE, 'Eingeschraenkt: hohe Volatilitaet'),
  ('regime-matrix-v1', 'trend_following', 'bear_trend',         1.00, FALSE, 'Idealbedingung fuer Short-Trendfolge'),
  ('regime-matrix-v1', 'trend_following', 'sideways_low_vol',   0.30, FALSE, 'Eingeschraenkt: kein klarer Trend'),
  ('regime-matrix-v1', 'trend_following', 'sideways_high_vol',  0.20, FALSE, 'Stark eingeschraenkt'),
  ('regime-matrix-v1', 'trend_following', 'stress',             0.00, TRUE,  'Blockiert: Stressregime'),
  ('regime-matrix-v1', 'trend_following', 'unknown',            0.30, FALSE, 'Unklares Regime: konservativ eingeschraenkt'),

  ('regime-matrix-v1', 'breakout', 'bull_trend_low_vol',  0.70, FALSE, 'Trendbeginn moeglich'),
  ('regime-matrix-v1', 'breakout', 'bull_trend_high_vol', 0.50, FALSE, 'Volatilitaetsexpansion, aber unklarer'),
  ('regime-matrix-v1', 'breakout', 'sideways_low_vol',    0.90, FALSE, 'Idealbedingung: Kontraktion vor Ausbruch typisch bei ruhiger Seitwaertsphase'),
  ('regime-matrix-v1', 'breakout', 'sideways_high_vol',   0.40, FALSE, 'Eingeschraenkt: erhoehtes Fehlausbruchsrisiko'),
  ('regime-matrix-v1', 'breakout', 'bear_trend',          0.50, FALSE, 'Nur fuer Short-Breakouts sinnvoll, hier pauschal eingeschraenkt'),
  ('regime-matrix-v1', 'breakout', 'stress',              0.00, TRUE,  'Blockiert: unklare Liquiditaet/Stress'),
  ('regime-matrix-v1', 'breakout', 'unknown',             0.20, FALSE, 'Stark eingeschraenkt: Liquiditaet/Regime unklar'),

  ('regime-matrix-v1', 'news_event', 'bull_trend_low_vol',  0.90, FALSE, 'Ruhiges Umfeld, Nachricht wirkt klarer'),
  ('regime-matrix-v1', 'news_event', 'bull_trend_high_vol', 0.60, FALSE, 'Eingeschraenkt: hohe Grundvolatilitaet ueberlagert Nachrichtenwirkung'),
  ('regime-matrix-v1', 'news_event', 'sideways_low_vol',    0.90, FALSE, 'Ruhiges Umfeld'),
  ('regime-matrix-v1', 'news_event', 'sideways_high_vol',   0.50, FALSE, 'Eingeschraenkt'),
  ('regime-matrix-v1', 'news_event', 'bear_trend',          0.70, FALSE, 'Nachrichten wirken oft staerker im Abwaertstrend'),
  ('regime-matrix-v1', 'news_event', 'stress',              0.30, FALSE, 'Stark eingeschraenkt, aber NICHT pauschal blockiert (Ereignis kann Stressursache selbst sein)'),
  ('regime-matrix-v1', 'news_event', 'unknown',             0.40, FALSE, 'Eingeschraenkt')
ON CONFLICT (rule_version, strategy, combined_regime) DO NOTHING;
