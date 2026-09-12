-- ============================================================================
-- 088 - trading.simulation_decision_log.decision: CHECK-Constraint um
-- 'SHADOW_LOGGED' erweitert (LIVE_PARITY Schritt 4L.3 Preflight, 2026-09-12).
-- ============================================================================
-- Der additive Shadow-Node aus Schritt 4L/4L.2 (AVAILABLE_DATA_LIVE_REPLAY-Modus,
-- "Verarbeite Tage-Paket") schreibt decision='SHADOW_LOGGED' fuer jede Shadow-
-- Entscheidung - bewusst ein NEUER, eindeutig erkennbarer Wert (siehe Code-
-- Kommentar dort), nicht ACCEPTED/REJECTED/BLOCKED/NO_FILL, damit Shadow- und
-- Research-Zeilen niemals in denselben Feldern zusammengefuehrt werden.
--
-- Der urspruengliche CHECK-Constraint aus Migration 084 kannte diesen Wert noch
-- nicht (SHADOW_LOGGED existierte zu dem Zeitpunkt im Code noch nicht) und wurde
-- seither nie erweitert (087 hat nur Spalten ergaenzt, den Constraint nicht
-- angefasst). Gefunden beim 4L.2-Abschlussaudit (2026-09-12, DB-seitiger
-- Shadow-Row-Nachweis fuer Runs 31/33, beide 0 wie erwartet - aber aus dem
-- falschen Grund fuer einen kuenftigen echten Replay-Lauf): jeder Versuch, eine
-- Shadow-Zeile zu inserten, waere an diesem Constraint gescheitert und haette
-- (der SQL-Builder "Baue SQL fuer Paket-Ergebnisse" erzeugt pro Tage-Paket ein
-- einziges Multi-Statement, das Postgres implizit als eine Transaktion
-- ausfuehrt) das gesamte Paket-Ergebnis dieses Tages mitgerissen - nie
-- beobachtet, weil AVAILABLE_DATA_LIVE_REPLAY vor Schritt 4L.3 noch nie ueber
-- den regulaeren Startpfad gelaufen ist.
--
-- Rein additiv: DROP + erneutes ADD desselben Constraint-Namens mit einem Wert
-- mehr, keine bestehende Zeile/Spalte betroffen (alle bisherigen Werte bleiben
-- gueltig, kein Backfill noetig).
-- ============================================================================

BEGIN;

ALTER TABLE trading.simulation_decision_log DROP CONSTRAINT simulation_decision_log_decision_check;
ALTER TABLE trading.simulation_decision_log ADD CONSTRAINT simulation_decision_log_decision_check
  CHECK (decision IN ('ACCEPTED','REJECTED','BLOCKED','NO_FILL','SHADOW_LOGGED'));

INSERT INTO trading.schema_migrations (version, description)
VALUES ('088', 'trading.simulation_decision_log.decision: CHECK-Constraint um SHADOW_LOGGED erweitert - 4L.3-Preflight-Fund, Shadow-Inserts waeren zuvor an jedem betroffenen Tage-Paket gescheitert')
ON CONFLICT (version) DO NOTHING;

COMMIT;
