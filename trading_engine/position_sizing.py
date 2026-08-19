"""Positionsgroessenberechnung (Phase 2 aus TRADING_ENGINE_ARCHITECTURE.md).

Loest WF06s computeRisk() (sizing_mode='reject') und WF17s sizePosition() (sizing_mode='clamp',
Nutzervorgabe 2026-08-03) ab.

WICHTIGE PRAEZISIERUNG gegenueber der bisherigen Beschreibung ("kappen vs. verwerfen als
Verhaltens-Flag derselben Berechnung"): Beim Nachvollziehen des echten Codes zeigt sich, dass
die beiden Modi nicht nur unterschiedlich auf eine Limitueberschreitung REAGIEREN, sondern
tatsaechlich zwei verschieden weit gefasste Berechnungen sind:

- reject (WF06s computeRisk()): rein EINZELTRADE-bezogen - Risiko-basierte Stueckzahl vs.
  Wertlimit-basierte Stueckzahl (MAX_POSITION_VALUE_PCT), Minimum der beiden. Kennt das
  Portfolio (offene Positionen/Sektor/Region) GAR NICHT. Die eigentliche "Verwerfen"-Entscheidung
  bei Portfolio-Limit-Ueberschreitung passiert NICHT hier, sondern separat in
  check_portfolio_limits() (WF14 Job A, risk_limits.py) - open_positions/sektor/region werden in
  diesem Modus deshalb entgegengenommen, aber nicht verwendet.
- clamp (WF17s sizePosition()): bezieht das Portfolio (verbleibendes Gesamtrisiko-/Sektor-/
  Regionsbudget ueber offene Positionen) DIREKT in dieselbe Berechnung ein und kappt auf das
  jeweils schaerfste Limit (inkl. MAX_SINGLE_POSITION_PCT - ein anderer Config-Key als
  MAX_POSITION_VALUE_PCT, siehe RiskConfig-Docstring). Enthaelt zusaetzlich Veto-Bedingungen
  (STOP_WRONG_SIDE/STOP_TARGET_INVALID/QUANTITY_TOO_SMALL/UNECONOMICAL_AFTER_COSTS/RRR_TOO_LOW),
  die reject-Modus (== computeRisk()) so nicht kennt - eine echte, im urspruenglichen Konzept
  nicht erwaehnte Asymmetrie zwischen beiden Modi.

sizing_mode selbst ist weiterhin die offene, nicht abschliessend entschiedene Architekturfrage
(siehe TRADING_ENGINE_ARCHITECTURE.md, "Architekturfragen" Punkt 1) - deshalb bewusst als
expliziter Parameter statt hart codiertes Verhalten.
"""

from __future__ import annotations

import math
from typing import Literal

from .models import FeeModel, Position, RiskConfig, Signal, SizingResult

MIN_TRADABLE_QUANTITY = 1


def size_position(
    signal: Signal,
    entry_price_estimate: float,
    risk_cfg: RiskConfig,
    open_positions: list[Position],
    sektor: str,
    region: str,
    sizing_mode: Literal["clamp", "reject"] = "clamp",
    fee_model: FeeModel | None = None,
) -> SizingResult:
    """fee_model ist keine Phase-2-Signatur-Vorgabe, sondern eine notwendige Ergaenzung fuer den
    clamp-Modus: der UNECONOMICAL_AFTER_COSTS-Veto in WF17s sizePosition() braucht
    feesBps/slippageBps, die sonst in keinem der uebergebenen Parameter verfuegbar waeren. Im
    reject-Modus ungenutzt (WF06s computeRisk() kennt diesen Veto nicht)."""
    unit_risk = abs(entry_price_estimate - signal.stop_price)
    if not (unit_risk > 0):
        return SizingResult(quantity=0, position_value=0, risk_amount=0, clamped=False, blocked=True, reason="STOP_WRONG_SIDE")

    if sizing_mode == "reject":
        return _size_position_reject(signal, entry_price_estimate, risk_cfg, unit_risk)
    return _size_position_clamp(signal, entry_price_estimate, risk_cfg, open_positions, sektor, region, unit_risk, fee_model)


def _size_position_reject(signal: Signal, entry_price_estimate: float, risk_cfg: RiskConfig, unit_risk: float) -> SizingResult:
    risk_amount = risk_cfg.model_portfolio_value * (risk_cfg.max_risk_per_trade_pct / 100)
    quantity_by_risk = math.floor(risk_amount / unit_risk)
    max_position_value = risk_cfg.model_portfolio_value * (risk_cfg.max_position_value_pct / 100)
    quantity_by_value = math.floor(max_position_value / entry_price_estimate) if entry_price_estimate > 0 else 0
    quantity = min(quantity_by_risk, quantity_by_value)
    position_value = quantity * entry_price_estimate
    risk_amount_realized = unit_risk * quantity
    return SizingResult(
        quantity=quantity,
        position_value=position_value,
        risk_amount=risk_amount_realized,
        clamped=quantity_by_value < quantity_by_risk,
        blocked=False,
        reason="value" if quantity_by_value < quantity_by_risk else None,
    )


def _size_position_clamp(
    signal: Signal,
    entry_price_estimate: float,
    risk_cfg: RiskConfig,
    open_positions: list[Position],
    sektor: str,
    region: str,
    unit_risk: float,
    fee_model: FeeModel | None,
) -> SizingResult:
    theoretical_risk_amount = risk_cfg.model_portfolio_value * (risk_cfg.max_risk_per_trade_pct / 100)
    risk_based_quantity = math.floor(theoretical_risk_amount / unit_risk)
    if risk_based_quantity <= 0:
        return SizingResult(quantity=0, position_value=0, risk_amount=0, clamped=False, blocked=True, reason="STOP_TARGET_INVALID")

    max_single_position_quantity = math.floor((risk_cfg.model_portfolio_value * (risk_cfg.max_single_position_pct / 100)) / entry_price_estimate)

    current_total_risk = sum(p.risk_amount for p in open_positions)
    remaining_portfolio_risk_budget = max(0.0, risk_cfg.model_portfolio_value * (risk_cfg.max_total_open_risk_pct / 100) - current_total_risk)
    remaining_portfolio_quantity = math.floor(remaining_portfolio_risk_budget / unit_risk)

    current_sector_value = sum(p.position_value for p in open_positions if p.sektor == sektor)
    remaining_sector_value = max(0.0, risk_cfg.model_portfolio_value * (risk_cfg.max_sector_exposure_pct / 100) - current_sector_value)
    remaining_sector_quantity = math.floor(remaining_sector_value / entry_price_estimate)

    current_region_value = sum(p.position_value for p in open_positions if p.region == region)
    remaining_region_value = max(0.0, risk_cfg.model_portfolio_value * (risk_cfg.max_region_exposure_pct / 100) - current_region_value)
    remaining_region_quantity = math.floor(remaining_region_value / entry_price_estimate)

    candidates = [
        (risk_based_quantity, None),
        (max_single_position_quantity, "SINGLE_POSITION_LIMIT"),
        (remaining_portfolio_quantity, "TOTAL_RISK_LIMIT"),
        (remaining_sector_quantity, "SECTOR_LIMIT"),
        (remaining_region_quantity, "REGION_LIMIT"),
    ]
    binding_quantity, binding_reason = candidates[0]
    for quantity, reason in candidates:
        if quantity < binding_quantity:
            binding_quantity, binding_reason = quantity, reason

    final_quantity = max(0, math.floor(binding_quantity))
    if final_quantity < MIN_TRADABLE_QUANTITY:
        return SizingResult(quantity=0, position_value=0, risk_amount=0, clamped=False, blocked=True, reason="QUANTITY_TOO_SMALL")

    position_value = final_quantity * entry_price_estimate
    actual_risk_amount = final_quantity * unit_risk

    if fee_model is not None and fee_model.kind == "fee_bps":
        estimated_fees = position_value * ((fee_model.fee_bps or 0) / 10000)
        estimated_slippage = position_value * ((fee_model.slippage_bps or 0) / 10000)
        if (estimated_fees + estimated_slippage) * 2 > actual_risk_amount:
            return SizingResult(quantity=0, position_value=0, risk_amount=0, clamped=False, blocked=True, reason="UNECONOMICAL_AFTER_COSTS")

    reward_risk_ratio = abs(signal.target_price - entry_price_estimate) / unit_risk if signal.target_price is not None else None
    if reward_risk_ratio is not None and reward_risk_ratio < risk_cfg.min_reward_risk_ratio:
        return SizingResult(quantity=0, position_value=0, risk_amount=0, clamped=False, blocked=True, reason="RRR_TOO_LOW")

    return SizingResult(
        quantity=final_quantity,
        position_value=position_value,
        risk_amount=actual_risk_amount,
        clamped=final_quantity < risk_based_quantity,
        blocked=False,
        reason=binding_reason if final_quantity < risk_based_quantity else None,
    )
