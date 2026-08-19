"""Portfolio-Risikolimits (Phase 2 aus TRADING_ENGINE_ARCHITECTURE.md).

Loest WF14 Job A ab (checkHardLimits() in WF17 deckt heute nur 5 von 9 Limits ab - siehe
Phase-1-Tabelle "Risikolimits (Portfolio)"). Bewusst getrennt von position_sizing.py: Sizing
(Kappen/Verwerfen einer Einzelposition) und Portfolio-Limit-Pruefung (Blockieren wegen
Gesamtportfolio-Zustand) sind zwei fachlich unterschiedliche Operationen mit unterschiedlichem
Scope, die WF14 bereits in Job A vs. WF06 trennt.

Alle 9 Limits aus Job A gehoeren hierher: MAX_TOTAL_OPEN_RISK_PCT (inkl.
STRESS_RISK_REDUCTION_FACTOR), MAX_SECTOR_EXPOSURE_PCT, MAX_SINGLE_POSITION_PCT,
MAX_OPEN_POSITIONS, MAX_DIRECTIONAL_EXPOSURE_PCT, MAX_PORTFOLIO_DRAWDOWN_PCT,
MAX_PAIRWISE_CORRELATION, MAX_REGION_EXPOSURE_PCT, MAX_NON_EUR_EXPOSURE_PCT.

NOTWENDIGE SIGNATURERWEITERUNG gegenueber Phase 2 des Konzepts: Die dort vorgesehene Signatur
`check_portfolio_limits(candidate: SizingResult, portfolio, risk_cfg, correlation_data)` reicht
nicht aus, um Job A 1:1 zu uebersetzen - SizingResult (quantity/position_value/risk_amount/
clamped/blocked/reason) traegt weder Ticker noch Sektor/Region/Waehrung/Richtung des Kandidaten,
die Job A fuer 5 der 9 Limits zwingend braucht (Sektor-/Region-/Waehrungs-/Richtungs-Exposition,
Korrelation). Deshalb hier um `ticker`/`sektor`/`region`/`currency`/`direction` ergaenzt.

BEWUSST NICHT UEBERNOMMEN: Job A prueft zusaetzlich STRATEGY_DEACTIVATED (Strategie global per
Lernvorschlag deaktiviert) - das ist kein numerisches Risikolimit, sondern ein Aktivierungs-Flag
aus einer voellig anderen Datenquelle (strategy_status, ausserhalb von RiskConfig/PortfolioState).
Gehoert fachlich nicht in risk_limits.py und bleibt hier bewusst aussen vor.
"""

from __future__ import annotations

from typing import Literal

from .models import Blocker, PortfolioState, RiskConfig, SizingResult


def _pearson(a: list[float], b: list[float]) -> float | None:
    """1:1 aus pearson() in WF14 Job A uebersetzt (Mindestlaenge 10, sonst None)."""
    n = min(len(a), len(b))
    if n < 10:
        return None
    av, bv = a[-n:], b[-n:]
    mean_a = sum(av) / n
    mean_b = sum(bv) / n
    cov = sum((av[i] - mean_a) * (bv[i] - mean_b) for i in range(n))
    var_a = sum((x - mean_a) ** 2 for x in av)
    var_b = sum((x - mean_b) ** 2 for x in bv)
    if var_a == 0 or var_b == 0:
        return None
    return cov / (var_a * var_b) ** 0.5


def check_portfolio_limits(
    candidate: SizingResult,
    ticker: str,
    sektor: str,
    region: str,
    currency: str,
    direction: Literal["long", "short"],
    portfolio: PortfolioState,
    risk_cfg: RiskConfig,
    is_stress_regime: bool = False,
    correlation_data: dict[str, list[float]] | None = None,
) -> list[Blocker]:
    """1:1 aus "Job A: Portfoliopruefung + Trade-Anlage" (WF14) uebersetzt (ausser
    STRATEGY_DEACTIVATED, siehe Modul-Docstring). Gibt einen Blocker pro verletztem Limit zurueck
    (leere Liste = genehmigt) - Job A macht daraus `approved = blockers.length === 0`."""
    blockers: list[Blocker] = []
    mpv = risk_cfg.model_portfolio_value
    open_positions = portfolio.open_positions

    risk_before = sum(p.risk_amount for p in open_positions)
    risk_after = risk_before + candidate.risk_amount
    portfolio_risk_after_pct = (risk_after / mpv) * 100 if mpv > 0 else 0
    effective_max_total_risk_pct = (
        risk_cfg.max_total_open_risk_pct * risk_cfg.stress_risk_reduction_factor
        if is_stress_regime
        else risk_cfg.max_total_open_risk_pct
    )
    if portfolio_risk_after_pct > effective_max_total_risk_pct:
        blockers.append(Blocker(limit_name="TOTAL_RISK_LIMIT", reason="Gesamtes offenes Stoprisiko ueberschreitet das Limit" + (" (stressreduziert)" if is_stress_regime else ""), current_value=portfolio_risk_after_pct, limit_value=effective_max_total_risk_pct))

    sektor_wert = sum(p.position_value for p in open_positions if p.sektor == sektor) + candidate.position_value
    sektor_pct = (sektor_wert / mpv) * 100 if mpv > 0 else 0
    if sektor_pct > risk_cfg.max_sector_exposure_pct:
        blockers.append(Blocker(limit_name="SECTOR_LIMIT", reason=f"Sektor {sektor} ueberschreitet das Limit", current_value=sektor_pct, limit_value=risk_cfg.max_sector_exposure_pct))

    region_wert = sum(p.position_value for p in open_positions if p.region == region) + candidate.position_value
    region_pct = (region_wert / mpv) * 100 if mpv > 0 else 0
    if region_pct > risk_cfg.max_region_exposure_pct:
        blockers.append(Blocker(limit_name="REGION_LIMIT", reason=f"Region {region} ueberschreitet das Limit", current_value=region_pct, limit_value=risk_cfg.max_region_exposure_pct))

    if currency != "EUR":
        non_eur_wert = sum(p.position_value for p in open_positions if p.currency != "EUR") + candidate.position_value
        non_eur_pct = (non_eur_wert / mpv) * 100 if mpv > 0 else 0
        if non_eur_pct > risk_cfg.max_non_eur_exposure_pct:
            blockers.append(Blocker(limit_name="CURRENCY_LIMIT", reason=f"Nicht-EUR-Exposition ({currency}) ueberschreitet das Limit", current_value=non_eur_pct, limit_value=risk_cfg.max_non_eur_exposure_pct))

    einzel_anteil_pct = (candidate.position_value / mpv) * 100 if mpv > 0 else 0
    if einzel_anteil_pct > risk_cfg.max_single_position_pct:
        blockers.append(Blocker(limit_name="SINGLE_POSITION_LIMIT", reason="Einzelposition ueberschreitet das Limit", current_value=einzel_anteil_pct, limit_value=risk_cfg.max_single_position_pct))

    if len(open_positions) + 1 > risk_cfg.max_open_positions:
        blockers.append(Blocker(limit_name="MAX_OPEN_POSITIONS", reason="Maximale Anzahl offener Positionen bereits erreicht", current_value=len(open_positions) + 1, limit_value=risk_cfg.max_open_positions))

    richtung_wert = sum(p.position_value for p in open_positions if p.direction == direction) + candidate.position_value
    richtung_pct = (richtung_wert / mpv) * 100 if mpv > 0 else 0
    if richtung_pct > risk_cfg.max_directional_exposure_pct:
        blockers.append(Blocker(limit_name="DIRECTIONAL_LIMIT", reason="Richtungs-Exposition ueberschreitet das Limit", current_value=richtung_pct, limit_value=risk_cfg.max_directional_exposure_pct))

    if portfolio.drawdown_pct > risk_cfg.max_portfolio_drawdown_pct:
        blockers.append(Blocker(limit_name="DRAWDOWN_LIMIT", reason="Aktueller Portfolio-Drawdown ueberschreitet das Limit - keine neuen Eroeffnungen", current_value=portfolio.drawdown_pct, limit_value=risk_cfg.max_portfolio_drawdown_pct))

    if correlation_data is not None:
        candidate_returns = correlation_data.get(ticker)
        if candidate_returns:
            max_corr, max_corr_ticker = None, None
            for position in open_positions:
                if position.ticker == ticker:
                    continue
                other_returns = correlation_data.get(position.ticker)
                if not other_returns:
                    continue
                corr = _pearson(candidate_returns, other_returns)
                if corr is not None and (max_corr is None or abs(corr) > abs(max_corr)):
                    max_corr, max_corr_ticker = corr, position.ticker
            if max_corr is not None and abs(max_corr) > risk_cfg.max_pairwise_correlation:
                blockers.append(Blocker(limit_name="CORRELATION_LIMIT", reason=f"Hohe Korrelation ({max_corr:.2f}) zu bereits offener Position {max_corr_ticker}", current_value=abs(max_corr), limit_value=risk_cfg.max_pairwise_correlation))

    return blockers
