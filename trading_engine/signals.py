"""Technische Signale (Phase 2 aus TRADING_ENGINE_ARCHITECTURE.md).

ENTSCHEIDUNG (2026-08-19, auf Nutzerwunsch): Von den zwei unabhaengig gepflegten
Implementierungen - Workflow 02 ("Technische Analyse (RSI/MACD/BB)", 6 gestaffelte
RSI-Schwellen 25/32/38/62/68/75) und Workflow 17s eigene computeSignals() (nur binaere
RSI-Schwellen 32/68) - wird WF02s feinere Logik hier 1:1 als der neue Standard uebernommen. WF17
verliert dadurch beim Umstieg seine eigene, groebere RSI-Stufung zugunsten von WF02s Version -
eine bewusste Vereinheitlichung, keine Kompromissformel zwischen beiden.

Deckt die 3 rein technischen Strategien ab: mean_reversion (RSI-Extremwert + Bollinger-Band +
EMA20-Abstand, Haertung Welle 1-3 Phase 9: echtes UND aus RSI-Ueberdehnung UND Preisueberdehnung
statt "je fuer sich genuegt"), trend_following (MACD-Kreuzung/Nulllinie/Histogramm +
EMA20-Trendbestaetigung), breakout (echter 52-Wochen-Ausbruch + Volumenbestaetigung, Haertung
Welle 1-3 Phase 9: blosse Naehe zum Hoch/Tief genuegt NICHT mehr).

BEWUSST NICHT UEBERNOMMEN (Vereinfachungen gegenueber dem echten WF02-Code):
- Die vierte Signal.strategy-Auspraegung 'news_event' - die braucht externe Nachrichtendaten,
  die diese Funktionssignatur (nur bars + rule_version) nicht hergibt. Bleibt ausserhalb dieser
  Funktion.
- 52-Wochen-Hoch/-Tief nutzt hier IMMER den highs/lows-Fallback (max/min ueber die uebergebenen
  bars). Der echte WF02-Code bevorzugt echte Yahoo-Finance-Meta-Werte
  (meta.fiftyTwoWeekHigh/-Low) und faellt nur bei fehlenden Metadaten auf highs/lows zurueck -
  diese Metadaten sind hier nicht verfuegbar, da bars nur OHLCV traegt.
- Datenqualitaets-Scoring, Evidence-Texte, Blocker-Objekte, regime_fit - keines davon ist im
  Signal-Datenmodell (Phase 3) vorgesehen, deshalb hier nicht berechnet.
- Bei zu kurzer Historie fuer eine stabile MACD-Berechnung (< 12 gueltige MACD-Werte oder < 2
  Signallinien-Werte) gibt der echte Code ein Fehlerobjekt zurueck; diese Funktion gibt
  stattdessen eine leere Liste zurueck (kein Fehler-Typ im Rueckgabewert vorgesehen).
"""

from __future__ import annotations

from .models import Bar, Signal

STRATEGY_ATR_MULTIPLIERS = {
    "mean_reversion": {"stop": 1.0, "target": 1.5},
    "trend_following": {"stop": 1.5, "target": 2.5},
    "breakout": {"stop": 1.0, "target": 3.0},
}


def _ema(values: list[float], period: int) -> float | None:
    if len(values) < period:
        return None
    k = 2 / (period + 1)
    e = sum(values[:period]) / period
    for v in values[period:]:
        e = v * k + e * (1 - k)
    return e


def _ema_series(values: list[float], period: int) -> list[float | None]:
    if len(values) < period:
        return []
    k = 2 / (period + 1)
    result: list[float | None] = []
    e = sum(values[:period]) / period
    for i, v in enumerate(values):
        if i < period - 1:
            result.append(None)
        elif i == period - 1:
            result.append(e)
        else:
            e = v * k + e * (1 - k)
            result.append(e)
    return result


def _rsi(values: list[float], period: int = 14) -> float | None:
    if len(values) <= period:
        return None
    gains = losses = 0.0
    for i in range(len(values) - period, len(values)):
        diff = values[i] - values[i - 1]
        if diff > 0:
            gains += diff
        else:
            losses += abs(diff)
    avg_gain = gains / period
    avg_loss = losses / period
    if avg_loss == 0:
        return 100.0
    return 100 - (100 / (1 + avg_gain / avg_loss))


def _atr(highs: list[float], lows: list[float], closes: list[float], period: int) -> float | None:
    if len(highs) <= period or len(lows) <= period or len(closes) <= period:
        return None
    n = min(len(highs), len(lows), len(closes))
    true_ranges = []
    for i in range(1, n):
        tr = max(highs[i] - lows[i], abs(highs[i] - closes[i - 1]), abs(lows[i] - closes[i - 1]))
        true_ranges.append(tr)
    if len(true_ranges) < period:
        return None
    atr = sum(true_ranges[:period]) / period
    for tr in true_ranges[period:]:
        atr = (atr * (period - 1) + tr) / period
    return atr


def _strategy_stop_target_entry(strategy: str, direction: str, price: float, atr: float | None) -> tuple[float | None, float | None, float | None, float | None]:
    if direction == "neutral" or atr is None or not (price > 0):
        return None, None, None, None
    m = STRATEGY_ATR_MULTIPLIERS[strategy]
    stop = price - m["stop"] * atr if direction == "long" else price + m["stop"] * atr
    target = price + m["target"] * atr if direction == "long" else price - m["target"] * atr
    entry_buffer = price * 0.003
    entry_low = price - entry_buffer if direction == "long" else price
    entry_high = price if direction == "long" else price + entry_buffer
    return entry_low, entry_high, stop, target


def calculate_signals(bars: list[Bar], rule_version: str) -> list[Signal]:
    """1:1 (siehe Modul-Docstring fuer bewusste Vereinfachungen) aus "Technische Analyse
    (RSI/MACD/BB)" (WF02) uebersetzt. bars muss chronologisch aufsteigend sortiert sein (letzter
    Eintrag = aktueller Tag), wie im Live-Code vorausgesetzt."""
    closes = [b.close for b in bars]
    highs = [b.high for b in bars]
    lows = [b.low for b in bars]
    volumes = [b.volume for b in bars]

    rsi_val = _rsi(closes, 14)
    if rsi_val is None:
        return []

    ema12_series = _ema_series(closes, 12)
    ema26_series = _ema_series(closes, 26)
    macd_series = [e12 - e26 for e12, e26 in zip(ema12_series, ema26_series) if e12 is not None and e26 is not None]
    if len(macd_series) < 12:
        return []
    macd_signal_series_raw = _ema_series(macd_series, 9)
    macd_signal_series = [v for v in macd_signal_series_raw if v is not None]
    if len(macd_signal_series) < 2:
        return []

    atr14 = _atr(highs, lows, closes, 14)
    aktueller_kurs = closes[-1]
    ema20 = _ema(closes, 20)
    trend_aufwaerts = ema20 is not None and aktueller_kurs > ema20

    bb20 = closes[-20:]
    bb_avg = sum(bb20) / 20
    bb_std = (sum((p - bb_avg) ** 2 for p in bb20) / 20) ** 0.5
    bb_oben = bb_avg + 2 * bb_std
    bb_unten = bb_avg - 2 * bb_std
    kurs_bei_oben = aktueller_kurs >= bb_oben * 0.995
    kurs_bei_unten = aktueller_kurs <= bb_unten * 1.005

    macd_val = macd_series[-1]
    macd_prev = macd_series[-2]
    macd_signal_val = macd_signal_series[-1]
    macd_signal_prev = macd_signal_series[-2]
    macd_histogramm = macd_val - macd_signal_val
    macd_histogramm_prev = macd_prev - macd_signal_prev
    macd_kreuzung_bullisch = macd_prev <= macd_signal_prev and macd_val > macd_signal_val
    macd_kreuzung_baerisch = macd_prev >= macd_signal_prev and macd_val < macd_signal_val
    macd_nulllinie_bullisch = macd_prev < 0 and macd_val > 0
    macd_nulllinie_baerisch = macd_prev > 0 and macd_val < 0
    macd_histogramm_verbessert = macd_histogramm > macd_histogramm_prev
    macd_histogramm_verschlechtert = macd_histogramm < macd_histogramm_prev

    # 52-Wochen-Hoch/-Tief: nur highs/lows-Fallback, siehe Modul-Docstring.
    hoch_52w = max(highs) if highs else aktueller_kurs
    tief_52w = min(lows) if lows else aktueller_kurs

    vols = [v for v in volumes if v is not None and v > 0]
    avg_vol = sum(vols) / len(vols) if vols else 0
    last_vol = vols[-1] if vols else 0
    vol_faktor = last_vol / avg_vol if avg_vol > 0 and last_vol > 0 else None
    volumen_erhoeht = vol_faktor is not None and vol_faktor > 1.5
    volumen_ok = vol_faktor is not None and vol_faktor > 1.0

    veraenderung_pct_raw = ((aktueller_kurs - closes[-2]) / closes[-2]) * 100 if len(closes) >= 2 and closes[-2] else 0.0

    # --- Mean-Reversion ---
    mr_score = 0.0
    if rsi_val < 25 or rsi_val > 75:
        mr_score += 0.4
    elif rsi_val < 32 or rsi_val > 68:
        mr_score += 0.25
    elif rsi_val < 38 or rsi_val > 62:
        mr_score += 0.15
    if kurs_bei_oben:
        mr_score += 0.35
    if kurs_bei_unten:
        mr_score += 0.35
    ema_dist_pct = abs(aktueller_kurs - ema20) / ema20 if ema20 and ema20 > 0 else 0
    if ema_dist_pct > 0.01:
        mr_score += min(0.25, ema_dist_pct * 5)
    rsi_ueberdehnt_long = rsi_val < 32
    rsi_ueberdehnt_short = rsi_val > 68
    preis_ueberdehnt_long = kurs_bei_unten or (ema_dist_pct > 0.01 and ema20 is not None and aktueller_kurs < ema20)
    preis_ueberdehnt_short = kurs_bei_oben or (ema_dist_pct > 0.01 and ema20 is not None and aktueller_kurs > ema20)
    mr_direction = "neutral"
    if rsi_ueberdehnt_long and preis_ueberdehnt_long:
        mr_direction = "long"
    elif rsi_ueberdehnt_short and preis_ueberdehnt_short:
        mr_direction = "short"
    mr_entry_low, mr_entry_high, mr_stop, mr_target = _strategy_stop_target_entry("mean_reversion", mr_direction, aktueller_kurs, atr14)

    mean_reversion_signal = Signal(
        strategy="mean_reversion", direction=mr_direction, raw_score=round(min(1, mr_score), 2),
        entry_zone_low=mr_entry_low, entry_zone_high=mr_entry_high, stop_price=mr_stop, target_price=mr_target,
        expected_horizon_days=3, rule_version=rule_version,
    )

    # --- Trend-Following ---
    tf_score = 0.0
    if macd_kreuzung_bullisch or macd_kreuzung_baerisch:
        tf_score += 0.4
    elif macd_nulllinie_bullisch or macd_nulllinie_baerisch:
        tf_score += 0.3
    elif macd_histogramm_verbessert or macd_histogramm_verschlechtert:
        tf_score += 0.15
    macd_momentum_pct = abs(macd_histogramm) / aktueller_kurs if aktueller_kurs > 0 else 0
    tf_score += min(0.3, macd_momentum_pct * 20)
    tf_direction = "neutral"
    if macd_val > macd_signal_val and trend_aufwaerts:
        tf_direction = "long"
    elif macd_val < macd_signal_val and not trend_aufwaerts:
        tf_direction = "short"
    tf_entry_low, tf_entry_high, tf_stop, tf_target = _strategy_stop_target_entry("trend_following", tf_direction, aktueller_kurs, atr14)

    trend_following_signal = Signal(
        strategy="trend_following", direction=tf_direction, raw_score=round(min(1, tf_score), 2),
        entry_zone_low=tf_entry_low, entry_zone_high=tf_entry_high, stop_price=tf_stop, target_price=tf_target,
        expected_horizon_days=15, rule_version=rule_version,
    )

    # --- Breakout ---
    bo_score = 0.0
    bo_direction = "neutral"
    dist_zu_hoch = (hoch_52w - aktueller_kurs) / hoch_52w if hoch_52w > 0 else 1
    dist_zu_tief = (aktueller_kurs - tief_52w) / tief_52w if tief_52w > 0 else 1
    tatsaechlicher_ausbruch_long = aktueller_kurs >= hoch_52w
    tatsaechlicher_ausbruch_short = tief_52w > 0 and aktueller_kurs <= tief_52w
    volumen_bestaetigt = volumen_erhoeht or volumen_ok
    if tatsaechlicher_ausbruch_long and volumen_bestaetigt:
        bo_score += 0.4
        bo_direction = "long"
    if tatsaechlicher_ausbruch_short and volumen_bestaetigt:
        bo_score += 0.4
        bo_direction = "short"
    if volumen_erhoeht:
        bo_score += 0.35
    elif volumen_ok:
        bo_score += 0.15
    if abs(veraenderung_pct_raw) > 2.5:
        bo_score += 0.25
    bo_entry_low, bo_entry_high, bo_stop, bo_target = _strategy_stop_target_entry("breakout", bo_direction, aktueller_kurs, atr14)

    breakout_signal = Signal(
        strategy="breakout", direction=bo_direction, raw_score=round(min(1, bo_score), 2),
        entry_zone_low=bo_entry_low, entry_zone_high=bo_entry_high, stop_price=bo_stop, target_price=bo_target,
        expected_horizon_days=7, rule_version=rule_version,
    )

    return [mean_reversion_signal, trend_following_signal, breakout_signal]
