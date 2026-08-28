"""Tests fuer calculate_signals() und die internen Indikator-Helfer (trading_engine/signals.py).

Untere Ebene (_rsi/_ema/_atr) gegen bekannte Lehrbuch-/Handrechnungswerte exakt geprueft - das
sind die fehleranfaelligsten Bausteine. calculate_signals() selbst gegen synthetische, bewusst
extreme Kursverlaeufe qualitativ geprueft (Richtung/Score-Groessenordnung), da ein exakter
Soll-Wert ohne echte Marktdaten kaum sinnvoll vorherzuberechnen ist.
"""

from trading_engine.models import Bar
from trading_engine.signals import _atr, _ema, _ema_series, _rsi, calculate_signals


def make_bars(closes, highs=None, lows=None, volumes=None, start="2026-01-01"):
    from datetime import date, timedelta
    start_date = date.fromisoformat(start)
    highs = highs or [c * 1.01 for c in closes]
    lows = lows or [c * 0.99 for c in closes]
    volumes = volumes or [1_000_000] * len(closes)
    return [
        Bar(ticker="TEST", trading_date=start_date + timedelta(days=i), open=c, high=h, low=l, close=c, volume=v)
        for i, (c, h, l, v) in enumerate(zip(closes, highs, lows, volumes))
    ]


# --- _rsi: klassisches Lehrbuchbeispiel (Wilder), 14 Perioden ---

def test_rsi_all_gains_is_100():
    closes = [100 + i for i in range(20)]  # streng monoton steigend
    assert _rsi(closes, 14) == 100.0


def test_rsi_symmetric_gain_loss_pattern():
    # 7 Tage +1, 7 Tage -1 im Wechsel -> gleich viele/grosse Gewinne wie Verluste -> RSI = 50.
    closes = [100]
    for _ in range(14):
        closes.append(closes[-1] + 1)
        closes.append(closes[-1] - 1)
    rsi = _rsi(closes[-15:], 14)
    assert abs(rsi - 50.0) < 0.01


def test_rsi_insufficient_data_returns_none():
    assert _rsi([100, 101, 102], 14) is None


# --- _ema ---

def test_ema_constant_series_equals_constant():
    closes = [100.0] * 30
    assert _ema(closes, 12) == 100.0


def test_ema_insufficient_data_returns_none():
    assert _ema([100, 101], 20) is None


def test_ema_series_length_matches_input():
    closes = [100 + i * 0.5 for i in range(30)]
    series = _ema_series(closes, 12)
    assert len(series) == 30
    assert series[10] is None  # vor Periode 12 -> kein Wert
    assert series[11] is not None


# --- _atr ---

def test_atr_constant_range_matches_true_range():
    # Konstante Tagesspanne (high-low=2, keine Gaps) -> ATR konvergiert exakt auf 2.
    closes = [100.0] * 20
    highs = [101.0] * 20
    lows = [99.0] * 20
    atr = _atr(highs, lows, closes, 14)
    assert abs(atr - 2.0) < 0.001


def test_atr_insufficient_data_returns_none():
    assert _atr([101, 102], [99, 100], [100, 101], 14) is None


# --- calculate_signals: Integrationstests ---

def test_insufficient_history_returns_empty_list():
    bars = make_bars([100, 101, 102, 101, 100])
    assert calculate_signals(bars, "test-v1") == []


def test_returns_three_strategy_signals_on_sufficient_history():
    # Leicht schwankende, aber grundsaetzlich flache Kursreihe -> genug Historie fuer MACD/RSI/EMA.
    closes = [100 + (i % 5) * 0.3 for i in range(60)]
    bars = make_bars(closes)
    signals = calculate_signals(bars, "test-v1")
    assert len(signals) == 3
    assert {s.strategy for s in signals} == {"mean_reversion", "trend_following", "breakout"}
    for s in signals:
        assert s.rule_version == "test-v1"
        assert 0 <= s.raw_score <= 1


def test_mean_reversion_long_on_oversold_dip_within_primary_uptrend():
    # FIX 2026-08-28 (#3): MR-long feuert nur, wenn der Primaertrend (SMA50 >= SMA100) aufwaerts
    # zeigt. Szenario: langer Aufwaertstrend, dann ein scharfer kurzer Ruecksetzer am Ende ->
    # RSI < 28 UND Kurs am/unter dem unteren Bollinger-Band, SMA50 weiterhin > SMA100.
    closes = [100.0]
    for _ in range(100):
        closes.append(closes[-1] * 1.004)  # stetiger Aufwaertstrend, SMA50 > SMA100
    for _ in range(7):
        closes.append(closes[-1] * 0.965)  # kurzer scharfer Ruecksetzer (dreht 50/100 nicht)
    bars = make_bars(closes)
    signals = calculate_signals(bars, "test-v1")
    mr = next(s for s in signals if s.strategy == "mean_reversion")
    assert mr.direction == "long"
    assert mr.stop_price is not None and mr.stop_price < closes[-1]
    assert mr.target_price is not None and mr.target_price > closes[-1]


def test_mean_reversion_neutral_on_oversold_in_primary_downtrend():
    # FIX 2026-08-28 (#3): dieselbe RSI-/Bollinger-Ueberdehnung, aber im Abwaertstrend
    # (SMA50 < SMA100) -> KEIN MR-long (kein "fallendes Messer" fangen). Vorher loeste genau
    # dieses Szenario faelschlich long aus.
    closes = [100.0]
    for _ in range(45):
        closes.append(closes[-1] * 0.995)  # stetiger Abwaertstrend
    closes.append(closes[-1] * 0.85)  # scharfer finaler Einbruch
    bars = make_bars(closes)
    signals = calculate_signals(bars, "test-v1")
    mr = next(s for s in signals if s.strategy == "mean_reversion")
    assert mr.direction == "neutral"


def test_mean_reversion_neutral_without_price_overextension():
    # Leichtes, symmetrisches Auf-und-Ab um 100 (RSI nahe 50, Kurs mittig im Bollinger-Band,
    # kein nennenswerter EMA20-Abstand) -> keines der beiden UND-Kriterien greift -> neutral.
    # (Eine wirklich KONSTANTE Reihe erzeugt stattdessen den bekannten RSI-0/0-Grenzfall
    # avgLoss==0 -> RSI=100 - identisch zum echten WF02-Code, kein Uebersetzungsfehler, aber
    # fuer diesen Testfall ungeeignet.)
    closes = [100.0]
    for i in range(40):
        closes.append(closes[-1] + (0.3 if i % 2 == 0 else -0.3))
    bars = make_bars(closes)
    signals = calculate_signals(bars, "test-v1")
    mr = next(s for s in signals if s.strategy == "mean_reversion")
    assert mr.direction == "neutral"
    assert mr.stop_price is None and mr.target_price is None


def test_breakout_long_on_actual_breakout_with_volume_confirmation():
    closes = [100.0] * 45 + [110.0]  # letzter Kurs ueber allem Vorherigen -> echter 52w-Ausbruch
    volumes = [1_000_000] * 45 + [2_000_000]  # Volumen deutlich erhoeht am Ausbruchstag
    # Am Ausbruchstag high==close setzen (kein Aufschlag) - sonst waere der 52-Wochen-Hoch-Wert
    # (Maximum ueber ALLE highs, inkl. des heutigen Tages) durch den Test-Default high=close*1.01
    # immer minimal ueber dem heutigen Close und ein "Ausbruch ueber das 52w-Hoch" koennte an
    # dieser synthetischen Kursreihe nie ausgeloest werden - ein Artefakt des Testaufbaus, kein
    # Verhalten des echten Codes.
    highs = [c * 1.01 for c in closes[:-1]] + [closes[-1]]
    bars = make_bars(closes, highs=highs, volumes=volumes)
    signals = calculate_signals(bars, "test-v1")
    bo = next(s for s in signals if s.strategy == "breakout")
    assert bo.direction == "long"
    assert bo.raw_score > 0.5


def test_breakout_neutral_near_high_without_confirmation():
    # Kurs nahe, aber nicht ueber dem bisherigen Hoch, normales Volumen -> kein bestaetigter Ausbruch.
    closes = [100.0] * 45 + [100.5]
    bars = make_bars(closes)
    signals = calculate_signals(bars, "test-v1")
    bo = next(s for s in signals if s.strategy == "breakout")
    assert bo.direction == "neutral"
