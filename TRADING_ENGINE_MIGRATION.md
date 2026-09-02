# TRADING_ENGINE_MIGRATION.md

Stand: 2026-08-20. Konkreter Umsetzungsplan für Phase 8 aus `TRADING_ENGINE_ARCHITECTURE.md`:
Workflow 17 ("Historische Simulation") von seiner eingebetteten JS-Simulationslogik ("Verarbeite
Tage-Paket", ~39.700 Zeichen) auf die getestete Python-Engine (`trading_engine/`, FastAPI-Endpunkt
`POST /engine/simulation/step`) umstellen. Workflow 14 (Live-Paper-Trading) ist **nicht** Teil
dieser Migration — eigener, späterer Schritt (siehe Ende dieses Dokuments).

**Warum ein eigenes Dokument statt direkt loszubauen:** Workflow 17 ist ein aktiver, alle paar
Minuten laufender Produktions-Workflow, der reale (Paper-)Trading-Entscheidungen simuliert. Der
Auftrag verlangt explizit, fachliche Verhaltensänderungen aus einer Zentralisierung sichtbar zu
dokumentieren statt sie stillschweigend mitlaufen zu lassen (siehe `TRADING_ENGINE_ARCHITECTURE.md`,
Architekturfragen-Abschnitt). Dieses Dokument ist die Umsetzung dieser Vorgabe für Phase 8 konkret.

---

## 1. Beim Code-Abgleich gefundene Punkte (vor der Migration zu klären, nicht danach)

Direkter Vergleich zwischen dem echten Live-Code in Workflow 17 ("Verarbeite Tage-Paket") und
`trading_engine/*.py`:

### 1.1 Engine-Bug gefunden und gefixt (2026-08-20)

`position_sizing.py::_size_position_clamp()` prüfte den `UNECONOMICAL_AFTER_COSTS`-Veto nur bei
`fee_model.kind == "fee_bps"`. WF17 nutzt `kind="mini_future"` — der Veto wäre nach einer Migration
nie mehr ausgelöst worden, obwohl der Live-Code ihn heute **immer** prüft (er nutzt dafür die
generischen `feesBps`/`slippageBps`-Config-Werte als reine Schwellenwert-Heuristik, unabhängig vom
tatsächlichen Abrechnungsmodell — siehe `cfg.feesBps`/`cfg.slippageBps` in "Verarbeite Tage-Paket",
getrennt von `miniFutureSpreadPct`/`miniFutureFinancingPctPa`). Kein bestehender Test deckte den
mini_future-Fall ab. **Gefixt**: der Veto greift jetzt, sobald `fee_bps`/`slippage_bps` im
`fee_model` gesetzt sind, unabhängig von `kind`. Zwei neue Tests ergänzt (mit/ohne bps-Felder bei
`kind="mini_future"`), 79/79 grün.

**Konsequenz für die Migration:** WF17 muss beim Aufruf zusätzlich zu den drei `miniFuture*`-Werten
auch die generischen `fees_bps`/`slippage_bps`-Werte aus `trading.pipeline_config`
(`DEFAULT_FEES_BPS`/`DEFAULT_SLIPPAGE_BPS`, dieselben Keys, die WF17 heute schon für genau diesen
Veto liest) im `fee_model`-Payload mitschicken.

### 1.2 Bewusste, gewollte Verhaltensverbesserung — betrifft Backtest-Ergebnisse spürbar

`risk_limits.py::check_portfolio_limits()` prüft bereits **alle 9** Risikolimits aus Workflow 14
Job A (`TOTAL_RISK_LIMIT`, `SECTOR_LIMIT`, `REGION_LIMIT`, `CURRENCY_LIMIT`, `SINGLE_POSITION_LIMIT`,
`MAX_OPEN_POSITIONS`, `DIRECTIONAL_LIMIT`, `DRAWDOWN_LIMIT`, `CORRELATION_LIMIT`, inkl.
Stress-Regime-Reduktion). WF17s heutiges `checkHardLimits()` prüft nur 2 davon
(`MAX_OPEN_POSITIONS`, `DIRECTIONAL_LIMIT`) — Sektor/Region/Gesamtrisiko laufen heute nur implizit
über die Kappung in `sizePosition()`, **Drawdown-Lock, Korrelationsgrenze und Fremdwährungsgrenze
existieren in WF17 heute gar nicht**.

Das ist laut `TRADING_ENGINE_ARCHITECTURE.md` (Phase 1: "Backtest-Ergebnisse sind... systematisch
zu optimistisch"; Phase 4: "Nach der Migration verschwinden [die Lücken] automatisch") ausdrücklich
gewollt — **aber es bedeutet, dass Backtest-Ergebnisse nach der Migration messbar anders ausfallen
werden**, besonders in Phasen mit hohem Drawdown. Das ist keine Regression, sondern der eigentliche
fachliche Zweck der Zentralisierung. Wird hiermit explizit dokumentiert, nicht stillschweigend
mitgeliefert.

**Bewusst limitierter erster Schritt:** `correlation_data` wird anfangs als `null`, `is_stress_regime`
als `false` übergeben — WF17 hat heute weder eine Korrelationsberechnung noch eine
Markt-Regime-Anbindung. Der Korrelationslimit-Zweig bleibt dadurch vorerst faktisch inaktiv, die
Stress-Reduktion wirkt nie. Das ist ein bewusster erster Ausbauschritt (5 von 9 Limits neu aktiv:
Drawdown, Währung — Korrelation/Stress folgen erst mit einer eigenen Datenanbindung, siehe
"Nicht in dieser Runde" unten), keine vollständige Angleichung an Workflow 14 in einem Schritt.

### 1.3 News-Bewertung bleibt vorerst außerhalb der Engine

`backtest.py`s Docstring nennt Phase-6-Nachrichtenbewertung explizit als Scope-Entscheidung dieser
ersten Engine-Implementierung. Der Workflow-Titel selbst ("...Pilot **ohne Nachrichten**") zeigt,
dass `news_enabled=false` der Haupt-Anwendungsfall ist. Lösung: der bestehende JS-Code bleibt für
`news_enabled=true`-Läufe unverändert die Berechnungsgrundlage — kein Funktionsverlust für den
selteneren Fall, siehe Routing unten.

### 1.5 `entry_grund`-Begründungstext wird generischer (akzeptiert, dokumentiert)

WF17s eigener `computeSignals()` liefert je Signal ein `evidence`-Array (z. B. `['RSI=28.4',
'Bollinger-Beruehrung']`), das zu `entry_grund` in `simulation_recommendations` zusammengesetzt
wird (UI-Anzeige). Die Engine (`trading_engine/signals.py::calculate_signals()`/`Signal`-Modell)
hat kein äquivalentes Feld — würde ohne Anpassung zu leerem/fehlendem `entry_grund` führen.
**Entscheidung (Nutzer, 2026-08-20):** kein Engine-Umbau für dieses reine Anzeige-Feld. Der neue
Node baut stattdessen einen generischen Ersatztext (`"<strategy> Signal (Engine), raw_score=X.XX"`
+ `" [gekappt: <clamp_reason>]"` falls gekappt). Funktional unverändert (beeinflusst keine
Berechnung), nur die Detailtiefe der UI-Begründung sinkt für Engine-generierte Empfehlungen.

### 1.4 Downstream-Vertrag bleibt unverändert

Der Folge-Node "Baue SQL fuer Paket-Ergebnisse" baut SQL rein aus der Feldstruktur, die "Verarbeite
Tage-Paket" zurückgibt (`orderUpdates`, `newOrderRows`, `newTradeRows`, `tradeUpdates`,
`openTradeUpdates`, `newRecRows`, `recCloseUpdates`, `positionRows`, `portfolioRows`,
`stepCompletions`, `lastDay`). Dieser Node wird **nicht verändert** — der neue Pfad muss exakt
dieselbe Struktur liefern. `errorRows` wird im Live-Code deklariert, aber nie befüllt/zurückgegeben
(toter Code) — wird nicht nachgebildet.

---

## 2. Architektur: neuer Node parallel zum alten, zweifach geroutet

Kein Ersatz des bestehenden Node-Inhalts:

```
DB: Historische Nachrichten laden
        |
   IF: Engine-Pfad nutzen?
     (pipeline_config.TRADING_ENGINE_STEP_ENABLED = true UND runCtx.news_enabled = false)
     /                                      \
   TRUE                                    FALSE
    |                                        |
Verarbeite Tage-Paket (Engine)      Verarbeite Tage-Paket   [unveraendert, bestehender Node]
   [NEU]                                     |
    \                                       /
        Baue SQL fuer Paket-Ergebnisse   [unveraendert]
```

- **Zwei unabhängige Gates**: das `pipeline_config`-Flag erlaubt sofortiges Zurückschalten ohne
  Redeploy (ein UPDATE-Statement); `news_enabled` verhindert automatisch, dass ein News-Lauf durch
  den Pfad ohne Nachrichtenunterstützung läuft. Beide bewusst redundant.
- Alter Node bleibt unverändert bestehen — nicht nur als totes Referenzmaterial, sondern als
  lebender Fallback für `news_enabled=true`-Läufe.
- Neuer `pipeline_config`-Key `TRADING_ENGINE_STEP_ENABLED` (Default `FALSE`, `sql/070`).

### Neuer Node "Verarbeite Tage-Paket (Engine)"

Gleiche Vorbereitung wie heute (unverändert übernommen): `runCtx`/`pktCtx`/`fensterCtx` laden,
`priceRows`→`barsByTicker`, `instrumentMetaRows`→`tickerToSektor`/`tickerToRegion`,
`openTradesRaw`/`pendingOrdersRaw`/`lastPortfolioRows` einlesen, `cfg`-Objekt bauen.

Unterschied: statt der eingebetteten `computeSignals`/`sizePosition`/`checkExit`-Funktionen läuft
pro Tag in `steps` (sortiert wie heute) ein `await this.helpers.httpRequest(...)`-Aufruf gegen
`http://172.16.1.14:8099/engine/simulation/step` (etabliertes Muster für Code-Node-interne
HTTP-Aufrufe in diesem Repo, siehe Workflow 03 "News Ingestion"). Payload pro Tag: `as_of`,
`next_trading_day` (via bestehende `nextWeekday()`-Hilfsfunktion, 1:1 übernommen — Kalenderlogik ist
laut Architekturdokument bewusst kein Engine-Rechenschritt), `tickers_today`, `bars_today`,
`bars_history` (je Ticker volle Historie bis `as_of`, wie `barsUpTo()` heute), `pending_orders`,
`open_trades`, `cash`, `previous_peak_equity`, `risk_cfg`, `fee_model` (`kind="mini_future"` + die
drei `miniFuture*`-Werte + `fee_bps`/`slippage_bps`, siehe 1.1), `rule_version` =
`"historische-simulation-v1"`, `ticker_sektor`/`ticker_region`/`ticker_currency` (Währung neu:
aus `instrumentMetaRows` ableiten falls vorhanden, sonst Default `"EUR"`, analog zur bestehenden
Region-Ableitung), `sizing_mode="clamp"`, `strategy_filter=runCtx.strategy_filter`,
`is_stress_regime=false`, `correlation_data=null`.

Nach jedem Tages-Aufruf: `DayStepResult` in die bekannten Row-Arrays übersetzen (mechanisches
Feld-Mapping, z. B. `exited_trades[].trade`+`.exit_result`+`.pnl` → eine `tradeUpdates`-Zeile).
**Wichtig**: `still_open_trades` ist der VOLLSTÄNDIGE Zustand für den nächsten Tages-Aufruf — NICHT
zusätzlich mit `new_trades` vereinigen (siehe `DayStepResult`-Docstring; das war im eigenen
Test-Harness beim Bau des Golden Run bereits ein echter, gefundener Bug). `still_pending_orders`
entsprechend für `pending_orders`; `cash`/`portfolio` für den nächsten `cash`/`previous_peak_equity`.

Bei HTTP-Fehler: Ausnahme werfen lassen, kein stilles Sonderverhalten — n8ns übliches
Retry-/On-Error-Verhalten greift wie bei jedem anderen Node in diesem Workflow.

---

## 3. Reihenfolge

1. ✅ Engine-Fix (1.1) + Tests — erledigt.
2. ✅ Dieses Dokument.
3. ✅ SQL-Migration `sql/070`: `TRADING_ENGINE_STEP_ENABLED` in `pipeline_config`, Default `FALSE` — live.
4. ✅ Neuer Node "Verarbeite Tage-Paket (Engine)" + "IF: Engine-Pfad nutzen?" + "DB: Engine-Flag
   laden" in Workflow 17 gebaut und per API deployt (Backup: `n8n_live_backup/
   17_Historische_Simulation_PRE_PHASE8_ENGINENODE_*.json`). Flag ist `FALSE` — Produktivbetrieb
   unverändert, nach dem Deploy per Live-Execution (57178, 2026-08-20 15:00 UTC) bestätigt. Alter
   Node + "Baue SQL fuer Paket-Ergebnisse" unangetastet. Zusätzlich bei der Umsetzung gefunden und
   mitgefixt: `theoretical_quantity`/`theoretical_risk_amount`/`clamp_reason` fehlten auf
   `Order`/`Trade`/`SizingResult` (Engine gab den Kappungs-Audit-Trail nicht nach außen) — ergänzt,
   eigener Test, siehe Commit. Offene DB-IDs (Order-PK) und Entry-Zone-Grenzen für gefüllte Trades
   werden lokal im neuen Node ticker-schlüsselig mitgeführt (kein Engine-Feld dafür, gehört nicht
   in die Domäne der Engine). Entry-Fee/-Slippage für `orderUpdates`/`newTradeRows` werden lokal
   nach derselben stabilen Mini-Future-Halb-Spread-Formel berechnet, die die Engine intern nutzt
   (DayStepResult gibt sie nicht einzeln zurück, nur über die Cash-Gesamtbilanz).
   **Wichtig für Schritt 5**: der Server (`/opt/trading-data-service`) hat die neuen
   Order/Trade/SizingResult-Felder noch NICHT — braucht vor dem Vergleichslauf ein manuelles
   Update (siehe Ende dieses Dokuments).
5. **Verifikation — KRITISCHEN BUG GEFUNDEN, Flag wieder `FALSE`.** Testlauf `test22` (id 11) lief
   noch über den alten Pfad (Flag `FALSE`, bestätigt per `entry_grund`-Format). Danach Flag auf
   `TRUE` gesetzt, zweiter Testlauf `test23` (id 12, `mean_reversion`, 2026-01-01 bis 2026-01-10)
   lief über den neuen Engine-Pfad (bestätigt: `entry_grund` = "mean_reversion Signal (Engine)
   [gekappt: SINGLE_POSITION_LIMIT]"). **Ergebnis zeigte 0 gefüllte Trades, aber +23,94% "Rendite"**
   — eindeutig falsch. Root Cause gefunden und gefixt (siehe Commit `a6d9868`): `step()`s
   Kandidaten-Schleife zählte neu erzeugte, noch NICHT gefüllte Order-Kandidaten fälschlich in die
   Tages-Equity/`positions_value` mit (fehlende Trennung zwischen "für nachfolgende Kandidaten
   desselben Tages als Risiko mitzählen" [richtig] und "in die Tages-Equity eingehen" [falsch] —
   WF17s eigener Live-Code filtert dafür explizit `_pending_only`-Einträge heraus, das fehlte in
   der Engine-Übersetzung). **Flag umgehend auf `FALSE` zurückgesetzt**, sobald der Fund bestätigt
   war. `simulation_metrics` für Lauf 12 wurde NICHT bereinigt (nur ein Testlauf-Report, keine
   Auswirkung auf Paper-Trading/echte Entscheidungen). Golden-Run-Referenzwerte aktualisiert (die
   alten waren durch denselben Bug verfälscht: `max_drawdown_pct` 52.37%→21.93% korrekt,
   `total_return_pct` +17.60%→-21.93% korrekt — Trade-Anzahl/PnL pro Trade blieben unverändert,
   der Bug betraf ausschließlich die Tages-Equity-Momentaufnahme).
   **Server aktualisiert, zweiter Vergleichslauf sauber:** `test24` (alter Pfad) vs. `test25`
   (Engine-Pfad, id 14), identischer Zeitraum 2026-01-01 bis 2026-01-10. Beide: 11 Empfehlungen,
   0,00% Rendite, 0 "Phantom-Equity"-Tage (`positions_value > 0 AND open_positions_count = 0`,
   der Sanity-Check für genau diese Bug-Klasse) — `entry_grund`-Format bestätigt je Lauf eindeutig
   den genutzten Pfad. **Schritt 5 damit erfolgreich abgeschlossen.**
6. ✅ Flag steht auf `TRUE` (Stand 2026-08-20 Abend) — Engine-Pfad ist für alle aktiven
   `news_enabled=false`-Läufe live. Rollback jederzeit über `UPDATE trading.pipeline_config SET
   value_bool=FALSE WHERE config_key='TRADING_ENGINE_STEP_ENABLED'` (wirkt ab dem nächsten Tick).
   Empfehlung: einige Tage/mehrere reale Läufe beobachten, insbesondere den Phantom-Equity-Sanity-
   Check gelegentlich wiederholen, bevor der alte Node als endgültig abgeloest betrachtet wird.
7. **Separat, später**: Workflow 14 migrieren — bringt eigene, echte fachliche Änderungen mit
   (Umstellung auf Mini-Future-Kostenmodell, erstmals Trailing-Stop für Live-Paper-Trading, siehe
   `TRADING_ENGINE_ARCHITECTURE.md` Architekturfragen 2+3), nicht Teil dieser Migration.

## Vor dem naechsten Vergleichslauf noetig: erneutes Server-Update

`/opt/trading-data-service` laeuft noch mit dem Engine-Stand von vor der Audit-Feld-Erweiterung
(1.1/Schritt 4). Fuer den Vergleichslauf muss der Nutzer manuell aktualisieren (kein SSH-Zugriff
fuer Claude, siehe [[finanz-trading-data-service-infra]]):
1. `~/Documents/finanz/trading_engine/` (kanonisch, bereits synchron mit `~/Downloads/trading_engine/`)
   auf den Server nach `/opt/trading-data-service/trading_engine/` hochladen (ersetzt den kompletten Ordner).
2. `systemctl restart trading-data-service`.
3. Kurzer Sanity-Check: `POST /engine/simulation/step` mit einem minimalen Testpaket aufrufen und
   pruefen, dass die Antwort `theoretical_quantity`/`clamp_reason` auf `new_orders`/`new_trades` enthaelt.

## Nicht in dieser Runde

- Korrelationsdaten/Stress-Regime-Erkennung für WF17 (macht `check_portfolio_limits()` bereits
  möglich, WF17 hat heute aber keine Datenquelle dafür).
- Währungs-Ableitung über einen simplen `"EUR"`-Default hinaus.
- Workflow-14-Migration, News-Unterstützung in der Engine selbst.

## Rollback

`TRADING_ENGINE_STEP_ENABLED=FALSE` schaltet sofort auf den alten Pfad zurück, ohne Redeploy. Der
alte Node bleibt unverändert im Workflow erhalten. `n8n_live_backup/` hält zusätzlich den
Workflow-Stand vor jeder strukturellen Änderung fest.

---

# 7. Workflow 14 — Live-Paper-Trading (2026-09-02)

Anders als Workflow 17 lässt sich Workflow 14 **nicht** 1:1 nach demselben Muster migrieren:
WF17 lässt die Engine selbst Handelssignale aus Kursdaten erzeugen
(`POST /engine/simulation/step`), WF14 Job A bekommt dagegen fertige, von Workflow 06 bereits
generierte Empfehlungen **ohne Kursdaten** und braucht nur Portfolio-Prüfung+Sizing; Job B führt
bereits vollständig spezifizierte Orders/Trades gegen den heutigen Tages-Bar aus, ohne selbst
Signale zu erzeugen. `/simulation/step`s Request-Schema erzwingt `bars_history` und ruft immer
`calculate_signals()` intern auf — es gibt kein Feld, um einen fertigen Kandidaten einzuschleusen.

**Deshalb zwei neue, schlankere Endpunkte** (`~/Downloads/trading_engine_router.py`):
- `POST /engine/portfolio/check-and-size` (Job A) — ein Aufruf pro Kandidat (Job A prüft
  sequenziell, jede Freigabe fließt sofort in die nächste Prüfung ein). Wrappt
  `size_position()` + `check_portfolio_limits()`.
- `POST /engine/execution/process-trades` (Job B) — ein Batch-Aufruf für alle Trades des Tages.
  Wrappt die neuen `execution.py`-Bausteine `fill_order()`/`process_open_trade()` (Phase 0,
  aus `backtest.py::step()` extrahiert, damit WF14 dieselbe Fill-/Exit-/Trailing-Stop-Logik
  bekommt wie WF17, ohne eine dritte, unabhängig driftende Implementierung).

## Drei bewusste Verhaltensänderungen (Nutzerentscheidungen 2026-09-02)

1. **Kappen statt Verwerfen** (`sizing_mode="clamp"`, wie WF17). Job A prüfte bisher nur
   Portfolio-Exposition gegen WF06s bereits fertig gesizte Werte (`empf.theoretical_quantity`/
   `risk_amount`/`position_value`) und verwarf den ganzen Kandidaten bei Limitüberschreitung.
   Jetzt reduziert die Engine die Größe auf das gerade noch zulässige Maß — der Trade entsteht
   trotzdem, nur kleiner. Weich werden dadurch: `TOTAL_RISK_LIMIT`/`SECTOR_LIMIT`/
   `REGION_LIMIT`/`SINGLE_POSITION_LIMIT`. Hart bleiben (unverändert Vetos, nicht kappbar):
   `MAX_OPEN_POSITIONS`/`DIRECTIONAL_LIMIT`/`DRAWDOWN_LIMIT`/`CORRELATION_LIMIT`/
   `CURRENCY_LIMIT`. **Vierte, bisher unbemerkte Änderung**: `size_position()`s Clamp-Pfad hat
   zusätzlich 5 harte Vetos, die Job A vorher nie kannte (`STOP_WRONG_SIDE`/
   `STOP_TARGET_INVALID`/`QUANTITY_TOO_SMALL`/`UNECONOMICAL_AFTER_COSTS`/`RRR_TOO_LOW`) — ob
   diese in der Praxis Kandidaten betreffen, die WF06 nicht schon selbst ausschließt, muss der
   Dry-Run-Vergleich zeigen (WF06s eigener Code wurde in dieser Session nicht gelesen).
2. **Mini-Future-Kostenmodell statt Gebühren-Basispunkte** (Job B). `fee_bps`/`slippage_bps`
   bleiben trotzdem im `FeeModel` gesetzt (aus `DEFAULT_FEES_BPS`/`DEFAULT_SLIPPAGE_BPS`,
   dieselben Config-Keys wie bisher) — nur für den `UNECONOMICAL_AFTER_COSTS`-Veto, der sie
   unabhängig von `kind` liest (siehe Abschnitt 1.1 oben, dieselbe Kompatibilitätslogik wie WF17).
3. **Trailing-Stop, erstmals für Live-Paper-Trading** (Job B). `paper_trades` hatte bisher keine
   Trailing-Stop-Felder — `sql/079` ergänzt `extreme_price_since_entry`/`trail_distance`
   (analog `simulation_trades`, sql/059/060), inkl. einmaligem Backfill für damals offene Trades
   (betraf 0 Zeilen — aktuell existiert keine einzige offene/vorgeschlagene Position, siehe
   [[finanz-human-in-the-loop-phase4-closed-2026-09-01]]). Gilt nur für
   `trend_following`/`breakout` (`execution.py::_TRAILING_STRATEGIES`), `mean_reversion`
   bewusst ausgenommen. `sql/080` ergänzt zusätzlich `theoretical_risk_amount`/`clamp_reason`
   auf `paper_trades` (Sizing-Audit-Trail für Änderung 1, analog sql/060 für WF17).

## Neuer Schreibpfad in Dispatcher B: `trailing_stop_update`

Für eine offene, nicht ausgestoppte Position gab es im alten Pfad **keinen** Grund,
`stop_price_current` neu zu schreiben (der Stop änderte sich dort nie intraday) — entsprechend
gab es dafür auch keinen `_typ`. Der Trailing-Stop braucht das jetzt jeden Tag, auch wenn sich
nichts bewegt hat. Neuer, rein additiver `_typ` in `SQL bauen (Dispatcher B)`, wird vom alten
Job B nie erzeugt. `fill_cluster` bekam zusätzlich `extreme_price_since_entry`/`trail_distance`
in seiner UPDATE-Klausel — für den alten Pfad bleiben diese Felder `undefined` → `NULL`, kein
Verhaltensunterschied.

## Bekannte, noch nicht geschlossene Lücke: `thesis_expired` für bereits offene Trades

Der alte Job B prüft für eine **bereits offene** Position zusätzlich zu Stop/Ziel/Zeitstop auch
`thesis_expires_at` (eigener Exit-Grund `thesis_expired`). `execution.py::evaluate_exit()` kennt
nur `time_stop_at`, keinen separaten `thesis_expires_at`-Check für offene Trades (nur für noch
nicht gefüllte `proposed`-Orders, dort clientseitig in n8n unverändert nachgebildet). Eine
bereits offene Position mit abgelaufener These würde über den Engine-Pfad also **nicht** mehr
automatisch geschlossen, bis eines der anderen Kriterien greift. Bewusst nicht "schnell gefixt"
in dieser Session (ein clientseitiger Vorab-Check hätte die Priorität stop/target vor
thesis_expired verletzt, wenn er naiv vor dem Engine-Aufruf eingebaut wird) — als offener Punkt
dokumentiert, der Dry-Run-Vergleich sollte gezielt einen Trade mit bald ablaufender
`thesis_expires_at` beobachten.

## n8n-seitig vs. Engine-seitig (Zusammenfassung)

Bleibt in n8n, unverändert: `STRATEGY_DEACTIVATED`-Vorfilter (Job A, kein Engine-Äquivalent),
alle DB-Loads, `DRY_RUN`-Guard, Dead-Letter-Eskalation (`MAX_PORTFOLIO_CHECK_ATTEMPTS`),
`data_error`-Retry-Zustandsmaschine (Job B), `session_incomplete`-Filterung,
`thesis_expires_at`-Ablauf für **unfilled** Orders, MFE/MAE- und Gap/Execution-Quality-
Audit-Felder, komplette Dispatcher-A/B-SQL-Logik (bis auf die additiven Erweiterungen oben).
Job C ("Stressszenarien berechnen") ist bestätigt unabhängig von Job A/B (andere Inputs, andere
Zieltabelle `trading.stress_scenarios`, von keinem der beiden gelesen) und bewusst außerhalb des
Scopes dieser Migration.

## Rollout-Status (Stand 2026-09-02)

- ✅ Phase 0 (Python-Refactor `fill_order()`/`process_open_trade()`) + Unit-Tests — fertig,
  94/94 Tests grün (82 bestehend + 12 neu), Golden Run unverändert.
- ✅ Phase 1 (zwei neue Endpunkte) — fertig, lokal funktional verifiziert (Sektor-Kappung +
  Trailing-Stop-Felder korrekt gesetzt).
- ✅ `sql/078` (zwei Flags, Default FALSE), `sql/079` (Trailing-Stop-Spalten + Backfill),
  `sql/080` (Sizing-Audit-Spalten) — live ausgeführt via WF97, verifiziert.
- ✅ Phase 2 (n8n-Verdrahtung, dual-gated wie WF17) — live deployed, **dormant** (beide Flags
  `FALSE`), Struktur per frischem GET verifiziert, alter Pfad byte-identisch unverändert.
- ✅ Server-Update — Nutzer hat hochgeladen+neugestartet, per echtem HTTP-Aufruf gegen
  `172.16.1.14:8099` verifiziert: `/engine/portfolio/check-and-size` liefert `clamped:true,
  reason:"SECTOR_LIMIT", approved:true` fürs Sektor-Limit-Beispiel; `/engine/execution/
  process-trades` liefert einen gefüllten Trade mit gesetztem `trail_distance`/
  `extreme_price_since_entry` fürs Fill-Beispiel — beide Stichproben aus Abschnitt "Server-
  Deployment" bestanden gegen den echten Server, nicht nur lokal.
- ⬜ Phase 3 (Dry-Run-Vergleich je Flag, dann kurzer schreibender Vergleichslauf, dann
  dauerhaft TRUE) — noch nicht begonnen. WF14 kann (anders als WF17) keinen Tag zweimal
  nachstellen — Vergleichsmethode: alten Pfad einmal regulär laufen lassen, Ergebnis notieren,
  dann Flag TRUE + `DRY_RUN` erzwungen für denselben Tag, Ergebnisse manuell gegenlesen,
  insbesondere ob die Engine-`theoretical_quantity` bei nicht gekappten Kandidaten mit WF06s
  gespeichertem Wert übereinstimmt (Sanity-Check gegen den `entry_price_estimate`-Ankerpunkt,
  Mittelpunkt der Entry-Zone — offene Designentscheidung, noch nicht gegen WF06s eigene Formel
  verifiziert).
- ⬜ Nächster natürlicher Trigger: `Trigger: Portfolio+Paper-Trading (18:15 Werktage)` — die
  erste echte Ausführung nach diesem Deploy bestätigt den unveränderten Altpfad "in freier
  Wildbahn" (Flags stehen auf FALSE, keine Aktion nötig, nur beobachten).
