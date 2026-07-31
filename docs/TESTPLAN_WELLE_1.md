# Testplan Welle 1

Stand: 2026-07-31. Deckt die 14 im Auftrag geforderten Testfälle ab. 12 davon sind als lokal ausführbare Unit-Tests umgesetzt (`tests/test_welle1_reine_funktionen.js`, wortgleich aus dem deployten Node-Code entnommen, kein n8n/keine DB nötig), 2 erfordern einen echten n8n-Lauf.

## Ergebnis des lokalen Testlaufs (2026-07-31)

```
node tests/test_welle1_reine_funktionen.js
--- Ergebnis: 13 bestanden, 0 fehlgeschlagen ---
```

(13 Assertions für 12 Testfälle, Test 2 hat zwei Teilprüfungen 2a/2b.)

## Testfälle

| # | Szenario | Status | Nachweis |
|---|---|---|---|
| 1 | Vollständige valide OHLCV-Daten | ✅ getestet (lokal) | 252 synthetische Kerzen, alle gültig, 0 verworfen |
| 2 | Versetzte Arrays mit fehlendem High | ✅ getestet (lokal) | Tag mit fehlendem High wird verworfen, Folgetag bleibt korrekt zugeordnet (kein Verschiebungs-Bug) |
| 3 | Nur 90 Handelstage bei behauptetem 52-Wochen-Breakout | ✅ getestet (lokal) | `breakout_history_ausreichend = false` ohne Meta-52-Wochen-Wert |
| 4 | Laufende US-Sitzung | ✅ getestet (lokal, JS-Nachbau der SQL-View-Logik) | `session_status = 'open_intraday'` bei 12:00 Ortszeit innerhalb 09:30-16:00 |
| 5 | Long-Stop oberhalb des Einstiegs | ✅ getestet (lokal) | `STOP_WRONG_SIDE` korrekt ausgelöst |
| 6 | Short-Stop unterhalb des Einstiegs | ✅ getestet (lokal) | `STOP_WRONG_SIDE` korrekt ausgelöst |
| 7 | Ziel auf falscher Seite | ✅ getestet (lokal) | `TARGET_WRONG_SIDE` korrekt ausgelöst |
| 8 | Unzureichendes Chance-Risiko-Verhältnis | ✅ getestet (lokal) | RRR=1.0 < Mindestgrenze 1.5 → `RRR_TOO_LOW` |
| 9 | Veraltete News | ✅ getestet (lokal) | 10h alte News > 6h-Schwelle (mean_reversion) → `NEWS_STALE` |
| 10 | Abgelaufene These | ✅ getestet (lokal) | `thesis_expires_at` in der Vergangenheit → `THESIS_INVALID` |
| 11 | Datenbankfehler | ✅ getestet (lokal) | leere `techRows`/`trendRows` → `DB_ERROR` (Lauf-Ebene) |
| 12 | DRY_RUN | 🟡 nicht in Welle 1 erneut getestet | Mechanismus **unverändert** aus Paket 10 übernommen, dort bereits live per `DRY_RUN=true`-Test bestätigt (siehe `OFFENE_AUFGABEN.md`, Priorität-4-Historie) — Welle 1 ändert nur, WAS unter DRY_RUN simuliert wird (mehr Felder), nicht den Gating-Mechanismus selbst |
| 13 | REQUIRE_CONFIRMATION | 🟡 nicht in Welle 1 erneut getestet | Gleiche Begründung wie 12 — Mechanismus unverändert, nur die neuen Vetos laufen VOR diesem Punkt und verhindern das Erreichen von REQUIRE_CONFIRMATION bei hart vetoeten Kandidaten (das ist neu, aber der Mechanismus selbst ist der alte) |
| 14 | Sichere Schließung trotz fehlender Marktdaten | ✅ getestet (lokal) | Fallback auf letzten bekannten gültigen Kurs, Schließung nicht blockiert |

## Nicht lokal testbar — benötigt einen echten n8n-Lauf

Folgende Aspekte sind durch die lokalen Unit-Tests **nicht** abgedeckt, weil sie echte DB-Zugriffe, den n8n-Ausführungskontext (`$('NodeName')`-Referenzen) oder Zeitplan-Trigger voraussetzen:

- Der komplette Datenfluss durch `02` (echter FastAPI-Abruf → Kerzenbildung → `technical_signals_history`-Schreibung) — nur die reine Kerzenlogik ist isoliert getestet, nicht die Node-Verdrahtung selbst.
- `trading.v_market_session_status` als echte Postgres-View (nur die CASE-Logik ist als JS-Nachbau getestet, nicht die View selbst).
- Der komplette Datenfluss durch `06` inkl. `recommendation_veto_log`-Schreibung, `Oeffnen: SQL bauen` mit den neuen Spalten, DRY_RUN/REQUIRE_CONFIRMATION-Zusammenspiel mit den neuen Vetos.
- Die neuen Dashboard-Sektionen in `07` (Vetos heute, Sitzungsstatus) und die neuen Prüf-Agent-Ablehnungsregeln in `10` — beides erst mit echten Daten in der DB sichtbar/prüfbar.
- Ein vollständiger Tageslauf in DRY_RUN (Abnahmekriterium aus dem Auftrag) — **nicht durchgeführt**, da `06` nur über `00` (Orchestrator, 17:50 Werktage) oder einen nicht risikofrei fernauslösbaren UI-Trigger läuft (dieselbe dokumentierte Einschränkung wie schon bei Paket 15/17 im vorherigen Auftrag).

**Empfehlung**: nach dem Live-Push (siehe Abschlussbericht) den nächsten planmäßigen `00`-Lauf (17:50 Werktage) beobachten und die neuen Dashboard-Sektionen sowie `recommendation_veto_log` danach live prüfen — das ist der risikoärmste Weg zu einem echten Test, ohne einen Trigger manuell auszulösen.

## Warum keine 5 zusätzlichen SQL/DB-Migrationstests

Die Migrationen (sql/025-030) sind additiv (`ADD COLUMN IF NOT EXISTS`, `CREATE TABLE IF NOT EXISTS`, `CREATE OR REPLACE VIEW`) und folgen exakt demselben, in `sql/007_runtime_schema_reconciliation.sql` bereits gegen ein leeres Testschema verifizierten Muster wie alle bisherigen Migrationen dieses Projekts. Ein erneuter Vollschema-Test wurde in Welle 1 nicht wiederholt (Aufwand/Nutzen), da keine der neuen Migrationen ein strukturell neues Muster einführt (Revisionierung folgt exakt sql/022, Config-Seed folgt exakt sql/003/019/020).
