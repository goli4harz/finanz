-- ============================================================================
-- Welle 2, Arbeitspaket 4+5+7: Opportunity/Risk/Evidence + Fundamentaltrend +
-- Strategiesignal-Verknuepfung auf trading.recommendations
-- ============================================================================
-- decision_score (seit Paket 7/Welle 1) bleibt aus Rueckwaertskompatibilitaet
-- bestehen, gilt aber als VERALTET (siehe Kommentar). Die drei neuen Felder
-- sind fachlich unterschiedliche Dimensionen, keine Ersatz-1:1-Abbildung.

ALTER TABLE trading.recommendations
  ADD COLUMN IF NOT EXISTS opportunity_score      NUMERIC(6,4),
  ADD COLUMN IF NOT EXISTS risk_score              NUMERIC(6,4),
  ADD COLUMN IF NOT EXISTS evidence_confidence     NUMERIC(6,4),
  ADD COLUMN IF NOT EXISTS strategy_signal_id      BIGINT REFERENCES trading.strategy_signals(id),
  ADD COLUMN IF NOT EXISTS alternative_strategies_json JSONB,
  ADD COLUMN IF NOT EXISTS entry_zone_low          NUMERIC(18,6),
  ADD COLUMN IF NOT EXISTS entry_zone_high         NUMERIC(18,6),
  ADD COLUMN IF NOT EXISTS market_regime_region    TEXT,
  ADD COLUMN IF NOT EXISTS combined_regime         TEXT,
  ADD COLUMN IF NOT EXISTS fundamental_quality     JSONB,
  ADD COLUMN IF NOT EXISTS fundamental_momentum    JSONB,
  ADD COLUMN IF NOT EXISTS valuation_context       JSONB,
  ADD COLUMN IF NOT EXISTS fundamental_data_quality TEXT,
  ADD COLUMN IF NOT EXISTS news_catalyst_json      JSONB,
  ADD COLUMN IF NOT EXISTS configuration_snapshot_json JSONB;

COMMENT ON COLUMN trading.recommendations.decision_score IS
  'VERALTET seit Welle 2 (2026-08-01) - war ein einziger gemischter Score, keine '
  'Erfolgswahrscheinlichkeit. Bleibt aus Rueckwaertskompatibilitaet befuellt (Migrationsplan: '
  'siehe docs/OPPORTUNITY_RISK_EVIDENCE.md), neue Entscheidungen nutzen '
  'opportunity_score/risk_score/evidence_confidence als getrennte Dimensionen.';
COMMENT ON COLUMN trading.recommendations.opportunity_score IS 'Attraktivitaet des Setups (0-1) - KEINE Gewinnwahrscheinlichkeit. Siehe docs/OPPORTUNITY_RISK_EVIDENCE.md.';
COMMENT ON COLUMN trading.recommendations.risk_score IS 'Gefaehrlichkeit (0-1) - HOHER Wert = HOHES Risiko (nicht invertiert).';
COMMENT ON COLUMN trading.recommendations.evidence_confidence IS 'Belastbarkeit der Evidenz (0-1), Doppelzaehlung korrelierter Indikatoren vermieden (Evidenzgruppen, siehe docs/OPPORTUNITY_RISK_EVIDENCE.md).';
COMMENT ON COLUMN trading.recommendations.strategy_signal_id IS 'Verweis auf die dominante trading.strategy_signals-Zeile, aus der diese Eroeffnung abgeleitet wurde.';
COMMENT ON COLUMN trading.recommendations.alternative_strategies_json IS 'Andere zum selben Zeitpunkt passende Strategien fuer denselben Ticker (Alternativszenarien, nicht gewaehlt), strukturiert.';
COMMENT ON COLUMN trading.recommendations.fundamental_quality IS 'Welle 2, AP5: {roe_trend, verschuldung_trend, umsatz_trend:"not_available", gewinn_trend:"not_available", data_quality}. Fehlende Rohdaten (Umsatz/Gewinn absolut) werden NICHT durch die KI ergaenzt.';
COMMENT ON COLUMN trading.recommendations.fundamental_momentum IS 'Welle 2, AP5: Richtung/Staerke der verfuegbaren Fundamentaltrends ueber die letzten Revisionen.';
COMMENT ON COLUMN trading.recommendations.valuation_context IS 'Welle 2, AP5: KGV-/KBV-/Kursziel-Veraenderung gegenueber vorheriger Revision.';
COMMENT ON COLUMN trading.recommendations.configuration_snapshot_json IS 'Snapshot der zum Entscheidungszeitpunkt aktiven Schwellenwerte (Regime-Matrix-Version, Risikomodell-Konfiguration, Scanner-Konfiguration) - fuer Nachvollziehbarkeit bei spaeteren Konfigurationsaenderungen.';
