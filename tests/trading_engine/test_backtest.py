"""Integrationstests fuer step() (trading_engine/backtest.py) - ein Tag im Leben von WF17s
"Verarbeite Tage-Paket", zusammengesetzt aus den bereits einzeln getesteten Bausteinen.
"""

from datetime import date

from trading_engine.backtest import step
from trading_engine.models import Bar, FeeModel, Order, RiskConfig, Trade

MINI_FUTURE = FeeModel(kind="mini_future", mini_future_leverage=5, mini_future_spread_pct=0.5, mini_future_financing_pct_pa=3.0)


def make_bar(ticker, close, open_=None, high=None, low=None, trading_date="2026-08-19"):
    open_ = open_ if open_ is not None else close
    high = high if high is not None else close
    low = low if low is not None else close
    return Bar(ticker=ticker, trading_date=trading_date, open=open_, high=high, low=low, close=close, volume=1_000_000)


def make_risk_cfg(**overrides):
    defaults = dict(
        model_portfolio_value=100000, max_risk_per_trade_pct=1.0, max_total_open_risk_pct=6.0,
        max_sector_exposure_pct=20.0, max_single_position_pct=20.0, max_open_positions=10,
        max_directional_exposure_pct=60.0, max_portfolio_drawdown_pct=15.0, max_pairwise_correlation=0.75,
        max_region_exposure_pct=60.0, max_non_eur_exposure_pct=30.0, stress_risk_reduction_factor=0.5,
        max_position_value_pct=20.0, min_reward_risk_ratio=0.1,
    )
    defaults.update(overrides)
    return RiskConfig(**defaults)


def test_pending_order_fills_and_becomes_open_trade():
    order = Order(
        ticker="AAA", direction="long", entry_zone_low=99, entry_zone_high=101, stop_price=95,
        target_price=110, quantity=10, intended_execution_date=date(2026, 8, 19),
        strategy="trend_following", sektor="Tech", region="US", risk_amount=50,
    )
    bar = make_bar("AAA", close=100, open_=100, high=101, low=99)
    result = step(
        as_of=date(2026, 8, 19), next_trading_day=date(2026, 8, 20), tickers_today=["AAA"],
        bars_today={"AAA": bar}, bars_history={"AAA": [bar]}, pending_orders=[order], open_trades=[],
        cash=100000, previous_peak_equity=100000, risk_cfg=make_risk_cfg(), fee_model=MINI_FUTURE,
        rule_version="test-v1", ticker_sektor={"AAA": "Tech"}, ticker_region={"AAA": "US"}, ticker_currency={"AAA": "EUR"},
    )
    assert len(result.new_trades) == 1
    trade = result.new_trades[0]
    assert trade.entry_price == 100
    assert trade.quantity == 10
    # Cash sinkt um Positionswert + Eintritts-Spread-Fee.
    expected_fee = 1000 * (0.5 / 100 / 2)
    assert round(result.cash, 4) == round(100000 - 1000 - expected_fee, 4)
    assert result.still_pending_orders == []


def test_order_fill_carries_theoretical_audit_fields_to_trade():
    # FIX 2026-08-20 (Phase-8-Migration): theoretical_quantity/theoretical_risk_amount/
    # clamp_reason muessen vom Order beim Fill 1:1 auf den entstehenden Trade durchgereicht
    # werden - sonst geht der Kappungs-Audit-Trail beim Umstieg von WF17s eigenem Code auf die
    # Engine stillschweigend verloren (newTradeRows braucht diese Felder).
    order = Order(
        ticker="AAA", direction="long", entry_zone_low=99, entry_zone_high=101, stop_price=95,
        target_price=110, quantity=10, intended_execution_date=date(2026, 8, 19),
        strategy="trend_following", sektor="Tech", region="US", risk_amount=50,
        theoretical_quantity=25, theoretical_risk_amount=125, clamp_reason="SECTOR_LIMIT",
    )
    bar = make_bar("AAA", close=100, open_=100, high=101, low=99)
    result = step(
        as_of=date(2026, 8, 19), next_trading_day=date(2026, 8, 20), tickers_today=["AAA"],
        bars_today={"AAA": bar}, bars_history={"AAA": [bar]}, pending_orders=[order], open_trades=[],
        cash=100000, previous_peak_equity=100000, risk_cfg=make_risk_cfg(), fee_model=MINI_FUTURE,
        rule_version="test-v1", ticker_sektor={"AAA": "Tech"}, ticker_region={"AAA": "US"}, ticker_currency={"AAA": "EUR"},
    )
    trade = result.new_trades[0]
    assert trade.theoretical_quantity == 25
    assert trade.theoretical_risk_amount == 125
    assert trade.clamp_reason == "SECTOR_LIMIT"


def test_hard_stop_cap_applied_on_fill():
    # Order-Stop liegt weiter als 10% vom Fuellpreis entfernt -> muss auf die harte 10%-Grenze gekappt werden.
    order = Order(
        ticker="AAA", direction="long", entry_zone_low=99, entry_zone_high=101, stop_price=70,  # 30% entfernt
        target_price=150, quantity=10, intended_execution_date=date(2026, 8, 19),
        strategy="trend_following", sektor="Tech", region="US", risk_amount=50,
    )
    bar = make_bar("AAA", close=100, open_=100, high=101, low=99)
    result = step(
        as_of=date(2026, 8, 19), next_trading_day=date(2026, 8, 20), tickers_today=["AAA"],
        bars_today={"AAA": bar}, bars_history={"AAA": [bar]}, pending_orders=[order], open_trades=[],
        cash=100000, previous_peak_equity=100000, risk_cfg=make_risk_cfg(), fee_model=MINI_FUTURE,
        rule_version="test-v1", ticker_sektor={"AAA": "Tech"}, ticker_region={"AAA": "US"}, ticker_currency={"AAA": "EUR"},
    )
    trade = result.new_trades[0]
    assert trade.stop_price_current == 90  # 100 * 0.9, nicht 70


def test_open_trade_stopped_out_updates_cash_and_returns_pnl():
    trade = Trade(
        trade_id="t1", ticker="AAA", direction="long", entry_price=100, stop_price_current=95,
        target_price=120, quantity=10, extreme_price_since_entry=100, trail_distance=5,
        entry_day=date(2026, 8, 1), strategy="trend_following", sektor="Tech", region="US", risk_amount=50,
    )
    bar = make_bar("AAA", close=94, open_=99, high=99, low=92)  # Low 92 <= Stop 95 -> Exit
    result = step(
        as_of=date(2026, 8, 19), next_trading_day=date(2026, 8, 20), tickers_today=["AAA"],
        bars_today={"AAA": bar}, bars_history={"AAA": [bar]}, pending_orders=[], open_trades=[trade],
        cash=90000, previous_peak_equity=100000, risk_cfg=make_risk_cfg(), fee_model=MINI_FUTURE,
        rule_version="test-v1", ticker_sektor={"AAA": "Tech"}, ticker_region={"AAA": "US"}, ticker_currency={"AAA": "EUR"},
    )
    assert len(result.exited_trades) == 1
    exited = result.exited_trades[0]
    assert exited.exit_result.price == 95
    assert exited.pnl.gross_pnl == -50  # (95-100)*10
    assert result.still_open_trades == []
    # Cash: 90000 (bereits abgezogene Margin) + exitCashInflow(950) - fees.
    assert result.cash > 90000  # Margin fliesst beim Exit zurueck


def test_open_trade_survives_and_trailing_stop_updates():
    trade = Trade(
        trade_id="t1", ticker="AAA", direction="long", entry_price=100, stop_price_current=95,
        target_price=200, quantity=10, extreme_price_since_entry=100, trail_distance=5,
        entry_day=date(2026, 8, 1), strategy="trend_following", sektor="Tech", region="US", risk_amount=50,
    )
    bar = make_bar("AAA", close=115, open_=110, high=120, low=109)  # kein Exit, neues Hoch
    result = step(
        as_of=date(2026, 8, 19), next_trading_day=date(2026, 8, 20), tickers_today=["AAA"],
        bars_today={"AAA": bar}, bars_history={"AAA": [bar]}, pending_orders=[], open_trades=[trade],
        cash=90000, previous_peak_equity=100000, risk_cfg=make_risk_cfg(), fee_model=MINI_FUTURE,
        rule_version="test-v1", ticker_sektor={"AAA": "Tech"}, ticker_region={"AAA": "US"}, ticker_currency={"AAA": "EUR"},
    )
    assert result.exited_trades == []
    assert len(result.still_open_trades) == 1
    updated = result.still_open_trades[0]
    assert updated.extreme_price_since_entry == 120
    assert updated.stop_price_current == 115  # 120 - trail_distance(5)


def test_data_gap_keeps_position_open_without_trailing_update():
    trade = Trade(
        trade_id="t1", ticker="AAA", direction="long", entry_price=100, stop_price_current=95,
        target_price=200, quantity=10, extreme_price_since_entry=100, trail_distance=5,
        entry_day=date(2026, 8, 1), strategy="trend_following", sektor="Tech", region="US", risk_amount=50,
    )
    result = step(
        as_of=date(2026, 8, 19), next_trading_day=date(2026, 8, 20), tickers_today=[],
        bars_today={}, bars_history={}, pending_orders=[], open_trades=[trade],
        cash=90000, previous_peak_equity=100000, risk_cfg=make_risk_cfg(), fee_model=MINI_FUTURE,
        rule_version="test-v1", ticker_sektor={}, ticker_region={}, ticker_currency={},
    )
    assert result.exited_trades == []
    assert result.still_open_trades == [trade]  # unveraendert


def test_already_open_ticker_not_duplicated_as_new_candidate():
    trade = Trade(
        trade_id="t1", ticker="AAA", direction="long", entry_price=100, stop_price_current=95,
        target_price=200, quantity=10, extreme_price_since_entry=100, trail_distance=5,
        entry_day=date(2026, 8, 1), strategy="trend_following", sektor="Tech", region="US", risk_amount=50,
    )
    # Starke Kursreihe mit klarem Ausbruch, die normalerweise einen neuen Kandidaten ausloesen wuerde.
    closes = [100.0] * 45 + [130.0]
    bars = [Bar(ticker="AAA", trading_date=date(2026, 7, 1), open=c, high=c, low=c, close=c, volume=1_000_000) for c in closes]
    bar_today = bars[-1]
    result = step(
        as_of=date(2026, 8, 19), next_trading_day=date(2026, 8, 20), tickers_today=["AAA"],
        bars_today={"AAA": bar_today}, bars_history={"AAA": bars}, pending_orders=[], open_trades=[trade],
        cash=90000, previous_peak_equity=100000, risk_cfg=make_risk_cfg(), fee_model=MINI_FUTURE,
        rule_version="test-v1", ticker_sektor={"AAA": "Tech"}, ticker_region={"AAA": "US"}, ticker_currency={"AAA": "EUR"},
    )
    assert result.new_orders == []  # AAA ist schon offen -> kein zweiter Kandidat


def test_new_candidate_generates_order_when_no_open_position():
    closes = [100.0] * 45 + [130.0]
    bars = [Bar(ticker="BBB", trading_date=date(2026, 7, 1), open=c, high=c, low=c, close=c, volume=1_000_000) for c in closes]
    bar_today = bars[-1]
    result = step(
        as_of=date(2026, 8, 19), next_trading_day=date(2026, 8, 20), tickers_today=["BBB"],
        bars_today={"BBB": bar_today}, bars_history={"BBB": bars}, pending_orders=[], open_trades=[],
        cash=100000, previous_peak_equity=100000, risk_cfg=make_risk_cfg(), fee_model=MINI_FUTURE,
        rule_version="test-v1", ticker_sektor={"BBB": "Tech"}, ticker_region={"BBB": "US"}, ticker_currency={"BBB": "EUR"},
    )
    assert len(result.new_orders) == 1
    order = result.new_orders[0]
    assert order.ticker == "BBB"
    assert order.intended_execution_date == date(2026, 8, 20)
    assert order.quantity > 0
    # BUGFIX 2026-08-20 (gefunden beim ersten echten WF17-Vergleichslauf, Phase-8-Migration): ein
    # neu erzeugter, aber noch NICHT gefuellter Order-Kandidat darf nicht in die Tages-Equity
    # eingehen - kein Cash wurde ausgegeben, keine Position existiert. Live reproduziert mit einem
    # 0-Trades-Testlauf, der trotzdem +23,9% "Rendite" zeigte, weil positions_value faelschlich
    # den vollen Wert jedes neuen Kandidaten mitzaehlte.
    assert result.portfolio.positions_value == 0
    assert result.portfolio.total_equity == 100000
    assert result.portfolio.drawdown_pct == 0
