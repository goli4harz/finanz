-- ============================================================================
-- 063: Fix trading.recommendations_status_check - fehlende Statuswerte aus
-- Migration 053 nachziehen
-- ============================================================================
-- Bestaetigter Fund (2026-08-17, erster echter Live-Test nach Reaktivierung
-- des Orchestrators): Migration 053 (Haertung Welle 1-3, Phasen 6+7) fuehrte
-- den Portfolioveto-Zwischenstatus 'portfolio_pending' sowie die Folgestaende
-- 'portfolio_blocked' und 'portfolio_check_failed' im Code ein (Workflow 06
-- "Oeffnen: SQL bauen", Workflow 14 "Job A: Portfoliopruefung + Trade-Anlage"),
-- vergass aber, die bestehende CHECK-Beschraenkung
-- recommendations_status_check entsprechend zu erweitern. Die Beschraenkung
-- erlaubte weiterhin nur 'offen'/'geschlossen' - jeder Versuch, eine
-- Empfehlung bei aktivem ENABLE_PAPER_TRADING zu oeffnen, scheiterte seit
-- dem 2. August an genau dieser Beschraenkung:
--   "new row for relation "recommendations" violates check constraint
--    "recommendations_status_check""
-- Live bestaetigt anhand eines echten Kandidaten (EOAN.DE, 2026-08-17).

BEGIN;

ALTER TABLE trading.recommendations
    DROP CONSTRAINT IF EXISTS recommendations_status_check;

ALTER TABLE trading.recommendations
    ADD CONSTRAINT recommendations_status_check
    CHECK (status = ANY (ARRAY[
        'offen'::text,
        'geschlossen'::text,
        'portfolio_pending'::text,
        'portfolio_blocked'::text,
        'portfolio_check_failed'::text
    ]));

INSERT INTO trading.schema_migrations (version, description)
VALUES ('063', 'Fix recommendations_status_check - fehlende Statuswerte aus Migration 053 nachgezogen (portfolio_pending/portfolio_blocked/portfolio_check_failed)')
ON CONFLICT (version) DO NOTHING;

COMMIT;
