-- ============================================================================
-- Experimentierplattform, Punkt 2: strategy_regime_matrix-Versionierung
-- ============================================================================
-- Bisher: Workflow 12 hat eine Freigabe vom Typ regime_restriction per UPDATE
-- in-place geschrieben, rule_version wurde dabei NICHT erhoeht. Ein alter
-- Backtest-Lauf (oder eine manuelle Abfrage), der 'regime-matrix-v1'
-- referenziert, konnte dadurch nachtraeglich andere Werte unter demselben
-- Versionsstring lesen (siehe EXPERIMENT_PLATFORM_REVIEW.md, Risiko 2).
-- Neues Muster (analog trading.scoring_weights, sql/001): 'active'-Flag statt
-- des reinen rule_version-Strings bestimmt, welche Zeile aktuell gilt. Eine
-- Freigabe deaktiviert die alte Zeile und fuegt eine neue mit eigenem
-- rule_version-Wert ein - der alte Snapshot bleibt fuer bereits gelaufene
-- Backtests unveraendert erhalten (die ohnehin die vollen Werte in
-- config_snapshot_json einfrieren, siehe sql/057 + WF17-Fix vom 2026-08-20).

ALTER TABLE trading.strategy_regime_matrix
  ADD COLUMN IF NOT EXISTS active BOOLEAN NOT NULL DEFAULT TRUE;

-- Alle bisherigen Zeilen (Seed-Daten aus sql/032, aktuell alle 'regime-matrix-v1')
-- sind die bislang einzige Version und bleiben aktiv.
UPDATE trading.strategy_regime_matrix SET active = TRUE WHERE active IS NULL;

-- Genau eine aktive Zeile je (strategy, combined_regime) - das ist die
-- Zieltabelle, aus der Workflow 06/17 die "aktuell gueltige" Eignung lesen.
CREATE UNIQUE INDEX IF NOT EXISTS uq_strategy_regime_matrix_active
  ON trading.strategy_regime_matrix (strategy, combined_regime)
  WHERE active;

COMMENT ON COLUMN trading.strategy_regime_matrix.active IS
  'Genau eine aktive Zeile je (strategy, combined_regime) - analog trading.scoring_weights.active. '
  'Ersetzt rule_version als "aktuelle Version"-Kriterium fuer Live-Lesezugriffe (WF06, WF17-Snapshot); '
  'rule_version bleibt als Audit-Label pro Zeile erhalten, wird bei jeder Freigabe ueber Workflow 12 '
  '(regime_restriction) auf einen neuen, eindeutigen Wert gesetzt statt in-place ueberschrieben.';
