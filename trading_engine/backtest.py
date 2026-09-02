"""Tages-Paket-Verarbeitung fuer Workflow 17 (Phase 2 aus TRADING_ENGINE_ARCHITECTURE.md).

step() ersetzt den Kontrollfluss von "Verarbeite Tage-Paket" (WF17) fuer EINEN Simulationstag,
zusammengesetzt aus den bereits getesteten Bausteinen dieses Packages: pending Orders fuellen
(execution.fill_order, kapselt simulate_entry + 10%-Hard-Stop-Cap + trail_distance-Ableitung) ->
Exits/Trailing-Stop fuer offene Trades (execution.process_open_trade, kapselt evaluate_exit MIT
dem alten Stop-Stand + update_trailing_stop NUR bei Nicht-Exit + PnL/Cash, siehe P17-1/P17-6-Fixe)
-> neue Kandidaten pruefen (signals.calculate_signals -> position_sizing.size_position ->
risk_limits.check_portfolio_limits) -> Tages-Equity (portfolio.calculate_portfolio_equity).

fill_order()/process_open_trade() wurden in Phase 0 der WF14-Migration (TRADING_ENGINE_MIGRATION.md
Abschnitt 7) aus dieser Funktion nach execution.py extrahiert, damit Workflow 14 (Live-Paper-
Trading) dieselbe Fill-/Exit-/Trailing-Stop-Logik ueber eigene, schlankere Endpunkte wiederverwenden
kann, statt eine dritte, unabhaengig driftende Implementierung zu bekommen - reiner Refactor, siehe
tests/trading_engine/test_execution.py fuer die direkte Abdeckung, Golden Run bleibt unveraendert.

BEWUSST NICHT UEBERNOMMEN gegenueber dem echten WF17-Code (Scope-Entscheidungen fuer diese
erste Implementierung, nicht stillschweigend anders):
- Phase-6-Nachrichtenbewertung (evaluateNewsForTicker/WIDERSPRUECHLICHE_NEWS) - kein
  News-Datenmodell in Phase 3, bleibt ausserhalb der Engine.
- Persistenz-Zeilen fuer simulation_recommendations/simulation_positions/simulation_errors -
  reine DB-Buchhaltung, kein Engine-Rechenschritt. DayStepResult liefert die Rechenergebnisse,
  n8n bleibt fuer das Schreiben zustaendig (siehe Phase 5/9 der Architektur).
- "openRecTickers" als eigene Menge - hier aus den Tickern der offenen Trades + pending Orders
  desselben Tages abgeleitet (fachlich aequivalent: verhindert eine zweite Position/Order fuer
  denselben Ticker, ohne eine separate Recommendation-Tabelle zu modellieren).
- nextWeekday()-Kalenderlogik (Wochenend-Ueberspringen) - Kalenderfragen sind kein
  Engine-Rechenschritt, deshalb hier ein expliziter next_trading_day-Parameter statt eigener
  Datumsarithmetik.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Literal

from pydantic import BaseModel

from .execution import fill_order, process_open_trade
from .models import (
    Bar,
    ExecutionResult,
    FeeModel,
    Order,
    PortfolioState,
    Position,
    RiskConfig,
    Trade,
    TradePnl,
)
from .position_sizing import size_position


def _add_trading_days(d: date, n: int) -> date:
    """FIX 2026-08-28 (#2, parallel zu WF17 nextWeekday-Schleife): expected_horizon_days sind
    HANDELSTAGE, nicht Kalendertage. Vorher: ``as_of + timedelta(days=n)`` -> bei n=8 und
    Wochenenden blieben real ~5-6 Handelstage, viel liefen ins time_stop. Ueberspringt nur
    Sa/So (keine Feiertage - gleiche Naeherung wie der Legacy-Pfad; ein echter Handelskalender
    waere eine gemeinsame kuenftige Verbesserung fuer beide Pfade)."""
    result = d
    added = 0
    while added < n:
        result += timedelta(days=1)
        if result.weekday() < 5:
            added += 1
    return result
from .risk_limits import check_portfolio_limits
from .signals import calculate_signals


class ExitedTrade(BaseModel):
    trade: Trade
    exit_result: ExecutionResult
    pnl: TradePnl


class DayStepResult(BaseModel):
    """WICHTIGER VERTRAG (beim Bau des Golden Run als echter Bug im eigenen Test-Harness
    entdeckt, siehe TRADING_ENGINE_TEST_REPORT.md): `still_open_trades` ist die VOLLSTAENDIGE,
    fuer sich alleinstehende Zustandsliste fuer den naechsten Aufruf - sie enthaelt bereits jeden
    heute neu gefuellten Trade, der den Tag ueberlebt hat. `new_trades` ist NUR eine zusaetzliche
    Berichts-/Persistenzliste ("das wurde heute neu angelegt") und ueberschneidet sich bewusst
    mit entweder `still_open_trades` ODER `exited_trades` (je nachdem ob der Trade den Tag
    ueberlebt oder noch am selben Tag wieder ausgestoppt wurde - same-bar fill+exit). Ein Aufrufer
    MUSS `still_open_trades` allein als naechsten `open_trades`-Input verwenden -
    `still_open_trades + new_trades` verdoppelt jeden ueberlebenden neuen Trade."""

    still_pending_orders: list[Order]
    new_trades: list[Trade]
    exited_trades: list[ExitedTrade]
    still_open_trades: list[Trade]
    new_orders: list[Order]
    cash: float
    portfolio: PortfolioState


def _trade_to_position(trade: Trade, currency: str) -> Position:
    return Position(
        ticker=trade.ticker, direction=trade.direction, quantity=trade.quantity,
        position_value=trade.entry_price * trade.quantity, sektor=trade.sektor, region=trade.region,
        currency=currency, risk_amount=trade.risk_amount,
    )


def step(
    as_of: date,
    next_trading_day: date,
    tickers_today: list[str],
    bars_today: dict[str, Bar],
    bars_history: dict[str, list[Bar]],
    pending_orders: list[Order],
    open_trades: list[Trade],
    cash: float,
    previous_peak_equity: float,
    risk_cfg: RiskConfig,
    fee_model: FeeModel,
    rule_version: str,
    ticker_sektor: dict[str, str],
    ticker_region: dict[str, str],
    ticker_currency: dict[str, str],
    sizing_mode: Literal["clamp", "reject"] = "clamp",
    strategy_filter: str | None = None,
    is_stress_regime: bool = False,
    correlation_data: dict[str, list[float]] | None = None,
) -> DayStepResult:
    """bars_history muss je Ticker die komplette bisherige Kerzenhistorie BIS EINSCHLIESSLICH
    `as_of` enthalten (fuer calculate_signals() - siehe dortige Docstring-Anforderung an
    chronologisch sortierte bars)."""
    open_positions_view = [_trade_to_position(t, ticker_currency.get(t.ticker, "EUR")) for t in open_trades]

    # --- 1. Pending Orders mit faelliger Ausfuehrung pruefen ---
    # Phase 0 der WF14-Migration (TRADING_ENGINE_MIGRATION.md Abschnitt 7): die eigentliche
    # Fill-Simulation lebt jetzt in execution.fill_order(), damit Workflow 14 dieselbe Logik
    # (inkl. 10%-Hard-Stop-Cap + trail_distance-Ableitung) ueber die neuen Endpunkte wiederverwenden
    # kann, statt eine dritte, unabhaengig driftende Implementierung zu bekommen.
    still_pending: list[Order] = []
    new_trades: list[Trade] = []
    for order in pending_orders:
        if order.intended_execution_date > as_of:
            still_pending.append(order)
            continue
        bar = bars_today.get(order.ticker)
        if bar is None:
            still_pending.append(order)  # Feiertag fuer dieses Instrument
            continue
        outcome = fill_order(order, bar, fee_model, as_of)
        if not outcome.fill.filled:
            continue  # not_filled_price - siehe Modul-Docstring: keine Persistenz-Zeile hier
        cash += outcome.cash_delta
        new_trades.append(outcome.trade)
        open_positions_view.append(_trade_to_position(outcome.trade, ticker_currency.get(order.ticker, "EUR")))
    pending_orders_result = still_pending

    # --- 2. Signale fuer heute berechnen (neue Kandidaten + opposite_signal-Exit-Check) ---
    signals_today = {ticker: calculate_signals(bars_history.get(ticker, []), rule_version) for ticker in tickers_today}

    # --- 3. Exits fuer offene Trades pruefen (inkl. heute frisch gefuellte) ---
    # Phase 0 der WF14-Migration: der P17-6-Invariant (evaluate_exit() VOR update_trailing_stop())
    # und die Exit-PnL/Cash-Berechnung leben jetzt in execution.process_open_trade(), aus
    # demselben Grund wie bei fill_order() oben.
    still_open: list[Trade] = []
    exited: list[ExitedTrade] = []
    open_ticker_set: set[str] = set()
    for trade in [*open_trades, *new_trades]:
        bar = bars_today.get(trade.ticker)
        if bar is None:
            still_open.append(trade)
            open_ticker_set.add(trade.ticker)
            continue
        candidate_signals = signals_today.get(trade.ticker, [])
        opposite_signal_today = any(s.strategy == trade.strategy and s.direction != trade.direction and s.direction != "neutral" for s in candidate_signals)
        outcome = process_open_trade(trade, bar, as_of, "conservative_stop_first", opposite_signal_today, fee_model)
        if not outcome.exit_result.exit:
            still_open.append(outcome.updated_trade)
            open_ticker_set.add(trade.ticker)
            continue
        cash += outcome.cash_delta
        exited.append(ExitedTrade(trade=outcome.updated_trade, exit_result=outcome.exit_result, pnl=outcome.pnl))
    open_trades_result = still_open

    open_positions_view = [_trade_to_position(t, ticker_currency.get(t.ticker, "EUR")) for t in open_trades_result]
    # BUGFIX 2026-08-20 (gefunden beim ersten echten WF17-Vergleichslauf, Phase-8-Migration):
    # ein neu erzeugter Order-Kandidat ist NOCH NICHT gefuellt - er darf fuer NACHFOLGENDE
    # Kandidaten DESSELBEN Tages als Portfolio-Risiko mitzaehlen (deshalb die separate
    # candidate_check_positions-Arbeitskopie unten), aber NICHT in die Tages-Equity/
    # positions_value eingehen (kein Cash wurde ausgegeben, keine Position existiert). Vorher
    # wurde open_positions_view direkt mutiert und dieselbe, bereits um Kandidaten erweiterte
    # Liste an calculate_portfolio_equity() weitergereicht - das Live-System (WF17s eigener
    # JS-Code) filtert genau dafuer explizit `_pending_only`-Eintraege vor der Tages-Portfolio-
    # Zeile wieder heraus. Ohne diesen Fix wird total_equity/positions_value um den vollen
    # Positionswert JEDES neuen (auch nie gefuellten) Kandidaten aufgeblaeht - live reproduziert
    # mit einem 0-Trades-Testlauf, der trotzdem +23,9% "Rendite" zeigte.
    candidate_check_positions = list(open_positions_view)

    # --- 4. Neue Kandidaten pruefen ---
    new_orders: list[Order] = []
    for ticker in tickers_today:
        if ticker in open_ticker_set or any(o.ticker == ticker for o in pending_orders_result):
            continue
        candidate_signals = list(signals_today.get(ticker, []))
        if strategy_filter:
            candidate_signals = [s for s in candidate_signals if s.strategy == strategy_filter]
        # FIX 2026-08-28: nur handelbare Signale in die best-Auswahl. calculate_signals() gibt
        # IMMER alle 3 Strategien zurueck, auch mit direction="neutral" (anders als WF17s
        # computeSignals(), das nur gerichtete Signale in die Liste legt). Ohne diesen Filter
        # konnte ein hoch bewertetes neutrales Signal (raw_score wird richtungsunabhaengig
        # berechnet) per max() gewinnen und den ganzen Ticker verwerfen, obwohl ein niedriger
        # bewertetes, aber gueltiges gerichtetes Signal vorlag.
        candidate_signals = [
            s for s in candidate_signals
            if s.direction != "neutral" and s.entry_zone_low is not None and s.entry_zone_high is not None
            and s.stop_price is not None and s.target_price is not None
        ]
        if not candidate_signals:
            continue
        best = max(candidate_signals, key=lambda s: s.raw_score)
        bar = bars_today[ticker]
        sektor = ticker_sektor.get(ticker, "unbekannt")
        region = ticker_region.get(ticker, "global")
        sizing = size_position(best, bar.close, risk_cfg, candidate_check_positions, sektor, region, sizing_mode, fee_model)
        if sizing.blocked:
            continue
        portfolio_for_check = PortfolioState(cash=cash, positions_value=0, total_equity=0, peak_equity=0, drawdown_pct=0, open_positions=candidate_check_positions)
        blockers = check_portfolio_limits(sizing, ticker, sektor, region, ticker_currency.get(ticker, "EUR"), best.direction, portfolio_for_check, risk_cfg, is_stress_regime, correlation_data)
        if blockers:
            continue
        order = Order(
            ticker=ticker, direction=best.direction, entry_zone_low=best.entry_zone_low, entry_zone_high=best.entry_zone_high,
            stop_price=best.stop_price, target_price=best.target_price, quantity=sizing.quantity,
            intended_execution_date=next_trading_day, strategy=best.strategy, sektor=sektor, region=region,
            risk_amount=sizing.risk_amount, time_stop_at=_add_trading_days(as_of, best.expected_horizon_days),
            theoretical_quantity=sizing.theoretical_quantity, theoretical_risk_amount=sizing.theoretical_risk_amount,
            clamp_reason=sizing.reason if sizing.clamped else None,
        )
        new_orders.append(order)
        candidate_check_positions.append(Position(ticker=ticker, direction=best.direction, quantity=sizing.quantity, position_value=sizing.position_value, sektor=sektor, region=region, currency=ticker_currency.get(ticker, "EUR"), risk_amount=sizing.risk_amount))

    portfolio = _calculate_portfolio_equity(cash, open_positions_view, bars_today, previous_peak_equity)

    return DayStepResult(
        still_pending_orders=pending_orders_result,
        new_trades=new_trades,
        exited_trades=exited,
        still_open_trades=open_trades_result,
        new_orders=new_orders,
        cash=cash,
        portfolio=portfolio,
    )


def _calculate_portfolio_equity(cash: float, open_positions: list[Position], bars_today: dict[str, Bar], previous_peak_equity: float) -> PortfolioState:
    from .portfolio import calculate_portfolio_equity
    return calculate_portfolio_equity(cash, open_positions, bars_today, previous_peak_equity)
