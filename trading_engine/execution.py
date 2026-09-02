"""Fill-/Exit-/Trailing-Stop-Ausfuehrung (Phase 2 aus TRADING_ENGINE_ARCHITECTURE.md).

simulate_entry() loest die praktisch identische Zone-Touch-Logik aus WF14
(zone_touch_conservative) und WF17 (simulateEntryFill()) ab - einer der wenigen Bereiche mit
echter 1:1-Uebereinstimmung, siehe Phase-1-Tabelle "Entry/Fill".

evaluate_exit() loest WF14s Stop/Target-Beruehrung + Gap-Handling (stopRawExitPrice(), Haertung
Welle 1-3 Phase 5) und WF17s checkExit() ab (bereits identische Semantik: gapThroughStop-Flag,
ambiguousBarPolicyCode).

WICHTIGER INVARIANT (P17-6, in dieser Session bereits im n8n-Live-Code von WF17 gefixt, siehe
FINAL_REVIEW.md): Ein aus der heutigen Kerze neu berechneter Trailing Stop darf NICHT rueckwirkend
fuer dieselbe Kerze gelten (Look-Ahead-Bias). evaluate_exit() MUSS mit dem Stop-Stand VOR der
heutigen update_trailing_stop()-Nachfuehrung aufgerufen werden; die Nachfuehrung wirkt sich erst
auf die naechste Kerze aus. Aufrufreihenfolge pro Tag: 1) evaluate_exit() mit altem Stop,
2) NUR falls kein Exit -> update_trailing_stop() (im echten WF17-Code steht die Nachfuehrung
explizit in einem `if (!exitCheck.exit)`-Zweig - eine bereits exitende Position bekommt keinen
neuen Trailing-Stop mehr).

Korrektur der in der vorigen Session dokumentierten Inkonsistenz: update_trailing_stop() ist hier
jetzt Trade -> Trade signiert (nicht Position -> Position wie im urspruenglichen Phase-2-Entwurf),
weil die Trailing-Stop-Felder (stop_price_current/extreme_price_since_entry/trail_distance) laut
Phase 3 auf Trade modelliert sind, nicht auf Position.
"""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel

from .models import AmbiguousBarPolicy, Bar, ExecutionResult, FeeModel, Order, Trade, TradePnl


def simulate_entry(order: Order, bar: Bar) -> ExecutionResult:
    """1:1 aus simulateEntryFill() im Live-Code von WF17 ("Verarbeite Tage-Paket") uebersetzt.
    Praktisch identisch zu WF14s zone_touch_conservative (siehe Phase-1-Tabelle "Entry/Fill")."""
    touched = bar.low <= order.entry_zone_high and bar.high >= order.entry_zone_low
    if not touched:
        return ExecutionResult(filled=False)
    if order.entry_zone_low <= bar.open <= order.entry_zone_high:
        return ExecutionResult(filled=True, price=bar.open, ambiguous=False)
    if bar.open < order.entry_zone_low:
        return ExecutionResult(filled=True, price=order.entry_zone_low, ambiguous=True)
    return ExecutionResult(filled=True, price=order.entry_zone_high, ambiguous=True)


def evaluate_exit(
    trade: Trade,
    bar: Bar,
    as_of: date,
    ambiguous_bar_policy: AmbiguousBarPolicy,
    opposite_signal_today: bool,
) -> ExecutionResult:
    """1:1 aus checkExit() im Live-Code von WF17 ("Verarbeite Tage-Paket") uebersetzt, inkl. des
    P17-6-Fixes (siehe FINAL_REVIEW.md): der Aufrufer MUSS trade.stop_price_current VOR der
    heutigen update_trailing_stop()-Nachfuehrung uebergeben (siehe Modul-Docstring).

    Same-Bar Stop+Target (stop_touched and target_touched) wird ueber ambiguous_bar_policy
    aufgeloest: default (== "conservative_stop_first") gewinnt der Stop, nur bei explizitem
    "conservative_target_first" gewinnt das Ziel - identische Semantik zu WF14
    (AMBIGUOUS_BAR_POLICY-Config, Default stop-first) und WF17 (ambiguousBarPolicyCode !== 2).
    """
    is_long = trade.direction == "long"
    stop_touched = bar.low <= trade.stop_price_current if is_long else bar.high >= trade.stop_price_current
    target_touched = bar.high >= trade.target_price if is_long else bar.low <= trade.target_price

    def gap_through_stop() -> bool:
        return bar.open < trade.stop_price_current if is_long else bar.open > trade.stop_price_current

    if stop_touched and target_touched:
        stop_first = ambiguous_bar_policy != "conservative_target_first"
        if stop_first:
            gapped = gap_through_stop()
            price = bar.open if gapped else trade.stop_price_current
            return ExecutionResult(exit=True, price=price, reason="stop_loss", ambiguous=True, gap_through_stop=gapped)
        return ExecutionResult(exit=True, price=trade.target_price, reason="take_profit", ambiguous=True, gap_through_stop=False)

    if stop_touched:
        gapped = gap_through_stop()
        price = bar.open if gapped else trade.stop_price_current
        return ExecutionResult(exit=True, price=price, reason="stop_loss", ambiguous=False, gap_through_stop=gapped)

    if target_touched:
        return ExecutionResult(exit=True, price=trade.target_price, reason="take_profit", ambiguous=False, gap_through_stop=False)

    if trade.time_stop_at is not None and as_of >= trade.time_stop_at:
        return ExecutionResult(exit=True, price=bar.close, reason="time_stop", ambiguous=False, gap_through_stop=False)

    if opposite_signal_today:
        return ExecutionResult(exit=True, price=bar.close, reason="opposite_signal", ambiguous=False, gap_through_stop=False)

    return ExecutionResult(exit=False)


# FIX 2026-08-28 (#1, parallel zu WF17 "Verarbeite Tage-Paket"): Strategien mit festem Kursziel
# bekommen KEINEN mitgezogenen Stop. mean_reversion zielt auf die Rueckkehr zum Mittel; ein
# im Anfangs-Bounce eng gezogener Stop wird vom normalen Ruecksetzer mitgenommen, bevor das
# Ziel greift (59% stop_loss / nur 11% take_profit ueber alle Sim-Trades). Trailing bleibt
# fuer trend_following/breakout ("Gewinner laufen lassen").
_TRAILING_STRATEGIES = {"trend_following", "breakout"}


def update_trailing_stop(trade: Trade, bar: Bar) -> Trade:
    """1:1 aus dem Trailing-Stop-Zweig von "Verarbeite Tage-Paket" (WF17) uebersetzt. Nur fuer
    Long/Short symmetrisch nachziehen, nie gegen die Trail-Distance zurueckziehen (der Vergleich
    `trail_stop > stop`/`trail_stop < stop` verhindert das). Der Aufrufer ist dafuer
    verantwortlich, diese Funktion NICHT aufzurufen, wenn evaluate_exit() fuer denselben Tag
    bereits `exit=True` zurueckgegeben hat (siehe Modul-Docstring).

    extreme_price_since_entry wird fuer ALLE Strategien mitgefuehrt (wird persistiert); der Stop
    wird aber nur fuer _TRAILING_STRATEGIES nachgezogen (siehe Kommentar oben, FIX #1)."""
    is_long = trade.direction == "long"
    extreme_price = trade.extreme_price_since_entry
    stop_price = trade.stop_price_current
    trailing_erlaubt = trade.strategy in _TRAILING_STRATEGIES

    if is_long:
        if bar.high > extreme_price:
            extreme_price = bar.high
        if trailing_erlaubt:
            trail_stop = extreme_price - trade.trail_distance
            if trail_stop > stop_price:
                stop_price = trail_stop
    else:
        if bar.low < extreme_price:
            extreme_price = bar.low
        if trailing_erlaubt:
            trail_stop = extreme_price + trade.trail_distance
            if trail_stop < stop_price:
                stop_price = trail_stop

    return trade.model_copy(update={"extreme_price_since_entry": extreme_price, "stop_price_current": stop_price})


class FillOutcome(BaseModel):
    """Rueckgabe von fill_order(). `trade`/`entry_fee`/`cash_delta` sind nur gesetzt, wenn
    `fill.filled` True ist."""

    fill: ExecutionResult
    trade: Trade | None = None
    entry_fee: float = 0.0
    cash_delta: float = 0.0


def fill_order(order: Order, bar: Bar, fee_model: FeeModel, as_of: date) -> FillOutcome:
    """Phase 0 der WF14-Migration (TRADING_ENGINE_MIGRATION.md Abschnitt 7): extrahiert 1:1 aus
    backtest.step() Schritt 1 (Zone-Touch-Fill, 10%-Hard-Stop-Cap, trail_distance-Ableitung,
    Entry-Fee, Cash-Delta) - reine Fill-Simulation fuer EINE Order an EINEM Tag, ohne Kenntnis von
    anderen Orders/Cash-Historie. Der Aufrufer (backtest.step() fuer WF17, oder ein externer
    API-Consumer wie Workflow 14 ueber /engine/portfolio/... bzw. /engine/execution/...) bleibt
    zustaendig fuer: pending-Order-Vorfilterung (intended_execution_date/fehlender Bar), das
    Fortschreiben von cash ueber mehrere Orders eines Tages hinweg, und still-pending-Buchfuehrung.

    Der 10%-Hard-Stop-Cap gilt bewusst nur HIER, beim Fill (siehe backtest.step()s Original-
    Kommentar) - nicht erneut in update_trailing_stop() auf Folgetagen."""
    fill = simulate_entry(order, bar)
    if not fill.filled:
        return FillOutcome(fill=fill)
    hard_stop_price = fill.price * 0.9 if order.direction == "long" else fill.price * 1.1
    capped_stop_price = (
        max(order.stop_price, hard_stop_price)
        if order.direction == "long"
        else min(order.stop_price, hard_stop_price)
    )
    position_value = fill.price * order.quantity
    entry_fee = (
        position_value * (fee_model.mini_future_spread_pct or 0.0) / 100 / 2
        if fee_model.kind == "mini_future"
        else position_value * (fee_model.fee_bps or 0.0) / 10000
    )
    trade = Trade(
        trade_id=f"trd-{order.ticker}-{as_of.isoformat()}", ticker=order.ticker, direction=order.direction,
        entry_price=fill.price, stop_price_current=capped_stop_price, target_price=order.target_price,
        quantity=order.quantity, extreme_price_since_entry=fill.price, trail_distance=abs(fill.price - capped_stop_price),
        entry_day=as_of, time_stop_at=order.time_stop_at, strategy=order.strategy, sektor=order.sektor,
        region=order.region, risk_amount=order.risk_amount,
        theoretical_quantity=order.theoretical_quantity, theoretical_risk_amount=order.theoretical_risk_amount,
        clamp_reason=order.clamp_reason,
    )
    return FillOutcome(fill=fill, trade=trade, entry_fee=entry_fee, cash_delta=-(position_value + entry_fee))


class TradeStepOutcome(BaseModel):
    """Rueckgabe von process_open_trade(). `pnl`/`cash_delta` sind nur gesetzt, wenn
    `exit_result.exit` True ist; `updated_trade` traegt sonst den nachgezogenen Trailing-Stop."""

    exit_result: ExecutionResult
    updated_trade: Trade
    pnl: TradePnl | None = None
    cash_delta: float | None = None


def process_open_trade(
    trade: Trade,
    bar: Bar,
    as_of: date,
    ambiguous_bar_policy: AmbiguousBarPolicy,
    opposite_signal_today: bool,
    fee_model: FeeModel,
) -> TradeStepOutcome:
    """Phase 0 der WF14-Migration (TRADING_ENGINE_MIGRATION.md Abschnitt 7): extrahiert 1:1 aus
    backtest.step() Schritt 3 den Koerper der Pro-Trade-Schleife. Erzwingt den P17-6-Invariant
    (evaluate_exit() MIT dem alten Stop-Stand VOR jeder update_trailing_stop()-Nachfuehrung, siehe
    Modul-Docstring) INNERHALB der Engine, statt jeden Aufrufer (n8n-Code fuer WF17 heute, ein
    externer API-Consumer wie Workflow 14 morgen) auf die richtige Reihenfolge zu verlassen. Der
    Aufrufer bleibt zustaendig fuer: fehlender-Bar-Handling (Feiertag fuer dieses Instrument -
    diese Funktion NICHT aufrufen, Trade unveraendert als weiter offen fuehren), das Ermitteln von
    `opposite_signal_today` aus der eigenen Signalquelle, und das Fortschreiben von cash."""
    exit_result = evaluate_exit(trade, bar, as_of, ambiguous_bar_policy, opposite_signal_today)
    if not exit_result.exit:
        updated_trade = update_trailing_stop(trade, bar)
        return TradeStepOutcome(exit_result=exit_result, updated_trade=updated_trade)
    from .portfolio import calculate_trade_pnl

    pnl = calculate_trade_pnl(trade, exit_result, fee_model, as_of)
    exit_notional = exit_result.price * trade.quantity
    # P17-1-Fix (siehe portfolio.py-Docstring): Short-Cash-Zufluss ist Margin+grossPnl, NICHT die
    # reine Exit-Notional. Formel entspricht 2*entry_value - exit_notional.
    exit_cash_inflow = (
        exit_notional if trade.direction == "long" else (2 * trade.entry_price * trade.quantity - exit_notional)
    )
    cash_delta = exit_cash_inflow - pnl.exit_fee - pnl.exit_slippage - pnl.financing_cost
    return TradeStepOutcome(exit_result=exit_result, updated_trade=trade, pnl=pnl, cash_delta=cash_delta)
