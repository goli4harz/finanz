-- ============================================================================
-- 052 (Haertung Welle 1-3, Phase 5, kritisch): Gap-through-Stop-Felder
-- ============================================================================
-- Ein Stop wurde bisher immer exakt zum Stop-Preis simuliert, auch bei einer
-- Kursluecke ueber den Stop hinweg - unrealistisch guenstig, ueberzeichnete
-- net_pnl/realized_r_multiple systematisch bei jedem echten Gap-Exit.

BEGIN;

ALTER TABLE trading.paper_trades
  ADD COLUMN IF NOT EXISTS raw_exit_price NUMERIC(18,6),
  ADD COLUMN IF NOT EXISTS effective_exit_price NUMERIC(18,6),
  ADD COLUMN IF NOT EXISTS gap_through_stop BOOLEAN NOT NULL DEFAULT FALSE,
  ADD COLUMN IF NOT EXISTS gap_amount NUMERIC(18,6),
  ADD COLUMN IF NOT EXISTS execution_quality TEXT;

COMMENT ON COLUMN trading.paper_trades.raw_exit_price IS
  'Roh-Ausfuehrungspreis vor Slippage/Gebuehren - bei stop_loss gap-bewusst (Open statt Stop, falls die Kerze durch den Stop gap-te), bei target_reached immer exakt der Zielkurs (kein rueckwirkend optimaler Gap-Kurs). Haertung Welle 1-3, Phase 5.';
COMMENT ON COLUMN trading.paper_trades.effective_exit_price IS
  'raw_exit_price minus Slippage/Gebuehren je Aktie in ungueltiger Richtung - reines Audit-/Anzeigefeld, net_pnl wird weiterhin ueber die bereits etablierte wertbasierte Formel berechnet (Fehleranalyse E6/E7).';
COMMENT ON COLUMN trading.paper_trades.gap_through_stop IS
  'TRUE, wenn der Exit-Grund stop_loss war UND die Eroeffnung bereits durch den Stop gap-te (raw_exit_price != stop_price).';
COMMENT ON COLUMN trading.paper_trades.gap_amount IS
  'Betrag der Kursluecke (|Stop - Open|), NULL/0 falls kein Gap-through-Stop vorlag.';
COMMENT ON COLUMN trading.paper_trades.execution_quality IS
  'Kategorisierung des Exits: exact_stop, gap_through_stop, exact_target, close_fallback (time_stop/thesis_expired/opposite_signal - bewusst konservativ ueber den Schlusskurs bewertet).';

INSERT INTO trading.schema_migrations (version, description)
VALUES ('052', 'Gap-through-Stop-Felder auf paper_trades (Haertung Welle 1-3, Phase 5)')
ON CONFLICT (version) DO NOTHING;

COMMIT;
