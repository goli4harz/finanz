"""Golden Run (Phase 7 aus TRADING_ENGINE_ARCHITECTURE.md).

Spielt eine feste, deterministische 3-Instrumente/~6-Monate-Kursreihe (fixtures/golden_run_*.json)
Tag fuer Tag durch backtest.step() und vergleicht die daraus resultierenden Kennzahlen exakt
gegen einen gespeicherten Referenzwert (fixtures/golden_run_expected.json). Aendert sich ein
Ergebnis, MUSS dieser Test rot werden - Ziel ist Sichtbarkeit von Verhaltensaenderungen der
Engine, nicht automatische Bestaetigung eines neuen Ergebnisses als "richtig".

WICHTIG (siehe fixtures/generate_golden_run.py): Die Kursreihen sind deterministisch SYNTHETISCH
(fester Zufalls-Seed), nicht echte historische Marktdaten - diese Session hatte keinen
DB-Zugriff. Erfuellt den Regressionstest-Zweck von Phase 7 vollstaendig, ersetzt aber nicht einen
spaeteren echten Golden Run mit echten historischen Daten.
"""

import json
from datetime import date, datetime

import pytest

from trading_engine.backtest import step
from trading_engine.models import Bar, FeeModel, RiskConfig

FIXTURES_DIR = __file__.rsplit("\\", 1)[0] + "\\fixtures"


def _load_fixtures():
    with open(f"{FIXTURES_DIR}/golden_run_bars.json", encoding="utf-8") as f:
        bars_fixture = json.load(f)
    with open(f"{FIXTURES_DIR}/golden_run_config.json", encoding="utf-8") as f:
        config_fixture = json.load(f)
    return bars_fixture, config_fixture


def run_golden_simulation():
    bars_fixture, config = _load_fixtures()
    trading_days = [date.fromisoformat(d) for d in bars_fixture["trading_days"]]
    tickers = list(bars_fixture["tickers"].keys())

    bars_by_ticker = {
        ticker: [Bar(**row) for row in bars_fixture["tickers"][ticker]]
        for ticker in tickers
    }

    risk_cfg = RiskConfig(**config["risk_cfg"])
    fee_model = FeeModel(**config["fee_model"])
    cash = float(config["initial_capital"])
    peak_equity = float(config["initial_capital"])

    pending_orders = []
    open_trades = []
    all_exited = []
    daily_drawdowns = []
    final_portfolio = None

    for i, day in enumerate(trading_days):
        bars_today = {t: bars_by_ticker[t][i] for t in tickers}
        bars_history = {t: bars_by_ticker[t][: i + 1] for t in tickers}
        next_day = trading_days[i + 1] if i + 1 < len(trading_days) else day

        result = step(
            as_of=day, next_trading_day=next_day, tickers_today=tickers,
            bars_today=bars_today, bars_history=bars_history,
            pending_orders=pending_orders, open_trades=open_trades,
            cash=cash, previous_peak_equity=peak_equity,
            risk_cfg=risk_cfg, fee_model=fee_model, rule_version=config["rule_version"],
            ticker_sektor=config["ticker_sektor"], ticker_region=config["ticker_region"],
            ticker_currency=config["ticker_currency"],
        )
        pending_orders = result.still_pending_orders + result.new_orders
        # NUR still_open_trades, NICHT + result.new_trades (new_trades ueberschneidet sich
        # bewusst mit still_open_trades/exited_trades, siehe DayStepResult-Docstring in
        # backtest.py - Verdopplung war der erste echte, vom Golden Run gefundene Bug).
        open_trades = result.still_open_trades
        cash = result.cash
        peak_equity = result.portfolio.peak_equity
        all_exited.extend(result.exited_trades)
        daily_drawdowns.append(result.portfolio.drawdown_pct)
        final_portfolio = result.portfolio

    winning = [e for e in all_exited if e.pnl.net_pnl > 0]
    losing = [e for e in all_exited if e.pnl.net_pnl < 0]
    gross_win = sum(e.pnl.net_pnl for e in winning)
    gross_loss = sum(e.pnl.net_pnl for e in losing)
    r_multiples = [e.pnl.net_pnl / e.trade.risk_amount for e in all_exited if e.trade.risk_amount > 0]

    return {
        "trade_count": len(all_exited),
        "winning_trades": len(winning),
        "losing_trades": len(losing),
        "net_pnl": round(sum(e.pnl.net_pnl for e in all_exited), 2),
        "total_return_pct": round((final_portfolio.total_equity / config["initial_capital"] - 1) * 100, 4),
        "max_drawdown_pct": round(max(daily_drawdowns) if daily_drawdowns else 0.0, 4),
        "profit_factor": round(gross_win / abs(gross_loss), 4) if gross_loss != 0 else None,
        "expectancy_r": round(sum(r_multiples) / len(r_multiples), 4) if r_multiples else None,
        "final_equity": round(final_portfolio.total_equity, 2),
        "open_trades_at_end": len(open_trades),
    }


def test_golden_run_matches_reference_snapshot():
    actual = run_golden_simulation()
    with open(f"{FIXTURES_DIR}/golden_run_expected.json", encoding="utf-8") as f:
        expected = json.load(f)
    assert actual == expected, (
        "Golden-Run-Kennzahlen weichen vom Referenzwert ab - das bedeutet, eine Aenderung an der "
        "Engine hat das Verhalten messbar veraendert. Pruefen, OB die Aenderung beabsichtigt war, "
        "bevor golden_run_expected.json aktualisiert wird (siehe TRADING_ENGINE_ARCHITECTURE.md "
        "Phase 7: 'Nicht automatisch neue Ergebnisse als korrekt akzeptieren')."
    )
