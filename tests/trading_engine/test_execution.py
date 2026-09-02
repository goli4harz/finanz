"""Tests fuer simulate_entry(), evaluate_exit(), update_trailing_stop() sowie fill_order()/
process_open_trade() (trading_engine/execution.py).

Faelle 1:1 gegen die live geladene Referenzimplementierung in WF17 ("Verarbeite Tage-Paket",
simulateEntryFill()/checkExit()) hergeleitet - siehe execution.py-Docstrings fuer die Herkunft.

fill_order()/process_open_trade() wurden in Phase 0 der WF14-Migration (TRADING_ENGINE_MIGRATION.md
Abschnitt 7) aus backtest.py::step() extrahiert - die Tests unten decken sie direkt ab, zusaetzlich
zur bestehenden impliziten Abdeckung ueber test_backtest.py/test_golden_run.py.
"""

from datetime import date

from trading_engine.execution import (
    evaluate_exit,
    fill_order,
    process_open_trade,
    simulate_entry,
    update_trailing_stop,
)
from trading_engine.models import Bar, FeeModel, Order, Trade


def make_bar(open_, high, low, close, trading_date="2026-08-19"):
    return Bar(ticker="TEST", trading_date=trading_date, open=open_, high=high, low=low, close=close, volume=1000)


def make_order(zone_low=99, zone_high=101, direction="long"):
    return Order(
        ticker="TEST", direction=direction, entry_zone_low=zone_low, entry_zone_high=zone_high,
        stop_price=95, target_price=110, quantity=10, intended_execution_date="2026-08-19",
    )


def make_trade(direction="long", stop=95, target=110, time_stop_at=None, strategy="trend_following"):
    # Default strategy = trend_following: die Trailing-Stop-Tests pruefen die Trailing-Mechanik,
    # die seit FIX 2026-08-28 (#1) nur noch fuer trend_following/breakout gilt. evaluate_exit-
    # Tests sind strategieunabhaengig.
    return Trade(
        trade_id="t1", ticker="TEST", direction=direction, entry_price=100,
        stop_price_current=stop, target_price=target, quantity=10,
        extreme_price_since_entry=100, trail_distance=5, entry_day="2026-08-18",
        time_stop_at=time_stop_at, strategy=strategy,
    )


# --- simulate_entry ---

def test_entry_not_touched():
    order = make_order(zone_low=99, zone_high=101)
    bar = make_bar(open_=105, high=106, low=104, close=105)
    result = simulate_entry(order, bar)
    assert result.filled is False


def test_entry_open_in_zone():
    order = make_order(zone_low=99, zone_high=101)
    bar = make_bar(open_=100, high=102, low=98, close=101)
    result = simulate_entry(order, bar)
    assert result.filled is True
    assert result.price == 100
    assert result.ambiguous is False


def test_entry_gap_under_zone():
    order = make_order(zone_low=99, zone_high=101)
    bar = make_bar(open_=97, high=100, low=96, close=99)
    result = simulate_entry(order, bar)
    assert result.filled is True
    assert result.price == 99
    assert result.ambiguous is True


def test_entry_gap_over_zone_recovered():
    order = make_order(zone_low=99, zone_high=101)
    bar = make_bar(open_=103, high=104, low=99, close=100)
    result = simulate_entry(order, bar)
    assert result.filled is True
    assert result.price == 101
    assert result.ambiguous is True


# --- evaluate_exit: Stop/Target, Long/Short ---

def test_exit_long_stop_touched():
    trade = make_trade(direction="long", stop=95, target=110)
    bar = make_bar(open_=100, high=101, low=94, close=96)
    result = evaluate_exit(trade, bar, date(2026, 8, 19), "conservative_stop_first", False)
    assert result.exit is True
    assert result.reason == "stop_loss"
    assert result.price == 95
    assert result.gap_through_stop is False


def test_exit_long_target_touched():
    trade = make_trade(direction="long", stop=95, target=110)
    bar = make_bar(open_=105, high=111, low=104, close=110)
    result = evaluate_exit(trade, bar, date(2026, 8, 19), "conservative_stop_first", False)
    assert result.exit is True
    assert result.reason == "take_profit"
    assert result.price == 110


def test_exit_short_stop_touched():
    trade = make_trade(direction="short", stop=110, target=95)
    bar = make_bar(open_=105, high=111, low=104, close=109)
    result = evaluate_exit(trade, bar, date(2026, 8, 19), "conservative_stop_first", False)
    assert result.exit is True
    assert result.reason == "stop_loss"
    assert result.price == 110


def test_exit_short_target_touched():
    trade = make_trade(direction="short", stop=110, target=95)
    bar = make_bar(open_=100, high=101, low=94, close=96)
    result = evaluate_exit(trade, bar, date(2026, 8, 19), "conservative_stop_first", False)
    assert result.exit is True
    assert result.reason == "take_profit"
    assert result.price == 95


def test_exit_gap_through_stop_long():
    trade = make_trade(direction="long", stop=95, target=110)
    bar = make_bar(open_=90, high=92, low=88, close=91)
    result = evaluate_exit(trade, bar, date(2026, 8, 19), "conservative_stop_first", False)
    assert result.exit is True
    assert result.reason == "stop_loss"
    assert result.price == 90
    assert result.gap_through_stop is True


def test_exit_same_bar_stop_and_target_default_stop_first():
    trade = make_trade(direction="long", stop=95, target=110)
    bar = make_bar(open_=100, high=111, low=94, close=105)
    result = evaluate_exit(trade, bar, date(2026, 8, 19), "conservative_stop_first", False)
    assert result.exit is True
    assert result.reason == "stop_loss"
    assert result.ambiguous is True


def test_exit_same_bar_stop_and_target_policy_target_first():
    trade = make_trade(direction="long", stop=95, target=110)
    bar = make_bar(open_=100, high=111, low=94, close=105)
    result = evaluate_exit(trade, bar, date(2026, 8, 19), "conservative_target_first", False)
    assert result.exit is True
    assert result.reason == "take_profit"
    assert result.ambiguous is True


def test_exit_time_stop():
    trade = make_trade(direction="long", stop=95, target=110, time_stop_at=date(2026, 8, 19))
    bar = make_bar(open_=100, high=102, low=99, close=101)
    result = evaluate_exit(trade, bar, date(2026, 8, 19), "conservative_stop_first", False)
    assert result.exit is True
    assert result.reason == "time_stop"
    assert result.price == 101  # close


def test_exit_opposite_signal():
    trade = make_trade(direction="long", stop=95, target=110)
    bar = make_bar(open_=100, high=102, low=99, close=101)
    result = evaluate_exit(trade, bar, date(2026, 8, 19), "conservative_stop_first", True)
    assert result.exit is True
    assert result.reason == "opposite_signal"


def test_exit_no_exit():
    trade = make_trade(direction="long", stop=95, target=110)
    bar = make_bar(open_=100, high=102, low=99, close=101)
    result = evaluate_exit(trade, bar, date(2026, 8, 19), "conservative_stop_first", False)
    assert result.exit is False


# --- update_trailing_stop ---

def test_trailing_stop_ratchets_up_for_long():
    # entry_price/extreme_price_since_entry=100, trail_distance=5 (siehe make_trade)
    trade = make_trade(direction="long", stop=95)
    bar = make_bar(open_=105, high=110, low=104, close=108)
    updated = update_trailing_stop(trade, bar)
    assert updated.extreme_price_since_entry == 110
    assert updated.stop_price_current == 105  # 110 - trail_distance(5)


def test_trailing_stop_never_loosens_for_long():
    trade = make_trade(direction="long", stop=95)
    trade = update_trailing_stop(trade, make_bar(open_=105, high=110, low=104, close=108))
    assert trade.stop_price_current == 105
    # Naechster Tag mit niedrigerem High -> Stop darf NICHT zurueckgezogen werden.
    trade = update_trailing_stop(trade, make_bar(open_=106, high=107, low=103, close=104))
    assert trade.extreme_price_since_entry == 110
    assert trade.stop_price_current == 105


def test_trailing_stop_ratchets_down_for_short():
    trade = make_trade(direction="short", stop=110)
    bar = make_bar(open_=98, high=99, low=90, close=92)
    updated = update_trailing_stop(trade, bar)
    assert updated.extreme_price_since_entry == 90
    assert updated.stop_price_current == 95  # 90 + trail_distance(5)


def test_trailing_stop_disabled_for_mean_reversion():
    """FIX 2026-08-28 (#1): mean_reversion hat ein festes Kursziel - der Stop wird NICHT
    nachgezogen (sonst systematisches Ausstoppen vor dem Ziel). extreme_price wird trotzdem
    mitgefuehrt (persistiert)."""
    trade = make_trade(direction="long", stop=95, strategy="mean_reversion")
    updated = update_trailing_stop(trade, make_bar(open_=105, high=110, low=104, close=108))
    assert updated.extreme_price_since_entry == 110  # weiter mitgefuehrt
    assert updated.stop_price_current == 95          # unveraendert, kein Trailing


def test_trailing_stop_look_ahead_ordering_from_audit_brief():
    """Szenario aus dem Audit-Brief: Open 100, Low 94, High 110, Close 108, alter Stop 95.
    Korrekte Reihenfolge (evaluate_exit MIT dem alten Stop, siehe P17-6-Invariant in
    execution.py): die Position wird zum exakten alten Stop (95) ausgestoppt - der erst
    moeglicherweise SPAETER erreichte Tages-Hoechststand (110) darf den Stop fuer diese Kerze
    nicht nachtraeglich verschieben."""
    trade = make_trade(direction="long", stop=95)
    bar = make_bar(open_=100, high=110, low=94, close=108)

    result = evaluate_exit(trade, bar, date(2026, 8, 19), "conservative_stop_first", False)
    assert result.exit is True
    assert result.reason == "stop_loss"
    assert result.price == 95
    assert result.gap_through_stop is False

    # Falsche Reihenfolge (Trailing-Stop VOR der Exit-Pruefung) wuerde denselben Tages-High
    # nutzen, um den Stop auf 105 zu verschieben, und liefert dadurch einen anderen (falschen)
    # Exit-Preis - Beleg dafuer, warum die Aufrufreihenfolge nicht vertauschbar ist.
    wrong_order_trade = update_trailing_stop(trade, bar)
    wrong_order_result = evaluate_exit(wrong_order_trade, bar, date(2026, 8, 19), "conservative_stop_first", False)
    assert wrong_order_result.price != result.price


# --- fill_order (Phase 0, WF14-Migration) ---

FEE_BPS_MODEL = FeeModel(kind="fee_bps", fee_bps=15, slippage_bps=10)
MINI_FUTURE_MODEL = FeeModel(kind="mini_future", mini_future_spread_pct=0.5, mini_future_financing_pct_pa=3.0)


def test_fill_order_not_touched_returns_no_trade():
    order = make_order(zone_low=99, zone_high=101)
    bar = make_bar(open_=105, high=106, low=104, close=105)
    outcome = fill_order(order, bar, FEE_BPS_MODEL, date(2026, 8, 19))
    assert outcome.fill.filled is False
    assert outcome.trade is None
    assert outcome.entry_fee == 0.0
    assert outcome.cash_delta == 0.0


def test_fill_order_fee_bps_model():
    order = make_order(zone_low=99, zone_high=101)
    bar = make_bar(open_=100, high=102, low=98, close=101)
    outcome = fill_order(order, bar, FEE_BPS_MODEL, date(2026, 8, 19))
    assert outcome.fill.filled is True
    position_value = 100 * order.quantity  # fill price 100 (open in zone) * 10
    expected_fee = position_value * 15 / 10000
    assert outcome.entry_fee == expected_fee
    assert outcome.cash_delta == -(position_value + expected_fee)
    assert outcome.trade is not None
    assert outcome.trade.entry_price == 100
    assert outcome.trade.ticker == "TEST"


def test_fill_order_mini_future_model():
    order = make_order(zone_low=99, zone_high=101)
    bar = make_bar(open_=100, high=102, low=98, close=101)
    outcome = fill_order(order, bar, MINI_FUTURE_MODEL, date(2026, 8, 19))
    position_value = 100 * order.quantity
    expected_fee = position_value * 0.5 / 100 / 2
    assert outcome.entry_fee == expected_fee


def test_fill_order_hard_stop_cap_binds_when_signal_stop_is_wider():
    # entry 100, signal stop 80 (20% weg) -> 10%-Hard-Cap (90) ist enger und muss binden.
    order = make_order(zone_low=99, zone_high=101, direction="long")
    order = order.model_copy(update={"stop_price": 80})
    bar = make_bar(open_=100, high=102, low=98, close=101)
    outcome = fill_order(order, bar, FEE_BPS_MODEL, date(2026, 8, 19))
    assert outcome.trade.stop_price_current == 90  # 100 * 0.9
    assert outcome.trade.trail_distance == 10  # |100 - 90|


def test_fill_order_signal_stop_binds_when_tighter_than_hard_cap():
    # entry 100, signal stop 97 (3% weg) -> enger als der 10%-Hard-Cap (90), Signal-Stop gilt.
    order = make_order(zone_low=99, zone_high=101, direction="long")
    order = order.model_copy(update={"stop_price": 97})
    bar = make_bar(open_=100, high=102, low=98, close=101)
    outcome = fill_order(order, bar, FEE_BPS_MODEL, date(2026, 8, 19))
    assert outcome.trade.stop_price_current == 97
    assert outcome.trade.trail_distance == 3


def test_fill_order_hard_stop_cap_short_direction():
    # Short-Entry 100, Signal-Stop 125 (25% weg) -> 10%-Hard-Cap (110) ist enger fuer Short
    # (min() statt max()) und muss binden.
    order = make_order(zone_low=99, zone_high=101, direction="short")
    order = order.model_copy(update={"stop_price": 125})
    bar = make_bar(open_=100, high=102, low=98, close=101)
    outcome = fill_order(order, bar, FEE_BPS_MODEL, date(2026, 8, 19))
    assert round(outcome.trade.stop_price_current, 6) == 110  # 100 * 1.1
    assert outcome.trade.direction == "short"


def test_fill_order_carries_audit_fields_from_order_to_trade():
    order = make_order(zone_low=99, zone_high=101)
    order = order.model_copy(update={
        "theoretical_quantity": 15, "theoretical_risk_amount": 250.0, "clamp_reason": "SECTOR_LIMIT",
        "strategy": "trend_following", "sektor": "Technologie", "region": "USA", "risk_amount": 200.0,
    })
    bar = make_bar(open_=100, high=102, low=98, close=101)
    outcome = fill_order(order, bar, FEE_BPS_MODEL, date(2026, 8, 19))
    assert outcome.trade.theoretical_quantity == 15
    assert outcome.trade.theoretical_risk_amount == 250.0
    assert outcome.trade.clamp_reason == "SECTOR_LIMIT"
    assert outcome.trade.strategy == "trend_following"
    assert outcome.trade.sektor == "Technologie"
    assert outcome.trade.region == "USA"
    assert outcome.trade.risk_amount == 200.0


# --- process_open_trade (Phase 0, WF14-Migration) ---

def test_process_open_trade_no_exit_applies_trailing_stop():
    trade = make_trade(direction="long", stop=95, target=200, strategy="trend_following")
    bar = make_bar(open_=105, high=110, low=104, close=108)
    outcome = process_open_trade(trade, bar, date(2026, 8, 19), "conservative_stop_first", False, FEE_BPS_MODEL)
    assert outcome.exit_result.exit is False
    assert outcome.updated_trade.extreme_price_since_entry == 110
    assert outcome.updated_trade.stop_price_current == 105  # 110 - trail_distance(5)
    assert outcome.pnl is None
    assert outcome.cash_delta is None


def test_process_open_trade_exit_computes_pnl_and_cash_delta_long():
    trade = make_trade(direction="long", stop=95, target=110)
    bar = make_bar(open_=100, high=101, low=94, close=96)  # stop touched at 95
    outcome = process_open_trade(trade, bar, date(2026, 8, 19), "conservative_stop_first", False, FEE_BPS_MODEL)
    assert outcome.exit_result.exit is True
    assert outcome.exit_result.reason == "stop_loss"
    assert outcome.pnl is not None
    exit_notional = 95 * trade.quantity  # long exit cash inflow = exit notional
    expected_cash_delta = exit_notional - outcome.pnl.exit_fee - outcome.pnl.exit_slippage - outcome.pnl.financing_cost
    assert outcome.cash_delta == expected_cash_delta
    assert outcome.updated_trade == trade  # Trade selbst unveraendert zurueckgegeben bei Exit


def test_process_open_trade_exit_computes_pnl_and_cash_delta_short():
    # P17-1-Fix (siehe portfolio.py-Docstring): Short-Cash-Zufluss ist 2*entry_value-exit_notional,
    # NICHT die reine Exit-Notional.
    trade = make_trade(direction="short", stop=110, target=95)
    bar = make_bar(open_=105, high=111, low=104, close=109)  # stop touched at 110
    outcome = process_open_trade(trade, bar, date(2026, 8, 19), "conservative_stop_first", False, FEE_BPS_MODEL)
    assert outcome.exit_result.exit is True
    exit_notional = 110 * trade.quantity
    expected_cash_inflow = 2 * trade.entry_price * trade.quantity - exit_notional
    expected_cash_delta = expected_cash_inflow - outcome.pnl.exit_fee - outcome.pnl.exit_slippage - outcome.pnl.financing_cost
    assert outcome.cash_delta == expected_cash_delta


def test_process_open_trade_mean_reversion_no_trailing_on_no_exit():
    trade = make_trade(direction="long", stop=95, target=200, strategy="mean_reversion")
    bar = make_bar(open_=105, high=110, low=104, close=108)
    outcome = process_open_trade(trade, bar, date(2026, 8, 19), "conservative_stop_first", False, FEE_BPS_MODEL)
    assert outcome.exit_result.exit is False
    assert outcome.updated_trade.extreme_price_since_entry == 110  # weiter mitgefuehrt
    assert outcome.updated_trade.stop_price_current == 95  # kein Trailing fuer mean_reversion


def test_process_open_trade_look_ahead_ordering():
    # Mirror von test_exit_look_ahead_ordering_from_audit_brief oben, aber ueber die kombinierte
    # Funktion: evaluate_exit MUSS mit dem alten Stop erfolgen, nicht dem durch denselben Bar
    # potenziell schon nachgezogenen.
    trade = make_trade(direction="long", stop=95)
    bar = make_bar(open_=100, high=110, low=94, close=108)
    outcome = process_open_trade(trade, bar, date(2026, 8, 19), "conservative_stop_first", False, FEE_BPS_MODEL)
    assert outcome.exit_result.exit is True
    assert outcome.exit_result.reason == "stop_loss"
    assert outcome.exit_result.price == 95
