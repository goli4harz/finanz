"""Pydantic-Datenmodelle der Trading-Engine (Phase 3 aus TRADING_ENGINE_ARCHITECTURE.md).

Wird von beiden Aufrufern (Workflow 14 "Portfolio-Risiko und Paper-Trading" und Workflow 17
"Historische Simulation") ueber den FastAPI-Dienst verwendet. Pydantic statt Dataclasses fuer
Konsistenz mit app.py und kostenlose Validierung/JSON-(De-)Serialisierung an der API-Grenze.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel

AmbiguousBarPolicy = Literal["conservative_stop_first", "conservative_target_first"]


class Bar(BaseModel):
    ticker: str
    trading_date: date
    open: float
    high: float
    low: float
    close: float
    volume: float


class Signal(BaseModel):
    strategy: Literal["mean_reversion", "trend_following", "breakout", "news_event"]
    direction: Literal["long", "short", "neutral"]
    raw_score: float
    entry_zone_low: float | None
    entry_zone_high: float | None
    stop_price: float | None
    target_price: float | None
    expected_horizon_days: int
    rule_version: str


class Order(BaseModel):
    ticker: str
    direction: Literal["long", "short"]
    entry_zone_low: float
    entry_zone_high: float
    stop_price: float
    target_price: float
    quantity: int
    intended_execution_date: date
    # Nicht in Phase 3 des Konzepts gelistet: backtest.step() (Phase 2) braucht diese Felder, um
    # bei Fill eine vollstaendige Trade/Position anzulegen (WF17s echtes Order-Objekt traegt
    # exakt dieselben Felder, siehe "let pendingOrders = pendingOrdersRaw.map(...)").
    strategy: str = ""
    sektor: str = "unbekannt"
    region: str = "global"
    risk_amount: float = 0.0
    time_stop_at: date | None = None
    # FIX 2026-08-20 (Phase-8-Migration, WF17-Persistenz): "Baue SQL fuer Paket-Ergebnisse"
    # braucht theoretical_quantity/theoretical_risk_amount/clamp_reason als eigene Audit-Spalten
    # auf simulation_orders/simulation_trades (WF17s eigenes Order-Objekt traegt exakt dieselben
    # Felder). SizingResult (position_sizing.py) berechnet risk_based_quantity/
    # theoretical_risk_amount bereits intern, gab sie aber nicht nach aussen - ohne diese Felder
    # wuerde der Audit-Trail beim Umstieg auf die Engine stillschweigend verloren gehen.
    theoretical_quantity: int = 0
    theoretical_risk_amount: float = 0.0
    clamp_reason: str | None = None


class Trade(BaseModel):
    trade_id: str
    ticker: str
    direction: Literal["long", "short"]
    entry_price: float
    stop_price_current: float
    target_price: float
    quantity: int
    extreme_price_since_entry: float
    trail_distance: float
    entry_day: date
    # Nicht in Phase 3 des Konzepts gelistet, aber von checkExit() im echten WF17-Live-Code
    # verwendet (time_stop-Exit-Grund) - ergaenzt, damit evaluate_exit() den echten Code 1:1
    # abbilden kann statt nur einen Teil davon.
    time_stop_at: date | None = None
    # Nicht in Phase 3 des Konzepts gelistet: backtest.step() braucht diese Felder, um aus einem
    # offenen Trade die fuer size_position()/check_portfolio_limits() noetige Position-Sicht
    # abzuleiten (Sektor/Region/Risikobetrag), ohne sie separat vorhalten zu muessen - WF17s
    # eigenes openPositions-Objekt traegt dieselben Felder direkt am Trade.
    strategy: str = ""
    sektor: str = "unbekannt"
    region: str = "global"
    risk_amount: float = 0.0
    # FIX 2026-08-20 (Phase-8-Migration): siehe identischer Kommentar auf Order oben - beim
    # Order-Fill (backtest.step()) muessen diese Felder vom Order auf den entstehenden Trade
    # durchgereicht werden, sonst sind sie fuer newTradeRows nicht mehr verfuegbar.
    theoretical_quantity: int = 0
    theoretical_risk_amount: float = 0.0
    clamp_reason: str | None = None


class Position(BaseModel):
    ticker: str
    direction: Literal["long", "short"]
    quantity: int
    position_value: float
    sektor: str
    region: str
    # Nicht in Phase 3 des Konzepts gelistet: check_portfolio_limits() (risk_limits.py) braucht
    # die Waehrung fuer den CURRENCY_LIMIT-Check aus WF14 Job A (Nicht-EUR-Exposition).
    currency: str = "EUR"
    # Nicht in Phase 3 des Konzepts gelistet: WF17s sizePosition() summiert das verbleibende
    # Gesamtrisikobudget ueber `openPositionsState.reduce((sum,p) => sum + p.risk_amount, 0)`,
    # NICHT ueber position_value - beide Werte sind fachlich unterschiedlich (risk_amount ist das
    # bei Entry festgelegte Risiko bis zum Stop, position_value der volle Positionswert). Ohne
    # dieses Feld waere size_position() im clamp-Modus fachlich falsch.
    risk_amount: float = 0.0


class PortfolioState(BaseModel):
    cash: float
    positions_value: float
    total_equity: float
    peak_equity: float
    drawdown_pct: float
    open_positions: list[Position]


class ExecutionResult(BaseModel):
    filled: bool = False
    exit: bool = False
    price: float | None = None
    reason: str | None = None
    ambiguous: bool = False
    gap_through_stop: bool = False


class RiskConfig(BaseModel):
    model_portfolio_value: float
    max_risk_per_trade_pct: float
    max_total_open_risk_pct: float
    max_sector_exposure_pct: float
    max_single_position_pct: float
    max_open_positions: int
    max_directional_exposure_pct: float
    max_portfolio_drawdown_pct: float
    max_pairwise_correlation: float
    max_region_exposure_pct: float
    max_non_eur_exposure_pct: float
    stress_risk_reduction_factor: float
    # Nicht in Phase 3 des Konzepts gelistet, aber von size_position() (Phase 2) fuer beide
    # sizing_mode-Zweige benoetigt und im echten Code zwei GENUINE unterschiedliche Config-Keys
    # (nicht dasselbe Limit unter zwei Namen, siehe sql/029/036/055): max_position_value_pct wird
    # nur von WF06s computeRisk() (sizing_mode='reject') als Zweitgrenze neben dem Risiko-Limit
    # verwendet, max_single_position_pct (oben) nur von WF17s sizePosition()
    # (sizing_mode='clamp') als portfolio-bewusste Haertegrenze.
    max_position_value_pct: float
    min_reward_risk_ratio: float


class StrategyConfig(BaseModel):
    atr_stop_multiplier: float
    atr_target_multiplier: float
    expected_horizon_days: int
    rule_version: str


class FeeModel(BaseModel):
    kind: Literal["fee_bps", "mini_future"]
    fee_bps: float | None = None
    slippage_bps: float | None = None
    mini_future_leverage: float | None = None
    mini_future_spread_pct: float | None = None
    mini_future_financing_pct_pa: float | None = None


class SimulationConfig(BaseModel):
    run_id: str
    initial_capital: float
    strategy_filter: str | None
    ambiguous_bar_policy: AmbiguousBarPolicy
    fee_model: FeeModel


class ConfigSnapshot(BaseModel):
    values: dict[str, float]
    loaded_at: datetime

    @classmethod
    def from_rows(cls, rows: list[dict]) -> "ConfigSnapshot":
        raise NotImplementedError

    def get(self, key: str, default: float) -> float:
        raise NotImplementedError


class SizingResult(BaseModel):
    """Nicht explizit in Phase 3 spezifiziert, aber von size_position()/check_portfolio_limits()
    (Phase 2) referenziert. Felder orientiert an WF06s theoretical_quantity/risk_amount/
    position_value und WF17s sizePosition()-Rueckgabe."""

    quantity: int
    position_value: float
    risk_amount: float
    clamped: bool
    blocked: bool
    reason: str | None = None
    # FIX 2026-08-20 (Phase-8-Migration): WF17s sizePosition() gibt bei Erfolg zusaetzlich die
    # UNGEKAPPTE (theoretische) Stueckzahl/Risikosumme zurueck - Audit-Trail, um sichtbar zu
    # machen, WIE STARK ein Trade tatsaechlich gekappt wurde. _size_position_clamp() berechnet
    # risk_based_quantity/theoretical_risk_amount bereits intern, gab sie bisher aber nicht nach
    # aussen. Nur auf dem Erfolgspfad sinnvoll befuellt (0 bei blocked=True, wie im Live-Code -
    # dort entsteht bei einem Veto ohnehin keine Order).
    theoretical_quantity: int = 0
    theoretical_risk_amount: float = 0.0


class Blocker(BaseModel):
    """Nicht explizit in Phase 3 spezifiziert, aber von check_portfolio_limits() (Phase 2)
    referenziert. Ein Blocker pro verletztem Portfolio-Limit (siehe Phase-1-Tabelle, WF14 Job A:
    9 Limits)."""

    limit_name: str
    reason: str
    current_value: float
    limit_value: float


class TradePnl(BaseModel):
    """Nicht explizit in Phase 3 spezifiziert, aber von calculate_trade_pnl() (Phase 2)
    referenziert. Feldaufteilung folgt der in Phase 1 dokumentierten Formel:
    net_pnl = gross_pnl - entry_fee - entry_slippage - exit_fee - exit_slippage - financing_cost."""

    gross_pnl: float
    entry_fee: float
    entry_slippage: float
    exit_fee: float
    exit_slippage: float
    financing_cost: float
    net_pnl: float
