# Wahrscheinlichkeiten und Kalibrierung (Welle 3, AP8)

Stand: 2026-08-01. Schema (`trading.probability_estimates`/`calibration_checks`, `sql/037`) vollständig funktionsfähig, **dormant** — 0 abgeschlossene Paper Trades zum Zeitpunkt dieser Migration.

## Grundprinzip

`probability_status` ist entweder `estimated` (Fallzahl ≥ `PROBABILITY_MIN_SAMPLE_SIZE`, Default 30) oder `insufficient_data` — **niemals** eine KI-Ersatzschätzung (Auftragsvorgabe wörtlich befolgt). Da `paper_trades` aktuell 0 geschlossene Zeilen hat, wäre JEDES Segment heute `insufficient_data` — korrektes, erwartbares Verhalten, kein Fehler.

## Segmentierung

`strategy × direction × market_regime × risk_bucket × evidence_bucket × time_horizon` — Auftragsvorgabe "Vermeide zu feine Segmentierung bei wenigen Fällen" wird über die Mindestfallzahl je vollständiger Segment-Kombination erzwungen: eine zu feine Kombination fällt automatisch unter die Mindestfallzahl und bleibt `insufficient_data`, ohne dass eine separate Grobheits-Heuristik nötig ist.

`risk_bucket`/`evidence_bucket`: geplant als Terzile von `risk_score`/`evidence_confidence` (Welle 2, AP4) — `niedrig`/`mittel`/`hoch` — noch nicht mit echten Daten befüllt (keine Trades).

## Berechnungsverfahren (Mechanismus vollständig implementierbar, aber ungetestet mangels Daten)

- **p_win**: Anteil `net_pnl > 0` im Segment.
- **p_positive_return**: identisch zu p_win (Namensklarheit für den Auftrags-Wortlaut).
- **p_target_before_stop**: Anteil `exit_reason='target_reached'` unter allen `IN ('target_reached','stop_loss')`-Exits.
- **expected_value_r**: Mittelwert `realized_r_multiple` im Segment.
- **Brier Score**: `mean((predicted_probability - observed_outcome)^2)` je Bucket.
- **Calibration Error**: `abs(predicted_probability - observed_frequency)`.
- **Konfidenzintervall**: Wilson-Score-Intervall (robust bei kleinen Fallzahlen, keine Normalverteilungsannahme).

## Warum kein Mechanismus-Workflow in Welle 3 gebaut wurde

Gleiche Priorisierungsentscheidung wie beim Backtesting-Modul (`docs/BACKTESTING_UND_WALK_FORWARD.md`): ohne abgeschlossene Trades gibt es nichts zu berechnen — ein Workflow, der heute liefe, würde nur `insufficient_data`-Zeilen erzeugen. Das Schema und die Formeln sind vollständig spezifiziert (oben), die eigentliche Berechnung sollte gebaut werden, sobald `paper_trades` eine dreistellige Zahl abgeschlossener Trades zeigt.

## Status

- 🟡 Schema + Formeln vollständig spezifiziert, Berechnungs-Workflow noch nicht gebaut (bewusste Priorisierung).
- 🔴 Keine Daten zum Testen — erwartungsgemäß.
