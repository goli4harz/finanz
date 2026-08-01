-- ============================================================================
-- 039_paper_trading_workflow14_haertung.sql
--
-- Haertungsauftrag Teil E (Fehleranalyse E3, E4, E7, E8, E12) - additive
-- Ergaenzungen fuer Workflow 14 (Portfolio-Risiko und Paper-Trading), keine
-- bestehende Spalte/Zeile wird veraendert oder geloescht.
--
-- E4: sektor fehlte komplett auf paper_trades - das Sektorlimit in Job A
--     (14) verglich Kandidaten nie gegen bereits offene Positionen desselben
--     Sektors, weil das Feld dort schlicht nie ankam.
-- E7: entry_fee_amount/entry_slippage_amount fehlten - beim Trade-Close
--     wurden nur die Ausstiegskosten von net_pnl abgezogen, die bereits beim
--     Fill berechneten Einstiegskosten gingen nie in Nettoergebnis/R-Multiple
--     ein. Jetzt am Fill-Zeitpunkt auf der Zeile gespeichert, beim Close
--     wieder ausgelesen.
-- E8: data_error_count/data_error_first_at/data_error_last_at fehlten -
--     ein auf 'data_error' gesetzter Trade wurde nie wieder geladen (siehe
--     WHERE-Klausel in "DB: Ausstehende/offene Paper-Trades laden"), es gab
--     keinen Retry-Zaehler und keine Eskalation nach Ausschoepfung. Neuer
--     Endzustand 'data_error_final' fuer die Eskalation nach MAX_RETRIES.
-- E3:  sequence_index/portfolio_state_snapshot_json auf
--     portfolio_risk_checks fehlten - Reihenfolge und Vorher/Nachher-Zustand
--     der einzelnen Pruefungen eines Laufs waren nicht nachvollziehbar.
-- E12: kein UNIQUE-Constraint auf paper_trade_costs - ein Retry nach einem
--     Teilfehler konnte doppelte Kostenzeilen fuer denselben Trade/Kostentyp
--     erzeugen.
--
-- Wiederholbar/idempotent: ADD COLUMN IF NOT EXISTS, CHECK-Constraint nur
-- erweitert falls noch nicht vorhanden (wie sql/038). Keine Migration von
-- Bestandsdaten noetig (alle neuen Spalten sind NULL-faehig bzw. haben einen
-- neutralen Default).
-- ============================================================================

ALTER TABLE trading.paper_trades
    ADD COLUMN IF NOT EXISTS sektor TEXT,
    ADD COLUMN IF NOT EXISTS entry_fee_amount NUMERIC(18,6),
    ADD COLUMN IF NOT EXISTS entry_slippage_amount NUMERIC(18,6),
    ADD COLUMN IF NOT EXISTS data_error_count INTEGER NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS data_error_first_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS data_error_last_at TIMESTAMPTZ;

COMMENT ON COLUMN trading.paper_trades.sektor IS
    'Snapshot aus trading.recommendations.sektor zum Eroeffnungszeitpunkt (sector_at_entry-Muster) - noetig, damit Job A (14) das Sektorlimit gegen tatsaechlich offene Positionen pruefen kann.';
COMMENT ON COLUMN trading.paper_trades.entry_fee_amount IS
    'Beim Fill berechnete Eintrittsgebuehr - wird beim Close zusaetzlich zu den Austrittskosten von net_pnl abgezogen (Fehleranalyse E7).';
COMMENT ON COLUMN trading.paper_trades.entry_slippage_amount IS
    'Beim Fill berechnete Eintritts-Slippage - wird beim Close zusaetzlich zu den Austrittskosten von net_pnl abgezogen (Fehleranalyse E7).';
COMMENT ON COLUMN trading.paper_trades.data_error_count IS
    'Anzahl aufeinanderfolgender Laeufe ohne gueltige Tageskerze fuer diesen Trade - Retry-Zaehler statt dauerhaftem Stillstand (Fehleranalyse E8).';

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'paper_trades_status_check'
          AND pg_get_constraintdef(oid) LIKE '%data_error_final%'
    ) THEN
        ALTER TABLE trading.paper_trades DROP CONSTRAINT IF EXISTS paper_trades_status_check;
        ALTER TABLE trading.paper_trades ADD CONSTRAINT paper_trades_status_check
            CHECK (status IN ('proposed','blocked','awaiting_confirmation','open','closed','expired_unfilled','cancelled','data_error','data_error_final'));
    END IF;
END $$;

COMMENT ON COLUMN trading.paper_trades.status IS
    'data_error = fehlende Tageskerze, wird bis MAX_DATA_ERROR_RETRIES erneut versucht (data_error_count). data_error_final = Retries ausgeschoepft, in trading.workflow_errors eskaliert, wird nicht mehr automatisch neu geladen (Fehleranalyse E8).';

ALTER TABLE trading.portfolio_risk_checks
    ADD COLUMN IF NOT EXISTS sequence_index INTEGER,
    ADD COLUMN IF NOT EXISTS portfolio_state_snapshot_json JSONB;

COMMENT ON COLUMN trading.portfolio_risk_checks.sequence_index IS
    'Position dieser Pruefung innerhalb des Laufs (deterministische Sortierreihenfolge, Fehleranalyse E1/E3).';
COMMENT ON COLUMN trading.portfolio_risk_checks.portfolio_state_snapshot_json IS
    'Vorher/Nachher-Zustand der geprueften Dimensionen (offene Positionen, Sektor-/Richtungswert, Korrelation) - macht die Fortschreibung aus Fehleranalyse E2 nachvollziehbar.';

-- E12: Idempotenz fuer Kostenzeilen - ein Retry nach einem Teilfehler darf denselben
-- Kostentyp fuer denselben Trade nicht doppelt anlegen. Bestehende Zeilen koennten
-- theoretisch bereits Duplikate enthalten (vor diesem Fix nicht verhindert) - der Index
-- wird nur erstellt, wenn er noch nicht existiert; ein Duplikat wuerde CREATE UNIQUE INDEX
-- fehlschlagen lassen und sichtbar machen statt es zu verschleiern.
CREATE UNIQUE INDEX IF NOT EXISTS ux_paper_trade_costs_trade_costtype
    ON trading.paper_trade_costs (trade_id, cost_type);
