"""Erzeugt die drei Golden-Run-Fixtures fuer die Trading-Engine (Phase 7).

WICHTIGER HINWEIS: Diese Session hat keinen Zugriff auf die echte Marktdaten-DB - die
Kursreihen hier sind DETERMINISTISCH SYNTHETISCH (fester Seed, kein echter historischer Verlauf),
nicht die "echten" 3 Instrumente/6 Monate aus dem Auftrag. Das erfuellt trotzdem den Zweck von
Phase 7 (reproduzierbarer Regressionstest, der eine Aenderung an der Engine sichtbar macht) -
aber es ist kein Ersatz fuer einen spaeteren echten Golden Run mit echten historischen Daten,
sobald DB-Zugriff verfuegbar ist.

Drei Ticker mit bewusst unterschiedlichem Charakter, damit alle drei Strategien (mean_reversion/
trend_following/breakout) im Lauf mindestens einmal ausgeloest werden:
- GOLD_A: oszillierend um einen Mittelwert (Ziel: mean_reversion-Trades)
- GOLD_B: stetiger Aufwaertstrend (Ziel: trend_following-Trades)
- GOLD_C: lange flach, dann ein echter Ausbruch (Ziel: breakout-Trade)

Nach einer Aenderung an dieser Datei (z.B. neue Kursreihen) muss golden_run_expected.json
NEU generiert werden (test_golden_run.run_golden_simulation() einmal laufen lassen und das
Ergebnis bewusst pruefen, nicht blind uebernehmen - siehe TRADING_ENGINE_ARCHITECTURE.md Phase 7).
"""
import json
import math
import random
from datetime import date, timedelta

OUT_DIR = __file__.rsplit("\\", 1)[0]
N_DAYS = 130  # ~6 Handelsmonate
START = date(2025, 1, 2)

rng = random.Random(1234)


def business_days(start, n):
    days = []
    d = start
    while len(days) < n:
        if d.weekday() < 5:
            days.append(d)
        d += timedelta(days=1)
    return days


dates = business_days(START, N_DAYS)


def make_series_mean_reverting(base=100.0, amplitude=8.0, noise=0.4):
    closes = []
    for i in range(N_DAYS):
        cyc = base + amplitude * math.sin(i / 9.0)
        closes.append(round(cyc + rng.uniform(-noise, noise), 2))
    return closes


def make_series_trending(base=100.0, drift=0.35, noise=0.6):
    closes = []
    price = base
    for i in range(N_DAYS):
        price += drift + rng.uniform(-noise, noise)
        closes.append(round(price, 2))
    return closes


def make_series_flat_then_breakout(base=100.0, flat_noise=0.3, breakout_day=100, breakout_jump=18.0):
    closes = []
    price = base
    for i in range(N_DAYS):
        if i < breakout_day:
            price = base + rng.uniform(-flat_noise, flat_noise)
        elif i == breakout_day:
            price = base + breakout_jump
        else:
            price += rng.uniform(-0.5, 0.8)
        closes.append(round(price, 2))
    return closes


def closes_to_bars(ticker, closes):
    bars = []
    for i, c in enumerate(closes):
        prev = closes[i - 1] if i > 0 else c
        daily_range = abs(c - prev) + 0.6
        high = round(max(c, prev) + daily_range * 0.3, 2)
        low = round(min(c, prev) - daily_range * 0.3, 2)
        open_ = round(prev, 2)
        volume = 1_000_000 + int(abs(c - prev) * 50_000)
        bars.append({
            "ticker": ticker, "trading_date": dates[i].isoformat(),
            "open": open_, "high": high, "low": low, "close": c, "volume": volume,
        })
    return bars


if __name__ == "__main__":
    series = {
        "GOLD_A": closes_to_bars("GOLD_A", make_series_mean_reverting()),
        "GOLD_B": closes_to_bars("GOLD_B", make_series_trending()),
        "GOLD_C": closes_to_bars("GOLD_C", make_series_flat_then_breakout()),
    }

    bars_fixture = {"tickers": series, "trading_days": [d.isoformat() for d in dates]}

    config_fixture = {
        "initial_capital": 25000,
        "rule_version": "golden-run-v1",
        "fee_model": {"kind": "mini_future", "mini_future_leverage": 5, "mini_future_spread_pct": 0.5, "mini_future_financing_pct_pa": 3.0},
        "risk_cfg": {
            "model_portfolio_value": 25000, "max_risk_per_trade_pct": 1.0, "max_total_open_risk_pct": 6.0,
            "max_sector_exposure_pct": 40.0, "max_single_position_pct": 25.0, "max_open_positions": 5,
            "max_directional_exposure_pct": 80.0, "max_portfolio_drawdown_pct": 25.0, "max_pairwise_correlation": 0.9,
            "max_region_exposure_pct": 100.0, "max_non_eur_exposure_pct": 100.0, "stress_risk_reduction_factor": 0.5,
            "max_position_value_pct": 25.0, "min_reward_risk_ratio": 0.5,
        },
        "ticker_sektor": {"GOLD_A": "Tech", "GOLD_B": "Tech", "GOLD_C": "Health"},
        "ticker_region": {"GOLD_A": "US", "GOLD_B": "US", "GOLD_C": "EU"},
        "ticker_currency": {"GOLD_A": "EUR", "GOLD_B": "EUR", "GOLD_C": "EUR"},
    }

    with open(f"{OUT_DIR}/golden_run_bars.json", "w", encoding="utf-8") as f:
        json.dump(bars_fixture, f, indent=2)
    with open(f"{OUT_DIR}/golden_run_config.json", "w", encoding="utf-8") as f:
        json.dump(config_fixture, f, indent=2)

    print("fixtures written:", len(dates), "days,", list(series.keys()))
