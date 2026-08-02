-- ============================================================================
-- 055 (Haertung Welle 1-3, Phase 10, kritisch): MAX_POSITION_VALUE_PCT
-- tatsaechlich durchsetzen statt nur zu protokollieren
-- ============================================================================
-- Bestaetigt: computeRisk() in 06 berechnete theoretical_quantity bisher
-- AUSSCHLIESSLICH aus dem Risikolimit (risk_amount/unit_risk).
-- MAX_POSITION_VALUE_PCT floss nur in das rein informative position_value_pct
-- ein, wurde aber nie als tatsaechliche Obergrenze auf die Stueckzahl
-- angewendet - ein reiner Hinweis statt eines echten Limits.

BEGIN;

ALTER TABLE trading.recommendations
  ADD COLUMN IF NOT EXISTS risk_amount_before_limit NUMERIC(18,6),
  ADD COLUMN IF NOT EXISTS quantity_by_risk INTEGER,
  ADD COLUMN IF NOT EXISTS quantity_by_value INTEGER,
  ADD COLUMN IF NOT EXISTS position_size_limiting_factor TEXT;

COMMENT ON COLUMN trading.recommendations.risk_amount_before_limit IS
  'Urspruenglicher, unbegrenzter theoretischer Risikobetrag (risk_amount = MODEL_PORTFOLIO_VALUE * MAX_RISK_PER_TRADE_PCT), bevor das Wertlimit (MAX_POSITION_VALUE_PCT) ggf. die Stueckzahl reduziert hat. risk_amount selbst ist seit Haertung Welle 1-3 Phase 10 der TATSAECHLICH realisierte Betrag nach Begrenzung.';
COMMENT ON COLUMN trading.recommendations.position_size_limiting_factor IS
  'risk (Risikolimit war bindend) oder value (Wertlimit MAX_POSITION_VALUE_PCT war bindend). Haertung Welle 1-3, Phase 10.';

INSERT INTO trading.schema_migrations (version, description)
VALUES ('055', 'Positionsgroessen-Wertlimit tatsaechlich durchgesetzt (Haertung Welle 1-3, Phase 10)')
ON CONFLICT (version) DO NOTHING;

COMMIT;
