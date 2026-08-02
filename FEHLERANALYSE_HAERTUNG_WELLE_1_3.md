# Fehleranalyse – Härtung Welle 1-3

Stand: 2026-08-02. Auftrag "Vollständige Härtung und betriebsfähige Integration der Handelsanalyse-Pipeline". Alle 11 genannten Workflow-Dateien vor der Analyse per `GET /workflows/:id` gegen Live abgeglichen (alle bereits synchron — Nodes/Connections identisch, kein Repo/Live-Drift vorhanden).

## Phase 1: Bestandsaufnahme

| Workflow | aktiv | fachliche Aufgabe | Eingabe | Ausgabe | Writes | bekannte Risiken | erforderliche Änderungen |
|---|---|---|---|---|---|---|---|
| `00` | ✅ | Orchestrator, 17:50 Werktage, ruft 02b/02/06/10/05 seriell | Trigger + `pipeline_config.DRY_RUN` | `pipeline_runs`-Logeinträge, Matrix-Warnungen | `pipeline_runs` (6 Log-Nodes) | `13`/`14` **nicht im Orchestrator verdrahtet** — laufen nur über eigene Schedule-Trigger, `00` weiß nichts von ihnen | Phase 14: Scanner/Portfolio kontrolliert einreihen, Feature-Flags |
| `02` | ✅ | Technische Signale + Strategiesignale täglich | Trigger (deaktiviert) oder Execute-Workflow-Aufruf von `00`, FastAPI-Kurse | `stock_technical_signals` (Data Table), `technical_signals_history`, `strategy_signals` | 4 DataTable-Writes, mehrere Postgres-INSERTs (nicht per Textmuster erkannt, da über `SQL bauen`-Zwischenschritt) | eigener Schedule-Trigger **deaktiviert** — läuft nur als Sub-Workflow von `00`, konsistent mit Doku | keine strukturelle Änderung nötig, Phase 9 prüft Regelqualität |
| `05` | ✅ | Tagesreport-Versand (Matrix+E-Mail) | Execute-Workflow-Aufruf von `00`, `10`s Envelope | Matrix/E-Mail, `pipeline_runs` | 0 direkte Postgres-Writes im Code | **eigenständiger `10`-Aufruf** ("standalone") zusätzlich zum von `00` übergebenen Envelope — zwei Quellen für dieselbe Information, Prüfpflicht Phase 13 | Phase 11 (Hebelprodukttext-Suche), Phase 13 (Zweigzusammenführung) |
| `06` | ✅ | Empfehlungs-/Kandidatenlogik, 12 harte Vetos | Execute-Workflow-Aufruf von `00`, `strategy_signals`/News/Regime | `recommendations` (offen/geschlossen) | mehrere Postgres-INSERTs/UPDATEs | **Kernbefund Phase 6**: schreibt `status='offen'` direkt, ohne auf `14`s Portfolio-Veto zu warten | Phase 6: `status='portfolio_pending'` als Zwischenzustand |
| `07` | ✅ | Status-Dashboard (Webhook, LAN) | Webhook-GET, liest fast alle `trading.*`-Tabellen | HTML-Dashboard | 1 Write (vermutlich Zugriffs-/Cache-Log) | **27 Merge-Nodes, 11 combine/combineAll** — größte Merge-Kette im gesamten System | Phase 2/12: Wrap-to-single-item-Muster |
| `09b` | ❌ (bewusst) | Lernagent Handelsstrategien | Manuell/Samstag 08:30 | `learning_rule_proposals` | 2 Postgres-Writes (Vorschlag, Agentenlauf) | bleibt laut Auftrag inaktiv — OOS-Gate blockt ohnehin jeden Vorschlag | Phase 15: nur prüfen, nicht aktivieren |
| `10` | ✅ | Report-Text + Prüfagent-Bewertung | Execute-Workflow-Trigger (von `00` UND `05` separat aufgerufen) | Envelope `{report_text, approved, ...}` an Aufrufer | 2 Postgres-Writes (Report-Agent, Prüf-Agent protokollieren) | **18 Merge-Nodes, 8 combine/combineAll** | Phase 2/12 |
| `11` | ✅ | Zentraler Error-Handler (ErrorTrigger) | n8n-interner Error-Trigger jedes anderen Workflows | Matrix-Alert, `workflow_errors` | 1 Postgres-Write | schlank, kein Merge-Risiko | keine |
| `12` | ✅ | Lernvorschlag-Freigabe (Web-UI) | Webhook GET/POST | Web-Formular, `learning_rule_proposals`-Updates | mehrere UPDATE-Pfade (5 Aktivierungstypen) | kein Merge-Risiko (0 Merge-Nodes) | keine strukturelle Änderung |
| `13` | ❌ (bewusst) | Markt-Screener, Stufe A/B | Manuell/18:20 Werktage | `scan_runs`/`scan_candidates` | mehrere Postgres-Writes | **7 von 7 Merge-Nodes combine/combineAll**, Stufe B nur Markierung (kein echter Tiefenanalyse-Workflow), reine Watchlist-Wiederverwendung statt echtem Universum, absolute statt relative Stärke | Phase 2, 8 — größter Umbau im gesamten Auftrag |
| `14` | ❌ (bewusst) | Portfoliorisiko + Paper-Trading (Job A/B/C) | Manuell/18:15 Werktage | `paper_trades`/`portfolio_risk_checks`/`stress_scenarios` | viele Postgres-Writes (Dispatcher-Muster) | **11 von 11 Merge-Nodes combine/combineAll**, `data_error`-Retry lädt nie nach (Phase 4), nur `entry_datum`-Filter statt Queue (Phase 7), kein Gap-through-Stop (Phase 5) | Phasen 2, 4, 5, 7 — zweitgrößter Umbau |

**Alle fachlichen Code-Nodes laufen mit `mode: runOnceForAllItems`** (explizit oder n8n-Default) und lesen ihre echten Daten über `$('NodeName').all()`-Rückverweise auf die Quellnodes, **nicht** über die gemergten `$input`/`$json`-Items. Das schützt bisher die **Schreib-Korrektheit** — es gab in keinem der Merge-Ketten-Workflows eine multiplikative Anzahl an SQL-Writes. Die `combineAll`-Ketten bauen aber trotzdem ein kartesisches Zwischenergebnis im Merge-Node selbst auf, bevor es (ungenutzt) verworfen wird — bei den im Auftrag genannten Fixture-Größen (100/25/500/80/30) ein reales Performance-/Speicherrisiko und ein Verstoß gegen das Abnahmekriterium, auch ohne fehlerhaftes Endergebnis.

**Kommentar-vs-Code-Drift**: keine gefunden in den 11 geprüften Workflows — im Gegenteil, mehrere Code-Kommentare (z. B. `14`s Sektor-Stressszenario vor dem Welle-3-Abgleich-Fix) beschrieben eine Einschränkung sogar akkurater als zunächst angenommen.

## Phase 2: combineAll-Merge-Ketten ersetzt

**Kernbefund vor der Änderung**: alle fachlichen Code-Nodes hinter den Merge-Ketten laufen mit `mode: runOnceForAllItems` und lesen ihre echten Daten über einen Namens-Rückverweis (`07`/`10` via eigene Helper `rows(nodeName)`/`safeAll(nodeName)` → `$(nodeName).all()`, `14` direkt `$('NodeName').all()`) — **nicht** über die gemergten `$input`/`$json`-Items. Die Schreib-Korrektheit war dadurch nie gefährdet. Trotzdem bauen `combine`/`combineAll`-Merge-Ketten ein reales kartesisches Zwischenergebnis im Merge-Node selbst auf, bevor es (ungenutzt) verworfen wird — bei den im Auftrag genannten Fixture-Größen ein Performance-/Speicherrisiko und ein Verstoß gegen das Abnahmekriterium.

**Nicht jeder Merge-Node war betroffen**: in `07` und `10` ist die Mehrheit der Merges (`Merge Status 1-16`, `Merge Grunddaten 1-10`) mit leeren `{}`-Parametern auf n8n-Default (append-Modus, sicher, keine Kreuzprodukt-Bildung) konfiguriert — nur ein hinterer Teilabschnitt jeder Kette (`Merge Status 17-27`, `Merge Grunddaten 11-18`) nutzt tatsächlich `combine`/`combineAll`.

**Lösung**: generische "Wrap-to-1-Item"-Funktion (`wrap_merge_chain.js`) — vor jeder direkten (Nicht-Merge-)Quelle einer betroffenen Kette wird ein Code-Node eingefügt, der `$input.all()` in **ein** Item (`{dataset, rows: [...]}`) verpackt. Die Merge-Kette kombiniert danach durchgehend 1×1×...×1 = 1 Item, unabhängig von der tatsächlichen Zeilenzahl jeder Quelle. Reine Graph-Änderung, kein einziger fachlicher Code-Node musste angefasst werden, da die Namens-Rückverweise unverändert auf dieselben (jetzt vorgeschalteten) Quell-Node-Namen zeigen.

| Workflow | betroffene Kette | Quellen gewrappt | aktiv? | Live-Verifikation |
|---|---|---|---|---|
| `14` | Merge A 1-7 (Job A) | 8 | ❌ (bewusst) | Graph-Integrität (0 defekte Referenzen), Push erfolgreich |
| `14` | Merge B 1-3 (Job B) | 4 | ❌ | s.o. |
| `14` | Merge C 1 (Job C) | 2 | ❌ | s.o. |
| `13` | Merge Vorbereitung 1-7 | 8 | ❌ (bewusst) | Graph-Integrität, Push erfolgreich |
| `07` | Merge Status 17-27 | 12 (inkl. Kettenende 16) | ✅ | **Live-Webhook getestet** (`GET /webhook/aktien-status`, HTTP 200, valides HTML, 25,5 KB, keine Fehlertexte) |
| `10` | Merge Grunddaten 11-18 | 9 (inkl. Kettenende 10) | ✅ | Graph-Integrität + Syntax-Check; **kein Live-Smoke-Test durchgeführt** (kein isolierter Trigger ohne Matrix-/KI-Seiteneffekt verfügbar — wird beim nächsten `00`-Lauf 17:50 real durchlaufen, siehe Restrisiken) |

**Alle anderen 7 Workflows geprüft** (`00`, `02`, `05`, `06`, `09b`, `11`, `12`) — keiner nutzt `combine`/`combineAll`, kein weiterer Fund.

**Nebenfund beim Push von `07`**: `PUT` schlug zunächst mit `HTTP 400 "settings must NOT have additional properties"` fehl — `settings.binaryMode` wird von n8ns Public-API-Schreibvalidierung nicht akzeptiert (bekanntes Muster, bereits aus dem ALLRIS-Projekt dokumentiert). Fix: `binaryMode` nur aus dem PUT-Payload entfernt (nicht aus der lokalen Datei), n8n behält den Wert serverseitig unverändert bei (per anschließendem GET bestätigt).

Fortsetzung folgt in den Phasen 3-18 (dieses Dokument wird laufend erweitert).
