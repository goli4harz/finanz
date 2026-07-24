# Offene Aufgaben

Stand: 2026-07-24

## Priorität 1 (erledigt, 2026-07-24)

- ✅ `08 – News-Wirkungsanalyse` lief am 24.07. automatisch um 19:00 Uhr erfolgreich durch (kein Fehler-Eintrag, anders als an den drei Tagen zuvor mit `error, mode:trigger` um 17:00 UTC) — die 3-Tage-Fehlserie ist durchbrochen, der Abhängigkeitsfehler ist behoben.
- ✅ Automatischer Taglauf über `00` (17:50 Uhr) lief bis zum Prüfagenten durch; dieser lehnte den Report inhaltlich begründet ab (Konfidenz 41) — das ist die vorgesehene Governance-Funktion, kein Fehler.

## Priorität 2

- ✅ Ablehnungs- und DRY_RUN-Pfad in Workflow `05` getestet (2026-07-24, per pinData auf `Execute Workflow Trigger`, danach zurückgesetzt): Ablehnung → `{ok:false, status:'failed'}` inkl. korrektem Matrix-Fehler-Alert; DRY_RUN → `{ok:true, status:'skipped'}`, kein echter Versand, sauber getaggt. Beide wie erwartet.
- ✅ Fehler-Pfade in `05` geprüft: `onError:continueRegularOutput` korrekt auf allen drei Sende-Nodes (Matrix-Report, E-Mail, Matrix-Fehler-Alert) gesetzt, wie in Priorität 6 spezifiziert. Echtes automatisches Node-Retry existiert bewusst nicht (API lehnt node-level `retryOnFail`/`maxTries` beim Push ab, siehe README) — bekannte, akzeptierte Grenze, kein offener Test.
- Noch offen: SMTP-E-Mail-Versand erneut bestätigen (optional, war in einer früheren Session schon einmal isoliert bestätigt).
- `sql/007_runtime_schema_reconciliation.sql` gegen eine leere Testdatenbank ausführen und die vollständige Reproduzierbarkeit des Schemas bestätigen.

## Priorität 3

- ✅ Veraltete Aussagen in `README.md` und `MIGRATIONSPLAN_AGENTEN.md` bereinigt (2026-07-24): `07`s Status-Übersicht fälschlich noch als "mit Header-Token" geführt (tatsächlich seit 07-23 ohne Auth), `05`s DRY_RUN-/Ablehnungs-Zweig noch als "ungetestet" vermerkt (heute bestätigt getestet). Aktivierungsstatus (`02`/`02b`/`05`/`06` eigene Trigger deaktiviert) live geprüft und stimmt weiterhin.
- Noch offen (optional): kontrollierter Freigabe-/Aktivierungsworkflow für die von Workflow `09` erzeugten Lernvorschläge. Gewichtungen dürfen dabei nicht ungeprüft automatisch aktiviert werden.

## Bereits erledigt

- Status- und Watchlist-Webseiten sind im LAN ohne Webhook-Authentifizierung erreichbar.
- Ticker können über die Watchlist-Webseite angelegt, bearbeitet, aktiviert, deaktiviert und nach Bestätigung gelöscht werden.
- Beim Ändern oder Löschen werden `trading.watchlist` und `trading.stock_instruments` synchron gehalten.
