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

07 – Status-Uebersicht – Agent V1 (Webhook, jetzt mit Header-Token; inkl. SVG-Diagramme fuer Wirkungsanalyse-Status und Trefferquote je Quelle)
01 – Fundamentaldaten täglich (06:00, unverändert — rein deterministisch, kein Agentenbedarf)
```

`01` und die Kernlogik von `02`/`02b` bleiben **unverändert** (rein deterministische Berechnung, kein KI-Einsatz nötig oder sinnvoll). `02b`/`02` haben lediglich einen zusätzlichen `Execute Workflow Trigger`-Einstiegspunkt bekommen (Dateien mit Suffix „– Orchestriert“), damit der Orchestrator sie aufrufen kann — die eigentliche Berechnungslogik ist byte-identisch zum Original.

## Neu erstellte Dateien

```
ARCHITEKTUR_BESTAND.md
MIGRATIONSPLAN_AGENTEN.md
TESTPLAN_AGENTEN.md
README.md (dieses Dokument)

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

## Benötigte n8n Credentials — Stand: alle angelegt und zugewiesen

| Credential-Name | Typ | Verwendung | Status |
|---|---|---|---|
| `Postgres account` (ID `NWckNyl8ZfwVVJCd`) | Postgres | Alle `n8n-nodes-base.postgres`-Nodes (executeQuery) in 00, 03, 03a, 04, 06, 07, 08, 09, 10, 97, 99 | **Angelegt und in allen betroffenen Nodes über 11 Workflows zugewiesen** (per API, `scratch/assign_postgres_credential.py`) |
| `Status-Webhook Token` (ID `5lPS4iU0YNbMcjWR`) | Header Auth | Absicherung des Status-Webhooks in 07 (Header `X-Status-Token`) | **Angelegt und zugewiesen, live getestet** — 07 liefert die Status-HTML mit korrektem Header, `403 Authorization data is wrong!` ohne |
| `Header Auth account` (ID `od1pN1F5wy2irSDs`) | Header Auth | Alle Matrix-Sends | Bereits vorhanden, unverändert aus den Originalen übernommen |
| `OpenAI account` (ID `RiT1gwJpQWzSo6NO`) | OpenAI API | Alle KI-Nodes (03, 03a, 09, 10) | Bereits vorhanden, live bestätigt funktionsfähig |
| `SMTP account` (ID `9z1hWYlOfxcO8avw`) | SMTP | E-Mail-Versand in 05 | Bereits vorhanden, noch nicht live getestet (05 wurde in den Orchestrator-Testläufen nie mit `approved=true` erreicht) |

**Kein Zugangsdatenwert steht in irgendeiner Workflow-Datei oder in Git.** Beide neuen Credentials (Postgres, Status-Webhook Token) wurden ausschließlich per API angelegt (Token/Passwort nur im API-Request an n8n selbst, nirgends im Repo) und danach per API-Referenz (Name+ID, kein Zugangsdatenwert) den Nodes zugewiesen — `scratch/assign_postgres_credential.py` deckt inzwischen beide Credential-Typen ab und muss nach jedem vollständigen PUT-Push der betroffenen Workflows erneut laufen.

## Benötigte Umgebungsvariablen / offene Platzhalter

- **Postgres-Verbindungsdetails** (Host, Port, Datenbankname, Benutzer, Passwort): nicht bekannt zum Zeitpunkt dieser Migration, werden ausschließlich über die oben genannte n8n-Credential konfiguriert, nirgends im Code.
- **`DRY_RUN`** und **`REQUIRE_CONFIRMATION`**: **überholt seit dem Verbesserungsauftrag Juli 2026** — beide sind seit 2026-07-20 keine Code-Konstanten mehr, sondern echte Werte in der neuen Tabelle `trading.pipeline_config` (`DRY_RUN` Default `false`, `REQUIRE_CONFIRMATION` Default `true`). Details, Wirkweise und Live-Testergebnisse: siehe „Nachtrag: Verbesserungsauftrag Juli 2026“ ganz unten.

## Datenbankmigration — ERLEDIGT und live verifiziert

1. `sql/001_agenten_architektur.sql` wurde über `99 – Einmalig – SQL-Migration ausfuehren` live ausgeführt — Schema `trading` mit allen 9 Tabellen existiert und wurde per Kontrollabfrage bestätigt (`information_schema.schemata`).
2. `sql/002_seed_stock_instruments.sql` (neu, während des Testens ergänzt) wurde ebenfalls live ausgeführt — `trading.stock_instruments` enthält alle 15 Ticker mit Name/Sektor (aus der bereits produktiven `stock_technical_signals` übernommen) und Aliasen/Ausschlussmustern (aus dem RSS-Vorfilter in 03 übernommen). War zwingend nötig, nicht optional: ohne diese Daten läuft 08s Benchmark-Zuordnung ins Leere.
3. `stock_price_history` (n8n Data Table) bleibt unverändert bestehen und unbefüllt; 08 nutzte anfangs `stock_technical_signals`/`stock_market_context` als Kursquelle — live bestätigt funktionsfähig (89 Tracking-Zeilen korrekt angelegt im Test). **Überholt seit 2026-07-20**: es gibt inzwischen eine echte, dediziert befüllte Tabelle `trading.stock_price_history` (Postgres), auf die 08 umgestellt wurde — siehe „Nachtrag: Verbesserungsauftrag Juli 2026“ unten.

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
| `03a` News-Recherche-Agent | ✅ bestanden | Künstlicher `wirkungsebene='unklar'`-Fall (News 71) lief durch kompletten Zweitpass (Artikel laden, ähnliche News, Ticker-Historie, KI-Bewertung, Persistierung) — SQL-Bug im Werkzeug „Frühere Meldungen zum Ticker lesen" dabei gefunden und behoben |
| `07` Status-Uebersicht | ✅ bestanden | Webhook mit Header-Auth angelegt und live getestet (korrekte Statusseite mit Header, `403` ohne) — Webhook-Pfad kollidiert mit dem noch aktiven Original-Workflow, daher nur kurzzeitig unter Test-Pfad aktiviert, danach wieder deaktiviert |
| `05` echter Versandpfad | ✅ bestanden | `approved=true` per gepinnten Testdaten auf dem `Execute Workflow Trigger`-Node erzwungen (klar als TEST-VERSAND markiert): Matrix-Nachricht real zugestellt (`event_id` erhalten), E-Mail vom Mailserver angenommen (`250 Ok`), kein Fehler in der Kette — Pin-Daten danach wieder entfernt |
| `04` Cleanup | ✅ bestanden | 6 künstlich zeitversetzte Test-News (klar als `TEST-04\|...` markiert) deckten alle 4 Zweige ab: alte `discarded`/`failed`-Zeilen korrekt gelöscht, zu junge `discarded`-Zeile korrekt behalten, alte `evaluated`-Zeile ohne Wirkungsdaten korrekt gelöscht, dieselbe MIT Wirkungsdaten korrekt geschützt (zentraler „Lerndaten nicht vorzeitig löschen"-Schutz greift), Zeile ohne Veröffentlichungsdatum korrekt markiert — Testzeilen danach wieder entfernt |
| `09` Lernagent | ✅ bestanden | 55 künstliche `completed`-Wirkungsanalyse-Zeilen in 3 Gruppen (35/15/5, klar als `TEST-09\|...` markiert) deckten alle Mindestfallzahl-Stufen ab: <10 korrekt komplett ausgeschlossen, 10-29 korrekt als „niedrig"/nicht vorschlagsfähig, ≥30 korrekt als „mittel"/vorschlagsfähig — dabei einen echten Bug gefunden und behoben (siehe unten). Alle 4 Dimensionen (news_category/source/ticker/konfidenz_bucket) korrekt ausgewertet, Vorschläge korrekt nur mit `status='proposed'` gespeichert, Matrix-Bericht real zugestellt. Testzeilen danach wieder entfernt |

## Zwölf echte Bugs beim Live-Testen gefunden und behoben

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
10. **SQL-Injection-artiger Quoting-Fehler in 03a** — `JSON.stringify(...)` wurde als n8n-Expression direkt ins SQL eingesetzt (`@> [...]::jsonb` statt `@> '[...]'::jsonb`), da dieser eine Node (anders als der Rest der Architektur) nicht über den zentralen `pgJson`-Helfer, sondern direkt per n8n-Expression im Postgres-Node gebaut wurde — schlug live bei allen 4 Testkandidaten mit Syntaxfehler fehl, Werkzeugergebnis blieb leer statt frühere Meldungen zum Ticker zu liefern.
11. **Lernvorschläge bekamen die falsche `target_type`-Dimension zugewiesen** — das KI-Prompt-Schema in 09 fragte keine Dimension (news_category/source/ticker/konfidenz_bucket) je Vorschlag ab, nur `proposal_type='source_weight'`. Die Validierung setzte `target_type` deshalb blind auf `'source'` und nutzte als Fallback eine reine Werte-Suche über ALLE Dimensionen hinweg — dadurch wurde live ein Ticker-Fund (`TEST9A.DE`) als `target_type='source'`-Vorschlag gespeichert. Fix: KI muss `dimension` explizit mitliefern, Validierung matcht strikt über `dimension+value`, `target_type` kommt aus dem getroffenen Finding, kein Fallback mehr. Nach dem Fix bekamen alle 4 vorschlagsfähigen Funde live korrekt ihre jeweilige Dimension zugewiesen.
12. **Workflow „97" hatte einen doppelt-kodierten Namen** (`â€"` statt `–`) — vermutlich aus einer frühen Erstellung dieser Session ohne durchgängige `encoding='utf-8'`-Disziplin, entdeckt am n8n-UI-Anzeigefehler. Alle 15 live angelegten Workflow-Namen per Byte-Vergleich geprüft — nur dieser eine betroffen, korrigiert per API.

## Testreihenfolge für die verbleibenden Workflows

Alle 13 neuen/geänderten Workflows (00, 02/02b-Orchestriert, 03, 03a, 04, 05, 06, 07, 08, 09, 10) sind inzwischen live getestet — siehe „Live-Testergebnisse" oben. Kein Workflow mehr offen; verbleibt nur noch die Aktivierung nach dem letzten manuellen Schritt (siehe „Offene manuelle Schritte" unten).

**Hinweis zum Testen webhook-basierter Workflows (aus dem 07-Test gelernt):** „Listen for test event" im n8n-Editor fängt bei `responseMode: responseNode` nur den Trigger-Aufruf ab und pinnt die Daten, führt aber NICHT automatisch die nachgelagerte Kette aus. Für einen echten End-to-End-Test muss der Workflow aktiviert und die Produktions-URL aufgerufen werden. Da `07`s Webhook-Pfad (`aktien-status`) mit dem noch aktiven Original-Workflow kollidiert, wurde für den Test kurzzeitig ein abweichender Pfad gesetzt, aktiviert, getestet und danach Pfad+Aktivierung wieder zurückgesetzt — bei der eigentlichen Umstellung muss der Original-Workflow zuerst deaktiviert werden, bevor die neue `07`-Version unter dem echten Pfad aktiviert werden kann.

**Hinweis zum Testen von `Execute Workflow Trigger`-Einstiegspunkten (aus dem 05-Test gelernt):** dieser Node-Typ bietet keine eigene "Testdaten eingeben"-Maske im Editor (die Parameter-Ansicht definiert nur das Input-Schema, nicht Testwerte) — er erwartet Werte ausschließlich von einem echten aufrufenden `Execute Workflow`-Node. Um ihn isoliert zu testen, per API `pinData` auf den Node setzen (`{"<Node-Name>": [{"json": {...}}]}` im PUT-Payload), danach im Editor auf „Execute workflow" klicken — läuft dann mit den gepinnten Werten durch die komplette nachgelagerte Kette. Pin-Daten nach dem Test wieder auf `{}` zurücksetzen, damit sie nicht versehentlich bei einem echten Aufruf greifen.

**Hinweis zum Testen zeitabhängiger Logik wie Retention-Regeln (aus dem 04-Test gelernt):** statt auf echte mehrtägige/-jährige Datenhistorie zu warten, künstliche Zeilen mit zurückdatiertem `created_at` (z. B. `now() - interval '400 days'`) direkt per SQL über `97 – Einmalig – Beliebige Query ausfuehren` einfügen, klar erkennbar markiert (z. B. `news_key` mit `TEST-<Workflow>|`-Präfix), den zu testenden Workflow ausführen, Ergebnis prüfen, Testzeilen danach wieder löschen. Deckt so auch Grenzfälle ab (z. B. "gerade noch zu jung" vs. "gerade alt genug"), die mit echten Daten Tage bis Monate zum natürlichen Auftreten bräuchten. Beim Aufräumen alle Filterspalten bedenken, nicht nur eine (im 09-Test wurde eine Testzeile übersehen, weil sie über `target_value` statt über den erwarteten `TEST-`-Präfix identifiziert werden musste — Kontrollabfrage nach dem Löschen ist Pflicht, nicht nur "sollte 0 sein").

**Hinweis zu doppelt-kodierten Workflow-Namen (aus dem 97-Namensfund gelernt):** n8n-UI zeigt `â€"` statt `–` an, wenn der Name-String beim Erzeugen ohne explizites `encoding='utf-8'` gelesen/geschrieben wurde (Windows-Python-Default ist cp1252). Bei Verdacht: `name.encode('utf-8')[:6].hex()` prüfen — korrekt beginnt ein Gedankenstrich nach einem Leerzeichen mit `20e28093`, korrupt mit `20c3a2e2` o.ä. Bei diesem Projekt wurde dadurch nur der Name eines einzelnen Wegwerf-Workflows beschädigt, keine Inhalte.

## Produktions-Umstellung — ERLEDIGT (Stand 2026-07-20)

Die neue Architektur ist live geschaltet. Alle alten Original-Workflows (`01` ausgenommen) sind deaktiviert, alle 15 neuen sind aktiv.

**Dabei gefundener, vorbestehender Bug (unabhängig von dieser Migration):** `02 – Technische Signale täglich` lief bereits **doppelt aktiv** — zwei unterschiedliche Workflow-Kopien (erstellt 2026-05-29 bzw. 2026-07-14, vermutlich ein Artefakt der Architektur-Review vom 07-14) liefen parallel auf demselben 18:00-Zeitplan. Beide wurden im Zuge der Umstellung deaktiviert.

**Wichtige technische Erkenntnis beim Aktivieren:** n8n verweigert die Aktivierung eines Workflows, wenn eines seiner `Execute Workflow`-Nodes auf einen **inaktiven** Sub-Workflow zeigt ("Cannot publish workflow: ... which is not published"). Die ursprünglich geplante Strategie „`00` aktivieren, die von ihm aufgerufenen Sub-Workflows (`02b`/`02`/`06`/`05`/`10`) aber inaktiv lassen, um deren eigene Schedule-Trigger nicht doppelt laufen zu lassen" funktioniert daher NICHT — alle referenzierten Sub-Workflows müssen selbst aktiv sein. Lösung: bei `02b`-Orchestriert, `02`-Orchestriert, `06` und `05` wurde stattdessen gezielt nur der jeweils eigene `scheduleTrigger`-Node deaktiviert (`"disabled": true`, sowohl live als auch in den lokalen Dateien), nicht der ganze Workflow — der Node bleibt für den `Execute Workflow`-Aufruf durch `00` nutzbar, feuert aber nicht mehr eigenständig. Bei `05` war das nicht nur eine Doppellauf-, sondern eine echte Sicherheitsfrage: dessen eigener 18:30-Trigger hätte den Prüf-Agenten komplett umgangen und immer versendet, unabhängig vom `approved`-Status.

**Aktueller Aktivierungsstatus:**

| Workflow | Status | Grund |
|---|---|---|
| `01` (Original) | aktiv, unverändert | kein Ersatz, rein deterministisch |
| `00`, `03`, `03a`, `04`, `07`, `08`, `09` (neu) | aktiv, eigener Zeitplan/Webhook | laufen unabhängig |
| `02b`, `02`, `06`, `05`, `10` (neu) | aktiv, aber eigener Schedule-Trigger deaktiviert | nur über `00`s Execute-Workflow-Aufruf erreichbar |
| `02b`, `02` (beide Kopien), `03`, `04`, `05`, `06`, `07` (Originale) | deaktiviert | durch neue Versionen ersetzt |
| `97`/`98`/`99` (Einmalig) | deaktiviert | Wegwerf-Workflows, nicht Teil der Kaskade |

## Rollback-Anleitung

- **Vollständiger Rollback auf den Ist-Zustand**: `git checkout main` im Repo `finanz` für die Dateien — der `main`-Branch enthält den unveränderten Ist-Stand (Commit `40e5575`). In n8n zusätzlich: die 15 neuen Workflows deaktivieren, die alten Originale (Liste oben) sowie deren eigene Schedule-Trigger wieder aktivieren.
- **Teilweiser Rollback**: da jede neue/geänderte Datei ein eigener, unabhängig aktivierbarer Workflow ist, kann z. B. nur `00 – Tagesabschluss-Orchestrator` deaktiviert werden, während `03`/`08`/`09` (News-Pipeline + Lernprozess) weiterlaufen. Achtung: `02b`/`02`/`06`/`05` liefern dann keinen Report mehr (ihr eigener Schedule-Trigger ist deaktiviert) — deren Original-Gegenstücke müssten dafür wieder aktiviert UND deren eigener Trigger wieder eingeschaltet werden.
- **Datenbank-Rollback**: `sql/001_agenten_architektur.sql` legt ausschließlich NEUE Tabellen im Schema `trading` an, verändert oder löscht nichts an den bestehenden n8n Data Tables. Ein Rollback bedeutet einfach: die `trading.*`-Tabellen nicht mehr befüllen/lesen lassen (Workflows deaktivieren) — sie können bei Bedarf mit `DROP SCHEMA trading CASCADE;` vollständig entfernt werden (nicht Teil der Migration selbst, bewusste manuelle Entscheidung).

## Offene manuelle Schritte (Zusammenfassung)

1. Alle 13 neuen/geänderten Workflows sind live getestet — keine offenen Einzeltests mehr.
2. Produktions-Umstellung durchgeführt (siehe oben) — alte Originale deaktiviert, alle 15 neuen aktiv.
3. `REQUIRE_CONFIRMATION` in `06` bei Bedarf von einer Konstante zu einem echten Konfigurationswert machen (im Auftrag nur als optional gefordert).
4. Den ersten echten, ungeplanten Produktionslauf (nächster planmäßiger Zeitpunkt) beobachten, um die Kaskade unter realen Bedingungen zu bestätigen — alle bisherigen Tests liefen manuell/isoliert.

## Punkte, die weiterhin nur statisch geprüft sind (nicht live getestet)

Live bereits bestätigt (siehe „Live-Testergebnisse" oben): `executeQuery`-Postgres-Nodes in 00/03/03a/04/06/07/08/09/10, `executeWorkflow`/`executeWorkflowTrigger`-Orchestrierung inkl. Fehlerzweig (`onError: continueErrorOutput`), die KI-Prompts in 03 (News-Bewertung), 03a (Recherche-Agent), 09 (Lernagent) und 10 (Report- + Prüf-Agent), `n8n-nodes-base.webhook` mit `authentication: headerAuth` in 07, der echte `05`-Versandpfad (Matrix + E-Mail bei `approved=true`, per gepinnten Testdaten erzwungen), `04`s vier Retention-Zweige und `09`s Mindestfallzahl-Stufen (beide per künstlich zurückdatierten/erzeugten Testzeilen), sowie die D+1-Zeile der Handelstage-Zählung in 08.

Noch offen:
- Die D+3/D+5/D+10/D+20-Zweige der Handelstage-Zählung in 08: nur D+1 wurde bisher tatsächlich erreicht (es liegt erst 1 Tag Kurshistorie seit der Migration vor), die späteren Zeitfenster sind weiterhin nur gegen die Codelogik durchdacht.
- Der komplette Aktivierungs-/Produktionsbetrieb (alle 15 Workflows gleichzeitig über Tage/Wochen aktiv, echte Cron-Zeitplan-Kaskade statt Einzeltests): jeder Workflow wurde einzeln getestet, aber noch nicht im Dauerbetrieb nebeneinander.

---

## Nachtrag: Verbesserungsauftrag Juli 2026 (Stand 2026-07-20, Nacht)

Nach der Produktions-Umstellung oben erteilte der Nutzer einen eigenständigen 29-Punkte-Verbesserungsauftrag (Priorität 1–12: sicherer Testbetrieb, echte Kurshistorie, Wirkungsanalyse-Korrektur, Störfaktoren, News-Datenqualität, Transaktionssicherheit, einheitliche Schnittstellen, Fehlerbehandlung, Lernagent-Verfeinerung, Prompt-Injection-Härtung, zentrale Konfiguration, Status-Dashboard-Erweiterung). Umgesetzt wurden in dieser Runde die **Prioritäten 1–5 vollständig**, **Priorität 6 teilweise** (nur `02`/`02b`) sowie **Priorität 7, Punkt 17**. Alles live gegen die echte Produktionsdatenbank getestet, 20 Commits auf `agenten-modernisierung`. Details je Bugfix/Commit: `git log`.

### Priorität 1 — Sicherer Testbetrieb (erledigt, live getestet)

Neue Tabelle `trading.pipeline_config` (`sql/003_pipeline_config.sql`, key-value: `config_key`, `value_bool`/`value_text`/`value_numeric`, `description`), Seed-Werte `DRY_RUN=false`, `REQUIRE_CONFIRMATION=true`.

- `00`: neuer Node `Config: DRY_RUN laden` (Postgres) direkt nach `Run-ID erzeugen`, gemerged in den weitergereichten Kontext — die frühere hartkodierte `DRY_RUN: false`-Zeile ist entfernt.
- `06`: neue Nodes `Config: DRY_RUN+REQUIRE_CONFIRMATION laden` + `Kontext ergaenzen`; echtes `IF: DRY_RUN aktiv?`-Gate direkt nach `Empfehlungen: Abgleich berechnen` — im DRY_RUN-Fall läuft ein neuer Zweig `Simulationsergebnis aufbauen` (`{dry_run, planned_actions[]}`), der **keinen** DB-Write und **keinen** Matrix-Versand mehr auslöst (vorher lief bei DRY_RUN weiterhin die volle Schreib-/Sendekette).
- **Gefundener und behobener Bug**: `IF: Bestaetigung erforderlich?` war invertiert verdrahtet — `REQUIRE_CONFIRMATION=true` führte zum echten Schreiben, `false` zum reinen Vorschlag (Gegenteil der eigenen Code-Kommentare). Polarität korrigiert.
- `00`s `Log Empfehlungswatchlist (SQL bauen)` schreibt jetzt echte `dry_run`/`planned_actions`-Werte in `metadata_json` statt immer `{}` — Simulationsergebnisse sind damit auditierbar.
- Live bestätigt: DRY_RUN=true → keine Zeilenänderung in `trading.recommendations`, Matrix klar als Simulation markiert; REQUIRE_CONFIRMATION=true/false beide Pfade korrekt (Vorschlag ohne Write vs. echter Write); ein echter UNIQUE-Constraint-Verstoß beim Schreiben wird sichtbar gemeldet statt verschluckt.

### Priorität 2 — Echte historische Kursdaten (erledigt, live getestet)

Neue Tabelle `trading.stock_price_history` (`sql/004_stock_price_history.sql`: `symbol`, `trading_date`, `open/high/low/close NOT NULL/volume`, `currency`, `source`, `fetched_at`, `UNIQUE(symbol, trading_date)`).

- `02`/`02b` bekamen je einen zusätzlichen `Kurshistorie: SQL bauen`/`Kurshistorie: upserten`-Zweig (additiv, ersetzt nicht die bestehenden `stock_technical_signals`/`stock_market_context`-Writes) — ein Datensatz je (Symbol, Handelstag) und Lauf, `ON CONFLICT (symbol, trading_date) DO UPDATE`.
- `08 – News-Wirkungsanalyse`: Kursquelle für `DB: Kursverlauf je Ticker laden`/`DB: Benchmark-Kursverlauf laden` von `stock_technical_signals`/`stock_market_context` auf `trading.stock_price_history` umgestellt (Spalten-Alias `symbol AS ticker, trading_date AS datum, close AS aktueller_kurs`, damit die nachgelagerte Gruppierungslogik unverändert bleibt).
- Damit ist der in `MIGRATIONSPLAN_AGENTEN.md` Phase 6 als „gelöst“ beschriebene Workaround (Wiederverwendung von `stock_technical_signals`/`stock_market_context` als Pseudo-Historie) überholt — echte, dedizierte Tagesreihen sind jetzt die Kursquelle.
- Offen: rückwirkendes Backfill über die FastAPI (`172.16.1.14:8099`) wurde nicht geprüft/gebaut — die Tabelle akkumuliert ab jetzt real, D+20-Auswertungen brauchen entsprechend ~20 echte Handelstage.

### Priorität 3 — Wirkungsanalyse-Korrektur (erledigt, live getestet)

- `08`, `Baseline-Fall je (News,Ticker) bestimmen`: Handelszeiten-Klassifizierung war grob (`hour < 17`, laut eigenem Kommentar „vereinfacht“) — jetzt minutengenau (`berlinMinutesSinceMidnight`, Grenzen 9:00 und 17:30).
- Neues Feld `baseline_quality` (`high` bei vor_handelsbeginn/nach_handelsende, `limited` bei waehrend_handelszeit, da nur Tagesschlusskurse vorliegen, keine Intraday-Daten) — DB-Migration `ALTER TABLE trading.news_impact_tracking ADD COLUMN baseline_quality ...`.
- Neue Felder `direction_correct_d1/d3/d5/d10/d20` (vorher wurde `direction_correct` nur einmal bei D+20 berechnet, nicht je Horizont) — je Horizont in `D+1..D+20 berechnen + Stoerfaktoren` berechnet.
- **Gefundener und behobener Crash**: `$('Benchmarkverlauf gruppieren').first()` warf einen Fehler, wenn die (neue, anfangs leere) `stock_price_history` 0 Zeilen lieferte und der Gruppierungs-Node dadurch übersprungen wurde — `alwaysOutputData: true` behebt das NICHT (nur wenn ein Node läuft aber nichts liefert, nicht wenn er wegen 0 Eingabe-Items gar nicht aufgerufen wird). Fix: `safeGrouped()`-Try/Catch-Helfer mit `{}`-Fallback.

### Priorität 4 — Störfaktoren + News-Datenqualität (erledigt, live getestet)

- **`news_kategorie`-Bug behoben**: die Spalte enthielt bisher fast durchgängig USAGE-Werte (`verwerfen`, `tagesreport`, `speichern`, `matrix_alert`) statt echter Inhaltskategorien — `Ergebnis persistieren (SQL bauen)` in `03` schrieb `verwendung` direkt in die `news_kategorie`-Spalte. Fix: neues, eigenes KI-Feld `news_kategorie` mit dem im Auftrag spezifizierten Enum (`quarterly_results, profit_warning, forecast_change, merger_acquisition, regulation, management_change, legal_dispute, product_news, macro, geopolitics, analyst_rating, other`) in `03` und `03a` ergänzt (Prompt + Validierung); neue Spalte `usage_type` nimmt jetzt den bisherigen `verwendung`-Wert auf.
- `08`, `DB: Neue News-Ticker-Paare laden`: `ni.source` wurde nie selektiert (immer NULL) — ergänzt; „beste Bewertung“ zwischen `03`/`03a` jetzt per `DISTINCT ON (ni.id)` + Prioritäts-`CASE` (`news-recherche-agent-v1` > `news-ingestion-v1` > sonst).
- Störfaktor-Erkennung ersetzt: die alte kumulative Rendite-Prüfung über D+1..D+20 war nahezu immer wahr (Dauer-Confounder) — durch `maxDailyMove()` (echte Tag-für-Tag-Benchmarkbewegung) ersetzt. Neuer Node `DB: Weitere News je Ticker laden` (60 Tage, hohe Wirkung) + `findAdditionalNews()` berechnet jetzt echte `additional_news_count`/`has_major_followup_news` (vorher `additional_news_count` immer 0, `has_major_followup_news` existierte nicht) — die bereits vorbereitete, aber tote `CATEGORY_KEYWORDS`-Liste ist jetzt aktiv verdrahtet.

### Priorität 5 — Transaktionssicherheit (erledigt, live getestet)

Architekturentscheidung mit dem Nutzer abgestimmt: `stock_empfehlungen` (n8n Data Table, keine Transaktionen/Unique-Constraints möglich) → neue Postgres-Tabelle `trading.recommendations` (`ticker`, `name`, `sektor`, `richtung` CHECK `kauf/verkauf`, `status` CHECK `offen/geschlossen`, Entry-/Exit-/Hebelprodukt-Felder, `run_id`, Zeitstempel) + `CREATE UNIQUE INDEX ux_recommendations_one_open_per_ticker ON trading.recommendations (ticker) WHERE status = 'offen'` — verhindert strukturell zwei gleichzeitig offene Positionen im selben Ticker.

- `06`: `DB: Bestehende Empfehlungen laden` von Data-Table-`get` auf Postgres-`SELECT` umgestellt; `DB: Empfehlung öffnen`/`schließen` in `SQL bauen`(Code)+`executeQuery`(Postgres, `onError: continueRegularOutput`, `INSERT/UPDATE ... RETURNING *`) aufgeteilt.
- **Gefundener und behobener Bug-Klasse** („Write-Node überschreibt Item“): nach jedem erfolgreichen Schreiben ging das JS-eigene Feld `_aktion` verloren, weil der DB-Node das Item durch sein eigenes Rückgabeschema ersetzt — neue `Oeffnen/Schliessen: _aktion ergaenzen`-Nodes stellen es wieder her, inkl. Ticker-Kontext-Wiederherstellung bei Schreibfehlern.
- `Schreiberfolg verifizieren` zeigt fehlgeschlagene Writes jetzt sichtbar in der Matrix-Nachricht an (vorher wurden sie stillschweigend verworfen).
- `07 – Status-Uebersicht`: `DB: Empfehlungen laden` ebenfalls auf `trading.recommendations` umgestellt.

### Priorität 6 — Einheitliche Rückgabeformate (vollständig: `02`/`02b`/`06`/`10`/`05`, Stand 2026-07-21)

Einheitliches Envelope: `{ok, workflow, run_id, processed, successful, failed, warnings[], errors[], started_at, finished_at, status}`, `status` ∈ `success/partial_failure/failed/skipped`.

- `02`/`02b`: `onError: continueRegularOutput` an den Kursabruf-Nodes, `_run_started_at`-Stempel, neuer `Abschluss-Ergebnis bauen`-Node.
- `00`: `IF: Technische Signale ok?`/`IF: Marktumfeld ok?` prüfen jetzt `status != 'failed'` (statt leerem `.error`) — `partial_failure` blockiert die Kaskade nicht mehr, nur `failed` tut das; die zugehörigen `Log ...`-Nodes hatten einen Operator-Vorrang-Bug (`errorMessage` war praktisch immer `'failed'` oder `''`), jetzt korrekt aus `errors[]` befüllt.
- **Zwei neue, session-eigene Bug-Klassen gefunden** (nicht Teil des ursprünglichen 29-Punkte-Katalogs):
  1. *Data-Table-„get"-Node mit templatiertem Pro-Item-Filter* (`{{ $json.symbol }}`) liefert effektiv nur 1 Treffer für den gesamten Node-Lauf, nicht 1 pro Eingabe-Item — unabhängig von `limit`/`alwaysOutputData`/`returnAll`. Betraf `02b`s `DB: Marktumfeld suchen`; behoben nach dem bereits korrekten Muster aus `02` (`DB: Signal suchen`: kein Filter, `returnAll: true`, Lookup-Map in Code statt Index-Pairing).
  2. *Merge-Node, zwei Quellen auf denselben Eingangsindex* kombiniert die Items NICHT — nur eine Quelle überlebt. Betraf `02` (unentdeckt seit dem Cutover, durch günstige Testdaten maskiert) und `02b`; beide auf getrennte Indizes (0/1) korrigiert.
- Live-Test über `00`: `02b` `processed:8, successful:8, status:success`; `02` `processed:15, successful:14, failed:1, status:partial_failure` (echter Fall: `BASF.DE "Keine Chartdaten vorhanden"`, korrekt als Teilfehler statt Totalausfall behandelt), gemeinsame `run_id` mit dem Orchestrator-Lauf bestätigt.

**2026-07-21: Rest (`06`, `10`, `05`) nachgezogen, plus `00`-Anpassungen — live deployed, funktionaler End-to-End-Test steht noch aus.**

- `06 – Empfehlungswatchlist`: die zwei bisher komplett unverbundenen Terminal-Zweige (echter Schreibpfad vs. DRY_RUN-Simulation) laufen jetzt über einen echten Merge-Node zusammen, gefolgt von `Abschluss-Ergebnis bauen`. `_run_started_at`-Stempel in `Trigger-Eingabe normalisieren` ergänzt.
- `10 – Report- und Prüfagent`: additiv erweitert — die bestehenden domänenspezifischen Felder (`approved`, `report_markdown`, …) bleiben unverändert (werden von `00` und `05` weiter direkt gelesen), Envelope-Felder kommen daneben. `status: approved ? 'success' : 'failed'` (kein `partial_failure`, da immer genau 1 Ergebnis pro Lauf).
- `05 – Tagesreport`: der größte Umbau — vier Terminal-Zweige liefen bisher NIE zusammen (Matrix+E-Mail parallel im Erfolgsfall, DRY_RUN-Skip, Ablehnung), `00` bekam dadurch ein faktisch undefiniertes Ergebnis zurück, je nachdem welcher Pfad zuletzt ausgeführt wurde. Fix: drei neue Merge-Nodes plus drei kleine „Ergebnis taggen"-Nodes (da Matrix-/E-Mail-Sendeknoten das Item beim Erfolg durch ihre eigene HTTP-Antwort ersetzen — gleiche Ursache wie der Write-Node-überschreibt-Item-Bug bei `06`s Empfehlungs-Writes). `onError: continueRegularOutput` neu an allen drei Sende-Nodes (Matrix-Report, E-Mail, Matrix-Fehler-Alert) — vorher killte ein SMTP-/Matrix-Ausfall den ganzen Lauf ohne Warnung.
- `00`: `Log Empfehlungswatchlist (SQL bauen)`, `Log Report-Pruef-Agent (SQL bauen)`, `Log Versand (SQL bauen)` hatten denselben toten Ternary-Bug wie `02` vor dessen Fix (`'success' === 'failed'`, immer `false` → `errorMessage` immer leer) — auf dasselbe `envelope.status`/`envelope.errors[]`-Muster umgestellt. Zwei neue Gates `IF: Empfehlungswatchlist ok?`/`IF: Versand ok?` (gleiches `status != 'failed'`-Muster wie bei `02`/`02b`/`10`) statt neuer Duplikat-Warnungs-Nodes wird der bereits bestehende, gemeinsame `Baue technische Warnung`-Node (der schon alle anderen Gates bedient) um die zwei neuen Fehlerquellen erweitert.
- Deploy-Skript `scratch/push_envelope_updates.py` (neu, wiederverwendbar): GET Live-Stand → Backup nach `n8n_live_backup/` → Node-Namen-Diff → PUT. Reihenfolge `10` → `06` → `05` → `00` eingehalten (kleinste additive Änderung zuerst, `00` zuletzt da abhängig von den `status`-Feldern der anderen drei).

**Funktionaler Live-Test — bestanden, ein echter Bug dabei gefunden und behoben:**

- Erster `00`-Testlauf (Execution 9171/9179) deckte sofort einen zweiten, tieferliegenden Bug in `06` auf: die neue Envelope-Kette lieferte `{}` statt des Envelopes an `00` zurück. Ursache #1 (behoben in Commit `41fed7f`): zwei nicht zusammengeführte Terminal-Nodes (`Abschluss-Ergebnis bauen` und die schon vorher offene `Matrix: Empfehlungs-Update senden`) — bei mehreren Leaf-Nodes ist der Rückgabewert eines Execute-Workflow-Aufrufs undefiniert. Ursache #2, tiefer und beim erneuten Test (Execution 9179) weiterhin reproduzierbar (behoben in Commit `02c1473`): n8n überspringt einen Node komplett, wenn **alle** seine Eingänge 0 Items liefern — nicht nur leere Ausgabe, sondern gar keine Ausführung (dieselbe Regel wie beim `08`-D+1..D+20-Crash-Fix vom 07-20). An einem Tag ganz ohne Empfehlungs-Kandidaten (leere Watchlist) liefen `IF: DRY_RUN aktiv?` und alles danach — inklusive der kompletten Envelope-Kette — überhaupt nicht. Fix: neuer `Envelope: Guard-Trigger`-Node hängt direkt an `Trigger-Eingabe normalisieren` (garantiert 1 Item, unabhängig von der Kandidatenzahl), eingespeist über einen dritten Merge, vor der Zählung explizit herausgefiltert. Bewusst NICHT die Schreib-Entscheidungskette selbst angefasst, um kein Risiko für Fehl-Schreibvorgänge bei leerem Input zu schaffen.
- Danach live bestätigt (Execution 9186): `06` liefert an einem kandidatenlosen Tag korrekt `{ok:true, processed:0, successful:0, failed:0, status:'skipped'}`, `Log Empfehlungswatchlist (SQL bauen)` schreibt `status:'skipped'` mit befülltem `metadata_json` statt leer, `IF: Empfehlungswatchlist ok?` lässt korrekt durch.
- `10` über drei aufeinanderfolgende reale Läufe bestätigt: `errors[]`/`warnings[]` korrekt mit den echten Prüf-Agent-Begründungen befüllt (`unsupported_claim`-Einträge, `missing_warnings`), `ok:false`/`status:'failed'` bei echter inhaltlicher Ablehnung — Governance-Verhalten wie gewollt, kein Pipeline-Fehler.
- `05` konnte nicht über einen echten `00`-Lauf getestet werden (Prüf-Agent hat drei Läufe in Folge abgelehnt) — stattdessen isoliert per `pinData` auf `Execute Workflow Trigger` getestet (`approved:true`, `DRY_RUN:false`, Testbericht klar als `TEST-VERSAND` markiert; Pin-Daten danach zurückgesetzt). Echter Versandpfad bestätigt (Execution 9191): Matrix-Nachricht zugestellt, E-Mail vom Mailserver angenommen (`250 2.0.0 Ok: queued`), beide Sende-Nodes korrekt getaggt, alle drei Merge-Nodes sauber durchlaufen, Endergebnis `{ok:true, processed:2, successful:2, failed:0, status:'success'}`.
- **Weiterhin ungetestet**: `05`s DRY_RUN- und Ablehnungs-Zweig (nutzen dasselbe, bereits bewährte Tag-Muster wie der getestete Erfolgszweig) sowie `IF: Versand ok?` in `00` selbst (die zugrundeliegende Envelope-Logik ist bewiesen korrekt, das Gate folgt exakt dem bereits getesteten `02`/`06`/`10`-Muster).

### Priorität 7, Punkt 17 — Durchgängige `run_id` (erledigt, live getestet)

`10 – Report- und Prüfagent`, `Reportdaten aufbereiten`: erzeugte bisher immer eine eigene `run_id` (`'report-' + heute + '-' + Date.now()`), auch wenn `10` als Sub-Workflow vom Orchestrator aufgerufen wurde — dadurch hatten `report-agent`/`pruef-agent`-Zeilen in `trading.agent_runs` nie dieselbe `run_id` wie der auslösende `00`-Lauf. Fix: liest jetzt per sicherem Try/Catch (`.all()[0]`) die `run_id` vom `Execute Workflow Trigger` und nutzt sie, falls vorhanden; Fallback auf eine lokal erzeugte nur bei eigenständigem Lauf. Live verifiziert: `00`s und `10`s `run_id` identisch, beide Agentenlauf-Zeilen tragen sie.

**Zusätzlich in dieser Runde behoben, unabhängig vom 29-Punkte-Auftrag**: der Cutover-Bug in `10`, der den täglichen Report seit der Produktions-Umstellung komplett blockierte (drei zusammenwirkende Ursachen: fragile `.item`-Referenzen über zwei Nodes, ein Node las versehentlich das Ergebnis des vorherigen Postgres-Writes statt der echten Report-Daten, kein definierter Sub-Workflow-Rückgabewert) — siehe Commit `c2cd1b9`.

### Priorität 8 — zentraler Error-Workflow (Teil 1+2 erledigt, live getestet, Stand 2026-07-21)

Nutzer-Entscheidung: Teil 1 (zentraler Workflow + überall verdrahten) + Teil 2 nur für die schlimmsten stillen Fälle (nicht alle 65 `continueRegularOutput`-Stellen).

Audit (Explore-Agent) über alle 13 Produktiv-Workflows ergab: kein Workflow hatte `settings.errorWorkflow` gesetzt; 15 riskante Nodes hatten gar kein `onError` (n8n-Default `stopWorkflow`, lauter Absturz, aber ungenutzt ohne aktive Beobachtung); 65 Nodes hatten `onError: continueRegularOutput`, aber **kein** nachgelagerter Node las das resultierende `error`-Feld — abgesehen von `05`/`06`, die bereits ein `_write_failed`/`_send_failed`-Muster aus Priorität 5/6 haben.

**Teil 1 — `11 – Zentraler Error-Handler.json`** (neu, n8n-ID `VTBfUuzQfMZNGYDM`): `errorTrigger`-Node → Code-Node extrahiert strukturierte Felder aus dem nativen Error-Trigger-Payload → parallel (a) `INSERT` in neue Tabelle `trading.workflow_errors` (`sql/005_workflow_errors.sql`), (b) Matrix-Alert. Isoliert getestet (gepinntes Fake-Payload). `settings.errorWorkflow` zeigt jetzt auf diesen Workflow in allen 13 Produktiv-Workflows — 12 per API deployt, `01 – Fundamentaldaten täglich` **manuell in der UI** gesetzt (hat live node-eigenes `retryOnFail`/`alwaysOutputData`, das ein API-PUT beim node-level-`settings`-Sanitizing sonst gelöscht hätte).

**Teil 2** — fünf gezielte `"... pruefen (sonst werfen)"`-Code-Nodes nach den konsequentesten stillen Write/Send-Stellen (Audit-Ranking): `03` (`Ergebnis persistieren`, News-Bewertung), `03a` (`Recherche-Ergebnis persistieren`, Zweitpass), `00` ×2 (`Log Gesamtlauf abgeschlossen`, `Matrix: Technische Warnung senden`), `08` (`Tracking-Zeile upserten`). Jeder prüft `$json.error` und wirft bewusst weiter, statt eigene Alert-Logik zu duplizieren — der Wurf wird vom in Teil 1 verdrahteten `errorWorkflow` abgefangen. Die übrigen ~60 `continueRegularOutput`-Stellen sind bewusst unverändert (Reads, redundante Audit-Logs, selbstheilende Cleanup-Operationen).

**Live verifiziert** (Execution 9235): `06`s `DB: Technische Signale laden (Empf.)` absichtlich auf eine ungültige Data-Table-ID gesetzt, über einen echten `Execute Workflow`-Aufruf ausgeführt (`mode: integrated`) → Matrix-Alert kam an, `trading.workflow_errors` korrekt befüllt. **Wichtiger Fund dabei**: n8ns Error-Workflow feuert grundsätzlich **nicht** bei `mode: manual` — auch nicht, wenn eine manuell gestartete Kette einen Sub-Workflow per `Execute Workflow`-Node aufruft (getestet: derselbe kaputte Node über einen manuell gestarteten Caller ausgeführt, `mode` blieb `manual`, kein Alert). Erst ein Aufruf, dessen Wurzel selbst nicht manuell war (hier: `06` als `mode: integrated` innerhalb eines Sub-Workflow-Aufrufs), löst den Handler aus — das ist aber exakt der Modus, in dem `00` seine Stufen im echten Betrieb aufruft, also produktionsrepräsentativ.

**Caveat** (Nutzer explizit mitgeteilt): "einheitliches Retry-Verhalten" wurde **nicht** als automatisches n8n-Node-Retry umgesetzt — die API lehnt node-level `settings` (dort liegt `retryOnFail`/`maxTries`) beim PUT grundsätzlich ab, das lässt sich über die bestehende Deploy-Pipeline nicht zuverlässig ausrollen. Der zentrale Handler liefert stattdessen einheitliche *Sichtbarkeit* aller unhandled Fehler. Echtes Retry bliebe ein manueller UI-Nachtrag pro Node.

### Noch offen aus dem 29-Punkte-Auftrag

- **Priorität 6**: erledigt und live getestet (siehe oben) — nur `05`s DRY_RUN-/Ablehnungs-Zweig und `IF: Versand ok?` selbst noch ungetestet (niedriges Risiko, gleiches bewährtes Muster wie der getestete Rest).
- **Priorität 7, Punkt 18**: einheitlicher `{context, config, payload}`-Input-Wrapper für alle Sub-Workflow-Aufrufe.
- **Priorität 8**: erledigt (siehe oben) — offen bleibt nur echtes automatisches Node-Retry (API-Limitation, s. Caveat).
- **Priorität 9**: Lernagent-Verfeinerung (Kennzahlen je Horizont, Mindestfallzahlen je Kombination, qualitätsgewichtete Bewertung).
- **Priorität 10**: Prompt-Injection-Härtung in allen KI-Nodes, strikte Schema-Validierung.
- **Priorität 11**: `pipeline_config` zur vollen zentralen Konfigurationstabelle ausbauen (Watchlist, Schwellenwerte, Modelle, Matrix-Räume, Prompt-Versionen — aktuell nur `DRY_RUN`/`REQUIRE_CONFIRMATION`).
- **Priorität 12**: Status-Übersicht (07) um Pipeline-Laufstatus, Wirkungsanalyse-Fortschritt, Trefferquoten, Konfigversion, Datenquellen-Aktualität erweitern.
- Offene Klärfrage zu Priorität 2: ob die FastAPI (`172.16.1.14:8099`) historische Kursdaten für einen Datumsbereich liefern kann (Backfill), statt ~20 Handelstage lang natürlich zu warten.
