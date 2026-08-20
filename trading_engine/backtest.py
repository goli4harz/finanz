"""Tages-Paket-Verarbeitung fuer Workflow 17 (Phase 2 aus TRADING_ENGINE_ARCHITECTURE.md).

step() ersetzt den Kontrollfluss von "Verarbeite Tage-Paket" (WF17) fuer EINEN Simulationstag,
zusammengesetzt aus den bereits getesteten Bausteinen dieses Packages: pending Orders fuellen
(execution.simulate_entry) -> Exits pruefen (execution.evaluate_exit, MIT dem alten Stop-Stand,
siehe P17-6-Invariant) -> Trailing-Stop nachziehen NUR fuer ueberlebende Positionen
(execution.update_trailing_stop) -> PnL/Cash bei Exit (portfolio.calculate_trade_pnl, P17-1-fix
beachten) -> neue Kandidaten pruefen (signals.calculate_signals -> position_sizing.size_position
-> risk_limits.check_portfolio_limits) -> Tages-Equity (portfolio.calculate_portfolio_equity).

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

from .execution import evaluate_exit, simulate_entry, update_trailing_stop
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
        fill = simulate_entry(order, bar)
        if not fill.filled:
            continue  # not_filled_price - siehe Modul-Docstring: keine Persistenz-Zeile hier
        hard_stop_price = fill.price * 0.9 if order.direction == "long" else fill.price * 1.1
        capped_stop_price = max(order.stop_price, hard_stop_price) if order.direction == "long" else min(order.stop_price, hard_stop_price)
        position_value = fill.price * order.quantity
        entry_fee = position_value * (fee_model.mini_future_spread_pct or 0.0) / 100 / 2 if fee_model.kind == "mini_future" else position_value * (fee_model.fee_bps or 0.0) / 10000
        cash -= (position_value + entry_fee)
        trade = Trade(
            trade_id=f"trd-{order.ticker}-{as_of.isoformat()}", ticker=order.ticker, direction=order.direction,
            entry_price=fill.price, stop_price_current=capped_stop_price, target_price=order.target_price,
            quantity=order.quantity, extreme_price_since_entry=fill.price, trail_distance=abs(fill.price - capped_stop_price),
            entry_day=as_of, time_stop_at=order.time_stop_at, strategy=order.strategy, sektor=order.sektor,
            region=order.region, risk_amount=order.risk_amount,
            theoretical_quantity=order.theoretical_quantity, theoretical_risk_amount=order.theoretical_risk_amount,
            clamp_reason=order.clamp_reason,
        )
        new_trades.append(trade)
        open_positions_view.append(_trade_to_position(trade, ticker_currency.get(order.ticker, "EUR")))
    pending_orders_result = still_pending

    # --- 2. Signale fuer heute berechnen (neue Kandidaten + opposite_signal-Exit-Check) ---
    signals_today = {ticker: calculate_signals(bars_history.get(ticker, []), rule_version) for ticker in tickers_today}

    # --- 3. Exits fuer offene Trades pruefen (inkl. heute frisch gefuellte) ---
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
        exit_result = evaluate_exit(trade, bar, as_of, "conservative_stop_first", opposite_signal_today)
        if not exit_result.exit:
            trade = update_trailing_stop(trade, bar)
            still_open.append(trade)
            open_ticker_set.add(trade.ticker)
            continue
        pnl = _calculate_trade_pnl(trade, exit_result, fee_model, as_of)
        exit_notional = exit_result.price * trade.quantity
        # P17-1-Fix (siehe portfolio.py-Docstring): Short-Cash-Zufluss ist Margin+grossPnl,
        # NICHT die reine Exit-Notional. Formel entspricht 2*entry_value - exit_notional.
        exit_cash_inflow = exit_notional if trade.direction == "long" else (2 * trade.entry_price * trade.quantity - exit_notional)
        cash += exit_cash_inflow - pnl.exit_fee - pnl.exit_slippage - pnl.financing_cost
        exited.append(ExitedTrade(trade=trade, exit_result=exit_result, pnl=pnl))
    open_trades_result = still_open

    open_positions_view = [_trade_to_position(t, ticker_currency.get(t.ticker, "EUR")) for t in open_trades_result]

    # --- 4. Neue Kandidaten pruefen ---
    new_orders: list[Order] = []
    for ticker in tickers_today:
        if ticker in open_ticker_set or any(o.ticker == ticker for o in pending_orders_result):
            continue
        candidate_signals = list(signals_today.get(ticker, []))
        if strategy_filter:
            candidate_signals = [s for s in candidate_signals if s.strategy == strategy_filter]
        if not candidate_signals:
            continue
        best = max(candidate_signals, key=lambda s: s.raw_score)
        if best.direction == "neutral" or best.entry_zone_low is None or best.entry_zone_high is None or best.stop_price is None or best.target_price is None:
            continue
        bar = bars_today[ticker]
        sektor = ticker_sektor.get(ticker, "unbekannt")
        region = ticker_region.get(ticker, "global")
        sizing = size_position(best, bar.close, risk_cfg, open_positions_view, sektor, region, sizing_mode, fee_model)
        if sizing.blocked:
            continue
        portfolio_for_check = PortfolioState(cash=cash, positions_value=0, total_equity=0, peak_equity=0, drawdown_pct=0, open_positions=open_positions_view)
        blockers = check_portfolio_limits(sizing, ticker, sektor, region, ticker_currency.get(ticker, "EUR"), best.direction, portfolio_for_check, risk_cfg, is_stress_regime, correlation_data)
        if blockers:
            continue
        order = Order(
            ticker=ticker, direction=best.direction, entry_zone_low=best.entry_zone_low, entry_zone_high=best.entry_zone_high,
            stop_price=best.stop_price, target_price=best.target_price, quantity=sizing.quantity,
            intended_execution_date=next_trading_day, strategy=best.strategy, sektor=sektor, region=region,
            risk_amount=sizing.risk_amount, time_stop_at=as_of + timedelta(days=best.expected_horizon_days),
            theoretical_quantity=sizing.theoretical_quantity, theoretical_risk_amount=sizing.theoretical_risk_amount,
            clamp_reason=sizing.reason if sizing.clamped else None,
        )
        new_orders.append(order)
        open_positions_view.append(Position(ticker=ticker, direction=best.direction, quantity=sizing.quantity, position_value=sizing.position_value, sektor=sektor, region=region, currency=ticker_currency.get(ticker, "EUR"), risk_amount=sizing.risk_amount))

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


def _calculate_trade_pnl(trade: Trade, exit_result: ExecutionResult, fee_model: FeeModel, exit_date: date) -> TradePnl:
    from .portfolio import calculate_trade_pnl
    return calculate_trade_pnl(trade, exit_result, fee_model, exit_date)


def _calculate_portfolio_equity(cash: float, open_positions: list[Position], bars_today: dict[str, Bar], previous_peak_equity: float) -> PortfolioState:
    from .portfolio import calculate_portfolio_equity
    return calculate_portfolio_equity(cash, open_positions, bars_today, previous_peak_equity)
