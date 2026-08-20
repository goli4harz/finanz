"""Tests fuer size_position() (trading_engine/position_sizing.py).

Deckt beide sizing_mode-Zweige ab: 'reject' (WF06s computeRisk(), rein einzeltrade-bezogen) und
'clamp' (WF17s sizePosition(), portfolio-bewusst mit mehreren Veto-Bedingungen).
"""

from trading_engine.models import FeeModel, Position, RiskConfig, Signal
from trading_engine.position_sizing import size_position


def make_signal(stop_price=95, target_price=110):
    return Signal(
        strategy="trend_following", direction="long", raw_score=0.8,
        entry_zone_low=99, entry_zone_high=101, stop_price=stop_price, target_price=target_price,
        expected_horizon_days=15, rule_version="welle1-v1",
    )


def make_risk_cfg(**overrides):
    defaults = dict(
        model_portfolio_value=100000, max_risk_per_trade_pct=1.0, max_total_open_risk_pct=6.0,
        max_sector_exposure_pct=20.0, max_single_position_pct=20.0, max_open_positions=10,
        max_directional_exposure_pct=60.0, max_portfolio_drawdown_pct=15.0, max_pairwise_correlation=0.7,
        max_region_exposure_pct=40.0, max_non_eur_exposure_pct=30.0, stress_risk_reduction_factor=0.5,
        max_position_value_pct=20.0, min_reward_risk_ratio=1.5,
    )
    defaults.update(overrides)
    return RiskConfig(**defaults)


def make_position(risk_amount=0, position_value=0, sektor="Tech", region="US", direction="long"):
    return Position(ticker="X", direction=direction, quantity=1, position_value=position_value, sektor=sektor, region=region, risk_amount=risk_amount)


# --- reject mode (WF06 computeRisk) ---

def test_reject_mode_ignores_portfolio_state():
    signal = make_signal(stop_price=95)  # unit_risk = 5, entry 100
    risk_cfg = make_risk_cfg()
    # Ein Portfolio, das im clamp-Modus alles blocken wuerde, darf im reject-Modus keine Rolle spielen.
    saturated_portfolio = [make_position(risk_amount=6000, position_value=90000, sektor="Tech", region="US")]
    result = size_position(signal, 100, risk_cfg, saturated_portfolio, "Tech", "US", sizing_mode="reject")
    assert result.blocked is False
    # risk-based: (100000*1%)/5 = 200; value-based: (100000*20%)/100 = 200 -> Minimum 200
    assert result.quantity == 200


def test_reject_mode_value_limit_binds():
    signal = make_signal(stop_price=90)  # unit_risk = 10 -> risk-based quantity hoch
    risk_cfg = make_risk_cfg(max_risk_per_trade_pct=5.0, max_position_value_pct=10.0)
    result = size_position(signal, 100, risk_cfg, [], "Tech", "US", sizing_mode="reject")
    # risk-based: (100000*5%)/10 = 500; value-based: (100000*10%)/100 = 100 -> Minimum 100
    assert result.quantity == 100
    assert result.clamped is True
    assert result.reason == "value"


def test_reject_mode_stop_wrong_side_blocked():
    signal = make_signal(stop_price=100)  # unit_risk = 0 bei entry=100
    result = size_position(signal, 100, make_risk_cfg(), [], "Tech", "US", sizing_mode="reject")
    assert result.blocked is True
    assert result.reason == "STOP_WRONG_SIDE"


# --- clamp mode (WF17 sizePosition) ---

def test_clamp_mode_no_portfolio_uses_risk_based_quantity():
    signal = make_signal(stop_price=95, target_price=120)  # unit_risk=5, RRR=(120-100)/5=4.0
    result = size_position(signal, 100, make_risk_cfg(), [], "Tech", "US", sizing_mode="clamp")
    assert result.blocked is False
    assert result.quantity == 200  # (100000*1%)/5
    assert result.clamped is False


def test_clamp_mode_total_risk_budget_binds():
    signal = make_signal(stop_price=95, target_price=120)
    risk_cfg = make_risk_cfg(max_total_open_risk_pct=6.0)
    # Bereits 5900 von 6000 Gesamtrisikobudget verbraucht -> nur noch 100 Budget uebrig -> 100/5=20 Stueck.
    open_positions = [make_position(risk_amount=5900, sektor="Health", region="EU")]
    result = size_position(signal, 100, risk_cfg, open_positions, "Tech", "US", sizing_mode="clamp")
    assert result.quantity == 20
    assert result.clamped is True
    assert result.reason == "TOTAL_RISK_LIMIT"


def test_clamp_mode_sector_limit_binds():
    signal = make_signal(stop_price=95, target_price=120)
    risk_cfg = make_risk_cfg(max_sector_exposure_pct=20.0)
    # Sektor-Budget: 100000*20%=20000. Bereits 19000 im selben Sektor -> Rest 1000 -> 1000/100=10 Stueck.
    open_positions = [make_position(risk_amount=0, position_value=19000, sektor="Tech", region="EU")]
    result = size_position(signal, 100, risk_cfg, open_positions, "Tech", "US", sizing_mode="clamp")
    assert result.quantity == 10
    assert result.reason == "SECTOR_LIMIT"


def test_clamp_mode_quantity_too_small_blocked():
    signal = make_signal(stop_price=95, target_price=120)
    risk_cfg = make_risk_cfg(max_total_open_risk_pct=6.0)
    # Gesamtrisikobudget quasi erschoepft -> resultierende Stueckzahl < 1.
    open_positions = [make_position(risk_amount=5999.9, sektor="Health", region="EU")]
    result = size_position(signal, 100, risk_cfg, open_positions, "Tech", "US", sizing_mode="clamp")
    assert result.blocked is True
    assert result.reason == "QUANTITY_TOO_SMALL"


def test_clamp_mode_rrr_too_low_blocked():
    signal = make_signal(stop_price=95, target_price=101)  # RRR = (101-100)/5 = 0.2
    risk_cfg = make_risk_cfg(min_reward_risk_ratio=1.5)
    result = size_position(signal, 100, risk_cfg, [], "Tech", "US", sizing_mode="clamp")
    assert result.blocked is True
    assert result.reason == "RRR_TOO_LOW"


def test_clamp_mode_uneconomical_after_costs_blocked():
    signal = make_signal(stop_price=99, target_price=120)  # unit_risk=1 -> sehr kleine Stueckzahl, hohe relative Kosten
    risk_cfg = make_risk_cfg(max_risk_per_trade_pct=0.01)  # winziges Risikobudget -> winzige Stueckzahl
    fee_model = FeeModel(kind="fee_bps", fee_bps=500, slippage_bps=500)  # unrealistisch hohe Kosten, erzwingt den Veto
    result = size_position(signal, 100, risk_cfg, [], "Tech", "US", sizing_mode="clamp", fee_model=fee_model)
    assert result.blocked is True
    assert result.reason in ("UNECONOMICAL_AFTER_COSTS", "QUANTITY_TOO_SMALL")


def test_clamp_mode_uneconomical_after_costs_blocked_for_mini_future():
    # FIX 2026-08-20: WF17 nutzt kind="mini_future", prueft den Veto im Live-Code aber trotzdem
    # ueber die generischen fee_bps/slippage_bps-Werte (Schwellenwert-Heuristik, unabhaengig vom
    # tatsaechlichen Abrechnungsmodell). Vorher wurde dieser Zweig nur bei kind="fee_bps" geprueft
    # - beim Abgleich gegen den Live-Code als echte Luecke gefunden, bevor WF17 migriert wird.
    signal = make_signal(stop_price=99, target_price=120)
    risk_cfg = make_risk_cfg(max_risk_per_trade_pct=0.01)
    fee_model = FeeModel(kind="mini_future", fee_bps=500, slippage_bps=500, mini_future_leverage=5,
                          mini_future_spread_pct=0.5, mini_future_financing_pct_pa=3.0)
    result = size_position(signal, 100, risk_cfg, [], "Tech", "US", sizing_mode="clamp", fee_model=fee_model)
    assert result.blocked is True
    assert result.reason in ("UNECONOMICAL_AFTER_COSTS", "QUANTITY_TOO_SMALL")


def test_clamp_mode_mini_future_without_bps_fields_skips_veto():
    # Gegenprobe: ein mini_future-fee_model OHNE fee_bps/slippage_bps (beide None, wie es vor der
    # Migration bei jedem anderen mini_future-Aufrufer der Fall waere) darf den Veto weiterhin
    # nicht versehentlich ueber einen impliziten 0-Schwellenwert ausloesen.
    signal = make_signal(stop_price=99, target_price=120)
    risk_cfg = make_risk_cfg(max_risk_per_trade_pct=0.01)
    fee_model = FeeModel(kind="mini_future", mini_future_leverage=5, mini_future_spread_pct=0.5,
                          mini_future_financing_pct_pa=3.0)
    result = size_position(signal, 100, risk_cfg, [], "Tech", "US", sizing_mode="clamp", fee_model=fee_model)
    assert result.reason != "UNECONOMICAL_AFTER_COSTS"


def test_clamp_mode_stop_target_invalid_blocked():
    signal = make_signal(stop_price=95, target_price=120)
    risk_cfg = make_risk_cfg(max_risk_per_trade_pct=0.001)  # Risikobudget so klein, dass quantity=0
    result = size_position(signal, 100, risk_cfg, [], "Tech", "US", sizing_mode="clamp")
    assert result.blocked is True
    assert result.reason == "STOP_TARGET_INVALID"
