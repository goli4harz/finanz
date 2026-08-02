-- ============================================================================
-- 054 (Haertung Welle 1-3, Phase 8.1+8.3, kritisch): Scanner-Universum von
-- Watchlist trennen + Stage-B-Analysestatus
-- ============================================================================
-- Bestaetigt: "DB: Universum laden" in 13 ist woertlich identisch mit der
-- Watchlist-Query (stock_instruments WHERE aktiv=TRUE). Additiv, verhaltens-
-- neutral bis zur ersten bewussten Konfigurationsaenderung: watchlist_active/
-- scanner_active werden aus dem bestehenden aktiv-Flag befuellt, das
-- Scanner-Universum bleibt also zunaechst identisch mit der Watchlist -
-- eine Erweiterung (DAX/MDAX/SDAX) ist eine separate, spaetere Entscheidung.

BEGIN;

ALTER TABLE trading.stock_instruments
  ADD COLUMN IF NOT EXISTS watchlist_active BOOLEAN,
  ADD COLUMN IF NOT EXISTS scanner_active BOOLEAN,
  ADD COLUMN IF NOT EXISTS universe_name TEXT,
  ADD COLUMN IF NOT EXISTS liquidity_class TEXT;

UPDATE trading.stock_instruments
SET watchlist_active = aktiv, scanner_active = aktiv, universe_name = 'watchlist'
WHERE watchlist_active IS NULL;

ALTER TABLE trading.stock_instruments
  ALTER COLUMN watchlist_active SET DEFAULT TRUE,
  ALTER COLUMN scanner_active SET DEFAULT TRUE,
  ALTER COLUMN watchlist_active SET NOT NULL,
  ALTER COLUMN scanner_active SET NOT NULL;

COMMENT ON COLUMN trading.stock_instruments.watchlist_active IS
  'Vom Nutzer bewusst beobachteter Titel (bisherige Bedeutung von "aktiv"). Haertung Welle 1-3, Phase 8.1.';
COMMENT ON COLUMN trading.stock_instruments.scanner_active IS
  'Teil des Scanner-Universums (Workflow 13). Aktuell identisch mit watchlist_active befuellt - eine Erweiterung auf ein groesseres Universum (DAX/MDAX/SDAX etc.) ist eine separate, bewusste Entscheidung fuer eine kuenftige Sitzung, siehe docs/MARKTSCANNER.md.';
COMMENT ON COLUMN trading.stock_instruments.universe_name IS
  'Bezeichner des Datenuniversums (z.B. "watchlist", kuenftig z.B. "dax40") - rein informativ/Filterhilfe.';
COMMENT ON COLUMN trading.stock_instruments.liquidity_class IS
  'Schema-vorbereitet fuer eine kuenftige Liquiditaetsklassifizierung des Scanner-Universums (Haertung Welle 1-3, Phase 8.1) - aktuell ungenutzt.';

-- Phase 8.3: Stage-B-Analysestatus - vorher gab es nur ein "included=true"-Flag ohne echten
-- Uebergabepfad an einen Tiefenanalyse-Workflow. analysis_status macht den Zustand explizit
-- abfragbar (pending -> ein kuenftiger Tiefenanalyse-Workflow kann gezielt danach fragen),
-- OHNE selbst schon eine Tiefenanalyse durchzufuehren (die bleibt bewusst nicht Teil dieser
-- Migration - kein Workflow existiert dafuer, siehe FEHLERANALYSE_HAERTUNG_WELLE_1_3.md).
ALTER TABLE trading.scan_candidates
  ADD COLUMN IF NOT EXISTS analysis_status TEXT;

COMMENT ON COLUMN trading.scan_candidates.analysis_status IS
  'NULL fuer Stage-A-only-Zeilen. Fuer stage=B: pending (wartet auf Tiefenanalyse), analyzed, rejected. Kein Workflow verarbeitet diesen Status aktuell automatisch - Struktur ist vorbereitet, der eigentliche Tiefenanalyse-Workflow (Auftrag Phase 8.3) ist noch nicht gebaut (Haertung Welle 1-3, bewusste Zurueckstellung).';

INSERT INTO trading.schema_migrations (version, description)
VALUES ('054', 'Scanner-Universum-Trennung + Stage-B-Analysestatus (Haertung Welle 1-3, Phase 8.1+8.3)')
ON CONFLICT (version) DO NOTHING;

COMMIT;
