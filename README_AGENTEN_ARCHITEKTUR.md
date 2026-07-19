# Agentenarchitektur Aktienanalyse-System — README

Dieses Dokument beschreibt den Zielzustand nach dem Umbau auf `agenten-modernisierung` und alles, was zur Inbetriebnahme nötig ist. Ausgangsdokumente: `ARCHITEKTUR_BESTAND.md` (Ist-Zustand), `MIGRATIONSPLAN_AGENTEN.md` (Umsetzungsplan je Phase), `TESTPLAN_AGENTEN.md` (Testfälle).

## Architekturüberblick

```
00 – Tagesabschluss-Orchestrator (17:50 Werktage)
│   erzeugt run_id, protokolliert jede Stufe in trading.pipeline_runs
│
├── 02b – Marktumfeld täglich – Orchestriert   (per Execute Workflow)
├── 02 – Technische Signale täglich – Orchestriert
├── 06 – Empfehlungswatchlist – Agent V1
├── 10 – Report- und Prüfagent                 (Report-Agent + Prüf-Agent in einem Workflow)
└── 05 – Tagesreport – Agent V1                 (nur bei approved=true, sonst Matrix-Warnung)

03 – News Ingestion stündlich – Agent V1  (eigener Zeitplan, unabhängig)
   → trading.news_items / trading.news_assessments
03a – News-Recherche-Agent (alle 2h)      (Zweitpass bei wirkungsebene='unklar')
04 – Cleanup News-Tabellen – Agent V1     (23:45 Mo-Fr / Sa 00:15)

08 – News-Wirkungsanalyse (19:00 Werktage, nach 02/02b)
   → trading.news_impact_tracking (D+1/D+3/D+5/D+10/D+20 je News+Ticker)
09 – Lernagent Newswirkung (Samstag 08:00)
   → trading.learning_rule_proposals (nur status='proposed')

07 – Status-Uebersicht – Agent V1 (Webhook, jetzt mit Header-Token)
01 – Fundamentaldaten täglich (06:00, unverändert — rein deterministisch, kein Agentenbedarf)
```

`01` und die Kernlogik von `02`/`02b` bleiben **unverändert** (rein deterministische Berechnung, kein KI-Einsatz nötig oder sinnvoll). `02b`/`02` haben lediglich einen zusätzlichen `Execute Workflow Trigger`-Einstiegspunkt bekommen (Dateien mit Suffix „– Orchestriert“), damit der Orchestrator sie aufrufen kann — die eigentliche Berechnungslogik ist byte-identisch zum Original.

## Neu erstellte Dateien

```
ARCHITEKTUR_BESTAND.md
MIGRATIONSPLAN_AGENTEN.md
TESTPLAN_AGENTEN.md
README_AGENTEN_ARCHITEKTUR.md (dieses Dokument)

00 – Tagesabschluss-Orchestrator.json
03a – News-Recherche-Agent.json
08 – News-Wirkungsanalyse.json
09 – Lernagent Newswirkung.json
10 – Report- und Prüfagent.json
99 – Einmalig – SQL-Migration ausfuehren.json   (Wegwerf-Workflow, nach einmaliger Ausführung löschbar)

sql/001_agenten_architektur.sql
```

## Geänderte Dateien (als „– Agent V1“ / „– Orchestriert“, Originale unverändert erhalten)

```
02b – Marktumfeld täglich – Orchestriert.json    (nur Execute-Workflow-Trigger ergänzt)
02 – Technische Signale täglich – Orchestriert.json   (nur Execute-Workflow-Trigger ergänzt)
03 – News Ingestion stündlich – Agent V1.json
04 – Cleanup News-Tabellen – Agent V1.json
05 – Tagesreport – Agent V1.json
06 – Empfehlungswatchlist – Agent V1.json
07 – Status-Uebersicht – Agent V1.json
```

## Nicht veränderte Originaldateien

```
01 – Fundamentaldaten täglich.json
02 – Technische Signale täglich.json   (Original bleibt als Rollback-Basis, siehe unten)
02b – Marktumfeld täglich (1).json     (Original bleibt als Rollback-Basis)
03 – News Ingestion stündlich.json
04 – Cleanup News-Tabellen.json
05 – Tagesreport.json
06 – Empfehlungswatchlist.json
07 – Status-Uebersicht.json
```

Alle sieben liegen unverändert im Baseline-Commit `40e5575` auf `main` und zusätzlich unverändert im ersten Commit des `agenten-modernisierung`-Branches.

## Benötigte n8n Credentials

| Credential-Name (Platzhalter im Workflow) | Typ | Verwendung |
|---|---|---|
| `Postgres – Trading (TODO Credential zuweisen)` | Postgres | Alle neuen `n8n-nodes-base.postgres`-Nodes (executeQuery) in 00, 03, 03a, 04, 06, 07, 08, 09, 10, 99 |
| `Status-Webhook Token (TODO Credential zuweisen)` | Header Auth | Absicherung des Status-Webhooks in 07 |
| `Header Auth account` (bereits vorhanden, ID `od1pN1F5wy2irSDs`) | Header Auth | Alle Matrix-Sends (unverändert aus den Originalen übernommen) |
| `OpenAI account` (bereits vorhanden, ID `RiT1gwJpQWzSo6NO`) | OpenAI API | Alle neuen KI-Nodes (03, 03a, 09, 10) |
| `SMTP account` (bereits vorhanden, ID `9z1hWYlOfxcO8avw`) | SMTP | E-Mail-Versand in 05 (unverändert) |

**Kein Zugangsdatenwert steht in irgendeiner Workflow-Datei.** Die beiden neuen Credentials (Postgres, Status-Webhook-Token) müssen einmalig in n8n angelegt und in jedem betroffenen Node manuell zugewiesen werden (n8n ersetzt Platzhalter-Credential-IDs beim Import nicht automatisch).

## Benötigte Umgebungsvariablen / offene Platzhalter

- **Postgres-Verbindungsdetails** (Host, Port, Datenbankname, Benutzer, Passwort): nicht bekannt zum Zeitpunkt dieser Migration, werden ausschließlich über die oben genannte n8n-Credential konfiguriert, nirgends im Code.
- **`DRY_RUN`**: wird als Execute-Workflow-Input-Parameter durchgereicht (00 → 06, 00 → 05), Default `false`. Für einen produktionsnahen Test ohne echten Matrix-/E-Mail-Versand `DRY_RUN=true` beim manuellen Start von `00` setzen.
- **`REQUIRE_CONFIRMATION`** (06): aktuell als Konstante `false` im Code gesetzt (siehe „Trigger-Eingabe normalisieren“-Node in 06) — kann bei Bedarf zu einem echten Konfigurationswert gemacht werden (z. B. Zeile in `trading.stock_instruments.metadata_json` oder eine eigene Einstellungstabelle), war im Auftrag nur als „optional“ gefordert.

## Datenbankmigration

1. `sql/001_agenten_architektur.sql` ist idempotent (`CREATE ... IF NOT EXISTS` durchgehend) — kann gefahrlos mehrfach laufen.
2. Ausführung: `99 – Einmalig – SQL-Migration ausfuehren.json` einmalig importieren, Postgres-Credential zuweisen, „Test workflow“ ausführen. Danach löschbar (oder als Referenz behalten, schadet nicht — der Migrationslauf selbst ist idempotent, könnte auch stehen bleiben und erneut ausgeführt werden).
3. **Nur statisch geprüft** — kein Testlauf gegen eine echte Datenbank, da kein bestätigter Zugang vorlag. Vor Produktivbetrieb einmal manuell verifizieren.
4. `stock_price_history` (n8n Data Table) bleibt unverändert bestehen; die neue Wirkungsanalyse (08) nutzt stattdessen `stock_technical_signals`/`stock_market_context` als Kursquelle (siehe MIGRATIONSPLAN_AGENTEN.md, „Offener Klärungspunkt vor Phase 6“ — durch die tatsächliche Umsetzung bereits aufgelöst, dort aber aus Nachvollziehbarkeit stehen gelassen).

## Importreihenfolge — bereits erledigt (Stand 2026-07-19)

Alle 15 Workflows wurden bereits über die n8n REST API als **neue, separate, inaktive** Workflows angelegt (nicht als Ersatz der laufenden Originale). Reale n8n-Workflow-IDs:

| Datei | n8n-ID |
|---|---|
| `00 – Tagesabschluss-Orchestrator` | `ncMZzkqDHpSiDGPm` |
| `02b – Marktumfeld täglich – Orchestriert` | `9zO3uZeZeakTnLnX` |
| `02 – Technische Signale täglich – Orchestriert` | `vgT6IrPp3ATaJg8s` |
| `03 – News Ingestion stündlich – Agent V1` | `kXfFAy97N6xgRgQ5` |
| `03a – News-Recherche-Agent` | `SUNb1rfSUTQGUTPN` |
| `04 – Cleanup News-Tabellen – Agent V1` | `3aeFh4tfDrCi4dUm` |
| `05 – Tagesreport – Agent V1` | `VRr5jIHj7G7dsMwi` |
| `06 – Empfehlungswatchlist – Agent V1` | `aguWZUolRizBnsj4` |
| `07 – Status-Uebersicht – Agent V1` | `7hQ3t6KrSo9uDNML` |
| `08 – News-Wirkungsanalyse` | `EvJKlqkuSIu9CHmR` |
| `09 – Lernagent Newswirkung` | `LjZHC5g7thqcCElo` |
| `10 – Report- und Prüfagent` | `BFlxfLyarzR2xbBT` |
| `98 – Einmalig – Postgres-Verbindungstest` | `rp35CZNrjp4BLrR6` |
| `99 – Einmalig – SQL-Migration ausfuehren` | `8PHV9RfaXjfTo3ZK` |

Alle `Execute Workflow`-Referenzen in `00` und `05` nutzen bereits diese echten IDs (in den Git-Dateien nachgetragen). Verbleibende manuelle Schritte in n8n selbst:

1. Postgres-Credential über `98 – Einmalig – Postgres-Verbindungstest` anlegen und verifizieren.
2. Dieselbe Credential in allen `executeQuery`-Nodes der übrigen Workflows zuweisen (n8n zeigt sie bis dahin mit fehlender Credential als Fehler an — erwartet).
3. `99 – Einmalig – SQL-Migration ausfuehren` einmal ausführen.
4. Status-Webhook-Token-Credential anlegen und in `07` zuweisen.
5. Jeden Workflow einzeln testen (siehe Testreihenfolge unten), erst danach aktivieren.
6. Alte Schedule-Trigger in den Original-Workflows `02b`/`02`/`05`/`06` bewusst weiterlaufen lassen, bis die neuen Versionen erfolgreich getestet sind — dann dort deaktivieren, um Doppelläufe zu vermeiden.

**Bekannte Einschränkung beim Live-Push:** die strikte Workflow-Create-API akzeptiert kein node-level `"settings"`-Feld (z. B. `retryOnFail`/`maxTries` an einzelnen `httpRequest`-Nodes), obwohl das UI-Export-Format es enthält — dieses Feld wurde nur für den API-Push entfernt, die Git-Dateien selbst enthalten es unverändert. Betroffene Nodes haben dadurch in der jetzt live angelegten Version keine node-eigene Retry-Konfiguration (ihre `neverError`/Fehlerbehandlung auf HTTP-Ebene bleibt aber erhalten) — bei Bedarf in der n8n-UI manuell nachtragen.

## Testreihenfolge

Siehe `TESTPLAN_AGENTEN.md` für alle Einzelfälle. Empfohlene Grobreihenfolge:
1. `03` isoliert testen (RSS→Dedup→Insert→KI→Assessment), dann `03a` mit einem künstlich auf `wirkungsebene='unklar'` gesetzten Datensatz.
2. `08` mit mindestens 2-3 Handelstagen realer `stock_technical_signals`-Historie testen (D+1 sollte dann befüllbar sein).
3. `09` erst sinnvoll testbar, sobald mindestens einige `news_impact_tracking`-Zeilen `status='completed'` erreicht haben — in der Anfangsphase wird der Bericht mangels Fallzahl leer/fast leer sein, das ist korrektes Verhalten (Mindestfallzahlen-Regel), kein Fehler.
4. `10` isoliert mit einem manuell gesetzten `run_id` testen, dann `06`, dann den kompletten `00`-Durchlauf.
5. `07` zuletzt, da es von allen anderen Tabellen liest.

## Rollback-Anleitung

- **Vollständiger Rollback auf den Ist-Zustand**: `git checkout main` im Repo `finanz` — der `main`-Branch enthält ausschließlich den unveränderten Ist-Stand (Commit `40e5575`), keine der neuen Dateien. In n8n die dort laufenden Original-Workflows unverändert weiter aktiv lassen (sie wurden durch diese Migration nicht angefasst).
- **Teilweiser Rollback**: da jede neue/geänderte Datei ein eigener, unabhängig importierbarer Workflow ist, kann z. B. nur `00 – Tagesabschluss-Orchestrator` deaktiviert werden, während `03`/`08`/`09` (News-Pipeline + Lernprozess) weiterlaufen — die alten `02b`/`02`/`05`/`06`-Originale mit ihren eigenen Schedule-Triggern funktionieren unabhängig vom Orchestrator weiter, solange sie nicht deaktiviert wurden.
- **Datenbank-Rollback**: `sql/001_agenten_architektur.sql` legt ausschließlich NEUE Tabellen im Schema `trading` an, verändert oder löscht nichts an den bestehenden n8n Data Tables. Ein Rollback bedeutet einfach: die `trading.*`-Tabellen nicht mehr befüllen/lesen lassen (Workflows deaktivieren) — sie können bei Bedarf mit `DROP SCHEMA trading CASCADE;` vollständig entfernt werden (nicht Teil der Migration selbst, bewusste manuelle Entscheidung).

## Offene manuelle Schritte (Zusammenfassung)

1. Postgres-Credential + Status-Webhook-Token-Credential in n8n anlegen.
2. `sql/001_agenten_architektur.sql` einmalig ausführen und verifizieren.
3. Echte Workflow-ID von `10` in `00` und `05` eintragen (Platzhalter ersetzen).
4. Nach erfolgreichem Test: alte Schedule-Trigger in den „– Orchestriert“/„– Agent V1“-Dateien deaktivieren, um Doppelläufe zu vermeiden.
5. `REQUIRE_CONFIRMATION` in `06` bei Bedarf von einer Konstante zu einem echten Konfigurationswert machen.
6. Alle Punkte aus `TESTPLAN_AGENTEN.md` einmal gegen echte Daten durchspielen (bisher nur statisch geprüft).

## Punkte, die wegen fehlender Laufzeitumgebung nur statisch geprüft werden konnten

- Sämtliche neuen `n8n-nodes-base.postgres`-Nodes: Verwendung der `executeQuery`-Operation ist als einzige Postgres-Operation real bestätigt (über den Migrations-Runner-Workflow selbst), aber kein tatsächlicher Lauf gegen eine echte Datenbank fand statt.
- `n8n-nodes-base.executeWorkflowTrigger` und `n8n-nodes-base.executeWorkflow` (Orchestrator-Mechanik): Standard-n8n-Funktionalität, aber nicht live gegen diese konkrete n8n-Instanz getestet — insbesondere die genaue Struktur des von `Execute Workflow` zurückgegebenen Objekts (`error`-Feld bei Fehlschlag) basiert auf allgemeinem n8n-Wissen, nicht auf einem lokalen Beispiel aus den 8 Original-Workflows (die alle nie Execute-Workflow verwenden).
- `n8n-nodes-base.webhook` mit `authentication: headerAuth`: Standard-n8n-Feature, aber kein lokales Beispiel eines bereits authentifizierten Webhooks in diesem Projekt zum Abgleich vorhanden.
- Alle KI-Prompts (03, 03a, 09, 10): Format-Erwartungen (JSON-Schema-Konformität der Modellantworten) sind nur anhand der bereits produktiv bewährten Prompt-Struktur aus den Originalen abgeleitet, nicht mit echten Modellaufrufen verifiziert.
- Die komplette Handelstage-Zählung in 08 (D+1..D+20 über tatsächlich vorhandene `stock_technical_signals`-Zeilen) wurde nur gegen die Codelogik durchdacht, nicht gegen reale mehrtägige Kursverlaufsdaten getestet.
