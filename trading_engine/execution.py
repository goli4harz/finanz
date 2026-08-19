"""Fill-/Exit-/Trailing-Stop-Ausfuehrung (Phase 2 aus TRADING_ENGINE_ARCHITECTURE.md).

simulate_entry() loest die praktisch identische Zone-Touch-Logik aus WF14
(zone_touch_conservative) und WF17 (simulateEntryFill()) ab - einer der wenigen Bereiche mit
echter 1:1-Uebereinstimmung, siehe Phase-1-Tabelle "Entry/Fill".

evaluate_exit() loest WF14s Stop/Target-Beruehrung + Gap-Handling (stopRawExitPrice(), Haertung
Welle 1-3 Phase 5) und WF17s checkExit() ab (bereits identische Semantik: gapThroughStop-Flag,
ambiguousBarPolicyCode).

WICHTIGER INVARIANT (P17-6, in dieser Session bereits im n8n-Live-Code von WF17 gefixt, siehe
FINAL_REVIEW.md): Ein aus der heutigen Kerze neu berechneter Trailing Stop darf NICHT rueckwirkend
fuer dieselbe Kerze gelten (Look-Ahead-Bias). evaluate_exit() MUSS mit dem Stop-Stand VOR der
heutigen update_trailing_stop()-Nachfuehrung aufgerufen werden; die Nachfuehrung wirkt sich erst
auf die naechste Kerze aus. Aufrufreihenfolge pro Tag: 1) evaluate_exit() mit altem Stop,
2) NUR falls kein Exit -> update_trailing_stop() (im echten WF17-Code steht die Nachfuehrung
explizit in einem `if (!exitCheck.exit)`-Zweig - eine bereits exitende Position bekommt keinen
neuen Trailing-Stop mehr).

Korrektur der in der vorigen Session dokumentierten Inkonsistenz: update_trailing_stop() ist hier
jetzt Trade -> Trade signiert (nicht Position -> Position wie im urspruenglichen Phase-2-Entwurf),
weil die Trailing-Stop-Felder (stop_price_current/extreme_price_since_entry/trail_distance) laut
Phase 3 auf Trade modelliert sind, nicht auf Position.
"""

from __future__ import annotations

from datetime import date

from .models import AmbiguousBarPolicy, Bar, ExecutionResult, Order, Trade


def simulate_entry(order: Order, bar: Bar) -> ExecutionResult:
    """1:1 aus simulateEntryFill() im Live-Code von WF17 ("Verarbeite Tage-Paket") uebersetzt.
    Praktisch identisch zu WF14s zone_touch_conservative (siehe Phase-1-Tabelle "Entry/Fill")."""
    touched = bar.low <= order.entry_zone_high and bar.high >= order.entry_zone_low
    if not touched:
        return ExecutionResult(filled=False)
    if order.entry_zone_low <= bar.open <= order.entry_zone_high:
        return ExecutionResult(filled=True, price=bar.open, ambiguous=False)
    if bar.open < order.entry_zone_low:
        return ExecutionResult(filled=True, price=order.entry_zone_low, ambiguous=True)
    return ExecutionResult(filled=True, price=order.entry_zone_high, ambiguous=True)


def evaluate_exit(
    trade: Trade,
    bar: Bar,
    as_of: date,
    ambiguous_bar_policy: AmbiguousBarPolicy,
    opposite_signal_today: bool,
) -> ExecutionResult:
    """1:1 aus checkExit() im Live-Code von WF17 ("Verarbeite Tage-Paket") uebersetzt, inkl. des
    P17-6-Fixes (siehe FINAL_REVIEW.md): der Aufrufer MUSS trade.stop_price_current VOR der
    heutigen update_trailing_stop()-Nachfuehrung uebergeben (siehe Modul-Docstring).

    Same-Bar Stop+Target (stop_touched and target_touched) wird ueber ambiguous_bar_policy
    aufgeloest: default (== "conservative_stop_first") gewinnt der Stop, nur bei explizitem
    "conservative_target_first" gewinnt das Ziel - identische Semantik zu WF14
    (AMBIGUOUS_BAR_POLICY-Config, Default stop-first) und WF17 (ambiguousBarPolicyCode !== 2).
    """
    is_long = trade.direction == "long"
    stop_touched = bar.low <= trade.stop_price_current if is_long else bar.high >= trade.stop_price_current
    target_touched = bar.high >= trade.target_price if is_long else bar.low <= trade.target_price

    def gap_through_stop() -> bool:
        return bar.open < trade.stop_price_current if is_long else bar.open > trade.stop_price_current

    if stop_touched and target_touched:
        stop_first = ambiguous_bar_policy != "conservative_target_first"
        if stop_first:
            gapped = gap_through_stop()
            price = bar.open if gapped else trade.stop_price_current
            return ExecutionResult(exit=True, price=price, reason="stop_loss", ambiguous=True, gap_through_stop=gapped)
        return ExecutionResult(exit=True, price=trade.target_price, reason="take_profit", ambiguous=True, gap_through_stop=False)

    if stop_touched:
        gapped = gap_through_stop()
        price = bar.open if gapped else trade.stop_price_current
        return ExecutionResult(exit=True, price=price, reason="stop_loss", ambiguous=False, gap_through_stop=gapped)

    if target_touched:
        return ExecutionResult(exit=True, price=trade.target_price, reason="take_profit", ambiguous=False, gap_through_stop=False)

    if trade.time_stop_at is not None and as_of >= trade.time_stop_at:
        return ExecutionResult(exit=True, price=bar.close, reason="time_stop", ambiguous=False, gap_through_stop=False)

    if opposite_signal_today:
        return ExecutionResult(exit=True, price=bar.close, reason="opposite_signal", ambiguous=False, gap_through_stop=False)

    return ExecutionResult(exit=False)


def update_trailing_stop(trade: Trade, bar: Bar) -> Trade:
    """1:1 aus dem Trailing-Stop-Zweig von "Verarbeite Tage-Paket" (WF17) uebersetzt. Nur fuer
    Long/Short symmetrisch nachziehen, nie gegen die Trail-Distance zurueckziehen (der Vergleich
    `trail_stop > stop`/`trail_stop < stop` verhindert das). Der Aufrufer ist dafuer
    verantwortlich, diese Funktion NICHT aufzurufen, wenn evaluate_exit() fuer denselben Tag
    bereits `exit=True` zurueckgegeben hat (siehe Modul-Docstring)."""
    is_long = trade.direction == "long"
    extreme_price = trade.extreme_price_since_entry
    stop_price = trade.stop_price_current

    if is_long:
        if bar.high > extreme_price:
            extreme_price = bar.high
        trail_stop = extreme_price - trade.trail_distance
        if trail_stop > stop_price:
            stop_price = trail_stop
    else:
        if bar.low < extreme_price:
            extreme_price = bar.low
        trail_stop = extreme_price + trade.trail_distance
        if trail_stop < stop_price:
            stop_price = trail_stop

    return trade.model_copy(update={"extreme_price_since_entry": extreme_price, "stop_price_current": stop_price})
