# EXPERIMENT_PLATFORM_REVIEW.md

Stand: 2026-08-20. Bestandsaufnahme vor jeder Implementierung (Auftragsvorgabe: "zuerst
vorhandene Tabellen, Workflows, Lernagenten und Simulationen vollständig prüfen"). Basiert auf
einer systematischen Durchsuchung aller `sql/*.sql`-Migrationen, aller Root-Workflow-JSONs und
aller `docs/*.md`-Dateien, plus einer gezielten Graph-Traversierung des Worker-Trigger-Pfads von
Workflow 17.

**Umsetzungsstand (laufend aktualisiert):**
- [x] Punkt 1 (Config-Snapshot in WF17) — bereits vor diesem Bericht live gefixt, siehe
  Commit `ab8af30`.
- [x] Punkt 3 (Champion/Challenger-Zwischenschritt) — 2026-08-20 live umgesetzt: Workflow 12
  jetzt `proposed → approved → activated` statt direkt `proposed → activated`, nur der manuelle
  Zwischenschritt (kein automatischer Vergleichslauf, Nutzerentscheidung). Commit `e8bacfa`.
- [x] Punkt 2 (`strategy_regime_matrix`-Versionierung) — 2026-08-20 live umgesetzt: `active`-
  Spalte (sql/067) ersetzt `rule_version`-String als "aktuelle Version"-Kriterium. Workflow 12
  dektiviert bei `regime_restriction`-Freigabe die alte Zeile und fügt eine neu versionierte
  ein statt in-place zu überschreiben; Workflow 06 und der Config-Snapshot in Workflow 17 lesen
  jetzt `WHERE active = TRUE` statt des festen Strings.
- [x] Punkt 4 (`market_context_history` Point-in-Time) — 2026-08-20 live umgesetzt: `sql/068`
  (gleiches Muster wie `sql/022`/`sql/041`). Workflow 02b (Writer) schliesst jetzt die aktuelle
  Revision und legt eine neue an statt in-place zu überschreiben; Workflow 06/07/10 (Reader)
  lesen `AND valid_to IS NULL`.
- [ ] Punkt 5 (Experiment-Register als View)
- [ ] Punkt 6 (Monitoring: Queue-Länge)
- [ ] Punkt 7 (`BACKTESTING_UND_WALK_FORWARD.md` aktualisieren)

---

## Gesamturteil

Das System ist deutlich näher an einer Experimentierplattform als der Auftragstext annimmt — die
meisten der 13 geforderten Bausteine existieren bereits in irgendeiner Form (Config-Snapshot-Spalten,
Point-in-Time-Revisionierung auf 3 von 4 Zieltabellen, ein aktiver P-Hacking-Schutz mit
Überschneidungssperre, ein Audit-Trail für Statusübergänge). Das eigentliche Problem ist **nicht
fehlende Struktur, sondern eine Lücke zwischen Schema und tatsächlicher Nutzung**: Die wichtigste
Spalte für Reproduzierbarkeit (`backtest_runs.config_snapshot_json`) wird von Workflow 17 nie
beschrieben und nie gelesen — die Simulation lädt stattdessen bei jedem Worker-Tick die aktuelle
Live-Konfiguration neu. Das ist der größte Einzelbefund dieser Prüfung und macht **jeden bisherigen
Simulationslauf, der über mehrere Worker-Ticks gelaufen ist, potenziell nicht exakt reproduzierbar**,
falls sich `trading.pipeline_config` währenddessen geändert hat.

Champion/Challenger existiert als Konzept **nicht** — Lernvorschläge werden direkt und einmalig
aktiviert (`proposed` → `activated`), obwohl das Schema selbst bereits ungenutzte
Zwischenzustände (`approved`/`rejected`) für genau so einen Zwischenschritt vorsieht.

---

## Kritischster Einzelfund: Config-Snapshot wird nicht verwendet

**Belegt per Graph-Traversierung** (nicht vermutet): Der Schedule-Trigger-Pfad in Workflow 17 lautet:

```
Schedule Trigger: Simulations-Worker
  → DB: Naechsten aktiven Lauf finden → Pruefe Run-Zustand → ... → DB: Lauf-Lock beanspruchen
  → DB: Lauf auf running setzen
  → DB: Simulations-Konfiguration laden        ← LIVE-Query gegen trading.pipeline_config
  → Baue Run-Kontext                             ← baut `cfg` NEU aus dieser Live-Query
  → DB: Naechstes Tage-Paket laden → ... → Verarbeite Tage-Paket   ← nutzt `cfg` fuer die Mathematik
```

`Baue Run-Kontext` liegt **direkt im 5-Minuten-Worker-Zyklus**, nicht in einem
Einmal-bei-Run-Erstellung-Pfad. Jedes Mal, wenn der Worker ein neues Tage-Paket eines aktiven
Laufs verarbeitet, wird `trading.pipeline_config` frisch abgefragt und daraus `cfg` (u. a.
`maxRiskPerTradePct`, `feesBps`, `slippageBps`, `maxTotalOpenRiskPct`, `ambiguousBarPolicyCode`)
neu gebaut.

Gleichzeitig existiert `trading.backtest_runs.config_snapshot_json` (JSONB), angelegt in
`sql/057_historische_simulation.sql:52,74-76` mit dem Kommentar: *"Unveraenderlicher Snapshot von
trading.pipeline_config zum Startzeitpunkt des Laufs — macht den Lauf reproduzierbar, auch wenn
sich pipeline_config spaeter aendert."* Eine Volltextsuche über alle Workflow-JSONs zeigt: **diese
Spalte kommt in Workflow 17 an keiner einzigen Stelle vor** — weder beim Schreiben (Run-Erstellung)
noch beim Lesen (Worker-Tick). Sie wird ausschließlich in Workflow 13 (Markt-Screener) und
Workflow 14 (Portfolio-Risiko) für deren *eigene*, andere Snapshot-Zwecke verwendet.

**Fachliche Konsequenz:** Ändert jemand während eines mehrtägigen/-wöchigen Simulationslaufs über
Workflow 12 einen Lernvorschlag, der `DEFAULT_FEES_BPS`, `MAX_RISK_PER_TRADE_PCT` o. ä. ändert,
verarbeiten spätere Tage-Pakete desselben Laufs andere Werte als frühere — ein und derselbe
`backtest_id` enthält dann intern zwei verschiedene Konfigurationsstände, ohne dass das irgendwo
sichtbar würde. Das widerspricht direkt der Auftragsvorgabe *"Nach Start eines Runs darf dieser
NICHT später die aktuelle Live-Konfiguration nachladen."*

**Das ist keine fehlende Funktion, sondern eine Verdrahtungslücke** — die Spalte, der Kommentar und
die Absicht existieren bereits seit `sql/057` (2026-08-03/04); nur der Code, der sie tatsächlich
befüllt und beim Worker-Tick liest statt live nachzuladen, fehlt.

---

## Ist-Zustand je Auftragspunkt

### 1. Configuration Snapshots — Struktur vorhanden, aber fragmentiert und (bei WF17) unbenutzt

Mehrere Snapshot-Spalten existieren bereits, verteilt auf verschiedene Tabellen statt eines
einheitlichen Konzepts:

| Spalte | Tabelle | Migration | Zweck |
|---|---|---|---|
| `configuration_version`, `rule_version` | `backtest_runs` | `sql/037:25-26` | Versions-*Schlüssel* (Text), kein Werte-Snapshot |
| `config_snapshot_json` | `backtest_runs` | `sql/057:52` | Werte-Snapshot — **von WF17 ungenutzt, siehe oben** |
| `known_at_entry_json` | `backtest_runs`/`simulation_trades` | `sql/037:57-59`, `sql/057:385-388` | Snapshot dessen, was zum Entscheidungszeitpunkt bekannt war (pro Lauf bzw. pro Trade) |
| `configuration_snapshot_json` | `trading.recommendations` | `sql/033:24,39` | Regime-Matrix-/Risikomodell-Version zum Entscheidungszeitpunkt (Live-Pfad, WF06) |
| `config_snapshot_json` | Markt-Screener-Läufe | `sql/034:14` | Screener-eigener Snapshot |
| `portfolio_state_snapshot_json` | `portfolio_risk_checks` | `sql/039:69,73` | Portfoliozustand, nicht Konfiguration |

**Volle Spaltenliste `trading.backtest_runs`** (zusammengesetzt aus `sql/037` + `sql/057`):
`id, backtest_id, run_type, strategy_filter, train_window_start/end, validation_window_start/end,
test_window_start/end, configuration_version, rule_version, data_schema_version, status,
trade_count, results_json, started_at, finished_at, data_category, name, description,
start_date, end_date, current_simulation_date, data_cutoff_time, timezone,
instrument_selection_json, benchmark_selection_json, news_enabled, fundamentals_enabled,
portfolio_enabled, learning_enabled, initial_capital, currency, commission_model_json,
slippage_model_json, model_version, dataset_version, config_snapshot_json, paused_at,
cancelled_at, progress_total/completed/percent, warning_count, error_count, last_error,
last_heartbeat, created_by, version, out_of_sample_locked`.

**Fehlt in `config_snapshot_json` selbst, auch wenn es benutzt würde:** kein Feld für die aktive
`scoring_weights`-Version, kein Feld für `strategy_regime_matrix.rule_version`, kein Feld für
News-Gewichte, kein `engine_version` (die neue `trading_engine`-Python-Engine aus dieser Session
existiert noch gar nicht als Versionsbegriff im Schema).

### 2. Point-in-Time — 3 von 4 Zieltabellen vollständig, `market_context_history` fehlt komplett

| Tabelle | known_at | valid_from | valid_to | revision_number |
|---|---|---|---|---|
| `stock_price_history` | nein (hat `fetched_at`) | ja | ja | ja |
| `fundamentals_history` | ja | ja | ja | ja |
| `technical_signals_history` | ja | ja | ja | ja |
| `strategy_signals` | ja | ja | ja | ja |
| **`market_context_history`** | **nein** | **nein** | **nein** | **nein** |
| `market_regime` | ja | nein | nein | nein (nur `rule_version`) |
| `strategy_regime_matrix` | nein | nein | nein | **kein Zeitfeld überhaupt** |
| `pipeline_config` | nein | nein | nein | nein (nur `updated_at`, überschreibt in-place) |
| `scoring_weights` | nein | nein | nein | eigenes Muster: `version`+`active`+`activated_at` |
| `news_assessments`/`historical_news_assessments` | nein | nein | nein | nein |

`market_context_history` ist die einzige der drei ursprünglichen "History"-Tabellen aus
`sql/018` (2025), die bei der Revisions-Nachrüstung 2025 (`sql/022`, `sql/041`) **ausgelassen**
wurde — seitdem nie erweitert.

Wichtiger, tieferliegender Punkt: Selbst wenn (1) oben behoben wird, bleibt eine offene
Design-Frage, die dieser Bericht nicht selbst entscheidet: Soll ein *heute gestarteter* Backtest
für einen *historischen* Zeitraum die Konfiguration verwenden, die **heute** aktiv ist (aktuelle
Regeln rückwirkend testen — klassisches Walk-Forward), oder die Konfiguration, die **damals**
tatsächlich aktiv war (echte historische Treue)? Beides sind legitime Fragestellungen mit
unterschiedlicher Antwort. Der Snapshot-Mechanismus (Punkt 1) löst nur "welche Konfiguration
wurde für DIESEN Lauf verwendet", nicht "war das dieselbe, die damals galt" — Letzteres bräuchte
eine eigene Point-in-Time-Historie auf `pipeline_config`/`scoring_weights`/`strategy_regime_matrix`,
die aktuell nicht existiert und laut Auftrag ("zunaechst keine komplizierte... wenn dafuer noch
keine Daten vorhanden sind") vermutlich bewusst zurückgestellt werden sollte.

### 3. Champion/Challenger — existiert nicht

Der Begriff kommt im gesamten Repository nicht vor. Aktueller Fluss:

- Workflow 09b/09c erzeugt ausschließlich `status='proposed'`-Zeilen in
  `trading.learning_rule_proposals` (nie automatische Aktivierung).
- Workflow 12 aktiviert direkt und synchron: `proposed → activated`, mit sofortigem Schreiben
  in die Zieltabelle (`pipeline_config`/`strategy_regime_matrix`/`strategy_status`/
  `strategy_parameters`/`scoring_weights`) und Optimistic Locking über `version`.
- **Bemerkenswert:** Der Status-CHECK (`sql/038:19-21`) erlaubt bereits `approved`/`rejected` als
  Zwischenzustände — der Code-Kommentar sagt explizit, dass sie *aktuell ungenutzt* sind, weil die
  Freigabe direkt `proposed → activated` springt. **Das Schema hat also bereits die Lücke, in die
  ein Champion/Challenger-Zwischenschritt eingehängt werden könnte, ohne eine neue Spalte
  anzulegen.**
- `learning_rule_proposals.source_run_id` (`sql/061:15-18`) existiert bereits und referenziert den
  Backtest-Lauf, aus dem ein Vorschlag stammt — das ist im Kern schon die "Challenger"-Referenz.
  Was fehlt: ein Gegenstück für den "Champion"-Vergleichslauf sowie ein erzwungener
  Walk-Forward-→-OOS-→-Vergleichs-Ablauf zwischen `proposed` und `activated`.

### 4. OOS/Walk-Forward-Gates — deutlich besser als der Auftragstext annimmt

Ein aktiver, funktionierender P-Hacking-Schutz existiert bereits:

- **Überschneidungssperre** (Workflow 17, Node "POST: Formular normalisieren + SQL bauen"): Ein
  neuer `run_type='out_of_sample'`-Lauf wird per `WHERE NOT EXISTS (...)`-Klausel verhindert, wenn
  für dieselbe Strategie bereits ein sich zeitlich überschneidender OOS-Lauf existiert
  (`queued/running/pausing/completed/completed_with_warnings`). Explizit als p-hacking-Schutz
  kommentiert.
- **Zeitliches Gate in Workflow 09c**: Ein OOS-Bestätigungslauf muss zeitlich NACH dem
  Explorationszeitraum liegen (`start_date > Quelllauf.end_date`) — verhindert, dass eine
  Simulation sich selbst bestätigt.
- **Je-Strategie-Gate in Workflow 09b**: OOS-Bestätigung wird separat je `strategy_filter`
  geprüft, nicht als globales Flag.
- **Mindestfensterlänge**: `BACKTEST_MIN_WINDOW_DAYS = 180` in `pipeline_config`.
- `trading.simulation_events` (`sql/057:475-492`) protokolliert Statusübergänge inkl.
  `event_type='reclassified'`, das **Pflicht** wird, sobald ein Lauf mit `out_of_sample_locked=TRUE`
  seine `data_category` nachträglich ändert — verhindert das im Auftrag befürchtete "OOS nachträglich
  zum Training machen".

Das größte real bestehende Risiko in diesem Bereich ist NICHT ein fehlendes Gate, sondern die
unter Punkt 1 beschriebene Config-Live-Nachladung — ein OOS-Lauf kann formal korrekt isoliert sein
und trotzdem mit unterschiedlicher Konfiguration an verschiedenen Tagen rechnen.

### 5. Experiment-Register — Bausteine vorhanden, aber verteilt

Keine einzelne Tabelle bildet einen Test als eine Zeile ab. Die Bausteine sind vorhanden:

- `backtest_runs`: Zeiträume (`train_window_*`/`validation_window_*`/`test_window_*`),
  Konfiguration (s. Punkt 1), Ergebnis (`results_json`, `trade_count`), Status.
- `learning_rule_proposals`: `reason` (≈ hypothesis), `current_value`/`proposed_value` (≈ ein
  Parameter, nicht ein Set), `status`/`reviewed_at`/`activated_at` (≈ decision/approved_at),
  `source_run_id` (Verweis auf den Backtest).
- `simulation_events`: Audit-Trail für Statusänderungen.

Ein `hypothesis`-Freitextfeld und ein zusammengeführtes "ein Experiment = eine Zeile"-Bild fehlen.

### 6. Scoring-Gewichte / Regime-Matrix — echtes Reproduzierbarkeits-Risiko in der Regime-Matrix gefunden

`trading.scoring_weights` (`sql/001:172-193`) hat eine funktionierende Versionierung:
`version` (INTEGER) + `active` (BOOLEAN) + `activated_at`/`activated_by`, mit Unique-Index "nur
eine aktive Version je Key". Neue Werte werden als **neue Zeile** mit neuer `version` eingefügt,
alte bleiben erhalten — das ist im Kern schon eine funktionierende Punkt-in-Zeit-Historie, auch
ohne explizites `valid_to`.

**`trading.strategy_regime_matrix` (`sql/032:48-57`) dagegen hat gar kein Zeitfeld** — nur den
String `rule_version` (aktuell fest `'regime-matrix-v1'`) als Versionsschlüssel. Workflow 12
verändert die Matrix bei einer `regime_restriction`-Freigabe per `UPDATE` **in place** — die Zeile
wird überschrieben, `rule_version` wird dabei nicht automatisch erhöht. **Das bedeutet: Ein alter
Backtest-Lauf, der `rule_version='regime-matrix-v1'` referenziert, liest bei einer erneuten
Abfrage heute andere Werte als beim ursprünglichen Lauf, obwohl derselbe `rule_version`-String
verwendet wird.** Das ist ein zur Config-Snapshot-Lücke (Punkt 1) strukturell verwandtes, aber
eigenständiges Reproduzierbarkeitsproblem.

### 7. Monitoring — solide Basis vorhanden, "Queue-Länge" fehlt als explizite Metrik

- Workflow 07 ("Status-Uebersicht") hat bereits 63 Nodes inkl. `DB: Letzte Pipeline-Laeufe je
  Stufe` (liest `workflow_name, stage_name, status, started_at, finished_at, duration_ms,
  retry_count, error_message, warning_count, error_count` aus `pipeline_runs`).
- "Simulation-Steuerzentrale" zeigt bereits `progress_total/completed`, `last_heartbeat`,
  `total_return_pct`, `trade_count`, `max_drawdown_pct` pro Lauf sowie eine
  Lauf-Detail-/Vergleichsansicht.
- Nicht gefunden: eine aggregierte "X Jobs warten"-Metrik über die vorhandenen
  Heartbeat-/Checkpoint-Felder (`simulation_run_steps.checkpoint_json`,
  `import_job_items.checkpoint_json`) hinweg.

### 8. Golden Run — bereits umgesetzt (diese Session, vor diesem Auftrag)

`trading_engine/` + `tests/trading_engine/test_golden_run.py` existieren bereits (siehe
`TRADING_ENGINE_ARCHITECTURE.md`). Reproduzierbarer, deterministischer (synthetischer) Regressionstest
vorhanden. Für Punkt 10 des Auftrags ("Vergleich zur vorherigen Version bei jeder
Engine-/Rule-Version") fehlt noch die *Versions-Verkettung* — der Golden Run vergleicht aktuell
gegen EINEN gespeicherten Referenzwert, nicht gegen eine Historie mehrerer Engine-Versionen.

### 9. Survivorship Bias — bereits transparent, bestätigt

Workflow 17 nutzt die aktuelle Watchlist (`trading.stock_instruments WHERE aktiv = TRUE`) nur zum
**Vorbefüllen** des Web-Formulars; das tatsächliche Ticker-Universum eines Laufs ist die manuell
editierbare, im Formular übergebene Liste (`instrument_selection_json`). Bereits in einer früheren
Runde dieser Session geprüft und bestätigt — kein neuer Fund.

### 10. Vorhandene Dokumentation

23 Dateien in `docs/`, thematisch sortiert nach Risikomodell (`RISIKOMODELL_EINZELTRADE.md`,
`PORTFOLIORISIKO.md`), Ausführungsmodell (`AUSFUEHRUNGSMODELL.md`), Backtesting/Walk-Forward
(`BACKTESTING_UND_WALK_FORWARD.md`, `HISTORISCHE_SIMULATION_KONZEPT.md`/
`_UMSETZUNGSBERICHT.md`), Lernagenten (`LERNAGENT_HANDELSSTRATEGIEN.md`). **Wichtiger Fund:**
`BACKTESTING_UND_WALK_FORWARD.md` beschreibt das Backtesting-Schema noch als *dormant* (Stand
2026-08-01) — das ist seit Workflow 17/`sql/057` (2026-08-03/04) überholt und wurde seitdem nicht
aktualisiert. Kein eigenständiges Dokument zu "Versionierung" als Gesamtkonzept — das Thema ist
über mehrere Dokumente und Migrationskommentare verstreut.

---

## Risiken (zusammengefasst, nach Schwere)

1. **[HOCH] Config-Live-Nachladung in WF17** (Punkt 1) — macht laufende/vergangene Simulationen
   potenziell nicht exakt reproduzierbar, falls sich `pipeline_config` während eines mehrtägigen
   Laufs geändert hat. Betrifft JEDEN bisherigen Simulationslauf, der über mehr als einen
   Worker-Tick gelaufen ist — nicht rückwirkend behebbar, nur für künftige Läufe.
2. **[MITTEL] `strategy_regime_matrix`-Updates ohne Versionsbump** (Punkt 6) — ein alter Lauf, der
   eine `rule_version` referenziert, kann durch eine spätere Freigabe stillschweigend andere Werte
   unter derselben Version bekommen.
3. **[MITTEL] Kein Champion/Challenger-Zwischenschritt** (Punkt 3) — ein Lernvorschlag geht ohne
   Shadow-Test/Vergleich direkt live, sobald er manuell freigegeben wird. Die Vier-Gates aus
   `LERNAGENT_HANDELSSTRATEGIEN.md` prüfen die Evidenzlage vor der Freigabe, aber nicht "performt
   der Vorschlag besser als das aktuell aktive Regelwerk in einem echten Vergleichslauf".
4. **[NIEDRIG] `market_context_history` ohne Point-in-Time-Revisionierung** (Punkt 2) — betrifft
   nur diese eine Tabelle, die anderen drei sind bereits vollständig.
5. **[NIEDRIG] Veraltete Dokumentation** (`BACKTESTING_UND_WALK_FORWARD.md`) — Verwechslungsgefahr
   für zukünftige Sitzungen, kein technisches Risiko.

---

## Vorgeschlagene minimale Erweiterungen (bevorzugt: bestehende Mechanismen erweitern)

1. **Config-Snapshot tatsächlich verdrahten** (behebt Risiko 1): Bei Run-Erstellung
   `config_snapshot_json` einmalig aus dem vollständigen `pipeline_config`-Stand
   *plus* der aktiven `scoring_weights`-Version *plus* `strategy_regime_matrix.rule_version`
   befüllen. `Baue Run-Kontext` im Worker-Pfad umstellen: `cfg` aus
   `runCtx.config_snapshot_json` lesen statt `trading.pipeline_config` live abzufragen. Keine neue
   Spalte nötig — die Spalte existiert bereits seit `sql/057`.
2. **`strategy_regime_matrix` versionieren wie `scoring_weights`** (behebt Risiko 2): Statt
   `UPDATE` bei Freigabe eine neue Zeile mit neuer `rule_version` einfügen (gleiches Muster wie
   `scoring_weights.version`). Kleine Änderung in Workflow 12s `RULE_TABLE`-Handhabung für
   `regime_restriction`.
3. **Champion/Challenger über die bereits vorhandenen, ungenutzten Status `approved`/`rejected`**
   (behebt Risiko 3): Freigabe-Fluss in Workflow 12 zweistufig machen —
   `proposed → approved` löst automatisch einen Walk-Forward-/OOS-Vergleichslauf aus
   (`source_run_id` als Challenger, ein neu zu bestimmender aktueller "Champion"-Lauf als
   Vergleich), erst danach manuelle Freigabe `approved → activated`. Keine neue Tabelle nötig.
4. **`market_context_history` auf das bestehende Revisionsschema heben** (behebt Risiko 4):
   gleiches Spaltenmuster wie `fundamentals_history`/`technical_signals_history` (`known_at`,
   `valid_from`, `valid_to`, `revision_number`) per neuer Migration ergänzen.
5. **Experiment-Register als View statt neuer Tabelle**: Eine SQL-View, die `backtest_runs` +
   `learning_rule_proposals` + `simulation_events` auf die im Auftrag gewünschten Experiment-Felder
   zusammenführt — deckt den Bedarf ohne Parallelstruktur. Ein `hypothesis`-Freitextfeld müsste
   ergänzt werden (kleine Spalten-Migration auf `learning_rule_proposals`, `reason` existiert
   schon ähnlich, aber nicht explizit als Hypothese vor dem Test formuliert).
6. **Monitoring**: bestehende Dashboards (07, Simulation-Steuerzentrale) um eine
   Queue-Länge-Kennzahl ergänzen (`COUNT(*) FROM simulation_run_steps WHERE status='pending'`
   o. ä.) — keine neue Plattform.
7. **`BACKTESTING_UND_WALK_FORWARD.md` aktualisieren** oder als veraltet kennzeichnen.

---

## Notwendige DB-Migrationen (Entwurf, noch nicht angelegt)

- Neue Migration: `market_context_history` um `known_at`/`valid_from`/`valid_to`/
  `revision_number` erweitern (analog `sql/022`/`sql/041`).
- Neue Migration: `strategy_regime_matrix` um Versionierungsmuster erweitern (entweder
  `valid_from`/`valid_to` ergänzen, oder auf das `scoring_weights`-Muster umstellen).
- Kleine Migration: `learning_rule_proposals` um `hypothesis` (TEXT) und `champion_run_id`
  (FK auf `backtest_runs`) ergänzen, falls Punkt 3 umgesetzt wird.
- Keine neue Tabelle für Config-Snapshots nötig (Spalte existiert bereits).
- Keine neue Tabelle für ein Experiment-Register nötig (View statt Tabelle vorgeschlagen).

## Notwendige Workflow-Änderungen (Entwurf, noch nicht umgesetzt)

- **Workflow 17**: `Baue Run-Kontext` umstellen (Live-Query → Snapshot-Read), Run-Erstellungspfad
  um vollständige Snapshot-Befüllung ergänzen (größter Einzeleingriff dieser Erweiterung).
- **Workflow 12**: `regime_restriction`-Freigabe von `UPDATE` auf "neue versionierte Zeile"
  umstellen; Freigabe-Fluss um den `approved`-Zwischenschritt (+ automatisch ausgelösten
  Vergleichslauf) erweitern, falls Champion/Challenger gewünscht.
- **Workflow 07 / Simulation-Steuerzentrale**: Queue-Längen-Query ergänzen.

## Notwendige Engine-Änderungen (trading_engine/, aus dieser Session)

- `ConfigSnapshot`/`RiskConfig`/`FeeModel` aus `trading_engine/models.py` sind bereits so
  gebaut, dass sie einen eingefrorenen Konfigurationsstand als expliziten Parameter erwarten
  (kein globaler Zustand, kein Nachladen) — das entspricht bereits dem Zielbild dieses Berichts
  und müsste NICHT geändert werden. Die Lücke liegt ausschließlich auf der n8n-Seite (Workflow 17
  lädt aktuell noch nicht einmal über die neue Engine, siehe Phase-8-Migration, die noch aussteht).
- Für ein `engine_version`-Feld im Snapshot: `trading_engine` bräuchte eine einfache
  `__version__`-Konstante (existiert noch nicht).

---

## Was dieser Bericht NICHT beantwortet (bewusst offen für die nächste Entscheidung)

- Ob eine historische Simulation die *damalige* oder die *heutige* Konfiguration verwenden soll
  (siehe Punkt 2, Design-Frage) — das ist eine fachliche Entscheidung, keine technische.
- Ob Champion/Challenger den `approved`-Zwischenschritt automatisch mit einem Vergleichslauf
  koppeln soll, oder ob das erstmal nur der manuelle Zwischenstopp selbst sein soll (kleinerer
  erster Schritt).
- Umfang der Monitoring-Erweiterung (welche Metriken zuerst).

Diese drei Punkte würde ich vor der Implementierung kurz mit dir klären, statt sie hier
vorwegzunehmen.
