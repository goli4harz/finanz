-- ============================================================================
-- 053 (Haertung Welle 1-3, Phasen 6+7, kritisch): Portfolioveto-Statusmodell
-- + Rueckstandsverarbeitung fuer trading.recommendations
-- ============================================================================
-- Bestaetigter Fund: 06 schrieb status='offen' fest verdrahtet ins INSERT,
-- OHNE dass 14 (Portfoliorisiko) je Gelegenheit hatte, vorher zu pruefen.
-- 14 schreibt bislang NIE auf trading.recommendations zurueck (nur auf
-- paper_trades) - ein von 14 blockierter Trade liess die zugehoerige
-- Empfehlung fuer immer als status='offen' stehen. Gleichzeitig las 14s
-- Ladequery nur "entry_datum = CURRENT_DATE" - ein verspaeteter/
-- unterbrochener Lauf verlor eine Empfehlung dauerhaft (Phase 7).
--
-- Neues Zwischenmodell: 06 schreibt initial 'portfolio_pending' statt
-- 'offen'. 14s Ladequery wird rein statusbasiert (kein Datumsfilter mehr) -
-- jede noch offene 'portfolio_pending'-Zeile wird beim naechsten Lauf
-- verarbeitet, unabhaengig vom Anlagedatum (loest Phase 7 nebenbei, da
-- dieselbe Ladequery betroffen ist). 14 schreibt danach zurueck:
-- approved -> 'offen', abgelehnt -> 'portfolio_blocked'.

BEGIN;

-- Bestehender Unique-Index deckte nur 'offen' ab - 'portfolio_pending' muss
-- ebenfalls "nur eine aktive Zeile je Ticker" garantieren, sonst koennte 06
-- denselben Ticker zweimal als portfolio_pending anlegen, bevor 14 den
-- ersten Kandidaten aufgeloest hat.
DROP INDEX IF EXISTS trading.ux_recommendations_one_open_per_ticker;
CREATE UNIQUE INDEX IF NOT EXISTS ux_recommendations_one_active_per_ticker
    ON trading.recommendations (ticker)
    WHERE status IN ('offen', 'portfolio_pending');

ALTER TABLE trading.recommendations
  ADD COLUMN IF NOT EXISTS portfolio_check_id BIGINT REFERENCES trading.portfolio_risk_checks(id),
  ADD COLUMN IF NOT EXISTS portfolio_checked_at TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS portfolio_blocked_reason TEXT,
  ADD COLUMN IF NOT EXISTS portfolio_risk_before NUMERIC(8,5),
  ADD COLUMN IF NOT EXISTS portfolio_risk_after NUMERIC(8,5),
  ADD COLUMN IF NOT EXISTS portfolio_check_attempts INTEGER NOT NULL DEFAULT 0,
  ADD COLUMN IF NOT EXISTS last_processing_error TEXT;

COMMENT ON COLUMN trading.recommendations.portfolio_check_id IS
  'Verweis auf die trading.portfolio_risk_checks-Zeile, die ueber offen/portfolio_blocked entschieden hat (Haertung Welle 1-3, Phase 6).';
COMMENT ON COLUMN trading.recommendations.portfolio_blocked_reason IS
  'Menschenlesbare Zusammenfassung der Blocker, falls status=portfolio_blocked - Detail in portfolio_risk_checks.blockers_json ueber portfolio_check_id.';
COMMENT ON COLUMN trading.recommendations.portfolio_check_attempts IS
  'Anzahl Laeufe von 14, in denen diese Zeile als portfolio_pending verarbeitet wurde - Grundlage fuer die Dead-Letter-Eskalation nach MAX_PORTFOLIO_CHECK_ATTEMPTS (Haertung Welle 1-3, Phase 7).';

INSERT INTO trading.pipeline_config (config_key, value_numeric, description)
VALUES ('MAX_PORTFOLIO_CHECK_ATTEMPTS', 5, 'Maximale Anzahl Laeufe, in denen eine Empfehlung als portfolio_pending verarbeitet werden darf, bevor sie als portfolio_check_failed eskaliert wird (Haertung Welle 1-3, Phase 7).')
ON CONFLICT (config_key) DO NOTHING;

INSERT INTO trading.schema_migrations (version, description)
VALUES ('053', 'Portfolioveto-Statusmodell + Rueckstandsverarbeitung fuer recommendations (Haertung Welle 1-3, Phasen 6+7)')
ON CONFLICT (version) DO NOTHING;

COMMIT;
