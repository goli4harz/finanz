-- ============================================================================
-- 044 (Fehleranalyse G1, mittel, Haertungsauftrag 2026-08-02): Migrations-
-- protokoll-Tabelle
-- ============================================================================
-- Bisher einziger Nachweis ueber bereits gelaufene Migrationen war Prosa in
-- OFFENE_AUFGABEN.md/FEHLERANALYSE.md - keine maschinenlesbare, aus der DB
-- selbst pruefbare Quelle. Migrationen laufen in diesem Projekt durchgehend
-- per Copy&Paste in Workflow 97 (Einmalig - Beliebige Query ausfuehren) und
-- manuellem Klick durch den Nutzer - Workflow 99 (Einmalig - SQL-Migration
-- ausfuehren) ist ein Relikt aus der allerersten Migration (001) und wurde
-- seit Migration 002 nicht mehr verwendet, deshalb hier NICHT erweitert.
--
-- WICHTIG - Grenzen dieser Loesung: eine ECHTE automatische Doppellauf-Sperre
-- (die einen erneuten Lauf verweigert) wuerde eigene Tooling-Infrastruktur
-- brauchen (ein Skript, das sql/*.sql der Reihe nach einliest, gegen diese
-- Tabelle prueft und nur fehlende Dateien ausfuehrt) - das ist mit dem
-- aktuellen "SQL einfuegen, Node ausfuehren"-Modell von Workflow 97 nicht
-- gegeben. Diese Migration legt nur die Tabelle an; ob eine echte
-- Sperr-Automatisierung gebaut werden soll, ist eine eigene, groessere
-- Entscheidung (siehe FEHLERANALYSE.md G1).
--
-- Konvention ab jetzt: jede kuenftige sql/0XX_*.sql-Datei endet mit einer
-- eigenen INSERT-Anweisung in diese Tabelle (Beispiel unten). Migrationen
-- 001-043 werden NICHT rueckwirkend eingetragen - die exakten Ausfuehrungs-
-- zeitpunkte sind nicht zuverlaessig rekonstruierbar (mehrere liefen nicht in
-- einer einzelnen Sitzung, teils mit manuellen Zwischenschritten).

CREATE TABLE IF NOT EXISTS trading.schema_migrations (
    version     TEXT PRIMARY KEY,
    applied_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    checksum    TEXT,
    description TEXT
);

COMMENT ON TABLE trading.schema_migrations IS
    'Protokoll bereits ausgefuehrter sql/*.sql-Migrationen (Fehleranalyse G1). Rueckwirkend nur ab 044 gepflegt, 001-043 nicht rekonstruiert. Jede kuenftige Migration traegt sich am Ende selbst ein.';

INSERT INTO trading.schema_migrations (version, description)
VALUES ('044', 'Migrationsprotokoll-Tabelle selbst (Fehleranalyse G1)')
ON CONFLICT (version) DO NOTHING;
