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
   **Nächster Schritt**: Server-Update (siehe unten, backtest.py hat sich seit dem letzten
   Server-Sync erneut geändert), dann EIN WEITERER Vergleichslauf mit dem jetzt gefixten Code,
   bevor das Flag erneut auf `TRUE` gesetzt wird.
6. Nach bestätigt sauberem Vergleichslauf: Flag auf `TRUE` setzen (`UPDATE trading.pipeline_config
   SET value_bool=TRUE WHERE config_key='TRADING_ENGINE_STEP_ENABLED'`, wirkt ab dem nächsten Tick,
   genauso einfach wieder auf `FALSE` zurückzusetzen bei Auffälligkeiten).
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
