"""Tests fuer check_portfolio_limits() (trading_engine/risk_limits.py).

Ein Testfall pro Limit aus der Phase-1-Tabelle "Risikolimits (Portfolio)", 1:1 gegen den echten
Live-Code von "Job A: Portfoliopruefung + Trade-Anlage" (WF14) hergeleitet.
"""

from trading_engine.models import PortfolioState, Position, RiskConfig, SizingResult
from trading_engine.risk_limits import check_portfolio_limits


def make_risk_cfg(**overrides):
    defaults = dict(
        model_portfolio_value=100000, max_risk_per_trade_pct=1.0, max_total_open_risk_pct=6.0,
        max_sector_exposure_pct=15.0, max_single_position_pct=8.0, max_open_positions=10,
        max_directional_exposure_pct=40.0, max_portfolio_drawdown_pct=15.0, max_pairwise_correlation=0.75,
        max_region_exposure_pct=60.0, max_non_eur_exposure_pct=30.0, stress_risk_reduction_factor=0.5,
        max_position_value_pct=20.0, min_reward_risk_ratio=1.5,
    )
    defaults.update(overrides)
    return RiskConfig(**defaults)


def make_position(ticker="A", risk_amount=0, position_value=0, sektor="Tech", region="US", currency="USD", direction="long"):
    return Position(ticker=ticker, direction=direction, quantity=1, position_value=position_value, sektor=sektor, region=region, currency=currency, risk_amount=risk_amount)


def make_portfolio(open_positions=None, drawdown_pct=0.0):
    return PortfolioState(cash=0, positions_value=0, total_equity=100000, peak_equity=100000, drawdown_pct=drawdown_pct, open_positions=open_positions or [])


def make_candidate(quantity=10, position_value=5000, risk_amount=500):
    return SizingResult(quantity=quantity, position_value=position_value, risk_amount=risk_amount, clamped=False, blocked=False)


def blocker_names(blockers):
    return {b.limit_name for b in blockers}


def test_approved_when_no_limit_violated():
    blockers = check_portfolio_limits(make_candidate(), "X", "Tech", "US", "EUR", "long", make_portfolio(), make_risk_cfg())
    assert blockers == []


def test_total_risk_limit():
    risk_cfg = make_risk_cfg(max_total_open_risk_pct=6.0)
    portfolio = make_portfolio([make_position(risk_amount=5600)])
    candidate = make_candidate(risk_amount=500)  # 5600+500=6100 -> 6.1% > 6.0%
    blockers = check_portfolio_limits(candidate, "X", "Health", "EU", "EUR", "long", portfolio, risk_cfg)
    assert "TOTAL_RISK_LIMIT" in blocker_names(blockers)


def test_total_risk_limit_stress_reduced():
    risk_cfg = make_risk_cfg(max_total_open_risk_pct=6.0, stress_risk_reduction_factor=0.5)
    portfolio = make_portfolio([make_position(risk_amount=2600)])
    candidate = make_candidate(risk_amount=500)  # 3100 -> 3.1%, unter 6% aber ueber stressreduziertem 3%
    blockers = check_portfolio_limits(candidate, "X", "Health", "EU", "EUR", "long", portfolio, risk_cfg, is_stress_regime=True)
    assert "TOTAL_RISK_LIMIT" in blocker_names(blockers)
    blockers_no_stress = check_portfolio_limits(candidate, "X", "Health", "EU", "EUR", "long", portfolio, risk_cfg, is_stress_regime=False)
    assert "TOTAL_RISK_LIMIT" not in blocker_names(blockers_no_stress)


def test_sector_limit():
    risk_cfg = make_risk_cfg(max_sector_exposure_pct=15.0)
    portfolio = make_portfolio([make_position(sektor="Tech", position_value=14000)])
    candidate = make_candidate(position_value=2000)  # 16000 -> 16% > 15%
    blockers = check_portfolio_limits(candidate, "X", "Tech", "US", "EUR", "long", portfolio, risk_cfg)
    assert "SECTOR_LIMIT" in blocker_names(blockers)


def test_region_limit():
    risk_cfg = make_risk_cfg(max_region_exposure_pct=60.0)
    portfolio = make_portfolio([make_position(region="US", position_value=58000)])
    candidate = make_candidate(position_value=3000)
    blockers = check_portfolio_limits(candidate, "X", "Tech", "US", "EUR", "long", portfolio, risk_cfg)
    assert "REGION_LIMIT" in blocker_names(blockers)


def test_currency_limit_only_for_non_eur_candidate():
    risk_cfg = make_risk_cfg(max_non_eur_exposure_pct=30.0)
    portfolio = make_portfolio([make_position(currency="USD", position_value=29000)])
    candidate = make_candidate(position_value=2000)
    blockers_usd = check_portfolio_limits(candidate, "X", "Tech", "US", "USD", "long", portfolio, risk_cfg)
    assert "CURRENCY_LIMIT" in blocker_names(blockers_usd)
    # Ein EUR-Kandidat loest den Check gar nicht erst aus (siehe Live-Code: `if (empfWaehrung !== 'EUR')`).
    blockers_eur = check_portfolio_limits(candidate, "X", "Tech", "US", "EUR", "long", portfolio, risk_cfg)
    assert "CURRENCY_LIMIT" not in blocker_names(blockers_eur)


def test_single_position_limit():
    risk_cfg = make_risk_cfg(max_single_position_pct=8.0)
    candidate = make_candidate(position_value=9000)  # 9% > 8%
    blockers = check_portfolio_limits(candidate, "X", "Tech", "US", "EUR", "long", make_portfolio(), risk_cfg)
    assert "SINGLE_POSITION_LIMIT" in blocker_names(blockers)


def test_max_open_positions():
    risk_cfg = make_risk_cfg(max_open_positions=2)
    portfolio = make_portfolio([make_position(ticker="A"), make_position(ticker="B")])
    blockers = check_portfolio_limits(make_candidate(), "X", "Tech", "US", "EUR", "long", portfolio, risk_cfg)
    assert "MAX_OPEN_POSITIONS" in blocker_names(blockers)


def test_directional_limit():
    risk_cfg = make_risk_cfg(max_directional_exposure_pct=40.0)
    portfolio = make_portfolio([make_position(direction="long", position_value=39000)])
    candidate = make_candidate(position_value=2000)
    blockers = check_portfolio_limits(candidate, "X", "Tech", "US", "EUR", "long", portfolio, risk_cfg)
    assert "DIRECTIONAL_LIMIT" in blocker_names(blockers)
    # Eine Short-Position im selben Portfolio zaehlt NICHT gegen das Long-Directional-Limit.
    blockers_short = check_portfolio_limits(candidate, "X", "Tech", "US", "EUR", "short", portfolio, risk_cfg)
    assert "DIRECTIONAL_LIMIT" not in blocker_names(blockers_short)


def test_drawdown_limit():
    risk_cfg = make_risk_cfg(max_portfolio_drawdown_pct=15.0)
    portfolio = make_portfolio(drawdown_pct=20.0)
    blockers = check_portfolio_limits(make_candidate(), "X", "Tech", "US", "EUR", "long", portfolio, risk_cfg)
    assert "DRAWDOWN_LIMIT" in blocker_names(blockers)


def test_correlation_limit():
    risk_cfg = make_risk_cfg(max_pairwise_correlation=0.75)
    portfolio = make_portfolio([make_position(ticker="OTHER")])
    # Zwei identische Renditereihen -> Korrelation 1.0 > 0.75.
    returns = [0.01 * ((-1) ** i) for i in range(20)]
    correlation_data = {"X": returns, "OTHER": returns}
    blockers = check_portfolio_limits(make_candidate(), "X", "Tech", "US", "EUR", "long", portfolio, risk_cfg, correlation_data=correlation_data)
    assert "CORRELATION_LIMIT" in blocker_names(blockers)


def test_correlation_limit_skipped_below_min_length():
    risk_cfg = make_risk_cfg(max_pairwise_correlation=0.75)
    portfolio = make_portfolio([make_position(ticker="OTHER")])
    short_returns = [0.01, 0.02, 0.01]  # < 10 Werte -> pearson() gibt None zurueck
    correlation_data = {"X": short_returns, "OTHER": short_returns}
    blockers = check_portfolio_limits(make_candidate(), "X", "Tech", "US", "EUR", "long", portfolio, risk_cfg, correlation_data=correlation_data)
    assert "CORRELATION_LIMIT" not in blocker_names(blockers)


def test_multiple_limits_can_fire_simultaneously():
    risk_cfg = make_risk_cfg(max_sector_exposure_pct=15.0, max_single_position_pct=8.0)
    portfolio = make_portfolio([make_position(sektor="Tech", position_value=14000)])
    candidate = make_candidate(position_value=9000)  # verletzt SECTOR_LIMIT und SINGLE_POSITION_LIMIT gleichzeitig
    blockers = check_portfolio_limits(candidate, "X", "Tech", "US", "EUR", "long", portfolio, risk_cfg)
    assert {"SECTOR_LIMIT", "SINGLE_POSITION_LIMIT"} <= blocker_names(blockers)
