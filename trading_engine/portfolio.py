"""PnL- und Portfolio-Equity-Berechnung (Phase 2 aus TRADING_ENGINE_ARCHITECTURE.md).

calculate_trade_pnl() vereinheitlicht WF14s Pro-Trade-PnL (kein fortlaufendes Cash-Konto) und
WF17s cash-Bilanz-Modell. Die Engine soll laut Phase-1-Tabelle "PnL (realized)" langfristig
WF17s Cash-Ledger-Modell als Standard uebernehmen (liefert WF14 nebenbei eine echte,
tagesaktuelle total_equity/Drawdown-Kurve statt der heutigen, nur aus geschlossenen Trades
rekonstruierten Naeherung).

PRAEZISIERUNG zum P17-1-Fund (in dieser Session bereits im n8n-Live-Code von WF17 gefixt, siehe
FINAL_REVIEW.md/CHANGELOG_REVIEW_FIXES.md): Der Bug (`cash += exitNotional` unabhaengig von der
Handelsrichtung) steckte NICHT in der grossPnl/netPnl-Formel (die war fuer Long/Short bereits
korrekt) - siehe echter Live-Code: `grossPnl` ist bereits richtungsabhaengig symmetrisch. Der Bug
betraf ausschliesslich die CASH-Fortschreibung beim Trade-Exit:
`cash += direction=='long' ? exitNotional : (2*position_value - exitNotional) - fees`.

OFFENE LUECKE: Keine der 8 in Phase 2 benannten Funktionen besitzt diese Cash-Fortschreibung als
klare Verantwortung - calculate_trade_pnl() liefert nur die PnL-Aufschluesselung ohne Cash-Bezug,
calculate_portfolio_equity() bekommt cash nur als fertigen Input. Vor der vollstaendigen
Implementierung klaeren, ob eine neue Funktion (z.B. apply_trade_exit_to_cash()) noetig ist oder
diese Logik bewusst in backtest.step() verbleibt.

calculate_portfolio_equity() loest WF17s tuegliche Mark-to-Market-Equity-Berechnung ab
(positions_value ueber ALLE offenen Positionen inkl. Short + cash = total_equity, mit laufendem
peak_equity/drawdown_pct) - laut Phase-1-Tabelle "Portfolio Equity" fachlich vollstaendiger als
WF14s heutige, nur aus realisiertem PnL rekonstruierte Drawdown-Metrik (ignoriert unrealisiertes
PnL offener Positionen).
"""

from __future__ import annotations

from datetime import date

from .models import Bar, ExecutionResult, FeeModel, Position, PortfolioState, Trade, TradePnl


def calculate_trade_pnl(
    trade: Trade,
    exit_result: ExecutionResult,
    fee_model: FeeModel,
    exit_date: date,
) -> TradePnl:
    """1:1 aus dem Exit-Zweig von "Verarbeite Tage-Paket" (WF17, mini_future) und "Job B:
    Ausfuehrung/Exit simulieren" (WF14, fee_bps) uebersetzt.

    exit_date ist keine Phase-2-Signatur-Vorgabe, sondern eine notwendige Ergaenzung: das
    mini_future-Finanzierungskosten-Modell braucht die Haltedauer (trade.entry_day bis exit_date),
    die in keinem der beiden Modelle (Trade, ExecutionResult) sonst verfuegbar ist.
    """
    is_long = trade.direction == "long"
    exit_price = exit_result.price
    position_value = trade.entry_price * trade.quantity
    exit_notional = exit_price * trade.quantity
    gross_pnl = (
        (exit_price - trade.entry_price) * trade.quantity
        if is_long
        else (trade.entry_price - exit_price) * trade.quantity
    )

    if fee_model.kind == "fee_bps":
        fee_bps = fee_model.fee_bps or 0.0
        slippage_bps = fee_model.slippage_bps or 0.0
        entry_fee = position_value * (fee_bps / 10000)
        exit_fee = exit_notional * (fee_bps / 10000)
        entry_slippage = position_value * (slippage_bps / 10000)
        exit_slippage = exit_notional * (slippage_bps / 10000)
        # Konstant 0, konsistent mit dem heutigen WF14-Live-Code (kein Broker/Produkt mit
        # definiertem Finanzierungssatz simuliert, siehe docs/AUSFUEHRUNGSMODELL.md).
        financing_cost = 0.0
    elif fee_model.kind == "mini_future":
        spread_pct = fee_model.mini_future_spread_pct or 0.0
        financing_pct_pa = fee_model.mini_future_financing_pct_pa or 0.0
        holding_days = max(1, (exit_date - trade.entry_day).days)
        entry_fee = position_value * (spread_pct / 100 / 2)
        exit_fee = exit_notional * (spread_pct / 100 / 2)
        entry_slippage = 0.0
        exit_slippage = 0.0
        financing_cost = position_value * (financing_pct_pa / 100) * (holding_days / 365)
    else:
        raise ValueError(f"unbekanntes fee_model.kind: {fee_model.kind!r}")

    net_pnl = gross_pnl - entry_fee - entry_slippage - exit_fee - exit_slippage - financing_cost

    return TradePnl(
        gross_pnl=gross_pnl,
        entry_fee=entry_fee,
        entry_slippage=entry_slippage,
        exit_fee=exit_fee,
        exit_slippage=exit_slippage,
        financing_cost=financing_cost,
        net_pnl=net_pnl,
    )


def calculate_portfolio_equity(
    cash: float,
    open_positions: list[Position],
    bars_today: dict[str, Bar],
    previous_peak_equity: float,
) -> PortfolioState:
    """1:1 aus dem Tages-Portfolio-Zeile-Block von "Verarbeite Tage-Paket" (WF17) uebersetzt.

    previous_peak_equity ist keine Phase-2-Signatur-Vorgabe, sondern eine notwendige Ergaenzung:
    peak_equity ist ein ueber die GESAMTE Simulation laufendes Maximum (`if (totalEquity >
    peakEquity) peakEquity = totalEquity` im Live-Code) - ohne den bisherigen Spitzenwert als
    Input kann drawdown_pct nicht korrekt berechnet werden. Der Aufrufer (backtest.step()) ist
    dafuer verantwortlich, den zurueckgegebenen peak_equity-Wert an den naechsten Aufruf
    weiterzureichen.

    Fehlt fuer einen Ticker die heutige Kerze (Datenluecke), faellt der Markwert auf den zuletzt
    bekannten position_value zurueck - identisch zum Live-Code (`if (!bar) return sum +
    p.position_value`).
    """
    positions_value = 0.0
    for position in open_positions:
        bar = bars_today.get(position.ticker)
        if bar is None:
            positions_value += position.position_value
            continue
        entry_price_per_share = position.position_value / position.quantity
        if position.direction == "long":
            mark_value = bar.close * position.quantity
        else:
            mark_value = (2 * entry_price_per_share - bar.close) * position.quantity
        positions_value += mark_value

    total_equity = cash + positions_value
    peak_equity = max(previous_peak_equity, total_equity)
    drawdown_pct = (peak_equity - total_equity) / peak_equity * 100 if peak_equity > 0 else 0.0

    return PortfolioState(
        cash=cash,
        positions_value=positions_value,
        total_equity=total_equity,
        peak_equity=peak_equity,
        drawdown_pct=drawdown_pct,
        open_positions=open_positions,
    )
