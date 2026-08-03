# Konzept: Historische Daten, Walk-Forward-Simulation und Web-Steuerzentrale

Stand: 2026-08-03. Phase 1 des Auftrags "Historische Daten, Walk-forward-Simulation und
Web-Steuerzentrale". Diese Analyse wurde gegen den tatsächlichen, aktuellen Code-/Schema-Stand
erstellt (nicht gegen Annahmen) — siehe Abschnitt 1 für die vollständige Bestandsaufnahme.

## 1. Ist-Zustand-Analyse

### 1.1 Datenbank

Alle 55 vorhandenen Migrationen (`sql/001` bis `sql/056`, Lücke bei `047` — nie vergeben, nicht
gelöscht) wurden gesichtet. Höchste vorhandene Nummer: **056**. Die neue Migration dieser
Sitzung erhält die Nummer **057**.

**Bereits vorhandenes, für dieses Vorhaben zentrales Schema:**

- `trading.backtest_runs` (`sql/037`) — **existiert bereits fast genau das, was der Auftrag als
  `simulation_runs` vorschlägt**: `backtest_id` (UNIQUE), `run_type` mit CHECK-Werten, die
  bereits `'walk_forward'` und `'out_of_sample'` enthalten, `train/validation/test_window_*`,
  `configuration_version`/`rule_version`/`data_schema_version`, `status`, `results_json`,
  `started_at`/`finished_at`. **Bewusst dormant** (0 Zeilen) — kein Workflow hat je
  hineingeschrieben.
- `trading.backtest_trades` (`sql/037`) — ein Trade-Ergebnis pro Zeile
  (`backtest_id`/`ticker`/`entry_date`/`exit_date`/`entry_price`/`exit_price`/`net_pnl`/
  `realized_r_multiple`/`exit_reason`/`known_at_entry_json`). Bewusst **grob** — ein
  Zusammenfassungs-Trade, keine Order-/Slippage-/Kosten-/Positions-Granularität.
- `trading.probability_estimates` + `trading.calibration_checks` (`sql/037`) — vollständiges
  Kalibrierungs-Schema, ebenfalls dormant.
- `trading.paper_trades` + `paper_trade_events` + `paper_trade_costs` + `paper_trade_valuations`
  (`sql/035`) — das reichhaltigste vorhandene Trade-Lebenszyklus-Schema im Projekt (Status-
  maschine `proposed→...→closed`, Einstiegszone, Stop/Ziel, Kosten je Typ, MFE/MAE,
  Versionsfelder). Live, aktiv genutzt vom echten Paper-Trading-System (`14`).
- `trading.stock_price_history` (`sql/004`, PIT seit `sql/025`) — vollständige OHLCV +
  `adjusted_close`, Point-in-Time-revisioniert (`valid_from`/`valid_to`/`revision_number`),
  aber **live**, gelesen von der gesamten aktuellen Entscheidungs-Pipeline
  (`02`/`06`/`07`/`08`/`10`/`13`/`14`) über `WHERE valid_to IS NULL`.
- `trading.fundamentals_history`/`technical_signals_history` — ebenfalls PIT-revisioniert, aber
  nur für die ~15 aktuellen Watchlist-Ticker über die ~2 Wochen seit System-Start — **zu
  schmal und zu kurz für eine mehrjährige Simulation**, nicht wiederverwendbar als Datenbasis.
  `market_regime`/`market_context_history` sind **nicht** PIT-revisioniert (`ON CONFLICT DO
  UPDATE`, überschreiben den Vortageswert).
- `trading.news_items`/`news_assessments` — live, `UNIQUE(news_key)` global, für die laufende
  stündliche Ingestion ausgelegt, nicht für einen Bulk-Import beliebiger historischer Zeiträume.
- `trading.recommendations` — live, `ux_recommendations_one_open_per_ticker` (WHERE
  `status='offen'`) ist ein **globaler** Constraint über das gesamte reale Buch.
- `trading.pipeline_config` — 31 bestehende Konfigurationswerte (Kommissionen/Slippage/
  Risikolimits/Mindestfallzahlen usw., vollständige Liste siehe Abschnitt 3.4), die von der
  neuen Simulation wiederverwendet statt dupliziert werden.
- `docs/BACKTESTING_UND_WALK_FORWARD.md` beschreibt bereits explizit das exakte
  Look-ahead-Bias-Konzept (`known_at_entry_json` als Nachweis), das dieser Auftrag verlangt —
  **die Grundidee existiert bereits als Spezifikation, nur ohne Ausführungs-Workflow.**

**Kein lokaler FastAPI-Code im Repo.** Der Kursdienst (`http://172.16.1.14:8099`) ist ein rein
externes HTTP-Ziel (`/chart/{ticker}?period=1y&interval=1d`, `/fundamentals/{ticker}`), aktuell
mit `period=1y` konfiguriert. **Offen (siehe Abschnitt 8):** ob dieser Dienst auch mehrjährige
Zeiträume/ein festes Start-/Enddatum liefern kann, ist nicht bekannt und muss vor dem
Produktivbetrieb von Workflow 15 per echtem Testaufruf verifiziert werden.

**Kein Job-/Worker-Pattern existiert bereits.** `SplitInBatches` wird nur in den News-Workflows
(`03`/`03a`/`04`) für Batch-Verarbeitung *innerhalb eines einzelnen synchronen Laufs* verwendet,
nicht für einen über mehrere Webhook-Aufrufe hinweg fortsetzbaren Hintergrundjob. `13`/`14`
verarbeiten ihre Kandidaten/Ticker-Listen vollständig innerhalb einzelner Code-Nodes (JS-Loops).
Ein echtes „Job in DB anlegen → Worker holt sich Pakete → Fortschritt speichern"-Muster (wie vom
Auftrag gefordert) existiert im Projekt noch nicht — das ist die zentrale neue
Architekturkomponente dieses Vorhabens.

**Kein zentraler Zeitkontext.** `getBusinessDate()` wird aktuell in jedem Code-Node, der es
braucht, lokal neu definiert (Copy-Paste), nicht über ein gemeinsames Kontextobjekt
weitergereicht. Der vom Auftrag geforderte Simulationskontext (`as_of_date`/`data_cutoff_at`/
Versionsfelder) existiert in dieser Form noch nicht.

### 1.2 Web-UI-Baumuster

Alle vier bestehenden Webhook-Verwaltungsseiten (`RSS-Quellen verwalten`,
`Watchlist verwalten`, `12 – Lernvorschlag-Freigabe`, `07 – Status-Uebersicht`) folgen demselben
Muster:

- **Zwei Webhook-Nodes pro Seite**, `GET` und `POST` auf demselben `path` (kein separater
  Router-Node auf HTTP-Ebene).
- **Ein einziger Code-Node `Baue HTML`** baut die komplette Seite als HTML-String.
- **Mehrere Aktionen (add/edit/delete/toggle) laufen in einem einzigen JS-Code-Node**
  (`POST: Formular normalisieren + SQL bauen`) über eine `if (action === '...')`-Kette mit
  einer festen `ALLOWED_ACTIONS`-Whitelist, nicht über n8n-IF-Nodes.
- Erst danach folgt **ein** generischer `POST: SQL ausfuehren`-Node.

Dieses Muster wird für die neue Steuerzentrale übernommen (Abschnitt 6) — es ist bereits
etabliert, getestet und passt zum Sicherheitsmodell (keine SQL-Fragmente aus Formularen, feste
Aktions-Whitelist).

## 2. Wiederverwendbare Komponenten

| Komponente | Wiederverwendung |
|---|---|
| `trading.backtest_runs` | Wird zur zentralen `simulation_runs`-Tabelle **erweitert** (nicht dupliziert) — siehe Abschnitt 3.1. |
| `trading.pipeline_config` | Alle bestehenden Kommissions-/Slippage-/Risiko-/Mindestfallzahl-Werte werden von der Simulation als Konfigurations-Default gelesen, nicht neu erfunden. |
| Web-UI-Baumuster (2 Webhook-Nodes + 1 `Baue HTML`-Node + Aktions-Whitelist-Code-Node) | Für alle 8 Steuerzentrale-Bereiche identisch angewendet. |
| `trading.probability_estimates`/`calibration_checks` | Für den Kalibrierungs-Simulationsart-Zweig wiederverwendet, FK auf `backtest_runs.id` erweitert. |
| `getBusinessDate()`-Musterfunktion | Als Vorlage für die neue zeitkontext-bewusste Variante (Abschnitt 5) — Prinzip bleibt (lokal pro Node definierte, reine Funktion), aber sie akzeptiert jetzt zwingend den Simulationskontext statt `new Date()`. |
| `tools/validate-workflows.js` | Wird um simulationsspezifische Prüfungen erweitert (Abschnitt 8/`tools/validate-historical-simulation.js`), nicht ersetzt. |
| `trading.schema_migrations`-Konvention (seit `sql/044`) | Migration `057` trägt sich selbst ein. |

## 3. Notwendige Änderungen — Datenmodell

### 3.1 `trading.backtest_runs` → erweitert zur zentralen Simulationssteuerung

**Entscheidung (siehe Abschnitt 8.1):** `backtest_runs` wird per `ALTER TABLE` um alle vom
Auftrag geforderten Job-Steuerungs-/Fortschritts-/Konfigurations-Felder erweitert, statt eine
parallele `simulation_runs`-Tabelle anzulegen, die inhaltlich fast identisch wäre. Name bleibt
`backtest_runs` (0 Zeilen live, keine Umbenennung nötig, spart eine Doku-weite Umbenennung in
`docs/BACKTESTING_UND_WALK_FORWARD.md`/`docs/WAHRSCHEINLICHKEITSKALIBRIERUNG.md`). Die Spalte
`backtest_id` übernimmt die Rolle der vom Auftrag geforderten `simulation_id`.

Neue Spalten (Auszug, vollständig in `sql/057`): `name`, `description`, `status` (CHECK erweitert
um `draft`/`queued`/`pausing`/`paused`/`cancelled`/`completed_with_warnings`/`archived`),
`start_date`/`end_date`/`current_simulation_date`, `data_cutoff_time`, `timezone` (Default
`'Europe/Berlin'`), `instrument_selection_json`, `benchmark_selection_json`, `news_enabled`/
`fundamentals_enabled`/`portfolio_enabled`/`learning_enabled` (bool), `initial_capital`,
`currency`, `commission_model_json`/`slippage_model_json`, `model_version`, `dataset_version`,
`paused_at`/`cancelled_at`, `progress_total`/`progress_completed`/`progress_percent`,
`warning_count`/`error_count`/`last_error`/`last_heartbeat`, `created_by`, `version` (Optimistic
Locking), `config_snapshot_json` (unveränderlicher Konfigurations-Snapshot, siehe
„Speicherung von Konfigurationsständen" im Auftrag).

### 3.2 Genuinely neue Tabellen (kein bestehendes Analog)

**Marktdaten/Nachrichten-Archiv (strukturell getrennt von den Live-Tabellen — Pflicht laut
Auftrag „keine unkontrollierte Vermischung"):**

- `trading.historical_price_data` — OHLCV + `adjusted_close` + `provider`/`source` +
  `import_job_id`, beliebiger Zeitraum, `UNIQUE(ticker, trading_date, provider)`. **Bewusst
  nicht** in `stock_price_history` integriert (auch nicht über ein Diskriminator-Feld) — die
  gesamte Live-Pipeline liest `stock_price_history` über `WHERE valid_to IS NULL` ohne
  zusätzlichen Kategorie-Filter; jede Vermischung wäre ein einziger vergessener WHERE-Zusatz
  von einer echten Live-Datenkorruption entfernt.
- `trading.historical_corporate_actions` — `ticker`, `action_type`
  (`split`/`dividend`), `ex_date`, `split_ratio` bzw. `dividend_amount`, `currency`, `source`.
- `trading.historical_news` — analog zu `news_items`, aber eigener Schlüsselraum
  (`UNIQUE(news_key, provider)` statt global `news_key`), zusätzlich `import_job_id`,
  `linked_tickers_json`. Bestehende `03a`-Recherche-/Bewertungslogik wird **kontrolliert
  wiederverwendet** (Abschnitt 4.2), nicht dupliziert.
- `trading.historical_fundamentals` (**Workflow 18, optional, deferred** — siehe Abschnitt 4.4)
  — `reporting_period`, `publication_date`, `filing_date`, `available_from`, `source`,
  `revision`.

**Job-/Import-Steuerung (komplett neu, kein Analog):**

- `trading.import_jobs` — `job_id` (UNIQUE), `job_type` (`market_data`/`news`), `status`
  (`draft`/`queued`/`running`/`pausing`/`paused`/`completed`/`completed_with_warnings`/
  `failed`/`cancelled`), Parameter-Snapshot (`provider`, `instrument_selection_json`,
  `date_range`, `dry_run`, `overwrite_mode`), Fortschritt (`progress_total`/
  `progress_completed`), `heartbeat_at`, `created_at`/`started_at`/`finished_at`.
- `trading.import_job_items` — ein Paket je (`job_id`, `sequence_number`): `instrument`/
  `period_from`/`period_to`, `status`, `attempt`, `started_at`/`finished_at`/`heartbeat_at`,
  `checkpoint_json`, `error`. Idempotenz über `UNIQUE(job_id, sequence_number)`.

**Simulations-Ausführung (reicher als `backtest_trades`, weil der Auftrag Order-/
Positions-/Tagesdepot-Granularität verlangt — bewusst getrennt von `paper_trades`, siehe
Abschnitt 8.2):**

- `trading.simulation_run_steps` — ein Paket je (`simulation_run_id`, `sequence_number`):
  `simulated_date`, `status`, `attempt`, `started_at`/`finished_at`/`heartbeat_at`,
  `checkpoint_json`, `error`. Ermöglicht Fortsetzen nach Serverneustart (Pflicht laut Auftrag).
- `trading.simulation_recommendations` — Spiegel von `recommendations`, aber
  `simulation_run_id`-gebunden, ohne den globalen `ux_recommendations_one_open_per_ticker`-
  Constraint (der ist live-buchweit gemeint, nicht je Simulationslauf sinnvoll — stattdessen
  `UNIQUE(simulation_run_id, ticker) WHERE status='offen'`).
- `trading.simulation_orders` — exakt die vom Auftrag genannten Felder: `signal_date`,
  `order_created_at`, `intended_execution_date`, `actual_execution_date`, `order_type`,
  `limit_price`, `raw_market_price`, `slippage`, `commission`, `executed_price`, `quantity`,
  `execution_status`.
- `trading.simulation_trades` — mirrort `paper_trades`' reiche Statusmaschine/Kosten-/
  MFE-MAE-Struktur eins zu eins (gleiches Feldset, siehe `sql/057`), zusätzlich
  `simulation_run_id` (FK), `as_of_date`. Getrennte Tabelle statt Diskriminator-Spalte auf
  `paper_trades` selbst — Begründung Abschnitt 8.2.
- `trading.simulation_positions` — Tagesposition je (`simulation_run_id`, `ticker`,
  `simulated_date`): Menge, Einstandskurs (Corporate-Action-adjustiert), unrealisiertes P&L.
- `trading.simulation_daily_portfolio` — Tages-Equity-Kurve: `simulation_run_id`,
  `simulated_date`, `cash`, `positions_value`, `total_equity`, `benchmark_value`,
  `drawdown_pct`, `open_positions_count`.
- `trading.simulation_metrics` — aggregierte, **abfragbare** Kennzahlen je Lauf (Rendite,
  Sharpe, Max-Drawdown, Trefferquote usw. als eigene typisierte Spalten, nicht nur als JSONB in
  `backtest_runs.results_json`) — Pflicht für den Vergleichs-Bereich (Abschnitt 6.5), da ein
  SQL-`ORDER BY`/Filter über ein JSONB-Blob unnötig fragil wäre.
- `trading.simulation_errors` — strukturierter Fehlerlog je Job-/Simulationsschritt (analog
  `workflow_errors`, aber mit `simulation_run_id`/`step_id`-Bezug statt Workflow-Name).
- `trading.simulation_events` — Audit-Trail (Start/Pause/Resume/Cancel/Retry/Umklassifizierung),
  Pflicht laut Auftrag für die Out-of-sample→Training-Umklassifizierungs-Regel.

### 3.3 Wiederverwendet ohne Änderung

`trading.probability_estimates`/`calibration_checks` (FK bereits auf `backtest_runs.id`
vorbereitet, keine Änderung nötig), `trading.pipeline_config` (nur gelesen, keine neuen
Simulations-Config-Keys dupliziert bereits vorhandene Werte).

### 3.4 Bestehende `pipeline_config`-Werte, die die Simulation übernimmt

`MODEL_PORTFOLIO_VALUE`, `MAX_RISK_PER_TRADE_PCT`, `MAX_TOTAL_OPEN_RISK_PCT`,
`MAX_SECTOR_EXPOSURE_PCT`, `MAX_SINGLE_POSITION_PCT`, `MAX_OPEN_POSITIONS`,
`MAX_DIRECTIONAL_EXPOSURE_PCT`, `MAX_PORTFOLIO_DRAWDOWN_PCT`, `CORRELATION_LOOKBACK_DAYS`,
`MAX_PAIRWISE_CORRELATION`, `STRESS_RISK_REDUCTION_FACTOR`, `MAX_REGION_EXPOSURE_PCT`,
`MAX_NON_EUR_EXPOSURE_PCT`, `AMBIGUOUS_BAR_POLICY_CODE`, `BACKTEST_MIN_WINDOW_DAYS`,
`PROBABILITY_MIN_SAMPLE_SIZE`, `LEARNING_MIN_TRADE_SAMPLE_SIZE`. Neue simulationsspezifische
Keys (`SIMULATION_DEFAULT_PACKAGE_SIZE`, `SIMULATION_HEARTBEAT_TIMEOUT_MIN`,
`SIMULATION_MAX_PARALLEL_RUNS` u. ä.) werden additiv in `sql/057` gesät.

## 4. Workflow-Struktur

### 4.1 Workflow 15 — Historische Marktdaten importieren

Neuer, eigenständiger Workflow (analog `RSS-Quellen verwalten`s Aufbau, aber mit Job-Tabelle
statt Direktverarbeitung): `Webhook POST /simulation/api/imports` legt eine Zeile in
`import_jobs` + eine Zeile je Instrument/Zeitfenster in `import_job_items` an und antwortet
sofort mit der `job_id` (kein synchrones Warten auf den vollständigen Import). Ein **separater,
per Schedule oder Execute-Workflow-Trigger laufender Worker-Zweig** holt sich pro Lauf ein
kleines Paket offener `import_job_items` (`SplitInBatches`, Paketgröße aus `pipeline_config`),
ruft den Kursdienst auf, schreibt nach `historical_price_data`/`historical_corporate_actions`,
aktualisiert `checkpoint_json`/`heartbeat_at`. Duplikatschutz über
`UNIQUE(ticker, trading_date, provider)` + `INSERT ... ON CONFLICT DO NOTHING`/`DO UPDATE`
gesteuert vom `overwrite_mode`-Parameter. Anbieterlimits über `pipeline_config`
(`SIMULATION_MAX_PARALLEL_RUNS` u. ä.) statt hartkodiert.

### 4.2 Workflow 16 — Historische Nachrichten importieren (GDELT, siehe Abschnitt 8.4)

Gleiches Job-/Worker-Muster wie Workflow 15, aber pro Paket ein **15-Minuten-Zeitfenster**
statt ein Instrument (Instrumentenzuordnung passiert erst NACH dem Download, nicht beim
Job-Zuschnitt — GDELT liefert einen globalen Strom, keine instrumentspezifische Abfrage):

1. **Zeitraumpakete**: `import_job_items.period_from`/`period_to` sind hier je ein
   15-Minuten-Fenster (nicht ein Instrument) — bei einer mehrjährigen Historie entstehen so
   zehn- bis hunderttausende Items; Paketgröße/Fortsetzbarkeit exakt wie Workflow 15
   (`checkpoint_json`, `heartbeat_at`, stale-Item-Selbstheilung).
2. **Download**: pro Fenster ein kleines Suchfenster (Minute 0–5 nach der Marke) gegen
   `data.gdeltproject.org/gdeltv3/gal/{ts}.gal.json.gz` probieren, alle antwortenden Dateien
   laden und entpacken (kein API-Key, kein Rate-Limit-Header bekannt — konservatives Delay
   zwischen Anfragen wie bei jedem unauthentifizierten öffentlichen Dienst).
3. **Deduplizierung**: `UNIQUE(news_key, provider)` auf `historical_news`, `news_key` aus
   normalisierter `url` (matches GDELTs eigene Duplikat-Warnung).
4. **Unternehmenszuordnung** (neu, nicht in Workflow 15 nötig): pro Artikel Titel+Beschreibung
   gegen `stock_instruments.name`/`aliases_json` (= die "Keywords" der Anforderung — `aliases_json`
   ist bereits die Keyword-Liste, kein neues Feld nötig) sowie `exclude_patterns_json` prüfen.
   Quelle ist `stock_instruments` direkt, nicht `trading.watchlist`: letztere enthält nur eine
   einmalig geseedete Kopie derselben Daten (`007_runtime_schema_reconciliation.sql`,
   `ON CONFLICT DO NOTHING`) und kann seither von `stock_instruments` abweichen. Eindeutiger
   Treffer → `linked_tickers_json`; **mehrdeutiger Treffer (mehrere Instrumente gleichzeitig
   plausibel) → explizit als unklar markieren**, nicht erraten; kein Treffer +
   Wirtschafts-/Marktbezug erkennbar → `is_general_market=true`; sonst verworfen (kein
   Datenbankeintrag, kein Bezug zum Projekt).
5. **Analyse-Wiederverwendung**: Titel+Beschreibung durch dieselbe Bewertungslogik wie `03`s
   `KI: Nachricht bewerten` schicken (kontrolliert wiederverwendet als `Execute Workflow`-
   Baustein, kein Prompt-Duplikat), Ergebnis in eine noch zu ergänzende
   `historical_news_assessments`-Struktur statt `news_assessments` — Details in Phase 5.
6. **Datenqualität**: fehlender Volltext (GDELT liefert nur Titel/Kurzbeschreibung) wird als
   strukturiertes Qualitätsmerkmal auf der Zeile dokumentiert, nicht verschwiegen — Simulation
   und Dashboard müssen sichtbar machen, dass die Bewertung auf Titel+Beschreibung statt
   Volltext beruht.
7. **Live-Feeds unverändert**: `trading.rss_sources`/`03` bleiben ausschließlich für aktuelle
   Nachrichten zuständig, keine Vermischung mit dem GDELT-Importpfad.
8. **Common Crawl CC-News**: bewusst nicht in Phase 5 — als späterer, optionaler Fallback
   vermerkt, falls GDELT-Abdeckung für bestimmte Zeiträume unzureichend ist.

### 4.3 Workflow 17 — Walk-Forward-Simulation

Der Kern-Worker: liest offene `simulation_run_steps` paketweise (ein oder mehrere simulierte
Handelstage pro Aufruf), baut für jeden Tag den Simulationskontext (Abschnitt 5), lädt
ausschließlich `historical_price_data`/`historical_news` mit `trading_date <= as_of_date` bzw.
`published_at <= data_cutoff_at`, berechnet technische Signale/Marktregime **neu** (die
vorhandene Live-Logik aus `02`/`02b` ist zu schmal/kurz für eine mehrjährige Historie, siehe
Abschnitt 1.1) über eine parametrisierte, zeitkontext-bewusste Variante, erzeugt
`simulation_recommendations`, simuliert Ausführung fühestens am nächsten Handelstag (Abschnitt
„Simulierte Orderausführung" des Auftrags) nach `simulation_orders`, führt Portfolio-/
Risikoregeln (wiederverwendet aus `14`s Konfigurationswerten) gegen `simulation_positions` aus,
schreibt `simulation_daily_portfolio` je Tag. Nach Abschluss aggregiert ein letzter Schritt
`simulation_metrics`.

### 4.4 Workflow 18 — Historische Fundamentaldaten (optional, deferred)

Wird **nicht** in Phase 3-6 gebaut. `historical_fundamentals`-Tabelle wird in `sql/057` bereits
angelegt (Schema-only, wie beim Vorbild `backtest_runs`/`probability_estimates`), aber ohne
Workflow, bis die Point-in-Time-Verfügbarkeit (`available_from` zuverlässig vom Datenanbieter)
geklärt ist — exakt die vom Auftrag selbst verlangte Bedingung. Die erste Simulationsversion
(Phase 3/4) läuft mit `fundamentals_enabled=false`.

## 5. Zentraler Simulationskontext

Da n8n-Code-Nodes keinen gemeinsamen Scope teilen (bestätigt in Abschnitt 1.1), wird der
Simulationskontext **nicht** als prozessweites Objekt, sondern als **durchgereichtes JSON-Feld**
auf jedem Item umgesetzt (gleiche Technik wie das bestehende `business_date`-Feld):

```json
{
  "run_type": "historical_replay",
  "simulation_id": "sim-...",
  "as_of_date": "2024-04-15",
  "data_cutoff_at": "2024-04-15T18:00:00+02:00",
  "timezone": "Europe/Berlin",
  "model_version": "...",
  "rule_version": "...",
  "configuration_version": "...",
  "dataset_version": "..."
}
```

Jede wiederverwendete/neu geschriebene Analysefunktion in Workflow 17 muss dieses Feld als
Pflichtparameter akzeptieren; `tools/validate-historical-simulation.js` (Phase-8-Tooling)
prüft automatisiert, dass kein neuer Node in Workflow 15/16/17 `now()`/`CURRENT_DATE`/
`new Date()` ohne Bezug auf dieses Feld verwendet (siehe Abschnitt 8, Validierungsplan).

## 6. Web-Steuerzentrale — technischer Zuschnitt

Neuer eigenständiger Workflow (Arbeitstitel `Simulation-Steuerzentrale`), Webhook-Pfad
`/simulation`, gebaut nach dem etablierten Muster aus Abschnitt 1.2: pro Bereich ein
GET-Webhook (Anzeige) + wo nötig ein POST-Webhook (Aktionen über eine
Aktions-Whitelist-Kette), jeweils ein `Baue HTML`-Node pro Unterseite. Die vom Auftrag
vorgeschlagenen Endpunkte (`/simulation/api/overview`, `/simulation/api/imports`, `/simulation/
api/runs/*`, `/simulation/api/data-quality` usw.) werden 1:1 als eigene Webhook-Pfade auf
demselben Workflow umgesetzt — konsistent mit der bestehenden Ein-Workflow-pro-Seite-
Konvention, nur mit mehr Pfaden innerhalb dieses einen neuen Workflows statt vieler kleiner
Workflows.

Schutzmaßnahmen (Abschnitt „Schutzmaßnahmen" des Auftrags) werden 1:1 aus den bestehenden
Mustern übernommen: feste Aktions-Whitelist, `pgStr`/`pgNum`/`pgJson`-Escaping (bereits
Projektkonvention in jedem `SQL bauen`-Node), IDs immer über `WHERE id = $1`-artige
`pgStr`/`pgNum`-Bindung nie direkt interpoliert aus Rohtext, serverseitige Statusübergangs-
Prüfung (z. B. „pausieren" nur erlaubt, wenn `status='running'`), `version`-Spalte für
Optimistic Locking auf `backtest_runs`, `Idempotency-Key`-Header oder Client-generierte
`job_id`/`simulation_id` gegen doppelte Start-Klicks (Duplikatsprüfung analog zum bereits
bestehenden `ux_recommendations_one_open_per_ticker`-Muster).

## 7. Bias-Risiken (Zusammenfassung, Details siehe Testkonzept Abschnitt 9)

1. **Look-ahead durch Wiederverwendung falscher Tabellen** — gebannt durch strukturelle
   Trennung (Abschnitt 3.2), nicht nur durch Disziplin.
2. **`now()`/`CURRENT_DATE`/`new Date()` in wiederverwendeter Logik** — Workflow 17 darf keine
   der Live-Berechnungsfunktionen (`02`s technische Analyse, `02b`s Marktregime, `06`s
   Empfehlungslogik) unverändert per `Execute Workflow` aufrufen, weil diese intern `now()`
   verwenden (frisch aus der heutigen P1.9-Reparatur bekannt — genau dieselbe Bugklasse würde
   hier zum eigentlichen Bias-Risiko). Stattdessen: parametrisierte Kopien, die den
   Simulationskontext zwingend injizieren (Abschnitt 5). Das ist mehr Code-Duplikation als eine
   gemeinsame Funktion, aber die einzige Variante ohne Restrisiko einer versehentlichen
   `now()`-Nutzung mitten in einer sonst korrekt injizierten Funktion.
3. **Fundamentaldaten-Publikationsverzug** — durch Deferral von Workflow 18 umgangen (Abschnitt
   4.4), nicht gelöst — erste Simulationsversion arbeitet bewusst ohne Fundamentaldaten.
4. **Konfigurationsdrift** — durch `config_snapshot_json` auf `backtest_runs` gebannt (Abschnitt
   3.1), ein Lauf bleibt reproduzierbar, auch wenn sich `pipeline_config` später ändert.

## 8. Offene Entscheidungen

### 8.1 `backtest_runs` erweitern vs. neue `simulation_runs`-Tabelle

**Entschieden für Erweiterung** (Abschnitt 3.1) — Begründung: `backtest_runs` ist dormant (0
Zeilen), inhaltlich bereits fast deckungsgleich mit dem Auftrags-Vorschlag, und der Auftrag
selbst verlangt „Prüfe zuerst, welche Tabellen bereits existieren" + „Passe Namen an bestehende
Namenskonventionen an". Eine Umbenennung in `simulation_runs` wäre möglich, würde aber
zusätzlich zwei bestehende Dokumente (`BACKTESTING_UND_WALK_FORWARD.md`,
`WAHRSCHEINLICHKEITSKALIBRIERUNG.md`) inkonsistent machen — daher Name `backtest_runs`
beibehalten, `backtest_id` erfüllt die `simulation_id`-Rolle.

### 8.2 `simulation_trades` als eigene Tabelle vs. Diskriminator auf `paper_trades`

**Entschieden für eigene Tabelle** (Abschnitt 3.2) — Begründung: anders als bei
`backtest_runs` (dormant, keine Live-Nutzung) ist `paper_trades` aktiv vom echten
Paper-Trading-System (`14`) genutzt. Ein Diskriminator-Feld würde bedeuten, dass **jede**
zukünftige Leseabfrage auf `paper_trades` (auch solche, die noch nicht existieren) diszipliniert
den Diskriminator mitfiltern müsste — ein einziges vergessenes `WHERE data_category='live'`
würde historische Simulationsdaten ins reale Buch mischen. Der Auftrag selbst listet
`historical_replay`/`training`/`calibration`/`out_of_sample` als von `paper_live` **getrennte**
Kategorien, nicht als Varianten derselben Tabelle. Mehrpflege einer zweiten, strukturell
ähnlichen Tabelle wird als geringeres Risiko bewertet als ein vergessener Filter auf einer
Live-Tabelle.

### 8.3 Kann der bestehende FastAPI-Kursdienst mehrjährige historische Zeiträume liefern?

**Geklärt 2026-08-03, JA — vollständig ausreichend für Workflow 15.** Live gegen
`http://172.16.1.14:8099` getestet (nach einem parallel gefundenen und behobenen Bug, siehe
unten): `/api/v1/history/{ticker}` liefert `period=5y`/`10y`/`max` (AAPL: 11.500 Zeilen zurück
bis 1980-12-12, dem Börsengang) ebenso wie explizite `start`/`end`-Datumsbereiche
(exakt gefiltert, im Test 20 Handelstage für Januar 2015). `/api/v1/history/batch` deckt
mehrere Instrumente gleichzeitig ab (getestet: AAPL/SAP.DE/MSFT, US+DE-Börse). Dedizierte
Corporate-Actions-Endpunkte (`/api/v1/dividends/{ticker}`, `/api/v1/splits/{ticker}`,
`/api/v1/actions/{ticker}`) liefern ebenfalls vollständige Historie (AAPL-Dividenden bis 1987)
mit `date`/`type`/`value`/`source`-Feldern — direkt passend für
`trading.historical_corporate_actions`. **Workflow 15 kann also direkt gegen diesen bestehenden
Dienst gebaut werden, kein neuer/anderer Anbieter nötig.**

**Zwei echte Bugs im Dienst selbst gefunden und behoben, um dahin zu kommen** (Datei
`app.py`, Deployment `root@n8n:/opt/trading-data-service`, systemd-Service
`trading-data-service`) — beide waren reine Zufallsfunde beim Testen, keine
Simulations-spezifischen Änderungen: (1) `fetch_history_df()` reichte `progress=False`/
`threads=False` an `Ticker().history()` durch — das sind Parameter von `yf.download()` (Modul-
Funktion), nie von `Ticker().history()` gültig; die aktuell installierte yfinance-Version
(`PriceHistory`-Klasse) validiert Keyword-Argumente jetzt strikt und lehnte sie ab, wodurch
JEDER `history()`/`chart`-Aufruf fehlschlug (bestätigt per `journalctl`: `PriceHistory.history()
got an unexpected keyword argument 'progress'`) — betraf auch den von `01`/`02`/`02b` taeglich
genutzten Legacy-Endpunkt `/chart/{ticker}`, war also ein **echtes, bereits vor dieser Sitzung
bestehendes Live-Produktionsproblem**, nicht nur ein Hindernis fuer die Simulation. (2) Nach
diesem Fix zweiter Fehler: `repair=True` (im Code bewusst gesetzt, Datenqualitaets-Reparatur)
braucht intern `scipy`, das im venv fehlte (`No module named 'scipy'`) — per
`pip install scipy` im venv nachinstalliert. Eine erste Hypothese (Yahoo-Bot-Erkennung,
curl_cffi-Workaround) erwies sich beim Live-Log-Abgleich als falsch und wurde wieder
zurueckgebaut, um keine unnoetige Komplexitaet/Abhaengigkeit fuer ein nicht bestehendes Problem
einzufuehren.

### 8.4 Datenanbieter für historische Nachrichten (Workflow 16)

**Entschieden 2026-08-03: GDELT Article List (GAL) Historical Backfile, kein Login/API-Key.**
Live verifiziert (nicht nur aus der Doku übernommen):

- **Basis-URL:** `http://data.gdeltproject.org/gdeltv3/gal/{YYYYMMDDHHMMSS}.gal.json.gz`
  (gzip-komprimiertes JSON-NL, ein JSON-Objekt pro Zeile).
- **Historische Abdeckung:** ab 2020-01-01 bis heute, live an mehreren Stichproben (2020,
  2023) bestätigt erreichbar.
- **Zeitraster ist NICHT exakt `:00/:15/:30/:45`.** Dateien clustern typischerweise 1–4
  Minuten NACH jeder Viertelstunden-Marke, der genaue Offset variiert (live beobachtet: 2020
  bei +1..+3, 2023 bei +2..+3) — **pro 15-Minuten-Fenster muss ein kleines Suchfenster
  (Minute 0–5 nach der Marke) durchprobiert werden**, alle mit HTTP 200 antwortenden Dateien
  herunterladen (können mehrere pro Fenster sein), 404 ist der Normalfall für die meisten
  Minuten und kein Fehler.
- **JSON-Zeilen-Schema** (live bestätigt): `date` (Zeitstempel), `url`, `domain`,
  `outletName`, `outletLogo`, `outletTwitter`, `title`, `image`, `desc` (Kurzbeschreibung/
  Meta-Description, laut GDELT bei ~91% der Artikel vorhanden), `lang` (CLD2-Sprachcode),
  `author`. **Kein Volltext** — nur Titel + Kurzbeschreibung, kein vollständiger Artikeltext.
  Wird als Datenqualitätseinschränkung dokumentiert (`historical_news.raw_content` bleibt
  NULL für GDELT-Quellen; Analyse arbeitet auf Titel+Beschreibung statt Volltext).
- **Hohe Duplikatrate laut GDELT selbst** ("substantially elevated number of duplicate
  records") — Deduplizierung über `UNIQUE(news_key, provider)` (news_key aus normalisierter
  URL) ist Pflicht, nicht optional.
- **Kein Ticker-/Unternehmensbezug in den Daten selbst** — das ist ein globaler,
  themenunabhängiger Nachrichtenstrom (keine Finanz-spezifische Filterung von GDELT aus).
  Unternehmenszuordnung muss vollständig clientseitig über die bestehende
  `stock_instruments`-Tabelle erfolgen (Name, `aliases_json`, Keywords, `exclude_patterns_json`
  — dieselben Felder, die `trading.watchlist`/`stock_instruments` laut Ist-Zustand bereits
  für Themen-/Keyword-Matching vorhalten, siehe Abschnitt 1.1).
- **Fallback (spät, optional, noch nicht spezifiziert):** Common Crawl CC-News, nur falls
  GDELT-Abdeckung für bestimmte Zeiträume/Regionen sich als unzureichend erweist.
- **Live-Feeds bleiben unverändert bei den bestehenden RSS-Quellen** (`trading.rss_sources`,
  `03`) — GDELT ist ausschließlich für die historische Simulation, keine Ablösung der
  Live-Pipeline.

### 8.5 Umfang der ersten produktiven Version

Gegeben die Größe des Gesamtauftrags (3 neue Workflows, ~19 neue/erweiterte Tabellen, 8
Web-Bereiche, Job-Engine, Bias-Schutz, Tests) wird empfohlen, die Entwicklungsreihenfolge des
Auftrags (Phase 1-8) strikt einzuhalten und nach jeder Phase einen funktionsfähigen
Zwischenstand zu haben, statt alle Komponenten gleichzeitig unfertig zu bauen — siehe
`docs/HISTORISCHE_SIMULATION_UMSETZUNGSBERICHT.md` für den jeweils aktuellen Umsetzungsstand.

## 9. Testkonzept (Übersicht, Details je Phase in `TESTPLAN`-artigen Dateien analog zu Welle 1-3)

Import-Idempotenz (wiederholter Import erzeugt keine Duplikate), Pagination/Fortsetzbarkeit,
Bias-Prüfungen (keine Daten nach `data_cutoff_at`, kein D+0-Kauf, Wochenenden/Feiertage
berücksichtigt), Oberfläche (ungültige IDs/Statusübergänge abgelehnt, keine doppelten Jobs),
Corporate-Actions-Korrektheit (Split-Anpassung, keine Doppelverrechnung bei bereits
adjustierten Kursen) — vollständige Testfälle werden mit der jeweiligen Phase geliefert
(gleiche Methode wie `tests/test_welle1/2/3_reine_funktionen.js`).

## 10. Nächste Schritte (Reihenfolge wie im Auftrag vorgegeben)

Phase 2 (SQL-Migration `sql/057`, idempotent, **nicht automatisch ausgeführt**) folgt direkt im
Anschluss an dieses Dokument. Phase 3 (Workflow 15 + Datenimport-UI) ist der nächste
umsetzungsintensive Schritt und braucht vorab die Klärung aus Abschnitt 8.3.
