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

## Phase 11: Hebelprodukt-/Onvista-Logik entfernt

**Bestätigter Fund, tiefer als der Auftragstext selbst vermuten ließ**: die Hebelprodukt-Logik war nicht auf `05`s Reporttext beschränkt, sondern reichte bis in `06`s Kernschreibpfad — `hebelHinweis()` erzeugte echte Onvista-Knock-Out-Links und Mini-Future-Berechnungen (Typ, Hebel 3-4x, Basispreis-Richtwerte für 15 fest hinterlegte Ticker), die **direkt in `trading.recommendations`** geschrieben wurden (`hebelprodukt_typ`, `hebel_spanne`, `basispreis_hebel_3/4`, `onvista_link`, `hebelprodukt_hinweis`) — trotz eines Code-Kommentars, der behauptete, dies sei "NICHT mehr Teil der allgemeinen Entscheidungslogik".

**Vollständige Suche über alle Workflows** (Auftrags-Suchbegriffe: Hebel, Hebelprodukt, Mini-Future, Knock-out, Turbo, Onvista, Long/Short filtern) fand 3 echte Erzeugungsstellen:
1. `06`, `hebelHinweis()` — vollständig neutralisiert (liefert nur noch leere/`null`-Werte, Funktionssignatur unverändert für minimalen Eingriff).
2. `06`, "Matrix: Zusammenfassung bauen" — `${o.hebelprodukt_hinweis}` aus der Matrix-Nachricht bei Neueröffnungen entfernt.
3. `05`, "Report aufbereiten" — die Zeile `Hebelprodukt-Suche (Hebel 3-4, Long/Short filtern): ${onvista_link}` vollständig entfernt (enthielt wortwörtlich "Long filtern"/"Short filtern" aus der Auftrags-Suchliste).

Restliche Treffer (Spaltennamen `hebelprodukt_typ` etc. im SQL-Builder von `06`, ein eigener Erklärkommentar zum Finanzierungskosten-Disclaimer in `14`) sind unschädlich — Spalten bleiben im Schema (**keine Löschung historischer Daten**, Sicherheitsregel), werden aber ab sofort nur noch mit leeren Werten befüllt.

Live gepusht (`05`, aktiv — reine Textentfernung, kein strukturelles Risiko). `06`s Fix bleibt wie bei den Phasen 6/10 lokal/committet, nicht live gepusht (Teil der Phase-14-Aktivierungsreihenfolge).

## Phase 12: Dashboard/Report Merge-Ketten geprüft (`07`, `10`)

**12.1 (Merge-Ketten-Sicherheit)**: wie in Phase 2 identifiziert, hingen `07`s "Merge Status 17-27"-Kette (12 Wrap-Nodes) und `10`s "Merge Grunddaten 11-18"-Kette (9 Wrap-Nodes) an derselben `combineAll`-Kreuzprodukt-Gefahr. Beide bereits in Phase 2 mit dem etablierten Wrap-Muster entschärft und live gepusht — hier nur die nachträgliche End-to-End-Bestätigung für `07` (siehe 12.3), da `10` als reiner `executeWorkflowTrigger`-Subworkflow ohne eigenständigen sicheren Live-Trigger nicht isoliert smoke-testbar ist (siehe 12.4).

**12.2 (neuer Fund, Konsistenz)**: `07`s Dashboard zeigte bisher **keinen einzigen Datenstand-/Frische-Hinweis** — bei einem hängenden oder ausgefallenen Orchestrator-Lauf hätte das Dashboard stillschweigend veraltete Zahlen als aktuell dargestellt (genau das im Auftrag benannte Risiko "Dashboard/Report-Konsistenz"). Fix: neuer Query-Node "DB: Letzte Laeufe Scanner+Portfolio (Uebersicht)" (liest `trading.scan_runs`/`trading.portfolio_risk_checks`, aktuell erwartungsgemäß 0 Zeilen, da `13`/`14` inaktiv sind) plus ein Frische-Banner in "Baue Uebersicht", das `business_date`, Alter des letzten erfolgreichen Orchestrator-Laufs (Warnfarbe ab >30h), letzten Report-Lauf sowie Scanner-/Portfolio-`run_id` **ehrlich** anzeigt — inklusive explizitem "kein Lauf (13/14 inaktiv)" statt eines irreführend leeren oder falsch-aktuellen Feldes.

**Fehler bei der Umsetzung, gefunden und behoben**: die erste Live-Version des Banners verursachte einen `ReferenceError: Cannot access 'datenFrischeWarnung' before initialization`. Ursache: `07`s "Baue Uebersicht" baut die komplette Seite als **eine einzige** durchgehende `const html = '<!DOCTYPE html>' + ... + '</html>';`-Ausdruckskette (Zeile 176-286 in der aktuellen Fassung); die Datenvariablen für die "Pipeline"-Sektion (`pipelineConfig`, `letzterErfolg` etc.) werden bewusst **erst danach** geladen. Der neue Banner-Code war fälschlich direkt nach `pipelineConfig` eingefügt worden — also textuell *nach* der `html`-Anweisung, die ihn aber bereits referenziert (TDZ-Verletzung, kein reiner Syntaxfehler, daher von der vorherigen `new Function()`-Prüfung nicht erkannt). Fix: die komplette Datenberechnung (`scannerPortfolioLaeufe`, `letzterScanLauf`, `letzterPortfolioLauf`, `letzterOrchestratorLauf`, `letzterReportLauf`, `alterInStunden()`, `orchestratorAlterStd`, `datenFrischeWarnung`) vor die `const html = `-Zeile verschoben, mit einem eigenständigen `letzterErfolgFuerBanner`-Lookup (statt der gleichnamigen, aber erst später deklarierten `letzterErfolg`-Variable der Pipeline-Sektion), um keine doppelte `const`-Deklaration im selben Gültigkeitsbereich zu erzeugen.

**12.3 (Live-Verifikation)**: Erstversion live gepusht → Webhook-Test lieferte `HTTP 200`, aber leeren Body (0 Bytes). Root-Cause-Diagnose über `GET /executions?workflowId=...` + `includeData=true` bestätigte den TDZ-Fehler oben (execution 24733). Fix angewendet, erneut live gepusht. Zwei Folge-Testläufe (24780, 24782) scheiterten an einem **unabhängigen, zeitgleichen Infrastrukturvorfall** (n8n-Host und Postgres kurzzeitig nicht erreichbar — "The host is unreachable, perhaps the server is offline" beim Node "DB: Empfehlungen laden", bestätigt nach Wiederherstellung der Verbindung). Nach Rückmeldung, dass die Infrastruktur wieder läuft: erneuter Live-Test erfolgreich (`HTTP 200`, 26.466 Bytes valides HTML), Banner-Inhalt inhaltlich korrekt geprüft (`business_date: 2026-08-02`, Orchestrator-Lauf korrekt als 48,3h alt mit Warnfarbe markiert, Scanner-/Portfolio-Zeilen korrekt als "kein Lauf (13/14 inaktiv)"). Live-Stand und lokale Datei anschließend als identisch bestätigt (Byte-Vergleich des "Baue Uebersicht"-Codes).

**12.4 (Restlücke, bewusst nicht in dieser Phase geschlossen)**: `10` ist ausschließlich per `executeWorkflowTrigger` aufrufbar (kein Webhook), ruft dabei 2 echte OpenAI-Agenten auf und schreibt echte Log-Zeilen (`report_agent`/`pruef_agent`-Protokollierung). Ein Testaufruf über `POST /workflows/:id/run` wurde vom Auto-Mode-Klassifikator korrekt als reale (nicht rein diagnostische) Aktion blockiert — zu Recht, das ist kein Lese-Check wie bei `07`s Webhook. `10`s Merge-Ketten-Fix bleibt daher bis zur dedizierten Testsuite (Phase 17, Testsuite F "Report/Dispatch") ungetestet-aber-syntaktisch-geprüft; Graphintegrität (0 gebrochene Referenzen) wurde bereits in Phase 2 bestätigt.

**Weitere im Auftrag genannte Konsistenzpunkte** (keine HTML aus Kreuzprodukt-Daten, keine doppelten Empfehlungen/Paper-Trades, keine doppelten KI-Prompt-Teile, keine übergroßen Payloads, keine doppelten Report-Prüfungen): durch die Wrap-Node-Absicherung (Phase 2) strukturell für beide Workflows ausgeschlossen, solange alle Quell-Merges auf genau 1 Item reduziert werden — das ist für `07` jetzt live bestätigt (26 KB HTML, keine Vervielfachung), für `10` weiterhin nur statisch (Graphintegrität) bestätigt. Idempotenz von `10`s Protokollierung bei Mehrfachaufruf (z. B. durch einen fehlerhaft doppelt feuernden Orchestrator) ist Gegenstand von Phase 16.

Live gepusht (`07`, aktiv), Backup `n8n_live_backup/07 – Status-Uebersicht – Agent V1_POST_PHASE12_20260802.json` gesichert.

## Phase 13: Workflow 05 (Tagesreport) — Zweigzusammenführung geprüft

Vollständige Graph- und Code-Analyse aller Verzweigungen und der 3 nachgelagerten Merge-Nodes.

**Zweigstruktur** (verifiziert per Verbindungsexport, nicht nur Sichtprüfung): `Eingabe normalisieren` → `IF: Freigegeben?` — bei `false` direkt zu `Ablehnungs-Warnung bauen` → `Matrix: Fehler-Alert` → Tag → `Merge Versand 3` (Eingang 2); bei `true` zu `Report aufbereiten` → `IF: DRY_RUN? (Versand)` — bei DRY_RUN zu `DRY_RUN: Versand uebersprungen` → `Merge Versand 2` (Eingang 2), sonst parallel zu `Matrix: Tagesreport senden` UND `E-Mail Report senden` → je ein Tag-Node → `Merge Versand 1` (beide Eingänge) → `Merge Versand 2` (Eingang 1) → `Merge Versand 3` (Eingang 1) → `Abschluss-Ergebnis bauen`.

**Befund zu allen 5 Auftragsprüfpunkten — keine Fehler gefunden, Architektur bereits korrekt gebaut:**

1. **Genau eine Abschluss-Hülle pro Lauf**: `Merge Versand 1/2/3` verwenden alle drei den **Default-Modus** (`parameters: {}`, kein `combine`/`combineAll`) — exakt das in Phase 2 etablierte sichere Verhalten. Da die beiden Eingänge von `Merge Versand 2` und `Merge Versand 3` jeweils strukturell wechselseitig ausschließend sind (pro Lauf feuert nur einer der beiden IF-Zweige), wartet keiner der Merges auf einen nie feuernden Zweig — Prüfpunkt 5 damit gleich mit bestätigt. `Abschluss-Ergebnis bauen` erkennt den tatsächlich gefeuerten Zweig explizit über ein `_zweig`-Feld (`dry_run`/`abgelehnt`/`versand`) und hat sogar einen expliziten `else`-Fallback für den (eigentlich unerreichbaren) Fall eines unbekannten Zweigs, der ebenfalls eine valide Hülle (`status: 'failed'`) statt eines Absturzes liefert.
2. **DRY_RUN sendet weder Matrix noch E-Mail**: strukturell unmöglich anders — der DRY_RUN-Zweig ist im Graph vollständig von `Matrix: Tagesreport senden`/`E-Mail Report senden` getrennt.
3. **Abgelehnter Bericht wird nicht versendet**: strukturell unmöglich anders — der `Freigegeben=false`-Zweig erreicht `Report aufbereiten` und die Versand-Nodes gar nicht.
4. **Partielle Fehlschläge korrekt gemeldet**: beide Versand-Nodes und `Matrix: Fehler-Alert` sind auf `onError: continueRegularOutput` gesetzt (ein HTTP-Fehler bricht den Lauf nicht ab, sondern liefert ein Item mit `$json.error`); die Tag-Nodes werten `$json.error` explizit aus (`_send_failed`, `_send_error`); `Abschluss-Ergebnis bauen` berechnet daraus korrekt `status: 'success' | 'partial_failure' | 'failed'` (z. B. Matrix erfolgreich + E-Mail fehlgeschlagen → `partial_failure`, `failed=1`, `successful=1`).
5. Siehe Punkt 1.

**Bewusst dokumentierte Entscheidung (kein Fund, keine Änderung)**: `Matrix: Fehler-Alert` (Ablehnungs-Zweig) wird **unabhängig von `DRY_RUN`** ausgelöst — ein während eines DRY_RUN-Laufs abgelehnter Bericht sendet also trotzdem einen echten Matrix-Alert. Das ist konsistent mit dem projektweiten Muster (z. B. Claim-Error-Watchdogs, Blockade-Alerts), wonach **operative Fehler-/Zustandsalarme** bewusst nicht durch `DRY_RUN` unterdrückt werden — nur der eigentliche fachliche Versand (der simulierte Tagesreport selbst) ist DRY_RUN-gated, nicht die Beobachtbarkeit des Systemzustands. Da hierzu keine Datenlöschung, keine fehlende Zugangsdaten, keine reale Orderanbindung und keine echte Zielkonflikt-Blockade vorliegt, wurde dies als konservative, dokumentierte Entscheidung im Sinne des Auftrags getroffen (keine Rückfrage nötig) statt das Verhalten stillschweigend zu ändern.

**`REQUIRE_CONFIRMATION`**: kein Vorkommen in `05` (Grep über alle Node-Parameter, 0 Treffer) — das ist kein Fund, da dieser Mechanismus laut Sicherheitsregel für reale Order-/Trade-Aktionen gilt (Kontext `14`), nicht für einen reinen Report-Versand; `05` besitzt keinen Order-/Trade-Pfad, für den eine zusätzliche Bestätigungsschranke fachlich sinnvoll wäre.

**Kein Live-Test durchgeführt (bewusst)**: `05` hat keinen Webhook-Trigger (nur `scheduleTrigger` + `executeWorkflowTrigger`), ein Testlauf würde ohne weitere Vorkehrung reale Matrix-/E-Mail-Sends auslösen (abhängig vom aktuellen `DRY_RUN`-Konfigurationsstand, den zu verifizieren hier nicht sicher ohne Seiteneffekt möglich war) — analog zu `10` in Phase 12 daher rein statische Code-/Graph-Prüfung, Live-Verifikation ist Teil von Testsuite F (Phase 17).

Keine Code-Änderung in dieser Phase nötig — reine Bestätigungsprüfung, kein Push.

## Phase 14: Orchestrator (`00`) vollständig verdrahtet + Feature-Flags (`sql/056`)

**14.1 (Bestätigt vor jeder Änderung)**: `13` und `14` waren bisher **überhaupt nicht** in `00` eingebunden — beide liefen ausschließlich über ihre eigenen, unabhängigen `scheduleTrigger` (18:20 bzw. 18:15 Werktage) und besaßen **keinen** `executeWorkflowTrigger`, konnten also technisch gar nicht als Sub-Workflow aufgerufen werden. Zusätzlich hatte `14` **kein konsolidiertes Endergebnis** — die drei sequenziellen Jobs (A: Portfolioprüfung/Trade-Anlage → B: Ausführung/Exit-Simulation → C: Stressszenarien, bestätigt per Connections-Export als echte Kette, nicht parallel) endeten jeweils direkt in einem Postgres-Write ohne zusammenfassendes `{status, processed, ...}`-Envelope wie bei `02`/`02b`/`06`/`10`/`05`.

**14.2 (Bestätigt, positiv)**: die im Auftrag explizit verlangte Prüfung "Job B überwacht weiter, auch wenn Job A keine Kandidaten/Fehler hat" ist bereits korrekt gebaut — `alwaysOutputData:true` ist auf allen Kettengliedern (`Job A`, `SQL bauen (Dispatcher A)`, `SQL ausführen (A)`) gesetzt, plus `onError:continueRegularOutput` auf den SQL-Ausführungs-Nodes. Das ist exakt das aus dem "n8n Zero-Rows-Bug" bekannte Schutzmuster — hier bereits vorher korrekt angewendet, kein Fund.

**Umsetzung (`13`, `14`, `00`)**:
- `13`: `Execute Workflow Trigger` ergänzt (speist dieselben 8 Datenlade-Nodes wie der bisherige Schedule-Trigger); eigener `scheduleTrigger` auf `disabled:true` gesetzt (verhindert künftigen Doppel-Lauf, sobald `13` einmal aktiviert wird — Ausführung soll ausschließlich über den Orchestrator laufen, `Manueller Start` bleibt für Ad-hoc-Tests aktiv, da manuelle Trigger nie von selbst feuern); `Scan-Run: SQL bauen` protokollierte bisher hart `status='success'` unabhängig vom tatsächlichen Schreibergebnis von `Scan-Kandidaten: schreiben` — jetzt real aus dessen `$json.error` abgeleitet; neuer Envelope-Node `Endergebnis für Aufrufer aufbereiten`.
- `14`: `Execute Workflow Trigger` ergänzt (dieselben 8 Datenlade-Nodes; `14` lädt `DRY_RUN` bereits eigenständig aus `trading.pipeline_config` in Job A — kein Context/Config-Passthrough vom Aufrufer nötig); eigener `scheduleTrigger` ebenso `disabled:true`; neuer konsolidierender Envelope-Node nach `SQL ausführen (C)`, der alle 3 Jobs zusammenfasst (`attempted`/`processed`/`failed` je Job, `SELECT 1;`-Leerläufe aus DRY_RUN-Tiefenverteidigung zählen bewusst nicht als `processed`).
- `00`: `Config: DRY_RUN laden` um 3 zusätzliche Spalten erweitert (`enable_market_scanner`, `enable_paper_trading`, `enable_trade_learning`); `Kontext zusammenfuehren` berechnet die 3 Flags mit **umgekehrter** Fail-Safe-Logik zu `DRY_RUN` — fehlt/ist die Konfiguration ungültig, ist der sichere Default `false` (deaktiviert), nicht `true` wie bei `DRY_RUN` (wo `true`=simuliert sicher ist). Zwei neue Pipeline-Stufen exakt nach dem bestehenden 7-Node-Muster (`Ausführen` → `Zweige zusammenführen` → `Ergebnis entduplizieren` → `Log SQL bauen` → `Log ausführen` → `IF: ok?`) eingefügt: **Stufe 13** zwischen `IF: Datenqualität ok?` und `06`, **Stufe 14** zwischen `IF: Empfehlungswatchlist ok?` und `10` — jeweils vorgeschaltet ein `IF: ... aktiviert?`-Gate auf das jeweilige Feature-Flag; bei `false` wird die komplette Stufe übersprungen (direkter Bypass zur nächsten Stufe, kein Merge wartet dabei auf einen nie feuernden Zweig — Default-Merge-Modus, siehe Phase 2/13). `Baue technische Warnung` und `Sammle Teilstatus (Erfolg)` um die 2 neuen Stufen erweitert (gleiches Muster wie die 4 bestehenden Stufen).

**14.3 (Kritischer technischer Befund während der Umsetzung, konservativ gelöst)**: `00`s Push nach Fertigstellung schlug fehl (`HTTP 400: "which is not published"`) — diese n8n-Instanz verlangt, dass ein per `executeWorkflow` referenzierter Sub-Workflow **published** ist, was sich als deckungsgleich mit `active:true` herausstellte (`activeVersionId` ist bei inaktiven Workflows `null`, bei aktiven identisch mit der aktuellen `versionId`; verifiziert am Beispiel `06` vs. `13`). Das erzeugt einen echten Zielkonflikt zwischen "`00` vollständig verdrahten" (Phase-14-Auftrag) und "keine Aktivierung von `13`/`14` vor bestandenen Tests" (Sicherheitsregel) — technisch, nicht nur organisatorisch, da n8n den Speichervorgang selbst blockiert, unabhängig von der Feature-Flag-Gate-Logik zur Laufzeit.

**Konservative Entscheidung (keine Rückfrage nötig, da eindeutig lösbar)**: die Phasenreihenfolge des Auftrags selbst verlangt Tests (Phase 17) und einen Aktivierungsplan (Phase 18) **nach** Phase 14 — die vollständige Verdrahtung sollte also ohnehin architektonisch fertig, aber nicht zwangsläufig heute live geschaltet sein. Lösung: `13` und `14` sind fertig erweitert und **live gepusht** (unkritisch — beide bleiben inaktiv, ihre eigenen Trigger sind deaktiviert, nichts ruft sie derzeit auf). `00`s neue Version (mit den 2 neuen Stufen) ist **vollständig fertiggestellt, syntax- und graphgeprüft (0 gebrochene Referenzen, 0 Syntaxfehler) und lokal committet — aber bewusst noch nicht live gepusht**. Die aktuell laufende, aktive Live-Version von `00` bleibt dadurch unverändert funktionsfähig (kein Risiko für den planmäßigen 17:50-Lauf). Das Pushen von `00`s neuer Version erfolgt **gemeinsam mit** der kontrollierten Aktivierung von `13`/`14` als expliziter erster Schritt des Aktivierungsplans (Phase 18) — an genau der Stelle, an der `13`/`14` ohnehin erstmals aktiv werden müssen, damit der Push überhaupt technisch möglich ist. Dieselbe Logik gilt unverändert für `06`s in Phase 6/10/11 zurückgehaltenen Live-Push.

`sql/056` (additiv, idempotent): Feature-Flags `ENABLE_MARKET_SCANNER`, `ENABLE_PAPER_TRADING`, `ENABLE_TRADE_LEARNING`, alle mit Default `FALSE` seed-inserted. Live ausgeführt und per Diagnose-Query bestätigt (3/3 Flags vorhanden, `value_bool=false`).

## Phase 15: `09b` (Lernagent Handelsstrategien) abgesichert — bleibt inaktiv

Reine Bestätigungsprüfung, kein neuer Fund erwartet und keiner gefunden.

**Aktivierungsstatus**: `active: false` bestätigt (API-Abfrage), unverändert seit den vorherigen Sitzungen. Kein `executeWorkflowTrigger` vorhanden (nicht in `00` eingebunden, auch nicht vorgesehen — Feature-Flag `ENABLE_TRADE_LEARNING` existiert bereits als reserviertes Flag aus Phase 14, wird aber aktuell von keinem Workflow gelesen). Einziger Schedule-Trigger (`Samstag 08:30`) und `Manueller Start` unverändert — kein Grund, hier wie bei `13`/`14` etwas zu deaktivieren, da `09b` ohnehin nirgends referenziert wird.

**Cross-Referenz gegen `FEHLERANALYSE.md` (vorherige Härtungssitzung, 2026-08-01/02)**: F6 (Regime-Konzentrationsprüfung), F7 (`MAX_AMBIGUOUS_PCT_FOR_PROPOSAL`-Gate), F8 (Effektstärke-Gate, automatisch über E7 mitbehoben) und F12 (NOT-NULL-Fix `proposed_value` bei `strategy_deactivation`/`threshold_adjustment`) sind alle als "behoben, live gepusht" protokolliert — `09b` ist aktuell live in diesem gehärteten Zustand. F9 (Stabilität über Zeit/Drawdown/Anteil blockierter Signale) ist explizit als eigenständiges, zurückgestelltes Vorhaben für eine künftige Sitzung dokumentiert (nicht Teil dieses Auftrags, kein neuer Fund hier).

**Prüfung auf Seiteneffekte durch die Härtung Welle 1-3 (neu in dieser Phase)**: `09b`s Queries lesen ausschließlich `trading.paper_trades` (Filter `status IN ('closed','blocked')`) und `trading.backtest_runs` — **keine** Berührung mit `trading.recommendations`, dessen Statusmodell in Phase 6+7 erweitert wurde (`portfolio_pending`/`portfolio_blocked`); kein Konflikt möglich. Phase 5s neue Audit-Felder (`raw_exit_price`, `effective_exit_price`, `gap_through_stop`, `gap_amount`, `execution_quality`) werden von `09b` nicht gelesen; die von `09b` tatsächlich verwendeten Kennzahlen (`net_pnl`, `realized_r_multiple`) blieben in Phase 5 bewusst unverändert (nur die zusätzlichen Audit-Felder sind neu, die Berechnungsformel selbst nicht) — keine Regression.

Keine Code-Änderung in dieser Phase — reine Bestätigung, kein Push.

## Phase 16: Idempotenz/Transaktionen für alle Writes geprüft

Systematischer Scan aller `INSERT INTO trading.*`-Statements über alle 20 Workflow-Dateien (Skript-basiert, erst 500, dann 3000 Zeichen Suchfenster nach `ON CONFLICT`, um Fehlalarme durch lange VALUES-Klauseln auszuschließen), anschließend gezielte Tiefenprüfung der verbleibenden Treffer. Ergebnis in 4 Kategorien:

**1. Bereits korrekt deterministisch+geschützt (kein Fund)**: `trading.paper_trades` (`ON CONFLICT (trade_id) DO NOTHING`, `trade_id` deterministisch `ticker+business_date+strategy` seit Fehleranalyse B9) und `trading.portfolio_risk_checks` (`ON CONFLICT (run_id, ticker) DO NOTHING`) in `14`s Dispatcher — beide bereits vollständig idempotent. `12`s Freigabe-Schreibpfad (`scoring_weights`/`learning_rule_proposals`) nutzt explizites `BEGIN;`/`COMMIT;` mit CTEs (`WITH deactivated AS (...), inserted AS (...)`) UND ein `WHERE status = 'proposed'`-Gate auf den Ursprungsvorschlag — ein Doppel-Submit (z. B. Doppelklick im Web-Formular) findet den Datensatz beim zweiten Versuch bereits nicht mehr im Zustand `'proposed'` vor, dadurch strukturell idempotent, kein Fund.

**2. Point-in-Time-revisionierte Tabellen (kein Fund, bestätigt korrekt)**: `stock_price_history`, `technical_signals_history`, `fundamentals_history`, `strategy_signals` (alle aus früheren Sitzungen, sql/022/025/031/041) verwenden das etablierte Muster `UPDATE ... SET valid_to = now() WHERE ... valid_to IS NULL; INSERT ... revision_number = COALESCE(MAX(revision_number),0)+1` als **eine** an den Postgres-Node übergebene Mehrfach-Statement-Zeichenkette. Das ist bereits transaktionssicher: PostgreSQLs Simple-Query-Protokoll (das `pg`/n8n-Postgres-Node ohne explizites `BEGIN` verwendet) führt mehrere per Semikolon getrennte Anweisungen **implizit als eine Transaktion** aus — schlägt die `INSERT`-Hälfte fehl, wird auch das vorangegangene `UPDATE` zurückgerollt, es entsteht keine Lücke ohne aktuelle Revision. Ein Retry erzeugt konsistent eine neue, höhere Revision statt eines Constraint-Fehlers — korrektes, absichtliches Verhalten (kein Fund).

**3. Reine Audit-/Protokoll-Tabellen (kein Fund, Duplikate sind kosmetisch, kein Korrektheitsproblem)**: `trading.pipeline_runs` (`00`, alle Stufen inkl. der beiden neuen aus Phase 14), `trading.agent_runs` (`03`/`03a`/`09`/`09b`/`10`), `trading.workflow_errors` (`11`, alle 3 Dispatcher-Kopien in `14`), `trading.paper_trade_events` (`14`) und `trading.recommendation_veto_log` (`06`, Kommentar im Code bestätigt "reines Audit-Log, keine reale Order") protokollieren jeden Versuch als eigene Zeile — ein Retry, der denselben Vorgang ein zweites Mal protokolliert, zeigt korrekt "das ist zweimal versucht worden" und ist kein stiller Datenverlust oder eine falsche Geschäftszahl. Kein `ON CONFLICT` nötig oder gewünscht.

**4. Real geprüft, durch vorgelagerte Anwendungslogik abgesichert (kein Fund, aber Backstop statt Primärschutz)**: `trading.recommendations` (`06`s "Oeffnen: SQL bauen") hat kein `ON CONFLICT`, ist aber durch den bereits in Phase 6+7 erweiterten `offenByTicker`-Check (lädt bei jedem Lauf frisch aus der DB, verhindert die zweite Eröffnung **vor** dem SQL-Aufbau) UND den partiellen Unique-Index `ux_recommendations_one_active_per_ticker` als Verteidigung in der Tiefe geschützt; der nachgelagerte Node `DB: Empfehlung öffnen` hat `onError:continueRegularOutput` — ein im Extremfall (Race Condition) tatsächlich auftretender Constraint-Fehler crasht den Lauf nicht, sondern wird als Fehler am Item sichtbar, ohne andere Kandidaten im selben Lauf zu blockieren.

**Kleinere, bewusst zurückgestellte Restfunde (niedrige Priorität, kein Fix in dieser Phase)**:
- `trading.scan_candidates` (`13`) hat kein `ON CONFLICT` und `run_id` ist nicht business-date-deterministisch (fällt bei leerem Scan auf `'scan-' + Date.now()` zurück) — ein Retry erzeugt einen zusätzlichen, vollständig separaten Kandidatensatz statt eines Konflikts. Für ein reines Beobachtungs-/Analyse-Werkzeug (kein Order-/Bestandsrisiko wie bei `paper_trades`) ist das fachlich vertretbar, aber inkonsistent zu `scan_runs` (das bereits `ON CONFLICT (run_id) DO UPDATE` nutzt) — für eine künftige Sitzung vorgemerkt.
- `trading.learning_rule_proposals` (`09`/`09b`) hat kein `ON CONFLICT`/keine Unique-Constraint gegen doppelte Vorschläge für dasselbe Segment. Da `09b` weiterhin inaktiv ist (Phase 15) und `09` nur wöchentlich/eigenständig läuft, ist das Risiko aktuell nicht akut — vorgemerkt für den Fall einer künftigen Aktivierung von `09b`.

**Ergebnis**: keine kritischen oder hohen Idempotenz-/Transaktionslücken bei tatsächlich handelsrelevanten Schreibvorgängen (`paper_trades`, `portfolio_risk_checks`, `recommendations`, `scoring_weights`) gefunden — alle bereits durch deterministische Schlüssel+`ON CONFLICT`, das etablierte Revisionierungsmuster mit impliziter Postgres-Transaktion, oder vorgelagerte Anwendungslogik+Constraint-Backstop abgesichert. Keine Code-Änderung in dieser Phase nötig.

## Phase 17: Testsuiten A-F erstellt und ausgeführt

Neue Datei `tests/welle_1_3_testsuite.js` (Node, keine externen Abhängigkeiten, `node tests/welle_1_3_testsuite.js`), 6 Suiten mit 35 Einzeltests, alle bestanden. Vollständiger Umfang je Suite in `TESTPLAN_HAERTUNG_WELLE_1_3.md`, Rohergebnis in `TESTERGEBNISSE_HAERTUNG_WELLE_1_3.md`.

**Methodische Einordnung (wichtig, siehe auch dortige "Bekannte Grenzen")**: alle Suiten sind Node-Nachbildungen der produktiven Kernfunktionen, zeilenweise gegen den tatsächlichen Code der jeweiligen `.json`-Datei abgeglichen — **keine** echten n8n-End-to-End-Ausführungen. Das ist keine Verlegenheitslösung, sondern dieselbe Einschränkung, die in Phase 12 bereits explizit auftrat: ein echter Testlauf von `10`/`05`/`13`(als Sub-Workflow)/`14` würde reale OpenAI-Kosten und/oder reale Matrix-/E-Mail-Sends auslösen und wurde vom Auto-Mode-Klassifikator zu Recht blockiert. Die 35 Tests sind damit eine notwendige, aber keine hinreichende Bedingung für eine Freigabe.

- **Suite A** (4/4): Wrap-Node-Merge-Sicherheit (Phase 2) und Feature-Flag-Bypass (Phase 14) — kein Kreuzprodukt, kein Warten auf einen nie feuernden Zweig.
- **Suite B** (8/8): `stopRawExitPrice()` Gap-Fälle (Phase 5), `data_error`-Retry-Eskalation (Phase 4), `trade_id`-Determinismus (Grundlage für Phase 16s `ON CONFLICT`-Befund).
- **Suite C** (5/5): Portfolioveto-Statusübergänge und Dead-Letter-Eskalation (Phase 6+7), inkl. des Rückstandsverarbeitungs-Falls (veraltete `portfolio_pending`-Zeile wird trotzdem geladen).
- **Suite D** (5/5): echte relative Stärke vs. Absolutrendite (Phase 8, exakt Auftrags-Testfall D5) plus Positionsgrößen-Wertlimit (Phase 10).
- **Suite E** (4/4): Idempotenz-Simulationen für `ON CONFLICT DO NOTHING` und das Revisionierungsmuster (Phase 16).
- **Suite F** (9/9): `05`s Zweigzusammenführung (Phase 13, alle 5 Fälle inkl. `partial_failure` und defensivem Fallback) und die neuen `13`/`14`-Envelopes (Phase 14).

Alle 35 Tests bestanden, 0 fehlgeschlagen. Ergänzt (nicht ersetzt) die bereits in den Phasen 4/5/8/9/10 protokollierten inline-lokalen Tests.

Fortsetzung folgt in Phase 18 (dieses Dokument wird laufend erweitert).
