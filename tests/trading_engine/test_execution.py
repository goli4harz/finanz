"""Tests fuer simulate_entry() und evaluate_exit() (trading_engine/execution.py).

Faelle 1:1 gegen die live geladene Referenzimplementierung in WF17 ("Verarbeite Tage-Paket",
simulateEntryFill()/checkExit()) hergeleitet - siehe execution.py-Docstrings fuer die Herkunft.
"""

from datetime import date

from trading_engine.execution import evaluate_exit, simulate_entry, update_trailing_stop
from trading_engine.models import Bar, Order, Trade


def make_bar(open_, high, low, close, trading_date="2026-08-19"):
    return Bar(ticker="TEST", trading_date=trading_date, open=open_, high=high, low=low, close=close, volume=1000)


def make_order(zone_low=99, zone_high=101, direction="long"):
    return Order(
        ticker="TEST", direction=direction, entry_zone_low=zone_low, entry_zone_high=zone_high,
        stop_price=95, target_price=110, quantity=10, intended_execution_date="2026-08-19",
    )


def make_trade(direction="long", stop=95, target=110, time_stop_at=None):
    return Trade(
        trade_id="t1", ticker="TEST", direction=direction, entry_price=100,
        stop_price_current=stop, target_price=target, quantity=10,
        extreme_price_since_entry=100, trail_distance=5, entry_day="2026-08-18",
        time_stop_at=time_stop_at,
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
