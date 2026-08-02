-- ============================================================================
-- 048 (Welle-3-Abgleich 2026-08-02, Fund 1/5): financing_cost fehlte komplett
-- ============================================================================
-- Der Welle-3-Auftrag listet financing_cost explizit als eine der
-- deterministisch zu berechnenden Trade-Kennzahlen (AP4). Additiv,
-- NOT NULL DEFAULT 0 - siehe docs/AUSFUEHRUNGSMODELL.md fuer die Begruendung,
-- warum der Wert aktuell immer 0 ist (kein Finanzierungskosten-/Leverage-
-- Modell implementiert, konsistent mit dem bereits bestehenden Hebelprodukt-
-- Disclaimer aus Phase 9: "kein konkretes Produkt - Emittent/Spread/
-- Finanzierungskosten selbst pruefen").

BEGIN;

ALTER TABLE trading.paper_trades
  ADD COLUMN IF NOT EXISTS financing_cost NUMERIC(18,6) NOT NULL DEFAULT 0;

COMMENT ON COLUMN trading.paper_trades.financing_cost IS
  'Welle 3, AP4 (Auftragsvorgabe): Finanzierungskosten (z.B. Haltekosten bei gehebelten/Leerverkaufs-Positionen). Aktuell IMMER 0 - kein konkretes Produkt/Broker mit definiertem Finanzierungssatz wird simuliert (siehe Hebelprodukt-Disclaimer, Phase 9, und docs/AUSFUEHRUNGSMODELL.md). Bereits in net_pnl beruecksichtigt (Formel vollstaendig, Wert aktuell neutral).';

-- Nachtrag: 045 und 046 haben sich entgegen der in 044 festgelegten Konvention
-- nicht selbst in trading.schema_migrations eingetragen (Uebersehen). Beide
-- sind bestaetigt bereits live ausgefuehrt - hier nur nachtraeglich vermerkt,
-- keine erneute Ausfuehrung ihres eigentlichen Inhalts.
INSERT INTO trading.schema_migrations (version, description)
VALUES
  ('045', 'Nachtrag: deterministische run_id + Dedup-Constraints in 14 (Fehleranalyse B9) - bereits vor dieser Zeile live ausgefuehrt'),
  ('046', 'Nachtrag: LEARNING_MIN_NEWS_SAMPLE_SIZE-Seed (Fehleranalyse F3) - bereits vor dieser Zeile live ausgefuehrt'),
  ('048', 'financing_cost auf paper_trades (Welle-3-Abgleich Fund 1/5), aktuell konstant 0')
ON CONFLICT (version) DO NOTHING;

COMMIT;
