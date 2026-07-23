# Offene Aufgaben

Stand: 2026-07-24

## Priorität 1

- Den nächsten regulären Lauf von `08 – News-Wirkungsanalyse` um 19:00 Uhr kontrollieren. Erwartung: Der zuvor auftretende Abhängigkeitsfehler ist behoben und der Lauf endet erfolgreich.
- Anschließend einen vollständigen automatischen Tageslauf über den Orchestrator `00` bis zum Reportversand prüfen.

## Priorität 2

- Seltene Ablaufpfade gezielt testen:
  - SMTP-E-Mail-Versand
  - Ablehnungs- und DRY_RUN-Pfad in Workflow `05`
  - Fehler- und Retry-Pfade
- `sql/007_runtime_schema_reconciliation.sql` gegen eine leere Testdatenbank ausführen und die vollständige Reproduzierbarkeit des Schemas bestätigen.

## Priorität 3

- Veraltete Aussagen in `README.md` und `MIGRATIONSPLAN_AGENTEN.md` zu Authentifizierung, Aktivierung und Teststatus bereinigen.
- Optional einen kontrollierten Freigabe-/Aktivierungsworkflow für die von Workflow `09` erzeugten Lernvorschläge bauen. Gewichtungen dürfen dabei nicht ungeprüft automatisch aktiviert werden.

## Bereits erledigt

- Status- und Watchlist-Webseiten sind im LAN ohne Webhook-Authentifizierung erreichbar.
- Ticker können über die Watchlist-Webseite angelegt, bearbeitet, aktiviert, deaktiviert und nach Bestätigung gelöscht werden.
- Beim Ändern oder Löschen werden `trading.watchlist` und `trading.stock_instruments` synchron gehalten.
