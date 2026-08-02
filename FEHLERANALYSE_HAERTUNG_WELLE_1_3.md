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

## Phase 3: Live-Schema-Verifikation (kritischer Fund)

Diagnose-Query gegen `information_schema`/`pg_constraint`/`pg_indexes` (19 Einzelprüfungen) über Workflow `97`, Ergebnis per `GET /executions/:id?includeData=true` gelesen statt Nutzer-Abtippen.

**Kritischer Fund**: 4 von 19 Prüfungen fielen negativ aus — allen voran **`sql/045` (Fehleranalyse B9) war nie tatsächlich ausgeführt worden**, obwohl der zugehörige Code in Workflow `14` bereits live gepusht war und auf die fehlende `paper_trade_events.business_date`-Spalte sowie drei fehlende UNIQUE-Indizes (`ux_paper_trade_events_trade_type_date`, `ux_portfolio_risk_checks_run_ticker`, `ux_stress_scenarios_run_scenario`) verwies. **Hätte `14` in diesem Zustand aktiviert oder manuell ausgeführt werden, wäre jeder einzelne Schreibvorgang in Job A, B und C mit einem SQL-Fehler abgestürzt** (referenzierte Spalte/Constraint existiert nicht) — exakt das Szenario, vor dem Phase 3 des Auftrags warnt ("Kein Workflow darf aktiv bleiben, wenn er in Spalten schreibt, die im Live-Schema fehlen").

**Root Cause**: `sql/045` wurde im Verlauf der vorherigen Sitzung in Workflow `97`s Query-Node geladen, aber bevor der Nutzer es ausführen konnte, mit `sql/046`s Inhalt überschrieben (derselbe Node kann nur eine Query gleichzeitig halten) — die Ausführungsbestätigung des Nutzers galt de facto nur noch `sql/046`. Ebenso betroffen: `sql/043` (`MAX_AMBIGUOUS_PCT_FOR_PROPOSAL`-Seed für Fehleranalyse F7) — dort aber folgenlos, da der Code bereits einen sicheren Fallback-Default (20.0) hatte.

**Behoben**: `sql/043`+`sql/045` erneut geladen und vom Nutzer ausgeführt, per zweiter Diagnose-Query bestätigt (alle 5 betroffenen Punkte jetzt `true`).

**Lehre für künftige Sitzungen**: wenn mehrere Migrationen nacheinander in denselben Einmalig-Query-Node geladen werden, muss die Ausführung JEDER einzelnen explizit bestätigt werden, bevor die nächste geladen wird — ein "ist ausgeführt" nach dem Laden von Migration N+1 ist kein Nachweis, dass auch Migration N lief. `trading.schema_migrations` (Fehleranalyse G1) mindert dieses Risiko für künftige Migrationen, wurde hier aber selbst noch nicht als Verifikationsquelle genutzt (nur `information_schema` direkt).

### Vollständige Diagnosetabelle (finaler Stand, alle ✅)

| Objekt | erwartet | vorhanden | Migration | verwendet durch |
|---|---|---|---|---|
| `strategy_signals.configuration_version`/`data_schema_version` | TEXT | ✅ | sql/050 | `02`, `06` |
| `paper_trades.financing_cost` | NUMERIC | ✅ | sql/048 | `14` Job B |
| `paper_trades.data_error_count/_first_at/_last_at` | diverse | ✅ | sql/039 | `14` Job B |
| `paper_trades_status_check` (inkl. `data_error_final`) | CHECK | ✅ | sql/039 | `14` Job B |
| `portfolio_risk_checks.sequence_index`/`state_snapshot` | diverse | ✅ | sql/039 | `14` Job A |
| `learning_rule_proposals.rule_version`/`learning_model_version` | TEXT | ✅ | sql/050 | `09`, `09b` |
| `pipeline_config.MAX_REGION_EXPOSURE_PCT`/`MAX_NON_EUR_EXPOSURE_PCT` | Zeile | ✅ | sql/049 | `14` Job A |
| `pipeline_config.MAX_AMBIGUOUS_PCT_FOR_PROPOSAL` | Zeile | ✅ (nachgezogen) | sql/043 | `09b` |
| `pipeline_config.AMBIGUOUS_BAR_POLICY_CODE` | Zeile | ✅ | sql/042 | `14` Job B |
| `pipeline_config.LEARNING_MIN_NEWS_SAMPLE_SIZE` | Zeile | ✅ | sql/046 | `09` |
| `paper_trade_events.business_date` | DATE | ✅ (nachgezogen) | sql/045 | `14` Job B |
| `ux_paper_trade_events_trade_type_date` | UNIQUE INDEX | ✅ (nachgezogen) | sql/045 | `14` Job B |
| `ux_portfolio_risk_checks_run_ticker` | UNIQUE INDEX | ✅ (nachgezogen) | sql/045 | `14` Job A |
| `ux_stress_scenarios_run_scenario` | UNIQUE INDEX | ✅ (nachgezogen) | sql/045 | `14` Job C |
| `trading.schema_migrations` | TABLE | ✅ | sql/044 | alle künftigen Migrationen |

## Phase 4: data_error-Retry repariert (`sql/051`)

**Bestätigter Fund**: Fehleranalyse E8s Fix vom 2026-08-01 baute den Retry-Zähler/Eskalationsmechanismus, vergaß aber die Ladequery selbst zu erweitern — der eigene Code-Kommentar benannte das Problem sogar wörtlich ("die Ladequery kennt diesen Status nicht"), ohne es zu beheben. `data_error` war seither eine dauerhafte Sackgasse, der Zähler kam nie über 1 hinaus.

**Fix**:
- `DB: Ausstehende/offene Paper-Trades laden` um `OR status = 'data_error'` erweitert (`data_error_final` bleibt bewusst terminal, nicht mit aufgenommen).
- Neue Spalte `paper_trades.pre_data_error_status` (`sql/051`) — beim ersten Fehleintritt wird der aktuelle Status (`open`/`proposed`) gesichert, bei wiederholtem Fehlschlag bleibt der gespeicherte Wert unverändert (nicht mit `'data_error'` selbst überschrieben).
- Wiederherstellung: sobald wieder eine gültige Kerze vorliegt, wird der Status aus `pre_data_error_status` restauriert (per SQL aus der DB, nicht aus dem möglicherweise veralteten In-Memory-Wert) und Zähler/Marker zurückgesetzt. Bewusst konservativ: der wiederhergestellte Trade wird **in diesem Lauf nicht mehr** fill-/exit-geprüft — das passiert garantiert unbelastet erst im nächsten Lauf.

**Tests** (lokal simuliert, 6/6 bestanden): erster Fehltag → `data_error`, Zähler=1; zweiter Retry → Zähler=2, `pre_data_error_status` bleibt erhalten; erfolgreiche Wiederherstellung → Status restauriert, Zähler=0; Erreichen von `MAX_DATA_ERROR_RETRIES` → genau eine Eskalation zu `data_error_final`; `data_error_final` taucht nicht in der Ladequery auf (strukturell terminal). "Keine doppelten Events bei Wiederholung desselben Laufes" ist durch SQL selbst garantiert (eine Zeile wird pro Lauf höchstens einmal geladen).

Live gepusht (`14`, inaktiv) und Migration ausgeführt, per Diagnose-Query bestätigt.

## Phase 5: Gap-through-Stop konservativ simuliert (`sql/052`)

**Fund**: Stop-Exits wurden bisher immer exakt zum Stop-Preis simuliert (`exitPrice = stop`), unabhängig davon, ob die Tageskerze durch den Stop gap-te — unrealistisch günstig, überzeichnete `net_pnl`/`realized_r_multiple` systematisch bei jedem echten Gap-Exit.

**Fix**: `stopRawExitPrice()` gap-bewusst (Long: `Open < Stop ? Open : Stop`, Short: `Open > Stop ? Open : Stop`, exakt die Auftragsformel). Ziel bleibt bewusst **immer** exakt der Zielkurs — kein rückwirkend optimaler Gap-Kurs, auch bei einem sehr günstigen Gap über das Ziel hinaus. Neue additive Felder (`sql/052`): `raw_exit_price`, `effective_exit_price` (reines Audit-Feld, Slippage/Gebühren je Aktie in ungünstiger Richtung — `net_pnl` selbst bleibt über die bereits getestete wertbasierte Formel aus Fehleranalyse E6/E7 berechnet, um dort keine Regression zu riskieren), `gap_through_stop`, `gap_amount`, `execution_quality` (`exact_stop`/`gap_through_stop`/`exact_target`/`close_fallback`). `execution_model_version`/`ambiguous_execution` existierten bereits.

**Tests** (lokal simuliert): Long normaler Stop, Long Gap unter Stop, Short normaler Stop, Short Gap über Stop, Gap über Ziel (bleibt exakt Zielkurs), Stop+Ziel in derselben Kerze (conservative_stop_first) — alle 6 bestanden (ein erster Testlauf hatte fehlerhafte Testdaten für Fall 3, korrigiert, Logik war von Anfang an richtig). Fehlende Open-Angabe/Datenanomalie: bereits durch den bestehenden `data_error`-Guard vor dieser Logik abgefangen (siehe Phase 4). Gebühren-macht-Gewinn-negativ: unverändert über die bereits getestete E7-Formel abgedeckt.

Live gepusht (`14`, inaktiv), Migration ausgeführt und per Diagnose-Query bestätigt (5/5 neue Spalten vorhanden).

## Phase 6+7: Empfehlung/Portfolioveto-Statusmodell + Rückstandsverarbeitung (`sql/053`)

Beide Phasen hängen an derselben Stelle (`14`s Ladequery für neue Empfehlungen) und wurden zusammen behoben.

**Bestätigter Fund (Phase 6)**: `06`s "Oeffnen: SQL bauen" schrieb `status='offen'` fest in die INSERT-VALUES-Klausel — **unbedingt, ohne jede Portfoliorisiko-Prüfung**. `14` (Job A/Dispatcher A) schrieb **zu keinem Zeitpunkt** auf `trading.recommendations` zurück (nur auf `paper_trades`) — bestätigt per Code-Grep (`jobA.parameters.jsCode.includes('recommendations')` → `false`). Eine von `14` blockierte Position ließ die zugehörige Empfehlung dauerhaft als `status='offen'` stehen, während `paper_trades.status='blocked'` — exakt der im Auftrag beschriebene Widerspruch, kein hypothetisches Szenario.

**Bestätigter Fund (Phase 7)**: `14`s "DB: Heutige neue Empfehlungen laden" filterte zusätzlich auf `entry_datum = CURRENT_DATE` — ein verspäteter/unterbrochener Lauf hätte eine Empfehlung dauerhaft verloren.

**Fix**: neuer Zwischenzustand `portfolio_pending` (06 schreibt diesen statt `offen`), `14` löst ihn nach der Portfolioprüfung auf zu `offen` (genehmigt) oder `portfolio_blocked` (abgelehnt) — inklusive Blocker-Begründung, Risikowerten vorher/nachher und Verweis auf die zugehörige `portfolio_risk_checks`-Zeile (`portfolio_check_id`, per Subquery über `(run_id, ticker)` aufgelöst, dank der `UNIQUE(run_id,ticker)`-Garantie aus Fehleranalyse B9). `14`s Ladequery wurde rein statusbasiert (`WHERE status = 'portfolio_pending'`, kein Datumsfilter mehr) — löst Phase 7 automatisch mit, da dieselbe Query betroffen ist: jede noch unaufgelöste Zeile wird beim nächsten Lauf verarbeitet, unabhängig vom Anlagedatum. Dead-Letter-Eskalation nach `MAX_PORTFOLIO_CHECK_ATTEMPTS` (Default 5, config-getrieben) mit `workflow_errors`-Eintrag, gleiches Muster wie Fehleranalyse E8/Phase 4.

Der bestehende partielle Unique-Index (`ux_recommendations_one_open_per_ticker`, nur `status='offen'`) wurde ersetzt durch `ux_recommendations_one_active_per_ticker` (`status IN ('offen','portfolio_pending')`) — sonst könnte `06` denselben Ticker zweimal vorschlagen, während der erste Kandidat noch auf `14` wartet. `06`s eigene `offenByTicker`-Prüfung wurde entsprechend erweitert.

**Bewusste Zurückstellung des Live-Pushes für `06`**: der Code-Fix in `06` ist fertig, syntaxgeprüft und im Repo committet — aber **noch nicht live gepusht**, da `14` aktuell inaktiv und noch nicht in den Orchestrator (`00`) eingebunden ist (das ist erst Phase 14). Würde `06`s Änderung jetzt live gehen, bliebe **jede künftige Empfehlung dauerhaft in `portfolio_pending` stecken**, da nichts sie auflösen würde — das hätte den laufenden Produktivbetrieb stiller beschädigt, als der ursprüngliche Fund es tat. `sql/053` (rein additiv: neue Spalten + erweiterter Unique-Index) wurde dagegen bereits live ausgeführt — unschädlich, solange `06` weiterhin nur `'offen'` schreibt. **`06`s Live-Push ist Teil der in Phase 14 zu planenden, kontrollierten Aktivierungsreihenfolge.**

Live gepusht (`14`, inaktiv) und Migration ausgeführt, per Diagnose-Query bestätigt (4/4 neue Spalten vorhanden).

## Phase 8: Markt-Screener fachlich korrigiert (`sql/054`)

**8.1 (bestätigt)**: "DB: Universum laden" war wörtlich identisch mit der Watchlist-Query (`stock_instruments WHERE aktiv=TRUE`). Neue unabhängige Flags `watchlist_active`/`scanner_active` (aus `aktiv` befüllt, verhaltensneutral) — Scanner-Universum bleibt bewusst == Watchlist, jetzt aber strukturell/dokumentiert statt zufällig gekoppelt.

**8.2 (bestätigt, kritisch)**: `relativeStrength()` berechnete ausschließlich eine Absolutrendite — exakt das im Auftrag verbotene Muster. Umbenannt zu `absoluteReturn()`, echte `relativeStrengthVsIndex()` ergänzt (`Aktienrendite − Referenzindexrendite`, via `stock_instruments.benchmark_symbol`). Referenzindex-Kursdaten (`^GDAXI`/`^GSPC`/`^IXIC`/`^MDAXI`/`^STOXX50E`) waren bereits in `stock_price_history` vorhanden (von `02b` mitgeladen) — keine neue Datenquelle nötig. `sector_relative_strength` bewusst `not_available` (kein Sektor-Index verfügbar). 3 lokale Tests bestanden, darunter exakt Testfall D5 aus dem Auftrag ("negative relative Stärke trotz positiver Absolutrendite").

**8.3**: `scan_candidates.analysis_status='pending'` strukturell ergänzt. Der eigentliche Tiefenanalyse-Workflow bewusst **nicht** gebaut — eigenständiges Projekt in der Größenordnung eines Teils von `02`/`06`, nicht sinnvoll als Unterpunkt dieser Sitzung.

**8.4**: zeitliche Reihenfolge — Cross-Referenz zu Phase 14 (Orchestrator-Einreihung).

Live gepusht (`13`, inaktiv), Migration ausgeführt und per Diagnose-Query bestätigt (3/3 Prüfungen ok). `docs/MARKTSCANNER.md` aktualisiert.

## Phase 9: Strategieregeln gehärtet

Live-Code-Check aller 4 Strategien gegen die Auftrags-Mindestanforderungen:

- **Mean Reversion (bestätigt, kritisch)**: `if (rsiVal < 35 || kursBeiUnten) mrDirection = 'long'` — ein moderates RSI (z. B. 34) **allein** setzte bereits eine Richtung, exakt das im Auftrag verbotene Muster ("Ein Einstieg darf nicht allein auf einem moderat niedrigen oder hohen RSI beruhen"). Fix: echtes UND aus RSI-Überdehnung (strengere Tier-Schwelle `<32`/`>68`) UND Preisüberdehnung (Bollinger-Berührung oder EMA20-Abstand `>1%`).
- **Breakout (bestätigt, kritisch)**: `if (distZuHoch < 0.02) boDirection = 'long'` — reine Nähe zum 52-Wochen-Hoch (auch von unten, kein tatsächlicher Ausbruch) setzte die Richtung **ohne jede Volumenbestätigung**. Fix: echter Ausbruch (`aktuellerKurs >= hoch52wRaw`, nicht nur "nahe dran") UND Volumenbestätigung (`volumenErhoeht || volumenOk`) als Pflichtbedingung.
- **Trend Following**: bereits korrekt — `if (macdValRaw > macdSignalValRaw && trendAufwaerts)` ist eine echte UND-Bedingung (Momentum UND Trendlage), kein Fund.
- **News/Event** (in `06`): bereits korrekt — Nachrichtenfilter ist hart auf den heutigen Kalendertag begrenzt (`(ni.published_at AT TIME ZONE 'Europe/Berlin')::date = heute`), Richtung erfordert Übereinstimmung mit dem technischen Signal (sonst kein Signal), widersprüchliche gleichtägige starke News blockt bereits (Welle 1), fester plausibler Zeithorizont (2 Tage). Kein Fund.

6/6 lokale Tests bestanden (3 Mean-Reversion-Fälle, 3 Breakout-Fälle). Live gepusht (`02`, aktiv — reine Verschärfung, kein strukturbrechendes Risiko wie bei Phase 6, daher ohne Zurückhaltung gepusht).

## Phase 10: Positionsgrößen-Wertlimit tatsächlich durchgesetzt (`sql/055`)

**Bestätigter Fund (kritisch)**: `computeRisk()` in `06` berechnete `theoretical_quantity` ausschließlich aus dem Risikolimit (`riskAmount / unitRisk`). `MAX_POSITION_VALUE_PCT` floss nur in das rein informative `position_value_pct` ein, wurde aber **nie** als tatsächliche Obergrenze auf die Stückzahl angewendet — ein reiner Hinweis statt eines echten Limits, exakt der im Auftrag benannte Fund.

**Fix**: `quantityByValue = floor(MODEL_PORTFOLIO_VALUE * MAX_POSITION_VALUE_PCT / 100 / entry)` ergänzt, `theoreticalQuantity = min(quantityByRisk, quantityByValue)` (exakte Auftragsformel). Neue Felder: `quantity_by_risk`, `quantity_by_value`, `position_size_limiting_factor` (`risk`/`value`), `risk_amount_before_limit`. **Wichtige Konsequenz**: `risk_amount` selbst ist jetzt der tatsächlich realisierte Betrag nach Begrenzung (nicht mehr der unbegrenzte theoretische Wert) — das ist der Wert, den `14`s Portfoliorisiko-Summierung und `realized_r_multiple` in Job B ohnehin schon verwenden; der ursprüngliche unbegrenzte Wert bleibt separat als Audit-Feld erhalten. Neuer Veto `QUANTITY_ZERO`: "Bei Stückzahl null darf keine Position geöffnet werden" (Auftragsvorgabe wörtlich) — durch das neue Wertlimit erstmals überhaupt möglich (ein sehr teurer Titel, bei dem schon 1 Stück das Limit überschreitet).

3/3 lokale Tests bestanden (Risiko bindet im Normalfall, Wertlimit bindet bei teurem Titel, Stückzahl 0 bei extrem teurem Titel).

Migration live ausgeführt und bestätigt. **`06`s Code-Fix bleibt wie bei Phase 6 lokal/committet, aber nicht live gepusht** — Teil derselben, in Phase 14 zu planenden Aktivierungsreihenfolge.

Fortsetzung folgt in den Phasen 11-18 (dieses Dokument wird laufend erweitert).
