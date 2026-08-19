# TRADING_ENGINE_ARCHITECTURE.md

Stand: 2026-08-19. Technisches Konzept vor jeder Umsetzung — entstanden aus einer vollständigen
Code-Analyse von Workflow 14 ("Portfolio-Risiko und Paper-Trading") und Workflow 17 ("Historische
Simulation"), plus Workflow 02 ("Technische Signale täglich", da dort — nicht in 14 — die live
verwendeten technischen Signale berechnet werden) und dem bestehenden `app.py`-FastAPI-Dienst.

**Wichtiger Hinweis zur Methodik:** Alle Aussagen unten basieren auf dem tatsächlichen, frisch von
n8n geladenen Code (`Job A`/`Job B`/`Job C` aus Workflow 14, `Verarbeite Tage-Paket` aus Workflow 17,
`Technische Analyse (RSI/MACD/BB)` aus Workflow 02), nicht auf den vorhandenen `docs/*.md`-Dateien
allein — diese wurden zur Einordnung gelesen, aber jede Formel gegen den Live-Code verifiziert. Noch
**nichts wurde verändert** — dies ist ausschließlich Analyse und Konzept (Phase 1+2 des Auftrags).

---

# Phase 1 — Vergleichstabelle: Workflow 14 vs. Workflow 17

| FUNKTION | Workflow 14 | Workflow 17 | identische Logik? | fachliche Unterschiede | zentralisierbar? |
|---|---|---|---|---|---|
| **Technische Signale** | Berechnet NICHT selbst — liest vorberechnete Signale aus `trading.strategy_signals` (Job B, `DB: Strategiesignale heute laden (Exec)`), geschrieben von **Workflow 02** (`Technische Analyse (RSI/MACD/BB)`, 1153 Zeilen). | Eigene, unabhängige Neuimplementierung in `computeSignals()` (in "Verarbeite Tage-Paket" eingebettet). | Mathematisch sehr ähnlich (RSI+Bollinger+EMA20 für Mean-Reversion, MACD+EMA20 für Trend, 52W+Volumen für Breakout — gleiche ATR-Multiplikatoren 1.0/1.5, 1.5/2.5, 1.0/3.0), aber **zwei unabhängig gepflegte Implementierungen**. WF02 hat feingranularere, gestaffelte RSI-Scoring-Schwellen (25/32/38/62/68/75) für `raw_score`; WF17 nur binär (32/68). Ein Fix in WF02 (z. B. die "Härtung Welle 1-3 Phase 9"-Korrektur, die ein reines UND aus RSI-Extrem UND Preisüberdehnung erzwingt) muss man **manuell** auch in WF17 nachziehen — Drift-Risiko real, nicht nur theoretisch. | **Ja, höchste Priorität.** Dies ist eigentlich ein **Drei-Wege-Problem** (02, 14 via 02, 17), keine reine 14-vs-17-Frage. |
| **Positionsgrößen** | Berechnet NICHT in 14 selbst — kommt fertig aus Workflow 06 (`theoretical_quantity`/`risk_amount`/`position_value`, feste Formel aus `docs/RISIKOMODELL_EINZELTRADE.md`). Job A prüft nur noch, verändert die Größe nicht. | `sizePosition()` berechnet UND **kappt** die Größe auf das jeweils schärfste Limit (Risiko/Einzelposition/Gesamtrisiko/Sektor/Region). | **Architektonisch verschieden, bewusst laut Code-Kommentar** ("Positionsgroesse: KAPPEN statt VERWERFEN, Nutzervorgabe 2026-08-03"). WF06/14 verwerfen bei Limitüberschreitung den ganzen Trade (`blocked`); WF17 reduziert die Stückzahl und öffnet trotzdem. Das ist eine **echte Strategieentscheidung**, kein Bug — muss aber in der Zielarchitektur EINMAL bewusst entschieden werden (siehe offene Fragen unten). | Ja, aber nur nach einer expliziten Entscheidung: Soll Live künftig auch kappen, oder Backtest künftig auch verwerfen? |
| **Risikolimits (Portfolio)** | Job A: **9 Limits vollständig** — `MAX_TOTAL_OPEN_RISK_PCT` (inkl. `STRESS_RISK_REDUCTION_FACTOR`-Halbierung im Stress-Regime), `MAX_SECTOR_EXPOSURE_PCT`, `MAX_SINGLE_POSITION_PCT`, `MAX_OPEN_POSITIONS`, `MAX_DIRECTIONAL_EXPOSURE_PCT`, `MAX_PORTFOLIO_DRAWDOWN_PCT` (peak/equity-Wanderung über realisierte `net_pnl`, sperrt ALLE neuen Eröffnungen), `MAX_PAIRWISE_CORRELATION` (Pearson auf 60-Tage-Renditen), `MAX_REGION_EXPOSURE_PCT`, `MAX_NON_EUR_EXPOSURE_PCT`. | `checkHardLimits()`/`sizePosition()`: **nur 5 von 9** — `TOTAL_RISK_LIMIT`, `SECTOR_LIMIT`, `SINGLE_POSITION_LIMIT`, `REGION_LIMIT`, `MAX_OPEN_POSITIONS`, `DIRECTIONAL_LIMIT`. | **Neu gefundene, konkrete Lücke:** WF17 hat **keine** Drawdown-Sperre, **keine** Korrelationsprüfung, **keine** Fremdwährungsgrenze, **keine** Stress-Regime-Risikoreduktion. Ein Backtest kann dadurch Trades zeigen, die im Live-Paper-Trading am selben Tag geblockt worden wären — die Backtest-Ergebnisse sind in Phasen mit Stress-Regime, hoher Korrelation oder bereits hohem Drawdown **systematisch zu optimistisch**. Erklärt auch, warum die Config-Sweep aus der letzten Runde diese 4 Keys nur "geladen von: 14" zeigte — kein Bug, sondern echte Funktionslücke in 17. | **Ja, hohe Priorität.** Größter fachlicher Hebel der ganzen Zentralisierung. |
| **Entry/Fill** | `zone_touch_conservative`: Berührung der Zone (`low<=zoneHigh && high>=zoneLow`), Fill-Preis nach 3 Fällen (Open in Zone→Open; Gap unter Zone→Zonenrand; Open über Zone, zurückgelaufen→ungünstigster Zonenrand, `ambiguous=true`). Kein Fill am Signaltag (`decision_time::date < CURRENT_DATE`). | `simulateEntryFill()`: **identische** 3-Fälle-Logik, gleiche Bedingungen. | **Ja, praktisch identisch** — einer der wenigen Bereiche mit echter 1:1-Übereinstimmung. Kleiner Unterschied: WF17 markiert bereits den Gap-unter-Zone-Fall als `ambiguous=true`; WF14 nur den dritten Fall (WF17s Kommentar/Doku-Abgleich lohnt sich, aber kein fachlicher Fehler — beide sind vertretbare Lesarten von "mehrdeutig"). | Ja, einfach — nahezu direkt übertragbar. |
| **Stop/Target-Berührung** | `low<=stop`/`high>=target` (Long, gespiegelt Short), Exit-Preis = exakter Stop-/Zielwert. | `checkExit()`: identische Berührungslogik. | Ja, identisch. | Ja, einfach. |
| **Gap-Handling (Stop)** | `stopRawExitPrice()`: Long `Open<Stop?Open:Stop`, Short `Open>Stop?Open:Stop` (Härtung Welle 1-3, Phase 5). Ziel bleibt IMMER exakt der Zielkurs. | `checkExit()` hat **dieselbe** Gap-Logik bereits eingebaut (`gapped = isLong ? bar.open < trade.stop_price : bar.open > trade.stop_price`), inkl. `gapThroughStop`-Flag. | **Ja, praktisch identisch** — korrigiert eine ursprüngliche Annahme aus einer früheren Analyse-Runde. | Ja, einfach. |
| **Ambiguous-Bar (Stop+Ziel gleiche Kerze)** | `AMBIGUOUS_BAR_POLICY` aus Config (`conservative_stop_first`/`conservative_target_first`), Default stop-first. | `checkExit()` unterstützt beide Policies über `ambiguousBarPolicyCode` (`!== 2` → stop-first) — **gleiche Semantik**. | Ja, identisch. | Ja, einfach. |
| **Trailing Stop** | **Existiert nicht.** `stop_price_current` wird bei Fill einmal gesetzt und danach nie mehr verändert — kein Trailing-Mechanismus im gesamten Job-B-Code. | Voller Trailing-Stop (`extreme_price`/`trail_distance`, nach dem in dieser Session behobenen Look-Ahead-Fix erst ab der Folgekerze wirksam), inkl. harter 10%-Stop-Deckelung bei Einstieg. | **Neu gefundene, echte Feature-Lücke in Live-Paper-Trading**, nicht nur Code-Duplikation: Workflow 14 hat schlicht **keinen** Trailing-Stop. Falls das gewollt ist (bewusste Design-Entscheidung), sollte das dokumentiert werden; falls nicht, ist die Zentralisierung die Gelegenheit, Live-Trading den Trailing-Stop erstmals zu geben. | Ja — aber die Zentralisierung bedeutet hier eine echte **neue Fähigkeit** für 14, nicht nur Aufräumen. |
| **Same-Bar Fill+Exit** | Explizit behandelt: `filledThisBar && exitReason` → `ambiguous=true` + `exit_reasons_all` bekommt `same_bar_fill_and_exit`. | Technisch passiert dasselbe (Order-Fill in Schritt 1, Exit-Prüfung in Schritt 3 derselben Tagesschleife erfasst auch heute gefüllte Positionen) — **aber es wird nirgends als `ambiguous`/Grund vermerkt.** | **Neu gefundene Lücke:** `fill.ambiguous` und `exitCheck.ambiguous`/`gapThroughStop` werden in WF17 zwar berechnet, aber beim Schreiben von `newTradeRows`/`tradeUpdates` **nirgends persistiert** — anders als in 14, wo `ambiguous_execution`, `gap_through_stop`, `gap_amount`, `execution_quality`, `exit_reasons_all` als Audit-Felder gespeichert werden. Der Backtest verliert dadurch genau die Transparenz, die das System an anderer Stelle bewusst als Prinzip verfolgt ("Grundregel 9"). | Ja — bei Zentralisierung automatisch mitbehoben. |
| **Gebühren** | `fee(value) = value * (DEFAULT_FEES_BPS/10000)`, separat bei Entry und Exit aus `trading.pipeline_config`. | Kein `DEFAULT_FEES_BPS`-Gebrauch — stattdessen `MINI_FUTURE_SPREAD_PCT` (hälftig bei Einstieg, hälftig bei Ausstieg). | **Bewusst unterschiedliches Produktmodell**, nicht identische Fachlichkeit: 14 simuliert (implizit) einen einfachen Aktien-/CFD-Handel mit Gebühren-Basispunkten; 17 simuliert explizit ein **Mini-Future/Hebelprodukt** mit Spread + Finanzierung. Beide sind im jeweiligen Kontext dokumentiert korrekt (14: `docs/AUSFUEHRUNGSMODELL.md`, Hebelprodukt-Disclaimer "kein konkretes Produkt"; 17: eigenes Mini-Future-Kostenmodell). | Nur zentralisierbar, wenn die Engine BEIDE Kostenmodelle als austauschbare Strategie unterstützt (`fee_model: 'fee_bps' \| 'mini_future_spread'`) — keine 1:1-Fusion möglich, ohne eines der beiden Modelle fachlich zu ändern. |
| **Slippage** | `slippage(value) = value * (DEFAULT_SLIPPAGE_BPS/10000)`, separat bei Entry/Exit. | Bei Entry: `slippage = 0` (Kommentar: "Mini-Future-Kostenmodell... keine Finanzierung [bei Einstieg]"); bei Exit: keine separate Slippage-Variable, im `exitSpreadFee` enthalten. | Unterschiedlich modelliert, konsistent mit der obigen Gebühren-Divergenz (unterschiedliches Produkt). | Gleiches Bild wie Gebühren — an das gewählte Kostenmodell gekoppelt. |
| **Finanzierungskosten** | Formel implementiert, aber **konstant 0** (kein Broker/Produkt mit definiertem Satz simuliert — bewusst laut `docs/AUSFUEHRUNGSMODELL.md`). | Echt berechnet: `financingCost = position_value * (miniFutureFinancingPctPa/100) * (holdingDays/365)`, ungleich 0. | Bewusst unterschiedlich (14 hat noch keinen konkreten Finanzierungssatz definiert, 17 schon). | Nach Wahl eines gemeinsamen Kostenmodells trivial übertragbar. |
| **PnL (realized)** | `net_pnl = grossPnl - entryFee - entrySlippage - exitFee - exitSlippage - financingCost`, PRO TRADE, kein fortlaufendes Cash-Konto. | `netPnl = grossPnl - entrySpreadFee - exitSpreadFee - financingCost`, ZUSÄTZLICH eine fortlaufende `cash`-Bilanz über den gesamten Lauf (inkl. der in dieser Session gefixten Short-Cash-Formel). | **Architektonisch verschieden:** 14 hat kein Portfolio-Cash-Ledger — jeder Trade steht für sich, `total_equity` eines Tages wird an keiner Stelle in 14 direkt fortgeschrieben (nur der Drawdown wird aus der Sequenz geschlossener Trades rekonstruiert). 17 führt ein echtes Cash-Konto (nötig für die tägliche Equity-Kurve eines Backtests). | Die Engine sollte das **Cash-Ledger-Modell aus 17 als Standard übernehmen** und 14 darauf umstellen (liefert 14 nebenbei eine echte, tagesaktuelle `total_equity`/Drawdown-Kurve statt nur einer aus geschlossenen Trades rekonstruierten Näherung). |
| **MFE / MAE** | `mfe_today`/`mae_today` pro Kerze berechnet und gespeichert (`favorable = high-entry`/`entry-low` bzw. gespiegelt), vermutlich außerhalb dieses Codes zu `maximum_favorable_excursion`/`maximum_adverse_excursion` aggregiert (`GREATEST()` in der SQL-Schicht). | **Nicht vorhanden.** Kein MFE/MAE-Tracking im gesamten "Verarbeite Tage-Paket"-Code. | **Neu gefundene, echte Lücke in 17.** Ein Backtest kann aktuell nicht beurteilen, wie nah ein verlorener Trade am Ziel war oder wie tief ein gewonnener Trade zwischenzeitlich im Minus war — relevant für spätere Strategiebewertung/Lernagenten. | Ja — bei Zentralisierung sollte MFE/MAE für beide Pfade einheitlich ergänzt werden. |
| **Exposure (Sektor/Region/Richtung)** | In Job A vollständig geprüft (siehe Risikolimits-Zeile). | In `sizePosition()`/`checkHardLimits()` teilweise geprüft (Sektor/Region/Richtung ja, Korrelation/Währung nein). | Siehe Risikolimits-Zeile — dieselbe Lücke. | Ja, gemeinsam mit den Risikolimits. |
| **Portfolio Equity** | **Keine fortlaufende Equity-Kurve.** Nur `aktuellerDrawdownPct`/`maxDrawdownPct` aus der Sequenz geschlossener Trades (realisiertes PnL), **ignoriert unrealisiertes PnL offener Positionen**. | Echte tägliche Equity-Kurve: `positionsValue` (Mark-to-Market ALLER offenen Positionen, inkl. korrektem Short-Markwert) + `cash` = `totalEquity`, mit laufendem `peakEquity`/`drawdownPct` — **berücksichtigt auch unrealisiertes PnL.** | **17 ist hier fachlich vollständiger als 14.** 14s Drawdown-Metrik kann den tatsächlichen aktuellen Risikograd unterschätzen, wenn offene Positionen bereits deutlich im Minus stehen, aber noch nicht geschlossen wurden. | Ja — 14 sollte bei Zentralisierung die vollständigere Equity-Berechnung aus 17 übernehmen (echter, kein nur kosmetischer Fachlichkeitsgewinn für Live-Trading). |

## Zusammenfassung Phase 1

Von 15 geprüften Funktionsbereichen sind **6 praktisch identisch** (Entry-Fill, Stop/Target-Berührung,
Gap-Handling, Ambiguous-Bar-Policy — die "Ausführungsmechanik" ist bereits weitgehend deckungsgleich,
nur doppelt implementiert), **2 bewusst unterschiedliche Produktmodelle** (Gebühren/Slippage/
Finanzierung — Mini-Future in 17 vs. einfaches Kostenmodell in 14), und **7 echte fachliche Lücken**
in die eine oder andere Richtung (4 fehlende Risikolimits in 17, kein Trailing-Stop in 14, kein
MFE/MAE in 17, keine vollständige Equity-Kurve in 14, keine Persistierung der same-bar/Gap-Ambiguität
in 17). Die Zentralisierung ist damit nicht nur Code-Hygiene — sie würde mehrere **echte,
bisher unbekannte fachliche Inkonsistenzen** zwischen Live und Backtest schließen.

---

# Phase 2 — Engine-Konzept

## Modulstruktur (angepasst an das bestehende Repository)

Das Repository (`~/Documents/finanz`) enthält aktuell nur n8n-Workflow-JSON, SQL-Migrationen und
JS-Tests (`tests/*.js`, reine Funktionstests gegen aus den Workflows kopierte Logik-Ausschnitte — kein
eigenständiges Python/Backend-Verzeichnis). Der FastAPI-Dienst (`app.py`) lebt **außerhalb** dieses
Repos (`~/Downloads/app.py`, separat per systemd auf dem n8n-Host deployt). Für die neue Engine wird
deshalb ein neues Unterverzeichnis im `finanz`-Repo vorgeschlagen, das vom FastAPI-Dienst als lokales
Package importiert wird (kein PyPI-Paket, kein zweites Deployment):

```
finanz/
  trading_engine/
    __init__.py
    models.py          # Bar, Signal, Order, Trade, Position, PortfolioState, ExecutionResult,
                        # RiskConfig, StrategyConfig, SimulationConfig, ConfigSnapshot (Pydantic)
    signals.py          # calculate_signals() — löst WF02 UND WF17s computeSignals() ab
    position_sizing.py  # size_position() — mit explizitem sizing_mode: 'clamp' | 'reject'
    risk_limits.py       # check_portfolio_limits() — alle 9 Limits + Region/Währung/Korrelation/Stress
    execution.py         # simulate_entry(), evaluate_exit(), update_trailing_stop()
    portfolio.py          # calculate_trade_pnl(), calculate_portfolio_equity(), MFE/MAE
    config.py              # ConfigSnapshot-Auflösung aus trading.pipeline_config-Zeilen
    backtest.py             # step()-Schleife für Workflow 17 (nutzt alle obigen Module)
  tests/
    trading_engine/
      test_signals.py
      test_position_sizing.py
      test_execution.py
      test_portfolio.py
      test_golden_run.py
      fixtures/
        golden_run_config.json
        golden_run_bars.json
        golden_run_expected.json
```

Begründung für diese Aufteilung (an den tatsächlich vorgefundenen Funktionsgrenzen orientiert, nicht
an der Beispielstruktur aus dem Auftrag 1:1 übernommen):
- `risk_limits.py` als **eigenes** Modul statt in `position_sizing.py`: Phase 1 zeigt, dass Sizing
  (Kappen) und Portfolio-Limit-Prüfung (Blockieren) zwei fachlich unterschiedliche Operationen mit
  unterschiedlichem Scope sind (Einzeltrade vs. Portfolio) — WF14 trennt sie bereits in Job A
  (Prüfung) vs. WF06 (Sizing), WF17 verschmilzt sie in `sizePosition()`. Eine sauberere Engine trennt
  sie bewusst, mit `sizing_mode` als Parameter, der beide bisherigen Verhaltensweisen (kappen vs.
  verwerfen) abbildet, statt sich für eines zu entscheiden.
- `config.py` als eigenes Modul: beide Workflows lesen `trading.pipeline_config`-Zeilen in eine
  flache `{key: value}`-Map — diese Übersetzung (inkl. Default-Fallback-Logik) ist selbst schon
  dupliziert (`CFG.KEY ?? default` in 14, `num('KEY', default)` in 17) und sollte einmalig als
  `ConfigSnapshot.from_rows(rows) -> ConfigSnapshot` existieren.

## Zentrale Funktionen (Signaturen, konzeptionell — noch nicht implementiert)

```python
def calculate_signals(bars: list[Bar], rule_version: str) -> list[Signal]: ...

def size_position(
    signal: Signal, entry_price_estimate: float, risk_cfg: RiskConfig,
    open_positions: list[Position], sektor: str, region: str,
    sizing_mode: Literal["clamp", "reject"] = "clamp",
) -> SizingResult: ...

def check_portfolio_limits(
    candidate: SizingResult, portfolio: PortfolioState, risk_cfg: RiskConfig,
    correlation_data: dict[str, list[float]] | None = None,
) -> list[Blocker]: ...

def simulate_entry(order: Order, bar: Bar) -> ExecutionResult: ...

def evaluate_exit(
    trade: Trade, bar: Bar, as_of: date, ambiguous_bar_policy: AmbiguousBarPolicy,
    opposite_signal_today: bool,
) -> ExecutionResult: ...

def update_trailing_stop(position: Position, bar: Bar) -> Position: ...

def calculate_trade_pnl(trade: Trade, exit_result: ExecutionResult, fee_model: FeeModel) -> TradePnl: ...

def calculate_portfolio_equity(cash: float, open_positions: list[Position], bars_today: dict[str, Bar]) -> PortfolioState: ...
```

Alle Funktionen: **deterministisch, ohne n8n-Bezug, ohne globalen Zustand** — Input/Output explizit,
wie gefordert. Kein Funktionsaufruf liest `trading.pipeline_config` selbst; `RiskConfig`/`StrategyConfig`
werden vorher aus DB-Zeilen aufgelöst übergeben (Trennung von Datenzugriff und Berechnung — n8n bzw.
FastAPI-Endpunkt bleibt für das Laden zuständig, die Engine nur für die Mathematik).

---

# Phase 3 — Datenmodelle (Konzept)

Pydantic (bereits im Ökosystem vorhanden — `app.py` nutzt es für alle Request-Bodies, z. B.
`BatchHistoryRequest`) statt Dataclasses, für Konsistenz mit dem bestehenden FastAPI-Dienst und
kostenlose Validierung/JSON-(De-)Serialisierung an der API-Grenze.

```python
class Bar(BaseModel):
    ticker: str
    trading_date: date
    open: float
    high: float
    low: float
    close: float
    volume: float

class Signal(BaseModel):
    strategy: Literal["mean_reversion", "trend_following", "breakout", "news_event"]
    direction: Literal["long", "short", "neutral"]
    raw_score: float
    entry_zone_low: float | None
    entry_zone_high: float | None
    stop_price: float | None
    target_price: float | None
    expected_horizon_days: int
    rule_version: str

class Order(BaseModel):
    ticker: str
    direction: Literal["long", "short"]
    entry_zone_low: float
    entry_zone_high: float
    stop_price: float
    target_price: float
    quantity: int
    intended_execution_date: date

class Trade(BaseModel):
    trade_id: str
    ticker: str
    direction: Literal["long", "short"]
    entry_price: float
    stop_price_current: float
    target_price: float
    quantity: int
    extreme_price_since_entry: float
    trail_distance: float
    entry_day: date

class Position(BaseModel):
    ticker: str
    direction: Literal["long", "short"]
    quantity: int
    position_value: float
    sektor: str
    region: str

class PortfolioState(BaseModel):
    cash: float
    positions_value: float
    total_equity: float
    peak_equity: float
    drawdown_pct: float
    open_positions: list[Position]

class ExecutionResult(BaseModel):
    filled: bool = False
    exit: bool = False
    price: float | None = None
    reason: str | None = None
    ambiguous: bool = False
    gap_through_stop: bool = False

class RiskConfig(BaseModel):
    model_portfolio_value: float
    max_risk_per_trade_pct: float
    max_total_open_risk_pct: float
    max_sector_exposure_pct: float
    max_single_position_pct: float
    max_open_positions: int
    max_directional_exposure_pct: float
    max_portfolio_drawdown_pct: float
    max_pairwise_correlation: float
    max_region_exposure_pct: float
    max_non_eur_exposure_pct: float
    stress_risk_reduction_factor: float

class StrategyConfig(BaseModel):
    atr_stop_multiplier: float
    atr_target_multiplier: float
    expected_horizon_days: int
    rule_version: str

class FeeModel(BaseModel):
    kind: Literal["fee_bps", "mini_future"]
    fee_bps: float | None = None
    slippage_bps: float | None = None
    mini_future_leverage: float | None = None
    mini_future_spread_pct: float | None = None
    mini_future_financing_pct_pa: float | None = None

class SimulationConfig(BaseModel):
    run_id: str
    initial_capital: float
    strategy_filter: str | None
    ambiguous_bar_policy: Literal["conservative_stop_first", "conservative_target_first"]
    fee_model: FeeModel

class ConfigSnapshot(BaseModel):
    values: dict[str, float]
    loaded_at: datetime

    @classmethod
    def from_rows(cls, rows: list[dict]) -> "ConfigSnapshot": ...
    def get(self, key: str, default: float) -> float: ...
```

---

# Phase 4 — Eine Engine für Paper und Backtest

**Zentrales Prinzip bestätigt und konkretisiert:** Die einzige zulässige Quelle des Unterschieds ist
die Datenquelle (heutige vs. historische Point-in-Time-Kerzen) — nicht die Berechnungslogik. Phase 1
zeigt aber, dass dieses Prinzip HEUTE bereits an drei Stellen verletzt wird, nicht nur durch doppelten
Code:

1. **Unterschiedliches Kostenmodell** (Mini-Future in 17 vs. einfache Basispunkte in 14) — das ist
   KEIN Datenquellen-Unterschied, sondern ein Produktmodell-Unterschied. Lösung: `FeeModel` als
   expliziter Parameter der `SimulationConfig`, den beide Aufrufer (14 und 17) setzen — 14 mit
   `kind='fee_bps'` (heutiges Verhalten unverändert), 17 mit `kind='mini_future'`. Falls gewünscht,
   könnte 14 künftig ebenfalls auf `mini_future` umgestellt werden — das wäre aber eine bewusste
   fachliche Entscheidung, keine Nebenwirkung der Zentralisierung.
2. **Unterschiedlicher Sizing-Modus** (kappen vs. verwerfen) — Lösung: `sizing_mode`-Parameter wie
   oben beschrieben.
3. **Fehlende Risikolimits/Trailing-Stop/MFE-MAE in einer der beiden Seiten** — das sind keine
   bewussten Unterschiede, sondern Lücken. Nach der Migration verschwinden sie automatisch, weil
   beide Aufrufer dieselbe vollständige Funktion nutzen.

---

# Phase 5 — FastAPI-Erweiterung

**Empfehlung: den bestehenden Dienst erweitern, keinen zweiten Microservice bauen** (Auftragsvorgabe
ohnehin, und fachlich sinnvoll — `app.py` läuft bereits als systemd-Dienst auf demselben Host wie n8n,
dieselbe Netzwerk-Erreichbarkeit, kein neues Deployment-/Monitoring-Ziel).

`app.py` ist heute ausschließlich ein Marktdaten-Wrapper um `yfinance` (57 Endpunkte, alle
`/api/v1/{history,quote,fundamentals,...}`) — keine Trading-Logik. Die neuen Endpunkte werden bewusst
als **eigenes Router-Modul** ergänzt (`trading_engine_router.py`, per `app.include_router(...)`
eingebunden), damit Marktdaten-Code und Trading-Engine-Code im selben Prozess, aber nicht in
derselben Datei/demselben Verantwortungsbereich vermischt werden.

**Endpunkt-Entscheidung: ein gebündelter Endpoint statt vier Einzel-Endpunkten**, begründet aus der
n8n-Aufrufstruktur: Sowohl Job B (Workflow 14) als auch "Verarbeite Tage-Paket" (Workflow 17) rufen
heute in EINEM Code-Node-Durchlauf hintereinander mehrere Engine-Funktionen für denselben Tag/dieselbe
Order-Menge auf (Signal → Sizing → Fill → Exit → Portfolio-Equity). Vier separate HTTP-Aufrufe pro
Ticker pro Tag würden bei WF17s Paketgröße (20 Tage × bis zu 30 Ticker) zu hunderten HTTP-Roundtrips
pro Worker-Tick führen — unnötiger Overhead für einen internen, nicht enterprise-tauglichen Dienst.

```
POST /engine/simulation/step
```
Nimmt ein Tages-Paket (Bars, offene Positionen, ausstehende Orders, Config-Snapshot) entgegen und
liefert die vollständige Tagesverarbeitung zurück (neue Orders, Fills, Exits, aktualisierte Positionen,
Tages-Portfolio-Zeile) — im Wesentlichen ein 1:1-Ersatz für den heutigen Inhalt von "Verarbeite
Tage-Paket" bzw. Job A+B in 14, aber als eine reine, getestete Funktion statt eingebettetem n8n-Code.
n8n bleibt zuständig für: Pakete laden, den Endpunkt aufrufen, das Ergebnis persistieren, Status
verwalten (siehe Phase 9).

---

# Architekturfragen — Entscheidungsstand (2026-08-19)

Drei Entscheidungen wurden dem Nutzer vorgelegt, da sie echte fachliche Konsequenzen haben (siehe
Phase-1-Tabelle):

1. **Sizing-Modus (kappen wie 17 vs. verwerfen wie 14/06):** ⏸️ **Noch NICHT entschieden — bewusst
   zurückgestellt.** Nutzer-Antwort: "genau hier machen wir später weiter" — das ist der exakte
   Wiedereinstiegspunkt für die nächste Sitzung, bevor mit `position_sizing.py`/`risk_limits.py`
   begonnen wird.
2. **Kostenmodell:** ✅ **Entschieden — Workflow 14 wird auf das Mini-Future-Kostenmodell aus 17
   umgestellt.** Das ist eine bewusste, echte fachliche Verhaltensänderung für Live-Paper-Trading
   (Spread+Finanzierung statt einfacher Gebühren-Basispunkte) — kein reines Code-Aufräumen. Bei der
   Umsetzung (Phase 8, Migration von 14) muss das explizit als Verhaltensänderung im
   `TRADING_ENGINE_MIGRATION.md` dokumentiert werden, nicht stillschweigend nebenbei passieren.
3. **Trailing-Stop für 14:** ✅ **Entschieden — wird ergänzt.** Live-Paper-Trading bekommt bei der
   Migration erstmals einen Trailing-Stop (echte neue Fähigkeit). Muss ebenfalls explizit als neue
   Funktionalität dokumentiert werden, nicht als "Bugfix" o. ä. kaschiert.

Damit ist EIN Parameter (`sizing_mode`) weiterhin offen, die anderen beiden sind für die Zielarchitektur
festgelegt: `FeeModel` wird langfristig für BEIDE Aufrufer auf `mini_future` stehen (keine dauerhafte
Parallelität wie ursprünglich als Option vorgeschlagen), Trailing-Stop wird Teil der gemeinsamen
`execution.py`/`update_trailing_stop()`-Funktion für beide Aufrufer.

---

# Status und nächster Schritt

Dies ist **ausschließlich Phase 1 (Analyse, abgeschlossen) und Phase 2/3/4/5-Konzept
(abgeschlossen)** — noch kein einziger Workflow, keine Datei außer diesem Dokument wurde verändert.

**Nutzer-Entscheidung (2026-08-19): Implementierung startet in einer separaten Sitzung ("wir starten
damit morgen"), nicht in dieser.** Wiedereinstiegspunkt für die nächste Sitzung:

1. Zuerst die offene Sizing-Modus-Frage klären (kappen vs. verwerfen vs. konfigurierbar) — laut
   Nutzer-Antwort ausdrücklich der Punkt, an dem weitergemacht wird.
2. Danach Phase 3 (Datenmodelle als Pydantic-Klassen, siehe Entwurf oben) tatsächlich implementieren.
3. Phase 6 (Unit-Tests) von Anfang an parallel zu jeder neuen Funktion, nicht nachträglich.
4. Phase 7 (Golden Run) vor jeder Migrationsentscheidung.
5. Migration in der im Auftrag vorgegebenen Reihenfolge (erst 17, dann erst nach Vergleichstests 14) —
   angesichts des Umfangs nicht in einem einzigen Durchgang, sondern mit Zwischenständen je
   Migrationsschritt.
