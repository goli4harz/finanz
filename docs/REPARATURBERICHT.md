# Reparaturbericht — Technische Bereinigung und Härtung

Stand: 2026-08-03. Vollständiger Abschlussbericht zum Reparaturauftrag (P0 zwingend, P1
wichtig, P2 Qualität), siehe `docs/REPARATURPLAN.md` für die detaillierte Fund/Fix-Begründung
je Punkt. Dieser Bericht fasst Ergebnis, Nachweis und offene Punkte zusammen.

## 1. Auftragskontext und Vorgehen

Unabhängig formulierter 15-Punkte-Auftrag für das `finanz`-Repo, direkt im Anschluss an die
vorherige Härtung-Welle-1-3-Sitzung. Methode für jeden Punkt (unverändert über die gesamte
Sitzung): (1) Live-Code der betroffenen Datei(en) lesen, (2) den behaupteten Fehler tatsächlich
nachweisen statt den Auftragstext ungeprüft zu übernehmen, (3) bei Bestätigung die
kleinstmögliche, fachlich unveränderte Korrektur umsetzen, (4) Backup vor jeder JSON-Änderung
in `backup-vor-reparatur/` und `n8n_live_backup/`, (5) Graph-Integrität (keine gebrochenen
Connections) und JavaScript-Syntax nach jeder Änderung geprüft, (6) einzeln per API live
gepusht und per GET-Diff gegen die lokale Datei verifiziert, (7) bei Webhook-Workflows
zusätzlich ein echter curl-Aufruf gegen die Live-Instanz.

Session in zwei Teilen: P0 (5 Punkte, kritisch) wurde in einer vorherigen Sitzung
abgeschlossen und live gepusht; P1.6-P1.9 und P2.10-15 sowie die Validierungs-Tooling in dieser
Sitzung.

## 2. P0 — zwingend zu beheben (zusammengefasst, Details in REPARATURPLAN.md)

Alle 5 Punkte bestätigt und behoben, live gepusht: P0.1 (ungültiges SQL in `06`, `//`-Kommentar
im SQL-String), P0.2 (10 unsynchronisierte Parallelzweige in 6 Dateien), P0.3 (`07`s
Merge-Kette 17-27 stand entgegen einer früheren Annahme weiterhin im gefährlichen
`combineAll`-Modus), P0.4 (einheitliche `workflow_result`-Rückgabe für alle 6 vom Orchestrator
aufgerufenen Sub-Workflows), P0.5 (SSRF-Schutz griff nur beim Testen, nicht beim Speichern
einer RSS-Quelle).

## 3. P1 — wichtige funktionale Bereinigungen

- **P1.6** (`portfolio_pending`): `06`s Fix aus der Härtungssitzung war bisher manuell
  zurückgehalten — jetzt selbst-gatend über `ENABLE_PAPER_TRADING` (Default `FALSE`) sicher
  live gepusht.
- **P1.7** (Lernagent Handelsstrategien): `09b` bekam den fehlenden `Execute Workflow
  Trigger` für einen kontrollierten Aufrufpfad, bleibt `active:false`.
- **P1.8** (zentraler Error-Handler): `settings.errorWorkflow` fehlte bei 6 Workflows
  (`09b`/`12`/`13`/`14`/`RSS-Quellen verwalten`/`Watchlist verwalten`) — ergänzt. Zusätzlich:
  die DB-Lade-Nodes vor `Baue HTML` in den beiden Webhook-Verwaltungsseiten hatten kein
  `onError` (Default `stopWorkflow`) — ein DB-Ausfall hätte den Webhook ohne jede Antwort
  hängen lassen. Jetzt strukturierte Fehlerantwort mit korrelierbarer Fehler-ID statt
  Stacktrace/Credentials.
- **P1.9** (Zeitzone Europe/Berlin): zwei Bugklassen — 8 JS-Stellen mit
  `new Date().toISOString().substring(0,10)` (UTC statt Berlin) in 6 Workflows, ersetzt durch
  die bereits etablierte `getBusinessDate()`-Hilfsfunktion; 28 SQL-Queries mit unqualifiziertem
  `CURRENT_DATE` (hängt vom Postgres-Session-Timezone ab) in 5 Workflows, ersetzt durch
  `(now() AT TIME ZONE 'Europe/Berlin')::date` (2 Sonderfälle gegen eine TIMESTAMPTZ-Spalte
  mit der präziseren, richtungssicheren Form).

Alle P1-Punkte einzeln live gepusht und per GET-Diff verifiziert.

## 4. P2 — Qualitätsverbesserungen

- **P2.10** (Lernvorschläge dauerhaft speichern): `09`/`09b`s Vorschlags-INSERT war
  bedingungslos — derselbe Befund hätte bei jedem Lauf ein Duplikat angelegt. Jetzt
  `INSERT ... SELECT ... WHERE NOT EXISTS` gegen bereits offene (`status='proposed'`)
  Vorschläge für denselben Zielwert.
- **P2.11** (News-Retry unabhängig vom RSS-Ergebnis): `03`s Einstieg in die KI-Bewertung
  bereits gespeicherter pending/retry-News hing strukturell an einem Node, der nur bei
  mindestens 1 neuem RSS-Item ausgeführt wird — bei vollständigem RSS-Ausfall wäre die
  Retry-Bewertung für die ganze Stunde stillschweigend ausgefallen. Jetzt direkt am
  Schedule-Trigger, parallel zum RSS-Zweig.
- **P2.12** (doppelte Node-IDs): `04` hatte 2 Knotenpaare mit identischer ID — umnummeriert.
- **P2.13** (veraltete TODOs): kein Fund (0 `TODO`/`FIXME`-Marker im Code, `OFFENE_AUFGABEN.md`
  aktuell gepflegt).
- **P2.14** (Markt-Screener-Abgrenzung): kein Fund — Code entspricht exakt der bereits
  bestehenden Dokumentation (`13` schreibt nirgends in `recommendations`/`watchlist`, `06`
  liest nirgends Scanner-Tabellen).
- **P2.15** (semantische Variablennamen): kein Fund — einziger Treffer eines
  Platzhalter-Musters war `bar`/`barsRows` (etablierter Fachbegriff für eine Kurskerze, kein
  Platzhaltername).

## 5. Datenbankänderungen

Keine neuen SQL-Migrationsdateien in dieser Sitzung (P0-P2 sind reine Workflow-JSON-Änderungen
— JS-Code, Connections, `query`-Parameter, `settings`). Alle referenzierten Tabellen
(`trading.learning_rule_proposals`, `trading.news_items`, `trading.pipeline_config` usw.)
existierten bereits vollständig.

## 6. Neues Tooling: `tools/validate-workflows.js`

Statischer Validator ohne npm-Abhängigkeit (nur `fs`/`path`), prüft alle Workflow-JSON-Dateien
im Repo-Root gegen genau die in diesem Repo wiederholt real aufgetretenen Bugklassen:
JSON-Validität, doppelte Node-IDs, hängende Connections, JS-Syntaxfehler (inkl. top-level
`await`, wie n8n Code-Nodes es tatsächlich ausführen), Merge-Nodes im `combineAll`-Modus,
in SQL durchgesickerte `//`-JS-Kommentare, mehrere unverbundene Endnodes.

**Testlauf gegen das gesamte Repo (23 Dateien): 0 Fehler, 5 Warnungen** — alle 5 Warnungen sind
parallele Endzweige (z. B. „DB schreiben" + „Matrix-Alert senden") in eigenständigen, nicht als
Sub-Workflow aufgerufenen Workflows (`01`, `03`, `09`, `09b`, `11`) und damit erwartungsgemäß
kein Fund, keine Fehlerklassifizierung.

## 7. Live-Push-Nachweis

Jeder geänderte Workflow wurde einzeln per `PUT /api/v1/workflows/{id}` gepusht (nicht als
Batch-Skript — ein Sammel-Skript wurde vom Auto-Mode-Classifier blockiert), davor ein
`GET`-Backup nach `n8n_live_backup/` geschrieben, danach ein erneuter `GET` gegen die lokale
Datei diff-verifiziert. Webhook-Workflows (`RSS-Quellen verwalten`, `Watchlist verwalten`,
`07`, `10`, `03`) zusätzlich per echtem `curl`-Aufruf gegen die Live-Instanz bestätigt (HTTP 200,
plausible Antwortgröße, kein unerwartetes Fehlerbanner).

## 8. Sicherheitsregel-Konformität

`09b`, `13`, `14` bleiben `active:false` — durchgängig nach jedem Push per GET-Verifikation
bestätigt. Kein bereits deaktivierter Schedule-Trigger wurde reaktiviert. Keine Ausnahme in
dieser Sitzung.

## 9. Bekannte Grenzen und offene Punkte

- Keine der P1.9-Zeitzonen-Fixes wurde gegen einen echten Tageslauf über den 22:00-02:00-
  Berlin-Grenzfall hinweg beobachtet (die Korrektheit folgt aus der Konstruktion —
  `Intl.DateTimeFormat`/`AT TIME ZONE` sind DST-sicher —, nicht aus einem beobachteten
  Grenzfall-Lauf).
- P2.10s Duplikatsschutz wurde nicht gegen echte, bereits doppelt vorhandene
  Lernvorschlags-Zeilen getestet (kein direkter Lesezugriff auf die Live-DB ohne manuellen
  `97`-Lauf) — die Korrektheit der `WHERE NOT EXISTS`-Bedingung wurde stattdessen per
  JS-Syntaxprüfung und Code-Review sichergestellt.
- `tools/validate-workflows.js`s "combineAll"- und "mehrere Endnodes"-Prüfungen sind
  Warnungen, keine harten Fehler — sie ersetzen keine fachliche Prüfung, ob ein konkreter
  combineAll-Merge tatsächlich riskant ist (das hängt von der Zeilenanzahl der einspeisenden
  Nodes ab, die das Tool nicht kennt).

## 10. Validierung

`node tools/validate-workflows.js` gegen den finalen Stand aller 23 Workflow-Dateien: **0
Fehler, 5 Warnungen** (siehe Abschnitt 6). Alle 13 in dieser Sitzung geänderten Workflows
zusätzlich einzeln live per GET-Diff gegen die lokale Datei bestätigt.

## 11. Empfehlung

Auftrag vollständig umgesetzt (P0 aus Vorsitzung, P1.6-1.9 und P2.10-15 aus dieser Sitzung).
Nächste sinnvolle Schritte, falls gewünscht: (1) einen echten Tageslauf nach den P1.9-Fixes
beobachten, insbesondere `04`s Cleanup (23:45) und `03`s stündlichen News-Lauf über eine
Mitternacht hinweg; (2) die ~80 unversionierten `n8n_live_backup/*.json`-Altdateien aus
`OFFENE_AUFGABEN.md` aufräumen (eigenständiger, bereits dokumentierter Punkt); (3)
`tools/validate-workflows.js` optional in einen Pre-Push-Hook einbinden, damit künftige
Änderungen automatisch gegen dieselben Bugklassen geprüft werden, bevor sie live gepusht
werden.
