"""Tests fuer calculate_trade_pnl() und calculate_portfolio_equity() (trading_engine/portfolio.py).

Enthaelt die vier im Audit-Brief explizit geforderten Testfaelle (Long/Short x Gewinn/Verlust,
10 Stueck zu 100, Exit 80/120) sowie Fee-Modell-Faelle (fee_bps vs. mini_future).
"""

from datetime import date

from trading_engine.models import Bar, ExecutionResult, FeeModel, Position, Trade
from trading_engine.portfolio import calculate_portfolio_equity, calculate_trade_pnl

ZERO_FEE_BPS = FeeModel(kind="fee_bps", fee_bps=0, slippage_bps=0)


def make_trade(direction, entry_price=100, quantity=10, entry_day="2026-08-01"):
    return Trade(
        trade_id="t1", ticker="TEST", direction=direction, entry_price=entry_price,
        stop_price_current=0, target_price=0, quantity=quantity,
        extreme_price_since_entry=entry_price, trail_distance=0, entry_day=entry_day,
    )


def make_exit(price):
    return ExecutionResult(exit=True, price=price, reason="take_profit")


# --- Audit-Brief-Testfaelle: reine Richtung/Vorzeichen, ohne Kosten ---

def test_long_gewinn():
    trade = make_trade("long")
    result = calculate_trade_pnl(trade, make_exit(120), ZERO_FEE_BPS, date(2026, 8, 10))
    assert result.gross_pnl == 200
    assert result.net_pnl == 200


def test_long_verlust():
    trade = make_trade("long")
    result = calculate_trade_pnl(trade, make_exit(80), ZERO_FEE_BPS, date(2026, 8, 10))
    assert result.gross_pnl == -200
    assert result.net_pnl == -200


def test_short_gewinn():
    trade = make_trade("short")
    result = calculate_trade_pnl(trade, make_exit(80), ZERO_FEE_BPS, date(2026, 8, 10))
    assert result.gross_pnl == 200
    assert result.net_pnl == 200


def test_short_verlust():
    trade = make_trade("short")
    result = calculate_trade_pnl(trade, make_exit(120), ZERO_FEE_BPS, date(2026, 8, 10))
    assert result.gross_pnl == -200
    assert result.net_pnl == -200


# --- Fee-Modelle ---

def test_fee_bps_deducted_symmetrically_long_short():
    fee_model = FeeModel(kind="fee_bps", fee_bps=15, slippage_bps=10)
    long_result = calculate_trade_pnl(make_trade("long"), make_exit(120), fee_model, date(2026, 8, 10))
    short_result = calculate_trade_pnl(make_trade("short"), make_exit(80), fee_model, date(2026, 8, 10))
    # Gleicher Positionswert (1000) und gleicher Exit-Notional (800 bzw. 1200 vertauscht durch
    # Richtung) -> Kosten muessen betragsgleich sein, nur der grosse Gewinn/Verlust unterscheidet.
    assert long_result.entry_fee == short_result.entry_fee
    assert long_result.financing_cost == 0
    assert long_result.net_pnl == long_result.gross_pnl - long_result.entry_fee - long_result.exit_fee - long_result.entry_slippage - long_result.exit_slippage


def test_mini_future_financing_cost_scales_with_holding_days():
    fee_model = FeeModel(kind="mini_future", mini_future_spread_pct=0.5, mini_future_financing_pct_pa=3.0)
    trade = make_trade("long", entry_day="2026-08-01")
    short_hold = calculate_trade_pnl(trade, make_exit(110), fee_model, date(2026, 8, 2))
    long_hold = calculate_trade_pnl(trade, make_exit(110), fee_model, date(2026, 9, 1))
    assert long_hold.financing_cost > short_hold.financing_cost
    assert long_hold.net_pnl < short_hold.net_pnl


def test_mini_future_minimum_one_holding_day():
    fee_model = FeeModel(kind="mini_future", mini_future_spread_pct=0.5, mini_future_financing_pct_pa=3.0)
    trade = make_trade("long", entry_day="2026-08-10")
    # Entry und Exit am selben Tag -> Haltedauer wird auf mindestens 1 Tag gerundet,
    # nicht auf 0 (sonst waere financing_cost=0, unrealistisch fuer einen echten Handelstag).
    result = calculate_trade_pnl(trade, make_exit(110), fee_model, date(2026, 8, 10))
    assert result.financing_cost > 0


def test_unknown_fee_model_kind_raises():
    import pytest
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        FeeModel(kind="unknown")


# --- calculate_portfolio_equity ---

def make_position(direction, ticker="TEST", entry_price=100, quantity=10, sektor="Tech", region="US"):
    return Position(
        ticker=ticker, direction=direction, quantity=quantity,
        position_value=entry_price * quantity, sektor=sektor, region=region,
    )


def make_bar(close, ticker="TEST"):
    return Bar(ticker=ticker, trading_date="2026-08-19", open=close, high=close, low=close, close=close, volume=1000)


def test_equity_long_position_marked_to_close():
    position = make_position("long", entry_price=100, quantity=10)
    bars_today = {"TEST": make_bar(close=110)}
    state = calculate_portfolio_equity(cash=1000, open_positions=[position], bars_today=bars_today, previous_peak_equity=2000)
    assert state.positions_value == 1100  # 110 * 10
    assert state.total_equity == 2100  # 1000 cash + 1100 positions


def test_equity_short_position_marked_mirrored():
    # Entry 100, aktueller Kurs 90 -> Short liegt im Plus, Markwert = (2*100 - 90) * 10 = 1100.
    position = make_position("short", entry_price=100, quantity=10)
    bars_today = {"TEST": make_bar(close=90)}
    state = calculate_portfolio_equity(cash=1000, open_positions=[position], bars_today=bars_today, previous_peak_equity=2000)
    assert state.positions_value == 1100


def test_equity_missing_bar_falls_back_to_position_value():
    position = make_position("long", entry_price=100, quantity=10)
    state = calculate_portfolio_equity(cash=1000, open_positions=[position], bars_today={}, previous_peak_equity=2000)
    assert state.positions_value == position.position_value == 1000


def test_equity_peak_updates_when_new_high():
    position = make_position("long", entry_price=100, quantity=10)
    bars_today = {"TEST": make_bar(close=150)}
    state = calculate_portfolio_equity(cash=1000, open_positions=[position], bars_today=bars_today, previous_peak_equity=2000)
    assert state.total_equity == 2500
    assert state.peak_equity == 2500
    assert state.drawdown_pct == 0


def test_equity_drawdown_when_below_previous_peak():
    position = make_position("long", entry_price=100, quantity=10)
    bars_today = {"TEST": make_bar(close=80)}
    state = calculate_portfolio_equity(cash=1000, open_positions=[position], bars_today=bars_today, previous_peak_equity=3000)
    assert state.total_equity == 1800
    assert state.peak_equity == 3000  # bleibt unveraendert, kein neues Hoch
    assert round(state.drawdown_pct, 4) == round((3000 - 1800) / 3000 * 100, 4)


def test_equity_multiple_positions_summed():
    positions = [make_position("long", ticker="A", entry_price=100, quantity=10), make_position("short", ticker="B", entry_price=50, quantity=20)]
    bars_today = {"A": make_bar(close=110, ticker="A"), "B": make_bar(close=40, ticker="B")}
    state = calculate_portfolio_equity(cash=500, open_positions=positions, bars_today=bars_today, previous_peak_equity=0)
    # A: 110*10=1100. B (short, entry 50, jetzt 40): (2*50-40)*20 = 1200.
    assert state.positions_value == 2300
    assert state.total_equity == 2800
