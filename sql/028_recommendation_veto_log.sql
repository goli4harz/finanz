-- ============================================================================
-- Welle 1, Arbeitspaket 5: strukturiertes Veto-Log
-- ============================================================================
-- trading.recommendations.decision_blockers (sql/017) existierte schon, wurde
-- aber nur fuer NICHT-blockierende Hinweise auf bereits geschriebene Zeilen
-- genutzt (z.B. "Trend widerspricht dem Signal"). Ein hartes Veto verhindert
-- per Definition genau das Schreiben einer Zeile - dafuer gibt es bisher
-- keinen Ablageort, die Ablehnung war nur ein console.warn im Execution-Log
-- (siehe Paket 15/17). Dieses Log macht harte Ablehnungen fuer 07/10
-- abfragbar, OHNE die recommendations-Tabelle oder ihre status-Semantik
-- ('offen'/'geschlossen') anzufassen.

CREATE TABLE IF NOT EXISTS trading.recommendation_veto_log (
  id           BIGSERIAL PRIMARY KEY,
  run_id       TEXT,
  ticker       TEXT NOT NULL,
  action       TEXT NOT NULL CHECK (action IN ('oeffnen', 'schliessen')),
  blockers_json JSONB NOT NULL,
  created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_recommendation_veto_log_ticker_created
  ON trading.recommendation_veto_log (ticker, created_at DESC);
CREATE INDEX IF NOT EXISTS ix_recommendation_veto_log_run
  ON trading.recommendation_veto_log (run_id);

COMMENT ON TABLE trading.recommendation_veto_log IS
    'Jeder durch ein hartes Veto (AP5) verhinderte Oeffnen/Schliessen-Versuch, '
    'mit strukturierten Blocker-Objekten ({code,severity,source,message,'
    'observed_value,required_value}). Keine reale Order/kein reales Schreiben '
    'wird hierdurch ausgeloest - reines Audit-Log fuer Dashboard/Report.';
