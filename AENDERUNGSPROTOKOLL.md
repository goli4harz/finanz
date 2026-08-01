# Änderungsprotokoll

Stand: 2026-08-01. Protokolliert alle Änderungen aus der Fehlerbereinigung/Härtung, siehe `FEHLERANALYSE.md` für die zugrundeliegenden Befunde.

Für jede Datei: vorheriges Verhalten, neues Verhalten, mögliche Nebenwirkungen, notwendige Migration, notwendiger Reimport.

---

## `Watchlist verwalten.json`
- **Vorher:** `pgArr()` escapte kein einfaches Anführungszeichen → SQL-Injection über Keywords/Ausschlussbegriffe möglich. Keine Ticker-/Feldvalidierung. Ungültige Eingaben zeigten eine normale Erfolgsseite.
- **Nachher:** Array-Werte über `ARRAY[pgStr(...),...]` gebaut (jedes Element korrekt escaped). Ticker-Regex, Pflichtfelder, Längenlimits serverseitig geprüft. Sichtbares Fehlerbanner bei ungültigen Eingaben.
- **Nebenwirkungen:** Keine funktionale Änderung für gültige Eingaben. Extrem lange Keyword-Listen (>30 Einträge) oder sehr lange Einzelwerte (>50 Zeichen) werden jetzt abgelehnt statt stillschweigend akzeptiert.
- **Migration:** keine.
- **Reimport:** bereits live gepusht (commit `d3996e8`, `27c39a6`).

## `RSS-Quellen verwalten.json`
- **Vorher:** Jede gespeicherte URL wurde ungeprüft abgerufen (SSRF möglich gegen jedes LAN-Ziel inkl. n8n selbst).
- **Nachher:** Protokoll-/Hostname-/IP-Prüfung vor jedem Abruf (blockiert Loopback/Link-Local/private Bereiche/lokale Hostnamen).
- **Nebenwirkungen:** Redirects bleiben aktiv (Deaktivierung brach einen echten Feed mit legitimem 301) - kein Schutz gegen redirect-basiertes SSRF, dokumentierte Restlücke.
- **Migration:** keine.
- **Reimport:** bereits live gepusht (commit `27c39a6`).

## `12 – Lernvorschlag-Freigabe.json`
- **Vorher:** Browser konnte `proposal_type`/`target_type`/`target_value`/`proposed_value`/`time_horizon` frei mitschicken - Server prüfte nur, ob irgendeine `proposed`-Zeile mit der `id` existiert. Aktivierung markierte immer `activated`, unabhängig vom Ergebnis des Ziel-Updates. Kein Bounds-Check, `pipeline_config.value_numeric` konnte auf NULL gesetzt werden.
- **Nachher:** Neue Nodes laden die Proposal-Zeile serverseitig frisch per `id`; Browser-Werte werden ignoriert. Ziel-Update-Erfolg wird per RETURNING/CTE geprüft, neuer Status `activation_failed` bei 0 betroffenen Zeilen. NULL/NaN-Guard vor jedem Ziel-Update. Allowlist für `threshold_adjustment`-Config-Schlüssel.
- **Nebenwirkungen:** Ein Vorschlag, dessen Ziel inzwischen nicht mehr existiert, wird jetzt sichtbar als `activation_failed` markiert statt fälschlich als `activated` zu gelten - das ist beabsichtigt, ändert aber den bisherigen (falschen) "Erfolg"-Anschein.
- **Migration:** `sql/038` (neuer Status-Wert `activation_failed`) - **muss vor der ersten Aktivierung eines fehlschlagenden Vorschlags ausgeführt sein**, sonst schlägt die Transaktion an der CHECK-Constraint fehl (Auswirkung: Vorschlag bleibt sicher auf `proposed`, kein Datenverlust, aber Fehlermeldung).
- **Reimport:** bereits live gepusht (commit `d3996e8`, `27c39a6`).

## `00 – Tagesabschluss-Orchestrator.json`
- **Vorher:** Vier Gates prüften nur `status !== 'failed'` - ein fehlendes `status`-Feld (z.B. bei einem Absturz vor dem eigenen Abschluss-Ergebnis-Node) galt als OK. DRY_RUN fiel bei fehlender/ungültiger Config auf `false` (unsicherer Echtpfad) zurück.
- **Nachher:** Explizite Erfolgs-Allowlist `['success','partial_failure','skipped']`. DRY_RUN-Fallback auf `true` gedreht, Quelle protokolliert (`DRY_RUN_SOURCE`). `alwaysOutputData` auf dem Config-Node ergänzt.
- **Nebenwirkungen:** Ein Sub-Workflow, der bisher durch das lückenhafte Gate rutschte (z.B. durch einen Absturz), blockiert den Lauf jetzt korrekt - das kann bei bestehenden, bisher unbemerkten Fehlerzuständen zu sichtbaren Blockaden führen (beabsichtigt, deckt reale Probleme auf statt sie zu verstecken).
- **Migration:** keine.
- **Reimport:** bereits live gepusht (commit `30b00cc`).

## `06 – Empfehlungswatchlist – Agent V1.json`
- **Vorher:** DRY_RUN-Fallback bei fehlendem Config-Eintrag auf `false`.
- **Nachher:** Fallback auf `true`.
- **Nebenwirkungen:** keine für den Normalbetrieb (Config-Eintrag ist üblicherweise vorhanden).
- **Migration:** keine.
- **Reimport:** bereits live gepusht (commit `30b00cc`).

## `02b – Marktumfeld täglich.json`
- **Vorher:** OHLCV-Rohwerte unabhängig je Feld gefiltert - bei fehlendem Wert an einem Tag konnten `kerze_open/high/low/volume` und `kerze_close` aus verschiedenen Handelstagen stammen. `data_quality_status` war hartcodiert `'limited'`.
- **Nachher:** Timestamp-indizierte Kerzenbildung + Zeilenvalidierung (identisch zu `02`). Echter `data_quality_status` (valid/limited).
- **Nebenwirkungen:** Bei Datenlücken werden jetzt mehr Zeilen als zuvor komplett verworfen (vorher wurden inkonsistente Teilzeilen stillschweigend akzeptiert) - führt zu saubereren, aber ggf. selteneren Datenpunkten.
- **Migration:** keine.
- **Reimport:** bereits live gepusht (commit `6dbbbfc`).

## `02 – Technische Signale täglich.json`
- **Vorher:** Node „Kurs abrufen (lokaler FastAPI)" rief `period=3mo` ab (~63 Handelstage) statt des in `docs/DATENQUALITAET_UND_SESSIONS.md`/`OFFENE_AUFGABEN.md` dokumentierten `period=1y`. Die bereits vorhandene, längenunabhängige Kerzenbildungs-/Datenqualitätslogik (identisch zu `02b`) bekam dadurch strukturell nie genug Historie: `breakoutHistoryAusreichend` (≥252 Handelstage) war praktisch nie erreichbar außer über das `fiftyTwoWeekHigh`-Metafeld, `volatilityHistoryAusreichend` (≥60 Tage) war grenzwertig.
- **Nachher:** `period=1y` (analog `02b`). Kein Code in der Analyse selbst geändert - die bestehende Logik skaliert bereits korrekt mit der tatsächlichen Antwortlänge.
- **Nebenwirkungen:** Größere Antworten pro Ticker-Abruf (≈251-253 statt ≈63 Zeilen) - mehr Datenvolumen pro Lauf, aber gleiche Anzahl API-Aufrufe. Breakout-Signale werden jetzt tatsächlich auslösbar, wo sie zuvor faktisch permanent blockiert waren.
- **Migration:** keine.
- **Reimport:** bereits live gepusht (Backup `n8n_live_backup/02_-_Technische_Signale_täglich_PRE_C1_20260801_233634.json`).

## `14 – Portfolio-Risiko und Paper-Trading.json`
- **Vorher:** Neun kritische Lücken (siehe `FEHLERANALYSE.md` E1-E12, C9) - u.a. keine deterministische Kandidaten-Reihenfolge, Portfoliozustand nicht innerhalb eines Laufs fortgeschrieben, Sektorlimit durch fehlende Spalte wirkungslos, Drawdown bei anfänglicher Verlustserie als 0% berechnet, Einstiegskosten fehlten in `net_pnl`, `data_error` als dauerhafte Sackgasse, kein Fill+Exit-Check derselben Kerze, keine Transaktionsatomarität.
- **Nachher:** Alle neun behoben (siehe Commit `0aaf567` für Details je Punkt).
- **Nebenwirkungen:** Deutlich vorsichtigeres Verhalten (mehr Blocker greifen, `net_pnl` fällt niedriger aus als vorher berechnet) - das ist die beabsichtigte Korrektur, nicht ein Nebeneffekt. Workflow bleibt bewusst inaktiv.
- **Migration:** `sql/039` - **muss vor jedem ersten Lauf (auch manuellem Test) ausgeführt sein**, sonst schlagen mehrere neue Spalten-Referenzen fehl (`sektor`, `entry_fee_amount`, `entry_slippage_amount`, `data_error_count`, `sequence_index`, `portfolio_state_snapshot_json`, UNIQUE-Index auf `paper_trade_costs`).
- **Reimport:** bereits live gepusht (commit `0aaf567`), Workflow bleibt inaktiv.

## `03 – News Ingestion stündlich – Agent V1.json`
- **Vorher:** `beschreibung` vor dem KI-Aufruf hart auf `''` gesetzt, `type` konstant `'stock_news'`. INSERT nach `news_items` schrieb nur 6 von 10 bereits vorhandenen Spalten - `description`/`preclassified_type`/`match_reason`/`preclassified_tickers` gingen verloren. Mehrere Ticker-Treffer derselben News überschrieben sich gegenseitig (`ON CONFLICT DO NOTHING`).
- **Nachher:** `beschreibung`/`type` kommen aus der DB (über die angepasste Lesequery). INSERT schreibt alle relevanten Spalten, `ON CONFLICT DO UPDATE` führt `preclassified_tickers` bei mehreren Treffern dedupliziert zusammen.
- **Nebenwirkungen:** Die KI bewertet News jetzt mit mehr Kontext als vorher - könnte zu geringfügig anderen Relevanz-/Wirkungseinschätzungen führen als bisher (beabsichtigt, war vorher unvollständig informiert).
- **Migration:** keine (Spalten existierten bereits seit `sql/009`).
- **Reimport:** bereits live gepusht (commit `cf3b398`), Workflow aktiv (stündlich).

## `08 – News-Wirkungsanalyse.json`
- **Vorher:** `NOT EXISTS`-Prüfung pro `news_id` statt pro `(news_id, ticker)` - eine News mit mehreren Tickern, bei der einer übersprungen wird, verlor das fehlende Ticker-Paar dauerhaft.
- **Nachher:** Prüfung jetzt pro fehlendem `(news_id, ticker)`-Paar.
- **Nebenwirkungen:** Kann kurzfristig mehr News-Ticker-Paare zur Nachverfolgung finden als vorher (die zuvor verlorenen) - einmaliger Nachhol-Effekt beim ersten Lauf nach dem Fix.
- **Migration:** keine.
- **Reimport:** bereits live gepusht (commit `ee699ee`), Workflow aktiv.

## `09 – Lernagent Newswirkung.json`
- **Vorher:** Prompt behauptete "current_value ist immer 1.0" unabhängig vom echten aktiven Gewicht. Validierung übernahm `current_value`/`proposed_value` der KI ungeprüft.
- **Nachher:** Neuer Node lädt echte aktive Gewichte, jedes Finding bekommt sein reales `current_value`. Validierung nutzt ausschließlich den echten Wert, prüft `proposed_value` gegen Schrittweite (0.5) und Wertebereich (0.1-3.0).
- **Nebenwirkungen:** Vorschläge mit unplausiblen Werten (die bisher durchgingen) werden jetzt verworfen statt als Lernvorschlag gespeichert zu werden - weniger, aber verlässlichere Vorschläge in `12`.
- **Migration:** keine.
- **Reimport:** bereits live gepusht (commit `c8cc52d`), Workflow aktiv (Samstag 08:00).

## `09b – Lernagent Handelsstrategien.json`
- **Vorher:** Ein globales `oosConfirmed`-Boolean für alle Strategien - ein einziger OOS-Backtest hätte alle Strategien/Regime-Kombinationen faelschlich mit freigeschaltet. `regime_restriction`-Kandidat entstand auch für den positiven Erwartungswert-Fall mit `proposed_value:null`.
- **Nachher:** OOS-Bestätigung je Strategie (`strategy_filter`). Kandidat nur noch für den negativen Fall.
- **Nebenwirkungen:** Da `trading.backtest_runs` aktuell leer ist (Backtesting-Modul dormant), ändert sich am heutigen Verhalten nichts (weiterhin keine Vorschläge) - der Fix wird erst beim ersten echten Backtest relevant, dann aber korrekt statt fälschlich global.
- **Migration:** keine.
- **Reimport:** bereits live gepusht (commit `fb51edd`), Workflow bleibt inaktiv.

## `97 – Einmalig – Beliebige Query ausfuehren.json`
- **Vorher/Nachher:** Ad-hoc-Query-Slot, Inhalt wiederholt überschrieben (kein dauerhafter Funktionswechsel). Enthält aktuell die kombinierten Migrationen `sql/038`+`sql/039`, bereit zur manuellen Ausführung.
- **Migration:** transportiert `sql/038`+`sql/039`, siehe unten.
- **Reimport:** bereits live gepusht, **manuelle Ausführung durch den Nutzer noch ausstehend**.

---

## Neue Migrationen

### `sql/038_learning_proposal_activation_failed_status.sql`
Erweitert `trading.learning_rule_proposals.status` um den Wert `activation_failed`. Additiv (`DO $$ ... ALTER CONSTRAINT`), keine Datenänderung. Voraussetzung für `12`s korrekte Fehlerbehandlung (A6).

### `sql/039_paper_trading_workflow14_haertung.sql`
Ergänzt `paper_trades.sektor/entry_fee_amount/entry_slippage_amount/data_error_count/data_error_first_at/data_error_last_at`, neuen Status `data_error_final`, `portfolio_risk_checks.sequence_index/portfolio_state_snapshot_json`, `UNIQUE(trade_id,cost_type)` auf `paper_trade_costs`. Additiv, keine Datenänderung. Voraussetzung für Workflow `14`s Fixes E3/E4/E7/E8/E12.

**Beide Migrationen sind im aktuellen Inhalt von `97 – Einmalig – Beliebige Query ausfuehren` zusammengefasst und müssen vor jedem weiteren Test von `12` (Aktivierung mit fehlerhaftem Ziel) oder `14` (jeder Lauf) einmalig manuell ausgeführt werden.**
