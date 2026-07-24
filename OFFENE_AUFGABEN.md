# Offene Aufgaben

Stand: 2026-07-24

## Priorität 1 (erledigt, 2026-07-24)

- ✅ `08 – News-Wirkungsanalyse` lief am 24.07. automatisch um 19:00 Uhr erfolgreich durch (kein Fehler-Eintrag, anders als an den drei Tagen zuvor mit `error, mode:trigger` um 17:00 UTC) — die 3-Tage-Fehlserie ist durchbrochen, der Abhängigkeitsfehler ist behoben.
- ✅ Automatischer Taglauf über `00` (17:50 Uhr) lief bis zum Prüfagenten durch; dieser lehnte den Report inhaltlich begründet ab (Konfidenz 41) — das ist die vorgesehene Governance-Funktion, kein Fehler.

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
