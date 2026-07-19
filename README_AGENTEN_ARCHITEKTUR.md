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

## Benötigte n8n Credentials — Stand: Postgres bereits angelegt und überall zugewiesen

| Credential-Name | Typ | Verwendung | Status |
|---|---|---|---|
| `Postgres account` (ID `NWckNyl8ZfwVVJCd`) | Postgres | Alle `n8n-nodes-base.postgres`-Nodes (executeQuery) in 00, 03, 03a, 04, 06, 07, 08, 09, 10, 97, 99 | **Angelegt und in allen 49 betroffenen Nodes über 11 Workflows zugewiesen** (per API, `scratch/assign_postgres_credential.py`) |
| `Status-Webhook Token (TODO Credential zuweisen)` | Header Auth | Absicherung des Status-Webhooks in 07 | Noch offen — 07 wurde in dieser Session nicht live getestet |
| `Header Auth account` (ID `od1pN1F5wy2irSDs`) | Header Auth | Alle Matrix-Sends | Bereits vorhanden, unverändert aus den Originalen übernommen |
| `OpenAI account` (ID `RiT1gwJpQWzSo6NO`) | OpenAI API | Alle KI-Nodes (03, 03a, 09, 10) | Bereits vorhanden, live bestätigt funktionsfähig |
| `SMTP account` (ID `9z1hWYlOfxcO8avw`) | SMTP | E-Mail-Versand in 05 | Bereits vorhanden, noch nicht live getestet (05 wurde in den Orchestrator-Testläufen nie mit `approved=true` erreicht) |

**Kein Zugangsdatenwert steht in irgendeiner Workflow-Datei oder in Git.** Die Postgres-Credential wurde ausschließlich in der n8n-UI angelegt und danach per API-Referenz (Name+ID, kein Passwort) den Nodes zugewiesen.

## Benötigte Umgebungsvariablen / offene Platzhalter

- **Postgres-Verbindungsdetails** (Host, Port, Datenbankname, Benutzer, Passwort): nicht bekannt zum Zeitpunkt dieser Migration, werden ausschließlich über die oben genannte n8n-Credential konfiguriert, nirgends im Code.
- **`DRY_RUN`**: wird als Execute-Workflow-Input-Parameter durchgereicht (00 → 06, 00 → 05), Default `false`. Für einen produktionsnahen Test ohne echten Matrix-/E-Mail-Versand `DRY_RUN=true` beim manuellen Start von `00` setzen.
- **`REQUIRE_CONFIRMATION`** (06): aktuell als Konstante `false` im Code gesetzt (siehe „Trigger-Eingabe normalisieren“-Node in 06) — kann bei Bedarf zu einem echten Konfigurationswert gemacht werden (z. B. Zeile in `trading.stock_instruments.metadata_json` oder eine eigene Einstellungstabelle), war im Auftrag nur als „optional“ gefordert.

## Datenbankmigration — ERLEDIGT und live verifiziert

1. `sql/001_agenten_architektur.sql` wurde über `99 – Einmalig – SQL-Migration ausfuehren` live ausgeführt — Schema `trading` mit allen 9 Tabellen existiert und wurde per Kontrollabfrage bestätigt (`information_schema.schemata`).
2. `sql/002_seed_stock_instruments.sql` (neu, während des Testens ergänzt) wurde ebenfalls live ausgeführt — `trading.stock_instruments` enthält alle 15 Ticker mit Name/Sektor (aus der bereits produktiven `stock_technical_signals` übernommen) und Aliasen/Ausschlussmustern (aus dem RSS-Vorfilter in 03 übernommen). War zwingend nötig, nicht optional: ohne diese Daten läuft 08s Benchmark-Zuordnung ins Leere.
3. `stock_price_history` (n8n Data Table) bleibt unverändert bestehen; 08 nutzt `stock_technical_signals`/`stock_market_context` als Kursquelle — live bestätigt funktionsfähig (89 Tracking-Zeilen korrekt angelegt im Test).

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

Alle `Execute Workflow`-Referenzen in `00` und `05` nutzen bereits diese echten IDs (in den Git-Dateien nachgetragen). Stand der ursprünglich geplanten manuellen Schritte:

1. ✅ Postgres-Credential über `98 – Einmalig – Postgres-Verbindungstest` angelegt und verifiziert.
2. ✅ Dieselbe Credential in allen `executeQuery`-Nodes der übrigen Workflows zugewiesen (per API, `scratch/assign_postgres_credential.py` — muss nach jedem vollständigen PUT-Push erneut laufen, da PUT die Credential sonst auf den Platzhalter zurücksetzt).
3. ✅ `99 – Einmalig – SQL-Migration ausfuehren` ausgeführt.
4. ⏳ Status-Webhook-Token-Credential noch nicht angelegt, `07` noch nicht getestet.
5. ⏳ Teilweise erledigt — `00`, `03`, `06`, `08`, `10` erfolgreich einzeln und im Gesamtlauf getestet (siehe Live-Testergebnisse unten), `03a`/`04`/`07`/`09` sowie der echte `05`-Versandpfad noch offen. Noch kein Workflow wurde aktiviert (bewusst — Aktivierung erst nach vollständigem Testdurchlauf).
6. ⏳ Alte Schedule-Trigger in `02b`/`02`/`05`/`06` laufen bewusst weiter unverändert, bis alle neuen Versionen getestet und aktiviert sind.

**Bekannte Einschränkung beim Live-Push:** die strikte Workflow-Create-API akzeptiert kein node-level `"settings"`-Feld (z. B. `retryOnFail`/`maxTries` an einzelnen `httpRequest`-Nodes), obwohl das UI-Export-Format es enthält — dieses Feld wurde nur für den API-Push entfernt, die Git-Dateien selbst enthalten es unverändert. Betroffene Nodes haben dadurch in der jetzt live angelegten Version keine node-eigene Retry-Konfiguration (ihre `neverError`/Fehlerbehandlung auf HTTP-Ebene bleibt aber erhalten) — bei Bedarf in der n8n-UI manuell nachtragen.

## Live-Testergebnisse (Stand 2026-07-19, Abend)

Alle Tests liefen gegen die echte Produktions-Postgres-Instanz und echte RSS-/OpenAI-Aufrufe (nicht simuliert). Verifikation lief über die n8n Executions-API (`GET /api/v1/executions/{id}?includeData=true`) plus Kontrollabfragen über den eigens gebauten Workflow `97 – Einmalig – Beliebige Query ausfuehren`.

| Workflow | Status | Ergebnis |
|---|---|---|
| `98` Postgres-Verbindungstest | ✅ bestanden | Credential angelegt, Verbindung bestätigt |
| `99` SQL-Migration | ✅ bestanden | Schema `trading` mit 9 Tabellen live erstellt |
| `03` News Ingestion | ✅ bestanden | 72 RSS-Artikel verarbeitet → 58 evaluated, 14 discarded, 0 hängengeblieben |
| `08` News-Wirkungsanalyse | ✅ bestanden | 89 `news_impact_tracking`-Zeilen korrekt angelegt (alle `waiting_d1`, da nur 1 Tag Kurshistorie vorliegt — erwartet) |
| `10` Report- und Prüfagent | ✅ bestanden | Beide KI-Agenten laufen, Prüf-Agent lehnt inhaltlich begründet ab (`quality_score` 14→47 nach Fixes) |
| `06` Empfehlungswatchlist | ✅ bestanden | Läuft durch, 0 Treffer diesmal (korrekt bei aktueller Datenlage) |
| `00` Tagesabschluss-Orchestrator | ✅ bestanden | Kompletter Durchlauf 02b→02→06→10→(Ablehnung)→Matrix-Warnung, keine Duplikate mehr |
| `03a`, `09`, `07` | ⏳ noch nicht live getestet | `03a` mangels `wirkungsebene='unklar'`-Fällen, `09` mangels `completed`-Wirkungsanalysen, `07` zurückgestellt |
| `05` echter Versandpfad | ⏳ noch nie erreicht | Der Prüf-Agent hat in allen Testläufen korrekt abgelehnt — der `approved=true`-Pfad (05 wird tatsächlich aufgerufen, Matrix+E-Mail gehen raus) ist dadurch noch nie durchlaufen worden |

## Neun echte Bugs beim Live-Testen gefunden und behoben

Diese wären bei rein statischer Prüfung nicht aufgefallen — Details in den jeweiligen Commit-Messages (`git log`), Kurzfassung:

1. **Postgres-Schreib-Nodes verarbeiteten nur 1 statt N Items** — der zentrale SQL-Bau-Helfer erstellte Code-Nodes ohne `mode: runOnceForEachItem` (n8n-Default ist „einmal für alle Items“), wodurch bei mehreren Items stillschweigend nur das erste verarbeitet wurde. Betraf praktisch jeden Postgres-Write in der gesamten Architektur.
2. **SplitInBatches-Verdrahtung invertiert** — Ausgang 0 ist „fertig", Ausgang 1 ist „aktueller Batch" (umgekehrt zur ursprünglichen Annahme, kein lokales Beispiel dieses Node-Typs vorhanden).
3. **Retry-Verarbeitung blockierte sich selbst** — wenn ein stündlicher Lauf 0 neue News fand, lief der komplette Batch-Verarbeitungszweig gar nicht erst an, da er hinter dem Insert-Ergebnis statt unabhängig davon hing.
4. **`news_key` fehlte** beim Aufbau neuer Wirkungsanalyse-Zeilen (in der DB-Query selektiert, aber im JS-Code nie durchgereicht) → NOT-NULL-Verletzung.
5. **`trading.stock_instruments` war leer** — ohne Seed-Daten schlug die Benchmark-Zuordnung in 08 fehl.
6. **`alwaysOutputData` ging beim API-Push verloren** — die node-level `settings`-Bereinigung (nötig, da die API dieses Feld sonst ablehnt) hat dieses Verhaltens-Flag mitgelöscht, nicht nur kosmetische Retry-Einstellungen.
7. **Prüf-Agent bekam nur Datensatz-Anzahlen statt der Werte selbst** — konnte dadurch nichts wirklich gegenprüfen und lehnte pauschal alles als „nicht verifizierbar" ab.
8. **`run_id` kam als NULL an, wenn 10 als Sub-Workflow aufgerufen wurde** — drei Fixversuche (`.all()[0]`, expliziter Merge-Zweig, schließlich lokale Erzeugung); der zugrunde liegende `workflowInputs`-Übergabemechanismus zwischen Execute Workflow und Execute Workflow Trigger verhielt sich anders als erwartet.
9. **Doppel-Ausführung bei rohen Mehrfachverbindungen** — zwei „main"-Verbindungen auf denselben Node erzeugen in n8n zwei separate Ausführungen, keine kombinierte; betraf sowohl das Dedup-Verhalten nach `alwaysOutputData` als auch grundsätzlich jede Stelle mit zwei Roh-Verbindungen auf ein Ziel.

## Testreihenfolge für die verbleibenden Workflows

1. `03a` — künstlich eine `news_assessments`-Zeile auf `wirkungsebene='unklar'` setzen, dann ausführen.
2. `09` — erst sinnvoll testbar, sobald mehrere `news_impact_tracking`-Zeilen `status='completed'` erreicht haben (braucht mehrere Tage `02`/`02b`-Historie). Bis dahin liefert der Bericht mangels Fallzahl leer/fast leer — das ist korrektes Verhalten (Mindestfallzahlen-Regel), kein Fehler.
3. `07` — Status-Webhook-Token-Credential anlegen, dann testen.
4. Den echten Versandpfad von `05` einmal gezielt erzwingen (z. B. testweise die `quality_score`-Schwelle in `10` lokal senken oder eine Testdaten-Konstellation bauen, die der Prüf-Agent freigibt), um Matrix+E-Mail-Versand mindestens einmal live zu verifizieren.

## Rollback-Anleitung

- **Vollständiger Rollback auf den Ist-Zustand**: `git checkout main` im Repo `finanz` — der `main`-Branch enthält ausschließlich den unveränderten Ist-Stand (Commit `40e5575`), keine der neuen Dateien. In n8n die dort laufenden Original-Workflows unverändert weiter aktiv lassen (sie wurden durch diese Migration nicht angefasst).
- **Teilweiser Rollback**: da jede neue/geänderte Datei ein eigener, unabhängig importierbarer Workflow ist, kann z. B. nur `00 – Tagesabschluss-Orchestrator` deaktiviert werden, während `03`/`08`/`09` (News-Pipeline + Lernprozess) weiterlaufen — die alten `02b`/`02`/`05`/`06`-Originale mit ihren eigenen Schedule-Triggern funktionieren unabhängig vom Orchestrator weiter, solange sie nicht deaktiviert wurden.
- **Datenbank-Rollback**: `sql/001_agenten_architektur.sql` legt ausschließlich NEUE Tabellen im Schema `trading` an, verändert oder löscht nichts an den bestehenden n8n Data Tables. Ein Rollback bedeutet einfach: die `trading.*`-Tabellen nicht mehr befüllen/lesen lassen (Workflows deaktivieren) — sie können bei Bedarf mit `DROP SCHEMA trading CASCADE;` vollständig entfernt werden (nicht Teil der Migration selbst, bewusste manuelle Entscheidung).

## Offene manuelle Schritte (Zusammenfassung)

1. Status-Webhook-Token-Credential in n8n anlegen und `07` zuweisen.
2. `03a`, `04`, `07`, `09` live testen (siehe „Testreihenfolge für die verbleibenden Workflows" oben) — bisher nur `00`, `03`, `06`, `08`, `10` live bestätigt.
3. Den echten `05`-Versandpfad (`approved=true`) mindestens einmal gezielt erzwingen und verifizieren — bisher hat der Prüf-Agent in jedem Testlauf korrekt abgelehnt, wodurch dieser Pfad nie durchlaufen wurde.
4. Nach erfolgreichem Test aller Stufen: alte Schedule-Trigger in den Original-Workflows `02b`/`02`/`05`/`06` deaktivieren, um Doppelläufe zu vermeiden — bewusst noch nicht geschehen.
5. `REQUIRE_CONFIRMATION` in `06` bei Bedarf von einer Konstante zu einem echten Konfigurationswert machen (im Auftrag nur als optional gefordert).
6. Erst nach Punkt 2+3: alle 15 Workflows aktivieren.

## Punkte, die weiterhin nur statisch geprüft sind (nicht live getestet)

Live bereits bestätigt (siehe „Live-Testergebnisse" oben): `executeQuery`-Postgres-Nodes in 00/03/06/08/10, `executeWorkflow`/`executeWorkflowTrigger`-Orchestrierung inkl. Fehlerzweig (`onError: continueErrorOutput`), die KI-Prompts in 03 (News-Bewertung) und 10 (Report- + Prüf-Agent), sowie die D+1-Zeile der Handelstage-Zählung in 08.

Noch offen:
- `n8n-nodes-base.webhook` mit `authentication: headerAuth` in `07`: Standard-n8n-Feature, aber noch keine Credential angelegt und kein Testlauf erfolgt.
- Die KI-Prompts in `03a` (Recherche-Agent) und `09` (Lernagent): Format-Erwartungen nur aus der Prompt-Struktur der bereits bestätigten Agenten (03/10) abgeleitet, nicht selbst mit echten Modellaufrufen verifiziert.
- Die D+3/D+5/D+10/D+20-Zweige der Handelstage-Zählung in 08: nur D+1 wurde bisher tatsächlich erreicht (es liegt erst 1 Tag Kurshistorie seit der Migration vor), die späteren Zeitfenster sind weiterhin nur gegen die Codelogik durchdacht.
- Der echte `05`-Versandpfad (Matrix + E-Mail bei `approved=true`): nie erreicht, da der Prüf-Agent in allen bisherigen Testläufen korrekt ablehnte.
- `04` (Cleanup) und dessen Retention-Regeln gegen echte, ausreichend alte Datensätze — die Testdaten sind dafür noch zu jung.
