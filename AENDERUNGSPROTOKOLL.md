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
- **Nachtrag A8/A7/F11 (2026-08-01):** Die Einzel-Allowlist für `threshold_adjustment`-Config-Schlüssel durch eine zentrale `RULE_TABLE` ersetzt, die alle 5 Vorschlagstypen abdeckt: `threshold_adjustment` (9 config_keys mit Min/Max/Ganzzahl-Flag), `strategy_parameter_change` (die 3 tatsächlich in `sql/036` verwendeten parameter_keys je Strategie), `regime_restriction` (feste Strategie-/combined_regime-Allowlist + `fit_multiplier` 0-1), `strategy_deactivation` (feste Strategie-Allowlist), `weight_adjustment` (Wertebereich 0.1-3.0, identisch zur bestehenden Validierung in Workflow 09). Jede Verletzung führt zu `activation_failed`. Nebenwirkung: ein Vorschlag mit einem plausibel aussehenden, aber nicht in der Regeltabelle enthaltenen Ziel (z.B. ein neuer parameter_key, der noch nicht in `sql/036` geseedet ist) wird jetzt abgelehnt statt durchgeführt - bei einer echten künftigen Erweiterung muss die `RULE_TABLE` mitgepflegt werden. Bewusst nicht umgesetzt: maximale Schrittweite gegenüber dem aktuellen Live-Wert. Migration: keine (nutzt ausschließlich bereits bestehende Spalten/Tabellen). Reimport: bereits live gepusht (Backup `n8n_live_backup/12_-_Lernvorschlag-Freigabe_PRE_A8_20260802_002338.json`).

## `00 – Tagesabschluss-Orchestrator.json`
- **Vorher:** Vier Gates prüften nur `status !== 'failed'` - ein fehlendes `status`-Feld (z.B. bei einem Absturz vor dem eigenen Abschluss-Ergebnis-Node) galt als OK. DRY_RUN fiel bei fehlender/ungültiger Config auf `false` (unsicherer Echtpfad) zurück.
- **Nachher:** Explizite Erfolgs-Allowlist `['success','partial_failure','skipped']`. DRY_RUN-Fallback auf `true` gedreht, Quelle protokolliert (`DRY_RUN_SOURCE`). `alwaysOutputData` auf dem Config-Node ergänzt.
- **Nebenwirkungen:** Ein Sub-Workflow, der bisher durch das lückenhafte Gate rutschte (z.B. durch einen Absturz), blockiert den Lauf jetzt korrekt - das kann bei bestehenden, bisher unbemerkten Fehlerzuständen zu sichtbaren Blockaden führen (beabsichtigt, deckt reale Probleme auf statt sie zu verstecken).
- **Migration:** keine.
- **Reimport:** bereits live gepusht (commit `30b00cc`).
- **Nachtrag B2 (2026-08-01):** Drei neue Nodes zwischen „IF: Versand ok?" und „Lauf abschliessen (Erfolg)": „Sammle Teilstatus (Erfolg)" (sammelt die vier Stufenstatus), „IF: Teilausfall trotz Erfolg?", „Baue Teilausfall-Warnung" (nutzt den bestehenden Matrix-Versandpfad mit). „Lauf abschliessen (Warnung/Fehler)" und „Log Gesamtlauf abgeschlossen (SQL bauen)" erweitert, damit die Teilausfall-Details trotz des dazwischenliegenden Matrix-HTTP-Calls in `trading.pipeline_runs.metadata_json` landen. `status`-Spalte bleibt beim bereits vorhandenen `'warning'` (CHECK-Constraint in sql/001 erlaubt keinen neuen Wert ohne Migration). Vorher: ein partial_failure/skipped einer Stufe wurde nach Passieren der B1-Gates komplett stillschweigend wie voller Erfolg behandelt. Nebenwirkung: bei Teilausfall geht jetzt zusätzlich eine Matrix-Meldung raus (vorher nur bei hartem Abbruch) - beabsichtigt, das war der Kern des Funds. Migration: keine. Reimport: bereits live gepusht (Backup `n8n_live_backup/00_-_Tagesabschluss-Orchestrator_PRE_B2_20260802_000651.json`).

## `06 – Empfehlungswatchlist – Agent V1.json`
- **Vorher:** DRY_RUN-Fallback bei fehlendem Config-Eintrag auf `false`.
- **Nachher:** Fallback auf `true`.
- **Nebenwirkungen:** keine für den Normalbetrieb (Config-Eintrag ist üblicherweise vorhanden).
- **Migration:** keine.
- **Reimport:** bereits live gepusht (commit `30b00cc`).
- **Nachtrag B8 (2026-08-02):** Node „DB: Trend-Signale laden (Empf.)": Query um `AND valid_to IS NULL` ergänzt - notwendiger Begleitfix zur Point-in-Time-Revisionierung von `technical_signals_history` (siehe `02`), sonst nach der Migration potenziell mehrere Zeilen je (ticker,snapshot_date). Migration: keine (nur Leseabfrage geändert). Reimport: bereits live gepusht (Backup `n8n_live_backup/06_-_Empfehlungswatchlist_-_Agent_V1_PRE_B8_VALID_TO_20260802_004526.json`).

## `07 – Status-Uebersicht – Agent V1.json` / `10 – Report- und Prüfagent.json` / `13 – Markt-Screener täglich.json`
- **Nachtrag B8 (2026-08-02):** Gleicher Begleitfix wie oben bei `06` - jeweils Node „DB: Trend-Signale laden"/„DB: Technische Signale heute laden (Scanner)" um `AND valid_to IS NULL` ergänzt. `07` ist besonders relevant, da als jederzeit abrufbarer Webhook ohne die Migration sofort fehlgeschlagen wäre. Migration: keine (nur Leseabfragen geändert). Reimport: bereits live gepusht (Backups `n8n_live_backup/07_-_Status-Uebersicht_-_Agent_V1_PRE_B8_VALID_TO_20260802_004528.json`, `10_-_Report-_und_Prüfagent_PRE_B8_VALID_TO_20260802_004530.json`, `13_-_Markt-Screener_täglich_PRE_B8_VALID_TO_20260802_004532.json`).

## `02b – Marktumfeld täglich.json`
- **Vorher:** OHLCV-Rohwerte unabhängig je Feld gefiltert - bei fehlendem Wert an einem Tag konnten `kerze_open/high/low/volume` und `kerze_close` aus verschiedenen Handelstagen stammen. `data_quality_status` war hartcodiert `'limited'`.
- **Nachher:** Timestamp-indizierte Kerzenbildung + Zeilenvalidierung (identisch zu `02`). Echter `data_quality_status` (valid/limited).
- **Nebenwirkungen:** Bei Datenlücken werden jetzt mehr Zeilen als zuvor komplett verworfen (vorher wurden inkonsistente Teilzeilen stillschweigend akzeptiert) - führt zu saubereren, aber ggf. selteneren Datenpunkten.
- **Migration:** keine.
- **Reimport:** bereits live gepusht (commit `6dbbbfc`).
- **Nachtrag C7/C8 (2026-08-01):** Node „Marktregime berechnen": `sessionStatusFor` kannte bisher nur 3 Zustände (holiday/closed_complete/open_intraday) und erklärte eine Sitzung nach Ablauf der Schlusszeit pauschal für abgeschlossen, selbst ohne eine tatsächlich vorliegende heutige Kerze. Jetzt 5 Zustände inkl. `stale`, abgeleitet aus den bereits im selben Lauf vorliegenden Kerzenzeitstempeln (keine neue DB-Abfrage, keine neuen Referenzdaten). `session_status` beeinflusst jetzt `combined_regime` (→ `vorlaeufig` bei laufender Sitzung), vorher folgenlos gespeichert. Nebenwirkung: Empfehlungen für Ticker der betroffenen Region werden während einer laufenden US-Sitzung jetzt über `06`s bestehenden Matrix-Fallback automatisch konservativer bewertet (`unknown`-Zeile) statt mit einem u.U. auf unvollständigen Tagesdaten basierenden, aber als „sicher" ausgewiesenen Regime. Migration: keine. Reimport: bereits live gepusht (Backup `n8n_live_backup/02b_-_Marktumfeld_täglich_PRE_C8_20260801_235839.json`).

## `02 – Technische Signale täglich.json`
- **Vorher:** Node „Kurs abrufen (lokaler FastAPI)" rief `period=3mo` ab (~63 Handelstage) statt des in `docs/DATENQUALITAET_UND_SESSIONS.md`/`OFFENE_AUFGABEN.md` dokumentierten `period=1y`. Die bereits vorhandene, längenunabhängige Kerzenbildungs-/Datenqualitätslogik (identisch zu `02b`) bekam dadurch strukturell nie genug Historie: `breakoutHistoryAusreichend` (≥252 Handelstage) war praktisch nie erreichbar außer über das `fiftyTwoWeekHigh`-Metafeld, `volatilityHistoryAusreichend` (≥60 Tage) war grenzwertig. Zusätzlich kollabierte Node „Kurshistorie: SQL bauen" den 5-Zustands-Serienstatus (`valid/limited/invalid/stale/session_incomplete`) beim Schreiben nach `stock_price_history` auf nur `valid`/`invalid` - Konsumenten wie `14` verloren dadurch die Information, aus einer laufenden Sitzung oder veralteten Daten zu stammen.
- **Nachher:** `period=1y` (analog `02b`, C1). `qualityStatus = j.data_quality_status || 'limited'` statt der Kollaps-Formel (analog `02b`, C6) - alle fünf Zustände werden jetzt unverändert durchgereicht. Kein Code in der Analyse selbst geändert - die bestehende Logik skaliert bereits korrekt mit der tatsächlichen Antwortlänge/dem tatsächlichen Status.
- **Nebenwirkungen:** Größere Antworten pro Ticker-Abruf (≈251-253 statt ≈63 Zeilen). Breakout-Signale werden jetzt tatsächlich auslösbar, wo sie zuvor faktisch permanent blockiert waren. **Macht den bereits deployten C9-Fix in Workflow `14` scharf** - `14` kann jetzt tatsächlich `session_incomplete` aus `stock_price_history` lesen und Fill/Exit-Entscheidungen entsprechend überspringen.
- **Migration:** `sql/040` (reine `COMMENT ON COLUMN`-Korrektur, keine Schema-Änderung - die Spalte war schon immer TEXT ohne CHECK-Constraint) - **ausgeführt** (kombiniert mit `sql/041`, Execution 24143, 2026-08-01T22:45:57Z).
- **Reimport:** bereits live gepusht (Backups `n8n_live_backup/02_-_Technische_Signale_täglich_PRE_C1_20260801_233634.json`, `..._PRE_C6_20260801_234054.json`).
- **Nachtrag C2/B8 (2026-08-02):** Node „Technische Analyse (RSI/MACD/BB)": neues Feld `historie52wZuverlaessig` (= `breakoutHistoryAusreichend`) macht sichtbar, wenn `hoch52w`/`tief52w` nur aus einer unzureichenden Ersatz-Historie stammen (Wert selbst bleibt erhalten). Node „Signal-Historie: SQL bauen": Point-in-Time-Revisionierung wie `fundamentals_history`/`stock_price_history` (UPDATE valid_to + INSERT neue Revision statt `ON CONFLICT DO UPDATE`) - ein zweiter Tageslauf überschreibt die erste Revision nicht mehr. Migration `sql/041` legt `known_at`/`valid_from`/`valid_to`/`revision_number` an. **Ausgeführt** (kombiniert mit `sql/040`, Execution 24143). Nebenwirkung: `06`/`07`/`10`/`13` mussten im selben Zug um `AND valid_to IS NULL` ergänzt werden (siehe dort), sonst hätten sie nach der Migration potenziell mehrere Zeilen je Tag zurückbekommen. Reimport: bereits live gepusht (Backup `n8n_live_backup/02_-_Technische_Signale_täglich_PRE_C2_B8_20260802_004444.json`).

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
- **Nachtrag D1/D2/D6 (2026-08-01):** Hartkodierte 15-Ticker-Liste im System-Prompt von „KI: Nachricht bewerten" durch Laufzeit-Abfrage ersetzt (neuer Node „DB: Watchlist fuer KI-Prompt laden", Prompt als Expression). Von der KI gemeldete `betroffene_ticker` werden jetzt gegen die geladene Watchlist gefiltert (`betroffene_ticker_verworfen` für Ausreißer). KI-Prompt um `relevanz_konfidenz`/`wahrscheinlichkeit_positiv`/`_negativ`/`_neutral`/`staerke_konfidenz`/`datenqualitaet_score` erweitert, die auf die seit `sql/011` bestehenden, bis dahin nie befüllten Spalten `relevance_confidence`/`probability_*`/`strength_confidence`/`data_quality_score` gemappt werden - mit Plausibilitätsprüfung (Zahlen-Check, Wahrscheinlichkeitssumme ≈1) vor dem Schreiben, sonst `NULL` statt erfundener Werte. Nebenwirkung: die KI erhält jetzt eine dynamische statt statischen Watchlist-Zeile im Prompt - bei einer Watchlist-Änderung wirkt sich das ab dem nächsten Lauf sofort aus, ohne Workflow-Edit. Migration: keine (Zielspalten existierten bereits seit `sql/011`). Reimport: bereits live gepusht (Backup `n8n_live_backup/03_-_News_Ingestion_stündlich_-_Agent_V1_PRE_D1_D2_D6_20260801_235032.json`).
- **Nachtrag D9 (2026-08-01):** „News: news_key erzeugen": URL wird vor dem `news_key`-Bau kanonisiert (Tracking-Parameter/Trailing-Slash/Fragment entfernt, Protokoll+Host lowercased), zusätzlich `content_hash` (djb2 über Titel+Beschreibung) berechnet. „News: Duplikat-Check" prüft jetzt zusätzlich gegen bekannte/laufinterne `content_hash`-Werte als dritte Dedup-Schicht. „Neue News speichern (SQL bauen)" persistiert `content_hash` (Spalte seit `sql/009` ungenutzt). „DB: Bekannte News laden (35 Tage)" liest `content_hash` mit. Nebenwirkung: der gespeicherte `url`-Wert bleibt der Original-Link (nur `news_key` nutzt die kanonisierte Form) - keine rückwirkende Bereinigung bereits gespeicherter Zeilen. Migration: keine (Spalte existiert bereits). Reimport: bereits live gepusht (Backup `n8n_live_backup/03_-_News_Ingestion_stündlich_-_Agent_V1_PRE_D9_20260802_001808.json`).
- **Nachtrag D10 (2026-08-02):** „News: Duplikat-Check" verwirft Duplikate nicht mehr, sondern gibt sie mit `_isDuplicate:true` + Match-Schlüssel aus. Der bisher tote false-Zweig von „IF: News neu?" ist jetzt live verdrahtet (3 neue Nodes) und aktualisiert `last_seen_at` bei exaktem Key/Link- oder `content_hash`-Match. Jaccard-Titel-Treffer bewusst ausgenommen (kein eindeutiger Schlüssel). Migration: keine (Spalte existiert seit `sql/009`). Reimport: bereits live gepusht (Backup `n8n_live_backup/03_-_News_Ingestion_stündlich_-_Agent_V1_PRE_D10_20260802_005627.json`).

## `03a – News-Recherche-Agent.json`
- **Vorher:** `Number(parsed.konfidenz) || 0` verwechselte eine fehlende Konfidenzangabe der KI mit einer echten 0. Fehlerpfad in „Recherche-Ergebnis persistieren (SQL bauen)" schrieb `last_error`/`last_attempt_at` (fuer 03s Ingestion-Retry gedacht) statt der eigens dafuer angelegten Spalten `research_status`/`research_attempts`/`next_research_at` (`sql/010`) - ein dauerhaft nicht parsebarer Kandidat wurde alle zwei Stunden unbegrenzt erneut versucht.
- **Nachher:** Konfidenz `Number.isFinite`-geprüft (fehlend → `NULL`, nicht `0`). Erfolgsfall setzt `research_status='success'`. Fehlerfall erhöht `research_attempts`, eskalierender Backoff (`Versuche × 4 Stunden`), ab 5 Versuchen `research_status='max_attempts_reached'` (kein weiterer Versuch). „DB: Zweitpass-Kandidaten laden" respektiert Backoff/Cap in der WHERE-Klausel.
- **Nebenwirkungen:** Ein Kandidat, der bereits mehrfach erfolglos versucht wurde, wird jetzt seltener/gar nicht mehr erneut versucht - beabsichtigt, war vorher eine unbegrenzte Dauerschleife.
- **Migration:** keine (Spalten existierten bereits seit `sql/010`, waren nie befüllt).
- **Reimport:** bereits live gepusht (Backup `n8n_live_backup/03a_-_News-Recherche-Agent_PRE_D7_D8_20260802_005140.json`).

## `08 – News-Wirkungsanalyse.json`
- **Vorher:** `NOT EXISTS`-Prüfung pro `news_id` statt pro `(news_id, ticker)` - eine News mit mehreren Tickern, bei der einer übersprungen wird, verlor das fehlende Ticker-Paar dauerhaft.
- **Nachher:** Prüfung jetzt pro fehlendem `(news_id, ticker)`-Paar.
- **Nebenwirkungen:** Kann kurzfristig mehr News-Ticker-Paare zur Nachverfolgung finden als vorher (die zuvor verlorenen) - einmaliger Nachhol-Effekt beim ersten Lauf nach dem Fix.
- **Migration:** keine.
- **Reimport:** bereits live gepusht (commit `ee699ee`), Workflow aktiv.
- **Nachtrag D11/D12 (2026-08-01):** Node „D+1..D+20 berechnen + Stoerfaktoren": Benchmark-Punkt je Horizont wird jetzt über das tatsächliche Kalenderdatum gesucht (`benchmarkByDatum[point.datum]`) statt über einen parallelen Array-Index (`bverlauf[bBaselineIdx+h]`) - bei einer einzelnen fehlenden Zeile in einem der beiden Kursverläufe drifteten beide Reihen vorher dauerhaft gegeneinander. Node „Baseline-Fall je (News,Ticker) bestimmen": Sitzungszeiten/-zone jetzt je Ticker aus `stock_instruments`/`market_reference` aufgelöst statt pauschal Europe/Berlin+09:00/17:30 (Query von „DB: Instrumente (Benchmark-Zuordnung)" entsprechend erweitert, LEFT JOIN). Nebenwirkung: `abnormal_return_dH`-Werte für bereits bestehende `waiting_*`-Tracking-Zeilen mit einer betroffenen Datenlücke ändern sich beim nächsten Lauf (waren vorher gegen den falschen Tag berechnet) - beabsichtigte Korrektur. Migration: keine. Reimport: bereits live gepusht (Backup `n8n_live_backup/08_-_News-Wirkungsanalyse_PRE_D11_D12_20260802_001205.json`).

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

## `97 – Einmalig – Beliebige Query ausfuehren.json` (Query-Text mehrfach überschrieben, Ausführung durch Nutzer)
- **Vorher/Nachher:** Ad-hoc-Query-Slot, Inhalt wiederholt überschrieben (kein dauerhafter Funktionswechsel). Transportierte `sql/038`+`sql/039` kombiniert - **vom Nutzer am 2026-08-01T21:24:02Z erfolgreich ausgeführt** (Execution 24086, `{"success": true}`). Enthält aktuell `sql/040`, bereit zur manuellen Ausführung.
- **Migration:** transportierte `sql/038`+`sql/039` (ausgeführt), transportiert jetzt `sql/040` (ausstehend).
- **Reimport:** bereits live gepusht, **manuelle Ausführung von `sql/040` durch den Nutzer noch ausstehend**.

---

## Neue Migrationen

### `sql/038_learning_proposal_activation_failed_status.sql`
Erweitert `trading.learning_rule_proposals.status` um den Wert `activation_failed`. Additiv (`DO $$ ... ALTER CONSTRAINT`), keine Datenänderung. Voraussetzung für `12`s korrekte Fehlerbehandlung (A6).

### `sql/039_paper_trading_workflow14_haertung.sql`
Ergänzt `paper_trades.sektor/entry_fee_amount/entry_slippage_amount/data_error_count/data_error_first_at/data_error_last_at`, neuen Status `data_error_final`, `portfolio_risk_checks.sequence_index/portfolio_state_snapshot_json`, `UNIQUE(trade_id,cost_type)` auf `paper_trade_costs`. Additiv, keine Datenänderung. Voraussetzung für Workflow `14`s Fixes E3/E4/E7/E8/E12.

**Beide Migrationen sind im aktuellen Inhalt von `97 – Einmalig – Beliebige Query ausfuehren` zusammengefasst und müssen vor jedem weiteren Test von `12` (Aktivierung mit fehlerhaftem Ziel) oder `14` (jeder Lauf) einmalig manuell ausgeführt werden.**
